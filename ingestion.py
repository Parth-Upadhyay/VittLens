"""
- Embedding: qwen3-embedding:0.6b  (Ollama)
- Table validation: Groq llama-3.1-8b-instant
- Table bridge: every SQLite table gets a RAG summary chunk
- Resumes automatically from ingestion_log
- HARD STOP on any Groq failure
- START_FRESH flag to wipe or resume

"""

import os
import json
import shutil
import re
import math
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv()

import pdfplumber
import pandas as pd
import chromadb
import ollama
from groq import Groq

# ══════════════════════════════════════════════
# CONFIG  —  SET THIS BEFORE RUNNING
# ══════════════════════════════════════════════
START_FRESH   =False   # ← True = wipe DBs and restart from zero
                        # ← False = resume from ingestion_log

BASE_FOLDER   = r"C:\Users\P\Documents\finnai\data\NIFTY 50 REPORTS\Financial Services"
DB_PATH       = r"C:\Users\P\Documents\finnai\data\tables.db"
CHROMA_PATH   = r"C:\Users\P\Documents\finnai\data\chromaqwen0-6bembedding"

EMBED_MODEL   = "qwen3-embedding:0.6b"
COLLECTION    = "qwen3_0_6bembeddingreports"
EMBED_WORKERS = 6
EMBED_BATCH   = 32
MAX_SENT_CHARS = 1800
PREFIX_BUDGET = 200       # chars reserved for metadata prefix
OVERLAP_SENTENCES = 1     # keep N trailing sentences in next chunk (0 = off)

# Groq — reads key from .env on every run
GROQ_MODEL    = "llama-3.1-8b-instant"
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")

# ── Quality thresholds ──
MIN_CHUNK_CHARS   = 40
MIN_TABLE_ROWS    = 3
MIN_TABLE_COLS    = 2
MIN_NUMERIC_RATIO = 0.08
# ─────────────────────────────────────────────


# ══════════════════════════════════════════════
# 0. PRE-FLIGHT
# ══════════════════════════════════════════════
def wipe_existing_data(db_path: str, chroma_path: str):
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted old SQLite DB: {db_path}")
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"Deleted old ChromaDB: {chroma_path}")

def verify_ollama_model():
    try:
        r = ollama.embed(model=EMBED_MODEL, input="test")
        dim = len(r.embeddings[0])
        print(f"Ollama model ready: {EMBED_MODEL} (dim={dim})")
    except Exception as e:
        print(f"\nOllama model not found: {EMBED_MODEL}\n   {e}")
        print(f"\nRun:   ollama pull {EMBED_MODEL}\n")
        raise SystemExit(1)

def _get_groq_client() -> Groq:
    """Create a fresh Groq client every time. No global state."""
    key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY_2")
    if not key:
        print("\nNo GROQ_API_KEY or GROQ_API_KEY_2 found in .env")
        raise SystemExit(1)
    return Groq(api_key=key)


# ══════════════════════════════════════════════
# CHROMADB SINGLETON
# ══════════════════════════════════════════════
_chroma_col = None

def get_collection() -> chromadb.Collection:
    global _chroma_col
    if _chroma_col is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_col = client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        print("ChromaDB ready:", CHROMA_PATH)
    return _chroma_col


