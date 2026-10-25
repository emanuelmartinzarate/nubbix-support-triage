"""Orquestador del triage: arma el prompt, llama al proveedor, valida con reintento y registra métricas."""

import secrets
from dataclasses import dataclass, field
from typing import Literal

from triage.cache import ResponseCache, cache_key
from triage.config import ConfigError, Settings
from triage.guardrails import GuardResult
from triage.guardrails.input_guard import check_input
from triage.guardrails.moderation import moderate
from triage.guardrails.output_guard import check_output
from triage.metrics import append_metrics, new_request_id, utc_now_iso
from triage.pricing import PricingError, estimate_cost
from triage.prompts import build_messages, load_prompt, prompt_fingerprint
from triage.providers import get_provider, model_for
from triage.providers.base import LLMParams, LLMProvider, Message, ProviderError, RefusalError
from triage.providers.retry import call_with_backoff
from triage.schema import TRIAGE_JSON_SCHEMA, ParseError, TriageResponse, blocked_response, parse_response

Source = Literal["cli", "api", "eval"]

CORRECTION_TEMPLATE = (
    "Tu respuesta no cumple el contrato JSON: {error}. Respondé solo con el JSON corregido."
)


@dataclass
class TriageOutcome:
    response: TriageResponse
    status: Literal["ok", "blocked"]
    record: dict
    canary: str


class TriageError(Exception):
    """No se pudo obtener una respuesta válida (reintentos agotados o error del proveedor)."""

    def __init__(self, message: str, record: dict):
        super().__init__(message)
        self.record = record


