# Evaluación

La corrección se realiza mediante rúbrica, con niveles Excelente / Satisfactorio / Insuficiente por categoría. El puntaje mínimo de aprobación es 70/100; un puntaje de 81 a 100 se considera que supera lo esperado.

## Categorías evaluadas

- **Funcionalidad y contrato JSON** — cliente LLM multi-proveedor, cumplimiento del esquema Pydantic, retry ante errores de parsing, manejo de casos borde.
- **Suite de evals y dataset** — cobertura del dataset (≥30 casos), automatización del runner, claridad del reporte.
- **Context engineering y prompting** — versionado de prompts, comparativa empírica, selección respaldada por datos.
- **Seguridad y guardrails** — detección y mitigación de prompt injection / jailbreak, suite adversarial (si se aborda el bonus).
- **Observabilidad y métricas** — registro estructurado en JSONL con tokens, latencia y costo por request.
- **Repositorio, README y extra credits** — calidad y modularidad del código, documentación ejecutable, y al menos un extra credit (FastAPI, caché con hash MD5, LLM-as-judge en runtime o comparativa de modelos).
