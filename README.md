# VittLens (formerly FinnAI)

A production-grade Financial Intelligence Platform built with a multi-agent AI architecture. VittLens empowers retail investors, researchers, and traders with AI-driven insights, RAG-powered SEC filing analysis, and real-time market data—all designed to operate efficiently within "No Credit Card" free-tier infrastructure.

Repository: **ArthDrishti**

---

## 🏛️ System Architecture

VittLens utilizes a microservices-inspired multi-agent architecture to process complex financial queries.

- **Frontend**: React, TypeScript, Tailwind CSS, Vite (Deployed on **Vercel**)
- **Backend**: FastAPI, Python (Deployed on **Render**)
- **Database**: PostgreSQL for relational user and chat data (Hosted on **Aiven**)
- **Vector Search**: Qdrant Cloud for storing and querying corporate SEC filings and annual reports
- **AI / LLM**: Groq API (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`)

---

## 🚀 Key Features

### 1. Multi-Agent Orchestration
VittLens dynamically routes your questions to specialized AI agents:
- **News Agent**: Analyzes the latest financial news, extracting sentiment and key entities.
- **Portfolio Agent**: Evaluates user portfolios against NIFTY 20/50 benchmarks and provides rebalancing suggestions.
- **Filing Agent (RAG)**: Conducts semantic search across Qdrant-vectorized corporate filings and reports.

### 2. Rate-Limiting & "No Credit Card" Cost Control
Designed specifically to respect strict free-tier quotas:
- **Guests**: Limited to **15** free AI queries per day (tracked securely via stateless HMAC-SHA256 cookies).
- **Authenticated Users**: Limited to **45** queries per day (tracked via Aiven PostgreSQL).
- **Context Management**: Prompts are strictly truncated to prevent `413 Request Too Large` errors and to respect the 8K-14K TPM limits of the Groq free tier.
- **Automatic Multi-Model Failover**: If an LLM rate limit (HTTP 429) is hit, the system automatically degrades gracefully to a smaller fallback model.

### 3. Stateless Guest Mode & Authentication
- Google OAuth 2.0 integration for seamless user onboarding.
- Guest Purpose Onboarding limits abuse while providing a generous trial experience for users.

---

## 🐳 Deployment (Docker & Cloud)

VittLens is fully containerized with a highly optimized `Dockerfile` tailored for Render.

- **Dynamic Port Binding**: Supports dynamic `$PORT` injection for Render compatibility.
- **`.dockerignore` Optimized**: Fast builds by ignoring local `.venv`, `__pycache__`, and node modules.

---

## 📥 Setup & Local Development

1. **Clone and Install Backend**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Copy `.env.example` to `.env` and configure your API Keys (Groq, Qdrant, Google OAuth, and Aiven Postgres URL).

3. **Run Backend**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Run Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
