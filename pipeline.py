"""
FinnAI Unified Pipeline — unified_pipeline.py
Handles: text extraction, table detection, chart detection, OCR, validation,
captioning, embedding, and storage in ONE process.

KEY FEATURES:
    • phi4-mini for ALL validation (tables + charts) with strict single-item prompts
    • Health monitor tracks last 10 responses; auto-restarts phi4-mini if
      quality drops below 50%
    • PyMuPDF fallback for corrupted PDFs
    • 3-pass chart capture (raster, vector, full-page fallback)
    • Sequential per-file processing: text/tables first, then charts
    • One embedding batch per file for efficiency

Run:
    python unified_pipeline.py --workers 4
    python unified_pipeline.py --fresh --yes
"""

import argparse
import io
import re
import sqlite3
import collections
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz
import pytesseract
from PIL import Image, ImageOps
import pdfplumber
import pandas as pd

import common as C

pytesseract.pytesseract.tesseract_cmd = C.TESSERACT_CMD

# ═══════════════════════════════════════════════════════════
# PHI4-MINI HEALTH MONITOR
# Tracks response quality and forces restart if model deteriorates
# ═══════════════════════════════════════════════════════════
_phi4_health = collections.deque(maxlen=10)

def _phi4_is_clean(response: str) -> bool:
    """True if response is exactly YES or NO (allowing whitespace)."""
    return bool(re.fullmatch(r'\s*(YES|NO)\s*', response.strip().upper()))

def _phi4_track_health(is_good: bool):
    """Force restart phi4-mini if < 50% of last 10 responses were clean."""
    _phi4_health.append(is_good)
    if len(_phi4_health) >= 5:
        good = sum(_phi4_health)
        total = len(_phi4_health)
        ratio = good / total
        if ratio < 0.5:
            print(f"\n    [phi4-health] DETERIORATING — {good}/{total} clean responses. "
                  f"Forcing model restart...")
            C._force_restart_ollama(C.VALIDATOR_MODEL)
            _phi4_health.clear()

def _phi4_strict_validate(prompt: str, system_msg: str, context: str) -> bool:
    """
    Single-shot phi4 validation with health monitoring.
    Returns True (keep) / False (reject). Garbled responses default to YES.
    """
    def _call():
        import ollama
        return ollama.chat(
            model=C.VALIDATOR_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.0, "num_predict": 5},
        )

    # Try once; if Ollama throws, restart and retry
    try:
        with C._ollama_gpu_gate:
            resp = _call()
    except Exception as e:
        print(f"    [phi4] '{context}' failed: {e}. Restarting model...")
        C._force_restart_ollama(C.VALIDATOR_MODEL)
        _phi4_health.clear()
        with C._ollama_gpu_gate:
            resp = _call()

    raw = resp["message"]["content"].strip().upper()
    is_good = _phi4_is_clean(raw)
    _phi4_track_health(is_good)

    if not is_good:
        print(f"    [phi4] '{context}' garbled ('{raw[:30]}...'), treating as YES")
        return True  # permissive: keep data rather than lose it

    return "YES" in raw


# ═══════════════════════════════════════════════════════════
# TABLE VALIDATION (strict single-item)
# ═══════════════════════════════════════════════════════════
def validate_table_single(preview: str, page: int, tidx: int) -> bool:
    prompt = (
        "You are a validator. Look at this table from a financial report.\n"
        "Reply with exactly ONE word: YES or NO.\n"
        "YES = meaningful financial table (P&L, balance sheet, ratios).\n"
        "NO = decorative, empty, or non-financial.\n\n"
        f"Table (page {page}):\n{preview}\n\n"
        "Your answer (YES or NO):"
    )
    return _phi4_strict_validate(
        prompt,
        "Reply with exactly one word: YES or NO. No numbers, no explanations.",
        f"table_p{page}_t{tidx}"
    )


# ═══════════════════════════════════════════════════════════
# CHART VALIDATION (strict single-item)
# ═══════════════════════════════════════════════════════════
def validate_chart_single(ocr_text: str, page: int, tag: str) -> bool:
    prompt = (
        "You are a validator. Look at this OCR text from a chart image.\n"
        "Reply with exactly ONE word: YES or NO.\n"
        "YES = real financial chart/graph with numbers, metrics, or trends.\n"
        "NO = logo, photo, decorative, or empty.\n\n"
        f"Image (page {page}):\n{ocr_text[:400] or '[no OCR text]'}\n\n"
        "Your answer (YES or NO):"
    )
    return _phi4_strict_validate(
        prompt,
        "Reply with exactly one word: YES or NO. No numbers, no explanations.",
        f"chart_p{page}_{tag}"
    )


