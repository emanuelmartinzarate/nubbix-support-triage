"""Guardrail de entrada, capa de moderación: un LLM barato clasifica abuso o manipulación.

Es opcional (MODERATION_ENABLED) porque agrega una llamada por request. Es fail-open: si la
respuesta no se puede interpretar, deja pasar el ticket, porque las capas heurística, de prompt
y de salida siguen activas; bloquear a un cliente real por un error del filtro sería peor.
"""

import dataclasses
import json

from triage.guardrails import GuardResult
from triage.prompts import build_messages, load_prompt
from triage.providers.base import LLMParams, LLMProvider, LLMResult

LAYER = "moderation"

MODERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "flagged": {"type": "boolean"},
        "category": {"type": "string", "enum": ["manipulation", "abuse", "harmful", "none"]},
    },
    "required": ["flagged", "category"],
    "additionalProperties": False,
}


def moderate(text: str, provider: LLMProvider, params: LLMParams) -> tuple[GuardResult, LLMResult | None]:
    system, messages = build_messages(load_prompt("moderation"), text, canary="moderation")
    result = provider.complete(system, messages, dataclasses.replace(params, json_schema=MODERATION_SCHEMA))
    try:
        raw = result.text
        verdict = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        flagged = bool(verdict["flagged"])
    except (ValueError, KeyError, TypeError):
        return GuardResult(True, "moderation_unparseable", LAYER), result
    if flagged:
        return GuardResult(False, f"moderation_{verdict.get('category', 'flagged')}", LAYER), result
    return GuardResult(True), result
