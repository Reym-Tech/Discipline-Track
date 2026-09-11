"""Production entry point for hosted deployment (e.g. Render + Gunicorn).

Exposes the Flask Adapter over the ledger Interface; the host runs:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT
Records live in data/records.json (seeded demo ships with the repo).
"""
from src.web import create_app

app = create_app()
