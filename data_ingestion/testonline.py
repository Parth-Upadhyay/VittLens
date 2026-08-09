"""
test_reembed.py — Fixed Qdrant search for client 1.18.0
"""

import os
import requests
from qdrant_client import QdrantClient
from qdrant_client.http import models
import chromadb
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

CHROMA_PATH = r"C:\Users\P\Documents\finnai\data\nifty_top20\chromaqwen0-6bembedding"
COLLECTION = "qwen3_0_6bembeddingreports"

COHERE_API_KEY = os.environ["COHERE_API_KEY"]
QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]

# Connect
print("Connecting to Chroma...")
chroma = chromadb.PersistentClient(path=CHROMA_PATH)
col = chroma.get_collection(name=COLLECTION)

# Paginated get
PAGE_SIZE = 500
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
    print(f"  Fetched {len(all_ids)} so far...", end="\r")
    if n < PAGE_SIZE:
        break
    offset += PAGE_SIZE

print(f"\nTotal chunks: {len(all_ids)}")

# Pick test chunks
test_indices = [0, 1, 2, 3, 4]
for i, m in enumerate(all_metas):
    if m.get("is_visual") == "true" and len(test_indices) < 10:
        test_indices.append(i)
        if len(test_indices) == 10:
            break

test_docs = [all_docs[i] for i in test_indices]
test_metas = [all_metas[i] for i in test_indices]
test_ids = [all_ids[i] for i in test_indices]

print("Test chunks:")
for i, (doc, meta) in enumerate(zip(test_docs, test_metas)):
    preview = doc[:80].replace("\n", " ")
    vis = " [VISUAL]" if meta.get("is_visual") == "true" else ""
    print(f"  {i+1}. {preview}...{vis}")

# Embed with Cohere
print("\nEmbedding with Cohere...")
resp = requests.post(
    "https://api.cohere.com/v1/embed",
    headers={"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"},
    json={
        "texts": test_docs,
        "model": "embed-english-v3.0",
        "input_type": "search_document"
    }
)
resp.raise_for_status()
embeddings = resp.json()["embeddings"]
print(f"Got {len(embeddings)} embeddings from Cohere.")

print("Connecting to Qdrant...")
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Convert Chroma IDs to Qdrant-compatible UUIDs
import hashlib
import uuid

points = []
for i, emb in enumerate(embeddings):
    qdrant_id = str(uuid.UUID(hashlib.md5(test_ids[i].encode("utf-8")).hexdigest()))
    payload = {"document": test_docs[i]}
    if test_metas[i]:
        payload.update(test_metas[i])
        
    points.append(models.PointStruct(
        id=qdrant_id,
        vector=emb,
        payload=payload
    ))

print(f"Upserting {len(points)} points to Qdrant...")

# Create collection if it doesn't exist
try:
    qdrant.get_collection(collection_name=COLLECTION)
except Exception:
    print(f"Creating collection {COLLECTION}...")
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(
            size=len(embeddings[0]),
            distance=models.Distance.COSINE
        )
    )

qdrant.upsert(
    collection_name=COLLECTION,
    points=points
)
print("Done!")
