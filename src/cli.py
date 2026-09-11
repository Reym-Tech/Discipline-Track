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
    "Pending Disciplinary Review": "bold white on red",
    "Pending Disciplinary Meeting": "bold white on red",
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
        if getattr(rec, "parent_name", "") or getattr(rec, "emergency_contact", ""):
            console.print(f"Parent: {rec.parent_name or '-'} | Contact: {rec.emergency_contact or '-'}")
        if getattr(rec, "meeting_date", ""):
            console.print(f"Conference: {rec.meeting_date}")
        if rec.history:
            t = Table(title="Violation history")
            t.add_column("Code")
            t.add_column("Pts", justify="right")
            t.add_column("Description")
            t.add_column("Reporter")
            for h in rec.history:
                t.add_row(h.code, str(h.points), h.description, getattr(h, "reporter", ""))
            console.print(t)
        if getattr(rec, "counseling_note", ""):
            console.print(f"Counseling note: {rec.counseling_note}")
    else:
        print(f"{rec.student_id} - {rec.name} ({rec.course})")
        print(f"Demerits: {rec.total_demerits} | Status: {rec.status}")
        if getattr(rec, "parent_name", "") or getattr(rec, "emergency_contact", ""):
            print(f"Parent: {rec.parent_name} | Contact: {rec.emergency_contact}")
        for h in rec.history:
            rep = f" (by {h.reporter})" if getattr(h, "reporter", "") else ""
            print(f"  {h.code} +{h.points}: {h.description}{rep}")


def _ask(prompt: str, default: str = "") -> str:
    if _RICH:
        assert Console is not None
        return Prompt.ask(prompt, default=default).strip()
    suffix = f" [{default}]" if default else ""
    ans = input(f"{prompt}{suffix}: ").strip()
    return ans or default


def do_guard_log(ledger: DisciplineLedger, path: str, say) -> None:
    """Phase 1: Guard Post — RB search by ID, log with reporter name."""
    sid = int(_ask("Student ID"))
    rec = ledger.get_student(sid)
    if rec is None:
        say("Student not found. Register first (menu 4) or check the ID.")
        return
    say(f"Found: {rec.student_id} — {rec.name} ({rec.total_demerits} demerits, {rec.status})")
    reporter = _ask("Guard name (e.g. Guard Ramos)")
    say(f"Codes: {', '.join(codes())}")
    code = _ask("Violation code").upper()
    label, _ = lookup(code)
    desc = _ask("Offense description", label)
    location = _ask("Location (e.g. campus entrance gate)", "")
    consequence = ledger.log_violation(sid, code, desc, reporter=reporter, location=location)
    save_json(ledger, path)
    rec = ledger.get_student(sid)
    assert rec is not None
    say(f"Logged {code} (+{lookup(code)[1]}). Total: {rec.total_demerits} -> {rec.status}")
    say(f"PROPOSAL: {consequence.status.upper()} — {consequence.sanction}")
    if rec.total_demerits >= 5:
        say("Routed to Dean: Pending Disciplinary Review.")


def do_dean_audit(ledger: DisciplineLedger, path: str, say) -> None:
    """Phase 2: Dean's Office — descending AVL audit, critical alert, yes-gate."""
    rows = ledger.audit_report(descending=True)
    if rows and rows[0].total_demerits >= 5:
        top = rows[0]
        say(f"CRITICAL ALERT: {top.student_id} — {top.name} ({top.total_demerits} demerits) — {top.status}")
        from src.consequences import evaluate as _eval

        say(f"PROPOSAL: {_eval(top.total_demerits).status.upper()} FROM THE IT DEPARTMENT — {_eval(top.total_demerits).sanction}")
    print_audit(ledger, rows, "Discipline Audit (highest first)")
    short = _ask("Enter student ID to approve consequence (blank to skip)", "")
    if not short.strip():
        return
    rec = ledger.get_student(int(short.strip()))
    if rec is None:
        say("Student not found.")
        return
    print_student(rec)
    verdict = _ask("Approve and authorize? Type 'yes' to confirm", "")
    if verdict.strip().lower() == "yes":
        ledger.approve_case(rec.student_id, approved_by="Dean")
        save_json(ledger, path)
        say(f"Authorized. {rec.student_id} is now Pending Disciplinary Meeting. Routed to Guidance.")
    else:
        say("Not approved — no change.")


