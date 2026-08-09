import os
import requests
# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from typing import Optional
from groq import Groq

load_dotenv()

COMPANY_VARIANTS = {
    "RELIANCE": ["Reliance Industries", "Reliance"],
    "HDFCBANK": ["HDFC Bank", "Hdfcbank"],
    "BHARTIARTL": ["Bharti Airtel", "Airtel"],
    "ICICIBANK": ["ICICI Bank"],
    "SBIN": ["State Bank of India", "SBI", "Sbin"],
    "TCS": ["Tata Consultancy Services", "TCS"],
    "BAJFINANCE": ["Bajaj Finance", "Bajfinance"],
    "LT": ["Larsen & Toubro", "L&T", "Larsen and Toubro"],
    "HINDUNILVR": ["Hindustan Unilever", "HUL"],
    "SUNPHARMA": ["Sun Pharma", "Sun Pharmaceuticals", "Sun Pharmaceutical"],
    "MARUTI": ["Maruti Suzuki", "Maruti"],
    "INFY": ["Infosys", "Infy"],
    "ADANIENT": ["Adani Enterprises", "Adanient"],
    "ADANIPORTS": ["Adani Ports", "Adani Ports & SEZ", "Adani Ports and SEZ"],
    "AXISBANK": ["Axis Bank", "Axisbank"],
    "TITAN": ["Titan Company", "Titan"],
    "M&M": ["Mahindra & Mahindra", "Mahindra and Mahindra", "M&M"],
    "KOTAKBANK": ["Kotak Mahindra Bank", "Kotakbank"],
    "ITC": ["ITC", "ITC Limited"],
    "ULTRACEMCO": ["UltraTech Cement", "Ultratech"],
}

QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
COLLECTION = "ollama_bge_m3_nifty20"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
from huggingface_hub import InferenceClient
hf_client = InferenceClient(token=HF_TOKEN) if HF_TOKEN else None
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "<YOUR_CLOUD_NAME>")

# Toggle this to False to easily remove/disable Groq synthesis
USE_GROQ = True
# Toggle this to False to easily disable Jina Reranking
USE_JINA_RERANKER = True

