import pytest

from evals.scoring import CaseResult, CostBudget, percentile, summarize


def _case(id_, expected, predicted, status="ok", attempts=1, latency=1.0, cost=0.001, cache_hit=False):
    return CaseResult(
        id=id_, expected=expected, predicted=predicted, status=status, attempts=attempts,
        latency_s=latency, input_tokens=100, output_tokens=50, cost_usd=cost, cache_hit=cache_hit, tags=[],
    )


def test_summarize_accuracy_and_per_category():
    s = summarize([
        _case("a", "billing", "billing"),
        _case("b", "billing", "technical"),
        _case("c", "technical", "technical"),
        _case("d", "account", None, status="error"),
    ])
    assert s["n"] == 4 and s["accuracy"] == pytest.approx(0.5)
    assert s["per_category"]["billing"] == {"n": 2, "correct": 1, "accuracy": 0.5}
    assert s["per_category"]["account"]["accuracy"] == 0.0 and s["errors"] == 1


def test_macro_vs_micro_differ_on_imbalance():
    cases = [_case(str(i), "billing", "billing") for i in range(9)] + [_case("x", "other", "billing")]
    s = summarize(cases)
    assert s["accuracy"] == pytest.approx(0.9) and s["macro_accuracy"] == pytest.approx(0.5)


def test_blocked_and_error_count_as_wrong():
    s = summarize([_case("a", "other", "other", status="blocked"), _case("b", "billing", None, status="error")])
    assert s["accuracy"] == 0.0 and s["blocked"] == 1 and s["errors"] == 1


def test_first_try_rate_excludes_cache_hits():
    s = summarize([
        _case("a", "billing", "billing", attempts=1),
        _case("b", "billing", "billing", attempts=2),
        _case("c", "billing", "billing", attempts=0, cache_hit=True, cost=0.0),
    ])
    assert s["json_valid_first_try_rate"] == pytest.approx(0.5) and s["cache_hits"] == 1


def test_latency_percentiles_exclude_cache_hits():
    s = summarize([_case("a", "billing", "billing", latency=2.0), _case("b", "billing", "billing", latency=0.0, cache_hit=True)])
    assert s["latency_p50"] == 2.0


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4], 50) == 2 and percentile([1, 2, 3, 4], 95) == 4
    assert percentile([], 50) is None


def test_confusion_matrix():
    s = summarize([_case("a", "billing", "technical"), _case("b", "billing", "billing")])
    assert s["confusion"]["billing"] == {"technical": 1, "billing": 1}


def test_totals():
    s = summarize([_case("a", "billing", "billing", cost=0.002), _case("b", "other", "other", cost=0.003)])
    assert s["cost_usd"] == pytest.approx(0.005) and s["input_tokens"] == 200


def test_budget_exhausts():
    b = CostBudget(0.01)
    b.add(0.006)
    assert not b.exhausted
    b.add(0.005)
    assert b.exhausted and b.spent == pytest.approx(0.011)
