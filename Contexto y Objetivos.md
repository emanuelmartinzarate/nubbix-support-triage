# Contexto y Objetivos

## Contexto

Eres un/a AI Engineer contratado/a por Nubbix, un SaaS de gestión para pymes de LATAM con 12.000 clientes. Su mesa de soporte recibe ~400 tickets por día, y el 60% son consultas repetitivas de cuatro tipos: facturación, problemas técnicos, gestión de cuenta y otros. El equipo de soporte de nivel 1 está saturado, el tiempo de primera respuesta se fue a 9 horas y los clientes se quejan.

Tu misión: automatizar el primer nivel de soporte con un servicio que recibe cada consulta en texto libre, la clasifica, propone una respuesta y sugiere acciones — con calidad medible, costos controlados y resistencia a usos maliciosos. Es un proyecto simple e independiente: no depende de ningún otro módulo.

## 🎯 Objetivos (qué vas a entregar y por qué importa)

- **Integrar LLMs por API** con al menos dos proveedores configurables (por ejemplo OpenAI y Anthropic), controlando costo, latencia y errores. Esto te obliga a construir una abstracción real, no un llamado hardcodeado a un solo proveedor.
- **Aplicar y justificar una técnica de context engineering**, con prompts versionados en archivos YAML fuera del código. La versión elegida se respalda con datos de evals, no con intuición.
- **Garantizar salidas estructuradas y validadas** (JSON Schema / Pydantic), con reintentos automáticos ante parsing inválido. Esto crea un contrato estable para quien consuma tu servicio.
- **Mitigar prompt injection** y aplicar moderación de entrada y salida.
- **Construir un dataset de evaluación y una suite de evals ejecutable**, con métricas globales y por categoría — así demostrás con números que tu sistema funciona, no con una demo manual.

**¿Por qué esto es importante?** Salidas estructuradas + métricas + decisiones de prompting documentadas y respaldadas por evals son habilidades centrales para construir sistemas de IA confiables, y son la base sobre la que vas a construir RAG en el Módulo 2.

## 📢 Consigna

Construir un servicio que recibe la consulta de un usuario en texto libre y devuelve una respuesta estructurada, segura y medida.

El servicio expone una CLI (interfaz de línea de comandos) que recibe la consulta y devuelve JSON validado con el contrato `{answer, confidence, category, actions}`, donde `category ∈ {billing, technical, account, other}` y `actions` es una lista de acciones sugeridas para el agente humano.

Cada ejecución registra tokens consumidos, latencia y costo. El proyecto incluye un dataset de evaluación etiquetado y una suite de evals que corre por comando y reporta score global y por categoría. La técnica de context engineering elegida debe estar documentada y justificada con resultados, no con opiniones.

**Bonus/opcional dentro de la consigna:** resistencia adversarial — una suite de 10 prompts maliciosos (injection, jailbreak, exfiltración del system prompt) documentados, con la mitigación aplicada y su efecto medido.
