# Diseño — Servicio de triage de soporte Nubbix (Proyecto Integrador M1)

Fecha: 2026-10-22
Documentos fuente (en la raíz del repo): `Contexto y Objetivos.md`, `Entregables del proyecto y requisitos de entrega.md`, `Evaluación.md`, `Guía para el desarrollo del proyecto integrador.md`, `Ejemplos ilustrativos de tickets.md`. Ante cualquier contradicción, mandan esos documentos.

## 1. Intención y por qué

Nubbix (SaaS de gestión para pymes LATAM, 12.000 clientes) recibe ~400 tickets/día; el 60% son repetitivos y el tiempo de primera respuesta llegó a 9 h. El servicio automatiza el nivel 1: recibe una consulta en texto libre y devuelve un JSON validado con una categoría, un borrador de respuesta y acciones sugeridas **para el agente humano** de soporte, que es quien lo consume.

El proyecto se aprueba demostrando con números (evals) que el sistema funciona, que los costos están controlados y que resiste usos maliciosos. La calidad del razonamiento de ingeniería documentado pesa tanto como el código.

Forma de trabajo: Claude escribe el código; el usuario (perfil de ingeniero de plataforma y arquitecto de soluciones) revisa las decisiones fase a fase. Cada decisión técnica relevante se explica en el README con criterio de AI Engineer.

## 2. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
- CLI que recibe una consulta y devuelve exactamente el contrato `{answer, confidence, category, actions}`.
- Abstracción multi-proveedor real: Anthropic y Gemini, intercambiables por configuración.
- Prompts versionados en YAML (≥3 versiones), elegidos con datos de evals.
- Validación Pydantic con reintento automático ante salida no parseable.
- Guardrails de entrada y salida en capas, más suite adversarial de 10 prompts (bonus) con efecto medido.
- Métricas por request en `data/metrics.jsonl`: tokens, latencia, costo auditable.
- Extra credits: FastAPI, caché MD5, comparativa de modelos/proveedores. LLM-as-judge solo si sobra margen.
- Ejecución por el evaluador con Docker Compose en pocos comandos, y también sin Docker con `pip`.

**No-objetivos**
- RAG, base de conocimiento de Nubbix, acceso a datos reales de clientes (es Módulo 2).
- Agentes con herramientas o bucles; frameworks de agentes (Google ADK, LangChain, LlamaIndex). Se evaluó ADK y se descartó: oculta la abstracción multi-proveedor que la rúbrica evalúa y agrega complejidad que la guía pide evitar.
- Bases de datos (SQLite incluida) para métricas: JSONL alcanza.
- Microservicios: una sola imagen Docker; compose solo define distintos modos de ejecución de esa imagen.

**Anti-objetivos (sería un fracaso aunque "funcione")**
- Credenciales en el código o en el historial de git.
- Elegir la versión de prompt por intuición, sin tabla de resultados.
- Un proveedor completo y el otro a medias.
- Números de costo que no se puedan recalcular a mano desde el log y la tabla de precios.
- Un "framework propio": capas genéricas, registros de plugins, inyección de dependencias elaborada.
- README que no coincide con el código o que exige preguntarle algo al autor.

## 3. Restricciones

