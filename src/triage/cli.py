"""CLI: recibe una consulta y escribe por stdout solo el JSON del contrato."""

import argparse
import json
import sys

from triage.config import ConfigError, load_settings
from triage.prompts import PromptNotFoundError
from triage.providers import get_provider
from triage.service import TriageError, triage

EXIT_OK, EXIT_TRIAGE_ERROR, EXIT_USAGE = 0, 1, 2


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="triage", description="Clasifica un ticket de soporte de Nubbix y devuelve JSON validado."
    )
    parser.add_argument("query", nargs="?", help="consulta del cliente (si se omite, se lee de stdin)")
    parser.add_argument("--provider", help="anthropic | gemini (default: LLM_PROVIDER)")
    parser.add_argument("--prompt", help="versión de prompt, p. ej. v1 (default: PROMPT_VERSION)")
    parser.add_argument("--no-cache", action="store_true", help="ignora la caché de respuestas")
    parser.add_argument("--verbose", action="store_true", help="imprime un resumen legible de la métrica del request en stderr")
    return parser.parse_args(argv)


def _read_query(args: argparse.Namespace) -> str:
    if args.query is not None:
        return args.query
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _usd(value: float) -> str:
    """Costo en decimales fijos: json.dumps escribe 7.31e-05, ilegible para una persona."""
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


def format_metric(record: dict) -> str:
    """Resumen legible del record para --verbose; la línea JSON completa queda en metrics.jsonl."""
    cost = f"costo USD {_usd(record['cost_usd'])}"
    moderation = record.get("moderation_cost_usd", 0.0)
    if moderation:
        triage_part = "USD 0, desde caché" if record["cache_hit"] else f"USD {_usd(record['cost_usd'] - moderation)}"
        cost += f" (moderación USD {_usd(moderation)} + triage {triage_part})"
    guardrail = record["guardrail"]
    guard = f"{guardrail['layer']}/{guardrail['reason']}" if guardrail else "—"
    lines = [
        f"[métrica] {record['provider']}/{record['model']} · prompt {record['prompt_version']}"
        f" · status {record['status']} · caché: {'hit' if record['cache_hit'] else 'miss'}",
        f"          tokens {record['input_tokens']} in / {record['output_tokens']} out"
        f" · latencia {record['latency_s']:.2f} s · {cost} · intentos {record['attempts']}",
        f"          guardrail: {guard} · request_id {record['request_id']}",
    ]
    if record.get("error"):
        lines.append(f"          error: {record['error']}")
    return "\n".join(lines)


def _fail(message: str, code: int) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    query = _read_query(args)
    if not query.strip():
        return _fail("consulta vacía", EXIT_USAGE)

    try:
        settings = load_settings()
        name = args.provider or settings.llm_provider
        provider = get_provider(name, settings)
        outcome = triage(
            query,
            settings,
            provider=provider,
            provider_name=name,
            prompt_version=args.prompt,
            source="cli",
            use_cache=False if args.no_cache else None,
        )
    except (ConfigError, PromptNotFoundError) as e:
        return _fail(str(e), EXIT_USAGE)
    except OSError as e:
        return _fail(f"no se pudieron escribir las métricas o la caché ({e}); revisá permisos de data/", EXIT_TRIAGE_ERROR)
    except TriageError as e:
        if args.verbose:
            print(format_metric(e.record), file=sys.stderr)
        return _fail(f"no se pudo generar una respuesta válida: {e}", EXIT_TRIAGE_ERROR)

    print(json.dumps(outcome.response.model_dump(), ensure_ascii=False))
    if args.verbose:
        print(format_metric(outcome.record), file=sys.stderr)
    return EXIT_OK
