"""Tipos compartidos por todos los proveedores LLM."""

from typing import Literal, TypedDict


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str