- Python 3.12, `requirements.txt` (exigido por la consigna). SDKs oficiales `anthropic` y `google-genai`; Pydantic v2; PyYAML; python-dotenv; FastAPI + uvicorn para la API.
- Proveedores disponibles: **Anthropic y Gemini** (son las únicas keys que tiene el usuario).
- Modelos por defecto: los más chicos y baratos de cada proveedor (familia Claude Haiku; familia Gemini Flash), configurables por `.env`. El builder verifica los IDs vigentes y sus precios en la documentación oficial antes de cargarlos.
- **Fecha de entrega: 2026-11-09 a las 09:00** (decisión del usuario). La planificación apunta a tener las fases 0–7 completas con margen de unos días para la prueba desde un clon limpio y ajustes.
- **Cuentas pagas (con créditos de API) en Anthropic y Gemini** (decisión del usuario). `cost_usd` refleja el costo real facturable según la tabla de precios. Igual el runner maneja 429 con backoff, y una concurrencia baja configurable (default secuencial o 2–4 en paralelo) para no chocar con los rate limits de los tiers iniciales.
- **Presupuesto: tope duro de USD 2 por corrida completa de evals** (decisión del usuario), configurable con `EVAL_MAX_COST_USD`. *Decisión de Claude:* el tope aplica a cada invocación del runner, y el conjunto de corridas que alimentan el README (matriz 3 prompts × 2 proveedores, suite adversarial sin y con mitigación, pasada de falsos positivos con moderación) se planifica para que en total entre en unos USD 2. La caché evita volver a pagar lo que no cambió.
- El runner de evals es un script simple (`python -m evals.runner` o `python evals/runner.py`), no pytest ni un framework de evals.
- Tests unitarios con pytest para la lógica propia (validación, guardrails, costo, caché) están permitidos y son deseables; el runner de evals es lo que no puede ser pytest.
- Repo git público y autocontenido; `.gitignore` excluye `.env`, `.venv`, `__pycache__` y la caché.
- Idioma de la documentación y de los prompts: español rioplatense/neutro LATAM, como los tickets.

## 4. Decisiones tomadas

### 4.1 Contrato de salida (estable, no cambia)

```python
class TriageResponse(BaseModel):
    answer: str          # borrador de respuesta al cliente, no vacío
    confidence: float    # 0.0–1.0
    category: Literal["billing", "technical", "account", "other"]
    actions: list[str]   # acciones sugeridas para el agente humano, 1–5 ítems no vacíos
```

- Con `extra="forbid"`: el modelo no puede agregar campos.
- La CLI imprime **solo** ese JSON por stdout (consumible por otro sistema sin transformar). Diagnóstico, avisos de guardrails y errores van a stderr y a `metrics.jsonl`.
- La API FastAPI devuelve el mismo contrato en `POST /triage`.
- *Decisión de Claude:* cuando un guardrail de entrada bloquea la consulta, igual se devuelve un contrato válido: `category: "other"`, `confidence: 0.0`, un `answer` neutro que no revela nada del sistema y `actions` con `"Revisión manual: posible intento de manipulación (<motivo>)"`. Así el consumidor nunca recibe una forma distinta. El motivo detallado queda en el log.
- *Decisión de Claude:* si se agotan los reintentos de parsing, la CLI termina con código de salida ≠ 0, un mensaje de error en stderr y nada en stdout; el fallo se registra en métricas.

### 4.2 Abstracción multi-proveedor

- Interfaz mínima `LLMProvider` con un método del estilo `complete(system, messages, params) -> LLMResult`, donde `LLMResult` trae texto, tokens de entrada/salida, latencia y modelo.
- Un adaptador por proveedor (`AnthropicProvider`, `GeminiProvider`). La lógica de negocio (triage, validación, guardrails) no importa ningún SDK.
- Selección por `--provider` / `LLM_PROVIDER` y `--model` / variables por proveedor.
- Errores transitorios (429, 5xx, timeouts) con reintento y backoff exponencial con jitter y un máximo de intentos; errores no recuperables (auth, request inválido) fallan rápido con un mensaje claro.
- Parámetros deliberados y documentados: `temperature` baja (≈0–0.2) para clasificación estable; `max_tokens` acotado al tamaño del contrato.

### 4.3 Salida estructurada y reintento

