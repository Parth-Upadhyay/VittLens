"""
FinnAI Ingestion Pipeline — common.py
Shared code for text_pipeline.py and chart_pipeline.py.

FAILURE POLICY (explicit, by design):
    Every Ollama / Groq call goes through call_ollama_with_restart() or
    call_groq_with_restart(). On failure these:
        1. Retry with backoff (transient network/model hiccups)
        2. Attempt to actually restart the Ollama connection (ping, and if
           that fails, `ollama stop <model>` to force a fresh model load)
        3. If still failing after all attempts -> CRASH THE APP (SystemExit).
    There is NO silent skip-and-continue path. If validation/captioning is
    broken, you want to know now, not discover a gap in the data later.
"""

import os
import re
import math
import time
import random
import shutil
import sqlite3
import hashlib
import subprocess
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv()

import ollama
from groq import Groq

# ── Windows Tesseract path (chart_pipeline.py sets pytesseract.tesseract_cmd) ──
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════
START_FRESH   = False
PAGE_TIMEOUT  = 30

BASE_FOLDER   = r"C:\Users\P\Documents\finnai\data\rawpdfs"
DB_PATH       = r"C:\Users\P\Documents\finnai\data\tables.db"
CHROMA_PATH   = r"C:\Users\P\Documents\finnai\data\chromaqwen0-6bembedding"

EMBED_MODEL   = "qwen3-embedding:0.6b"
COLLECTION    = "qwen3_0_6bembeddingreports"
EMBED_WORKERS = int(os.getenv("EMBED_WORKERS", "10"))
EMBED_BATCH   = 32
MAX_SENT_CHARS = 1800
PREFIX_BUDGET  = 200
OVERLAP_SENTENCES = 1

VALIDATOR_MODEL = "phi4-mini:latest"
GROQ_MODEL      = "llama-3.1-8b-instant"

TEXT_PIPELINE_WORKERS  = int(os.getenv("TEXT_WORKERS", "6"))
CHART_PIPELINE_WORKERS = int(os.getenv("CHART_WORKERS", "4"))

OLLAMA_CONCURRENCY = int(os.getenv("OLLAMA_CONCURRENCY", "2"))

MAX_ATTEMPTS      = 4
BACKOFF_BASE_SECS = 3
RESTART_WAIT_SECS = 5

MIN_CHUNK_CHARS   = 40
MIN_TABLE_ROWS    = 3
MIN_TABLE_COLS    = 2
MIN_NUMERIC_RATIO = 0.08


# ═══════════════════════════════════════════════════════════
# GROQ RATE LIMITER (token bucket)
# ═══════════════════════════════════════════════════════════
class TokenBucket:
    def __init__(self, rate_per_sec: float, capacity: float):
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: float = 1.0):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait(self, tokens: float = 1.0):
        while not self.consume(tokens):
            time.sleep(0.05)

_groq_rate_limiter = TokenBucket(rate_per_sec=0.35, capacity=2)


# ══════════════════════════════════════════════
# OLLAMA / GROQ RESTART-THEN-CRASH WRAPPERS
# ══════════════════════════════════════════════
_ollama_gpu_gate = threading.Semaphore(OLLAMA_CONCURRENCY)


def _ping_ollama() -> bool:
    try:
        ollama.chat(
            model=VALIDATOR_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            options={"num_predict": 1},
        )
        return True
    except Exception:
        return False


def _force_restart_ollama(model: str):
    try:
        print(f"    [ollama] forcing restart of model '{model}' ...")
        subprocess.run(["ollama", "stop", model], timeout=20,
                        capture_output=True, check=False)
    except Exception as e:
        print(f"    [ollama] could not run 'ollama stop': {e}")
    time.sleep(RESTART_WAIT_SECS)


def call_ollama_with_restart(fn, *, model: str, context: str, **kwargs):
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with _ollama_gpu_gate:
                return fn()
        except Exception as e:
            last_err = e
            print(f"    [ollama] '{context}' failed (attempt {attempt}/{MAX_ATTEMPTS}): {e}")
            if attempt == MAX_ATTEMPTS:
                break
            if not _ping_ollama():
                _force_restart_ollama(model)
            backoff = BACKOFF_BASE_SECS * (2 ** (attempt - 1))
            print(f"    [ollama] retrying '{context}' in {backoff}s ...")
            time.sleep(backoff)

    print(f"\n{'!'*60}")
    print(f"FATAL: Ollama call '{context}' failed {MAX_ATTEMPTS}x after restart attempts.")
    print(f"Last error: {last_err}")
    print(f"Model: {model}  — check `ollama list`, `ollama ps`, and server logs.")
    print(f"{'!'*60}\n")
    raise SystemExit(1)


