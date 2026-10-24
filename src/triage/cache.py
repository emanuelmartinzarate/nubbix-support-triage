"""Caché de respuestas en disco, indexada por MD5 de todo lo que determina la salida."""

import json
import hashlib
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from triage.schema import TriageResponse


def cache_key(
    provider: str, model: str, prompt_version: str, temperature: float, max_tokens: int, query: str
) -> str:
    payload = json.dumps(
        [provider, model, prompt_version, temperature, max_tokens, query.strip()], ensure_ascii=False
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, cache_dir: Path, enabled: bool):
        self.cache_dir = cache_dir
        self.enabled = enabled

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> TriageResponse | None:
        if not self.enabled:
            return None
        try:
            return TriageResponse.model_validate_json(self._path(key).read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            return None

    def set(self, key: str, response: TriageResponse) -> None:
        if not self.enabled:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Escritura atómica: un lector concurrente nunca ve un archivo a medio escribir.
        fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(response.model_dump_json())
        os.replace(tmp, self._path(key))
