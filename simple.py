"""
FinnAI Sequential Pipeline — Text + Visual Pages Only
Groq for classification, phi4-mini for embeddings only.
Fast sampling: checks every 3rd page + page boundaries around visual hits.
"""

import argparse
import io
import re
import sqlite3
from pathlib import Path
from datetime import datetime

import fitz
import pytesseract
from PIL import Image, ImageOps
import pdfplumber

import common as C

pytesseract.pytesseract.tesseract_cmd = C.TESSERACT_CMD


# ═══════════════════════════════════════════════════════════
# OCR
# ═══════════════════════════════════════════════════════════
def _ocr(img_pil: Image.Image) -> str:
    try:
        gray = ImageOps.grayscale(img_pil)
        gray = ImageOps.autocontrast(gray)
        return pytesseract.image_to_string(gray, config='--psm 6').strip()
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════
# GROQ CLASSIFICATION — fast, reliable, no GPU wait
# ═══════════════════════════════════════════════════════════
def groq_classify_page(ocr_text: str, page_num: int) -> str:
    """
    Returns: TABLE, CHART, MIXED, or TEXT
    Uses Groq gpt-oss-20b — ~0.5s per call, no rate limit issues at this volume.
    """
    # Pre-filter: obvious text pages (no need to waste API call)
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
    if len(lines) < 4:
        return "TEXT"
    
    numeric_lines = sum(1 for l in lines if re.search(r'\d{3,}', l))
    if len(lines) > 10 and numeric_lines / len(lines) < 0.08:
        return "TEXT"
    
    prompt = (
        f"You are analyzing OCR text from a financial report page. "
        f"Classify this page into exactly ONE word: TABLE, CHART, MIXED, or TEXT.\n\n"
        f"TABLE = structured grid of financial data (rows/columns of numbers, like P&L, balance sheet, cash flow)\n"
        f"CHART = visual graph (bar chart, line graph, pie chart, with axes, legends, colored bars/lines)\n"
        f"MIXED = contains both a table and a chart on the same page\n"
        f"TEXT = mostly prose paragraphs, headers, or footnotes with no significant visual data\n\n"
        f"Page {page_num} OCR text:\n{ocr_text[:700]}\n\n"
        f"Classification (one word only):"
    )

    def _call(client):
        resp = client.chat.completions.create(
            model=C.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Reply with exactly one word: TABLE, CHART, MIXED, or TEXT. No explanations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=10,
            timeout=15,
        )
        return resp.choices[0].message.content.strip().upper()

    raw = C.call_groq_with_restart(_call, context=f"classify_p{page_num}")
    
    if "MIXED" in raw:
        return "MIXED"
    elif "TABLE" in raw:
        return "TABLE"
    elif "CHART" in raw:
        return "CHART"
    else:
        return "TEXT"


