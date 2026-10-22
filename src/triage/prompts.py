"""Carga de prompts versionados (prompts/*.yaml) y armado de mensajes."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from triage.providers.base import Message

DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
NON_TRIAGE_VERSIONS = {"moderation"}


class PromptNotFoundError(Exception):
    """No existe un YAML de prompt con esa versión."""


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: str
    technique: str
    description: str
    system: str
    user_template: str
    examples: tuple[dict, ...] = ()


def _prompts_dir(prompts_dir: Path | None) -> Path:
    return prompts_dir or Path(os.environ.get("PROMPTS_DIR", DEFAULT_PROMPTS_DIR))


def _load_all(prompts_dir: Path | None) -> dict[str, PromptTemplate]:
    templates = {}
    for path in sorted(_prompts_dir(prompts_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["version"] = str(data["version"])
        data["examples"] = tuple(data.get("examples") or ())
        templates[data["version"]] = PromptTemplate(**data)
    return templates


def load_prompt(version: str, prompts_dir: Path | None = None) -> PromptTemplate:
    templates = _load_all(prompts_dir)
    if version not in templates:
        raise PromptNotFoundError(
            f"no existe el prompt {version!r}; disponibles: {', '.join(sorted(templates))}"
        )
    return templates[version]


def list_prompt_versions(prompts_dir: Path | None = None) -> list[str]:
    return sorted(v for v in _load_all(prompts_dir) if v not in NON_TRIAGE_VERSIONS)


def _neutralize_delimiters(query: str) -> str:
    # El ticket va entre <ticket>...</ticket>; el usuario no puede cerrarlo ni abrir otro.
    return query.replace("</ticket>", "[ticket]").replace("<ticket>", "[ticket]")


def _render_user(prompt: PromptTemplate, query: str) -> str:
    # replace y no format: las llaves dentro del ticket no deben romper el template.
    return prompt.user_template.replace("{query}", _neutralize_delimiters(query))


def build_messages(prompt: PromptTemplate, query: str, canary: str) -> tuple[str, list[Message]]:
    system = f"{prompt.system.rstrip()}\n\n[ref:{canary}]"
    messages: list[Message] = []
    for example in prompt.examples:
        messages.append({"role": "user", "content": _render_user(prompt, example["query"])})
        messages.append(
            {"role": "assistant", "content": json.dumps(example["output"], ensure_ascii=False)}
        )
    messages.append({"role": "user", "content": _render_user(prompt, query)})
    return system, messages