# ══════════════════════════════════════════════
# 1. SQLITE SETUP
# ══════════════════════════════════════════════
def setup_database(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.executescript("""
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
        CREATE TABLE IF NOT EXISTS ingestion_log (
            file_path   TEXT PRIMARY KEY,
            ingested_at TEXT
        );
    """)
    conn.commit()
    print("SQLite ready:", db_path)
    return conn


# ══════════════════════════════════════════════
# 2. METADATA PARSING  (FIXED v14)
# ══════════════════════════════════════════════

# ── FY regexes (most specific first) ──
_FY_RE       = re.compile(r'\bFY[:\s]?(\d{4})[_\-](\d{4})\b', re.IGNORECASE)          # FY2024-2025
_FY_SHORT_RE = re.compile(r'\bFY[:\s]?(\d{2})[_\-](\d{2,4})\b', re.IGNORECASE)         # FY25-26
_FY_MIXED    = re.compile(r'\bFY[:\s]?(\d{4})[_\-](\d{2})\b', re.IGNORECASE)           # FY2025-26
_FY_SINGLE   = re.compile(r'(?<![a-zA-Z0-9])FY[:\s]?(\d{4})(?![a-zA-Z0-9])', re.IGNORECASE)  # FY2025
_FY_ULTRA    = re.compile(r'FY(\d{2})(?![a-zA-Z0-9])', re.IGNORECASE)                    # FY26  (no boundary before, boundary after)
_FY_AFTER_Q  = re.compile(r'[qQ][1-4][\s\-]?[fF][yY](\d{2})', re.IGNORECASE)              # Q1FY26, q1-fy26
_YEAR_RANGE  = re.compile(r'(?<![0-9])(\d{4})[_\-](\d{4})(?![0-9])', re.IGNORECASE)      # 2024-2025
_YEAR_SHORT  = re.compile(r'(?<![0-9])(\d{4})[_\-](\d{2})(?![0-9])', re.IGNORECASE)      # 2024-25
_YEAR_SINGLE = re.compile(r'(?<![0-9])(20\d{2})(?![0-9])', re.IGNORECASE)                 # 2024, 2025  (digit boundaries, not word boundaries!)

# ── Quarter / Period ──
_QUARTER_RE  = re.compile(r'\bQ([1-4])\b', re.IGNORECASE)
_QN_RE       = re.compile(r'\b(?:quarter|q)[\s\-]?([1-4])\b', re.IGNORECASE)
_PERIOD_RE   = re.compile(r'\b(12M|9M|6M|3M|H1|H2)\b', re.IGNORECASE)

# ── Quarter-ended dates (filings) ──
_QE_RE = re.compile(
    r'(?:quarter[\s\-]?ended|quarterly[\s\-]?results(?:[\s\-]?consolidated)?).*?'
    r'(june|september|sept|december|dec|march|mar)[\s\-]?(?:30|31)?[\s\-]?(20\d{2})',
    re.IGNORECASE
)

# ── Earnings call dates ──
_CALL_DATE_RE = re.compile(
    r'(?:held\s+on|call[\s\-]|[\-_])'
    r'(?:\d{1,2}(?:st|nd|rd|th)?[\s\-])?'
    r'(january|jan|february|feb|march|mar|april|apr|may|june|jun|'
    r'july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)'
    r'[\s\-]?(?:\d{1,2}(?:st|nd|rd|th)?)?[\s\-]?(20\d{2})',
    re.IGNORECASE
)

# ── Fallback month + year ──
_MONTH_FALLBACK = re.compile(
    r'\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|'
    r'july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)\b'
    r'(?:[\s\-]?(20\d{2}))?',
    re.IGNORECASE
)

# ── Decade shorthand: Dec25, Sep25 ──
_YEAR_DECADE = re.compile(
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[\s.]?(\d{2})\b',
    re.IGNORECASE
)

# ── Raw DDMMYYYY in filename (e.g. nsebse25072025) ──
_DATE_DDMMYYYY = re.compile(r'(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)')

_MONTH_MAP = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
    'july': 7, 'jul': 7, 'august': 8, 'aug': 8,
    'september': 9, 'sept': 9, 'sep': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

_QE_MONTH_Q = {
    'june': 'Q1', 'september': 'Q2', 'sept': 'Q2',
    'december': 'Q3', 'dec': 'Q3', 'march': 'Q4', 'mar': 'Q4',
}

# ── Doc type keywords (filename-based) ──
_DOC_TYPE_KEYWORDS = [
    (re.compile(r'\bannual\s+report\b|\bar\b|\bintegrated\s+annual\s+report\b', re.IGNORECASE), "Annual Report"),
    (re.compile(r'\btranscript\b|\bearnings\s+call\b|\banalyst\s+call\b|\bconference\s+call\b|\bearnings\s+conference\b', re.IGNORECASE), "Earnings Call Transcript"),
    (re.compile(r'\binvestor\s+presentation\b|\banalyst\s+presentation\b|\bearnings\s+presentation\b', re.IGNORECASE), "Investor Presentation"),
    (re.compile(r'\bfinancial\s+results\b|\bunaudited\s+financials\b|\baudited\s+financials\b|\bpress\s+release\b|\bpress\s+table\b', re.IGNORECASE), "Financial Results"),
    (re.compile(r'\boutcome\s+of\s+board\s+meeting\b|\bbm\s+outcome\b|\bboard\s+meeting\b', re.IGNORECASE), "Board Meeting Outcome"),
    (re.compile(r'\bnsebse\b|\bnse\s+bse\b|\bstock\s+exchange\b', re.IGNORECASE), "Stock Exchange Filing"),
]

# ── Company normalizations (folder names) ──
_COMPANY_FOLDER_MAP = {
    'ICICIBANK': 'ICICI Bank',
    'HDFC_Bank': 'HDFC Bank',
    'HDFC-Life': 'HDFC Life',
    'SBILife': 'SBI Life',
    'Shriram_Finance': 'Shriram Finance',
    'IndusInd': 'IndusInd Bank',
    'IndusInd-Bank': 'IndusInd Bank',
    'Kotak-Mahindra-Bank-Limited': 'Kotak Mahindra Bank',
    'Axis': 'Axis Bank',
    'Bajaj Finserv': 'Bajaj Finserv',
    'Bajaj Finance': 'Bajaj Finance',
    'SBI': 'SBI',
}

# ── Doc-type folder names ──
_DOC_TYPE_FOLDERS = {
    'annual reports', 'call transcripts', 'presentations',
    'press releases', 'quarterly reports', 'financial results',
    'investor presentations', 'earnings calls', 'transcripts',
    'board meeting outcomes', 'stock exchange filings',
}


def _looks_like_doc_type_folder(name: str) -> bool:
    return name.lower() in _DOC_TYPE_FOLDERS


def _extract_company_from_filename(fname: str) -> str:
    """Extract company name from filename keywords."""
    f = fname.lower()

    # Most specific patterns first
    if re.search(r'\bhdfc[-_]?life\b', f):
        return "HDFC Life"
    if re.search(r'\bhdfc[-_]?bank\b|\bhdfcbank\b', f):
        return "HDFC Bank"
    if re.search(r'\bhdfc\b', f):
        return "HDFC Bank"

    if re.search(r'\bsbi[-_]?life\b|\bsbilife\b', f):
        return "SBI Life"
    if re.search(r'\bsbi\b', f):
        return "SBI"

    if re.search(r'\bbajaj[-_]?finserv\b', f):
        return "Bajaj Finserv"
    if re.search(r'\bbajaj[-_]?finance\b', f):
        return "Bajaj Finance"
    if re.search(r'\bbajaj\b', f):
        return "Bajaj Finserv"  # ambiguous, default to parent

    if re.search(r'\bicici[-_]?bank\b|\bicicibank\b', f):
        return "ICICI Bank"
    if re.search(r'\bicici\b', f):
        return "ICICI Bank"

    if re.search(r'\bindusind[-_]?bank\b|\bindusindbank\b', f):
        return "IndusInd Bank"
    if re.search(r'\bindusind\b', f):
        return "IndusInd Bank"

    if re.search(r'\bkotak[-_]?mahindra\b', f):
        return "Kotak Mahindra Bank"
    if re.search(r'\bkotak\b', f):
        return "Kotak Mahindra Bank"

    if re.search(r'\bshriram[-_]?finance\b', f):
        return "Shriram Finance"
    if re.search(r'\bsfl[\-_]', f):
        return "Shriram Finance"

    if re.search(r'\baxis[-_]?bank\b', f):
        return "Axis Bank"
    if re.search(r'\baxis\b', f):
        return "Axis Bank"

    return "UNKNOWN"


def _extract_fy(fname: str) -> str:
    """Robust FY extractor for Indian fiscal-year filenames."""
    # 1. FY2024-2025  → FY2025
    if m := _FY_RE.search(fname):
        return f"FY{m.group(2)}"
    # 2. FY25-26  → FY2026
    if m := _FY_SHORT_RE.search(fname):
        y2 = m.group(2)
        return f"FY20{y2}" if len(y2) == 2 else f"FY{y2}"
    # 3. FY2025-26  → FY2026
    if m := _FY_MIXED.search(fname):
        return f"FY20{m.group(2)}"
    # 4. FY2025
    if m := _FY_SINGLE.search(fname):
        return f"FY{m.group(1)}"
    # 5. FY26  (must be after FY2025 to avoid matching inside FY2025)
    if m := _FY_ULTRA.search(fname):
        return f"FY20{m.group(1)}"
    # 6. Q1FY26  (no word boundary issue)
    if m := _FY_AFTER_Q.search(fname):
        return f"FY20{m.group(1)}"
    # 7. 2024-2025  → FY2025
    if m := _YEAR_RANGE.search(fname):
        return f"FY{m.group(2)}"
    # 8. 2024-25  → FY2025  (validate second part is a short year, not a month)
    if m := _YEAR_SHORT.search(fname):
        y2 = int(m.group(2))
        if 20 <= y2 <= 40:  # Valid short year range
            return f"FY20{m.group(2)}"
    # 9. Quarter-ended / quarterly-results date
    if m := _QE_RE.search(fname):
        month_str = m.group(1).lower()
        year = int(m.group(2))
        if month_str in ('march', 'mar'):
            return f"FY{year}"
        return f"FY{year + 1}"
    # 10. Earnings call date
    if m := _CALL_DATE_RE.search(fname):
        month_str = m.group(1).lower()
        year = int(m.group(2))
        month = _MONTH_MAP[month_str]
        if 1 <= month <= 5:
            return f"FY{year}"
        return f"FY{year + 1}"
    # 11. Decade shorthand: Dec25, Sep25
    if m := _YEAR_DECADE.search(fname):
        month_str = m.group(1).lower()
        year = 2000 + int(m.group(2))
        month = _MONTH_MAP[month_str]
        if 1 <= month <= 5:
            return f"FY{year}"
        return f"FY{year + 1}"
    # 12. Fallback month + year (press releases, etc.)
    if m := _MONTH_FALLBACK.search(fname):
        month_str = m.group(1).lower()
        year_str = m.group(2)
        month = _MONTH_MAP[month_str]
        if year_str:
            year = int(year_str)
            if 1 <= month <= 5:
                return f"FY{year}"
            return f"FY{year + 1}"
        else:
            years = _YEAR_SINGLE.findall(fname)
            if years:
                year = int(years[-1])
                if 1 <= month <= 5:
                    return f"FY{year}"
                return f"FY{year + 1}"
    # 13. Raw DDMMYYYY (e.g. nsebse25072025)
    if m := _DATE_DDMMYYYY.search(fname):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            if 1 <= month <= 5:
                return f"FY{year}"
            return f"FY{year + 1}"
    # 14. QX-YYYY pattern
    if m := re.search(r'[Qq]([1-4])[.\-_]?\s*(20\d{2})', fname):
        return f"FY{m.group(2)}"
    # 15. Last resort: any year
    years = _YEAR_SINGLE.findall(fname)
    if years:
        return f"FY{years[-1]}"
    return "UNKNOWN"


def _extract_quarter(fname: str) -> str:
    """Robust quarter extractor."""
    # Explicit Q1-Q4
    if m := _QUARTER_RE.search(fname):
        return f"Q{m.group(1)}"
    if m := _QN_RE.search(fname):
        return f"Q{m.group(1)}"
    # Period patterns: 3M=Q1, 6M/H1=Q2, 9M=Q3, 12M=Q4
    if m := _PERIOD_RE.search(fname):
        period = m.group(1).upper()
        return {'3M': 'Q1', '6M': 'Q2', 'H1': 'Q2', '9M': 'Q3', '12M': 'Q4'}.get(period, 'NONE')
    # Quarter-ended month
    if m := _QE_RE.search(fname):
        return _QE_MONTH_Q.get(m.group(1).lower(), 'NONE')
    # Earnings call date
    if m := _CALL_DATE_RE.search(fname):
        month = _MONTH_MAP[m.group(1).lower()]
        return {1: 'Q3', 2: 'Q3', 3: 'Q4', 4: 'Q4', 5: 'Q4',
                6: 'Q1', 7: 'Q1', 8: 'Q1', 9: 'Q2', 10: 'Q2', 11: 'Q2', 12: 'Q3'}.get(month, 'NONE')
    # Fallback month
    if m := _MONTH_FALLBACK.search(fname):
        month = _MONTH_MAP[m.group(1).lower()]
        return {1: 'Q3', 2: 'Q3', 3: 'Q4', 4: 'Q4', 5: 'Q4',
                6: 'Q1', 7: 'Q1', 8: 'Q1', 9: 'Q2', 10: 'Q2', 11: 'Q2', 12: 'Q3'}.get(month, 'NONE')
    # DDMMYYYY fallback
    if m := _DATE_DDMMYYYY.search(fname):
        month = int(m.group(2))
        return {1: 'Q3', 2: 'Q3', 3: 'Q4', 4: 'Q4', 5: 'Q4',
                6: 'Q1', 7: 'Q1', 8: 'Q1', 9: 'Q2', 10: 'Q2', 11: 'Q2', 12: 'Q3'}.get(month, 'NONE')
    return "NONE"


def _extract_doc_type(fname: str, folder_name: str = "") -> str:
    """Extract doc type from filename keywords, fallback to folder name."""
    for pat, dtype in _DOC_TYPE_KEYWORDS:
        if pat.search(fname):
            return dtype
    if re.search(r'\bAR\b', fname, re.IGNORECASE):
        return "Annual Report"
    # Fallback to folder name if it looks like a doc-type
    if folder_name and _looks_like_doc_type_folder(folder_name):
        return folder_name.title()
    return "Report"


def _normalize_company(name: str) -> str:
    return _COMPANY_FOLDER_MAP.get(name, name.replace('_', ' ').replace('-', ' ').title())


def parse_metadata(pdf_path: Path) -> dict:
    parts = pdf_path.parts
    fname = pdf_path.stem.lower()

    # Adaptive structure detection
    # Possible structures:
    #   .../Sector/Company/DocType/file.pdf
    #   .../Sector/Company/file.pdf
    #   .../Sector/DocType/file.pdf  (company in filename)
    #   .../Sector/DocType/Company/file.pdf

    folder_minus1 = parts[-2] if len(parts) >= 2 else ""      # immediate parent
    folder_minus2 = parts[-3] if len(parts) >= 3 else ""      # grandparent
    folder_minus3 = parts[-4] if len(parts) >= 4 else ""      # great-grandparent

    # Step 1: Try to extract company from filename
    company_from_file = _extract_company_from_filename(fname)

    # Step 2: Determine folder structure
    parent_is_doctype = _looks_like_doc_type_folder(folder_minus1)
    grandparent_is_doctype = _looks_like_doc_type_folder(folder_minus2)
    parent_is_company = not parent_is_doctype and folder_minus1

    if company_from_file != "UNKNOWN":
        # Company is in filename — use it regardless of folder structure
        company = company_from_file
        # Doc type: if parent folder is a doc-type, use it (or filename if more specific)
        if parent_is_doctype:
            doc_type = _extract_doc_type(fname, folder_minus1)
        elif grandparent_is_doctype:
            doc_type = _extract_doc_type(fname, folder_minus2)
        else:
            doc_type = _extract_doc_type(fname, folder_minus1)
    else:
        # Company NOT in filename — must come from folder structure
        if parent_is_company:
            # .../Company/file.pdf or .../Company/DocType/file.pdf
            company = _normalize_company(folder_minus1)
            if grandparent_is_doctype:
                doc_type = _extract_doc_type(fname, folder_minus2)
            else:
                doc_type = _extract_doc_type(fname, folder_minus1)
        elif parent_is_doctype and folder_minus2:
            # .../DocType/file.pdf  — try grandparent as company
            if grandparent_is_doctype or not folder_minus2:
                company = "UNKNOWN"
            else:
                company = _normalize_company(folder_minus2)
            doc_type = _extract_doc_type(fname, folder_minus1)
        else:
            company = _normalize_company(folder_minus1) if folder_minus1 else "UNKNOWN"
            doc_type = _extract_doc_type(fname, folder_minus1)

    fy = _extract_fy(fname)
    quarter = _extract_quarter(fname)

    return {
        "sector"   : "Financial Services",
        "company"  : company,
        "doc_type" : doc_type,
        "fy"       : fy,
        "quarter"  : quarter,
        "file_name": pdf_path.name,
        "file_path": str(pdf_path),
    }


# ══════════════════════════════════════════════
# 3. TEXT CLEANER
# ══════════════════════════════════════════════
_NOISE_PATTERNS = [
    re.compile(r'^\s*\d+\s*$', re.MULTILINE),
    re.compile(r'^\s*(?:www\.|http|https?://)\S+\s*$', re.MULTILINE),
    re.compile(r'^\s*(?:axis bank|annual report|investor presentation|earnings call|transcript)\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*(?:confidential|proprietary|all rights reserved|copyright)\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*(?:note\s*:?\s*\d+|schedule\s*\d+|annexure\s*\d+)\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]'),
]

def clean_page_text(raw: str) -> str:
    if not raw:
        return ""
    text = raw
    for pat in _NOISE_PATTERNS:
        text = pat.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln) > 2 or any(c.isalnum() for c in ln)]
    return '\n'.join(lines).strip()


