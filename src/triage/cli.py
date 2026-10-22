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
    parser.add_argument("--verbose", action="store_true", help="imprime la métrica del request en stderr")
    return parser.parse_args(argv)


def _read_query(args: argparse.Namespace) -> str:
    if args.query is not None:
        return args.query
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


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
    except TriageError as e:
        if args.verbose:
            print(json.dumps(e.record, ensure_ascii=False), file=sys.stderr)
        return _fail(f"no se pudo generar una respuesta válida: {e}", EXIT_TRIAGE_ERROR)

    print(json.dumps(outcome.response.model_dump(), ensure_ascii=False))
    if args.verbose:
        print(json.dumps(outcome.record, ensure_ascii=False), file=sys.stderr)
    return EXIT_OK
