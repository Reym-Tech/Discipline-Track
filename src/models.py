"""StudentRecord: plain data Module. No tree logic lives here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ViolationEntry:
    code: str
    points: int
    description: str
    reporter: str = ""
    location: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _utcnow_iso()


@dataclass
class Consequence:
    status: str
    sanction: str


# Workflow statuses deliberately overwrite the demerit matrix value
# (per approved proposal). `evaluate(total)` stays pure; the record's
# `status` may diverge to one of these after logging/approval.
PENDING_REVIEW = "Pending Disciplinary Review"
PENDING_MEETING = "Pending Disciplinary Meeting"


@dataclass
class StudentRecord:
    student_id: int
    name: str
    course: str = ""
    total_demerits: int = 0
    status: str = "Good Standing"
    history: list = field(default_factory=list)
    # Phase 3 coordination (Guidance Office). All optional so old JSON loads.
    parent_name: str = ""
    emergency_contact: str = ""
    meeting_date: str = ""
    counseling_note: str = ""
    dean_approved: bool = False
    approved_by: str = ""
    letter_signed: bool = False

    def apply_violation(
        self,
        code: str,
        points: int,
        description: str,
        reporter: str = "",
        location: str = "",
        created_at: str = "",
    ) -> None:
        from src.consequences import evaluate

        self.history.append(
            ViolationEntry(
                code=code,
                points=points,
                description=description,
                reporter=reporter.strip(),
                location=location.strip(),
                created_at=created_at or _utcnow_iso(),
            )
        )
        self.total_demerits += points
        consequence = evaluate(self.total_demerits)
        self.status = consequence.status
        # Phase 1 Guard Post rule: expulsion-level cases route to the Dean.
        if self.total_demerits >= 5:
            self.status = PENDING_REVIEW
            self.dean_approved = False

    def expulsion_letter(self) -> str:
        lines = [
            "IT DEPARTMENT — OFFICIAL EXPULSION NOTICE",
            f"Student: {self.name} (ID {self.student_id}, {self.course or 'no course'})",
            f"Total demerits: {self.total_demerits} | Status: {self.status}",
            "Violation history:",
        ]
        for h in self.history:
            who = f" [reported by {h.reporter}]" if getattr(h, "reporter", "") else ""
            lines.append(f"  - {h.code} +{h.points}: {h.description}{who}")
        if self.meeting_date:
            lines.append(f"Disciplinary conference: {self.meeting_date}")
        if self.parent_name or self.emergency_contact:
            lines.append(f"Parent/guardian: {self.parent_name or '-'} ({self.emergency_contact or 'no contact'})")
        lines.append("Dean signature: ____________________   Date: __________")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "name": self.name,
            "course": self.course,
            "total_demerits": self.total_demerits,
            "status": self.status,
            "parent_name": self.parent_name,
            "emergency_contact": self.emergency_contact,
            "meeting_date": self.meeting_date,
            "counseling_note": self.counseling_note,
            "dean_approved": self.dean_approved,
            "approved_by": self.approved_by,
            "letter_signed": self.letter_signed,
            "history": [
                {
                    "code": h.code,
                    "points": h.points,
                    "description": h.description,
                    "reporter": getattr(h, "reporter", ""),
                    "location": getattr(h, "location", ""),
                    "created_at": getattr(h, "created_at", ""),
                }
                for h in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StudentRecord":
        rec = cls(
            student_id=int(data["student_id"]),
            name=data.get("name", ""),
            course=data.get("course", ""),
            total_demerits=int(data.get("total_demerits", 0)),
            status=data.get("status", "Good Standing"),
            parent_name=data.get("parent_name", ""),
            emergency_contact=data.get("emergency_contact", ""),
            meeting_date=data.get("meeting_date", ""),
            counseling_note=data.get("counseling_note", ""),
            dean_approved=bool(data.get("dean_approved", False)),
            approved_by=data.get("approved_by", ""),
            letter_signed=bool(data.get("letter_signed", False)),
        )
        for h in data.get("history", []):
            rec.history.append(
                ViolationEntry(
                    code=h["code"],
                    points=int(h["points"]),
                    description=h.get("description", ""),
                    reporter=h.get("reporter", ""),
                    location=h.get("location", ""),
                    created_at=h.get("created_at", ""),
                )
            )
        return rec
