"""Unit tests for the LLM provider abstraction.

All external calls (Groq API, Ollama HTTP) are mocked.

Coverage:
- get_llm_provider()
  — returns GroqProvider when LLM_PROVIDER='groq'
  — returns OllamaProvider when LLM_PROVIDER='ollama'
  — raises ValueError for unknown provider
  — is a singleton (same object returned on repeated calls)
  — reset_llm_provider() clears the singleton
- GroqProvider.acomplete()
  — happy path: returns text from LlamaIndex Groq response
  — maps system/user/assistant roles correctly
  — raises RuntimeError on Groq failure
- OllamaProvider.acomplete()
  — happy path: returns text from Ollama /api/chat response
  — raises RuntimeError on HTTP error
  — raises RuntimeError on connection error
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_groq_response(text: str) -> MagicMock:
    """Simulate a LlamaIndex ChatResponse object."""
    resp = MagicMock()
    resp.message.content = text
    return resp


# ── get_llm_provider factory ──────────────────────────────────────────────


def test_get_llm_provider_returns_groq() -> None:
    """Returns a GroqProvider when LLM_PROVIDER='groq'."""
    from app.ai.llm_provider import GroqProvider, get_llm_provider, reset_llm_provider

    reset_llm_provider()
    with patch("app.ai.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "groq"
        mock_settings.GROQ_API_KEY = "test-key"
        provider = get_llm_provider()

    assert isinstance(provider, GroqProvider)
    reset_llm_provider()


def test_get_llm_provider_returns_ollama() -> None:
    """Returns an OllamaProvider when LLM_PROVIDER='ollama'."""
    from app.ai.llm_provider import OllamaProvider, get_llm_provider, reset_llm_provider

    reset_llm_provider()
    with patch("app.ai.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "ollama"
        mock_settings.GROQ_API_KEY = ""
        provider = get_llm_provider()

    assert isinstance(provider, OllamaProvider)
    reset_llm_provider()


def test_get_llm_provider_raises_for_unknown() -> None:
    """Raises ValueError for an unknown LLM_PROVIDER value."""
    from app.ai.llm_provider import get_llm_provider, reset_llm_provider

    reset_llm_provider()
    with patch("app.ai.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "openai"
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm_provider()

    reset_llm_provider()


def test_get_llm_provider_is_singleton() -> None:
    """Returns the same provider instance on repeated calls."""
    from app.ai.llm_provider import get_llm_provider, reset_llm_provider

    reset_llm_provider()
    with patch("app.ai.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "groq"
        mock_settings.GROQ_API_KEY = "test-key"
        p1 = get_llm_provider()
        p2 = get_llm_provider()

    assert p1 is p2
    reset_llm_provider()


def test_reset_llm_provider_clears_singleton() -> None:
    """reset_llm_provider() forces a fresh instance on next call."""
    from app.ai.llm_provider import get_llm_provider, reset_llm_provider

    reset_llm_provider()
    with patch("app.ai.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "groq"
        mock_settings.GROQ_API_KEY = "key1"
        p1 = get_llm_provider()

    reset_llm_provider()

    with patch("app.ai.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "groq"
        mock_settings.GROQ_API_KEY = "key2"
        p2 = get_llm_provider()

    assert p1 is not p2
    reset_llm_provider()


# ── GroqProvider ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_groq_provider_acomplete_happy_path() -> None:
    """Returns text from the Groq LLM response."""
    from app.ai.llm_provider import GroqProvider

    mock_response = _make_groq_response("This is the AI response.")
    mock_achat = AsyncMock(return_value=mock_response)

    with (
        patch("app.ai.llm_provider.settings") as mock_settings,
        patch("app.ai.llm_provider.Groq") as mock_groq_cls,
    ):
        mock_settings.GROQ_API_KEY = "fake-key"
        mock_groq_cls.return_value.achat = mock_achat
        provider = GroqProvider()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Summarize my week."},
        ]
        result = await provider.acomplete(messages)

    assert result == "This is the AI response."
    mock_achat.assert_called_once()


@pytest.mark.asyncio
async def test_groq_provider_maps_roles() -> None:
    """Maps system/user/assistant roles to LlamaIndex MessageRole."""
    from llama_index.core.llms import MessageRole

    from app.ai.llm_provider import GroqProvider

    mock_response = _make_groq_response("ok")
    mock_achat = AsyncMock(return_value=mock_response)

    with (
        patch("app.ai.llm_provider.settings") as mock_settings,
        patch("app.ai.llm_provider.Groq") as mock_groq_cls,
    ):
        mock_settings.GROQ_API_KEY = "fake-key"
        mock_groq_cls.return_value.achat = mock_achat
        provider = GroqProvider()

        await provider.acomplete(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "usr"},
                {"role": "assistant", "content": "asst"},
            ]
        )

    call_args = mock_achat.call_args[0][0]  # positional list of ChatMessage
    assert call_args[0].role == MessageRole.SYSTEM
    assert call_args[1].role == MessageRole.USER
    assert call_args[2].role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_groq_provider_raises_runtime_error_on_failure() -> None:
    """Raises RuntimeError when the Groq call fails."""
    from app.ai.llm_provider import GroqProvider

    mock_achat = AsyncMock(side_effect=Exception("rate limit exceeded"))

    with (
        patch("app.ai.llm_provider.settings") as mock_settings,
        patch("app.ai.llm_provider.Groq") as mock_groq_cls,
    ):
        mock_settings.GROQ_API_KEY = "fake-key"
        mock_groq_cls.return_value.achat = mock_achat
        provider = GroqProvider()

        with pytest.raises(RuntimeError, match="Groq inference failed"):
            await provider.acomplete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_groq_provider_model_name() -> None:
    """model_name returns groq/<model>."""
    from app.ai.llm_provider import GroqProvider

    with (
        patch("app.ai.llm_provider.settings") as mock_settings,
        patch("app.ai.llm_provider.Groq"),
    ):
        mock_settings.GROQ_API_KEY = ""
        provider = GroqProvider()

    assert provider.model_name.startswith("groq/")


# ── OllamaProvider ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ollama_provider_acomplete_happy_path() -> None:
    """Returns text from Ollama /api/chat response."""
    import httpx

    from app.ai.llm_provider import OllamaProvider

    provider = OllamaProvider()

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"content": "Ollama says hello."}}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ai.llm_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.acomplete([{"role": "user", "content": "Hello Ollama!"}])

    assert result == "Ollama says hello."
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"]["stream"] is False


@pytest.mark.asyncio
async def test_ollama_provider_raises_on_http_error() -> None:
    """Raises RuntimeError on HTTP error status."""
    import httpx

    from app.ai.llm_provider import OllamaProvider

    provider = OllamaProvider()

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    http_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=mock_resp)

    with patch("app.ai.llm_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=http_error)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="Ollama HTTP"):
            await provider.acomplete([{"role": "user", "content": "hello"}])


@pytest.mark.asyncio
async def test_ollama_provider_raises_on_connection_error() -> None:
    """Raises RuntimeError on network/connection failure."""
    from app.ai.llm_provider import OllamaProvider

    provider = OllamaProvider()

    with patch("app.ai.llm_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="Ollama inference failed"):
            await provider.acomplete([{"role": "user", "content": "hello"}])


@pytest.mark.asyncio
async def test_ollama_provider_model_name() -> None:
    """model_name returns ollama/<model>."""
    from app.ai.llm_provider import OllamaProvider

    provider = OllamaProvider()
    assert provider.model_name.startswith("ollama/")