# ══════════════════════════════════════════════
# 4. HYBRID CHUNKER
# ══════════════════════════════════════════════
_HEADER_RE = re.compile(
    r'^(?:'
    r'[A-Z][A-Z\s\d\-\(\)\/]{4,}|'
    r'\d+[\.\)]\s+[A-Z][^\n]{3,}|'
    r'(?:Note|Schedule|Annexure)\s+[\dA-Z]+|'
    r'Particulars\s*$'
    r')$',
    re.MULTILINE,
)

_SENT_SPLIT_RE = re.compile(r'[.!?](?=\s+[A-Z(₹\d])')
_ABBREV_RE = re.compile(
    r'\b(?:Rs|No|Mr|Mrs|Dr|St|Ltd|Co|vs|etc|Fig|Vol|Sr|Jr|Cr|Mn|Bn|'
    r'Inc|LLP|Pvt|i\.e|e\.g|U\.S|FY|Q[1-4]|FY\d{2}|Q[1-4]FY\d{2})\.'
)

def _is_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) < 3:
        return False
    # Reject lines that look like table cells
    if line.count('|') >= 2 or line.count('\t') >= 2:
        return False
    # Reject pure numeric lines
    if re.sub(r'[,\s]', '', line).replace('.', '').isdigit():
        return False
    if _HEADER_RE.match(line):
        return True
    if len(line) < 80 and line.istitle() and line[-1] not in '.,:;-':
        return True
    return False