# ═══════════════════════════════════════════════════════════
# GROQ CAPTIONING
# ═══════════════════════════════════════════════════════════
def groq_caption(ocr_text: str, meta: dict, page_num: int, visual_type: str) -> str:
    prompt = (
        f"You are a financial analyst. This is OCR from a {visual_type} on page {page_num} "
        f"of {meta['company']}'s {meta['doc_type']} for {meta['fy']} {meta['quarter']}.\n"
        f"Describe what this {visual_type} shows in 2-3 sentences. "
        f"Include key metrics, time periods, and notable numbers if visible. "
        f"Do not hallucinate data not in the OCR.\n\n"
        f"OCR Text:\n{ocr_text[:900]}\n"
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

    return C.call_groq_with_restart(_call, context=f"caption_{visual_type}_p{page_num}")


# ═══════════════════════════════════════════════════════════
# FAST VISUAL DETECTION — sampled + boundary expansion
# ═══════════════════════════════════════════════════════════
def find_visual_pages(doc: fitz.Document, sample_every: int = 3) -> list:
    """
    Speed strategy:
    1. Sample every Nth page for classification (fast)
    2. When a visual page is found, check neighbors (N-1, N+1) — visuals often span 2-3 pages
    3. Render and OCR only pages that pass heuristic pre-filter
    
    Returns: list of (page_num, classification, img_pil, ocr_text)
    """
    total = len(doc)
    checked = set()
    visuals = []
    
    # Phase 1: Sample every Nth page
    sample_indices = list(range(0, total, sample_every))
    
    for idx in sample_indices:
        if idx in checked:
            continue
        checked.add(idx)
        
        page = doc[idx]
        page_num = idx + 1
        
        # Quick heuristic: page text length and number density
        page_text = page.get_text() or ""
        if len(page_text.strip()) < 40:
            continue
        
        # Render at low res for fast OCR (1.2x is enough for classification)
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
            img_pil = Image.open(io.BytesIO(pix.tobytes("png")))
        except Exception:
            continue
        
        ocr_text = _ocr(img_pil)
        
        # Classify with Groq
        classification = groq_classify_page(ocr_text, page_num)
        
        if classification == "TEXT":
            continue
        
        # Phase 2: Boundary expansion — check neighbors for multi-page visuals
        visuals.append((page_num, classification, img_pil, ocr_text))
        print(f"      Page {page_num}: {classification} (sampled)")
        
        # Check previous page (if not already checked)
        if idx - 1 >= 0 and (idx - 1) not in checked:
            checked.add(idx - 1)
            neighbor = doc[idx - 1]
            n_text = neighbor.get_text() or ""
            if len(n_text.strip()) >= 40:
                try:
                    n_pix = neighbor.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                    n_img = Image.open(io.BytesIO(n_pix.tobytes("png")))
                    n_ocr = _ocr(n_img)
                    n_class = groq_classify_page(n_ocr, idx)
                    if n_class != "TEXT":
                        visuals.append((idx, n_class, n_img, n_ocr))
                        print(f"      Page {idx}: {n_class} (neighbor)")
                except Exception:
                    pass
        
        # Check next page (if not already checked)
        if idx + 1 < total and (idx + 1) not in checked:
            checked.add(idx + 1)
            neighbor = doc[idx + 1]
            n_text = neighbor.get_text() or ""
            if len(n_text.strip()) >= 40:
                try:
                    n_pix = neighbor.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                    n_img = Image.open(io.BytesIO(n_pix.tobytes("png")))
                    n_ocr = _ocr(n_img)
                    n_class = groq_classify_page(n_ocr, idx + 2)
                    if n_class != "TEXT":
                        visuals.append((idx + 2, n_class, n_img, n_ocr))
                        print(f"      Page {idx + 2}: {n_class} (neighbor)")
                except Exception:
                    pass
    
    # Re-render visuals at higher quality (1.5x) for saving
    print(f"    Re-rendering {len(visuals)} visual pages at full quality...")
    high_quality = []
    for page_num, classification, _, ocr_text in visuals:
        page = doc[page_num - 1]
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_pil = Image.open(io.BytesIO(pix.tobytes("png")))
            high_quality.append((page_num, classification, img_pil, ocr_text))
        except Exception:
            pass
    
    return high_quality


# ═══════════════════════════════════════════════════════════
# PER-FILE PROCESSOR
# ═══════════════════════════════════════════════════════════
def process_one_file(pdf_path: Path, conn: sqlite3.Connection, col) -> dict:
    fp = str(pdf_path)
    meta = C.parse_metadata(pdf_path)
    safe_company = C.sanitize(meta['company'])
    safe_fy = C.sanitize(meta['fy'])
    fprint = C.file_fingerprint(fp)

    all_texts, all_metadatas, all_ids = [], [], []
    file_visuals = 0

    print(f"  Processing {pdf_path.name}...")

    # ── TEXT EXTRACTION ──
    page_texts = {}
    try:
        pdf = pdfplumber.open(pdf_path)
        for page_num, page in enumerate(pdf.pages, 1):
            try:
                raw_text = C.clean_page_text(C.extract_text_with_timeout(page))
            except Exception as e:
                print(f"    WARNING: Page {page_num} text extraction failed: {e}")
                raw_text = ""
            page_texts[page_num] = raw_text
        pdf.close()
    except Exception as e:
        print(f"    pdfplumber failed: {e}, using PyMuPDF...")
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(1, len(doc) + 1):
                page = doc[page_num - 1]
                page_texts[page_num] = C.clean_page_text(page.get_text() or "")
            doc.close()
        except Exception as e2:
            print(f"    PyMuPDF also failed: {e2}")
            raise

    # ── TEXT CHUNKS ──
    for page_num, raw_text in page_texts.items():
        for i, ch in enumerate(C.hybrid_chunk(raw_text, meta, page_num)):
            all_texts.append(ch["text"])
            all_metadatas.append(ch["metadata"])
            all_ids.append(C.chunk_id(fp, page_num, ch["metadata"]["section"], i))

    # ── VISUAL PAGES (sampled detection + boundary expansion) ──
    print(f"    Scanning for visual pages (sampled every 3rd page)...")
    doc = fitz.open(pdf_path)
    visual_pages = find_visual_pages(doc, sample_every=3)
    doc.close()

    # Save visual pages
    for page_num, classification, img_pil, ocr_text in visual_pages:
        file_visuals += 1

        caption = groq_caption(ocr_text, meta, page_num, classification)

        visual_dir = Path(C.CHROMA_PATH).parent / "visuals" / safe_company / safe_fy
        visual_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{safe_company}_{safe_fy}_{fprint}_p{page_num}_{classification.lower()}.png"
        visual_path = visual_dir / fname
        img_pil.save(visual_path)

        chunk_text = (
            f"[{classification.upper()} IMAGE] {fname}\n"
            f"Company: {meta['company']} | FY: {meta['fy']} | "
            f"Quarter: {meta['quarter']} | Page: {page_num}\n"
            f"Description: {caption}\n"
            f"Raw OCR: {ocr_text[:600]}\n"
            f"Image Path: {visual_path}"
        )
        metadata = {
            "company": meta["company"], "sector": meta["sector"],
            "doc_type": meta["doc_type"], "fy": meta["fy"],
            "quarter": meta["quarter"], "page": page_num,
            "section": f"{classification.upper()}:{fname}", "file": meta["file_name"],
            "is_visual": "true", "visual_type": classification.lower(),
            "visual_path": str(visual_path),
        }
        all_texts.append(chunk_text)
        all_metadatas.append(metadata)
        all_ids.append(C.chunk_id(fp, page_num, f"{classification.upper()}_{fname}", 0))

    # ── EMBED + UPSERT ──
    if all_texts:
        print(f"    Embedding {len(all_texts)} chunks...")
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

    # Log
    with C._db_lock:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO unified_ingestion_log VALUES (?,?,?,?,?)",
            (fp, datetime.now().isoformat(), len(all_texts), 0, file_visuals),
        )
        conn.commit()

    print(f"    Done: {len(all_texts)} chunks, {file_visuals} visuals")
    return {
        "meta": meta, "chunks": len(all_texts),
        "tables_kept": 0, "tables_skipped": 0,
        "charts_kept": file_visuals,
    }


