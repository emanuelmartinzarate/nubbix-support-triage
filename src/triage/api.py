"""API HTTP (FastAPI): capa fina sobre el mismo servicio que usa la CLI.

    uvicorn triage.api:app --port 8000
"""

from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from triage.config import ConfigError, Settings, load_settings
from triage.prompts import PromptNotFoundError
from triage.providers import get_provider
from triage.schema import TriageResponse
from triage.service import TriageError, triage

app = FastAPI(
    title="Nubbix Triage",
    description="Clasifica tickets de soporte y devuelve {answer, confidence, category, actions}.",
    version="0.1.0",
)


class TriageRequest(BaseModel):
    query: str = Field(min_length=1, description="Consulta del cliente en texto libre")
    provider: Literal["anthropic", "gemini"] | None = None
    prompt_version: str | None = None

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("la consulta no puede estar vacía")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
async def triage_endpoint(request: TriageRequest) -> TriageResponse:
    settings = get_settings()
    name = request.provider or settings.llm_provider
    try:
        provider = get_provider(name, settings)
        # El servicio es sincrónico (SDKs bloqueantes): se corre en un thread para no frenar el event loop.
        outcome = await run_in_threadpool(
            triage, request.query, settings, provider=provider, provider_name=name,
            prompt_version=request.prompt_version, source="api",
        )
    except (ConfigError, PromptNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TriageError as e:
        raise HTTPException(status_code=502, detail="No se pudo generar una respuesta válida") from e
    return outcome.response