def _split_sentences(text: str) -> list:
    parts = _SENT_SPLIT_RE.split(text)
    sentences = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        ending = '.' if i < len(parts) - 1 else ''
        candidate = part + ending
        if _ABBREV_RE.search(candidate):
            if sentences:
                sentences[-1] = sentences[-1] + ' ' + candidate
            else:
                sentences.append(candidate)
            continue
        sentences.append(candidate)
    return [s for s in sentences if s.strip()]

def _group_sentences(sentences: list, max_chars: int, overlap: int = 0) -> list:
    chunks, current, current_len = [], [], 0
    for i, sent in enumerate(sentences):
        if current_len + len(sent) > max_chars and current:
            chunks.append(" ".join(current))
            current = current[-overlap:] if overlap > 0 else []
            current_len = sum(len(s) + 1 for s in current)
        current.append(sent)
        current_len += len(sent) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks

def hybrid_chunk(page_text: str, meta: dict, page_num: int) -> list:
    if not page_text or not page_text.strip():
        return []
    lines = page_text.splitlines()
    sections = []
    current_header = f"Page {page_num}"
    current_lines = []
    for line in lines:
        if _is_header(line):
            if current_lines:
                sections.append((current_header, "\n".join(current_lines)))
            current_header = line.strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_header, "\n".join(current_lines)))

    def _make_chunk(header: str, body: str) -> dict:
        prefix = (
            f"[Company:{meta['company']}] "
            f"[DocType:{meta['doc_type']}] "
            f"[FY:{meta['fy']}] "
            f"[Quarter:{meta['quarter']}] "
            f"[Page:{page_num}] "
            f"[Section:{header}]\n\n"
        )
        return {
            "text": prefix + body.strip(),
            "metadata": {
                "company": meta["company"], "sector": meta["sector"],
                "doc_type": meta["doc_type"], "fy": meta["fy"],
                "quarter": meta["quarter"], "page": page_num,
                "section": header, "file": meta["file_name"],
            },
        }

    chunks = []
    effective_max = MAX_SENT_CHARS - PREFIX_BUDGET
    for header, body in sections:
        if not body.strip():
            continue
        sentences = _split_sentences(body)
        if not sentences:
            chunks.append(_make_chunk(header, body))
            continue
        for group in _group_sentences(sentences, effective_max, overlap=OVERLAP_SENTENCES):
            if len(group.strip()) < MIN_CHUNK_CHARS:
                continue
            chunks.append(_make_chunk(header, group))
    return chunks