- Se pide JSON explícitamente en el prompt y, donde el proveedor lo soporte de forma nativa (JSON mode / schema en Gemini, tool use o salida estructurada en Anthropic), se usa además. El builder decide el mecanismo nativo exacto por proveedor, pero **la validación Pydantic siempre se aplica** igual: nunca se confía en el proveedor.
- Reintento de parsing: ante JSON inválido o error de esquema, se reintenta hasta N veces (default 2) **agregando a la conversación el error de validación** para que el modelo se corrija. Cada intento cuenta tokens y costo.
- Se toleran envoltorios comunes (bloques ```json) antes de validar.

### 4.4 Context engineering y prompts

- `prompts/v1_zero_shot.yaml`, `prompts/v2_few_shot.yaml`, `prompts/v3_few_shot_rules.yaml` (nombres a criterio del builder). Cada YAML tiene: `id`, `version`, `description`, `technique`, `system`, `user_template` y, si corresponde, `examples`.
- v1: instrucciones + definición de categorías. v2: + ejemplos few-shot (que **no** se repiten en el dataset de eval, para no contaminar la medición). v3: + criterios explícitos de desempate entre categorías, reglas de seguridad (tratar el texto del usuario como dato, delimitado) y guía de calibración de `confidence`.
- **Regla de desempate para tickets con varios temas (decisión del usuario):** gana la categoría del tema que **bloquea la operación del cliente** (normalmente `technical`), y el otro tema aparece como acción en `actions`. Por ejemplo, "se cayó la integración con Mercado Pago y me cobraron doble" se etiqueta `technical` y lleva una acción para revisar el doble cobro. Esta regla se fija **antes** de etiquetar el dataset, y la usan tanto las etiquetas como el prompt v3.
- La versión elegida se decide con la comparativa 3 versiones × 2 proveedores: **criterio principal accuracy macro por categoría**, después tasa de JSON válido al primer intento, después costo y latencia. El README muestra la tabla y el razonamiento, incluido lo que falló.
- La versión de prompt activa se elige por `--prompt` / `PROMPT_VERSION`.

### 4.5 Dataset y runner de evals

- `evals/dataset.jsonl`: ~40 casos (≥30 exigidos), unos 10 por categoría, con campos como `id`, `query`, `expected_category`, `notes`/`tags` (por ejemplo `ambiguous`, `multi-topic`, `informal`, `typos`, `edge`).
- Cobertura: tono real (informal, sin tildes, con urgencia), casos ambiguos entre categorías, consultas con dos temas, muy cortas o muy largas, mezcla con inglés/portugués, y alguna entrada vacía o sin sentido. Los ejemplos del enunciado son solo referencia de tono; no se copian.
- Lo genera Claude con asistencia de IA (se documenta) y lo revisa el usuario antes de usarlo para decidir.
- `evals/runner.py` reporta: accuracy global y por categoría (más una matriz de confusión simple), tasa de JSON válido y de reintentos, latencia p50/p95, tokens y costo total. Imprime una tabla legible y guarda un resultado en `evals/results/` (JSON o Markdown) para copiarlo al README.
- Flags: `--provider`, `--prompt`, `--limit N`, `--all` (matriz completa de prompts × proveedores), `--no-cache`.
- Tope de costo: suma el costo real request a request y **aborta limpio** al superar `EVAL_MAX_COST_USD` (default 2.0), reportando lo que alcanzó a correr.
- Caché MD5 sobre (proveedor, modelo, versión de prompt, parámetros, consulta). Vive en `data/cache/` y no se versiona. Un hit no gasta tokens y se registra en métricas como hit con costo 0.

### 4.6 Métricas

- `data/metrics.jsonl`, append-only, una línea por request: `timestamp` (ISO 8601 UTC), `request_id`, `provider`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `total_tokens`, `latency_s`, `cost_usd`, `attempts`, `cache_hit`, `guardrail` (resultado), `status` (`ok`, `blocked` o `error`), `source` (`cli`, `api` o `eval`).
- Costo = tokens × precio de `src/.../pricing.yaml` (o equivalente versionado), con la fecha y la URL de la fuente de cada precio. Cualquiera puede recalcular el número a mano.
- `data/metrics.jsonl` se versiona con al menos una ejecución real de la CLI (requisito del checklist).

### 4.7 Seguridad y guardrails (en capas)

- **Entrada, capa 1 (determinística, gratis):** normalización (minúsculas, sin acentos, unicode y espacios raros, decodificación básica de base64) y detección por patrones de injection, jailbreak y pedido del system prompt, en español e inglés. También límite de longitud.
- **Entrada, capa 2 (moderación):** clasificación de contenido dañino o abusivo. Anthropic no tiene endpoint de moderación, así que el builder elige entre una llamada barata de clasificación con el modelo chico o los filtros de seguridad de Gemini. Debe ser activable por configuración, y su costo y efecto se miden en la suite adversarial.
- **Prompt (capa 3):** el texto del usuario va delimitado y se declara como dato no confiable; el system prompt incluye reglas de no revelarse ni cambiar de rol (v3).
- **Salida (capa 4):** validación de esquema, detección de fuga del system prompt (con un *canary token* en el prompt y similitud con fragmentos del system) y reglas de contenido (por ejemplo, que `answer` no prometa reintegros o acciones irreversibles en nombre de Nubbix y no incluya instrucciones ajenas al soporte).
- `evals/adversarial.jsonl`: 10 casos (injection directa e indirecta, jailbreak de rol, exfiltración del system prompt, ofuscación, cambio de idioma, payload en base64, "ignorá lo anterior" incrustado en un ticket legítimo, etc.). Se mide la **tasa de ataques exitosos sin y con mitigaciones** (por capa, si es viable) y la tasa de falsos positivos sobre el dataset legítimo. Todo eso va a una sección del README.

### 4.8 Plataforma

- Una imagen Docker (Python 3.12-slim, usuario no root).
- `docker-compose.yml` con servicios que reutilizan la imagen: `api` (uvicorn, puerto expuesto), `cli` y `evals` (para `docker compose run --rm`). `data/` montado como volumen. `.env` por `env_file`.
- FastAPI: `POST /triage` (body `{query, provider?, prompt_version?}`, responde el contrato) y `GET /health`. Comparte toda la lógica con la CLI; la API es una capa fina.
- Camino sin Docker documentado: `python -m venv`, `pip install -r requirements.txt`, `cp .env.example .env`.

### 4.9 Proceso

- Fases en orden; cada una termina en algo que funciona y en commits chicos con mensajes convencionales (`feat:`, `fix:`, `docs:`):
  0) Base y estructura · 1) Flujo mínimo con Anthropic y v1 · 2) Gemini, reintentos y errores · 3) Dataset y runner con tope, caché y `--limit` · 4) Prompts v2/v3 y comparativa · 5) Guardrails y suite adversarial · 6) FastAPI y Docker · 7) README final y prueba desde un clon limpio.
- No se avanza a extra credits (fase 6) sin las fases 1–5 funcionando.
- Mientras se itera, se usa `--limit`; la corrida completa (dentro del tope de USD 2) se usa para los números finales.
- El README incluye una sección "Uso de IA en el desarrollo" con los prompts usados y cómo influyeron.

## 5. Queda a criterio del builder

- El layout interno de `src/` (nombres de módulos y paquete), siempre que se separen cliente LLM, validación, guardrails, métricas y prompts.
- El mecanismo nativo de salida estructurada por proveedor y la librería o implementación de backoff.
- Los patrones exactos de detección de injection y el umbral de similitud para detectar fugas.
- El formato exacto del reporte del runner y del archivo de resultados.
- Los ejemplos few-shot concretos y el texto de los prompts.
- La herramienta de lint o formato (opcional).
- Si suma LLM-as-judge para la calidad de `answer` (solo si las fases 1–7 están completas antes de unos 3 días del deadline del 2026-11-09 y el presupuesto lo permite).
- El idioma de `answer` ante tickets en inglés o portugués (*decisión de Claude por defecto*: responder en el idioma del ticket).
