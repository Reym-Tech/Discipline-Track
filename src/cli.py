"""Terminal front-end at the outer Seam. Calls only DisciplineLedger's Interface."""
from __future__ import annotations

import sys

from src.catalog import UnknownViolationError, codes, lookup
from src.ledger import DisciplineLedger, DuplicateStudentError, StudentNotFoundError
from src.stores import DEFAULT_PATH, load_json, save_json

try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.table import Table

    _RICH = True
except ImportError:  # fallback for locked-down lab machines
    _RICH = False
    Console = None  # type: ignore[assignment,misc]

STATUS_STYLE = {
    "Good Standing": "green",
    "Warned": "yellow",
    "Probation": "dark_orange",
    "Suspended": "red",
    "Lab Banned": "bold red",
    "Expelled": "bold white on red",
}


def _console():
    return Console() if _RICH else None


def print_audit(ledger: DisciplineLedger, records=None, title="Discipline Audit") -> None:
    rows = records if records is not None else ledger.audit_report()
    if _RICH:
        console = _console()
        assert console is not None
        table = Table(title=f"{title} ({len(rows)} students)")
        table.add_column("ID", justify="right")
        table.add_column("Name")
        table.add_column("Course")
        table.add_column("Demerits", justify="right")
        table.add_column("Status")
        for r in rows:
            table.add_row(
                str(r.student_id),
                r.name,
                r.course,
                str(r.total_demerits),
                f"[{STATUS_STYLE.get(r.status, '')}]{r.status}[/]"
                if STATUS_STYLE.get(r.status)
                else r.status,
            )
        console.print(table)
    else:
        print(f"--- {title} ({len(rows)}) ---")
        for r in rows:
            print(f"{r.student_id:>6} | {r.name:<20} | {r.total_demerits:>2} | {r.status}")


def print_student(rec) -> None:
    if _RICH:
        console = _console()
        assert console is not None
        console.print(f"[bold]{rec.student_id} — {rec.name}[/bold] ({rec.course or 'no course'})")
        console.print(f"Demerits: {rec.total_demerits} | Status: {rec.status}")
        if rec.history:
            t = Table(title="Violation history")
            t.add_column("Code")
            t.add_column("Pts", justify="right")
            t.add_column("Description")
            for h in rec.history:
                t.add_row(h.code, str(h.points), h.description)
            console.print(t)
    else:
        print(f"{rec.student_id} - {rec.name} ({rec.course})")
        print(f"Demerits: {rec.total_demerits} | Status: {rec.status}")
        for h in rec.history:
            print(f"  {h.code} +{h.points}: {h.description}")


def _ask(prompt: str, default: str = "") -> str:
    if _RICH:
        assert Console is not None
        return Prompt.ask(prompt, default=default).strip()
    suffix = f" [{default}]" if default else ""
    ans = input(f"{prompt}{suffix}: ").strip()
    return ans or default


def main(path: str = DEFAULT_PATH) -> None:
    ledger = load_json(path)
    console = _console()
    say = console.print if console else print
    say(f"Discipline-Track loaded: {len(ledger)} student(s). Data: {path}")

    while True:
        say("\n[bold]1[/bold] Register  [bold]2[/bold] Log violation  [bold]3[/bold] Lookup"
            "  [bold]4[/bold] Audit  [bold]5[/bold] High-risk  [bold]6[/bold] Save  [bold]0[/bold] Exit"
            if _RICH else
            "\n1 Register  2 Log violation  3 Lookup  4 Audit  5 High-risk  6 Save  0 Exit")
        choice = _ask("Choose", "4" if len(ledger) else "1")
        try:
            if choice == "1":
                sid = int(_ask("Student ID (e.g. 1001)"))
                name = _ask("Full name")
                course = _ask("Course/section", "BSIT-1A")
                rec = ledger.register_student(sid, name, course)
                save_json(ledger, path)
                say(f"Registered {rec.student_id} - {rec.name}.")
            elif choice == "2":
                sid = int(_ask("Student ID"))
                say(f"Codes: {', '.join(codes())}")
                code = _ask("Violation code").upper()
                label, _ = lookup(code)
                desc = _ask("Description", label)
                consequence = ledger.log_violation(sid, code, desc)
                save_json(ledger, path)
                rec = ledger.get_student(sid)
                assert rec is not None
                say(f"Logged {code} (+{lookup(code)[1]}). Total: {rec.total_demerits} -> {consequence.status}: {consequence.sanction}")
            elif choice == "3":
                rec = ledger.get_student(int(_ask("Student ID")))
                print_student(rec) if rec else say("Student not found.")
            elif choice == "4":
                print_audit(ledger)
            elif choice == "5":
                threshold = int(_ask("Minimum demerits", "3"))
                print_audit(ledger, ledger.list_by_severity(threshold),
                            f"High-risk (>= {threshold})")
            elif choice == "6":
                save_json(ledger, path)
                say("Saved.")
            elif choice == "0":
                save_json(ledger, path)
                say("Saved. Goodbye.")
                return
            else:
                say("Unknown choice.")
        except ValueError as exc:
            say(f"Input error: {exc}")
        except (DuplicateStudentError, StudentNotFoundError, UnknownViolationError) as exc:
            say(f"Error: {exc}")
        except KeyboardInterrupt:
            save_json(ledger, path)
            say("\nSaved. Goodbye.")
            return


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