# ══════════════════════════════════════════════
# 5. TABLE HEURISTIC FILTER
# ══════════════════════════════════════════════
def _is_important_table(table: list) -> bool:
    if not table or len(table) < MIN_TABLE_ROWS + 1:
        return False
    rows = table[1:]
    if len(rows) < MIN_TABLE_ROWS:
        return False
    col_counts = [len(r) for r in table]
    if max(col_counts) < MIN_TABLE_COLS:
        return False

    total_cells = 0
    numeric_cells = 0
    numeric_pattern = re.compile(r'[\d,]+(?:\.\d+)?\s*(?:%|Cr|Lac|Mn|Bn|Rs|₹)?', re.IGNORECASE)

    for row in rows:
        for cell in row:
            if cell is None:
                continue
            total_cells += 1
            s = str(cell).strip()
            if s and (numeric_pattern.search(s) or s.replace(',', '').replace('.', '').replace('-', '').isdigit()):
                numeric_cells += 1

    if total_cells == 0:
        return False
    return (numeric_cells / total_cells) >= MIN_NUMERIC_RATIO


# ══════════════════════════════════════════════
# 6. GROQ LLM VALIDATION
# ══════════════════════════════════════════════
def _format_table_preview(table: list, max_rows: int = 3) -> str:
    lines = []
    for row in table[:max_rows]:
        lines.append(" | ".join(str(cell) if cell is not None else "" for cell in row))
    return "\n".join(lines)

