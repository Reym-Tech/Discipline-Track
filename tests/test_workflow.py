"""End-to-end proposal flow: Guard -> Dean -> Guidance.

Seam under test: DisciplineLedger Interface + HTTP case endpoints.
"""
from src.ledger import DisciplineLedger


def _john_at_4():
    ledger = DisciplineLedger()
    ledger.register_student(63326, "John Doe", "BSIT-1A",
                            parent_name="Jane Doe", emergency_contact="+63-900-000-0000")
    ledger.log_violation(63326, "PLAGIARISM", "Prior coding plagiarism")
    assert ledger.get_student(63326).total_demerits == 4
    return ledger


def test_guard_noid_pushes_4_to_5_pending_review():
    ledger = _john_at_4()
    consequence = ledger.log_violation(
        63326, "NOID", "No ID",
        reporter="Guard Ramos", location="campus entrance gate",
    )
    rec = ledger.get_student(63326)
    assert rec.total_demerits == 5
    assert consequence.status == "Expelled"  # matrix recommendation stays pure
    assert rec.status == "Pending Disciplinary Review"  # overwrite decision
    assert rec.history[-1].reporter == "Guard Ramos"
    assert rec.history[-1].location == "campus entrance gate"


def test_descending_audit_puts_highest_first():
    ledger = DisciplineLedger()
    ledger.register_student(1, "Low")
    ledger.register_student(63326, "John Doe")
    ledger.log_violation(63326, "HACK")
    asc = [(r.student_id, r.total_demerits) for r in ledger.audit_report()]
    desc = [(r.student_id, r.total_demerits) for r in ledger.audit_report(descending=True)]
    assert asc[0][1] <= asc[-1][1]
    assert desc[0][1] >= desc[-1][1]
    assert desc[0][0] == 63326


def test_dean_approve_moves_to_pending_meeting():
    ledger = _john_at_4()
    ledger.log_violation(63326, "NOID", "No ID", reporter="Guard Ramos")
    rec = ledger.approve_case(63326, approved_by="Dean")
    assert rec.status == "Pending Disciplinary Meeting"
    assert rec.dean_approved is True
    assert ledger.pending_cases()[0].student_id == 63326


def test_guidance_schedules_meeting_and_letter():
    ledger = _john_at_4()
    ledger.log_violation(63326, "NOID", "No ID", reporter="Guard Ramos")
    ledger.approve_case(63326)
    ledger.schedule_meeting(63326, "2026-09-15 10:00",
                            parent_name="Jane Doe", emergency_contact="+63-900-000-0000")
    ledger.save_counseling_note(63326, "Exit interview: transfer guidance given.")
    ledger.sign_letter(63326)
    rec = ledger.get_student(63326)
    assert rec.meeting_date == "2026-09-15 10:00"
    assert "transfer" in rec.counseling_note
    assert rec.letter_signed is True
    letter = rec.expulsion_letter()
    assert "John Doe" in letter and "63326" in letter


def test_serialization_preserves_workflow_fields():
    ledger = _john_at_4()
    ledger.log_violation(63326, "NOID", "No ID", reporter="Guard Ramos")
    ledger.approve_case(63326)
    restored = DisciplineLedger.from_dict(ledger.to_dict())
    rec = restored.get_student(63326)
    assert rec.status == "Pending Disciplinary Meeting"
    assert rec.history[-1].reporter == "Guard Ramos"
    assert restored.pending_cases()[0].student_id == 63326
