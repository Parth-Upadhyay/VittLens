# FinnAI Platform - Core Foundation Layer

A production-grade Python core foundation for the **FinnAI Financial Intelligence Platform**, designed for high throughput, containerized deployment (Docker & Google Cloud Run), and seamless integration across downstream financial intelligence, agentic, and RAG modules.

---

## 🏛️ System Architecture

The core layer (`core/`) serves as the single source of truth for configuration, structured logging, domain schemas, error handling, and shared resilience primitives across the platform.

```
c:\Users\P\Documents\finnai
├── core/                        # Production-grade foundation package
│   ├── config/                  # Pydantic Settings & environment constants
│   │   ├── constants.py         # Global enums, environments, currency primitives
│   │   ├── settings.py          # Type-safe settings aggregator
│   │   └── __init__.py
│   ├── logging/                 # GCP Cloud Logging / Docker-friendly structured logging
│   │   ├── formatters.py        # JSON & Console log formatters
│   │   ├── logger.py            # Logger factory & context-aware log adapters
│   │   └── __init__.py
│   ├── schemas/                 # Shared data contracts & Pydantic models
│   │   ├── base.py              # Core base model with UTC serialization
│   │   ├── responses.py         # Standard API & paginated response envelopes
│   │   ├── financial.py         # Financial primitives (Ticker, Currency, Period, Monetary)
│   │   ├── errors.py            # Standardized error response models
│   │   └── __init__.py
│   ├── utils/                   # Shared utility modules & resilience decorators
│   │   ├── datetime_utils.py    # Timezone-aware dates & Indian fiscal quarter helpers
│   │   ├── exceptions.py        # Domain exception hierarchy
│   │   ├── sanitizers.py        # Financial number parsers & text sanitizers
│   │   ├── retry.py             # Exponential backoff retry decorator with jitter
│   │   └── __init__.py
│   └── env.py                   # Environment loader & validator
├── .env.example                 # Comprehensive environment variable template
├── requirements.txt             # Production dependency list
└── README.md                    # Core documentation
```

---

## 🚀 Key Features & Core Components

### 1. Configuration Management (`core.config`)
- Powered by `pydantic-settings` for type-safe environment variable parsing.
- Default settings auto-detect environment (`development`, `staging`, `production`, `testing`).
- Direct integration with `.env` files via `python-dotenv`.

```python
from core.config import settings

print(settings.app.name)           # "FinnAI Platform"
print(settings.app.is_production)  # False (in dev)
print(settings.resilience.max_retries) # 3
```

### 2. Cloud-Ready Structured Logging (`core.logging`)
- Automatic JSON formatting in `production` or when `LOGGING_FORMAT=json` is set, matching **Google Cloud Logging** severity and timestamp specifications.
- Human-readable colorized output for local CLI development.
- Thread and async task-safe context propagation (`LogContext`) to attach trace IDs, ticker symbols, or request context without modifying function signatures.

```python
from core.logging import get_logger, LogContext

logger = get_logger(__name__)

logger.info("Initializing financial analysis")

with LogContext(ticker="RELIANCE", trace_id="req_98765"):
    logger.info("Extracting balance sheet key metrics")
```

### 3. Domain Schemas & Contracts (`core.schemas`)
- **`CoreBaseModel`**: Enforces strict string stripping, UTC datetime serialization, and immutability options.
- **`MonetaryAmount`**: Value object pairing values with ISO currency codes (INR, USD, EUR, etc.).
- **`TickerSymbol`**: Normalized financial ticker validation (e.g. `RELIANCE`, `NSE:INFY`).
- **`FinancialPeriod`**: Fiscal year & quarter representation supporting Indian Fiscal Year cycles (April-March).
- **`APIResponse[T]` & `PaginatedResponse[T]`**: Uniform API response envelopes.

```python
from core.schemas import MonetaryAmount, Currency, TickerSymbol, FinancialPeriod

price = MonetaryAmount(amount=2450.75, currency=Currency.INR)
ticker = TickerSymbol(symbol="RELIANCE", exchange="NSE")
period = FinancialPeriod(fiscal_year=2024, quarter=3)

print(price.formatted)    # "INR 2,450.75"
print(ticker.full_ticker) # "NSE:RELIANCE"
print(period.label)       # "FY2024 Q3"
```

### 4. Utilities & Resilience (`core.utils`)
- **`retry_with_backoff`**: Sync & Async retry decorator with exponential backoff and randomized jitter to prevent thundering herd issues on external API calls.
- **`parse_financial_number`**: Extracts numeric figures from financial strings including crore (`Cr`), lakh (`Lk`), million (`M`), billion (`B`), and accounting parentheses `(100.00)`.
- **`FinnAIException`**: Domain exception hierarchy providing machine-readable error codes (`ConfigurationError`, `ValidationError`, `ExternalServiceError`, `RateLimitError`).

```python
from core.utils import retry_with_backoff, parse_financial_number, sanitize_ticker

@retry_with_backoff(max_retries=3, initial_delay=1.0)
def fetch_external_quote(symbol: str):
    ...

amount = parse_financial_number("₹ 12.5 Cr") # Returns 125000000.0
clean_symbol = sanitize_ticker(" nse: infy ") # Returns "NSE:INFY"
```

---

## 🐳 Docker & Cloud Run Readiness

The foundation is built to run seamlessly inside Google Cloud Run or Docker containers:
1. **Logs to `stdout`**: Structured JSON log entries are emitted to standard output for Google Cloud Logging ingestion.
2. **Environment Ingestion**: Configuration reads environment variables directly injected by Docker / GCP Secrets Manager.
3. **Stateless Core**: Zero file lockings or local state mutations.

---

## 📥 Setup & Usage Guide

1. **Clone environment variables**:
   ```bash
   cp .env.example .env
   ```

2. **Verify Foundation Core Setup**:
   ```bash
   python -c "import core; from core.config import settings; from core.logging import get_logger; logger = get_logger('test'); logger.info('Foundation loaded successfully!')"
   ```