def do_guidance(ledger: DisciplineLedger, path: str, say) -> None:
    """Phase 3+4: Guidance — routed queue, contacts/meeting, letter, counseling note."""
    queue = ledger.pending_cases()
    if not queue:
        say("No pending cases routed from the Dean.")
        return
    print_audit(ledger, queue, "Guidance queue (routed from Dean)")
    short = _ask("Enter student ID to open case file (blank to go back)", "")
    if not short.strip():
        return
    rec = ledger.get_student(int(short.strip()))
    if rec is None:
        say("Student not found.")
        return
    print_student(rec)
    say(f"Emergency contact: {rec.parent_name or '-'} ({rec.emergency_contact or 'no contact on file'})")
    # Arrange the mandatory face-to-face conference.
    meeting = _ask("Conference date/time (blank keeps current)", rec.meeting_date or "")
    parent = _ask("Parent/guardian name", rec.parent_name or "")
    contact = _ask("Emergency contact / phone", rec.emergency_contact or "")
    if meeting or parent or contact:
        ledger.schedule_meeting(rec.student_id, meeting or rec.meeting_date,
                                parent_name=parent, emergency_contact=contact)
        save_json(ledger, path)
        say(f"Conference arranged: call {parent or rec.parent_name} at {contact or rec.emergency_contact}.")
    # Combined board meeting: hand over the signed expulsion letter.
    want_letter = _ask("Print expulsion letter? (yes/no)", "yes")
    if want_letter.strip().lower() == "yes":
        say("--- EXPULSION LETTER ---")
        say(rec.expulsion_letter())
        ledger.sign_letter(rec.student_id)
        save_json(ledger, path)
        say("Letter signed and handed over. Dean penalty executed.")
    # Private exit interview: counselor stays behind with family.
    note = _ask("Exit-interview counseling note (blank to skip)", "")
    if note.strip():
        ledger.save_counseling_note(rec.student_id, note.strip())
        save_json(ledger, path)
        say("Counseling note saved.")


def main(path: str = DEFAULT_PATH) -> None:
    ledger = load_json(path)
    console = _console()
    say = console.print if console else print
    say(f"Discipline-Track loaded: {len(ledger)} student(s). Data: {path}")

    while True:
        say("\n[bold]1[/bold] Guard: Log violation  [bold]2[/bold] Dean: Discipline audit"
            "  [bold]3[/bold] Guidance: Coordination  [bold]4[/bold] Register"
            "  [bold]5[/bold] Lookup  [bold]6[/bold] High-risk  [bold]0[/bold] Save+Exit"
            if _RICH else
            "\n1 Guard: Log violation  2 Dean: Discipline audit  3 Guidance: Coordination"
            "  4 Register  5 Lookup  6 High-risk  0 Save+Exit")
        choice = _ask("Choose", "2" if len(ledger) else "4")
        try:
            if choice == "1":
                do_guard_log(ledger, path, say)
            elif choice == "2":
                do_dean_audit(ledger, path, say)
            elif choice == "3":
                do_guidance(ledger, path, say)
            elif choice == "4":
                sid = int(_ask("Student ID (e.g. 1001)"))
                name = _ask("Full name")
                course = _ask("Course/section", "BSIT-1A")
                parent = _ask("Parent/guardian name (optional)", "")
                contact = _ask("Emergency contact / phone (optional)", "")
                rec = ledger.register_student(sid, name, course,
                                              parent_name=parent, emergency_contact=contact)
                save_json(ledger, path)
                say(f"Registered {rec.student_id} - {rec.name}.")
            elif choice == "5":
                rec = ledger.get_student(int(_ask("Student ID")))
                print_student(rec) if rec else say("Student not found.")
            elif choice == "6":
                threshold = int(_ask("Minimum demerits", "3"))
                print_audit(ledger, ledger.list_by_severity(threshold, descending=True),
                            f"High-risk (>= {threshold}, highest first)")
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
