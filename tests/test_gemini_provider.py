from types import SimpleNamespace

import pytest
from google.genai import errors

from triage.providers.base import FatalProviderError, LLMParams, RefusalError, TransientProviderError
from triage.providers.gemini_provider import GeminiProvider

PARAMS = LLMParams(model="gemini-3.8-flash", temperature=0.0, max_tokens=600, timeout_s=30.0)
SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}}
MESSAGES = [
    {"role": "user", "content": "ejemplo"},
    {"role": "assistant", "content": '{"a":0}'},
    {"role": "user", "content": "hola"},
]


class FakeModels:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.last_kwargs = result, error, None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


def _client(**kw):
    return SimpleNamespace(models=FakeModels(**kw))


def _ok(text='{"a":1}', thoughts=5):
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=20, candidates_token_count=8, thoughts_token_count=thoughts),
        candidates=[SimpleNamespace(finish_reason="STOP")],
    )


def test_maps_roles_and_system_instruction():
    client = _client(result=_ok())
    GeminiProvider("k", client=client).complete("sys", MESSAGES, PARAMS)
    kw = client.models.last_kwargs
    assert [c.role for c in kw["contents"]] == ["user", "model", "user"]
    assert kw["contents"][2].parts[0].text == "hola"
    assert kw["config"].system_instruction == "sys" and kw["model"] == "gemini-3.8-flash"
    assert kw["config"].temperature == 0.0 and kw["config"].max_output_tokens == 600


def test_json_mode_sets_mime_type_and_schema():
    client = _client(result=_ok())
    params = LLMParams(**{**PARAMS.__dict__, "json_schema": SCHEMA})
    GeminiProvider("k", client=client).complete("s", MESSAGES, params)
    cfg = client.models.last_kwargs["config"]
    assert cfg.response_mime_type == "application/json" and cfg.response_json_schema == SCHEMA


def test_usage_includes_thinking_tokens_as_output():
    r = GeminiProvider("k", client=_client(result=_ok(thoughts=5))).complete("s", MESSAGES, PARAMS)
    assert (r.input_tokens, r.output_tokens) == (20, 13) and r.text == '{"a":1}'


def test_missing_thoughts_count_is_zero():
    r = GeminiProvider("k", client=_client(result=_ok(thoughts=None))).complete("s", MESSAGES, PARAMS)
    assert r.output_tokens == 8


def test_empty_text_is_fatal():
    blocked = _ok(text=None)
    blocked.candidates = [SimpleNamespace(finish_reason="SAFETY")]
    with pytest.raises(RefusalError, match="SAFETY"):
        GeminiProvider("k", client=_client(result=blocked)).complete("s", MESSAGES, PARAMS)


def test_429_is_transient():
    err = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(TransientProviderError):
        GeminiProvider("k", client=_client(error=err)).complete("s", MESSAGES, PARAMS)


def test_503_is_transient():
    err = errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
    with pytest.raises(TransientProviderError):
        GeminiProvider("k", client=_client(error=err)).complete("s", MESSAGES, PARAMS)


def test_400_is_fatal():
    err = errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})
    with pytest.raises(FatalProviderError):
        GeminiProvider("k", client=_client(error=err)).complete("s", MESSAGES, PARAMS)


def test_empty_text_without_safety_is_plain_fatal():
    empty = _ok(text=None)
    empty.candidates = [SimpleNamespace(finish_reason="MAX_TOKENS")]
    with pytest.raises(FatalProviderError) as exc:
        GeminiProvider("k", client=_client(result=empty)).complete("s", MESSAGES, PARAMS)
    assert not isinstance(exc.value, RefusalError)
