"""Métricas de evaluación: accuracy global/por categoría, validez de JSON, latencia, costo."""

import math
from collections import defaultdict
from dataclasses import dataclass, field

CATEGORIES = ("billing", "technical", "account", "other")


@dataclass
class CaseResult:
    id: str
    expected: str
    predicted: str | None
    status: str  # ok | blocked | error
    attempts: int
    latency_s: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cache_hit: bool
    tags: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def correct(self) -> bool:
        # Un bloqueo o un error nunca cuentan como acierto.
        return self.status == "ok" and self.predicted == self.expected


def percentile(values: list[float], p: float) -> float | None:
    """Percentil por nearest-rank: el menor valor con al menos p% de los datos por debajo o igual."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


class CostBudget:
    def __init__(self, max_usd: float):
        self.max_usd = max_usd
        self.spent = 0.0

    def add(self, cost: float) -> None:
        self.spent += cost

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.max_usd


def summarize(results: list[CaseResult]) -> dict:
    n = len(results)
    per_category = {}
    for cat in CATEGORIES:
        cases = [r for r in results if r.expected == cat]
        if cases:
            correct = sum(r.correct for r in cases)
            per_category[cat] = {"n": len(cases), "correct": correct, "accuracy": correct / len(cases)}

    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        predicted = r.predicted if r.status == "ok" else r.status
        confusion[r.expected][predicted] += 1

    fresh_ok = [r for r in results if r.status == "ok" and not r.cache_hit]
    latencies = [r.latency_s for r in results if not r.cache_hit and r.status != "blocked"]
    return {
        "n": n,
        "accuracy": sum(r.correct for r in results) / n if n else 0.0,
        "macro_accuracy": (
            sum(c["accuracy"] for c in per_category.values()) / len(per_category) if per_category else 0.0
        ),
        "per_category": per_category,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "json_valid_first_try_rate": (
            sum(r.attempts == 1 for r in fresh_ok) / len(fresh_ok) if fresh_ok else None
        ),
        "avg_attempts": sum(r.attempts for r in fresh_ok) / len(fresh_ok) if fresh_ok else None,
        "errors": sum(r.status == "error" for r in results),
        "blocked": sum(r.status == "blocked" for r in results),
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "input_tokens": sum(r.input_tokens for r in results),
        "output_tokens": sum(r.output_tokens for r in results),
        "cost_usd": round(sum(r.cost_usd for r in results), 8),
        "cache_hits": sum(r.cache_hit for r in results),
    }
