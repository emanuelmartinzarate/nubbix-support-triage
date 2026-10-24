# Entregables del proyecto y requisitos de entrega

Enviar mediante un enlace público al repositorio en Git. Asegurate de que el repositorio sea autocontenido y que se pueda ejecutar sin depender de elementos externos no documentados.

## 📂 Estructura de repositorio esperada

| Entregable | Archivo/Formato | Contenido mínimo |
|---|---|---|
| CLI de triage | `src/main.py` (o similar) | Acepta una consulta por línea de comandos; llama a un cliente LLM con ≥2 proveedores configurables; devuelve JSON validado con el contrato `{answer, confidence, category, actions}`; retry automático ante respuesta no parseable. |
| Prompts versionados | `prompts/*.yaml` | Al menos 2 versiones de prompt (ej. zero-shot, few-shot, chain-of-thought, con reglas de seguridad, etc.), documentadas y comparadas contra el dataset. |
| Dataset y suite de evals | `evals/dataset.jsonl` + `evals/runner.py` | Dataset de ≥30 casos etiquetados; runner ejecutable por comando (script simple, no framework de testing) con score global y por categoría. |
| Registro de métricas | `data/metrics.jsonl` | Log estructurado append-only por request: timestamp, tokens (prompt/completion/total), latencia (s) y costo estimado (USD). |
| Guardrails de seguridad | dentro de `src/` | Al menos un guardrail de entrada (moderación / detección de injection) y uno de salida (validación de contenido). |
| README | `README.md` | Setup y uso (con ejemplos de comando/respuesta), técnica de context engineering elegida y por qué, tabla de resultados de evals, decisiones técnicas. |
| Configuración | `.env.example`, `requirements.txt` | Variables de entorno documentadas (nunca credenciales reales); dependencias declaradas. |
| Seguridad adversarial (bonus) | `evals/adversarial.jsonl` + sección en el README | Suite de 10 prompts maliciosos documentados, con la mitigación aplicada y su efecto medido. |

## ✅ Checklist de entrega

- [ ] Claves de API cargadas por variable de entorno, nunca en el código. `src/main.py` incluido y versionado.
- [ ] Al menos una ejecución de la CLI registrada que produzca JSON válido y una línea de métricas.
- [ ] Suite de evals corrida y con resultados reflejados en el README.
- [ ] README y código consistentes entre sí: alguien que clone el repo debería poder instalarlo y correrlo sin preguntarte nada.
