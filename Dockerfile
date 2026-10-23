FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias primero: esta capa se reutiliza mientras no cambien requirements/pyproject.
COPY requirements.txt pyproject.toml ./
COPY src/ src/
RUN pip install -r requirements.txt

COPY prompts/ prompts/
COPY evals/ evals/

RUN useradd --create-home --uid 1000 app && mkdir -p data && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

CMD ["uvicorn", "triage.api:app", "--host", "0.0.0.0", "--port", "8000"]
