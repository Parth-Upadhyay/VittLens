"""
Groq Provider implementation wrapping Groq Python SDK.
Concrete implementation of abstract LLMProvider base class.
Includes automated multi-model rate-limit failover chain and real-time streaming support.
"""

import time
from typing import Generator, List, Optional
import groq

from app.config.settings import Settings
from app.schemas import GenerationMetadata, LLMResponse, TokenUsage
from app.services.base_provider import LLMProvider
from app.utils import (
    LLMAuthenticationError,
    LLMBaseError,
    LLMGenerationError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.utils import get_logger
from app.cache import SyncCacheService
from app.cache import llm_generation_key

logger = get_logger("finnai.groq_service")


class GroqProvider(LLMProvider):
    """
    Groq LLM Service implementation.
    Manages Groq Client lifecycle, rate-limit fallback execution, and real-time token streaming.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.api_key = self.settings.api_key

        if not self.api_key or self.api_key == "DUMMY_KEY_UNSET":
            logger.warning("GROQ_API_KEY is not configured or empty.")

        self.primary_model = self.settings.model_name
        self.fallback_models: List[str] = self.settings.groq_fallback_models
        self.timeout = self.settings.timeout

        self._client: Optional[groq.Groq] = None

    @property
    def client(self) -> groq.Groq:
        """Lazy initialization of Groq SDK Client."""
        if self._client is None:
            if not self.api_key or self.api_key == "DUMMY_KEY_UNSET":
                raise LLMAuthenticationError(
                    "GROQ_API_KEY environment variable is not set. Cannot initialize Groq client."
                )
            logger.info("Initializing Groq SDK client instance.")
            self._client = groq.Groq(api_key=self.api_key, timeout=self.timeout)
        return self._client

    def _get_model_candidate_chain(self, requested_model: Optional[str] = None) -> List[str]:
        """Construct priority-ordered list of candidate models for fallback retry."""
        candidates = []
        target = requested_model or self.primary_model
        candidates.append(target)
        for m in self.fallback_models:
            if m not in candidates:
                candidates.append(m)
        return candidates

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Execute Groq LLM completion with automatic model failover on rate limit (HTTP 429 / 413).
        Caches the response if temperature is deterministic (<= 0.3).
        """
        target_model = model or self.primary_model
        cache_key = None
        if temperature <= 0.3:
            cache_key = llm_generation_key(target_model, system_prompt, user_prompt, temperature)
            cached_data = SyncCacheService.get(cache_key)
            if cached_data:
                logger.info(f"LLM Cache HIT for prompt using model '{target_model}'.")
                return LLMResponse.model_validate(cached_data)

        candidate_models = self._get_model_candidate_chain(target_model)
        start_time = time.perf_counter()
        last_exception: Optional[Exception] = None

        for model_candidate in candidate_models:
            # Prepare current message prompt
            current_user_prompt = user_prompt
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_user_prompt},
            ]

            try:
                logger.info(f"Attempting Groq completion using model '{model_candidate}'...")
                kwargs = {
                    "model": model_candidate,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens

                response = self.client.chat.completions.create(**kwargs)
                latency = (time.perf_counter() - start_time) * 1000.0

                choice = response.choices[0]
                content = choice.message.content or ""
                finish_reason = choice.finish_reason or "stop"

                usage_obj = getattr(response, "usage", None)
                token_usage = TokenUsage(
                    prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) if usage_obj else 0,
                    completion_tokens=getattr(usage_obj, "completion_tokens", 0) if usage_obj else 0,
                    total_tokens=getattr(usage_obj, "total_tokens", 0) if usage_obj else 0,
                )

                metadata = GenerationMetadata(
                    model=model_candidate,
                    latency_ms=round(latency, 2),
                    finish_reason=finish_reason,
                    token_usage=token_usage,
                )

                logger.info(f"Groq completion succeeded with model '{model_candidate}' in {latency:.2f} ms.")
                llm_response = LLMResponse(
                    content=content,
                    metadata=metadata,
                    usage=token_usage,
                    raw_model_name=model_candidate,
                )

                if cache_key and temperature <= 0.3:
                    SyncCacheService.set(cache_key, llm_response, ttl=86400) # Cache for 24h
                    
                return llm_response

            except groq.AuthenticationError as e:
                logger.error(f"Groq authentication failed (Invalid API Key): {e}")
                raise LLMAuthenticationError(f"Invalid Groq API Key: {e}") from e

            except groq.BadRequestError as e:
                logger.warning(f"Groq Bad Request / Decommissioned Model error for '{model_candidate}': {e}. Skipping to next candidate...")
                last_exception = e
                continue

            except groq.RateLimitError as e:
                logger.warning(f"Groq Rate Limit hit for model '{model_candidate}': {e}. Failing over to next candidate...")
                last_exception = e

                # If rate limit includes TPM/413 error, try truncating prompt context and retrying current model candidate once
                err_str = str(e).lower()
                if "413" in err_str or "request_too_large" in err_str or "tpm" in err_str:
                    try:
                        truncated_prompt = current_user_prompt[:4000] + "\n\n[Context truncated for fallback model bounds]"
                        logger.info(f"Retrying Groq completion with model '{model_candidate}' using truncated prompt context...")
                        retry_messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": truncated_prompt},
                        ]
                        kwargs["messages"] = retry_messages
                        retry_resp = self.client.chat.completions.create(**kwargs)
                        latency = (time.perf_counter() - start_time) * 1000.0
                        choice = retry_resp.choices[0]
                        content = choice.message.content or ""
                        finish_reason = choice.finish_reason or "stop"
                        usage_obj = getattr(retry_resp, "usage", None)
                        token_usage = TokenUsage(
                            prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) if usage_obj else 0,
                            completion_tokens=getattr(usage_obj, "completion_tokens", 0) if usage_obj else 0,
                            total_tokens=getattr(usage_obj, "total_tokens", 0) if usage_obj else 0,
                        )
                        metadata = GenerationMetadata(
                            model=model_candidate,
                            latency_ms=round(latency, 2),
                            finish_reason=finish_reason,
                            token_usage=token_usage,
                        )
                        logger.info(f"Groq completion succeeded with model '{model_candidate}' after prompt truncation.")
                        return LLMResponse(
                            content=content,
                            metadata=metadata,
                            usage=token_usage,
                            raw_model_name=model_candidate,
                        )
                    except Exception as retry_err:
                        logger.warning(f"Retry after truncation failed for model '{model_candidate}': {retry_err}")
                continue

            except groq.APITimeoutError as e:
                logger.warning(f"Groq API timeout for model '{model_candidate}': {e}.")
                last_exception = e
                continue

            except Exception as e:
                logger.error(f"Groq API call error with model '{model_candidate}': {e}")
                last_exception = e
                continue

        raise LLMRateLimitError(
            f"All Groq fallback candidate models failed or rate-limited. Last error: {last_exception}"
        ) from last_exception

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Stream real-time completion tokens from Groq as a generator.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        candidate_models = self._get_model_candidate_chain(model)

        for model_candidate in candidate_models:
            try:
                logger.info(f"Starting Groq token stream with model '{model_candidate}'...")
                kwargs = {
                    "model": model_candidate,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                }
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens

                stream_response = self.client.chat.completions.create(**kwargs)

                for chunk in stream_response:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

                return  # Stream completed cleanly

            except groq.RateLimitError as e:
                logger.warning(f"Groq stream rate limit hit for model '{model_candidate}'. Failing over...")
                continue
            except Exception as e:
                logger.error(f"Groq streaming error with model '{model_candidate}': {e}")
                continue

    def test_connection(self) -> bool:
        """Test Groq connectivity using candidate models."""
        try:
            res = self.generate(
                system_prompt="You are a health check assistant.",
                user_prompt="ping",
                max_tokens=5,
            )
            return bool(res.content)
        except Exception as e:
            logger.error(f"Groq connection test failed: {e}")
            return False


class GroqService(GroqProvider):
    """
    Backwards-compatible service alias for GroqProvider.
    """
    pass
