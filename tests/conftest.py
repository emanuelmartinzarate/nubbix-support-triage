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
