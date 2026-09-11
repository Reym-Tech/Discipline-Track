"""Storage Adapters at the persistence Seam.

InMemory Adapter = the live DisciplineLedger itself (no code needed).
JsonFile Adapter = save_json / load_json below. The ledger never touches
files directly; it only exposes to_dict/from_dict.
"""
from __future__ import annotations

import json
import os

from src.ledger import DisciplineLedger

DEFAULT_PATH = os.path.join("data", "records.json")


def save_json(ledger: DisciplineLedger, path: str = DEFAULT_PATH) -> str:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger.to_dict(), fh, indent=2)
    return path


def load_json(path: str = DEFAULT_PATH) -> DisciplineLedger:
    if not os.path.exists(path):
        return DisciplineLedger()
    with open(path, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError:
            return DisciplineLedger()
    return DisciplineLedger.from_dict(data if isinstance(data, dict) else {})
