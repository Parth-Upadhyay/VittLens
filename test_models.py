"""
Standalone Model Tester & Connectivity Diagnostic Tool for Groq Fallback Models.

Usage:
    python test_models.py
"""

import json
import os
import sys
import time
from dotenv import load_dotenv
import groq

from app.config.settings import Settings
from app.utils import get_logger

logger = get_logger("finnai.test_models", "INFO")


def mask_key(key: str) -> str:
    """Safely mask API key for terminal display."""
    if not key:
        return "UNSET / MISSING"
    if len(key) <= 8:
        return "*******"
    return f"{key[:4]}...{key[-4:]}"


def test_groq_models() -> None:
    load_dotenv()
    settings = Settings()

    raw_api_key = settings.api_key or os.getenv("GROQ_API_KEY", "")
    masked = mask_key(raw_api_key)

    print("\n" + "=" * 75)
    print("           GROQ MODELS CONNECTIVITY & DIAGNOSTIC TEST             ")
    print("=" * 75)
    print(f"Active Groq API Key: {masked}")
    print(f"Primary Model:       {settings.model_name}")
    print(f"Timeout:             {settings.timeout}s")
    print("=" * 75 + "\n")

    if not raw_api_key or raw_api_key == "DUMMY_KEY_UNSET":
        print("\033[91m[ERROR] GROQ_API_KEY is not set or is empty in your .env file.\033[0m")
        print("Please place a valid Groq API key (starting with 'gsk_') in your .env file:\n")
        print("    GROQ_API_KEY=gsk_your_actual_key_here\n")
        sys.exit(1)

    client = groq.Groq(api_key=raw_api_key, timeout=10.0)

    candidate_models = settings.groq_fallback_models

    print(f"Testing {len(candidate_models)} candidate fallback models...\n")
    print("-" * 75)
    print(f"{'MODEL NAME':<32} | {'STATUS':<20} | {'LATENCY':<10} | {'DETAILS'}")
    print("-" * 75)

    online_count = 0
    test_messages = [{"role": "user", "content": "ping"}]

    for model_name in candidate_models:
        start_time = time.perf_counter()
        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=test_messages,
                max_tokens=5,
                timeout=10.0,
            )
            latency = (time.perf_counter() - start_time) * 1000.0
            online_count += 1
            print(f"{model_name:<32} | \033[92mONLINE / READY\033[0m      | {latency:6.1f} ms | OK")

        except groq.AuthenticationError as e:
            print(f"{model_name:<32} | \033[91mINVALID API KEY\033[0m     | --        | HTTP 401 Invalid Key")
        except groq.RateLimitError as e:
            print(f"{model_name:<32} | \033[93mRATE LIMITED\033[0m        | --        | HTTP 429 Limit Exceeded")
        except groq.NotFoundError as e:
            print(f"{model_name:<32} | \033[90mNOT FOUND\033[0m           | --        | Model ID Not Recognized")
        except Exception as e:
            err_short = str(e)[:30].replace("\n", " ")
            print(f"{model_name:<32} | \033[91mFAILED\033[0m              | --        | {err_short}")

    print("-" * 75)
    print(f"Summary: {online_count} / {len(candidate_models)} models online.")
    print("=" * 75 + "\n")

    if online_count == 0:
        print("\033[93m[NOTE] All model pings failed. If status is 'INVALID API KEY', verify that GROQ_API_KEY in .env is correct.\033[0m\n")


if __name__ == "__main__":
    test_groq_models()
