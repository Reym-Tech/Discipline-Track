"""Web Adapter at the outer Seam: HTTP in, DisciplineLedger Interface out.

Thin by design: no tree logic, no consequence matrix, no file handling
beyond delegating to the JsonFile Adapter. Ledger owns all behaviour.
Run:  python -m src.web [data_path] [--port 5000]
"""
from __future__ import annotations

import argparse
import threading

from flask import Flask, jsonify, render_template, request

from src.catalog import UnknownViolationError, codes, lookup
from src.consequences import evaluate
from src.ledger import DisciplineLedger, DuplicateStudentError, StudentNotFoundError
from src.models import StudentRecord
from src.stores import DEFAULT_PATH, load_json, save_json

SERVER_RENDER_CAP = 10
SEARCH_CAP = 10
AUDIT_DEFAULT_LIMIT = 10
AUDIT_LIMIT_CAP = 5000


def record_to_json(rec: StudentRecord) -> dict:
    consequence = evaluate(rec.total_demerits)
    return {
        "student_id": rec.student_id,
        "name": rec.name,
        "course": rec.course,
        "total_demerits": rec.total_demerits,
        "status": rec.status,
        "sanction": consequence.sanction,
        "proposal": f"{consequence.status.upper()} — {consequence.sanction}",
        "parent_name": getattr(rec, "parent_name", ""),
        "emergency_contact": getattr(rec, "emergency_contact", ""),
        "meeting_date": getattr(rec, "meeting_date", ""),
        "counseling_note": getattr(rec, "counseling_note", ""),
        "dean_approved": getattr(rec, "dean_approved", False),
        "approved_by": getattr(rec, "approved_by", ""),
        "letter_signed": getattr(rec, "letter_signed", False),
        "history": [
            {
                "code": h.code,
                "points": h.points,
                "description": h.description,
                "reporter": getattr(h, "reporter", ""),
                "location": getattr(h, "location", ""),
                "created_at": getattr(h, "created_at", ""),
            }
            for h in rec.history
        ],
    }


def violation_options() -> list[dict]:
    return [{"code": c, "label": lookup(c)[0], "points": lookup(c)[1]} for c in codes()]


