"""Storage Adapter seam spec: JSON file round-trip, missing file behaviour."""


def test_json_save_and_load_round_trip(tmp_path):
    from src.ledger import DisciplineLedger
    from src.stores import load_json, save_json

    ledger = DisciplineLedger()
    ledger.register_student(1001, "Ada", "BSIT-1A")
    ledger.register_student(1002, "Bob", "BSIT-1B")
    ledger.log_violation(1001, "CHEAT")

    path = tmp_path / "records.json"
    save_json(ledger, str(path))
    assert path.exists()

    restored = load_json(str(path))
    assert restored.get_student(1001).total_demerits == 3
    assert restored.get_student(1002).total_demerits == 0
    assert [(r.student_id, r.total_demerits) for r in restored.audit_report()] == [
        (1002, 0),
        (1001, 3),
    ]


def test_load_missing_file_returns_empty_ledger(tmp_path):
    from src.stores import load_json

    ledger = load_json(str(tmp_path / "does-not-exist.json"))
    assert len(ledger) == 0
    assert ledger.audit_report() == []