COMPANY_ALIASES = {
    # Reliance
    "reliance industries": "RELIANCE", "reliance": "RELIANCE", "ril": "RELIANCE",
    "reliance ind": "RELIANCE", "rel industries": "RELIANCE", "reliance inds": "RELIANCE",
    
    # HDFC Bank
    "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK", "hdfcbank": "HDFCBANK", 
    "housing development finance": "HDFCBANK", "hdfc bk": "HDFCBANK", "hdfc limited": "HDFCBANK",
    
    # Bharti Airtel
    "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL", "bharti": "BHARTIARTL",
    "bhartiairtel": "BHARTIARTL", "bharti telecom": "BHARTIARTL",
    
    # ICICI Bank
    "icici bank": "ICICIBANK", "icici": "ICICIBANK", "icicibank": "ICICIBANK", "icici bk": "ICICIBANK",
    
    # SBI
    "state bank of india": "SBIN", "state bank": "SBIN", "sbi": "SBIN", "sbin": "SBIN", 
    "sbi bank": "SBIN", "statebank": "SBIN",
    
    # TCS
    "tata consultancy services": "TCS", "tcs": "TCS", "tata consultancy": "TCS", 
    "tata cons": "TCS", "tcs ltd": "TCS", "tata tcs": "TCS",
    
    # Bajaj Finance
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE", "bajaj fin": "BAJFINANCE", 
    "bfl": "BAJFINANCE", "bajaj finance ltd": "BAJFINANCE",
    
    # L&T
    "larsen & toubro": "LT", "larsen and toubro": "LT", "l&t": "LT", "lt": "LT", 
    "larsen": "LT", "l and t": "LT",
    
    # Hindustan Unilever
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR", "hindustan lever": "HINDUNILVR", 
    "hindunilvr": "HINDUNILVR", "unilever": "HINDUNILVR",
    
    # Sun Pharma
    "sun pharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA", "sun pharmaceuticals": "SUNPHARMA",
    "sunpharma": "SUNPHARMA", "sun": "SUNPHARMA",
    
    # Maruti Suzuki
    "maruti suzuki": "MARUTI", "maruti": "MARUTI", "maruti suzuki india": "MARUTI", 
    "msil": "MARUTI", "marutisuzuki": "MARUTI",
    
    # Infosys
    "infosys": "INFY", "infy": "INFY", "infosys ltd": "INFY", "infosys limited": "INFY",
    
    # Adani Enterprises
    "adani enterprises": "ADANIENT", "adani enterprises limited": "ADANIENT",
    "adani ent": "ADANIENT", "adanient": "ADANIENT", "adani enterprise": "ADANIENT",
    
    # Adani Ports
    "adani ports": "ADANIPORTS", "adani ports & sez": "ADANIPORTS", "adani ports and sez": "ADANIPORTS",
    "adani port": "ADANIPORTS", "adaniports": "ADANIPORTS",
    
    # Axis Bank
    "axis bank": "AXISBANK", "axis": "AXISBANK", "axisbank": "AXISBANK", 
    "axis bk": "AXISBANK", "uti bank": "AXISBANK",
    
    # Titan
    "titan company": "TITAN", "titan": "TITAN", "titan ind": "TITAN", "titan industries": "TITAN",
    
    # M&M
    "mahindra & mahindra": "M&M", "mahindra and mahindra": "M&M", "m&m": "M&M", 
    "mahindra": "M&M", "m and m": "M&M", "mnm": "M&M",
    
    # Kotak Mahindra Bank
    "kotak mahindra bank": "KOTAKBANK", "kotak bank": "KOTAKBANK", "kotak": "KOTAKBANK", 
    "kotakbank": "KOTAKBANK", "kmb": "KOTAKBANK", "kotak mahindra": "KOTAKBANK",
    
    # ITC
    "itc": "ITC", "itc limited": "ITC", "itc ltd": "ITC", "indian tobacco company": "ITC",
    
    # UltraTech Cement
    "ultratech cement": "ULTRACEMCO", "ultratech": "ULTRACEMCO", "ultra tech": "ULTRACEMCO",
    "ultracemco": "ULTRACEMCO", "ultra tech cement": "ULTRACEMCO",
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

def extract_companies(query: str) -> list:
    q = query.lower()
    found = []
    for alias in sorted(COMPANY_ALIASES, key=len, reverse=True):
        if alias in q and COMPANY_ALIASES[alias] not in found:
            found.append(COMPANY_ALIASES[alias])
    return found

def extract_fy(query: str) -> list:
    q = query.lower()
    found = []
    for alias in sorted(FY_ALIASES, key=len, reverse=True):
        if alias in q and FY_ALIASES[alias] not in found:
            found.append(FY_ALIASES[alias])
    return found

def ticker_to_db_values(tickers: list) -> list:
    values = []
    for t in tickers:
        values.extend(COMPANY_VARIANTS.get(t, [t]))
    return values

def synthesize_with_groq(question: str, documents: list) -> str:
    """Removable Groq synthesis layer"""
    if not GROQ_API_KEY or not USE_GROQ:
        return "[Groq synthesis is disabled or API key is missing]"
        
    print("Synthesizing answer with Groq...")
    client = Groq(api_key=GROQ_API_KEY)
    
    # Compress context and explicitly inject company metadata to trigger scale awareness
    context_chunks = []
    for doc in documents:
        company = doc.payload.get("company", "Unknown Company")
        text = doc.payload.get("document", "")
        context_chunks.append(f"[Source Metadata: Company={company}]\n{text}")
    context_text = "\n\n---\n\n".join(context_chunks)
    
    system_prompt = f"""You are a senior financial analyst assistant specialising in Indian banking and financial services.
CRITICAL RULES:
1. UNIT AWARENESS & DEFAULT SCALES: You must state currency units and scales explicitly (e.g., "₹ Crores", "₹ Lakhs"). 
   ⚠️ CRITICAL: Indian Nifty 50 companies (like UltraTech, Reliance, HDFC) report financials in ₹ Lakhs or ₹ Crores. If a text chunk provides a massive raw number (e.g., 9,652,828) for a revenue metric without a unit, DO NOT output just the raw number. Use financial common sense: assume the base unit from the report was '₹ in Lakhs' (meaning 9,652,828 Lakhs = ₹96,528 Crores) or '₹ in Crores'. Always format your final answer in ₹ Crores for large-cap companies unless specifically asked otherwise.
2. NO CURRENCY CONVERSION: Do not convert between USD and INR, but YOU MUST scale raw table numbers correctly using Indian numbering systems (Lakhs/Crores) if the OCR chunk dropped the unit header.
3. VALIDATION LAYER (SANITY CHECK): Perform a strict sanity check on your final numbers. Do the segments add up to the total? Are margins mathematically realistic for the sector? If you are reporting an annual revenue for a Nifty 50 company that is under ₹1,000 Crores, you have likely missed a "₹ in Lakhs/Crores" unit modifier. If the extracted numbers seem illogical, you MUST start your response with "⚠️ SANITY WARNING: " followed by the reason.
4. VISUAL CHARTS: ONLY if the context contains references to visual charts (paths with '{{BASE_DIR}}/visuals/'), return a separated Cloudinary link formatting it as 'https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/finnai/visuals/<relative_path_without_extension>'. If there are no image paths in the context, DO NOT mention visuals, images, or charts in your response at all."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}\n\nAnswer:"}
    ]
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            max_completion_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq synthesis failed: {e}"

def embed_query(query: str):
    if not hf_client:
        raise Exception("HF_TOKEN is not set.")
    result = hf_client.feature_extraction(query, model="BAAI/bge-m3")
    if hasattr(result, 'tolist'):
        result = result.tolist()
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        return result[0]
    return result

def rerank_with_jina(query: str, documents: list, top_n: int = 3):
    if not JINA_API_KEY:
        print("[WARNING] JINA_API_KEY not found. Skipping reranking.")
        return documents[:top_n]
        
    print("Reranking with Jina...")
    # Jina reranker expects a list of text strings or dicts with text
    texts = [doc.payload.get("document", "") for doc in documents]
    
    resp = requests.post(
        "https://api.jina.ai/v1/rerank",
        headers={
            "Authorization": f"Bearer {JINA_API_KEY}", 
            "Content-Type": "application/json"
        },
        json={
            "model": "jina-reranker-v2-base-multilingual",
            "query": query,
            "documents": texts,
            "top_n": top_n
        }
    )
    resp.raise_for_status()
    results = resp.json()["results"]
    
    # Map back to original Qdrant documents based on the index returned by Jina
    reranked_docs = []
    for res in results:
        idx = res["index"]
        original_doc = documents[idx]
        # Attach the reranker score to the document payload so we can display it
        original_doc.payload["jina_score"] = res["relevance_score"]
        reranked_docs.append(original_doc)
        
    return reranked_docs

qdrant = None

def init_qdrant():
    global qdrant
    if qdrant is None:
        print("Connecting to Qdrant...")
        qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
        try:
            qdrant.create_payload_index(collection_name=COLLECTION, field_name="company", field_schema=models.PayloadSchemaType.KEYWORD)
            qdrant.create_payload_index(collection_name=COLLECTION, field_name="fy", field_schema=models.PayloadSchemaType.KEYWORD)
        except Exception:
            pass

def query_financial_data(question: str) -> str:
    """
    Main function to query Qdrant and synthesize an answer using Groq.
    Designed to be imported and used within a LangGraph chain or other frameworks.
    """
    init_qdrant()
    
    print("Embedding query...")
    query_vector = embed_query(question)
    
    # 1. Extract metadata filters from the question
    detected_companies = extract_companies(question)
    detected_fy = extract_fy(question)
    
    must_conditions = []
    
    if detected_companies:
        db_vals = ticker_to_db_values(detected_companies)
        print(f"Applying Company Filter: {db_vals}")
        must_conditions.append(
            models.FieldCondition(
                key="company", 
                match=models.MatchAny(any=db_vals)
            )
        )
        
    if detected_fy:
        print(f"Applying FY Filter: {detected_fy}")
        must_conditions.append(
            models.FieldCondition(
                key="fy", 
                match=models.MatchAny(any=detected_fy)
            )
        )
        
    qdrant_filter = models.Filter(must=must_conditions) if must_conditions else None

    print("Searching Qdrant...")
    # Retrieval Depth Adjustment
    is_deep_query = any(keyword in question.lower() for keyword in ["split", "breakdown", "segment", "revenue by", "geography", "subsidiary", "margin"])
    
    if USE_JINA_RERANKER:
        fetch_limit = 30 if is_deep_query else 15
        keep_top_n = 5 if is_deep_query else 3
    else:
        fetch_limit = 7 if is_deep_query else 3
        keep_top_n = fetch_limit
        
    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=fetch_limit
    ).points
    
    if not results:
        print("No results found.")
        return "I could not find any relevant information to answer your question."
        
    # 2. Rerank the initial dense results with Jina (if enabled)
    if USE_JINA_RERANKER:
        top_results = rerank_with_jina(question, results, top_n=keep_top_n)
        print(f"\nTop {len(top_results)} results after reranking:")
    else:
        top_results = results
        print(f"\nTop {len(top_results)} dense results (Reranking Disabled):")
        
    for i, res in enumerate(top_results, 1):
        doc = res.payload.get("document", "No text")
        jina_score = res.payload.get("jina_score", "N/A")
        score = res.score  # Original dense score
        meta = {k:v for k,v in res.payload.items() if k not in ["document", "jina_score"]}
        
        print(f"\n[{i}] Jina Rerank Score: {jina_score} (Original Dense Score: {score:.3f})")
        print(f"ID: {res.id}")
        print(f"Metadata:\n{meta}")
        print(f"Full Text Chunk:\n{doc}")
        print("-" * 50)
        
    if USE_GROQ:
        print("\n" + "="*20 + " GROQ SYNTHESIS " + "="*20)
        answer = synthesize_with_groq(question, top_results)
        return answer
    else:
        return "Groq synthesis is disabled."

if __name__ == "__main__":
    print("\nQdrant Test Query System (Dense + Metadata Filter + Jina Rerank + Groq Synthesis)")
    print("Type your question and press Enter. Type END to quit.\n")
    
    while True:
        try:
            user_q = input("Ask: ").strip()
            if user_q.upper() == "END":
                break
            if not user_q:
                continue
                
            ans = query_financial_data(user_q)
            if ans:
                print(f"\n{ans}")
                
            print("\n" + "="*50 + "\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"An error occurred: {e}")
