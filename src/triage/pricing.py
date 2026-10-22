"""Costo estimado por request a partir de tokens y de una tabla de precios versionada."""

from functools import lru_cache
from pathlib import Path

import yaml

PRICING_FILE = Path(__file__).with_name("pricing.yaml")


class PricingError(Exception):
    """El modelo no tiene precio cargado en pricing.yaml."""


@lru_cache(maxsize=1)
def load_pricing_table() -> dict:
    with PRICING_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["models"]


def estimate_cost(model: str, input_tokens: int, output_tokens: int, table: dict | None = None) -> float:
    prices = (table if table is not None else load_pricing_table()).get(model)
    if prices is None:
        raise PricingError(f"modelo sin precio en pricing.yaml: {model}")
    cost = (
        input_tokens * prices["input_usd_per_mtok"] + output_tokens * prices["output_usd_per_mtok"]
    ) / 1_000_000
    return round(cost, 8)