def _get_groq_clients() -> list:
    keys = [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2")]
    keys = [k for k in keys if k]
    if not keys:
        print("\nNo GROQ_API_KEY or GROQ_API_KEY_2 found in .env")
        raise SystemExit(1)
    return [Groq(api_key=k) for k in keys]


_groq_clients = None
_groq_client_idx = 0
_groq_lock = threading.Lock()


def call_groq_with_restart(fn_factory, *, context: str):
    global _groq_clients, _groq_client_idx
    with _groq_lock:
        if _groq_clients is None:
            _groq_clients = _get_groq_clients()

    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _groq_rate_limiter.wait()
        with _groq_lock:
            client = _groq_clients[_groq_client_idx % len(_groq_clients)]
        try:
            return fn_factory(client)
        except Exception as e:
            last_err = e
            print(f"    [groq] '{context}' failed (attempt {attempt}/{MAX_ATTEMPTS}): {e}")
            if attempt == MAX_ATTEMPTS:
                break
            with _groq_lock:
                if len(_groq_clients) > 1:
                    _groq_client_idx += 1
                    print("    [groq] swapping to backup API key ...")
            backoff = BACKOFF_BASE_SECS * (2 ** (attempt - 1))
            print(f"    [groq] retrying '{context}' in {backoff}s ...")
            time.sleep(backoff)

    print(f"\n{'!'*60}")
    print(f"FATAL: Groq call '{context}' failed {MAX_ATTEMPTS}x (all API keys exhausted).")
    print(f"Last error: {last_err}")
    print(f"{'!'*60}\n")
    raise SystemExit(1)


def print_concurrency_settings(pipeline_name: str, file_workers: int):
    print(f"{'─'*60}")
    print(f"{pipeline_name} concurrency:")
    print(f"  File workers (CPU: parsing/OCR/render) : {file_workers}")
    print(f"  Ollama GPU gate (this process)          : {OLLAMA_CONCURRENCY}")
    print(f"  Embed threads (queue on the GPU gate)   : {EMBED_WORKERS}")
    print(f"{'─'*60}")


def confirm_and_wipe(db_path: str, chroma_path: str, skip_confirm: bool = False):
    print(f"\n{'!'*60}")
    print("--fresh will PERMANENTLY DELETE:")
    print(f"  - SQLite DB: {db_path}")
    print(f"  - ChromaDB:  {chroma_path}")
    print(f"  - Chart PNGs: {Path(chroma_path).parent / 'charts'}")
    print(f"{'!'*60}")
    if not skip_confirm:
        resp = input("Type YES to confirm wipe and start fresh: ").strip()
        if resp != "YES":
            print("Aborted. No data was deleted.")
            raise SystemExit(0)
    wipe_existing_data(db_path, chroma_path)


def verify_ollama_model():
    try:
        r = ollama.embed(model=EMBED_MODEL, input="test")
        dim = len(r.embeddings[0])
        print(f"Ollama model ready: {EMBED_MODEL} (dim={dim})")
    except Exception as e:
        print(f"\nOllama embed model not found/reachable: {EMBED_MODEL}\n   {e}")
        raise SystemExit(1)

    if not _ping_ollama():
        _force_restart_ollama(VALIDATOR_MODEL)
        if not _ping_ollama():
            print(f"\nOllama validator model not reachable: {VALIDATOR_MODEL}")
            print(f"Run:   ollama pull {VALIDATOR_MODEL}")
            raise SystemExit(1)
    print(f"Ollama model ready: {VALIDATOR_MODEL}")


def verify_groq():
    def _test(client):
        return client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
            timeout=15,
        )
    call_groq_with_restart(_test, context="startup self-test")
    print(f"Groq model ready: {GROQ_MODEL}")


# ══════════════════════════════════════════════
# CHROMADB
# ══════════════════════════════════════════════
_chroma_col = None


