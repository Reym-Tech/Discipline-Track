"""Seed a demo ledger and persist it via the JsonFile Adapter.

Usage:  python scripts/seed.py [path]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ledger import DisciplineLedger
from src.stores import save_json

SEED_STUDENTS = [
    (1001, "Ada Lovelace", "BSIT-1A"),
    (1002, "Bob Santos", "BSIT-1A"),
    (1003, "Cid Reyes", "BSIT-2B"),
    (1004, "Dana Cruz", "BSIT-2B"),
    (1005, "Eli Ramos", "BSIT-3A"),
    (1006, "Faye Aquino", "BSIT-3A"),
    (1007, "Gus Lim", "BSIT-1B"),
    (1008, "Hana Uy", "BSIT-1B"),
]

SEED_VIOLATIONS = [
    (1001, "SMOKE", "Smoking near lab"),
    (1002, "CUTTING", "Skipped IT lab"),
    (1002, "SMOKE", "No ID worn"),
    (1003, "CHEAT", "Quiz cheating"),
    (1004, "PLAGIARISM", "Copied lab output"),
    (1005, "HACK", "Portal probe attempt"),
    (1006, "NOID", "No ID worn"),
    (1007, "CUTTING", "Cutting class"),
    (1007, "CHEAT", "Quiz cheating"),
]


def build() -> DisciplineLedger:
    ledger = DisciplineLedger()
    for sid, name, course in SEED_STUDENTS:
        ledger.register_student(sid, name, course)
    for sid, code, desc in SEED_VIOLATIONS:
        ledger.log_violation(sid, code, desc)
    return ledger


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "records.json")
    ledger = build()
    save_json(ledger, path)
    print(f"Seeded {len(ledger)} students -> {path}")
    for r in ledger.audit_report():
        print(f"  {r.student_id} {r.name:<15} {r.total_demerits:>2} {r.status}")
