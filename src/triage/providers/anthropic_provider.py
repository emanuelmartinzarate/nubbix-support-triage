"""Adaptador de Anthropic (Claude) sobre la interfaz LLMProvider."""

import time
from typing import Any

import anthropic

from triage.providers.base import (
    FatalProviderError,
    LLMParams,
    LLMResult,
    Message,
    TransientProviderError,
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, client: Any | None = None):
        # max_retries=0: los reintentos los maneja call_with_backoff, para no duplicarlos.
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=0)

    def complete(self, system: str, messages: list[Message], params: LLMParams) -> LLMResult:
        # La API 2026-10-21 rechaza temperature/top_p/top_k: no se envían.
        # Clasificación corta: sin thinking y effort bajo para controlar costo y latencia.
        output_config: dict = {"effort": "low"}
        if params.json_mode and params.json_schema:
            output_config["format"] = {"type": "json_schema", "schema": params.json_schema}

        start = time.perf_counter()
        try:
            response = self._client.messages.create(
                model=params.model,
                max_tokens=params.max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "disabled"},
                output_config=output_config,
                timeout=params.timeout_s,
            )
        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            raise TransientProviderError(f"anthropic {e.status_code}: {e.message}") from e
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
            raise TransientProviderError(f"anthropic: {e.__class__.__name__}") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise TransientProviderError(f"anthropic {e.status_code}: {e.message}") from e
            raise FatalProviderError(f"anthropic {e.status_code}: {e.message}") from e
        latency = time.perf_counter() - start

        if response.stop_reason == "refusal":
            raise FatalProviderError("anthropic: el modelo rechazó la solicitud (refusal)")
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_s=round(latency, 4),
            model=params.model,
        )