# ═══════════════════════════════════════════════════════════
# GROQ CAPTIONING (unchanged)
# ═══════════════════════════════════════════════════════════
def groq_caption_chart(ocr_text: str, meta: dict) -> str:
    prompt = (
        "You are a financial analyst. The text below is OCR output from a chart "
        "in a financial report. It may be messy or fragmented. "
        "Describe what the chart shows in 2-3 sentences. "
        "Include: company name, metric names, time period, and key numbers if visible. "
        "Do not hallucinate data not present in the OCR.\n\n"
        f"Company: {meta['company']} | FY: {meta['fy']} | Quarter: {meta['quarter']}\n"
        f"OCR Text:\n{ocr_text[:800]}\n"
    )

    def _call(client):
        resp = client.chat.completions.create(
            model=C.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=150,
            timeout=15,
        )
        return resp.choices[0].message.content.strip()

    return C.call_groq_with_restart(_call, context="chart_caption")


# ═══════════════════════════════════════════════════════════
# CHART CAPTURE (3-pass from chart_pipeline.py)
# ═══════════════════════════════════════════════════════════
CHART_KEYWORD_RE = re.compile(
    r'\b(revenue|profit|loss|growth|margin|ebitda|eps|crore|cr\.?|lakh|mn|bn|'
    r'percent|%|quarter|fy\d{2}|chart|graph|fig(?:ure)?|trend|ratio|market\s*share)\b',
    re.IGNORECASE
)

def _capture_raster_images(page: fitz.Page, doc: fitz.Document, page_num: int) -> list:
    out = []
    for img_idx, img in enumerate(page.get_images(full=True), 1):
        xref = img[0]
        try:
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            img_pil = Image.open(io.BytesIO(pix.tobytes("png")))
        except Exception:
            continue
        w, h = img_pil.size
        if w < 100 or h < 100 or w > 4000 or h > 4000:
            continue
        out.append((page_num, f"r{img_idx}", img_pil))
    return out

def _cluster_drawing_rects(page: fitz.Page, min_area: float = 4000) -> list:
    try:
        drawings = page.get_drawings()
    except Exception:
        return []
    rects = []
    for d in drawings:
        r = d.get("rect")
        if r is None:
            continue
        if r.width * r.height >= min_area and r.width > 60 and r.height > 60:
            rects.append(r)
    if not rects:
        return []
    rects.sort(key=lambda r: (r.y0, r.x0))
    merged = []
    for r in rects:
        placed = False
        for i, m in enumerate(merged):
            if r.intersects(m + (-15, -15, 15, 15)):
                merged[i] = fitz.Rect(
                    min(m.x0, r.x0), min(m.y0, r.y0),
                    max(m.x1, r.x1), max(m.y1, r.y1),
                )
                placed = True
                break
        if not placed:
            merged.append(r)
    return [m for m in merged if m.width > 80 and m.height > 80]

def _capture_vector_charts(page: fitz.Page, page_num: int) -> list:
    out = []
    rects = _cluster_drawing_rects(page)
    for i, rect in enumerate(rects, 1):
        try:
            pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2))
            img_pil = Image.open(io.BytesIO(pix.tobytes("png")))
        except Exception:
            continue
        out.append((page_num, f"v{i}", img_pil))
    return out

def _capture_full_page_fallback(page: fitz.Page, page_num: int, already_found: bool, page_text: str) -> list:
    if already_found:
        return []
    if not CHART_KEYWORD_RE.search(page_text or ""):
        return []
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_pil = Image.open(io.BytesIO(pix.tobytes("png")))
    except Exception:
        return []
    return [(page_num, "fullpage", img_pil)]

def _ocr(img_pil: Image.Image) -> str:
    try:
        gray = ImageOps.grayscale(img_pil)
        gray = ImageOps.autocontrast(gray)
        return pytesseract.image_to_string(gray, config='--psm 6').strip()
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════
# TABLE STORAGE (from text_pipeline.py)
# ═══════════════════════════════════════════════════════════
def store_table(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str):
    try:
        df = df.dropna(axis=1, how='all')
        df.columns = C.make_unique_columns(df.columns)
        with C._db_lock:
            df.to_sql(table_name, conn, if_exists="replace", index=False)
    except Exception as e:
        print(f"    Table store failed '{table_name}': {e}")

