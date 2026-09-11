"""Web Adapter seam spec: HTTP in, DisciplineLedger Interface out.

Tests cross only the HTTP Interface (Flask test client). No tree,
ledger-internal, or template assertions beyond status codes and JSON
shapes plus key page markers.
"""
import pytest


@pytest.fixture()
def client(tmp_path):
    from src.web import create_app

    app = create_app(str(tmp_path / "web.json"))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def _register(client, sid=1001, name="Ada Lovelace", course="BSIT-1A"):
    return client.post("/api/students", json={"student_id": sid, "name": name, "course": course})


def test_pages_render(client):
    assert client.get("/").status_code == 200
    res = client.get("/log")
    assert res.status_code == 200
    # Log screen carries the violation codes from the catalog
    assert b"PLAGIARISM" in res.data


def test_pages_include_accessibility_landmarks(client):
    for path in ("/", "/log"):
        html = client.get(path).data
        assert b'id="skip-link"' in html
        assert b"<main" in html
        assert b'id="tour-start"' in html
        # Display controls were removed; header keeps nav + tour only.
        assert b'id="text-size"' not in html
        assert b'id="contrast-toggle"' not in html


def test_self_hosted_fonts_served(client):
    for name in ("SpaceMono-Regular", "SpaceMono-Bold", "JetBrainsMono-Regular"):
        res = client.get(f"/static/fonts/{name}.woff2")
        assert res.status_code == 200
        assert res.data[:4] == b"wOF2"


def test_tour_assets_and_trigger(client):
    for path in ("/", "/log"):
        html = client.get(path).data
        assert b'id="tour-start"' in html
        assert b"tour.js" in html
    res = client.get("/static/tour.js")
    assert res.status_code == 200
    assert b"dt-tour-seen" in res.data


def test_register_then_duplicate_maps_to_409(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_log_violation_returns_consequence_and_reorders_audit(client):
    _register(client, 1001, "Ada Lovelace")
    _register(client, 1002, "Bob Santos")
    res = client.post("/api/violations", json={"student_id": 1001, "code": "CHEAT"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["consequence"]["status"] == "Suspended"
    assert body["record"]["total_demerits"] == 3

    audit = client.get("/api/audit").get_json()
    assert [(r["student_id"], r["total_demerits"]) for r in audit["students"]] == [
        (1002, 0),
        (1001, 3),
    ]


def test_audit_filter_and_limit(client):
    _register(client, 1001, "Ada")
    _register(client, 1002, "Bob")
    client.post("/api/violations", json={"student_id": 1001, "code": "HACK"})
    body = client.get("/api/audit?min_demerits=3").get_json()
    assert [r["student_id"] for r in body["students"]] == [1001]
    assert body["total"] == 1
    limited = client.get("/api/audit?limit=1").get_json()
    assert limited["returned"] == 1
    assert limited["total"] == 2


def test_audit_defaults_to_ten_rows(client):
    for i in range(12):
        _register(client, 2000 + i, f"Student {i}")
    body = client.get("/api/audit").get_json()
    assert body["total"] == 12
    assert body["returned"] == 10
    assert len(body["students"]) == 10


def test_audit_rejects_bad_min_demerits(client):
    assert client.get("/api/audit?min_demerits=-1").status_code == 400
    assert client.get("/api/audit?min_demerits=abc").status_code == 400
    assert client.get("/api/audit?min_demerits=2.5").status_code == 400


def test_audit_page_has_no_row_limit_input(client):
    html = client.get("/").data
    assert b'id="limit"' not in html
    assert b'id="min"' in html


def test_audit_page_renders_at_most_ten_rows(client):
    for i in range(12):
        _register(client, 3000 + i, f"Student {i}")
    html = client.get("/").data
    assert html.count(b"<tr data-sid=") == 10


def test_student_search_by_name_and_id(client):
    _register(client, 1001, "Ada Lovelace")
    _register(client, 1002, "Bob Santos")
    assert [r["student_id"] for r in client.get("/api/students?q=ada").get_json()["students"]] == [1001]
    assert [r["student_id"] for r in client.get("/api/students?q=100").get_json()["students"]] == [1001, 1002]
    assert client.get("/api/students?q=").get_json()["students"] == []


def test_student_detail_and_error_modes(client):
    _register(client, 1001, "Ada Lovelace")
    client.post("/api/violations", json={"student_id": 1001, "code": "SMOKE", "description": "Near lab"})
    detail = client.get("/api/students/1001").get_json()
    assert detail["total_demerits"] == 1
    assert detail["history"][0]["code"] == "SMOKE"

    assert client.get("/api/students/9999").status_code == 404
    assert client.post("/api/violations", json={"student_id": 9999, "code": "SMOKE"}).status_code == 404
    assert client.post("/api/violations", json={"student_id": 1001, "code": "NOPE"}).status_code == 400
    assert client.post("/api/students", json={"student_id": 1003}).status_code == 400
    assert client.post("/api/violations", json={"student_id": 1001}).status_code == 400


def test_mutations_persist_to_json_file(tmp_path):
    from src.stores import load_json
    from src.web import create_app

    path = str(tmp_path / "persist.json")
    app = create_app(path)
    c = app.test_client()
    c.post("/api/students", json={"student_id": 1001, "name": "Ada"})
    c.post("/api/violations", json={"student_id": 1001, "code": "CHEAT"})
    restored = load_json(path)
    assert restored.get_student(1001).total_demerits == 3