def create_app(data_path: str = DEFAULT_PATH) -> Flask:
    app = Flask(__name__)
    app.config["LEDGER"] = load_json(data_path)
    app.config["DATA_PATH"] = data_path
    app.config["LOCK"] = threading.Lock()

    def ledger() -> DisciplineLedger:
        return app.config["LEDGER"]

    def persist() -> None:
        save_json(ledger(), app.config["DATA_PATH"])

    # -- pages ---------------------------------------------------------
    @app.get("/")
    def audit_page():
        rows = ledger().audit_report(descending=True)[:SERVER_RENDER_CAP]
        total = len(ledger())
        critical = rows[0] if rows and rows[0].total_demerits >= 5 else None
        return render_template(
            "audit.html",
            rows=rows,
            total=total,
            rendered=len(rows),
            at_risk=len(ledger().list_by_severity(3)),
            critical=critical,
        )

    @app.get("/log")
    def log_page():
        return render_template("log.html", options=violation_options())

    # -- JSON endpoints ------------------------------------------------
    @app.get("/api/audit")
    def api_audit():
        try:
            min_demerits = int(request.args.get("min_demerits", 0))
            limit = int(request.args.get("limit", AUDIT_DEFAULT_LIMIT))
        except (TypeError, ValueError):
            return jsonify(error="min_demerits and limit must be integers"), 400
        if min_demerits < 0:
            return jsonify(error="min_demerits must be 0 or higher"), 400
        order = (request.args.get("order") or "asc").strip().lower()
        if order not in ("asc", "desc"):
            return jsonify(error="order must be 'asc' or 'desc'"), 400
        limit = max(1, min(limit, AUDIT_LIMIT_CAP))
        matching = ledger().list_by_severity(min_demerits, descending=(order == "desc"))
        return jsonify(
            students=[record_to_json(r) for r in matching[:limit]],
            total=len(matching),
            returned=min(len(matching), limit),
            order=order,
        )

    @app.get("/api/students")
    def api_search():
        query = (request.args.get("q") or "").strip().lower()
        if not query:
            return jsonify(students=[])
        hits = sorted(
            (
                r
                for r in ledger().audit_report()
                if query in r.name.lower() or str(r.student_id).startswith(query)
            ),
            key=lambda r: r.student_id,
        )
        return jsonify(students=[record_to_json(r) for r in hits[:SEARCH_CAP]])

    @app.get("/api/students/<int:student_id>")
    def api_detail(student_id: int):
        rec = ledger().get_student(student_id)
        if rec is None:
            return jsonify(error=f"Student {student_id} not found"), 404
        return jsonify(record_to_json(rec))

    @app.post("/api/students")
    def api_register():
        data = request.get_json(silent=True) or {}
        try:
            sid = int(data.get("student_id"))
        except (TypeError, ValueError):
            return jsonify(error="student_id must be an integer"), 400
        name = str(data.get("name") or "").strip()
        if not name:
            return jsonify(error="name is required"), 400
        course = str(data.get("course") or "").strip()
        parent_name = str(data.get("parent_name") or "").strip()
        emergency_contact = str(data.get("emergency_contact") or "").strip()
        try:
            with app.config["LOCK"]:
                rec = ledger().register_student(
                    sid, name, course,
                    parent_name=parent_name, emergency_contact=emergency_contact,
                )
                persist()
        except DuplicateStudentError as exc:
            return jsonify(error=str(exc)), 409
        return jsonify(record_to_json(rec)), 201

    @app.post("/api/violations")
    def api_violation():
        data = request.get_json(silent=True) or {}
        try:
            sid = int(data.get("student_id"))
        except (TypeError, ValueError):
            return jsonify(error="student_id must be an integer"), 400
        code = str(data.get("code") or "").strip().upper()
        if not code:
            return jsonify(error="code is required"), 400
        description = str(data.get("description") or "").strip()
        reporter = str(data.get("reporter") or "").strip()
        location = str(data.get("location") or "").strip()
        try:
            with app.config["LOCK"]:
                consequence = ledger().log_violation(
                    sid, code, description, reporter=reporter, location=location
                )
                rec = ledger().get_student(sid)
                assert rec is not None
                persist()
        except StudentNotFoundError as exc:
            return jsonify(error=str(exc)), 404
        except UnknownViolationError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(
            record=record_to_json(rec),
            consequence={"status": consequence.status, "sanction": consequence.sanction},
        )

    # -- Guidance case queue (Phases 2-4) ------------------------------
    @app.get("/api/cases")
    def api_cases():
        return jsonify(
            cases=[record_to_json(r) for r in ledger().pending_cases()],
            total=len(ledger().pending_cases()),
        )

    @app.post("/api/cases/<int:student_id>/approve")
    def api_approve(student_id: int):
        data = request.get_json(silent=True) or {}
        approved_by = str(data.get("approved_by") or "Dean")
        confirm = str(data.get("confirm") or "").strip().lower()
        # Web requires explicit confirm=yes to mirror terminal "yes" gate.
        if confirm not in ("yes", "y"):
            return jsonify(error="confirm must be 'yes' to authorize"), 400
        try:
            with app.config["LOCK"]:
                rec = ledger().approve_case(student_id, approved_by=approved_by)
                persist()
        except StudentNotFoundError as exc:
            return jsonify(error=str(exc)), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(record_to_json(rec))

    @app.post("/api/cases/<int:student_id>/meeting")
    def api_meeting(student_id: int):
        data = request.get_json(silent=True) or {}
        try:
            with app.config["LOCK"]:
                rec = ledger().schedule_meeting(
                    student_id,
                    str(data.get("meeting_date") or ""),
                    parent_name=str(data.get("parent_name") or ""),
                    emergency_contact=str(data.get("emergency_contact") or ""),
                )
                persist()
        except StudentNotFoundError as exc:
            return jsonify(error=str(exc)), 404
        return jsonify(record_to_json(rec))

    @app.post("/api/cases/<int:student_id>/counseling")
    def api_counseling(student_id: int):
        data = request.get_json(silent=True) or {}
        try:
            with app.config["LOCK"]:
                rec = ledger().save_counseling_note(student_id, str(data.get("note") or ""))
                persist()
        except StudentNotFoundError as exc:
            return jsonify(error=str(exc)), 404
        return jsonify(record_to_json(rec))

    @app.get("/api/cases/<int:student_id>/letter")
    def api_letter(student_id: int):
        rec = ledger().get_student(student_id)
        if rec is None:
            return jsonify(error=f"Student {student_id} not found"), 404
        return jsonify(letter=rec.expulsion_letter(), record=record_to_json(rec))

    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Discipline-Track web frontend")
    parser.add_argument("data_path", nargs="?", default=DEFAULT_PATH)
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args(argv)
    create_app(args.data_path).run(port=args.port)


if __name__ == "__main__":
    main()
