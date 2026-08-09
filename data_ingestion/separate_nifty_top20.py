"""
separate_nifty_top20.py
════════════════════════════════════════════════════════════════════════
Pulls EVERYTHING related to your NIFTY-Top-20 companies out of the full
FinnAI stores into one self-contained folder — vectors, documents, full
metadata, visual PNGs (+ their own metadata sidecars), and the matching
SQLite rows. Nothing in the original stores is touched.

Because Qdrant's free tier is storage-capped, this script can also push
the matched vectors + payloads straight into a Qdrant collection instead
of (or in addition to) writing a local ChromaDB copy — so you're not
paying disk twice for something that's headed to Qdrant anyway.

Produces, under --dest-root:
    <chroma-folder>/            local ChromaDB copy (unless --skip-local-chroma)
    visuals/<company>/<fy>/*.png              the image files
    visuals/<company>/<fy>/*.json             one metadata sidecar per image
                                               (company, fy, quarter, page,
                                               visual_type, caption, OCR text,
                                               original chroma id, etc.)
    tables.db                                  filtered SQLite (same schema)
    metadata_manifest.json                     everything in one index:
                                               run info, full list of every
                                               chunk's id + metadata (text
                                               and visual), sqlite counts,
                                               qdrant upload result

Usage:
    # local-only copy (Chroma + visuals + sqlite + manifest)
    python separate_nifty_top20.py

    # see counts first, write nothing
    python separate_nifty_top20.py --dry-run

    # skip the local Chroma copy, push straight to Qdrant Cloud free tier
    python separate_nifty_top20.py --skip-local-chroma --to-qdrant \\
        --qdrant-url "https://xxxx.cloud.qdrant.io:6333" \\
        --qdrant-api-key "your-api-key" \\
        --qdrant-collection nifty_top20

    # custom company list / dest folder
    python separate_nifty_top20.py --companies "HDFC Bank,Reliance Industries"
    python separate_nifty_top20.py --dest-root "C:\\Users\\P\\Documents\\finnai\\data\\nifty_top20"

Run it from the same folder as common.py (it imports common.py for the
CHROMA_PATH / DB_PATH config, sanitize(), and parse_metadata()).

If you're pushing to Qdrant, install the client first:
    pip install qdrant-client --break-system-packages
════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import chromadb

import common as C

# ═══════════════════════════════════════════════════════════
# DEFAULT NIFTY TOP 20 (by free-float weightage, NSE, ~mid-2026)
# Edit this list any time — weights get rebalanced by NSE every
# Jan 31 / Jul 31, and inclusions do occasionally change.
# Names below match exactly what common.py's _normalize_company() /
# _COMPANY_FOLDER_MAP produces, since that's what's stored as
# metadata["company"] in Chroma and the `company` column in SQLite.
# ═══════════════════════════════════════════════════════════
NIFTY_TOP_20 = [
    "Reliance Industries",
    "HDFC Bank",
    "Bharti Airtel",
    "ICICI Bank",
    "State Bank of India",
    "Tata Consultancy Services",
    "Bajaj Finance",
    "Larsen & Toubro",
    "Hindustan Unilever",
    "Sun Pharma",
    "Maruti Suzuki",
    "Infosys",
    "Adani Enterprises",
    "Adani Ports & SEZ",
    "Axis Bank",
    "Titan Company",
    "Mahindra & Mahindra",
    "Kotak Mahindra Bank",
    "ITC",
    "UltraTech Cement",
]

# Stable namespace for turning Chroma's md5-hex ids into Qdrant-legal
# UUID point ids (Qdrant only accepts unsigned ints or UUIDs).
_QDRANT_ID_NAMESPACE = uuid.UUID("6f6e6f74-6f6e-6f74-6f6e-6f746f6e6f74")


def _to_qdrant_id(chroma_id: str) -> str:
    return str(uuid.uuid5(_QDRANT_ID_NAMESPACE, chroma_id))


# ═══════════════════════════════════════════════════════════
# 1. FETCH MATCHING CHUNKS FROM CHROMA (shared by every downstream step)
# ═══════════════════════════════════════════════════════════
def fetch_matching_chunks(companies: list, page_size: int = 300) -> dict:
    print(f"\n[chroma] source : {C.CHROMA_PATH}")
    client = chromadb.PersistentClient(path=C.CHROMA_PATH)
    col = client.get_collection(name=C.COLLECTION)

    # Pulling everything in one get() call makes Chroma's SQLite backend
    # bind one variable per MATCHED row internally, which blows past
    # SQLite's variable limit on large collections ("too many SQL
    # variables"). Paging with limit/offset keeps each call small.
    where = {"company": {"$in": companies}}
    ids, embeddings, documents, metadatas = [], [], [], []
    offset = 0
    while True:
        page = col.get(
            where=where,
            limit=page_size,
            offset=offset,
            include=["embeddings", "documents", "metadatas"],
        )
        n_page = len(page["ids"])
        if n_page == 0:
            break
        ids.extend(page["ids"])
        embeddings.extend(page["embeddings"])
        documents.extend(page["documents"])
        metadatas.extend(page["metadatas"])
        print(f"    fetched {len(ids)} so far...", end="\r")
        if n_page < page_size:
            break
        offset += page_size

    print(f"\n[chroma] matched {len(ids)} chunks across {len(companies)} companies")
    return {"ids": ids, "embeddings": embeddings, "documents": documents, "metadatas": metadatas}


def write_local_chroma_copy(result: dict, dest_chroma_path: Path, dry_run: bool = False) -> int:
    ids = result["ids"]
    n = len(ids)
    print(f"[chroma] local copy dest : {dest_chroma_path}")

    if n == 0:
        print("[chroma] nothing to copy, skipping write")
        return 0
    if dry_run:
        print("[chroma] --dry-run set, not writing")
        return n

    dest_chroma_path.mkdir(parents=True, exist_ok=True)
    dst_client = chromadb.PersistentClient(path=str(dest_chroma_path))
    dst_col = dst_client.get_or_create_collection(
        name=C.COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    embeddings, documents, metadatas = result["embeddings"], result["documents"], result["metadatas"]
    batch = C.EMBED_BATCH
    for start in range(0, n, batch):
        end = start + batch
        dst_col.upsert(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        print(f"    upserted {min(end, n)}/{n}", end="\r")
    print()
    print(f"[chroma] local copy done -> {dest_chroma_path}")
    return n


# ═══════════════════════════════════════════════════════════
# 2. PUSH DIRECTLY TO QDRANT (for the free-tier destination)
# ═══════════════════════════════════════════════════════════
def push_to_qdrant(result: dict, url: str, api_key: str, collection_name: str,
                    batch_size: int = 128, dry_run: bool = False) -> dict:
    ids, embeddings = result["ids"], result["embeddings"]
    documents, metadatas = result["documents"], result["metadatas"]
    n = len(ids)
    print(f"\n[qdrant] target collection : {collection_name}")
    print(f"[qdrant] points to upload  : {n}")

    if n == 0:
        print("[qdrant] nothing to upload, skipping")
        return {"uploaded": 0, "collection": collection_name}
    if dry_run:
        print("[qdrant] --dry-run set, not uploading")
        return {"uploaded": 0, "collection": collection_name, "dry_run": True}

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
    except ImportError:
        raise SystemExit(
            "qdrant-client not installed. Run:\n"
            "    pip install qdrant-client --break-system-packages"
        )

    client = QdrantClient(url=url, api_key=api_key)
    vector_size = len(embeddings[0])

    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        print(f"[qdrant] created collection '{collection_name}' (dim={vector_size})")
    else:
        print(f"[qdrant] collection '{collection_name}' already exists, upserting into it")

    for start in range(0, n, batch_size):
        end = start + batch_size
        points = []
        for i in range(start, end):
            payload = dict(metadatas[i])
            payload["document"] = documents[i]
            payload["chroma_id"] = ids[i]
            points.append(
                models.PointStruct(
                    id=_to_qdrant_id(ids[i]),
                    vector=embeddings[i],
                    payload=payload,
                )
            )
        client.upsert(collection_name=collection_name, points=points)
        print(f"    uploaded {min(end, n)}/{n}", end="\r")
    print()
    print(f"[qdrant] done -> {url}  collection='{collection_name}'")
    return {"uploaded": n, "collection": collection_name, "url": url}


# ═══════════════════════════════════════════════════════════
# 3. VISUALS SPLIT (+ per-image metadata sidecar JSON)
# ═══════════════════════════════════════════════════════════
def split_visuals(result: dict, dest_visuals_path: Path, dry_run: bool = False):
    """
    Copies the matched companies' visual PNGs into dest_visuals_path,
    writes a metadata sidecar (with the caption + OCR text) next to each,
    and returns (n_copied, path_map) where path_map maps each image's
    ORIGINAL absolute path -> its NEW absolute path in the copy. The
    caller uses path_map to rewrite `visual_path` in the Chroma/Qdrant
    metadata too, so the split store is self-contained and doesn't
    silently point back at the original data folder.
    """
    src_visuals_dir = Path(C.CHROMA_PATH).parent / "visuals"
    print(f"\n[visuals] source : {src_visuals_dir}")
    print(f"[visuals] dest   : {dest_visuals_path}")

    if not src_visuals_dir.exists():
        print("[visuals] source dir does not exist, skipping")
        return 0, {}

    # Index visual-chunk metadata AND document text (the caption + OCR
    # live in the document, not the metadata) by their PNG's absolute
    # path, so we can drop a full sidecar JSON next to each copied image.
    ids, metadatas, documents = result["ids"], result["metadatas"], result["documents"]
    meta_by_visual_path = {}
    for cid, meta, doc in zip(ids, metadatas, documents):
        if meta.get("is_visual") == "true" and meta.get("visual_path"):
            meta_by_visual_path[str(Path(meta["visual_path"]))] = {
                **meta,
                "chroma_id": cid,
                "document": doc,  # includes the caption + raw OCR text
            }

    companies = {meta["company"] for meta in metadatas}
    safe_names = {C.sanitize(name): name for name in companies}

    copied_png = 0
    copied_json = 0
    path_map = {}  # original absolute path (str) -> new absolute path (str)

    for company_dir in src_visuals_dir.iterdir():
        if not company_dir.is_dir() or company_dir.name not in safe_names:
            continue

        real_name = safe_names[company_dir.name]
        dest_company_dir = dest_visuals_path / company_dir.name
        pngs = list(company_dir.rglob("*.png"))
        print(f"    {real_name}: {len(pngs)} PNG(s)")

        # Build the path map regardless of dry-run — it's just string math,
        # and the caller needs it to preview what the rewrite would look like.
        for src_png in pngs:
            rel = src_png.relative_to(company_dir)
            dest_png = dest_company_dir / rel
            path_map[str(src_png)] = str(dest_png)

        if dry_run:
            copied_png += len(pngs)
            continue

        if dest_company_dir.exists():
            shutil.rmtree(dest_company_dir)
        shutil.copytree(company_dir, dest_company_dir)
        copied_png += len(pngs)

        # write a sidecar .json next to each copied image, with
        # visual_path rewritten to point at the copy, not the original
        for src_png in pngs:
            rel = src_png.relative_to(company_dir)
            dest_png = dest_company_dir / rel
            meta = meta_by_visual_path.get(str(src_png))
            if meta is None:
                continue
            meta = {**meta, "visual_path": str(dest_png)}
            sidecar = dest_png.with_suffix(".json")
            with open(sidecar, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            copied_json += 1

    print(f"[visuals] {'would copy' if dry_run else 'copied'} {copied_png} PNG(s), "
          f"{copied_json} metadata sidecar(s)")
    return copied_png, path_map


# ═══════════════════════════════════════════════════════════
# 4. SQLITE (tables.db) SPLIT
# ═══════════════════════════════════════════════════════════
def split_sqlite(companies: list, dest_db_path: Path, dry_run: bool = False) -> dict:
    print(f"\n[sqlite] source : {C.DB_PATH}")
    print(f"[sqlite] dest   : {dest_db_path}")

    src = sqlite3.connect(C.DB_PATH)
    src.row_factory = sqlite3.Row
    scur = src.cursor()

    company_set = set(companies)
    counts = {}

    # ---- master_registry (has a `company` column directly) ----
    placeholders = ",".join("?" for _ in companies)
    try:
        scur.execute(
            f"SELECT * FROM master_registry WHERE company IN ({placeholders})",
            companies,
        )
        registry_rows = scur.fetchall()
    except sqlite3.OperationalError:
        registry_rows = []  # table doesn't exist in this DB
    registry_ids = [r["id"] for r in registry_rows]
    counts["master_registry"] = len(registry_rows)
    print(f"[sqlite] master_registry matched : {len(registry_rows)} rows")

    # ---- text_content (joined via registry_id) ----
    text_rows = []
    if registry_ids:
        id_placeholders = ",".join("?" for _ in registry_ids)
        scur.execute(
            f"SELECT * FROM text_content WHERE registry_id IN ({id_placeholders})",
            registry_ids,
        )
        text_rows = scur.fetchall()
    counts["text_content"] = len(text_rows)
    print(f"[sqlite] text_content matched    : {len(text_rows)} rows")

    # NOTE: unified_ingestion_log / text_ingestion_log / chart_ingestion_log
    # are intentionally NOT copied — they're just "has this file already
    # been processed" bookkeeping for the ingestion pipeline, keyed by
    # file_path, and aren't used for retrieval. Skipping them here.

    if dry_run:
        print("[sqlite] --dry-run set, not writing")
        src.close()
        return counts

    dest_db_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_db_path.exists():
        dest_db_path.unlink()
    dst = sqlite3.connect(dest_db_path)
    dst.execute("PRAGMA journal_mode=WAL;")
    dcur = dst.cursor()
    dcur.executescript("""
        CREATE TABLE IF NOT EXISTS master_registry (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            sector         TEXT,
            company        TEXT,
            doc_type       TEXT,
            fy             TEXT,
            quarter        TEXT,
            file_name      TEXT,
            page_number    INTEGER,
            sql_table_name TEXT,
            is_table       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS text_content (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            registry_id INTEGER,
            raw_text    TEXT,
            FOREIGN KEY(registry_id) REFERENCES master_registry(id)
        );
    """)

    if registry_rows:
        cols = registry_rows[0].keys()
        placeholders_i = ",".join("?" for _ in cols)
        dcur.executemany(
            f"INSERT INTO master_registry ({','.join(cols)}) VALUES ({placeholders_i})",
            [tuple(r[c] for c in cols) for r in registry_rows],
        )
    if text_rows:
        cols = text_rows[0].keys()
        placeholders_i = ",".join("?" for _ in cols)
        dcur.executemany(
            f"INSERT INTO text_content ({','.join(cols)}) VALUES ({placeholders_i})",
            [tuple(r[c] for c in cols) for r in text_rows],
        )

    dst.commit()
    dst.close()
    src.close()
    print(f"[sqlite] done -> {dest_db_path}")
    return counts


# ═══════════════════════════════════════════════════════════
# 5. MANIFEST — one JSON index of everything that was copied
# ═══════════════════════════════════════════════════════════
def write_manifest(dest_root: Path, companies: list, result: dict,
                    chroma_local_n, visuals_n, sql_counts, qdrant_result,
                    dry_run: bool = False):
    ids, metadatas = result["ids"], result["metadatas"]
    chunks_index = [
        {"chroma_id": cid, **meta} for cid, meta in zip(ids, metadatas)
    ]
    manifest = {
        "run_at": datetime.now().isoformat(),
        "companies": companies,
        "total_chunks_matched": len(ids),
        "text_chunks": sum(1 for m in metadatas if m.get("is_visual") != "true"),
        "visual_chunks": sum(1 for m in metadatas if m.get("is_visual") == "true"),
        "local_chroma_copy": chroma_local_n,
        "visual_pngs_copied": visuals_n,
        "sqlite_counts": sql_counts,
        "qdrant_upload": qdrant_result,
        "chunks": chunks_index,
    }
    if dry_run:
        print(f"\n[manifest] --dry-run set, not writing (would contain {len(ids)} chunk entries)")
        return

    dest_root.mkdir(parents=True, exist_ok=True)
    manifest_path = dest_root / "metadata_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n[manifest] written -> {manifest_path}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="Split NIFTY Top-20 data into a separate store")
    ap.add_argument(
        "--dest-root",
        default=str(Path(C.CHROMA_PATH).parent / "nifty_top20"),
        help="Folder to write the local chroma copy, visuals, tables.db, and manifest into",
    )
    ap.add_argument(
        "--companies",
        default=None,
        help="Comma-separated override list of company names (must match the normalized "
             "names used in common.py, e.g. 'HDFC Bank,Reliance Industries'). "
             "Defaults to the built-in NIFTY_TOP_20 list.",
    )
    ap.add_argument("--dry-run", action="store_true", help="Report counts only, write nothing")
    ap.add_argument("--skip-local-chroma", action="store_true",
                     help="Don't write a local ChromaDB copy (use this if you're only going to Qdrant)")
    ap.add_argument("--to-qdrant", action="store_true", help="Also upload vectors+payloads to Qdrant")
    ap.add_argument("--qdrant-url", default=None, help="e.g. https://xxxx.cloud.qdrant.io:6333")
    ap.add_argument("--qdrant-api-key", default=None)
    ap.add_argument("--qdrant-collection", default=None,
                     help=f"Defaults to '{{}}' (same as source collection name)".format(C.COLLECTION))
    ap.add_argument("--qdrant-batch-size", type=int, default=128)
    args = ap.parse_args()

    if args.to_qdrant and not (args.qdrant_url and args.qdrant_api_key):
        raise SystemExit("--to-qdrant requires --qdrant-url and --qdrant-api-key")

    companies = (
        [c.strip() for c in args.companies.split(",") if c.strip()]
        if args.companies
        else NIFTY_TOP_20
    )

    dest_root = Path(args.dest_root)
    dest_chroma_path = dest_root / Path(C.CHROMA_PATH).name
    dest_visuals_path = dest_root / "visuals"
    dest_db_path = dest_root / Path(C.DB_PATH).name

    print(f"{'─'*60}")
    print("NIFTY Top-20 split")
    print(f"Companies ({len(companies)}): {', '.join(companies)}")
    print(f"Dest root: {dest_root}")
    if args.dry_run:
        print("MODE: DRY RUN (no files written)")
    print(f"{'─'*60}")

    # One fetch, reused by the visuals step, the local-copy step, the
    # Qdrant step, and the manifest.
    result = fetch_matching_chunks(companies)

    # Copy visuals FIRST, so we get a path_map (original absolute path ->
    # new absolute path in the copy). We then rewrite `visual_path` in
    # every visual chunk's metadata before it goes into the Chroma copy
    # or Qdrant — otherwise the split store would silently keep pointing
    # back at your original data/visuals folder instead of its own copy.
    visuals_n, path_map = split_visuals(result, dest_visuals_path, dry_run=args.dry_run)

    remapped = 0
    for meta in result["metadatas"]:
        old_path = meta.get("visual_path")
        if old_path and old_path in path_map:
            meta["visual_path"] = path_map[old_path]
            remapped += 1
    if remapped:
        print(f"\n[visuals] rewrote visual_path -> new location in {remapped} chunk metadata entries")

    chroma_local_n = 0
    if not args.skip_local_chroma:
        chroma_local_n = write_local_chroma_copy(result, dest_chroma_path, dry_run=args.dry_run)
    else:
        print("\n[chroma] --skip-local-chroma set, no local copy written")

    qdrant_result = None
    if args.to_qdrant:
        qdrant_result = push_to_qdrant(
            result,
            url=args.qdrant_url,
            api_key=args.qdrant_api_key,
            collection_name=args.qdrant_collection or C.COLLECTION,
            batch_size=args.qdrant_batch_size,
            dry_run=args.dry_run,
        )

    sql_counts = split_sqlite(companies, dest_db_path, dry_run=args.dry_run)

    write_manifest(dest_root, companies, result, chroma_local_n, visuals_n,
                    sql_counts, qdrant_result, dry_run=args.dry_run)

    print(f"\n{'═'*60}")
    print("SUMMARY")
    print(f"  Chunks matched (chroma) : {len(result['ids'])}")
    if not args.skip_local_chroma:
        print(f"  Local chroma copy       : {chroma_local_n}")
    if args.to_qdrant:
        print(f"  Qdrant upload           : {qdrant_result}")
    print(f"  Visual PNGs copied      : {visuals_n}")
    for k, v in sql_counts.items():
        print(f"  SQLite {k:<24}: {v}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
