import os
import re
import time

import pytest

from triage.cache import ResponseCache, cache_key
from triage.schema import TriageResponse

BASE = dict(provider="anthropic", model="m", prompt_version="v1", temperature=0.0, max_tokens=600, query="hola")
RESP = TriageResponse(answer="a", confidence=0.5, category="other", actions=["x"])


def test_key_stable_and_32_hex():
    k = cache_key(**BASE)
    assert k == cache_key(**BASE) and re.fullmatch(r"[0-9a-f]{32}", k)


@pytest.mark.parametrize(
    "field,value",
    [("provider", "gemini"), ("model", "m2"), ("prompt_version", "v2"),
     ("temperature", 0.5), ("max_tokens", 100), ("query", "chau")],
)
def test_key_changes_with_each_field(field, value):
    assert cache_key(**{**BASE, field: value}) != cache_key(**BASE)


def test_key_ignores_surrounding_whitespace():
    assert cache_key(**{**BASE, "query": "  hola \n"}) == cache_key(**BASE)


def test_roundtrip(tmp_path):
    cache = ResponseCache(tmp_path, enabled=True)
    cache.set("k", RESP)
    assert cache.get("k") == RESP


def test_disabled_cache_never_hits(tmp_path):
    cache = ResponseCache(tmp_path, enabled=False)
    cache.set("k", RESP)
    assert cache.get("k") is None and not list(tmp_path.iterdir())


def test_corrupt_file_is_miss(tmp_path):
    (tmp_path / "k.json").write_text("{roto", encoding="utf-8")
    assert ResponseCache(tmp_path, enabled=True).get("k") is None


def _aged(tmp_path, seconds):
    cache = ResponseCache(tmp_path, enabled=True)
    cache.set("k", RESP)
    old = time.time() - seconds
    os.utime(tmp_path / "k.json", (old, old))
    return tmp_path


def test_ttl_zero_never_expires(tmp_path):
    assert ResponseCache(_aged(tmp_path, 10 * 365 * 86400), enabled=True, ttl_s=0).get("k") == RESP


def test_entry_older_than_ttl_is_miss(tmp_path):
    assert ResponseCache(_aged(tmp_path, 7200), enabled=True, ttl_s=3600).get("k") is None


def test_entry_within_ttl_is_hit(tmp_path):
    assert ResponseCache(_aged(tmp_path, 60), enabled=True, ttl_s=3600).get("k") == RESP
