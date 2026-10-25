import io
import json

import pytest

from conftest import FakeProvider
from triage import cli
from triage.config import ConfigError

VALID = '{"answer":"Revisamos la factura de año pasado, ñandú 🙂","confidence":0.9,"category":"billing","actions":["Reenviar factura"]}'


@pytest.fixture
def wired(monkeypatch, settings_tmp):
    fp = FakeProvider([VALID])
    monkeypatch.setattr(cli, "load_settings", lambda: settings_tmp)
    monkeypatch.setattr(cli, "get_provider", lambda name, s: fp)
    return fp


def test_cli_prints_only_contract_json_unescaped(wired, capsys):
    assert cli.main(["no me llega la factura"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert set(data) == {"answer", "confidence", "category", "actions"}
    assert "ñandú 🙂" in out


def test_cli_reads_query_from_stdin(wired, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("me cobraron doble\n"))
    assert cli.main([]) == 0
    assert json.loads(capsys.readouterr().out)["category"] == "billing"


def test_cli_empty_query_exit_2(wired, capsys):
    assert cli.main(["   "]) == 2
    assert "consulta vacía" in capsys.readouterr().err and wired.calls == []


def test_cli_missing_key_exit_2_no_traceback(monkeypatch, settings_tmp, capsys):
    monkeypatch.setattr(cli, "load_settings", lambda: settings_tmp)

    def boom(name, s):
        raise ConfigError("Falta ANTHROPIC_API_KEY")

    monkeypatch.setattr(cli, "get_provider", boom)
    assert cli.main(["hola"]) == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err and "Traceback" not in err


def test_cli_triage_error_exit_1(monkeypatch, settings_tmp, capsys):
    monkeypatch.setattr(cli, "load_settings", lambda: settings_tmp)
    monkeypatch.setattr(cli, "get_provider", lambda n, s: FakeProvider(["nope"] * 3))
    assert cli.main(["hola"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "Traceback" not in captured.err


def test_cli_unwritable_metrics_exit_1_no_traceback(wired, monkeypatch, capsys):
    def deny(record, path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("triage.service.append_metrics", deny)
    assert cli.main(["factura"]) == 1
    err = capsys.readouterr().err
    assert "métricas" in err and "Traceback" not in err


def test_cli_verbose_summary_is_human_readable(wired, capsys):
    assert cli.main(["--verbose", "factura"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["category"] == "billing"
    assert "[métrica]" in captured.err and "e-0" not in captured.err
    assert "costo USD 0.0000" in captured.err and "request_id" in captured.err


def test_format_metric_breaks_down_cache_hit_cost():
    record = {
        "provider": "anthropic", "model": "claude-haiku-5-5", "prompt_version": "v3", "status": "ok",
        "cache_hit": True, "input_tokens": 651, "output_tokens": 16, "latency_s": 1.4412,
        "cost_usd": 7.31e-05, "moderation_cost_usd": 7.31e-05, "attempts": 0,
        "guardrail": None, "request_id": "abc", "error": None,
    }
    text = cli.format_metric(record)
    assert "caché: hit" in text and "tokens 651 in / 16 out" in text and "latencia 1.44 s" in text
    assert "costo USD 0.0000731 (moderación USD 0.0000731 + triage USD 0, desde caché)" in text
    assert "e-05" not in text and "request_id abc" in text
