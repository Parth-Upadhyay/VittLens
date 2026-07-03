import os
import re
from dotenv import load_dotenv
load_dotenv()

import ollama
import chromadb
import sqlite3
from sentence_transformers import CrossEncoder
from groq import Groq

# --- Paths & Config ---
DB_PATH = r"C:\Users\P\Documents\finnai\data\tables.db"
CHROMA_PATH = r"C:\Users\P\Documents\finnai\data\chromaqwen0-6bembedding"
COLLECTION = "qwen3_0_6bembeddingreports"
EMBED_MODEL = "qwen3-embedding:0.6b"
LLM_MODEL = "groq/compound"
COMPRESS_MODEL = "phi4-mini:latest"

MAX_CHUNK_CHARS = 400
MAX_ROWS_PER_TABLE = 5
MAX_TABLES = 3
MAX_CONTEXT_CHARS = 1200

# --- Clients ---
print("Loading reranker model (one-time)...")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
print("Reranker loaded.\n")

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- Company / FY mappings ---
COMPANY_VARIANTS = {
    "AXISBANK": ["Axis Bank", "Axisbank"],
    "BAJAJFINSV": ["Bajaj Finserv", "Bajajfinsv"],
    "BAJFINANCE": ["Bajfinance"],
    "HDFCBANK": ["HDFC Bank", "Hdfcbank"],
    "HDFCLIFE": ["HDFC Life", "Hdfclife"],
    "ICICIBANK": ["ICICI Bank"],
    "INDUSINDBK": ["IndusInd Bank", "Indusindbk"],
    "JIOFIN": ["Jiofin"],
    "KOTAKBANK": ["Kotak Mahindra Bank", "Kotakbank"],
    "SBILIFE": ["SBI Life", "Sbilife"],
    "SBIN": ["SBI", "Sbin"],
    "SHRIRAMFIN": ["Shriram Finance"],
}

COMPANY_ALIASES = {
    "axis bank": "AXISBANK", "axis": "AXISBANK", "axisbank": "AXISBANK",
    "bajaj finserv": "BAJAJFINSV", "bajaj financial services": "BAJAJFINSV",
    "bajajfinserv": "BAJAJFINSV", "bajajfinsv": "BAJAJFINSV", "bfs": "BAJAJFINSV",
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE",
    "bajaj fin": "BAJFINANCE", "bfl": "BAJFINANCE",
    "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK", "hdfcbank": "HDFCBANK",
    "housing development finance": "HDFCBANK",
    "hdfc life": "HDFCLIFE", "hdfc life insurance": "HDFCLIFE",
    "hdfclife": "HDFCLIFE", "hdfc standard life": "HDFCLIFE",
    "icici bank": "ICICIBANK", "icici": "ICICIBANK", "icicibank": "ICICIBANK",
    "indusind bank": "INDUSINDBK", "indusind": "INDUSINDBK",
    "indusindbk": "INDUSINDBK", "indus ind": "INDUSINDBK", "iib": "INDUSINDBK",
    "jio financial": "JIOFIN", "jio financial services": "JIOFIN",
    "jiofin": "JIOFIN", "jio finance": "JIOFIN", "jfs": "JIOFIN",
    "kotak mahindra bank": "KOTAKBANK", "kotak bank": "KOTAKBANK",
    "kotak": "KOTAKBANK", "kotakbank": "KOTAKBANK", "kmb": "KOTAKBANK",
    "sbi life": "SBILIFE", "sbi life insurance": "SBILIFE",
    "sbilife": "SBILIFE", "state bank life": "SBILIFE",
    "state bank of india": "SBIN", "state bank": "SBIN", "sbi": "SBIN", "sbin": "SBIN",
    "shriram finance": "SHRIRAMFIN", "shriram": "SHRIRAMFIN",
    "shriramfin": "SHRIRAMFIN", "shriram transport": "SHRIRAMFIN",
    "stfc": "SHRIRAMFIN", "scuf": "SHRIRAMFIN",
}

FY_ALIASES = {
    "2026": "FY2026", "fy26": "FY2026", "fy 26": "FY2026",
    "2025-26": "FY2026", "fy2025-26": "FY2026",
    "2025": "FY2025", "fy25": "FY2025", "fy 25": "FY2025",
    "2024-25": "FY2025", "fy2024-25": "FY2025",
    "2024": "FY2024", "fy24": "FY2024", "fy 24": "FY2024",
    "2023-24": "FY2024",
    "2023": "FY2023", "fy23": "FY2023", "2022-23": "FY2023",
}

DISPLAY_TO_TICKER = {v: k for k, vals in COMPANY_VARIANTS.items() for v in vals}

