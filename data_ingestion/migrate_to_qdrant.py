import os
import sqlite3
import hashlib
import uuid
import time
import requests
import re
import chromadb
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Config
CHROMA_PATH = r"C:\Users\P\Documents\finnai\data\nifty_top20\chromaqwen0-6bembedding"
CHROMA_COLLECTION = "qwen3_0_6bembeddingreports"
QDRANT_COLLECTION = "ollama_bge_m3_nifty20"
PROGRESS_DB = os.path.join(os.path.dirname(__file__), "migration_progress.db")

QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]

OLLAMA_BATCH_SIZE = 32  # Local inference batch size
OLLAMA_URL = "http://localhost:11434/api/embed"

def setup_progress_db():
    conn = sqlite3.connect(PROGRESS_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            chroma_id TEXT PRIMARY KEY,
            migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def get_migrated_ids(conn):
    cur = conn.cursor()
    cur.execute("SELECT chroma_id FROM progress")
    return set(r[0] for r in cur.fetchall())

def mark_as_migrated(conn, chroma_ids):
    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO progress (chroma_id) VALUES (?)", [(cid,) for cid in chroma_ids])
    conn.commit()

def make_paths_dynamic(text: str) -> str:
    # Safely replace hardcoded Windows/Unix paths up to /visuals/ with {BASE_DIR}/visuals/
    # e.g. C:\Users\P\Documents\finnai\data\nifty_top20\visuals\HDFCBANK\... -> {BASE_DIR}/visuals/HDFCBANK/...
    return re.sub(r"(?i)c:[a-z0-9_\\\/\.\-]*?[\\/]visuals[\\/]", "{BASE_DIR}/visuals/", text)

def embed_with_ollama_with_retry(texts, max_retries=10, initial_delay=2.0):
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                OLLAMA_URL, 
                json={"model": "bge-m3", "input": texts},
                timeout=120
            )
            resp.raise_for_status()
            return resp.json()['embeddings']
        except Exception as e:
            print(f"\n[Error] Attempt {attempt+1} failed: {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
            delay *= 2
    raise Exception("Failed to embed after max retries")

def main():
    conn = setup_progress_db()
    
    # 1. Connect to Chroma and fetch all chunk references
    print("Connecting to Chroma...")
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    col = chroma.get_collection(name=CHROMA_COLLECTION)
    
    total_chroma_count = col.count()
    print(f"Total chunks in Chroma: {total_chroma_count}")
    
    # Check what's already migrated
    migrated_ids = get_migrated_ids(conn)
    print(f"Already migrated chunks: {len(migrated_ids)}")
    
    if len(migrated_ids) >= total_chroma_count:
        print("All chunks seem to be migrated already!")
        return

    # Load all chunks from Chroma to memory to filter
    print("Loading chunks from Chroma...")
    PAGE_SIZE = 5000
    offset = 0
    all_ids, all_docs, all_metas = [], [], []
    
    while True:
        page = col.get(limit=PAGE_SIZE, offset=offset, include=["documents", "metadatas"])
        n = len(page["ids"])
        if n == 0:
            break
        all_ids.extend(page["ids"])
        all_docs.extend(page["documents"])
        all_metas.extend(page["metadatas"])
        print(f"  Loaded {len(all_ids)}/{total_chroma_count} references...", end="\r")
        if n < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print()

    # Filter out migrated
    pending_indices = [i for i, cid in enumerate(all_ids) if cid not in migrated_ids]
    print(f"Chunks pending migration: {len(pending_indices)}")
    
    if not pending_indices:
        print("No pending chunks to migrate.")
        return

    # 2. Connect to Qdrant
    print("Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
    
    # Create collection if it doesn't exist.
    try:
        qdrant.get_collection(QDRANT_COLLECTION)
        print(f"Qdrant collection '{QDRANT_COLLECTION}' exists.")
    except Exception:
        print(f"Creating collection '{QDRANT_COLLECTION}' in Qdrant...")
        # Get one embedding to find size
        test_emb = embed_with_ollama_with_retry(["test text"])[0]
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=len(test_emb),
                distance=models.Distance.COSINE
            )
        )

    # 3. Migration Loop
    start_time = time.time()
    total_to_migrate = len(pending_indices)
    migrated_this_run = 0
    
    print(f"Starting migration of {total_to_migrate} chunks using batch size {OLLAMA_BATCH_SIZE}...")
    
    for start_idx in range(0, total_to_migrate, OLLAMA_BATCH_SIZE):
        batch_indices = pending_indices[start_idx : start_idx + OLLAMA_BATCH_SIZE]
        
        batch_ids = [all_ids[i] for i in batch_indices]
        batch_docs = [make_paths_dynamic(all_docs[i]) for i in batch_indices]
        batch_metas = [all_metas[i] for i in batch_indices]
        
        # Embed
        embeddings = embed_with_ollama_with_retry(batch_docs)
        
        # Prepare Qdrant points
        points = []
        for i, emb in enumerate(embeddings):
            # Same MD5 UUID conversion as testonline.py
            qdrant_id = str(uuid.UUID(hashlib.md5(batch_ids[i].encode("utf-8")).hexdigest()))
            payload = {"document": batch_docs[i]}
            if batch_metas[i]:
                payload.update(batch_metas[i])
                
            points.append(models.PointStruct(
                id=qdrant_id,
                vector=emb,
                payload=payload
            ))
            
        # Upsert
        qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points
        )
        
        # Record progress
        mark_as_migrated(conn, batch_ids)
        
        migrated_this_run += len(batch_ids)
        elapsed = time.time() - start_time
        rate = migrated_this_run / elapsed if elapsed > 0 else 0
        est_remaining = (total_to_migrate - migrated_this_run) / rate if rate > 0 else 0
        
        print(
            f"Migrated: {migrated_this_run}/{total_to_migrate} | "
            f"Speed: {rate:.1f} chunks/sec | "
            f"ETA: {est_remaining/60:.1f} mins", 
            end="\r"
        )
        
    print(f"\nMigration completed successfully! Total chunks migrated this run: {migrated_this_run}")
    
    # 4. Final Verification
    qdrant_count = qdrant.get_collection(QDRANT_COLLECTION).points_count
    print(f"Verification:\n- Chroma total: {total_chroma_count}\n- Qdrant total points: {qdrant_count}")

if __name__ == "__main__":
    main()