def _groq_validate_table(table: list, company: str, page: int) -> bool:
    preview = _format_table_preview(table, max_rows=3)
    prompt = (
        "Reply with exactly one word: YES or NO.\n"
        "Is this a meaningful financial/business table?\n\n"
        f"Table:\n{preview}\n"
    )

    try:
        client = _get_groq_client()
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Reply with exactly one word and NOTHING ELSE : YES or NO"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=3,
            timeout=10,
        )
    except Exception as e:
        print(f"\nGroq API failed on page {page}: {e}")
        print("   STOPPING at last committed PDF.")
        print("   Swap API key in .env and restart — script will resume automatically.")
        raise SystemExit(1)

    answer = resp.choices[0].message.content.strip().upper()

    if answer == "YES":
        return True
    elif answer == "NO":
        print(f"    Groq rejected table on page {page}")
        return False
    else:
        print(f"    Groq non-compliant on page {page}: '{answer}' — treating as NO")
        return False


# ══════════════════════════════════════════════
# 7. TABLE → RAG BRIDGE
# ══════════════════════════════════════════════
def _make_table_summary_chunk(tbl_name: str, df: pd.DataFrame, meta: dict, page_num: int) -> dict:
    safe_cols = _make_unique_columns(df.columns)
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
            "company"     : meta["company"],
            "sector"      : meta["sector"],
            "doc_type"    : meta["doc_type"],
            "fy"          : meta["fy"],
            "quarter"     : meta["quarter"],
            "page"        : page_num,
            "section"     : f"TABLE:{tbl_name}",
            "file"        : meta["file_name"],
            "is_table_ref": "true",
            "sql_table"   : tbl_name,
        },
    }


