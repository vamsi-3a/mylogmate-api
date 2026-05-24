"""LLM provider abstraction — Groq and Ollama adapters.

Rules (ai-module.md):
  - NEVER call Groq or Ollama directly outside this file.
  - All callers go through get_llm_provider() → BaseLLMProvider.acomplete().
  - Swapping providers = change LLM_PROVIDER in settings. Zero code changes.

Providers:
  groq   — Groq Cloud API via llama-index-llms-groq (Llama 3.1 8B Instant)
  ollama — Self-hosted Ollama via direct HTTP (no llama-index-llms-ollama required)

Usage:
    from app.ai.llm_provider import get_llm_provider

    llm = get_llm_provider()
    response = await llm.acomplete(messages=[{"role": "user", "content": "..."}])
"""

from __future__ import annotations

import abc
from typing import Any

import httpx
import structlog
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.groq import Groq

from app.core.config import settings

logger = structlog.get_logger()

# ── Type alias ────────────────────────────────────────────────────────────

# A message dict: {"role": "system"|"user"|"assistant", "content": str}
MessageDict = dict[str, str]

_ROLE_MAP: dict[str, MessageRole] = {
    "system": MessageRole.SYSTEM,
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
}

# ── Base class ────────────────────────────────────────────────────────────


class BaseLLMProvider(abc.ABC):
    """Abstract LLM provider interface.

    All providers must implement acomplete(), which accepts a list of message
    dicts and returns the assistant's reply as a string.
    """

    @abc.abstractmethod
    async def acomplete(self, messages: list[MessageDict]) -> str:
        """Send messages to the LLM and return the text reply.

        Args:
            messages: Ordered list of {"role": ..., "content": ...} dicts.
                      Supported roles: "system", "user", "assistant".

        Returns:
            The assistant's reply as a plain string.

        Raises:
            RuntimeError: If the provider call fails after retries.
        """

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Human-readable identifier of the model in use."""


# ── Groq provider ─────────────────────────────────────────────────────────


class GroqProvider(BaseLLMProvider):
    """Groq Cloud API via llama-index-llms-groq.

    Default model: llama-3.1-8b-instant (free tier, 30 RPM / 14k TPM).
    Set GROQ_API_KEY in settings to use.
    """

    _GROQ_MODEL = "llama-3.1-8b-instant"

    def __init__(self) -> None:
        self._llm = Groq(
            model=self._GROQ_MODEL,
            api_key=settings.GROQ_API_KEY or None,
            max_tokens=2048,
            temperature=0.2,
        )

    @property
    def model_name(self) -> str:
        return f"groq/{self._GROQ_MODEL}"

    async def acomplete(self, messages: list[MessageDict]) -> str:
        """Call Groq via LlamaIndex async chat interface."""
        chat_messages = [
            ChatMessage(
                role=_ROLE_MAP.get(m["role"], MessageRole.USER),
                content=m["content"],
            )
            for m in messages
        ]

        logger.debug("llm_groq_request", model=self._GROQ_MODEL, n_messages=len(chat_messages))

        try:
            response = await self._llm.achat(chat_messages)
            text: str = response.message.content or ""
            logger.debug("llm_groq_response", chars=len(text))
            return text
        except Exception as exc:
            logger.error("llm_groq_error", error=str(exc))
            raise RuntimeError(f"Groq inference failed: {exc}") from exc


# ── Ollama provider ───────────────────────────────────────────────────────


class OllamaProvider(BaseLLMProvider):
    """Self-hosted Ollama via direct HTTP API.

    Reads OLLAMA_BASE_URL (default: http://localhost:11434) and
    OLLAMA_MODEL (default: llama3.1:8b) from settings if present.
    Falls back to built-in defaults when not configured.

    Requires: Ollama running locally or on a reachable host.
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"
    _DEFAULT_MODEL = "llama3.1:8b"

    def __init__(self) -> None:
        base_url = getattr(settings, "OLLAMA_BASE_URL", self._DEFAULT_BASE_URL)
        self._base_url = base_url.rstrip("/")
        self._model = getattr(settings, "OLLAMA_MODEL", self._DEFAULT_MODEL)

    @property
    def model_name(self) -> str:
        return f"ollama/{self._model}"

    async def acomplete(self, messages: list[MessageDict]) -> str:
        """Call Ollama /api/chat endpoint (non-streaming)."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 2048},
        }

        logger.debug("llm_ollama_request", model=self._model, n_messages=len(messages))

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                text: str = data["message"]["content"]
                logger.debug("llm_ollama_response", chars=len(text))
                return text
        except httpx.HTTPStatusError as exc:
            logger.error("llm_ollama_http_error", status=exc.response.status_code, error=str(exc))
            raise RuntimeError(f"Ollama HTTP {exc.response.status_code}: {exc}") from exc
        except Exception as exc:
            logger.error("llm_ollama_error", error=str(exc))
            raise RuntimeError(f"Ollama inference failed: {exc}") from exc


# ── Factory ───────────────────────────────────────────────────────────────

_provider: BaseLLMProvider | None = None


def get_llm_provider() -> BaseLLMProvider:
    """Return the configured LLM provider (singleton per process).

    Provider selection is driven by settings.LLM_PROVIDER:
      "groq"   → GroqProvider  (default)
      "ollama" → OllamaProvider

    Raises:
        ValueError: If LLM_PROVIDER is not a known value.
    """
    global _provider  # noqa: PLW0603

    if _provider is not None:
        return _provider

    provider_name = settings.LLM_PROVIDER.lower()

    if provider_name == "groq":
        _provider = GroqProvider()
    elif provider_name == "ollama":
        _provider = OllamaProvider()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
            "Supported values: 'groq', 'ollama'."
        )

    logger.info("llm_provider_initialized", provider=provider_name, model=_provider.model_name)
    return _provider


def reset_llm_provider() -> None:
    """Reset the singleton — used in tests to swap providers between test cases."""
    global _provider  # noqa: PLW0603
    _provider = None
