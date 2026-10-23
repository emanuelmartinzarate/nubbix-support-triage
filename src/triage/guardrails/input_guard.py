"""Guardrail de entrada, capa determinística: normalización + patrones de injection (ES/EN).

Es la primera capa (gratis y sin latencia). No pretende atrapar todo: las variaciones que
la evaden las cubren las reglas del prompt v3 y el guardrail de salida.
"""

import base64
import binascii
import re
import unicodedata

from triage.guardrails import GuardResult

LAYER = "input_heuristic"

_ZERO_WIDTH = re.compile("[​-‏⁠﻿]")

# Patrones sobre texto normalizado (minúsculas, sin acentos ni caracteres de ancho cero).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("injection", re.compile(
        r"\b(ignor\w*|olvid\w*|forget|disregard|descarta\w*|saltea\w*)\b.{0,40}?"
        r"\b(instrucciones|indicaciones|reglas|instructions|rules|directivas)\b"
    )),
    ("prompt_exfiltration", re.compile(r"\b(system prompt|prompt del sistema|prompt de sistema|system message)\b")),
    ("prompt_exfiltration", re.compile(
        r"\b(mostra\w*|revela\w*|repet\w*|imprim\w*|deci\w*|copia\w*|show|reveal|print|repeat|tell me)\b.{0,25}?"
        r"\b(tus|tu|your)\s+(instrucciones|prompt|reglas|instructions|rules|configuracion)\b"
    )),
    ("role_override", re.compile(r"\b(a partir de ahora|desde ahora|from now on)\b.{0,20}?\b(sos|eres|seras|you are|you're)\b")),
    ("role_override", re.compile(r"\b(you are now|act as|pretend to be)\b")),
    ("role_override", re.compile(
        r"\b(actua\w*|comportate|hace de cuenta)\b.{0,20}?"
        r"\b(asistente|ia|modelo|bot|ai|sin (restricciones|reglas|filtros|limites))\b"
    )),
    ("role_override", re.compile(r"\b(developer mode|modo desarrollador|modo dios|god mode|jailbreak|do anything now)\b")),
    ("role_override", re.compile(r"\b(sos|eres|you are|modo|mode)\s+dan\b")),
]

# Patrones sobre el texto crudo: intentos de cerrar el delimitador o inyectar turnos.
_DELIMITERS = re.compile(r"</?\s*(ticket|system|sistema|assistant|user)\s*>|\[/?inst\]|<<\s*/?sys\s*>>", re.IGNORECASE)

_BASE64_TOKEN = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(text.casefold().split())


def _match_patterns(normalized: str) -> str | None:
    for reason, pattern in _PATTERNS:
        if pattern.search(normalized):
            return reason
    return None


def _decoded_base64_chunks(text: str) -> list[str]:
    chunks = []
    for token in _BASE64_TOKEN.findall(text):
        try:
            decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=False)
        except (binascii.Error, ValueError):
            continue
        chunks.append(decoded.decode("utf-8", errors="ignore"))
    return chunks


def check_input(text: str, max_chars: int) -> GuardResult:
    if len(text) > max_chars:
        return GuardResult(False, "too_long", LAYER)
    if _DELIMITERS.search(text):
        return GuardResult(False, "delimiter_attack", LAYER)
    reason = _match_patterns(normalize(text))
    if reason:
        return GuardResult(False, reason, LAYER)
    for chunk in _decoded_base64_chunks(text):
        reason = _match_patterns(normalize(chunk))
        if reason:
            return GuardResult(False, f"{reason}_base64", LAYER)
    return GuardResult(True)