# ══════════════════════════════════════════════
# 8. OLLAMA EMBEDDING
# ══════════════════════════════════════════════
def _embed_one(text: str) -> list:
    r = ollama.embed(model=EMBED_MODEL, input=text)
    return r.embeddings[0]

def embed_parallel(texts: list, workers: int = EMBED_WORKERS) -> list:
    results = [None] * len(texts)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_embed_one, t): i for i, t in enumerate(texts)}
        done = 0
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
            done += 1
            if done % 20 == 0 or done == len(texts):
                print(f"    Embedded {done}/{len(texts)}", end="\r")
    print()
    return results


# ══════════════════════════════════════════════
# 9. TABLE STORAGE
# ══════════════════════════════════════════════
def _sanitize(name) -> str:
    if name is None:
        return "col"
    try:
        if isinstance(name, float) and math.isnan(name):
            return "col"
    except (TypeError, ValueError):
        pass
    s = re.sub(r'[^a-zA-Z0-9]', '_', str(name)).lower().strip('_')
    return s or "col"

def _make_unique_columns(cols: list) -> list:
    result = []
    seen = set()
    for i, c in enumerate(cols):
        base = _sanitize(c)
        if not base:
            base = f"col_{i}"
        candidate = base
        n = 1
        while candidate in seen:
            candidate = f"{base}_{n}"
            n += 1
        seen.add(candidate)
        result.append(candidate)
    return result

def store_table(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str):
    try:
        df = df.dropna(axis=1, how='all')
        df.columns = _make_unique_columns(df.columns)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
    except Exception as e:
        print(f"\n    Table store failed '{table_name}': {e}")


# ══════════════════════════════════════════════
# 10. CHUNK ID
# ══════════════════════════════════════════════
def chunk_id(file_path: str, page_num: int, section: str, idx: int) -> str:
    key = f"{file_path}|{page_num}|{section}|{idx}"
    return hashlib.md5(key.encode()).hexdigest()


# ══════════════════════════════════════════════
# 11. INGESTION LOOP
# ══════════════════════════════════════════════
def already_ingested(cur: sqlite3.Cursor, file_path: str) -> bool:
    cur.execute("SELECT 1 FROM ingestion_log WHERE file_path=?", (file_path,))
    return cur.fetchone() is not None

def mark_ingested(cur: sqlite3.Cursor, file_path: str):
    cur.execute(
        "INSERT OR REPLACE INTO ingestion_log VALUES (?,?)",
        (file_path, datetime.now().isoformat()),
    )