def chroma_upsert_with_retry(col, ids, embeddings, documents, metadatas, max_retries=12, base_delay=0.5):
    for attempt in range(max_retries):
        try:
            col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            return
        except Exception as e:
            err_str = str(e).lower()
            if "database is locked" in err_str or "locked" in err_str or "busy" in err_str:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.2)
                    print(f"    [chroma] database locked, retrying in {delay:.2f}s... ({attempt+1}/{max_retries})")
                    time.sleep(delay)
                    continue
            raise
    raise RuntimeError(f"ChromaDB upsert failed after {max_retries} retries")


def get_collection():
    import chromadb
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
# SQLITE
# ══════════════════════════════════════════════
_db_lock = threading.Lock()


def setup_database(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
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
        CREATE TABLE IF NOT EXISTS text_ingestion_log (
            file_path   TEXT PRIMARY KEY,
            ingested_at TEXT,
            chunks      INTEGER,
            tables_kept INTEGER
        );
        CREATE TABLE IF NOT EXISTS chart_ingestion_log (
            file_path   TEXT PRIMARY KEY,
            ingested_at TEXT,
            charts_kept INTEGER,
            charts_seen INTEGER
        );
    """)
    conn.commit()
    print("SQLite ready:", db_path)
    return conn


def already_ingested(cur, table: str, file_path: str) -> bool:
    cur.execute(f"SELECT 1 FROM {table} WHERE file_path=?", (file_path,))
    return cur.fetchone() is not None


def wipe_existing_data(db_path: str, chroma_path: str):
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted old SQLite DB: {db_path}")
    for suffix in ("-wal", "-shm"):
        p = db_path + suffix
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"Deleted old ChromaDB: {chroma_path}")
    charts_dir = Path(chroma_path).parent / "charts"
    if charts_dir.exists():
        shutil.rmtree(charts_dir)
        print(f"Deleted extracted chart PNGs: {charts_dir}")


# ══════════════════════════════════════════════
# METADATA PARSING
# ══════════════════════════════════════════════
_FY_RE       = re.compile(r'\bFY[:\s]?(\d{4})[_\-](\d{4})\b', re.IGNORECASE)
_FY_SHORT_RE = re.compile(r'\bFY[:\s]?(\d{2})[_\-](\d{2,4})\b', re.IGNORECASE)
_FY_MIXED    = re.compile(r'\bFY[:\s]?(\d{4})[_\-](\d{2})\b', re.IGNORECASE)
_FY_SINGLE   = re.compile(r'(?<![a-zA-Z0-9])FY[:\s]?(\d{4})(?![a-zA-Z0-9])', re.IGNORECASE)
_FY_ULTRA    = re.compile(r'FY(\d{2})(?![a-zA-Z0-9])', re.IGNORECASE)
_FY_AFTER_Q  = re.compile(r'[qQ][1-4][\s\-]?[fF][yY](\d{2})', re.IGNORECASE)
_YEAR_RANGE  = re.compile(r'(?<![0-9])(\d{4})[_\-](\d{4})(?![0-9])', re.IGNORECASE)
_YEAR_SHORT  = re.compile(r'(?<![0-9])(\d{4})[_\-](\d{2})(?![0-9])', re.IGNORECASE)
_YEAR_SINGLE = re.compile(r'(?<![0-9])(20\d{2})(?![0-9])', re.IGNORECASE)

_QUARTER_RE  = re.compile(r'\bQ([1-4])\b', re.IGNORECASE)
_QN_RE       = re.compile(r'\b(?:quarter|q)[\s\-]?([1-4])\b', re.IGNORECASE)
_PERIOD_RE   = re.compile(r'\b(12M|9M|6M|3M|H1|H2)\b', re.IGNORECASE)

_QE_RE = re.compile(
    r'(?:quarter[\s\-]?ended|quarterly[\s\-]?results(?:[\s\-]?consolidated)?).*?'
    r'(june|september|sept|december|dec|march|mar)[\s\-]?(?:30|31)?[\s\-]?(20\d{2})',
    re.IGNORECASE
)

_CALL_DATE_RE = re.compile(
    r'(?:held\s+on|call[\s\-]|[\-_])'
    r'(?:\d{1,2}(?:st|nd|rd|th)?[\s\-])?'
    r'(january|jan|february|feb|march|mar|april|apr|may|june|jun|'
    r'july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)'
    r'[\s\-]?(?:\d{1,2}(?:st|nd|rd|th)?)?[\s\-]?(20\d{2})',
    re.IGNORECASE
)

_MONTH_FALLBACK = re.compile(
    r'\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|'
    r'july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)\b'
    r'(?:[\s\-]?(20\d{2}))?',
    re.IGNORECASE
)

_YEAR_DECADE = re.compile(
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[\s.]?(\d{2})\b',
    re.IGNORECASE
)

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

_DOC_TYPE_KEYWORDS = [
    (re.compile(r'\bannual\s+report\b|\bar\b|\bintegrated\s+annual\s+report\b', re.IGNORECASE), "Annual Report"),
    (re.compile(r'\btranscript\b|\bearnings\s+call\b|\banalyst\s+call\b|\bconference\s+call\b|\bearnings\s+conference\b', re.IGNORECASE), "Earnings Call Transcript"),
    (re.compile(r'\binvestor\s+presentation\b|\banalyst\s+presentation\b|\bearnings\s+presentation\b', re.IGNORECASE), "Investor Presentation"),
    (re.compile(r'\bfinancial\s+results\b|\bunaudited\s+financials\b|\baudited\s+financials\b|\bpress\s+release\b|\bpress\s+table\b', re.IGNORECASE), "Financial Results"),
    (re.compile(r'\boutcome\s+of\s+board\s+meeting\b|\bbm\s+outcome\b|\bboard\s+meeting\b', re.IGNORECASE), "Board Meeting Outcome"),
    (re.compile(r'\bnsebse\b|\bnse\s+bse\b|\bstock\s+exchange\b', re.IGNORECASE), "Stock Exchange Filing"),
]

_COMPANY_FOLDER_MAP = {
    'AXISBANK': 'Axis Bank', 'BAJAJFINSV': 'Bajaj Finserv', 'BAJFINANCE': 'Bajaj Finance',
    'BHARTIARTL': 'Bharti Airtel', 'HDFCBANK': 'HDFC Bank', 'HDFCLIFE': 'HDFC Life',
    'HINDUNILVR': 'Hindustan Unilever', 'ICICIBANK': 'ICICI Bank', 'INDUSINDBK': 'IndusInd Bank',
    'INFY': 'Infosys', 'ITC': 'ITC', 'JIOFIN': 'Jio Financial Services',
    'KOTAKBANK': 'Kotak Mahindra Bank', 'RELIANCE': 'Reliance Industries',
    'SBILIFE': 'SBI Life', 'SBIN': 'State Bank of India', 'SHRIRAMFIN': 'Shriram Finance',
    'TCS': 'Tata Consultancy Services', 'LT': 'Larsen & Toubro', 'SUNPHARMA': 'Sun Pharma',
    'MARUTI': 'Maruti Suzuki', 'ADANIPORTS': 'Adani Ports & SEZ', 'ADANIENT': 'Adani Enterprises',
    'TITAN': 'Titan Company', 'ULTRACEMCO': 'UltraTech Cement', 'M&M': 'Mahindra & Mahindra',
    'NTPC': 'NTPC', 'HCLTECH': 'HCLTech', 'TMPV': 'Tata Motors', 'POWERGRID': 'Power Grid',
    'ONGC': 'ONGC', 'COALINDIA': 'Coal India', 'TATASTEEL': 'Tata Steel', 'JSWSTEEL': 'JSW Steel',
    'BEL': 'Bharat Electronics', 'WIPRO': 'Wipro', 'TRENT': 'Trent', 'NESTLEIND': 'Nestle India',
    'GRASIM': 'Grasim Industries', 'HINDALCO': 'Hindalco Industries', 'TECHM': 'Tech Mahindra',
    'EICHERMOT': 'Eicher Motors', 'CIPLA': 'Cipla', 'DRREDDY': "Dr. Reddy's Laboratories",
    'APOLLOHOSP': 'Apollo Hospitals', 'ASIANPAINT': 'Asian Paints', 'TATACONSUM': 'Tata Consumer Products',
    'BAJAJ-AUTO': 'Bajaj Auto', 'INDIGO': 'IndiGo', 'ETERNAL': 'Eternal', 'MAXHEALTH': 'Max Healthcare',
}


def _extract_company_from_filename(fname: str) -> str:
    f = fname.lower()
    if re.search(r'\bhdfc[-_]?life\b', f): return "HDFC Life"
    if re.search(r'\bhdfc[-_]?bank\b|\bhdfcbank\b', f): return "HDFC Bank"
    if re.search(r'\bhdfc\b', f): return "HDFC Bank"
    if re.search(r'\bsbi[-_]?life\b|\bsbilife\b', f): return "SBI Life"
    if re.search(r'\bsbi\b', f): return "SBI"
    if re.search(r'\bbajaj[-_]?finserv\b', f): return "Bajaj Finserv"
    if re.search(r'\bbajaj[-_]?finance\b', f): return "Bajaj Finance"
    if re.search(r'\bbajaj\b', f): return "Bajaj Finserv"
    if re.search(r'\bicici[-_]?bank\b|\bicicibank\b', f): return "ICICI Bank"
    if re.search(r'\bicici\b', f): return "ICICI Bank"
    if re.search(r'\bindusind[-_]?bank\b|\bindusindbank\b', f): return "IndusInd Bank"
    if re.search(r'\bindusind\b', f): return "IndusInd Bank"
    if re.search(r'\bkotak[-_]?mahindra\b', f): return "Kotak Mahindra Bank"
    if re.search(r'\bkotak\b', f): return "Kotak Mahindra Bank"
    if re.search(r'\bshriram[-_]?finance\b', f): return "Shriram Finance"
    if re.search(r'\bsfl[\-_]', f): return "Shriram Finance"
    if re.search(r'\baxis[-_]?bank\b', f): return "Axis Bank"
    if re.search(r'\baxis\b', f): return "Axis Bank"
    return "UNKNOWN"


def _extract_fy(fname: str) -> str:
    if m := _FY_RE.search(fname): return f"FY{m.group(2)}"
    if m := _FY_SHORT_RE.search(fname):
        y2 = m.group(2)
        return f"FY20{y2}" if len(y2) == 2 else f"FY{y2}"
    if m := _FY_MIXED.search(fname): return f"FY20{m.group(2)}"
    if m := _FY_SINGLE.search(fname): return f"FY{m.group(1)}"
    if m := _FY_ULTRA.search(fname): return f"FY20{m.group(1)}"
    if m := _FY_AFTER_Q.search(fname): return f"FY20{m.group(1)}"
    if m := _YEAR_RANGE.search(fname): return f"FY{m.group(2)}"
    if m := _YEAR_SHORT.search(fname):
        y2 = int(m.group(2))
        if 20 <= y2 <= 40: return f"FY20{m.group(2)}"
    if m := _QE_RE.search(fname):
        month_str = m.group(1).lower()
        year = int(m.group(2))
        return f"FY{year}" if month_str in ('march', 'mar') else f"FY{year + 1}"
    if m := _CALL_DATE_RE.search(fname):
        month_str = m.group(1).lower()
        year = int(m.group(2))
        month = _MONTH_MAP[month_str]
        return f"FY{year}" if 1 <= month <= 5 else f"FY{year + 1}"
    if m := _YEAR_DECADE.search(fname):
        month_str = m.group(1).lower()
        year = 2000 + int(m.group(2))
        month = _MONTH_MAP[month_str]
        return f"FY{year}" if 1 <= month <= 5 else f"FY{year + 1}"
    if m := _MONTH_FALLBACK.search(fname):
        month_str = m.group(1).lower()
        year_str = m.group(2)
        month = _MONTH_MAP[month_str]
        if year_str:
            year = int(year_str)
            return f"FY{year}" if 1 <= month <= 5 else f"FY{year + 1}"
        else:
            years = _YEAR_SINGLE.findall(fname)
            if years:
                year = int(years[-1])
                return f"FY{year}" if 1 <= month <= 5 else f"FY{year + 1}"
    if m := _DATE_DDMMYYYY.search(fname):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"FY{year}" if 1 <= month <= 5 else f"FY{year + 1}"
    if m := re.search(r'[Qq]([1-4])[.\-_]?\s*(20\d{2})', fname):
        return f"FY{m.group(2)}"
    years = _YEAR_SINGLE.findall(fname)
    if years: return f"FY{years[-1]}"
    return "UNKNOWN"


def _extract_quarter(fname: str) -> str:
    if m := _QUARTER_RE.search(fname): return f"Q{m.group(1)}"
    if m := _QN_RE.search(fname): return f"Q{m.group(1)}"
    if m := _PERIOD_RE.search(fname):
        return {'3M': 'Q1', '6M': 'Q2', 'H1': 'Q2', '9M': 'Q3', '12M': 'Q4'}.get(m.group(1).upper(), 'NONE')
    if m := _QE_RE.search(fname): return _QE_MONTH_Q.get(m.group(1).lower(), 'NONE')
    if m := _CALL_DATE_RE.search(fname):
        month = _MONTH_MAP[m.group(1).lower()]
        return {1: 'Q3', 2: 'Q3', 3: 'Q4', 4: 'Q4', 5: 'Q4', 6: 'Q1', 7: 'Q1', 8: 'Q1', 9: 'Q2', 10: 'Q2', 11: 'Q2', 12: 'Q3'}.get(month, 'NONE')
    if m := _MONTH_FALLBACK.search(fname):
        month = _MONTH_MAP[m.group(1).lower()]
        return {1: 'Q3', 2: 'Q3', 3: 'Q4', 4: 'Q4', 5: 'Q4', 6: 'Q1', 7: 'Q1', 8: 'Q1', 9: 'Q2', 10: 'Q2', 11: 'Q2', 12: 'Q3'}.get(month, 'NONE')
    if m := _DATE_DDMMYYYY.search(fname):
        month = int(m.group(2))
        return {1: 'Q3', 2: 'Q3', 3: 'Q4', 4: 'Q4', 5: 'Q4', 6: 'Q1', 7: 'Q1', 8: 'Q1', 9: 'Q2', 10: 'Q2', 11: 'Q2', 12: 'Q3'}.get(month, 'NONE')
    return "NONE"


def _extract_doc_type(fname: str) -> str:
    for pat, dtype in _DOC_TYPE_KEYWORDS:
        if pat.search(fname): return dtype
    if re.search(r'\bAR\b', fname, re.IGNORECASE): return "Annual Report"
    return "Report"


def _normalize_company(name: str) -> str:
    clean_name = name.split('.')[0]
    return _COMPANY_FOLDER_MAP.get(clean_name, clean_name.replace('_', ' ').replace('-', ' ').title())


def parse_metadata(pdf_path: Path) -> dict:
    parts = pdf_path.parts
    fname = pdf_path.stem.lower()
    folder_parent = parts[-2] if len(parts) >= 2 else ""
    folder_company = parts[-3] if len(parts) >= 3 else ""
    company = _normalize_company(folder_company)
    parent_lower = folder_parent.lower()
    if parent_lower in ('annualreports', 'annual reports', 'annual_reports', 'ar'):
        doc_type = "Annual Report"
    elif parent_lower in ('concalls', 'concall', 'call transcripts', 'earnings calls', 'transcripts', 'earnings call'):
        doc_type = "Earnings Call Transcript"
    else:
        doc_type = _extract_doc_type(fname)
    fy = _extract_fy(fname)
    quarter = _extract_quarter(fname)
    return {
        "sector": "Financial Services",
        "company": company,
        "doc_type": doc_type,
        "fy": fy,
        "quarter": quarter,
        "file_name": pdf_path.name,
        "file_path": str(pdf_path),
    }


# ══════════════════════════════════════════════
# TEXT CLEANER
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
    if not raw: return ""
    text = raw
    for pat in _NOISE_PATTERNS:
        text = pat.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln) > 2 or any(c.isalnum() for c in ln)]
    return '\n'.join(lines).strip()


# ══════════════════════════════════════════════
# HYBRID CHUNKER
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
    if not line or len(line) < 3: return False
    if line.count('|') >= 2 or line.count('\t') >= 2: return False
    if re.sub(r'[,\s]', '', line).replace('.', '').isdigit(): return False
    if _HEADER_RE.match(line): return True
    if len(line) < 80 and line.istitle() and line[-1] not in '.,:;-': return True
    return False


def _split_sentences(text: str) -> list:
    parts = _SENT_SPLIT_RE.split(text)
    sentences = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part: continue
        ending = '.' if i < len(parts) - 1 else ''
        candidate = part + ending
        if _ABBREV_RE.search(candidate):
            if sentences: sentences[-1] = sentences[-1] + ' ' + candidate
            else: sentences.append(candidate)
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
    if current: chunks.append(" ".join(current))
    return chunks


def hybrid_chunk(page_text: str, meta: dict, page_num: int) -> list:
    if not page_text or not page_text.strip(): return []
    lines = page_text.splitlines()
    sections = []
    current_header = f"Page {page_num}"
    current_lines = []
    for line in lines:
        if _is_header(line):
            if current_lines: sections.append((current_header, "\n".join(current_lines)))
            current_header = line.strip()
            current_lines = []
        else: current_lines.append(line)
    if current_lines: sections.append((current_header, "\n".join(current_lines)))

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
        if not body.strip(): continue
        sentences = _split_sentences(body)
        if not sentences:
            chunks.append(_make_chunk(header, body))
            continue
        for group in _group_sentences(sentences, effective_max, overlap=OVERLAP_SENTENCES):
            if len(group.strip()) < MIN_CHUNK_CHARS: continue
            chunks.append(_make_chunk(header, group))
    return chunks


# ══════════════════════════════════════════════
# TABLE HEURISTIC PRE-FILTER
# ══════════════════════════════════════════════
def is_important_table(table: list) -> bool:
    if not table or len(table) < MIN_TABLE_ROWS + 1: return False
    rows = table[1:]
    if len(rows) < MIN_TABLE_ROWS: return False
    col_counts = [len(r) for r in table]
    if max(col_counts) < MIN_TABLE_COLS: return False
    total_cells = 0
    numeric_cells = 0
    numeric_pattern = re.compile(r'[\d,]+(?:\.\d+)?\s*(?:%|Cr|Lac|Mn|Bn|Rs|₹)?', re.IGNORECASE)
    for row in rows:
        for cell in row:
            if cell is None: continue
            total_cells += 1
            s = str(cell).strip()
            if s and (numeric_pattern.search(s) or s.replace(',', '').replace('.', '').replace('-', '').isdigit()):
                numeric_cells += 1
    if total_cells == 0: return False
    return (numeric_cells / total_cells) >= MIN_NUMERIC_RATIO


def format_table_preview(table: list, max_rows: int = 3) -> str:
    lines = []
    for row in table[:max_rows]:
        lines.append(" | ".join(str(cell) if cell is not None else "" for cell in row))
    return "\n".join(lines)


# ══════════════════════════════════════════════
# PAGE EXTRACTION TIMEOUT
# ══════════════════════════════════════════════
def extract_text_with_timeout(page, timeout_secs: int = PAGE_TIMEOUT) -> str:
    result = [""]
    exception = [None]

    def _extract():
        try:
            result[0] = page.extract_text() or ""
        except Exception as e:
            exception[0] = e

    t = threading.Thread(target=_extract)
    t.daemon = True
    t.start()
    t.join(timeout=timeout_secs)

    if t.is_alive():
        print(f"    WARNING: Page extraction timed out after {timeout_secs}s, skipping page")
        return ""
    if exception[0]:
        raise exception[0]
    return result[0]


# ══════════════════════════════════════════════
# SANITIZERS / IDS
# ══════════════════════════════════════════════
def sanitize(name) -> str:
    if name is None: return "col"
    try:
        if isinstance(name, float) and math.isnan(name): return "col"
    except (TypeError, ValueError): pass
    s = re.sub(r'[^a-zA-Z0-9]', '_', str(name)).lower().strip('_')
    return s or "col"


def make_unique_columns(cols: list) -> list:
    result = []
    seen = set()
    for i, c in enumerate(cols):
        base = sanitize(c)
        if not base: base = f"col_{i}"
        candidate = base
        n = 1
        while candidate in seen:
            candidate = f"{base}_{n}"
            n += 1
        seen.add(candidate)
        result.append(candidate)
    return result


def chunk_id(file_path: str, page_num: int, section: str, idx: int) -> str:
    key = f"{file_path}|{page_num}|{section}|{idx}"
    return hashlib.md5(key.encode()).hexdigest()


def file_fingerprint(file_path: str, length: int = 8) -> str:
    return hashlib.md5(file_path.encode()).hexdigest()[:length]


# ══════════════════════════════════════════════
# EMBEDDING
# ══════════════════════════════════════════════
def _embed_one(text: str) -> list:
    r = ollama.embed(model=EMBED_MODEL, input=text)
    return r.embeddings[0]


def embed_parallel(texts: list, workers: int = EMBED_WORKERS) -> list:
    results = [None] * len(texts)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                call_ollama_with_restart, lambda t=t: _embed_one(t),
                model=EMBED_MODEL, context="embed"
            ): i
            for i, t in enumerate(texts)
        }
        done = 0
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
            done += 1
            if done % 20 == 0 or done == len(texts):
                print(f"    Embedded {done}/{len(texts)}", end="\r")
    print()
    return results