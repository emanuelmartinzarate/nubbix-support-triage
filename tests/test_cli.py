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


def test_cli_verbose_prints_record_to_stderr(wired, capsys):
    assert cli.main(["--verbose", "factura"]) == 0
    assert '"cost_usd"' in capsys.readouterr().err
