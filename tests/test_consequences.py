"""Behaviour spec for ConsequenceEngine + ViolationCatalog + models.

Seams under test:
  - src.catalog.lookup(code)
  - src.consequences.evaluate(total)
These are pure in-process Modules: no I/O, no Adapters.
Expected values are literals from the project spec, not recomputed.
"""
import pytest

from src.catalog import UnknownViolationError, lookup
from src.consequences import evaluate


def test_catalog_known_codes_return_label_and_points():
    label, points = lookup("CHEAT")
    assert points == 3
    assert "dishonesty" in label.lower() or "cheat" in label.lower()


def test_catalog_all_spec_codes():
    # Independent truth table from spec §6
    assert lookup("SMOKE")[1] == 1
    assert lookup("NOID")[1] == 1
    assert lookup("CUTTING")[1] == 2
    assert lookup("CHEAT")[1] == 3
    assert lookup("PLAGIARISM")[1] == 4
    assert lookup("HACK")[1] == 5


def test_catalog_unknown_code_raises():
    with pytest.raises(UnknownViolationError):
        lookup("NOPE")


def test_consequence_matrix_statuses():
    # Spec §6: literal expectations
    assert evaluate(0).status == "Good Standing"
    assert evaluate(1).status == "Warned"
    assert evaluate(2).status == "Probation"
    assert evaluate(3).status == "Suspended"
    assert evaluate(4).status == "Lab Banned"
    assert evaluate(5).status == "Expelled"
    assert evaluate(9).status == "Expelled"  # 5+ saturates


def test_consequence_matrix_sanctions_mention_key_phrases():
    assert "warning" in evaluate(1).sanction.lower()
    assert "parent" in evaluate(2).sanction.lower()
    assert "suspension" in evaluate(3).sanction.lower()
    assert "fail" in evaluate(4).sanction.lower() or "ban" in evaluate(4).sanction.lower()
    assert "expul" in evaluate(5).sanction.lower()


def test_student_record_totals_and_history():
    from src.models import StudentRecord

    s = StudentRecord(student_id=1001, name="Ada", course="BSIT-1A")
    assert s.total_demerits == 0
    assert s.status == "Good Standing"
    s.apply_violation("CHEAT", 3, "Quiz cheating")
    assert s.total_demerits == 3
    assert s.status == "Suspended"
    assert len(s.history) == 1
