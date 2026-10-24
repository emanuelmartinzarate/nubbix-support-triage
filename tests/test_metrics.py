import json
from concurrent.futures import ThreadPoolExecutor

from triage.metrics import append_metrics, new_request_id, utc_now_iso


def test_append_creates_dir_and_writes_one_line_per_record(tmp_path):
    p = tmp_path / "sub" / "metrics.jsonl"
    append_metrics({"a": 1, "t": "ñandú"}, p)
    append_metrics({"a": 2}, p)
    lines = p.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["a"] for line in lines] == [1, 2] and "ñandú" in lines[0]


def test_concurrent_appends_do_not_interleave(tmp_path):
    p = tmp_path / "m.jsonl"
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: append_metrics({"i": i, "pad": "x" * 5000}, p), range(200)))
    assert sorted(json.loads(line)["i"] for line in p.read_text().splitlines()) == list(range(200))


def test_ids_and_timestamps():
    assert len(new_request_id()) == 32 and new_request_id() != new_request_id()
    assert utc_now_iso().endswith("Z")
