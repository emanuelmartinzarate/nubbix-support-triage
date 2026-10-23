import json

from conftest import FakeProvider
from evals import runner

VALID = '{"answer":"ok","confidence":0.9,"category":"billing","actions":["x"]}'


def test_runner_aborts_when_budget_exhausted(monkeypatch, settings_tmp, tmp_path, capsys):
    dataset = tmp_path / "ds.jsonl"
    dataset.write_text("".join(json.dumps({"id": f"c{i}", "query": f"q{i}", "expected_category": "billing"}) + "\n"
                               for i in range(5)), encoding="utf-8")
    monkeypatch.setattr(runner, "load_settings", lambda: settings_tmp)
    monkeypatch.setattr(runner, "get_provider", lambda n, s: FakeProvider([VALID] * 5))
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    # Cada caso cuesta ~0.000035 USD con Haiku: un tope de 0.00005 deja pasar 2 casos.
    assert runner.main(["--provider", "anthropic", "--prompt", "v1", "--dataset", str(dataset), "--max-cost", "0.00005"]) == 0
    saved = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    assert saved["summary"]["aborted_by_cost_cap"] is True and saved["summary"]["n"] == 2
    assert "cortada por el tope" in capsys.readouterr().err
