"""DisciplineLedger: deep Module owning both indexes.

Interface (what callers learn):
  register_student(student_id, name, course="") -> StudentRecord
  log_violation(student_id, violation_code, description="") -> Consequence
  get_student(student_id) -> StudentRecord | None
  audit_report() -> [StudentRecord] ordered by (demerits, student_id)
  list_by_severity(min_demerits) -> filtered ordered [StudentRecord]
  to_dict() / from_dict() for persistence Adapters

Implementation (hidden): RBTree keyed by student_id for ingestion,
AVLTree keyed by (total_demerits, student_id) for audit. The same
StudentRecord object sits in both; on demerit change the AVL entry is
deleted under its old composite key and reinserted under the new one.
"""
from __future__ import annotations

from src.avl import AVLTree
from src.catalog import lookup
from src.consequences import evaluate
from src.models import Consequence, StudentRecord


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
    def register_student(self, student_id: int, name: str, course: str = "") -> StudentRecord:
        sid = int(student_id)
        if self._rb.search(sid) is not None:
            raise DuplicateStudentError(f"Student {sid} already registered")
        rec = StudentRecord(student_id=sid, name=name, course=course)
        self._rb.insert(sid, rec)
        self._avl.insert((rec.total_demerits, sid), rec)
        return rec

    def log_violation(
        self, student_id: int, violation_code: str, description: str = ""
    ) -> Consequence:
        sid = int(student_id)
        rec = self._rb.search(sid)
        if rec is None:
            raise StudentNotFoundError(f"Student {sid} not found")
        label, points = lookup(violation_code)  # raises UnknownViolationError
        old_key = (rec.total_demerits, sid)
        rec.apply_violation(violation_code.strip().upper(), points, description or label)
        self._avl.delete(old_key)
        self._avl.insert((rec.total_demerits, sid), rec)
        return evaluate(rec.total_demerits)

    # -- queries -------------------------------------------------------
    def get_student(self, student_id: int) -> StudentRecord | None:
        return self._rb.search(int(student_id))

    def audit_report(self) -> list[StudentRecord]:
        return [rec for _, rec in self._avl.inorder()]

    def list_by_severity(self, min_demerits: int = 0) -> list[StudentRecord]:
        return [rec for _, rec in self._avl.inorder() if rec.total_demerits >= min_demerits]

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
