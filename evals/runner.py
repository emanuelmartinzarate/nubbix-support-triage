"""Runner de evals: corre el dataset contra proveedores y versiones de prompt y reporta métricas.

Uso:
    python evals/runner.py --provider anthropic --prompt v1 --limit 5
    python evals/runner.py --all                 # todas las versiones x ambos proveedores
    python evals/runner.py --all --no-cache --max-cost 2
"""

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.scoring import CATEGORIES, CaseResult, CostBudget, summarize  # noqa: E402
from triage.config import ConfigError, Settings, load_settings  # noqa: E402
from triage.prompts import list_prompt_versions  # noqa: E402
from triage.providers import PROVIDERS, get_provider  # noqa: E402
from triage.service import TriageError, triage  # noqa: E402

DEFAULT_DATASET = ROOT / "evals" / "dataset.jsonl"
RESULTS_DIR = ROOT / "evals" / "results"


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_cases(path: Path, limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit] if limit else rows


def run_case(case: dict, settings: Settings, provider, provider_name: str, version: str, use_cache: bool) -> CaseResult:
    base = dict(id=case["id"], expected=case["expected_category"], tags=case.get("tags", []))
    try:
        out = triage(
            case["query"], settings, provider=provider, provider_name=provider_name,
            prompt_version=version, source="eval", use_cache=use_cache,
        )
        rec = out.record
        return CaseResult(
            **base, predicted=out.response.category, status=out.status, attempts=rec["attempts"],
            latency_s=rec["latency_s"], input_tokens=rec["input_tokens"], output_tokens=rec["output_tokens"],
            cost_usd=rec["cost_usd"], cache_hit=rec["cache_hit"],
            confidence=out.response.confidence, actions=out.response.actions,
        )
    except TriageError as e:
        rec = e.record
        return CaseResult(
            **base, predicted=None, status="error", attempts=rec["attempts"], latency_s=rec["latency_s"],
            input_tokens=rec["input_tokens"], output_tokens=rec["output_tokens"], cost_usd=rec["cost_usd"],
            cache_hit=False, error=str(e),
        )


def run_combo(cases, settings, provider_name, version, use_cache, budget: CostBudget) -> tuple[list[CaseResult], bool]:
    provider = get_provider(provider_name, settings)
    lock = threading.Lock()
    aborted = threading.Event()

    def work(case):
        with lock:
            if budget.exhausted:
                aborted.set()
                return None
        result = run_case(case, settings, provider, provider_name, version, use_cache)
        with lock:
            budget.add(result.cost_usd)
        return result

    workers = max(1, settings.eval_concurrency)
    with ThreadPoolExecutor(workers) as pool:
        results = [r for r in pool.map(work, cases) if r is not None]
    return results, aborted.is_set()


def format_summary(provider_name: str, version: str, s: dict) -> str:
    def pct(x):
        return "-" if x is None else f"{x:.0%}"

    def sec(x):
        return "-" if x is None else f"{x:.2f}s"

    def num(x):
        return "-" if x is None else f"{x:.2f}"

    lines = [
        f"\n== {provider_name} / {version}  (n={s['n']}) ==",
        f"accuracy {pct(s['accuracy'])} | macro {pct(s['macro_accuracy'])} | "
        f"JSON válido 1er intento {pct(s['json_valid_first_try_rate'])} | errores {s['errors']} | bloqueados {s['blocked']}",
        "por categoría: " + ", ".join(
            f"{c} {pct(s['per_category'][c]['accuracy'])} ({s['per_category'][c]['correct']}/{s['per_category'][c]['n']})"
            for c in CATEGORIES if c in s["per_category"]
        ),
        f"latencia p50 {sec(s['latency_p50'])} p95 {sec(s['latency_p95'])} | tokens in {s['input_tokens']} out {s['output_tokens']} | "
        f"costo ${s['cost_usd']:.4f} | cache hits {s['cache_hits']}",
        f"confianza media: casos claros {num(s['confidence_clear'])} | ambiguos {num(s['confidence_ambiguous'])} "
        f"| brecha {num(s['confidence_gap'])}",
    ]
    return "\n".join(lines)


def comparison_table(rows: list[tuple[str, str, dict]]) -> str:
    def pct(x):
        return "-" if x is None else f"{x:.0%}"

    def sec(x):
        return "-" if x is None else f"{x:.2f}"

    header = (
        "| Proveedor | Prompt | Accuracy | Macro | billing | technical | account | other "
        "| JSON 1er intento | Brecha confianza | p50 (s) | p95 (s) | Costo (USD) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    body = []
    for provider_name, version, s in rows:
        cats = [pct(s["per_category"].get(c, {}).get("accuracy")) for c in CATEGORIES]
        body.append(
            f"| {provider_name} | {version} | {pct(s['accuracy'])} | {pct(s['macro_accuracy'])} | "
            + " | ".join(cats)
            + f" | {pct(s['json_valid_first_try_rate'])} | {sec(s['confidence_gap'])} | {sec(s['latency_p50'])} | {sec(s['latency_p95'])} | {s['cost_usd']:.4f} |"
        )
    return header + "\n" + "\n".join(body) + "\n"


def save_result(provider_name, version, config, summary, results, suffix="") -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"{stamp}_{provider_name}_{version}{suffix}.json"
    payload = {"config": config, "summary": summary, "cases": [r.__dict__ for r in results]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args(argv):
    p = argparse.ArgumentParser(description="Runner de evals del servicio de triage")
    p.add_argument("--provider", choices=PROVIDERS, help="proveedor (default: LLM_PROVIDER)")
    p.add_argument("--prompt", help="versión de prompt (default: PROMPT_VERSION)")
    p.add_argument("--all", action="store_true", help="todas las versiones de prompt x todos los proveedores")
    p.add_argument("--limit", type=int, help="solo los primeros N casos (para iterar barato)")
    p.add_argument("--no-cache", action="store_true", help="no leer la caché (fuerza llamadas reales)")
    p.add_argument("--max-cost", type=float, help="tope de costo USD para esta invocación (default: EVAL_MAX_COST_USD)")
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    cases = load_cases(args.dataset, args.limit)
    budget = CostBudget(args.max_cost if args.max_cost is not None else settings.eval_max_cost_usd)

    if args.all:
        combos = [(p, v) for p in PROVIDERS for v in list_prompt_versions()]
    else:
        combos = [(args.provider or settings.llm_provider, args.prompt or settings.prompt_version)]

    rows, aborted = [], False
    for provider_name, version in combos:
        if budget.exhausted:
            aborted = True
            break
        try:
            results, combo_aborted = run_combo(cases, settings, provider_name, version, not args.no_cache, budget)
        except ConfigError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        summary = summarize(results)
        summary["aborted_by_cost_cap"] = combo_aborted
        config = {"provider": provider_name, "prompt_version": version, "dataset": str(args.dataset.name),
                  "limit": args.limit, "no_cache": args.no_cache}
        path = save_result(provider_name, version, config, summary, results)
        print(format_summary(provider_name, version, summary))
        print(f"resultado: {_display(path)}")
        rows.append((provider_name, version, summary))
        if combo_aborted:
            aborted = True
            break

    if args.all and rows:
        (RESULTS_DIR / "comparison.md").write_text(comparison_table(rows), encoding="utf-8")
        print(f"\ncomparativa: {_display(RESULTS_DIR / 'comparison.md')}")
    print(f"\ncosto total de esta corrida: ${budget.spent:.4f} (tope ${budget.max_usd:.2f})")
    if aborted:
        print("ATENCIÓN: corrida cortada por el tope de costo; los resultados son parciales.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
