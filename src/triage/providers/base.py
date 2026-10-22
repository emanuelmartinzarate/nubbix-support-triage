"""Contrato común de proveedores LLM: la lógica de negocio solo conoce estos tipos."""

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMParams:
    model: str
    temperature: float
    max_tokens: int
    timeout_s: float
    json_mode: bool = True
    # JSON Schema para salida estructurada nativa, si el proveedor la soporta.
    json_schema: dict | None = None


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    model: str


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, messages: list[Message], params: LLMParams) -> LLMResult: ...


class ProviderError(Exception):
    """Error al llamar al proveedor."""


class TransientProviderError(ProviderError):
    """Error recuperable (429, 5xx, timeout, red): se reintenta con backoff."""


class FatalProviderError(ProviderError):
    """Error no recuperable (auth, request inválido, rechazo): falla rápido."""
