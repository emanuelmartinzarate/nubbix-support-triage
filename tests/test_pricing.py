import pytest

from triage.pricing import PricingError, estimate_cost, load_pricing_table

TABLE = {"m": {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 5.0}}


def test_cost_formula():
    assert estimate_cost("m", 1000, 200, TABLE) == pytest.approx(0.002)


def test_zero_tokens():
    assert estimate_cost("m", 0, 0, TABLE) == 0.0


def test_unknown_model():
    with pytest.raises(PricingError):
        estimate_cost("nope", 1, 1, TABLE)


def test_packaged_table_has_source_for_every_model():
    for model in load_pricing_table().values():
        assert model["source_url"].startswith("https://") and model["retrieved"]


def test_default_models_are_priced():
    table = load_pricing_table()
    assert "claude-haiku-5-5" in table and "gemini-3.8-flash" in table
