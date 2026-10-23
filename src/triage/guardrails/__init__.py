"""Guardrails de entrada y salida del servicio de triage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str | None = None
    layer: str | None = None
