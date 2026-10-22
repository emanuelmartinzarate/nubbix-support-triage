"""Configuración del servicio, cargada desde .env y variables de entorno."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuración inválida o incompleta (variable faltante o mal formada)."""


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    anthropic_api_key: str | None
    anthropic_model: str
    gemini_api_key: str | None
    gemini_model: str
    prompt_version: str
    temperature: float
    max_tokens: int
    parse_max_retries: int
    api_max_retries: int
    request_timeout_s: float
    metrics_path: Path
    cache_dir: Path
    cache_enabled: bool
    guardrails_enabled: bool
    moderation_enabled: bool
    max_query_chars: int
    eval_max_cost_usd: float
    eval_concurrency: int


_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off"}


def _str(name: str, default: str | None) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or default


def _bool(name: str, default: bool) -> bool:
    raw = _str(name, None)
    if raw is None:
        return default
    if raw.lower() in _TRUE:
        return True
    if raw.lower() in _FALSE:
        return False
    raise ConfigError(f"{name} debe ser true/false, se recibió {raw!r}")


def _num(name: str, default, cast):
    raw = _str(name, None)
    if raw is None:
        return default
    try:
        return cast(raw)
    except ValueError as e:
        raise ConfigError(f"{name} debe ser numérico, se recibió {raw!r}") from e


def load_settings(env_file: str | None = ".env") -> Settings:
    if env_file:
        load_dotenv(env_file, override=False)
    return Settings(
        llm_provider=_str("LLM_PROVIDER", "anthropic").lower(),
        anthropic_api_key=_str("ANTHROPIC_API_KEY", None),
        anthropic_model=_str("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        gemini_api_key=_str("GEMINI_API_KEY", None),
        gemini_model=_str("GEMINI_MODEL", "gemini-3.8-flash"),
        prompt_version=_str("PROMPT_VERSION", "v1"),
        temperature=_num("TEMPERATURE", 0.0, float),
        max_tokens=_num("MAX_TOKENS", 600, int),
        parse_max_retries=_num("PARSE_MAX_RETRIES", 2, int),
        api_max_retries=_num("API_MAX_RETRIES", 3, int),
        request_timeout_s=_num("REQUEST_TIMEOUT_S", 30.0, float),
        metrics_path=Path(_str("METRICS_PATH", "data/metrics.jsonl")),
        cache_dir=Path(_str("CACHE_DIR", "data/cache")),
        cache_enabled=_bool("CACHE_ENABLED", True),
        guardrails_enabled=_bool("GUARDRAILS_ENABLED", True),
        moderation_enabled=_bool("MODERATION_ENABLED", False),
        max_query_chars=_num("MAX_QUERY_CHARS", 4000, int),
        eval_max_cost_usd=_num("EVAL_MAX_COST_USD", 2.0, float),
        eval_concurrency=_num("EVAL_CONCURRENCY", 1, int),
    )