def process_all(
    base_folder : str = BASE_FOLDER,
    db_path     : str = DB_PATH,
    chroma_path : str = CHROMA_PATH,
):
    if START_FRESH:
        wipe_existing_data(db_path, chroma_path)
    else:
        print("Resuming from previous run (START_FRESH=False)")

    verify_ollama_model()

    base = Path(base_folder)
    conn = setup_database(db_path)
    cur  = conn.cursor()
    col  = get_collection()

    pdf_files = [p for p in sorted(base.rglob("*.pdf")) if len(p.parts) >= 3]

    print(f"\nFound {len(pdf_files)} PDFs")
    print(f"{'─'*60}")

    grand_chunks = 0
    grand_tables = 0
    skipped_tables = 0

    for file_idx, pdf_path in enumerate(pdf_files, 1):
        fp   = str(pdf_path)
        meta = parse_metadata(pdf_path)

        print(f"\n[{file_idx}/{len(pdf_files)}] "
              f"{meta['company']} | {meta['doc_type']} | "
              f"{meta['fy']}  ← {meta['file_name']}")

        if already_ingested(cur, fp):
            print("    Already ingested, skipping")
            continue

        try:
            all_texts     = []
            all_metadatas = []
            all_ids       = []
            file_tables   = 0
            file_skipped  = 0

            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    if page_num == 1 or page_num % 10 == 0 or page_num == total_pages:
                        print(f"    Page {page_num}/{total_pages} ...", end="\r")

                    raw_text = clean_page_text(page.extract_text() or "")

                    cur.execute("""
                        INSERT INTO master_registry
                            (sector, company, doc_type, fy, quarter,
                             file_name, page_number, is_table)
                        VALUES (?,?,?,?,?,?,?,0)
                    """, (meta["sector"], meta["company"], meta["doc_type"],
                          meta["fy"], meta["quarter"], meta["file_name"], page_num))
                    reg_id = cur.lastrowid

                    if raw_text:
                        cur.execute(
                            "INSERT INTO text_content (registry_id, raw_text) VALUES (?,?)",
                            (reg_id, raw_text),
                        )

                    for t_idx, table in enumerate(page.extract_tables(), 1):
                        if not table or len(table) < 2:
                            continue

                        if not _is_important_table(table):
                            file_skipped += 1
                            continue

                        if not _groq_validate_table(table, meta["company"], page_num):
                            file_skipped += 1
                            continue

                        header = table[0]
                        rows   = table[1:]
                        if not any(header):
                            header = [f"col_{i}" for i in range(len(rows[0]))]

                        df       = pd.DataFrame(rows, columns=header)
                        tbl_name = (
                            f"{_sanitize(meta['company'])}"
                            f"_{_sanitize(meta['fy'])}"
                            f"_p{page_num}_t{t_idx}"
                        )
                        store_table(conn, df, tbl_name)

                        cur.execute("""
                            INSERT INTO master_registry
                                (sector, company, doc_type, fy, quarter,
                                 file_name, page_number, sql_table_name, is_table)
                            VALUES (?,?,?,?,?,?,?,?,1)
                        """, (meta["sector"], meta["company"], meta["doc_type"],
                              meta["fy"], meta["quarter"], meta["file_name"],
                              page_num, tbl_name))
                        file_tables += 1

                        bridge = _make_table_summary_chunk(tbl_name, df, meta, page_num)
                        all_texts.append(bridge["text"])
                        all_metadatas.append(bridge["metadata"])
                        all_ids.append(chunk_id(fp, page_num, f"TABLE_{tbl_name}", 0))

                    for i, ch in enumerate(hybrid_chunk(raw_text, meta, page_num)):
                        all_texts.append(ch["text"])
                        all_metadatas.append(ch["metadata"])
                        all_ids.append(
                            chunk_id(fp, page_num, ch["metadata"]["section"], i)
                        )

                print(f"    Pages done: {total_pages}          ")

            if all_texts:
                print(f"    Embedding {len(all_texts)} chunks ...")
                embeddings = embed_parallel(all_texts)

                for start in range(0, len(all_texts), EMBED_BATCH):
                    end = start + EMBED_BATCH
                    col.upsert(
                        ids        = all_ids[start:end],
                        embeddings = embeddings[start:end],
                        documents  = all_texts[start:end],
                        metadatas  = all_metadatas[start:end],
                    )

                grand_chunks += len(all_texts)

            grand_tables += file_tables
            skipped_tables += file_skipped
            mark_ingested(cur, fp)
            conn.commit()
            print(f"    {len(all_texts)} chunks | {file_tables} tables kept | {file_skipped} tables skipped")

        except SystemExit:
            conn.close()
            raise

        except Exception as e:
            print(f"\n    FAILED: {e}")
            conn.rollback()
            import traceback
            traceback.print_exc()

    conn.close()
    print(f"\n{'═'*60}")
    print(f"Done  |  {grand_chunks} chunks  |  {grand_tables} tables kept  |  {skipped_tables} tables skipped")
    print(f"   SQLite → {DB_PATH}")
    print(f"   Chroma → {CHROMA_PATH}")
    _print_summary(DB_PATH)


# ══════════════════════════════════════════════
# 12. SUMMARY
# ══════════════════════════════════════════════
def _print_summary(db_path: str):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    print(f"\n{'─'*60}  Summary")

    cur.execute("SELECT COUNT(*) FROM text_content")
    print(f"  Text pages : {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM master_registry WHERE is_table=1")
    print(f"  SQL tables : {cur.fetchone()[0]}")

    print(f"\n  {'Company':<20} {'DocType':<25} {'FY':<12} Pages")
    print(f"  {'─'*20} {'─'*25} {'─'*12} {'─'*5}")
    cur.execute("""
        SELECT company, doc_type, fy, COUNT(*)
        FROM master_registry WHERE is_table=0
        GROUP BY company, doc_type, fy
        ORDER BY company, fy
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:<20} {row[1]:<25} {str(row[2]):<12} {row[3]}")
    conn.close()
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    process_all()