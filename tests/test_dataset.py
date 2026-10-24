import json
from collections import Counter
from pathlib import Path

from triage.prompts import list_prompt_versions, load_prompt

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"billing", "technical", "account", "other"}


def _rows(name):
    path = ROOT / "evals" / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(s):
    return " ".join(s.casefold().split())


def test_dataset_is_valid_and_balanced():
    rows = _rows("dataset.jsonl")
    assert len(rows) >= 30 and len({r["id"] for r in rows}) == len(rows)
    counts = Counter(r["expected_category"] for r in rows)
    assert set(counts) == CATEGORIES and min(counts.values()) >= 8
    assert all(r["query"].strip() and isinstance(r["tags"], list) for r in rows)


def test_dataset_covers_required_variety():
    tags = Counter(t for r in _rows("dataset.jsonl") for t in r["tags"])
    assert tags["multi-topic"] + tags["ambiguous"] >= 8
    assert tags["informal"] + tags["typos"] >= 6
    assert tags["lang-en"] >= 2 and tags["lang-pt"] >= 2
    assert tags["gibberish"] >= 2 and tags["long"] >= 1 and tags["short"] >= 2
    assert tags["benign-trigger"] >= 2


def test_long_case_is_long():
    assert any(len(r["query"]) > 1500 for r in _rows("dataset.jsonl") if "long" in r["tags"])


def test_few_shot_examples_not_in_dataset():
    dataset = {_norm(r["query"]) for r in _rows("dataset.jsonl")}
    for version in list_prompt_versions():
        for example in load_prompt(version).examples:
            assert _norm(example["query"]) not in dataset, (version, example["query"])
