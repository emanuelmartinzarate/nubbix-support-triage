# Guía para el desarrollo del proyecto integrador

## Propósito de esta guía

Esta guía te acompaña en el desarrollo del Proyecto Integrador de AI Engineering correspondiente al Módulo 1. No reemplaza la consigna ni define pasos obligatorios: te orienta para que puedas organizarte, priorizar correctamente y evitar errores comunes.

El foco está en ayudarte a construir un MVP funcional, claro y bien documentado, alineado con los estándares esperados para un perfil Junior en AI Engineering.

## Qué se espera del proyecto

Se espera que desarrolles una aplicación que integre LLMs a través de su API, aplicando lo aprendido en el módulo, y que cumpla con los requisitos definidos en la consigna oficial.

Más allá de la cantidad de funcionalidades, se valorará especialmente:

- Que la CLI funcione correctamente de punta a punta.
- Que el código sea legible, modular y esté bien organizado.
- Que el proyecto esté versionado con Git.
- Que las decisiones de prompting, de proveedor y de diseño estén documentadas y justificadas.
- Que la documentación permita entender y ejecutar la aplicación sin ayuda externa.

## Cómo orientar el desarrollo

### Antes de escribir código

- Lee la consigna completa.
- Asegurate de entender qué problema resuelve el servicio y quién lo va a usar (el agente de soporte de Nubbix).
- Identificá las funcionalidades mínimas obligatorias y las opcionales (extra credits).
- Definí una estructura simple de archivos (`src/`, `prompts/`, `evals/`, `data/`) antes de empezar a programar.
- Pensá cómo vas a gestionar credenciales de ambos proveedores desde el inicio, para no tener que refactorizar después.

### Durante el desarrollo

- Priorizá que el flujo principal funcione antes de pulir detalles: una consulta por CLI que devuelva un JSON válido ya es un punto de partida sólido.
- Implementá primero el caso más simple (un proveedor, un prompt) y después sumá el segundo proveedor y las versiones adicionales de prompt.
- Tratá tus prompts como código: probalos, ajustalos e iterá. La primera versión rara vez es la mejor — por eso el proyecto pide comparar al menos 2 versiones con datos.
- Probá la CLI con entradas variadas (incluidas ambiguas) para validar que la salida se mantiene consistente.
- Hacé commits pequeños y descriptivos.

### Al finalizar

- Revisá que la CLI funcione sin errores en una ejecución limpia, idealmente desde un clon nuevo del repositorio.
- Verificá que la salida sea consumible por otro sistema sin transformaciones adicionales.
- Asegurate de que el README explique claramente cómo instalar, configurar y ejecutar el proyecto.
- Confirmá que las credenciales sensibles no queden expuestas en el repositorio.

## Buenas prácticas recomendadas

### Prompt Engineering

- Elegí conscientemente la técnica de prompting que vas a usar y dejá documentado por qué la elegiste para tu caso.
- Tratá el prompt como una hipótesis: probá al menos 2 versiones y compará resultados contra tu dataset antes de decidir.
- Sé explícito en tus instrucciones. Cuanto más concreto sea el prompt, menos margen tendrá el modelo para improvisar.
- Versioná cada prompt en su propio archivo YAML, nunca hardcodeado en el código.
- Dejá evidencia de tu proceso de iteración en el README: qué probaste, qué falló y por qué te quedaste con la versión final.

### Salida estructurada

- Trabajá con la idea de contrato: `{answer, confidence, category, actions}` no cambia a lo largo del proyecto.
- Sé consistente en el naming y en los tipos de datos.
- Validá la salida con Pydantic antes de confiar en ella.
- Definí una estrategia de reintento clara para cuando el modelo no respeta el contrato — no asumas que siempre lo va a respetar.

### Integración con la API (multi-proveedor)

- Las credenciales nunca van en el código. Cargalas desde variables de entorno y documentá cuáles hacen falta en `.env.example`.
- Construí una abstracción mínima (`LLMProvider` o similar) que te permita cambiar de proveedor sin tocar la lógica de negocio.
- Configurá los parámetros de la llamada (modelo, temperature, límites de tokens) de forma deliberada y dejá registro de por qué elegiste esos valores.
- Manejá rate limits y errores de API de forma explícita, no dejes que la CLI se caiga ante un error transitorio.

### Observabilidad

- Registrá tus métricas en `data/metrics.jsonl` (formato append-only, una línea por request). Si una métrica no responde una pregunta concreta de costo, latencia o consumo, sobra.
- Asegurate de que el costo estimado sea reproducible y auditable: alguien debería poder revisar tus números y llegar al mismo resultado.
- No uses SQLite ni una base de datos para esto — JSONL alcanza y evita complejidad innecesaria en este módulo.

### Seguridad

- Pensá en capas: un solo guardrail de entrada suele ser fácil de evadir.
- Documentá con un ejemplo concreto cómo se comporta tu sistema frente a una entrada adversarial: qué detectaste, qué decisión tomó el sistema y por qué.
- Si abordás el bonus, una buena defensa no se rompe con variaciones triviales del ataque.

### Calidad del código

- Separá responsabilidades en funciones pequeñas: cliente LLM, validación, guardrails y métricas no deberían vivir todos en el mismo archivo.
- Usá nombres que expliquen la intención.
- Si encontrás lógica repetida, extraela.
- No armes un framework propio: la complejidad va al prompt y a los evals, no a la arquitectura ni a las herramientas (el runner de evals es un script simple, no pytest ni un framework de testing).

### Documentación

- Tu README es la primera impresión del proyecto. Debe permitir que alguien más lo entienda, lo instale y lo ejecute sin necesidad de preguntarte nada.
- Explicá las decisiones técnicas clave: qué técnica de prompting usaste y por qué, por qué elegiste esos proveedores, qué limitaciones tiene tu solución.
- Mantené la documentación sincronizada con el código.

### Git y GitHub

- Usá mensajes de commit claros (por ejemplo: `feat: agregar registro de métricas`).
- Versioná el proyecto desde el inicio.
- Verificá que el repositorio sea público y autocontenido.
- Configurá el repositorio para no subir credenciales, archivos locales ni dependencias instaladas.

## Errores comunes a evitar

- Saltar a los extra credits antes de tener el flujo principal funcionando.
- Dejar credenciales sensibles dentro del código fuente.
- Asumir que el modelo siempre va a respetar el contrato JSON, sin validar la salida.
- Construir un prompt único, sin versionar ni comparar su rendimiento.
- Registrar métricas sin que sea posible verificar de dónde salieron los números.
- Implementar un solo proveedor y dejar la abstracción multi-proveedor a medias.
- No probar el proyecto en una ejecución limpia antes de entregarlo.

## Sobre el uso de IA

Podés utilizar herramientas de IA como apoyo durante el desarrollo, siguiendo lo aprendido en el módulo. Documentá los prompts que usaste y explicá cómo influyeron en las decisiones técnicas del proyecto. El objetivo del Proyecto Integrador es demostrar tu comprensión sobre cómo se construye un sistema con LLMs, no delegar esa comprensión a otra herramienta.

## Cierre

Esta guía está pensada para ayudarte a tomar buenas decisiones técnicas y de organización. El objetivo final es que puedas demostrar que comprendés el flujo completo de integración con LLMs — desde el cliente multi-proveedor y el diseño del prompt hasta la observabilidad y la seguridad de tu sistema — y que podés entregar una solución funcional, robusta y bien presentada.
