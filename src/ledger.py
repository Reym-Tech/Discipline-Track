"""DisciplineLedger: deep Module owning both indexes.

Interface (what callers learn):
  register_student(student_id, name, course="", parent_name="",
                   emergency_contact="") -> StudentRecord
  log_violation(student_id, violation_code, description="", reporter="",
                location="") -> Consequence
  get_student(student_id) -> StudentRecord | None
  audit_report(descending=False) -> [StudentRecord] ordered by (demerits, student_id)
  list_by_severity(min_demerits, descending=False) -> filtered ordered [StudentRecord]
  pending_cases() -> [StudentRecord] with workflow status, highest first
  approve_case(student_id, approved_by="Dean") -> StudentRecord
  schedule_meeting(student_id, meeting_date, parent_name="", emergency_contact="") -> StudentRecord
  save_counseling_note(student_id, note) -> StudentRecord
  sign_letter(student_id) -> StudentRecord
  to_dict() / from_dict() for persistence Adapters

Implementation (hidden): RBTree keyed by student_id for ingestion,
AVLTree keyed by (total_demerits, student_id) for audit. The same
StudentRecord object sits in both; on demerit change the AVL entry is
deleted under its old composite key and reinserted under the new one.

Workflow note: `status` intentionally diverges from `evaluate(total)`
once a case hits 5+ demerits ("Pending Disciplinary Review") and after
Dean approval ("Pending Disciplinary Meeting"). Filter routed queues by
`pending_cases()`, not by `status == "Expelled"`.
"""
from __future__ import annotations

from src.avl import AVLTree
from src.catalog import lookup
from src.consequences import evaluate
from src.models import (
    PENDING_MEETING,
    PENDING_REVIEW,
    Consequence,
    StudentRecord,
)


class DuplicateStudentError(ValueError):
    pass


class StudentNotFoundError(KeyError):
    pass


class DisciplineLedger:
    def __init__(self) -> None:
        from src.rbtree import RBTree

        self._rb: RBTree[int, StudentRecord] = RBTree()
        self._avl: AVLTree[tuple[int, int], StudentRecord] = AVLTree()

    # -- commands ------------------------------------------------------
    def register_student(
        self,
        student_id: int,
        name: str,
        course: str = "",
        parent_name: str = "",
        emergency_contact: str = "",
    ) -> StudentRecord:
        sid = int(student_id)
        if self._rb.search(sid) is not None:
            raise DuplicateStudentError(f"Student {sid} already registered")
        rec = StudentRecord(
            student_id=sid,
            name=name,
            course=course,
            parent_name=parent_name.strip(),
            emergency_contact=emergency_contact.strip(),
        )
        self._rb.insert(sid, rec)
        self._avl.insert((rec.total_demerits, sid), rec)
        return rec

    def log_violation(
        self,
        student_id: int,
        violation_code: str,
        description: str = "",
        reporter: str = "",
        location: str = "",
    ) -> Consequence:
        sid = int(student_id)
        rec = self._rb.search(sid)
        if rec is None:
            raise StudentNotFoundError(f"Student {sid} not found")
        label, points = lookup(violation_code)  # raises UnknownViolationError
        old_key = (rec.total_demerits, sid)
        rec.apply_violation(
            violation_code.strip().upper(),
            points,
            description or label,
            reporter=reporter,
            location=location,
        )
        self._avl.delete(old_key)
        self._avl.insert((rec.total_demerits, sid), rec)
        return evaluate(rec.total_demerits)

    def approve_case(self, student_id: int, approved_by: str = "Dean") -> StudentRecord:
        rec = self._rb.search(int(student_id))
        if rec is None:
            raise StudentNotFoundError(f"Student {student_id} not found")
        if rec.total_demerits < 5 and rec.status != PENDING_REVIEW:
            raise ValueError(f"Student {rec.student_id} is not expulsion-level (total {rec.total_demerits})")
        rec.status = PENDING_MEETING
        rec.dean_approved = True
        rec.approved_by = (approved_by or "Dean").strip() or "Dean"
        return rec

    def schedule_meeting(
        self,
        student_id: int,
        meeting_date: str,
        parent_name: str = "",
        emergency_contact: str = "",
    ) -> StudentRecord:
        rec = self._rb.search(int(student_id))
        if rec is None:
            raise StudentNotFoundError(f"Student {student_id} not found")
        rec.meeting_date = (meeting_date or "").strip()
        if parent_name:
            rec.parent_name = parent_name.strip()
        if emergency_contact:
            rec.emergency_contact = emergency_contact.strip()
        return rec

    def save_counseling_note(self, student_id: int, note: str) -> StudentRecord:
        rec = self._rb.search(int(student_id))
        if rec is None:
            raise StudentNotFoundError(f"Student {student_id} not found")
        rec.counseling_note = (note or "").strip()
        return rec

    def sign_letter(self, student_id: int) -> StudentRecord:
        rec = self._rb.search(int(student_id))
        if rec is None:
            raise StudentNotFoundError(f"Student {student_id} not found")
        rec.letter_signed = True
        return rec

    # -- queries -------------------------------------------------------
    def get_student(self, student_id: int) -> StudentRecord | None:
        return self._rb.search(int(student_id))

    def audit_report(self, descending: bool = False) -> list[StudentRecord]:
        rows = [rec for _, rec in self._avl.inorder()]
        if descending:
            rows.reverse()
        return rows

    def list_by_severity(
        self, min_demerits: int = 0, descending: bool = False
    ) -> list[StudentRecord]:
        rows = [rec for _, rec in self._avl.inorder() if rec.total_demerits >= min_demerits]
        if descending:
            rows.reverse()
        return rows

    def pending_cases(self) -> list[StudentRecord]:
        # Include legacy "Expelled" rows so pre-workflow JSON still routes.
        wanted = {PENDING_REVIEW, PENDING_MEETING, "Expelled"}
        rows = [rec for _, rec in self._avl.inorder() if rec.status in wanted]
        rows.reverse()  # highest demerits first for the Dean/Counselor queue
        return rows

    def __len__(self) -> int:
        return len(self._rb)

    # -- persistence surface (used by storage Adapters) ----------------
    def to_dict(self) -> dict:
        return {"records": [rec.to_dict() for _, rec in self._rb.inorder()]}

    @classmethod
    def from_dict(cls, data: dict) -> "DisciplineLedger":
        ledger = cls()
        for item in data.get("records", []):
            rec = StudentRecord.from_dict(item)
            ledger._rb.insert(rec.student_id, rec)
            ledger._avl.insert((rec.total_demerits, rec.student_id), rec)
        return ledger
