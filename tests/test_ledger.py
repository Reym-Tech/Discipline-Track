"""DisciplineLedger seam spec: the deep Module under test.

Callers cross only this Interface; AVL/RB sync is hidden Implementation.
"""
import pytest


def make_ledger():
    from src.ledger import DisciplineLedger

    return DisciplineLedger()


def test_register_and_lookup_by_id():
    ledger = make_ledger()
    ledger.register_student(1001, "Ada", "BSIT-1A")
    rec = ledger.get_student(1001)
    assert rec is not None and rec.name == "Ada"
    assert ledger.get_student(9999) is None


def test_register_duplicate_raises():
    from src.ledger import DuplicateStudentError

    ledger = make_ledger()
    ledger.register_student(1001, "Ada")
    with pytest.raises(DuplicateStudentError):
        ledger.register_student(1001, "Ada Again")


def test_log_violation_applies_consequence_and_status():
    ledger = make_ledger()
    ledger.register_student(1001, "Ada")
    consequence = ledger.log_violation(1001, "CHEAT")
    assert consequence.status == "Suspended"
    assert ledger.get_student(1001).total_demerits == 3
    assert ledger.get_student(1001).status == "Suspended"


def test_repeat_offender_escalates_to_expulsion():
    ledger = make_ledger()
    ledger.register_student(1002, "Bob")
    ledger.log_violation(1002, "SMOKE")  # 1 -> Warned
    assert ledger.get_student(1002).status == "Warned"
    ledger.log_violation(1002, "CUTTING")  # total 3 -> Suspended
    assert ledger.get_student(1002).status == "Suspended"
    ledger.log_violation(1002, "HACK")  # total 8 -> Expelled
    rec = ledger.get_student(1002)
    assert rec.total_demerits == 8
    assert rec.status == "Expelled"


def test_audit_report_is_ordered_by_demerits_then_id():
    ledger = make_ledger()
    ledger.register_student(1003, "Cid")
    ledger.register_student(1001, "Ada")
    ledger.register_student(1002, "Bob")
    ledger.log_violation(1003, "HACK")  # 5
    ledger.log_violation(1001, "SMOKE")  # 1
    # 1002 stays at 0
    ordered = [(r.student_id, r.total_demerits) for r in ledger.audit_report()]
    assert ordered == [(1002, 0), (1001, 1), (1003, 5)]


def test_list_by_severity_filters_and_stays_synced_after_update():
    ledger = make_ledger()
    for sid in (1001, 1002, 1003):
        ledger.register_student(sid, f"S{sid}")
    ledger.log_violation(1001, "SMOKE")  # 1
    ledger.log_violation(1002, "CHEAT")  # 3
    ledger.log_violation(1003, "HACK")  # 5
    severe = [r.student_id for r in ledger.list_by_severity(min_demerits=3)]
    assert severe == [1002, 1003]
    # Update 1001 from 1 -> 4 (PLAGIARISM); AVL key must move, no stale entry
    ledger.log_violation(1001, "CHEAT")  # total 4
    ordered = [(r.student_id, r.total_demerits) for r in ledger.audit_report()]
    assert ordered == [(1002, 3), (1001, 4), (1003, 5)]
    assert len(ordered) == len(set(sid for sid, _ in ordered)) == 3


def test_log_errors_for_unknown_student_and_code():
    from src.catalog import UnknownViolationError
    from src.ledger import StudentNotFoundError

    ledger = make_ledger()
    ledger.register_student(1001, "Ada")
    with pytest.raises(StudentNotFoundError):
        ledger.log_violation(9999, "SMOKE")
    with pytest.raises(UnknownViolationError):
        ledger.log_violation(1001, "NOPE")


def test_serialization_round_trip_preserves_both_indexes():
    ledger = make_ledger()
    ledger.register_student(1001, "Ada", "BSIT-1A")
    ledger.register_student(1002, "Bob", "BSIT-1B")
    ledger.log_violation(1001, "CHEAT")
    data = ledger.to_dict()
    from src.ledger import DisciplineLedger

    restored = DisciplineLedger.from_dict(data)
    assert restored.get_student(1001).total_demerits == 3
    assert [(r.student_id, r.total_demerits) for r in restored.audit_report()] == [
        (1002, 0),
        (1001, 3),
    ]
    assert [k for k, _ in restored._rb.inorder()] == [1001, 1002]
