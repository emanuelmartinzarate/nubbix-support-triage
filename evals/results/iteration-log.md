# Log de iteración de prompts

Dataset: `evals/dataset.jsonl` (40 casos, 10 por categoría, etiquetas revisadas por el usuario).
Modelos: `claude-haiku-5-5` (Anthropic) y `gemini-3.8-flash` (Gemini). Criterio de selección
(definido en el diseño **antes** de correr): macro accuracy → JSON válido al 1er intento → costo → latencia.

## Versiones comparadas

| Versión | Técnica | Hipótesis |
|---|---|---|
| v1 | zero-shot | Línea base: instrucciones + definición de categorías. |
| v2 | few-shot (8 ejemplos, 2 por categoría) | Los ejemplos mejoran consistencia de formato y casos ambiguos sin reglas explícitas. |
| v3 | few-shot + reglas explícitas | Criterios de desempate (regla del tema que bloquea la operación), guía de calibración de `confidence`, guía de `actions` y reglas anti-injection. |

## Corrida 1 (2026-10-23, `--all --no-cache`, USD 0.1864)

Solo accuracy y costo (la métrica de calibración se agregó después; ver abajo). Salida de consola en `run-1-console.log`.

| Proveedor | v1 | v2 | v3 |
|---|---|---|---|
| anthropic | 100% | 100% | 100% |
| gemini | 95% (fallos: tec-03, oth-06) | 98% (fallo: tec-03) | 100% |

**Qué aprendimos:**
1. La accuracy de Anthropic está **saturada** (100% en las tres versiones): con 40 casos la categoría sola no discrimina prompts en ese modelo.
2. El caso que separa versiones es **tec-03** ("se cayó la integración con Mercado Pago y encima me cobraron doble"): es exactamente la regla de desempate multi-tema. v1/v2 lo mandan a `billing`; solo v3, que tiene la regla explícita, lo resuelve.
3. Few-shot (v2/v3) bajó los tokens de salida a la mitad (~12.6k → ~6.3k en Anthropic) y la latencia p50 (~2.6 s → ~1.6 s): los ejemplos enseñan respuestas más concisas.

**Cambio:** se agregó al runner la métrica de **calibración de confianza** (confianza media en casos claros vs. ambiguos/multi-tema/cortos/sin sentido) para tener señal más allá de la categoría. Para que todos los números del README salgan de una sola corrida reproducible, se volvió a correr la matriz completa (los JSON de la corrida 1 se descartaron; queda su salida de consola).

## Corrida 2 (2026-10-23, `--all --no-cache`, USD 0.1842) — la que va al README

Ver `comparison.md` y los JSON de `evals/results/`.

| Proveedor | Prompt | Macro acc. | Fallos | JSON 1er intento | Brecha de confianza (claros − ambiguos) | p50 | Costo |
|---|---|---|---|---|---|---|---|
| anthropic | v1 | 100% | — | 98% | 0.13 | 2.57 s | 0.0102 |
| anthropic | v2 | 98% | tec-03 | 100% | 0.10 | 1.56 s | 0.0121 |
| anthropic | v3 | 100% | — | 100% | 0.14 | 1.65 s | 0.0149 |
| gemini | v1 | 98% | oth-06 | 100% | 0.03 | 3.42 s | 0.0342 |
| gemini | v2 | 95% | tec-03, oth-06 | 100% | 0.06 | 2.97 s | 0.0493 |
| gemini | v3 | 100% | — | 100% | 0.16 | 2.63 s | 0.0636 |

**Variabilidad entre corridas:** tec-03 falló en v2 de Anthropic en la corrida 2 pero no en la 1, y en v1 de Gemini al revés. Haiku 5.5 no admite `temperature` (la API 2026-10-21 lo rechaza) y Gemini con `temperature=0` igual varía: los casos de borde son **no deterministas** sin una regla explícita. v3 es la única versión sin fallos en **las dos corridas y los dos proveedores**.

## Decisión: v3 (few-shot + reglas explícitas)

1. **Macro accuracy (criterio principal):** v3 es la única con 100% en ambos proveedores y en ambas corridas (4/4). v1 y v2 fallan de forma intermitente justo en el caso multi-tema.
2. **JSON válido al 1er intento:** 100% en ambos proveedores (v1 tuvo un reintento en Anthropic).
3. **Calibración:** v3 tiene la mayor brecha de confianza en ambos proveedores (0.14 y 0.16): baja la confianza cuando el ticket es ambiguo, que es lo que necesita el agente humano para saber cuándo revisar con más cuidado. Gemini v1 casi no discrimina (0.03).
4. **Costo:** v3 es la más cara por los ejemplos y las reglas (~1.5× v1 en Anthropic, ~1.9× en Gemini), pero en valores absolutos es ~USD 0.0004 (Haiku) y ~USD 0.0016 (Gemini) por ticket: para ~400 tickets/día son ~USD 0.15 o ~USD 0.64 por día. El costo no compensa la pérdida de precisión en los casos multi-tema.
5. **Seguridad:** v3 además incluye las reglas anti-injection que se miden en la suite adversarial (Task 13).

**Limitaciones:** 40 casos dan una resolución de 2.5 puntos de accuracy global por caso (y 10 puntos por categoría, con 10 casos cada una); la accuracy está cerca del techo y las diferencias entre v1/v2/v3 dependen de pocos casos. Lo que sostiene la decisión es la consistencia de v3 en el caso que la regla está diseñada para resolver, sumada a la calibración.
