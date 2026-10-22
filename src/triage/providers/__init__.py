"""Registro de proveedores: elige el adaptador por nombre y valida sus credenciales."""

from triage.config import ConfigError, Settings
from triage.providers.base import LLMProvider

PROVIDERS = ("anthropic",)


def model_for(name: str, settings: Settings) -> str:
    if name == "anthropic":
        return settings.anthropic_model
    raise ConfigError(f"proveedor desconocido: {name!r} (opciones: {', '.join(PROVIDERS)})")


def get_provider(name: str, settings: Settings) -> LLMProvider:
    if name == "anthropic":
        if not settings.anthropic_api_key:
            raise ConfigError("Falta ANTHROPIC_API_KEY (cargala en .env o en el entorno)")
        from triage.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key)
    raise ConfigError(f"proveedor desconocido: {name!r} (opciones: {', '.join(PROVIDERS)})")
