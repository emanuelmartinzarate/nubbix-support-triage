"""Adaptador de Google Gemini sobre la interfaz LLMProvider."""

import time
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from triage.providers.base import (
    FatalProviderError,
    LLMParams,
    LLMResult,
    Message,
    TransientProviderError,
)

_ROLES = {"user": "user", "assistant": "model"}


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, client: Any | None = None):
        self._client = client or genai.Client(api_key=api_key)

    def complete(self, system: str, messages: list[Message], params: LLMParams) -> LLMResult:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=params.temperature,
            max_output_tokens=params.max_tokens,
            # Thinking mínimo: la clasificación no lo necesita y se factura como salida.
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            http_options=types.HttpOptions(timeout=int(params.timeout_s * 1000)),
        )
        if params.json_mode:
            config.response_mime_type = "application/json"
            if params.json_schema:
                config.response_json_schema = params.json_schema
        contents = [
            types.Content(role=_ROLES[m["role"]], parts=[types.Part(text=m["content"])])
            for m in messages
        ]

        start = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=params.model, contents=contents, config=config
            )
        except errors.APIError as e:
            message = f"gemini {e.code}: {e.message}"
            if e.code == 429 or (e.code or 0) >= 500:
                raise TransientProviderError(message) from e
            raise FatalProviderError(message) from e
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise TransientProviderError(f"gemini: {e.__class__.__name__}") from e
        latency = time.perf_counter() - start

        if not response.text:
            reason = response.candidates[0].finish_reason if response.candidates else "sin candidatos"
            raise FatalProviderError(f"gemini: respuesta vacía o bloqueada por safety ({reason})")
        usage = response.usage_metadata
        return LLMResult(
            text=response.text,
            input_tokens=usage.prompt_token_count or 0,
            # Los tokens de thinking se facturan como salida.
            output_tokens=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
            latency_s=round(latency, 4),
            model=params.model,
        )
