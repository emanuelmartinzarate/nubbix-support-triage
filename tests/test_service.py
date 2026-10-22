import dataclasses

import pytest

from conftest import FakeProvider, last_metric
from triage.config import ConfigError
from triage.providers import get_provider
from triage.providers.base import FatalProviderError, TransientProviderError
from triage.service import TriageError, triage

VALID = '{"answer":"Hola","confidence":0.9,"category":"billing","actions":["Revisar cobro"]}'


def test_happy_path_logs_metrics(settings_tmp):
    out = triage("me cobraron doble", settings_tmp, provider=FakeProvider([VALID]))
    rec = last_metric(settings_tmp)
    assert out.status == "ok" and out.response.category == "billing"
    assert rec["attempts"] == 1 and rec["total_tokens"] == 150 and rec["status"] == "ok"
    assert rec["cost_usd"] > 0 and rec["source"] == "cli" and rec["prompt_version"] == "v1"
    assert rec["model"] == settings_tmp.anthropic_model


def test_retries_with_validation_error_in_conversation(settings_tmp):
    fp = FakeProvider(['{"category":"Facturación"}', VALID])
    out = triage("x", settings_tmp, provider=fp)
    assert out.record["attempts"] == 2 and out.record["total_tokens"] == 300
    assert "no cumple el contrato" in fp.calls[1].messages[-1]["content"]
    assert fp.calls[1].messages[-2] == {"role": "assistant", "content": '{"category":"Facturación"}'}


def test_exhausted_retries_raise_and_still_log(settings_tmp):
    with pytest.raises(TriageError):
        triage("x", settings_tmp, provider=FakeProvider(["nope"] * 3))
    rec = last_metric(settings_tmp)
    assert rec["status"] == "error" and rec["attempts"] == 3 and rec["error"]


def test_fatal_provider_error_raises_triage_error(settings_tmp):
    with pytest.raises(TriageError):
        triage("x", settings_tmp, provider=FakeProvider([FatalProviderError("401")]))
    assert last_metric(settings_tmp)["status"] == "error"


def test_transient_error_is_retried_with_backoff(settings_tmp, monkeypatch):
    monkeypatch.setattr("triage.providers.retry.time.sleep", lambda s: None)
    out = triage("x", settings_tmp, provider=FakeProvider([TransientProviderError("429"), VALID]))
    assert out.status == "ok"


def test_empty_query_raises_value_error_without_calling_provider(settings_tmp):
    fp = FakeProvider([VALID])
    with pytest.raises(ValueError):
        triage("   ", settings_tmp, provider=fp)
    assert fp.calls == []


def test_prompt_version_override(settings_tmp):
    out = triage("x", settings_tmp, provider=FakeProvider([VALID]), prompt_version="v1", source="eval")
    assert out.record["source"] == "eval" and len(out.canary) == 16


def test_get_provider_missing_key_names_variable(settings_tmp):
    s = dataclasses.replace(settings_tmp, anthropic_api_key=None)
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        get_provider("anthropic", s)


def test_get_provider_unknown_name(settings_tmp):
    with pytest.raises(ConfigError):
        get_provider("openai", settings_tmp)


def test_second_call_hits_cache_without_provider_call(settings_tmp):
    fp = FakeProvider([VALID])
    triage("me cobraron doble", settings_tmp, provider=fp)
    out = triage("me cobraron doble", settings_tmp, provider=fp)
    rec = last_metric(settings_tmp)
    assert out.response.category == "billing" and len(fp.calls) == 1
    assert rec["cache_hit"] is True and rec["cost_usd"] == 0.0 and rec["attempts"] == 0


def test_no_cache_flag_bypasses(settings_tmp):
    fp = FakeProvider([VALID, VALID])
    triage("x", settings_tmp, provider=fp)
    triage("x", settings_tmp, provider=fp, use_cache=False)
    assert len(fp.calls) == 2


def test_cache_disabled_in_settings(settings_tmp):
    s = dataclasses.replace(settings_tmp, cache_enabled=False)
    fp = FakeProvider([VALID, VALID])
    triage("x", s, provider=fp)
    triage("x", s, provider=fp)
    assert len(fp.calls) == 2


def test_failed_request_is_not_cached(settings_tmp):
    with pytest.raises(TriageError):
        triage("x", settings_tmp, provider=FakeProvider(["nope"] * 3))
    fp = FakeProvider([VALID])
    triage("x", settings_tmp, provider=fp)
    assert len(fp.calls) == 1


def test_editing_prompt_text_invalidates_cache(settings_tmp, tmp_path, monkeypatch):
    import shutil

    from triage import prompts

    pdir = tmp_path / "prompts"
    shutil.copytree(prompts.DEFAULT_PROMPTS_DIR, pdir)
    monkeypatch.setenv("PROMPTS_DIR", str(pdir))
    fp = FakeProvider([VALID, VALID])
    triage("x", settings_tmp, provider=fp)
    v1 = pdir / "v1_zero_shot.yaml"
    v1.write_text(v1.read_text(encoding="utf-8").replace("Sos el asistente", "Sos EL asistente"), encoding="utf-8")
    triage("x", settings_tmp, provider=fp)
    assert len(fp.calls) == 2
