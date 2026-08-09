"""
CLI test & interactive query script for FinnAI Groq LLM Layer.

Usage:
    python test_llm.py                      -> Starts interactive query REPL mode
    python test_llm.py "Your query here"    -> Runs single inline query
    python test_llm.py --test               -> Runs automated system benchmark test
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from app.config.settings import Settings
from app.prompts import PromptBuilder
from app.prompts import FINANCIAL_ANALYST_SYSTEM_PROMPT
from app.schemas import LLMResponse, Message
from app.services import LLMProvider, GroqProvider, get_llm_provider
from app.utils import LLMAuthenticationError, LLMBaseError
from app.utils import get_logger


def print_response(response: LLMResponse) -> None:
    """Pretty prints structured LLMResponse output, metrics, and telemetry."""
    print("\n" + "=" * 65)
    print("                      FINNAI LLM RESPONSE                      ")
    print("=" * 65)
    print(f"\n{response.content}\n")
    print("-" * 65)
    print("Telemetry & Metrics:")
    print(f"  • Model:          {response.raw_model_name}")
    print(f"  • Latency:        {response.metadata.latency_ms:.2f} ms")
    print(
        f"  • Tokens Used:    {response.usage.total_tokens} "
        f"(Prompt: {response.usage.prompt_tokens} | Completion: {response.usage.completion_tokens})"
    )
    print(f"  • Finish Reason:  {response.metadata.finish_reason}")
    print("=" * 65 + "\n")


def execute_single_query(
    service: LLMProvider,
    user_query: str,
    history: list[Message] | None = None,
    system_prompt: str = FINANCIAL_ANALYST_SYSTEM_PROMPT,
) -> LLMResponse:
    """Helper to process a single user query through PromptBuilder and LLMProvider."""
    prompt_builder = PromptBuilder().with_question(user_query)
    formatted_prompt = prompt_builder.build()

    response = service.generate(
        system_prompt=system_prompt,
        user_prompt=formatted_prompt,
        history=history,
        temperature=0.3,
    )
    return response


def run_benchmark_test(service: LLMProvider, logger) -> None:
    """Runs the canned automated benchmark test."""
    logger.info("Executing benchmark test suite...")
    prompt_builder = (
        PromptBuilder()
        .with_question(
            "Analyze the impact of a 50 bps interest rate cut by the Federal Reserve on tech equity valuations and capital allocation."
        )
        .with_market_data({
            "index_sp500": 5400.25,
            "10y_treasury_yield": "3.85%",
            "fed_funds_rate": "5.25%",
        })
        .with_ratios({
            "tech_sector_pe_avg": 28.5,
            "debt_to_equity_median": 0.45,
        })
        .with_instructions(
            "Provide a concise bulleted summary with: 1) Equity Valuation Impact, 2) Cost of Debt Impact, 3) Key Sector Risks."
        )
    )

    response = service.generate(
        system_prompt=FINANCIAL_ANALYST_SYSTEM_PROMPT,
        user_prompt=prompt_builder.build(),
        history=[
            Message(role="user", content="Hello, I am reviewing our Q3 macro portfolio strategy."),
            Message(role="assistant", content="Understood. I am ready to assist with macro and equity analysis."),
        ],
        temperature=0.3,
    )
    print_response(response)
    logger.info("Benchmark test completed successfully.")


def run_interactive_repl(service: LLMProvider, logger) -> None:
    """Runs an interactive multi-turn conversation shell in the terminal."""
    print("\n" + "=" * 65)
    print("   FinnAI Financial Intelligence Platform - Interactive LLM Shell")
    print(f"   Provider: {service.provider_name.upper()}  | Model: {service.model_name}")
    print("=" * 65)
    print(" Commands:")
    print("   • Type your question/prompt and press Enter")
    print("   • 'clear' : Reset conversation history")
    print("   • 'exit' or 'quit' : Stop the session\n")

    history: list[Message] = []

    while True:
        try:
            user_input = input("\nFinnAI > ").strip()
            if not user_input:
                continue

            lowered = user_input.lower()
            if lowered in ("exit", "quit", "q"):
                print("Exiting interactive query shell. Goodbye!")
                break
            elif lowered == "clear":
                history.clear()
                print("Conversation history cleared.")
                continue
            elif lowered == "test":
                run_benchmark_test(service, logger)
                continue

            # Execute interactive query
            print(f"\nGenerating response from {service.provider_name.title()}...")
            response = execute_single_query(service, user_input, history=history)
            print_response(response)

            # Update conversation history for multi-turn context
            history.append(Message(role="user", content=user_input))
            history.append(Message(role="assistant", content=response.content))

        except KeyboardInterrupt:
            print("\nSession interrupted. Exiting...")
            break
        except LLMAuthenticationError as e:
            logger.error(f"Authentication Error: {e.message}")
            print("\nPlease verify that GROQ_API_KEY in your .env file is correct.")
            break
        except LLMBaseError as e:
            logger.error(f"LLM Provider Error: {e.message} (Status: {e.status_code})")


def main() -> None:
    load_dotenv()
    logger = get_logger("finnai.cli", "INFO")

    settings = Settings()
    if not settings.api_key:
        logger.warning("GROQ_API_KEY is not set in environment or .env file.")

    # Use Provider Factory to instantiate the abstract LLMProvider interface
    service: LLMProvider = get_llm_provider("groq", settings=settings)

    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="FinnAI LLM CLI & Interactive Query Tool")
    parser.add_argument("query", nargs="?", help="Direct query string to process immediately")
    parser.add_argument("--test", action="store_true", help="Run automated benchmark test")
    parser.add_argument("-i", "--interactive", action="store_true", help="Force interactive mode")

    args = parser.parse_args()

    try:
        if args.test:
            run_benchmark_test(service, logger)
        elif args.query:
            logger.info(f"Processing query: '{args.query}' via Provider [{service.provider_name.upper()}]")
            response = execute_single_query(service, args.query)
            print_response(response)
        else:
            # Default to interactive REPL mode when launched without direct query arguments
            run_interactive_repl(service, logger)

    except LLMAuthenticationError as e:
        logger.error(f"Authentication Error: {e.message}")
        print("\n[NOTE] Please ensure GROQ_API_KEY is set in your .env file.")
        sys.exit(1)
    except LLMBaseError as e:
        logger.error(f"LLM Provider Error: {e.message} (Status: {e.status_code})")
        sys.exit(1)
        logger.error(f"Groq Layer Error: {e.message} (Status: {e.status_code})")
        sys.exit(1)


if __name__ == "__main__":
    main()
