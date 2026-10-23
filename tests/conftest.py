from dataclasses import dataclass, field
from typing import Callable

from triage.providers.base import LLMParams, LLMResult


@dataclass
class Call:
    system: str
    messages: list
    params: LLMParams


@dataclass
class FakeProvider:
    """Proveedor guionado: devuelve (o levanta) las respuestas en orden y registra las llamadas.

    Cada respuesta puede ser un str, una Exception o un callable (system, messages) -> str.
    """

    responses: list
    name: str = "fake"
    input_tokens: int = 100
    output_tokens: int = 50
    calls: list[Call] = field(default_factory=list)

    def complete(self, system, messages, params):
        self.calls.append(Call(system, [dict(m) for m in messages], params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, Callable):
            response = response(system, messages)
        return LLMResult(
            text=response,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            latency_s=0.01,
            model=params.model,
        )


import dataclasses

import pytest

from triage.config import load_settings


@pytest.fixture
def settings_tmp(tmp_path, monkeypatch):
    """Settings aisladas: métricas y caché en tmp, sin leer .env, modelo con precio conocido."""
    for var in ("LLM_PROVIDER", "PROMPT_VERSION", "CACHE_ENABLED", "GUARDRAILS_ENABLED", "MODERATION_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    base = load_settings(env_file=None)
    return dataclasses.replace(
        base,
        anthropic_api_key="test-key",
        prompt_version="v1",
        moderation_enabled=False,
        metrics_path=tmp_path / "metrics.jsonl",
        cache_dir=tmp_path / "cache",
    )


def last_metric(settings):
    import json

    return json.loads(settings.metrics_path.read_text(encoding="utf-8").splitlines()[-1])