# ═══════════════════════════════════════════════════════════
# MAIN — SEQUENTIAL
# ═══════════════════════════════════════════════════════════
def process_all(base_folder=C.BASE_FOLDER, db_path=C.DB_PATH, chroma_path=C.CHROMA_PATH,
                fresh=False, yes=False):
    if fresh:
        C.confirm_and_wipe(db_path, chroma_path, skip_confirm=yes)
    else:
        print("Resuming from previous run (use --fresh to start over)")

    C.verify_ollama_model()
    C.verify_groq()

    base = Path(base_folder)
    conn = C.setup_database(db_path)
    col = C.get_collection()
    cur = conn.cursor()

    with C._db_lock:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS unified_ingestion_log (
                file_path TEXT PRIMARY KEY,
                ingested_at TEXT,
                chunks INTEGER,
                tables_kept INTEGER,
                charts_kept INTEGER
            )
        """)
        conn.commit()

    pdf_files = sorted(base.rglob("*.pdf"))
    pending = [p for p in pdf_files if not C.already_ingested(cur, "unified_ingestion_log", str(p))]
    print(f"\nFound {len(pdf_files)} PDFs, {len(pending)} pending")
    print(f"Processing SEQUENTIALLY (one file at a time)")
    print(f"Visual detection: sampled every 3rd page + boundary expansion")
    print(f"Classification: Groq gpt-oss-20b")
    print(f"Embeddings: phi4-mini (qwen3-embedding)")
    print(f"{'─'*60}")

    grand_chunks = grand_visuals = 0
    failures = []

    for i, pdf_path in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {pdf_path.name}")
        try:
            result = process_one_file(pdf_path, conn, col)
            grand_chunks += result["chunks"]
            grand_visuals += result["charts_kept"]
            m = result["meta"]
            print(f"  OK  {m['company']} | {m['doc_type']} | {m['fy']} "
                  f"({result['chunks']} chunks, {result['charts_kept']} visuals)")
        except SystemExit:
            print(f"\nCRASHING: fatal Ollama/Groq failure on {pdf_path.name}")
            conn.close()
            raise
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append((str(pdf_path), str(e)))

    conn.close()
    print(f"\n{'═'*60}")
    print(f"Done | {grand_chunks} chunks | {grand_visuals} visuals")
    if failures:
        print(f"\n{len(failures)} file(s) failed:")
        for fp, err in failures:
            print(f"  - {fp}: {err}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        C.verify_ollama_model()
        C.verify_groq()
        print("Self-test passed.")
    else:
        process_all(fresh=args.fresh, yes=args.yes)