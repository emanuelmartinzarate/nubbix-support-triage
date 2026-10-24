"""Reintento con backoff exponencial y jitter para errores transitorios del proveedor."""

import random
import time
from typing import Callable, TypeVar

from triage.providers.base import TransientProviderError

T = TypeVar("T")


def call_with_backoff(
    fn: Callable[[], T],
    max_attempts: int,
    base_delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(max_attempts):
        try:
            return fn()
        except TransientProviderError:
            if attempt == max_attempts - 1:
                raise
            sleep(base_delay_s * 2**attempt + random.uniform(0, base_delay_s))
    raise ValueError("max_attempts debe ser >= 1")
