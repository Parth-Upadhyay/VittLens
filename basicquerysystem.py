"""
NIFTY 20 RAG — BM25 + Dense + RRF with Visual-Aware Reranking,
Explainable Provenance, and Smart Compression (SLM or Direct)
"""

import os
import re
import math
import sqlite3
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

import chromadb
import ollama
from groq import Groq
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
DB_PATH       = r"C:\Users\P\Documents\finnai\data\nifty_top20\tables.db"
CHROMA_PATH   = r"C:\Users\P\Documents\finnai\data\nifty_top20\chromaqwen0-6bembedding"
COLLECTION    = "qwen3_0_6bembeddingreports"
EMBED_MODEL   = "qwen3-embedding:0.6b"
LLM_MODEL     = "groq/compound"
LLM_FALLBACK  = "llama-3.3-70b-versatile"
COMPRESS_MODEL = "phi4-mini:latest"

RRF_K         = 60
BM25_TOP_K    = 50
DENSE_FETCH_K = 20
FUSION_TOP_K  = 10
RERANK_TOP_K  = 3
MAX_CONTEXT_CHARS = 1200

# Smart compression threshold: if raw context is under this, skip SLM entirely
DIRECT_SEND_THRESHOLD = 1500

MAX_CHUNK_CHARS = 800
MAX_ROWS_PER_TABLE = 3
MAX_TABLES = 2

VISUAL_KEYWORDS = {"chart", "graph", "pie", "bar", "line", "image", "visual",
                   "show me", "diagram", "plot", "infographic", "picture"}
VISUAL_BOOST = 1.5