TABLE_PREFIX_MAP = {
    "AXISBANK": ["axisbank"],
    "BAJAJFINSV": ["bajaj_finserv", "bajajfinserv", "bajajfinsv"],
    "BAJFINANCE": ["bajfinance"],
    "HDFCBANK": ["hdfcbank"],
    "HDFCLIFE": ["hdfc_life", "hdfclife"],
    "ICICIBANK": ["icici_bank"],
    "INDUSINDBK": ["indusindbk"],
    "JIOFIN": ["jiofin"],
    "KOTAKBANK": ["kotakbank", "kotak_mahindra_bank"],
    "SBILIFE": ["sbilife", "sbi_life"],
    "SBIN": ["sbin", "sbi"],
    "SHRIRAMFIN": ["shriram_finance"],
}

# Row filtering keywords
ROW_FILTER_KEYWORDS = {
    "casa": ["casa", "current account", "savings account", "casa ratio", "casa deposits"],
    "revenue": ["revenue", "total income", "net revenue", "interest income", "total net revenue", "operating revenue"],
    "profit": ["profit", "pat", "net profit", "profit after tax", "pbt", "profit before tax", "operating profit"],
    "npa": ["npa", "gross npa", "net npa", "gnpa", "nnpa", "non performing"],
    "nim": ["nim", "net interest margin", "interest margin", "net interest income"],
    "capital": ["capital adequacy", "car", "tier 1", "tier 2", "crar", "capital ratio"],
    "dividend": ["dividend", "dps", "dividend per share", "interim dividend", "final dividend"],
    "deposit": ["deposit", "total deposits", "casa deposits", "term deposits", "fixed deposits"],
    "asset": ["total assets", "assets", "balance sheet", "asset size"],
    "liability": ["liabilities", "total liabilities", "borrowings"],
    "roe": ["roe", "return on equity", "return on average equity"],
    "roa": ["roa", "return on assets", "return on average assets"],
    "cost": ["cost to income", "cost income ratio", "operating cost", "expense ratio"],
    "eps": ["eps", "earnings per share", "basic eps", "diluted eps"],
    "provision": ["provision", "provisions", "credit cost", "provision coverage"],
    "advance": ["advances", "total advances", "loan book", "gross advances", "net advances"],
    "employee": ["employees", "staff", "workforce", "headcount", "branches", "atms", "digital"],
}

SYSTEM_PROMPT = """You are a senior financial analyst assistant specialising in Indian banking and financial services.

STRICT RULES:
1. Answer ONLY using the context provided.
2. Every number or fact must be followed by its source in parentheses with EXACT company name, FY, and page number.
3. For comparisons, you MUST have data for BOTH sides.
4. If the context is insufficient, say so explicitly.
5. Do not mention any company that was not asked about.
6. Be concise. Lead with the direct answer, then cite sources.
7. If multiple rows are provided, pick the ONE row that directly answers the question. Do not list all rows."""


# --- Helpers ---

def extract_companies(query: str) -> list:
    q = query.lower()
    found = []
    for alias in sorted(COMPANY_ALIASES, key=len, reverse=True):
        if alias in q and COMPANY_ALIASES[alias] not in found:
            found.append(COMPANY_ALIASES[alias])
    return found


def extract_fy(query: str) -> str | None:
    q = query.lower()
    for alias in sorted(FY_ALIASES, key=len, reverse=True):
        if alias in q:
            return FY_ALIASES[alias]
    return None


def ticker_to_db_values(tickers: list) -> list:
    values = []
    for t in tickers:
        values.extend(COMPANY_VARIANTS.get(t, [t]))
    return values


