"""Contrato de salida del servicio de triage y su parseo/validación."""

import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

Category = Literal["billing", "technical", "account", "other"]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

BLOCKED_ANSWER = (
    "Gracias por tu mensaje. Un agente de soporte va a revisar tu consulta "
    "y te responderá a la brevedad."
)


class TriageResponse(BaseModel):
    """Contrato estable: {answer, confidence, category, actions}."""

    model_config = ConfigDict(extra="forbid")

    answer: NonEmptyStr
    confidence: float = Field(ge=0.0, le=1.0)
    category: Category
    actions: list[NonEmptyStr] = Field(min_length=1, max_length=5)


class ParseError(Exception):
    """La salida del modelo no cumple el contrato. El mensaje se reenvía al modelo."""


_FENCE_RE = re.compile(r"```(?:json)?", re.IGNORECASE)


def parse_response(text: str) -> TriageResponse:
    cleaned = _FENCE_RE.sub("", text)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ParseError("no se encontró un objeto JSON en la respuesta")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON inválido: {e.msg} (posición {e.pos})") from e
    try:
        return TriageResponse.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'raíz'}: {err['msg']}" for err in e.errors()
        )
        raise ParseError(f"no cumple el esquema: {problems}") from e


def blocked_response(reason: str) -> TriageResponse:
    """Respuesta válida para consultas bloqueadas por un guardrail; no revela detalles del sistema."""
    return TriageResponse(
        answer=BLOCKED_ANSWER,
        confidence=0.0,
        category="other",
        actions=[f"Revisión manual: posible intento de manipulación ({reason})"],
    )