# ═══════════════════════════════════════════════════════════
# CLIENTS
# ═══════════════════════════════════════════════════════════
print("Loading reranker model...")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
print("Reranker loaded.\n")

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ═══════════════════════════════════════════════════════════
# MAPPINGS
# ═══════════════════════════════════════════════════════════
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
3. ALSO cite the RETRIEVAL PROVENANCE for each fact: (Dense rank #X, BM25 rank #Y, Rerank score: Z).
4. For comparisons, you MUST have data for BOTH sides.
5. If the context is insufficient, say so explicitly.
6. Do not mention any company that was not asked about.
7. Be concise. Lead with the direct answer, then cite sources.
8. If multiple rows are provided, pick the ONE row that directly answers the question. Do not list all rows."""


# ═══════════════════════════════════════════════════════════
# BM25
# ═══════════════════════════════════════════════════════════
class SimpleBM25:
    def __init__(self, documents: List[str]):
        self.k1 = 1.5
        self.b = 0.75
        self.docs = documents
        self.N = len(documents)
        self.tokenized = [self._tokenize(d) for d in documents]
        self.doc_freqs = self._compute_df()
        self.idf = {term: math.log((self.N - f + 0.5) / (f + 0.5) + 1.0)
                    for term, f in self.doc_freqs.items()}
        self.doc_lengths = [len(t) for t in self.tokenized]
        self.avgdl = sum(self.doc_lengths) / self.N if self.N > 0 else 0

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t.lower() for t in re.findall(r'[a-zA-Z0-9]+', text or '')]

    def _compute_df(self) -> Dict[str, int]:
        df = defaultdict(int)
        for tokens in self.tokenized:
            seen = set(tokens)
            for t in seen:
                df[t] += 1
        return dict(df)

    def score(self, query: str) -> List[Tuple[int, float]]:
        q_tokens = self._tokenize(query)
        scores = [0.0] * self.N
        for q in q_tokens:
            if q not in self.idf:
                continue
            w = self.idf[q]
            for i, tokens in enumerate(self.tokenized):
                f = tokens.count(q)
                if f == 0:
                    continue
                dl = self.doc_lengths[i]
                denom = f + self.k1 * (1 - self.b + self.b * (dl / self.avgdl))
                scores[i] += w * (f * (self.k1 + 1)) / denom
        return sorted(enumerate(scores), key=lambda x: x[1], reverse=True)


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════
def extract_companies(query: str) -> list:
    q = query.lower()
    found = []
    for alias in sorted(COMPANY_ALIASES, key=len, reverse=True):
        if alias in q and COMPANY_ALIASES[alias] not in found:
            found.append(COMPANY_ALIASES[alias])
    return found


def extract_fy(query: str) -> Optional[str]:
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


def build_where(companies: list, fy: Optional[str], manual_company: Optional[str],
                manual_fy: Optional[str]) -> Optional[dict]:
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


def is_visual_query(query: str) -> bool:
    q_lower = query.lower()
    return any(kw in q_lower for kw in VISUAL_KEYWORDS)


def rerank_docs(query: str, docs: list, metas: list, top_k: int, visual_boost: bool = False) -> List[Tuple[str, float, dict]]:
    if not docs:
        return []
    pairs = [(query, doc) for doc in docs]
    scores = reranker.predict(pairs)
    
    adjusted_scores = []
    for score, meta in zip(scores, metas):
        adj = score
        if visual_boost and meta.get("is_visual") == "true":
            adj += VISUAL_BOOST
        adjusted_scores.append(adj)
    
    ranked = sorted(zip(adjusted_scores, docs, metas), key=lambda x: x[0], reverse=True)
    return [(doc, round(score, 3), meta) for score, doc, meta in ranked[:top_k]]


# ═══════════════════════════════════════════════════════════
# TABLE LAYER
# ═══════════════════════════════════════════════════════════
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

            query_lower = question.lower()
            matched_rows = []
            for metric, terms in ROW_FILTER_KEYWORDS.items():
                if any(term in query_lower for term in terms):
                    for row in rows:
                        first_col = str(row[0]).lower() if row[0] else ""
                        if any(term in first_col for term in terms):
                            matched_rows.append(row)
                    break

            display_rows = matched_rows if matched_rows else rows[:3]

            header = " | ".join(cols)
            sep = " | ".join(["---"] * len(cols))
            row_lines = []
            for row in display_rows:
                cells = [str(c)[:50] if c is not None else "-" for c in row]
                cells[0] = f"**{cells[0]}**"
                row_lines.append(" | ".join(cells))

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


# ═══════════════════════════════════════════════════════════
# SLM COMPRESSION WITH CITATION PRESERVATION (Option A)
# ═══════════════════════════════════════════════════════════
def compress_with_slm(raw_context: str, question: str) -> str:
    if not raw_context or len(raw_context) < 600:
        return raw_context

    compress_prompt = f"""You are a financial data compressor. Condense the context into a dense factual briefing.

ABSOLUTE RULES:
- Preserve EVERY financial ratio, percentage, and absolute number exactly as written.
- NEVER confuse Gross NPA with Net NPA. They are different metrics.
- NEVER confuse any metric with another.
- KEEP ALL source citations in the format: (Company | FY | Page | Dense rank #X, BM25 rank #Y, Rerank score: Z).
- Keep the RETRIEVAL PROVENANCE tags intact in every fact line.
- If a metric is NOT in the context, do NOT invent it.
- Remove narrative filler, adjectives, and generic statements.
- Output ONLY compressed facts with their citations. No intro, no conclusion.

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


# ═══════════════════════════════════════════════════════════
# RRF FUSION WITH PROVENANCE
# ═══════════════════════════════════════════════════════════
def reciprocal_rank_fusion(dense_results: list, sparse_results: list, k: int = 60):
    scores = defaultdict(float)
    prov = {}

    for rank, (doc, meta, dist) in enumerate(dense_results):
        key = (doc, tuple(sorted(meta.items())))
        scores[key] += 1.0 / (k + rank + 1)
        prov[key] = {"dense_rank": rank + 1, "dense_dist": round(dist, 3)}

    for rank, (doc, meta, bm25_score) in enumerate(sparse_results):
        key = (doc, tuple(sorted(meta.items())))
        scores[key] += 1.0 / (k + rank + 1)
        if key in prov:
            prov[key]["bm25_rank"] = rank + 1
            prov[key]["bm25_score"] = round(bm25_score, 3)
        else:
            prov[key] = {"bm25_rank": rank + 1, "bm25_score": round(bm25_score, 3)}

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for key, rrf_score in fused:
        doc, meta_items = key
        result.append((doc, dict(meta_items), rrf_score, prov.get(key, {})))
    return result


# ═══════════════════════════════════════════════════════════
# EXPLAINABILITY PRINTOUT
# ═══════════════════════════════════════════════════════════
def explain_retrieval(reranked_docs, reranked_metas, reranked_provs, reranked_scores):
    print("\n" + "─"*70)
    print("RETRIEVAL EXPLANATION (Explainable AI Audit Trail)")
    print("─"*70)
    for i, (doc, meta, prov, score) in enumerate(zip(reranked_docs, reranked_metas, reranked_provs, reranked_scores), 1):
        src = f"{meta.get('company')} {meta.get('fy')} P{meta.get('page')}"
        is_vis = " [VISUAL]" if meta.get("is_visual") == "true" else ""
        dense = f"Dense #{prov.get('dense_rank', '—')} (dist={prov.get('dense_dist', '—')})"
        if 'bm25_rank' in prov:
            bm25 = f"BM25 #{prov['bm25_rank']} (score={prov['bm25_score']})"
        else:
            bm25 = "BM25: not in top-50"
        print(f"  [{i}] {src}{is_vis}")
        print(f"      Path: {dense} | {bm25}")
        print(f"      Rerank score: {score}")
        print(f"      Section: {meta.get('section', 'N/A')[:60]}")
    print("─"*70)


# ═══════════════════════════════════════════════════════════
# GROQ CALL WITH FALLBACK
# ═══════════════════════════════════════════════════════════
def groq_generate(compressed_context: str, question: str, model: str = LLM_MODEL):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{compressed_context}\n\nQuestion: {question}\n\nAnswer:"},
    ]
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_completion_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        err_str = str(e).lower()
        if "413" in err_str or "too large" in err_str or "request_too_large" in err_str:
            print(f"  [!] {model} returned 413. Falling back to {LLM_FALLBACK}...")
            return groq_generate(compressed_context, question, model=LLM_FALLBACK)
        raise


# ═══════════════════════════════════════════════════════════
# MAIN QUERY
# ═══════════════════════════════════════════════════════════
def ask(
    question: str,
    company: str = None,
    fy: str = None,
    top_k: int = 3,
    fetch_k: int = 20,
    distance_cutoff: float = 0.65,
):
    print(f"\nQuestion: {question}\n")

    visual_query = is_visual_query(question)
    if visual_query:
        print(f"[Visual query detected — boosting chart/image chunks by +{VISUAL_BOOST}]")

    detected_companies = extract_companies(question)
    detected_fy = extract_fy(question)

    if detected_companies:
        db_vals = ticker_to_db_values(detected_companies)
        print(f"Detected companies: {detected_companies} -> DB values: {db_vals}")
    if detected_fy or fy:
        print(f"Detected FY: {detected_fy or fy}")

    # ── 1. DENSE RETRIEVAL ──
    query_embedding = ollama.embed(model=EMBED_MODEL, input=question).embeddings[0]

    where = build_where(detected_companies, detected_fy, company, fy)
    if where:
        print(f"Chroma filtering: {where}")

    dense_raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    raw_docs = dense_raw["documents"][0]
    raw_metas = dense_raw["metadatas"][0]
    raw_dists = dense_raw["distances"][0]

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

    dense_filtered = [
        (doc, meta, dist)
        for doc, meta, dist in zip(raw_docs, raw_metas, raw_dists)
        if dist <= distance_cutoff
    ]
    if not dense_filtered:
        print(f"No chunks passed distance cutoff ({distance_cutoff}). Best: {raw_dists[0]:.3f}")
        return

    print(f"Dense retrieval: {len(dense_filtered)} chunks (cutoff {distance_cutoff})")

    # ── 2. SPARSE RETRIEVAL (BM25) ──
    bm25_docs = [d for d, _, _ in dense_filtered]
    bm25_metas = [m for _, m, _ in dense_filtered]

    if len(bm25_docs) < 20:
        all_data = collection.get(where=where, include=["documents", "metadatas"])
        bm25_docs = all_data["documents"]
        bm25_metas = all_data["metadatas"]

    print(f"BM25 index size: {len(bm25_docs)} documents")
    bm25 = SimpleBM25(bm25_docs)
    sparse_scores = bm25.score(question)
    sparse_top = sparse_scores[:BM25_TOP_K]
    sparse_results = [(bm25_docs[i], bm25_metas[i], score) for i, score in sparse_top]

    print(f"Sparse retrieval: top-{len(sparse_results)} BM25 hits")

    # ── 3. RRF FUSION ──
    fused = reciprocal_rank_fusion(dense_filtered, sparse_results, k=RRF_K)
    print(f"RRF fusion: top-{len(fused)} unique chunks")

    # ── 4. CROSS-ENCODER RERANK (with visual boost) ──
    fused_docs = [d for d, _, _, _ in fused[:FUSION_TOP_K]]
    fused_metas = [m for _, m, _, _ in fused[:FUSION_TOP_K]]
    fused_provs = [p for _, _, _, p in fused[:FUSION_TOP_K]]

    if not fused_docs:
        print("No documents after fusion.")
        return

    print(f"Reranking top-{len(fused_docs)} fused chunks to final {top_k}...")
    reranked = rerank_docs(question, fused_docs, fused_metas, top_k, visual_boost=visual_query)
    reranked_docs = [d for d, _, _ in reranked]
    reranked_scores = [s for _, s, _ in reranked]
    reranked_metas = [m for _, _, m in reranked]

    reranked_provs = []
    for d in reranked_docs:
        idx = fused_docs.index(d)
        reranked_provs.append(fused_provs[idx])

    # ── 5. EXPLAINABILITY PRINTOUT ──
    explain_retrieval(reranked_docs, reranked_metas, reranked_provs, reranked_scores)

    # ── 6. VISUAL SURFACE ──
    visual_hits = [(d, m, s) for d, m, s in zip(reranked_docs, reranked_metas, reranked_scores)
                   if m.get("is_visual") == "true"]
    if visual_hits:
        print("\n📊 VISUAL CHUNKS RETRIEVED:")
        for d, m, s in visual_hits:
            vtype = m.get('visual_type', 'image').upper()
            vpath = m.get('visual_path', 'N/A')
            print(f"  [{m.get('company')} {m.get('fy')} P{m.get('page')}] {vtype}")
            print(f"      Path: {vpath}")
            print(f"      Rerank score: {s}")

    # ── 7. TABLE LAYER ──
    table_context = fetch_tables_by_pages(conn, reranked_metas, question=question)
    if table_context:
        print("Tables from pages: Yes")
    else:
        print("Tables from pages: No")

    # ── 8. ASSEMBLE CONTEXT WITH PROVENANCE HEADERS ──
    def _make_source_block(doc, meta, prov, rerank_score):
        lines = [
            f"[Company:{meta.get('company')} | FY:{meta.get('fy')} | Page:{meta.get('page')} | Section:{meta.get('section')}]",
        ]
        dense_str = f"Dense rank #{prov.get('dense_rank', 'N/A')} (dist={prov.get('dense_dist', 'N/A')})"
        if 'bm25_rank' in prov:
            bm25_str = f"BM25 rank #{prov['bm25_rank']} (score={prov['bm25_score']})"
        else:
            bm25_str = "BM25: absent"
        lines.append(f"[Retrieval: {dense_str} | {bm25_str} | Rerank score: {rerank_score}]")
        lines.append(doc)
        return "\n".join(lines)

    text_context = "\n\n---\n\n".join(
        _make_source_block(d, m, p, s)
        for d, m, p, s in zip(reranked_docs, reranked_metas, reranked_provs, reranked_scores)
    )

    parts = []
    if table_context:
        parts.append(f"STRUCTURED TABLES:\n{table_context}")
    if text_context:
        parts.append(f"NARRATIVE CHUNKS:\n{text_context}")

    if not parts:
        print("No data from tables or text.")
        return

    raw_context = "\n\n===\n\n".join(parts)
    raw_len = len(raw_context)
    print(f"\nRaw context size: {raw_len} chars")

    # ═══════════════════════════════════════════════════════════
    # 9. SMART COMPRESSION: Option B (direct) or Option A (SLM)
    # ═══════════════════════════════════════════════════════════
    if raw_len <= DIRECT_SEND_THRESHOLD:
        # OPTION B: Skip SLM — send raw directly. Citations stay intact.
        compressed_context = raw_context
        print(f"[DIRECT SEND] Raw context under {DIRECT_SEND_THRESHOLD} chars — skipping SLM compression")
        compression_method = "direct"
    else:
        # OPTION A: SLM compression with citation preservation instruction
        compressed_context = compress_with_slm(raw_context, question)
        print(f"[SLM COMPRESSION] Compressed size: {len(compressed_context)} chars")
        compression_method = "slm"

    if len(compressed_context) > MAX_CONTEXT_CHARS:
        print(f"WARNING: Truncating from {len(compressed_context)} to {MAX_CONTEXT_CHARS} chars")
        compressed_context = compressed_context[:MAX_CONTEXT_CHARS].rsplit("\n", 1)[0]

    print("\nCompressed context sent to Groq:\n" + "-" * 50)
    print(compressed_context[:1200])
    print("-" * 50 + " ... (truncated for display)")

    # ── 10. GROQ GENERATION ──
    try:
        answer = groq_generate(compressed_context, question)
        print("\n" + "=" * 60)
        print(answer)
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"Groq API error: {e}")
        print(f"Context length sent: {len(compressed_context)} chars")
        print("=" * 60)

    # ── 11. FINAL SOURCE TRACE ──
    print("\nSources:")
    if table_context:
        print("  [Structured tables from same pages]")
    for d, m, p, s in zip(reranked_docs, reranked_metas, reranked_provs, reranked_scores):
        src = f"{m.get('company')} {m.get('fy')} P{m.get('page')}"
        vis_tag = " [VISUAL]" if m.get("is_visual") == "true" else ""
        prov_str = f"Dense#{p.get('dense_rank','—')} BM25#{p.get('bm25_rank','—')} Rerank={s}"
        print(f"  - {src}{vis_tag} [{prov_str}]")
    print(f"\n  Compression: {compression_method} | fused {len(fused)} from dense {len(dense_filtered)} + sparse {len(sparse_results)}")


# ═══════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════
conn = sqlite3.connect(DB_PATH)
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(name=COLLECTION)
print(f"Chunks in NIFTY 20 DB: {collection.count()}")

if __name__ == "__main__":
    print("\nNIFTY 20 RAG ready. BM25 + Dense + RRF + Visual Boost + Explainable Provenance.")
    print(f"Smart compression: direct send if <{DIRECT_SEND_THRESHOLD} chars, else SLM with citation preservation.")
    print("Type your question and press Enter. Type END to quit.\n")

    while True:
        question = input("Ask: ").strip()
        if question.upper() == "END":
            print("\nGoodbye.")
            break
        if not question:
            continue
        ask(question)
        print()