def build_where(companies: list, fy: str | None, manual_company: str | None, manual_fy: str | None) -> dict | None:
    conditions = []
    effective_tickers = [manual_company] if manual_company else companies
    db_values = ticker_to_db_values(effective_tickers)

    if len(db_values) == 1:
        conditions.append({"company": {"$eq": db_values[0]}})
    elif len(db_values) > 1:
        conditions.append({"company": {"$in": db_values}})

    effective_fy = manual_fy or fy
    if effective_fy:
        conditions.append({"fy": {"$eq": effective_fy}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def rerank_docs(query: str, docs: list, top_k: int) -> list:
    if not docs:
        return []
    pairs = [(query, doc) for doc in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked[:top_k]]


# --- Table Layer ---

def fetch_tables_by_pages(conn, metadatas: list, question: str = "") -> str:
    if not conn or not metadatas:
        return ""

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    all_tables = {r[0] for r in cursor.fetchall()}

    page_targets = []
    seen = set()
    for m in metadatas:
        company_display = m.get("company")
        fy = m.get("fy")
        page = m.get("page")
        if not company_display or not fy or page is None:
            continue
        key = (company_display, fy, int(page))
        if key in seen:
            continue
        seen.add(key)

        ticker = DISPLAY_TO_TICKER.get(company_display)
        if not ticker:
            continue
        prefixes = TABLE_PREFIX_MAP.get(ticker, [ticker.lower()])
        page_targets.append((prefixes, fy.lower(), int(page), company_display, fy))

    if not page_targets:
        return ""

    matched_tables = []
    for prefixes, fy, page, company_display, fy_val in page_targets:
        for prefix in prefixes:
            pattern = f"{prefix}_{fy}_p{page}_"
            for t in all_tables:
                if t.startswith(pattern):
                    matched_tables.append((t, fy, page, company_display, fy_val))

    matched_tables = sorted(set(matched_tables), key=lambda x: x[0])
    if not matched_tables:
        return ""

    print(f"Tables matched: {[t[0] for t in matched_tables[:MAX_TABLES]]}")

    snippets = []

    for table, fy, page, company_display, fy_val in matched_tables[:MAX_TABLES]:
        try:
            cursor.execute(f'PRAGMA table_info("{table}")')
            cols = [c[1] for c in cursor.fetchall()]
            if not cols:
                continue

            cursor.execute(f'SELECT * FROM "{table}" LIMIT {MAX_ROWS_PER_TABLE}')
            rows = cursor.fetchall()
            if not rows:
                continue

            # --- FILTER ROWS BY QUESTION ---
            query_lower = question.lower()
            matched_rows = []
            
            for metric, terms in ROW_FILTER_KEYWORDS.items():
                if any(term in query_lower for term in terms):
                    for row in rows:
                        first_col = str(row[0]).lower() if row[0] else ""
                        if any(term in first_col for term in terms):
                            matched_rows.append(row)
                    break
            
            # If no specific match, use first 3 rows only
            display_rows = matched_rows if matched_rows else rows[:3]

            # --- FORMAT WITH ROW LABELS ---
            header = " | ".join(cols)
            sep = " | ".join(["---"] * len(cols))
            
            row_lines = []
            for row in display_rows:
                cells = [str(c)[:50] if c is not None else "-" for c in row]
                # Bold the first column (metric name)
                cells[0] = f"**{cells[0]}**"
                row_lines.append(" | ".join(cells))

            # Add question context
            question_note = f"\n> RELEVANT ROWS for: '{question}'\n> Only use the row that matches this question. Ignore unrelated rows.\n"

            snippets.append(
                f"**Table: {table} ({company_display} | {fy_val} | Page {page})**"
                f"{question_note}"
                f"{header}\n{sep}\n" + "\n".join(row_lines)
            )

        except Exception as e:
            print(f"Table error ({table}): {e}")
            continue

    return "\n\n".join(snippets)


# --- SLM Compression ---

def compress_with_slm(raw_context: str, question: str) -> str:
    if not raw_context or len(raw_context) < 600:
        return raw_context

    compress_prompt = f"""You are a financial data compressor. Condense the context into a dense factual briefing.

ABSOLUTE RULES:
- Preserve EVERY financial ratio, percentage, and absolute number exactly as written.
- NEVER confuse Gross NPA with Net NPA. They are different metrics.
- NEVER confuse any metric with another.
- Keep source citations with EXACT company names, FY, and page numbers.
- If a metric is NOT in the context, do NOT invent it.
- Remove narrative filler, adjectives, and generic statements.
- Output ONLY compressed facts. No intro, no conclusion.

Question: {question}

Context:
{raw_context[:8000]}

Compressed Facts:"""

    try:
        resp = ollama.chat(
            model=COMPRESS_MODEL,
            messages=[{"role": "user", "content": compress_prompt}],
            options={"temperature": 0.0, "num_predict": 1024},
        )
        compressed = resp["message"]["content"].strip()
        return compressed if compressed else raw_context[:2000]
    except Exception as e:
        print(f"SLM compression failed ({e}). Using raw truncated context.")
        return raw_context[:2000]


# --- Main Query Function ---

def ask(
    question: str,
    company: str = None,
    fy: str = None,
    top_k: int = 6,
    fetch_k: int = 20,
    distance_cutoff: float = 0.65,
):
    print(f"\nQuestion: {question}\n")

    detected_companies = extract_companies(question)
    detected_fy = extract_fy(question)

    if detected_companies:
        db_vals = ticker_to_db_values(detected_companies)
        print(f"Detected companies: {detected_companies} -> DB values: {db_vals}")
    if detected_fy or fy:
        print(f"Detected FY: {detected_fy or fy}")

    # 1. Vector Layer (Chroma + Ollama)
    query_embedding = ollama.embed(model=EMBED_MODEL, input=question).embeddings[0]

    where = build_where(detected_companies, detected_fy, company, fy)
    if where:
        print(f"Chroma filtering: {where}")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    raw_docs = results["documents"][0]
    raw_metadatas = results["metadatas"][0]
    raw_distances = results["distances"][0]

    if not raw_docs:
        print("-" * 50)
        print("ChromaDB returned 0 results.")
        if detected_fy or fy:
            where_nofy = build_where(detected_companies, None, company, None)
            r2 = collection.query(
                query_embeddings=[query_embedding], n_results=10,
                where=where_nofy, include=["metadatas"],
            )
            if r2["metadatas"][0]:
                fys = sorted(set(m.get("fy", "?") for m in r2["metadatas"][0]))
                print(f"Company data exists under FY tags: {fys}")
            else:
                print("No data for this company.")
        print("-" * 50)
        return

    filtered = [
        (doc, meta, dist)
        for doc, meta, dist in zip(raw_docs, raw_metadatas, raw_distances)
        if dist <= distance_cutoff
    ]

    if not filtered:
        print("-" * 50)
        print(f"No chunks passed distance cutoff ({distance_cutoff}).")
        if raw_distances:
            print(f"Best distance: {raw_distances[0]:.3f}")
        print("-" * 50)
        return

    docs_filtered = [d for d, _, _ in filtered]
    meta_filtered = [m for _, m, _ in filtered]
    dist_filtered = [v for _, _, v in filtered]

    print(f"Reranking {len(docs_filtered)} chunks to top {top_k}...")
    reranked_docs = rerank_docs(question, docs_filtered, top_k)
    reranked_meta = [meta_filtered[docs_filtered.index(d)] for d in reranked_docs]

    # 2. Table Layer (with question for row filtering)
    table_context = fetch_tables_by_pages(conn, reranked_meta, question=question)
    if table_context:
        print("Tables from pages: Yes")
    else:
        print("Tables from pages: No")

    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0] + " ..."

    text_context = "\n\n---\n\n".join(
        f"[{m.get('company')} | {m.get('fy')} | Page {m.get('page')} | {m.get('section')}]\n{_truncate(d, MAX_CHUNK_CHARS)}"
        for d, m in zip(reranked_docs, reranked_meta)
    )

    # 3. Assemble Raw Context
    parts = []
    if table_context:
        parts.append(f"STRUCTURED TABLES:\n{table_context}")
    if text_context:
        parts.append(f"NARRATIVE CHUNKS:\n{text_context}")

    if not parts:
        print("No data from tables or text.")
        return

    raw_context = "\n\n===\n\n".join(parts)
    print(f"Raw context size: {len(raw_context)} chars")

    # 4. SLM Compression
    compressed_context = compress_with_slm(raw_context, question)
    print(f"Compressed size: {len(compressed_context)} chars")

    # Hard cap
    if len(compressed_context) > MAX_CONTEXT_CHARS:
        print(f"Truncating from {len(compressed_context)} to {MAX_CONTEXT_CHARS} chars")
        compressed_context = compressed_context[:MAX_CONTEXT_CHARS].rsplit("\n", 1)[0]

    print("\nCompressed context sent to Groq:\n" + "-" * 50)
    print(compressed_context[:1200])
    print("-" * 50 + " ... (truncated for display)")

    # 5. Groq Compound Call
    try:
        response = groq_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{compressed_context}\n\nQuestion: {question}\n\nAnswer:"},
            ],
            temperature=0.1,
            max_completion_tokens=2048,
        )

        print("\n" + "=" * 60)
        print(response.choices[0].message.content)
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"Groq API error: {e}")
        print(f"Context length sent: {len(compressed_context)} chars")
        print("=" * 60)

    print("\nSources:")
    if table_context:
        print("  [Structured tables from same pages]")
    for d, m in zip(reranked_docs, reranked_meta):
        dist = dist_filtered[docs_filtered.index(d)]
        print(f"  - {m.get('company')} {m.get('fy')} P{m.get('page')} [{m.get('section')}] (dist={dist:.3f})")
    print(f"\n  (fetched {len(docs_filtered)} after cutoff from {len(raw_docs)} raw)")


# --- Init & Run ---
conn = sqlite3.connect(DB_PATH)
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(name=COLLECTION)
print(f"Chunks in DB: {collection.count()}")

if __name__ == "__main__":
    print("\nFinnAI ready. Type your question and press Enter.")
    print("Type END to quit.\n")

    while True:
        question = input("Ask: ").strip()
        if question.upper() == "END":
            print("\nGoodbye.")
            break
        if not question:
            continue
        ask(question)
        print()