def make_table_summary_chunk(tbl_name: str, df: pd.DataFrame, meta: dict, page_num: int) -> dict:
    safe_cols = C.make_unique_columns(df.columns)
    cols = ", ".join(safe_cols)
    sample_rows = []
    for _, row in df.head(2).iterrows():
        row_dict = {k: v for k, v in row.items() if v is not None}
        sample_rows.append(str(row_dict))
    summary_text = (
        f"[TABLE REFERENCE] {tbl_name}\n"
        f"Company: {meta['company']} | FY: {meta['fy']} | Quarter: {meta['quarter']} | Page: {page_num}\n"
        f"Columns: {cols}\n"
        f"Sample rows:\n"
    )
    for sr in sample_rows:
        summary_text += f"  {sr}\n"
    return {
        "text": summary_text,
        "metadata": {
            "company": meta["company"], "sector": meta["sector"],
            "doc_type": meta["doc_type"], "fy": meta["fy"],
            "quarter": meta["quarter"], "page": page_num,
            "section": f"TABLE:{tbl_name}", "file": meta["file_name"],
            "is_table_ref": "true", "sql_table": tbl_name,
        },
    }


# ═══════════════════════════════════════════════════════════
# PER-FILE UNIFIED PROCESSOR
# ═══════════════════════════════════════════════════════════
def process_one_file(pdf_path: Path, conn: sqlite3.Connection, col) -> dict:
    fp = str(pdf_path)
    meta = C.parse_metadata(pdf_path)
    safe_company = C.sanitize(meta['company'])
    safe_fy = C.sanitize(meta['fy'])
    fprint = C.file_fingerprint(fp)

    all_texts, all_metadatas, all_ids = [], [], []
    file_tables, file_skipped, file_charts = 0, 0, 0

    # ── TEXT + TABLES (pdfplumber with PyMuPDF fallback) ──
    candidate_tables = []
    page_texts = {}
    use_pdfplumber = True

    try:
        pdf = pdfplumber.open(pdf_path)
        total_pages = len(pdf.pages)
    except Exception as e:
        print(f"    pdfplumber failed: {e}, falling back to PyMuPDF...")
        use_pdfplumber = False
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            for page_num in range(1, total_pages + 1):
                page = doc[page_num - 1]
                page_texts[page_num] = C.clean_page_text(page.get_text() or "")
            doc.close()
        except Exception as e2:
            print(f"    PyMuPDF fallback also failed: {e2}")
            raise

    cur = conn.cursor()
    if use_pdfplumber:
        for page_num, page in enumerate(pdf.pages, 1):
            try:
                raw_text = C.clean_page_text(C.extract_text_with_timeout(page))
            except Exception as e:
                print(f"    WARNING: Page {page_num} extraction failed: {e}")
                raw_text = ""
            page_texts[page_num] = raw_text

            with C._db_lock:
                cur.execute("""
                    INSERT INTO master_registry
                        (sector, company, doc_type, fy, quarter, file_name, page_number, is_table)
                    VALUES (?,?,?,?,?,?,?,0)
                """, (meta["sector"], meta["company"], meta["doc_type"],
                      meta["fy"], meta["quarter"], meta["file_name"], page_num))
                reg_id = cur.lastrowid
                if raw_text:
                    cur.execute("INSERT INTO text_content (registry_id, raw_text) VALUES (?,?)",
                                (reg_id, raw_text))
                conn.commit()

            try:
                tables = page.extract_tables()
            except Exception:
                tables = []
            for t_idx, table in enumerate(tables, 1):
                if not table or len(table) < 2:
                    continue
                if not C.is_important_table(table):
                    file_skipped += 1
                    continue
                preview = C.format_table_preview(table, max_rows=3)
                candidate_tables.append((table, page_num, t_idx, preview))
        pdf.close()
    else:
        # PyMuPDF fallback: registry only, no tables
        for page_num, raw_text in page_texts.items():
            with C._db_lock:
                cur.execute("""
                    INSERT INTO master_registry
                        (sector, company, doc_type, fy, quarter, file_name, page_number, is_table)
                    VALUES (?,?,?,?,?,?,?,0)
                """, (meta["sector"], meta["company"], meta["doc_type"],
                      meta["fy"], meta["quarter"], meta["file_name"], page_num))
                reg_id = cur.lastrowid
                if raw_text:
                    cur.execute("INSERT INTO text_content (registry_id, raw_text) VALUES (?,?)",
                                (reg_id, raw_text))
                conn.commit()

    # Validate tables one-by-one with phi4-mini
    validated_tables = []
    for table, page_num, t_idx, preview in candidate_tables:
        if validate_table_single(preview, page_num, t_idx):
            validated_tables.append((table, page_num, t_idx))
        else:
            file_skipped += 1

    # Store validated tables
    for table, page_num, t_idx in validated_tables:
        header = table[0]
        rows = table[1:]
        if not any(header):
            header = [f"col_{i}" for i in range(len(rows[0]))]
        df = pd.DataFrame(rows, columns=header)
        tbl_name = f"{C.sanitize(meta['company'])}_{C.sanitize(meta['fy'])}_{fprint}_p{page_num}_t{t_idx}"
        store_table(conn, df, tbl_name)

        with C._db_lock:
            cur.execute("""
                INSERT INTO master_registry
                    (sector, company, doc_type, fy, quarter, file_name, page_number, sql_table_name, is_table)
                VALUES (?,?,?,?,?,?,?,?,1)
            """, (meta["sector"], meta["company"], meta["doc_type"],
                  meta["fy"], meta["quarter"], meta["file_name"], page_num, tbl_name))
            conn.commit()
        file_tables += 1

        bridge = make_table_summary_chunk(tbl_name, df, meta, page_num)
        all_texts.append(bridge["text"])
        all_metadatas.append(bridge["metadata"])
        all_ids.append(C.chunk_id(fp, page_num, f"TABLE_{tbl_name}", 0))

    # Text hybrid chunks
    for page_num, raw_text in page_texts.items():
        for i, ch in enumerate(C.hybrid_chunk(raw_text, meta, page_num)):
            all_texts.append(ch["text"])
            all_metadatas.append(ch["metadata"])
            all_ids.append(C.chunk_id(fp, page_num, ch["metadata"]["section"], i))

    # ── CHARTS (PyMuPDF 3-pass) ──
    doc = fitz.open(pdf_path)
    chart_candidates = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_num = page_index + 1

        raster = _capture_raster_images(page, doc, page_num)
        vector = _capture_vector_charts(page, page_num)
        found_any = bool(raster or vector)

        page_text = page.get_text() or ""
        fallback = _capture_full_page_fallback(page, page_num, found_any, page_text)

        for tup in raster + vector + fallback:
            chart_candidates.append(tup)

    # OCR + validate charts one-by-one with phi4-mini
    chart_survivors = []
    for page_num, tag, img_pil in chart_candidates:
        ocr_text = _ocr(img_pil)
        if len(ocr_text) < 15 and not re.search(r'\d{2,}', ocr_text):
            continue
        if validate_chart_single(ocr_text, page_num, tag):
            chart_survivors.append((page_num, tag, ocr_text, img_pil))
            file_charts += 1

    doc.close()

    # Save chart PNGs + caption + embed
    for page_num, tag, ocr_text, img_pil in chart_survivors:
        caption = groq_caption_chart(ocr_text, meta)
        chart_dir = Path(C.CHROMA_PATH).parent / "charts" / safe_company / safe_fy
        chart_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{safe_company}_{safe_fy}_{fprint}_p{page_num}_{tag}.png"
        chart_path = chart_dir / fname
        img_pil.save(chart_path)

        chunk_text = (
            f"[CHART IMAGE] {fname}\n"
            f"Company: {meta['company']} | FY: {meta['fy']} | "
            f"Quarter: {meta['quarter']} | Page: {page_num}\n"
            f"Description: {caption}\n"
            f"Raw OCR: {ocr_text[:300]}\n"
            f"Image Path: {chart_path}"
        )
        metadata = {
            "company": meta["company"], "sector": meta["sector"],
            "doc_type": meta["doc_type"], "fy": meta["fy"],
            "quarter": meta["quarter"], "page": page_num,
            "section": f"CHART:{fname}", "file": meta["file_name"],
            "is_chart": "true", "chart_path": str(chart_path),
        }
        all_texts.append(chunk_text)
        all_metadatas.append(metadata)
        all_ids.append(C.chunk_id(fp, page_num, metadata["section"], 0))

    # ── EMBED + UPSERT (one batch per file) ──
    if all_texts:
        embeddings = C.embed_parallel(all_texts)
        with C._db_lock:
            for start in range(0, len(all_texts), C.EMBED_BATCH):
                end = start + C.EMBED_BATCH
                C.chroma_upsert_with_retry(
                    col,
                    ids=all_ids[start:end],
                    embeddings=embeddings[start:end],
                    documents=all_texts[start:end],
                    metadatas=all_metadatas[start:end],
                )

    # Ingestion log
    with C._db_lock:
        cur.execute(
            "INSERT OR REPLACE INTO unified_ingestion_log VALUES (?,?,?,?,?)",
            (fp, datetime.now().isoformat(), len(all_texts), file_tables, file_charts),
        )
        conn.commit()

    return {
        "meta": meta, "chunks": len(all_texts),
        "tables_kept": file_tables, "tables_skipped": file_skipped,
        "charts_kept": file_charts,
    }


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def process_all(base_folder=C.BASE_FOLDER, db_path=C.DB_PATH, chroma_path=C.CHROMA_PATH,
                workers=4, fresh=False, yes=False):
    if fresh:
        C.confirm_and_wipe(db_path, chroma_path, skip_confirm=yes)
    else:
        print("Resuming from previous run (use --fresh to start over)")

    C.verify_ollama_model()
    C.verify_groq()
    C.print_concurrency_settings("unified_pipeline", workers)

    base = Path(base_folder)
    conn = C.setup_database(db_path)
    col = C.get_collection()
    cur = conn.cursor()

    # Add unified log table if not exists
    with C._db_lock:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS unified_ingestion_log (
                file_path   TEXT PRIMARY KEY,
                ingested_at TEXT,
                chunks      INTEGER,
                tables_kept INTEGER,
                charts_kept INTEGER
            )
        """)
        conn.commit()

    pdf_files = sorted(base.rglob("*.pdf"))
    pending = [p for p in pdf_files if not C.already_ingested(cur, "unified_ingestion_log", str(p))]
    print(f"\nFound {len(pdf_files)} PDFs, {len(pending)} pending")
    print(f"Running with {workers} concurrent workers")
    print(f"{'─'*60}")

    grand_chunks = grand_tables = skipped_tables = grand_charts = 0
    failures = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process_one_file, p, conn, col): p for p in pending}
        done_count = 0
        for future in as_completed(futures):
            pdf_path = futures[future]
            done_count += 1
            try:
                result = future.result()
                grand_chunks += result["chunks"]
                grand_tables += result["tables_kept"]
                skipped_tables += result["tables_skipped"]
                grand_charts += result["charts_kept"]
                m = result["meta"]
                print(f"[{done_count}/{len(pending)}] OK  {m['company']} | {m['doc_type']} | {m['fy']} "
                      f"← {m['file_name']}  ({result['chunks']} chunks, {result['tables_kept']} tables, {result['charts_kept']} charts)")
            except SystemExit:
                print(f"\nCRASHING: fatal Ollama/Groq failure on {pdf_path.name}")
                conn.close()
                raise
            except Exception as e:
                print(f"[{done_count}/{len(pending)}] FAILED {pdf_path.name}: {e}")
                failures.append((str(pdf_path), str(e)))

    conn.close()
    print(f"\n{'═'*60}")
    print(f"Done | {grand_chunks} chunks | {grand_tables} tables | {skipped_tables} skipped | {grand_charts} charts")
    if failures:
        print(f"\n{len(failures)} file(s) failed:")
        for fp, err in failures:
            print(f"  - {fp}: {err}")
    print(f"SQLite → {db_path}")
    print(f"Chroma → {chroma_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--workers", type=int, default=4,
                    help="CPU-bound file workers. Safe to raise on multi-core.")
    ap.add_argument("--gpu-concurrency", type=int, default=None)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    if args.gpu_concurrency is not None:
        C.OLLAMA_CONCURRENCY = args.gpu_concurrency
        C._ollama_gpu_gate = __import__("threading").Semaphore(args.gpu_concurrency)

    if args.selftest:
        C.verify_ollama_model()
        C.verify_groq()
        print("Self-test passed.")
    else:
        process_all(workers=args.workers, fresh=args.fresh, yes=args.yes)