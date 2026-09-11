"""StudentRecord: plain data Module. No tree logic lives here."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ViolationEntry:
    code: str
    points: int
    description: str


@dataclass
class Consequence:
    status: str
    sanction: str


@dataclass
class StudentRecord:
    student_id: int
    name: str
    course: str = ""
    total_demerits: int = 0
    status: str = "Good Standing"
    history: list = field(default_factory=list)

    def apply_violation(self, code: str, points: int, description: str) -> None:
        from src.consequences import evaluate

        self.history.append(ViolationEntry(code=code, points=points, description=description))
        self.total_demerits += points
        consequence = evaluate(self.total_demerits)
        self.status = consequence.status

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "name": self.name,
            "course": self.course,
            "total_demerits": self.total_demerits,
            "status": self.status,
            "history": [
                {"code": h.code, "points": h.points, "description": h.description}
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
        )
        for h in data.get("history", []):
            rec.history.append(
                ViolationEntry(
                    code=h["code"], points=int(h["points"]), description=h.get("description", "")
                )
            )
        return rec
