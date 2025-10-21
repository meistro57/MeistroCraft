# llm_provider.py
"""Utilities for managing configurable LLM providers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - handled gracefully at runtime
    OpenAI = None  # type: ignore


SUPPORTED_PROVIDERS = {"openai", "openrouter"}
DEFAULT_PROVIDER = "openai"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_PROVIDER_PLACEHOLDERS = {
    "openai": "<YOUR_OPENAI_API_KEY>",
    "openrouter": "<YOUR_OPENROUTER_API_KEY>",
}


@dataclass(frozen=True)
class ProviderConfig:
    """Structured configuration for an LLM provider."""

    provider: str
    api_key: Optional[str]
    model: Optional[str]
    base_url: Optional[str] = None
    default_headers: Optional[Dict[str, str]] = None


class ProviderConfigurationError(RuntimeError):
    """Raised when LLM provider configuration is invalid."""


def normalise_provider(value: Optional[str]) -> str:
    """Return a supported provider value, falling back to the default."""
    if not value:
        return DEFAULT_PROVIDER
    value = value.strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        return DEFAULT_PROVIDER
    return value


def get_provider_display_name(provider: str) -> str:
    """Convert provider identifier into a user-friendly display name."""
    mapping = {
        "openai": "OpenAI",
        "openrouter": "OpenRouter",
    }
    return mapping.get(provider, provider.title())


def get_provider_api_key(config: Dict[str, Any], provider: Optional[str] = None) -> Optional[str]:
    """Extract the API key for the configured provider."""
    provider = normalise_provider(provider or config.get("llm_provider"))
    key_lookup = {
        "openai": config.get("openai_api_key"),
        "openrouter": config.get("openrouter_api_key"),
    }
    return key_lookup.get(provider)


def get_provider_model(config: Dict[str, Any], provider: Optional[str] = None, default: str = "gpt-4-0613") -> str:
    """Return the preferred model for the configured provider."""
    provider = normalise_provider(provider or config.get("llm_provider"))
    model_lookup = {
        "openai": config.get("openai_model", default),
        "openrouter": config.get("openrouter_model", "openrouter/anthropic/claude-3.5-sonnet"),
    }
    return model_lookup.get(provider, default)


def is_provider_configured(config: Dict[str, Any], provider: Optional[str] = None) -> bool:
    """Determine whether the provider has a usable API key."""
    provider = normalise_provider(provider or config.get("llm_provider"))
    api_key = get_provider_api_key(config, provider)
    placeholder = _PROVIDER_PLACEHOLDERS.get(provider)
    if not api_key:
        return False
    if placeholder and api_key.strip() == placeholder:
        return False
    if provider == "openai" and api_key.strip().startswith("sk-your-"):
        return False
    if provider == "openrouter" and api_key.strip().startswith("or-your-"):
        return False
    return True


def build_provider_config(config: Dict[str, Any], provider: Optional[str] = None) -> ProviderConfig:
    """Construct a :class:`ProviderConfig` from raw configuration data."""
    provider = normalise_provider(provider or config.get("llm_provider"))
    api_key = get_provider_api_key(config, provider)
    model = get_provider_model(config, provider)

    if not api_key:
        raise ProviderConfigurationError(f"Missing API key for {get_provider_display_name(provider)}")

    placeholder = _PROVIDER_PLACEHOLDERS.get(provider)
    if placeholder and api_key == placeholder:
        raise ProviderConfigurationError(f"{get_provider_display_name(provider)} API key is using placeholder value")

    if OpenAI is None:
        raise ProviderConfigurationError("openai package is not installed. Install with: pip install openai")

    if provider == "openrouter":
        openrouter_settings = config.get("openrouter", {})
        base_url = openrouter_settings.get("base_url", OPENROUTER_BASE_URL)
        default_headers: Dict[str, str] = {}
        referer = openrouter_settings.get("referer")
        title = openrouter_settings.get("title")
        if referer:
            default_headers["HTTP-Referer"] = referer
        if title:
            default_headers["X-Title"] = title
        if not default_headers:
            default_headers = {
                "X-Title": "MeistroCraft",
            }
        return ProviderConfig(provider=provider, api_key=api_key, model=model, base_url=base_url, default_headers=default_headers)

    return ProviderConfig(provider=provider, api_key=api_key, model=model)


def create_chat_client(config: Dict[str, Any], provider: Optional[str] = None) -> Optional[Any]:
    """Create an OpenAI-compatible chat client for the configured provider."""
    try:
        provider_config = build_provider_config(config, provider)
    except ProviderConfigurationError:
        return None

    assert OpenAI is not None  # for type-checkers

    client_kwargs: Dict[str, Any] = {"api_key": provider_config.api_key}
    if provider_config.base_url:
        client_kwargs["base_url"] = provider_config.base_url
    if provider_config.default_headers:
        client_kwargs["default_headers"] = provider_config.default_headers

    try:
        return OpenAI(**client_kwargs)
    except Exception as exc:  # pragma: no cover - runtime failure guarded by tests
        raise ProviderConfigurationError(str(exc)) from exc


def get_provider_details(config: Dict[str, Any]) -> Tuple[str, str]:
    """Return the provider identifier and display name."""
    provider = normalise_provider(config.get("llm_provider"))
    return provider, get_provider_display_name(provider)


__all__ = [
    "ProviderConfig",
    "ProviderConfigurationError",
    "SUPPORTED_PROVIDERS",
    "DEFAULT_PROVIDER",
    "create_chat_client",
    "get_provider_api_key",
    "get_provider_details",
    "get_provider_display_name",
    "get_provider_model",
    "is_provider_configured",
    "normalise_provider",
]
