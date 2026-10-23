"""Guardrail de salida: valida el contenido de una respuesta que ya cumple el esquema.

Detecta (1) fuga del system prompt, por el canary token o por fragmentos textuales de las
instrucciones, y (2) compromisos que el borrador no puede asumir en nombre de Nubbix.
"""

import re

from triage.guardrails import GuardResult
from triage.guardrails.input_guard import normalize
from triage.schema import TriageResponse

LAYER = "output"
# 8 palabras seguidas del system prompt en la respuesta ya no son casualidad.
NGRAM_WORDS = 8

_COMMITMENTS = [
    re.compile(
        r"\bya (te |le |les )?(hemos |hicimos )?"
        r"(reintegr|reembols|devolv|acredit|cancel|elimin|borr|dimos de baja|dado de baja)\w*"
    ),
    re.compile(
        r"\b(garantizamos|aseguramos|prometemos)\b.{0,30}?"
        r"\b(reintegro|reembolso|devolucion|baja|cancelacion)\b"
    ),
    re.compile(r"\b(we have|we've|we) (already )?(refunded|cancell?ed|deleted|reimbursed)\b"),
]

_WORD = re.compile(r"\w+")


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = _WORD.findall(normalize(text))
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def check_output(response: TriageResponse, system_prompt: str, canary: str) -> GuardResult:
    text = " ".join([response.answer, *response.actions])
    if canary and canary in text:
        return GuardResult(False, "system_prompt_leak", LAYER)
    if _ngrams(text, NGRAM_WORDS) & _ngrams(system_prompt, NGRAM_WORDS):
        return GuardResult(False, "system_prompt_leak", LAYER)
    normalized_answer = normalize(response.answer)
    if any(p.search(normalized_answer) for p in _COMMITMENTS):
        return GuardResult(False, "unauthorized_commitment", LAYER)
    return GuardResult(True)
