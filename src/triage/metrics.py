"""Registro append-only de métricas por request en JSONL."""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


def new_request_id() -> str:
    return uuid.uuid4().hex


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def append_metrics(record: dict, path: Path) -> None:
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