@dataclass
class _Usage:
    """Acumula tokens, costo y latencia de todas las llamadas de un request."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    moderation_cost_usd: float = 0.0
    latency_s: float = 0.0
    attempts: int = 0
    extra: dict = field(default_factory=dict)

    def add(self, input_tokens: int, output_tokens: int, latency_s: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += estimate_cost(self.model, input_tokens, output_tokens)
        self.latency_s += latency_s


def _record(
    *, request_id: str, source: Source, provider: str, prompt_version: str, usage: _Usage,
    status: str, error: str | None = None, cache_hit: bool = False, guardrail: dict | None = None,
) -> dict:
    return {
        "timestamp": utc_now_iso(),
        "request_id": request_id,
        "source": source,
        "provider": provider,
        "model": usage.model,
        "prompt_version": prompt_version,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
        "latency_s": round(usage.latency_s, 4),
        "cost_usd": round(usage.cost_usd, 8),
        "moderation_cost_usd": round(usage.moderation_cost_usd, 8),
        "attempts": usage.attempts,
        "cache_hit": cache_hit,
        "guardrail": guardrail,
        "status": status,
        "error": error,
    }


def _call_until_valid(
    provider: LLMProvider, system: str, messages: list[Message], params: LLMParams,
    settings: Settings, usage: _Usage,
) -> TriageResponse:
    conversation = list(messages)
    last_error = ""
    for _ in range(1 + settings.parse_max_retries):
        usage.attempts += 1
        result = call_with_backoff(
            lambda: provider.complete(system, conversation, params), settings.api_max_retries
        )
        usage.add(result.input_tokens, result.output_tokens, result.latency_s)
        try:
            return parse_response(result.text)
        except ParseError as e:
            last_error = str(e)
            conversation += [
                {"role": "assistant", "content": result.text},
                {"role": "user", "content": CORRECTION_TEMPLATE.format(error=last_error)},
            ]
    raise ParseError(f"reintentos agotados: {last_error}")


def _check_input_layers(
    query: str, provider: LLMProvider, params: LLMParams, settings: Settings, usage: _Usage
) -> GuardResult:
    """Capa 1 (heurística, gratis) y, si está habilitada, capa 2 (moderación LLM)."""
    verdict = check_input(query, settings.max_query_chars)
    if not verdict.allowed or not settings.moderation_enabled:
        return verdict
    try:
        verdict, result = call_with_backoff(
            lambda: moderate(query, provider, params), settings.api_max_retries
        )
    except ProviderError:
        # Fail-open: si la moderación no responde, siguen las capas de prompt y de salida.
        return GuardResult(True, "moderation_unavailable", "moderation")
    if result is not None:
        before = usage.cost_usd
        usage.add(result.input_tokens, result.output_tokens, result.latency_s)
        usage.moderation_cost_usd += usage.cost_usd - before
    return verdict


def triage(
    query: str,
    settings: Settings,
    *,
    provider: LLMProvider | None = None,
    provider_name: str | None = None,
    prompt_version: str | None = None,
    source: Source = "cli",
    use_cache: bool | None = None,
    guardrails: bool | None = None,
) -> TriageOutcome:
    if not query or not query.strip():
        raise ValueError("consulta vacía")

    name = provider_name or settings.llm_provider
    model = model_for(name, settings)
    try:
        estimate_cost(model, 0, 0)
    except PricingError as e:
        raise ConfigError(str(e)) from e
    provider = provider or get_provider(name, settings)
    version = prompt_version or settings.prompt_version
    prompt = load_prompt(version)

    request_id = new_request_id()
    canary = secrets.token_hex(8)
    usage = _Usage(model=model)
    params = LLMParams(
        model=model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        timeout_s=settings.request_timeout_s,
        json_schema=TRIAGE_JSON_SCHEMA,
    )
    log = dict(request_id=request_id, source=source, provider=name, prompt_version=version)
    guards_on = settings.guardrails_enabled if guardrails is None else guardrails

    degraded_guard = None
    if guards_on:
        verdict = _check_input_layers(query, provider, params, settings, usage)
        if verdict.allowed and verdict.reason:
            # Moderación degradada (no respondió o no parseó): no bloquea, pero queda registrada.
            degraded_guard = {"layer": verdict.layer, "reason": verdict.reason}
        if not verdict.allowed:
            guardrail = {"layer": verdict.layer, "reason": verdict.reason}
            record = _record(**log, usage=usage, status="blocked", guardrail=guardrail)
            append_metrics(record, settings.metrics_path)
            return TriageOutcome(
                response=blocked_response(verdict.reason), status="blocked", record=record, canary=canary
            )

    system, messages = build_messages(prompt, query, canary)
    cache = ResponseCache(settings.cache_dir, settings.cache_enabled, settings.cache_ttl_s)
    key = cache_key(
        name, model, f"{version}:{prompt_fingerprint(prompt)}", settings.temperature, settings.max_tokens, query
    )
    read_cache = settings.cache_enabled if use_cache is None else use_cache
    response = cache.get(key) if read_cache else None
    cache_hit = response is not None

    if not cache_hit:
        try:
            response = _call_until_valid(provider, system, messages, params, settings, usage)
        except RefusalError:
            # El rechazo del proveedor es un guardrail más: el consumidor recibe el contrato igual.
            guardrail = {"layer": "provider_safety", "reason": "refusal"}
            record = _record(**log, usage=usage, status="blocked", guardrail=guardrail)
            append_metrics(record, settings.metrics_path)
            return TriageOutcome(
                response=blocked_response("refusal"), status="blocked", record=record, canary=canary
            )
        except (ParseError, ProviderError) as e:
            record = _record(**log, usage=usage, status="error", error=str(e))
            append_metrics(record, settings.metrics_path)
            raise TriageError(str(e), record) from e

    # La salida se valida siempre, también la cacheada: pudo guardarse con los guardrails apagados.
    if guards_on:
        verdict = check_output(response, system, canary)
        if not verdict.allowed:
            guardrail = {"layer": verdict.layer, "reason": verdict.reason}
            record = _record(**log, usage=usage, status="blocked", cache_hit=cache_hit, guardrail=guardrail)
            append_metrics(record, settings.metrics_path)
            return TriageOutcome(
                response=blocked_response(verdict.reason), status="blocked", record=record, canary=canary
            )

    if not cache_hit:
        cache.set(key, response)
    record = _record(**log, usage=usage, status="ok", cache_hit=cache_hit, guardrail=degraded_guard)
    append_metrics(record, settings.metrics_path)
    return TriageOutcome(response=response, status="ok", record=record, canary=canary)
