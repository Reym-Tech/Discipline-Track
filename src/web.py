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

SERVER_RENDER_CAP = 500
SEARCH_CAP = 10
AUDIT_LIMIT_CAP = 5000


def record_to_json(rec: StudentRecord) -> dict:
    return {
        "student_id": rec.student_id,
        "name": rec.name,
        "course": rec.course,
        "total_demerits": rec.total_demerits,
        "status": rec.status,
        "sanction": evaluate(rec.total_demerits).sanction,
        "history": [
            {"code": h.code, "points": h.points, "description": h.description}
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
        rows = ledger().audit_report()[:SERVER_RENDER_CAP]
        total = len(ledger())
        return render_template(
            "audit.html",
            rows=rows,
            total=total,
            rendered=len(rows),
            at_risk=len(ledger().list_by_severity(3)),
        )

    @app.get("/log")
    def log_page():
        return render_template("log.html", options=violation_options())

    # -- JSON endpoints ------------------------------------------------
    @app.get("/api/audit")
    def api_audit():
        try:
            min_demerits = int(request.args.get("min_demerits", 0))
            limit = int(request.args.get("limit", 500))
        except (TypeError, ValueError):
            return jsonify(error="min_demerits and limit must be integers"), 400
        limit = max(1, min(limit, AUDIT_LIMIT_CAP))
        matching = ledger().list_by_severity(min_demerits)
        return jsonify(
            students=[record_to_json(r) for r in matching[:limit]],
            total=len(matching),
            returned=min(len(matching), limit),
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
        try:
            with app.config["LOCK"]:
                rec = ledger().register_student(sid, name, course)
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
        try:
            with app.config["LOCK"]:
                consequence = ledger().log_violation(sid, code, description)
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

    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Discipline-Track web frontend")
    parser.add_argument("data_path", nargs="?", default=DEFAULT_PATH)
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args(argv)
    create_app(args.data_path).run(port=args.port)


if __name__ == "__main__":
    main()
