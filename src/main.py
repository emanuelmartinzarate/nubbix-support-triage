"""Entrypoint de la CLI de triage: python src/main.py "consulta del cliente"."""

import sys

from triage.cli import main

if __name__ == "__main__":
    sys.exit(main())
