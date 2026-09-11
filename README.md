# Discipline-Track: Dual-Index Violation Ledger (AVL + Red-Black)

Terminal-based IT Department Student Violation Tracking System.
One record set, two indexes, one owner.

## Run

```bash
pip install -r requirements.txt
python scripts/seed.py            # demo data -> data/records.json
python -m src.cli                 # interactive terminal (Rich tables)
python -m src.cli data/custom.json
python -m src.web                 # web frontend -> http://127.0.0.1:5000
python -m src.web data/custom.json --port 5001
python scripts/benchmark.py 1000 5000
python -m pytest -q
```

No Rich? The CLI falls back to plain `print` automatically.

## Use

| Choice | Role / Action |
|---|---|
| 1 | Guard Post: Log New Campus Violation (ID search via RB-Tree + guard name + code + description + location) |
| 2 | Dean's Office: Run Discipline Audit (AVL descending, Critical Alert on top, `yes` to authorize) |
| 3 | Guidance Office: Coordination queue (contacts, conference date, expulsion letter, counseling note) |
| 4 | Register student (ID, name, course, parent + emergency contact) |
| 5 | Lookup student + history |
| 6 | High-risk filter (min demerits, highest first) |
| 0 | Save + Exit (autosaves after every mutation) |

Violation codes: `SMOKE` 1, `NOID` 1, `CUTTING` 2, `CHEAT` 3,
`PLAGIARISM` 4, `HACK` 5. Each entry also stores reporter, location, timestamp.

Consequence matrix: 0 Good Standing · 1 Warned (Written Warning) ·
2 Probation (Parent Conference) · 3 Suspended (3-Day Suspension + zero) ·
4 Lab Banned (subject failure + lab ban) · 5+ Expelled
(`Immediate expulsion from the IT Department`).

Workflow overwrite (approved proposal): the matrix recommendation stays
pure, but the record `status` is overwritten to route the case —
5+ demerits → `Pending Disciplinary Review` (Guard log),
Dean `yes` → `Pending Disciplinary Meeting`. Filter routed queues via
`pending_cases()`, not `status == "Expelled"`.

Demo: seed includes `63326 John Doe` at 4 demerits (plagiarism). Log `NOID`
as `Guard Ramos` to reproduce the 4→5 review flow.

## Layout

```
src/models.py        StudentRecord, ViolationEntry, Consequence
src/catalog.py       code -> (label, points)
src/consequences.py  total -> (status, sanction)
src/avl.py           AVLTree keyed by (demerits, student_id)
src/rbtree.py        RBTree keyed by student_id
src/ledger.py        DisciplineLedger — owns both indexes + sync
src/stores.py        JsonFile Adapter (save_json/load_json)
src/cli.py           Rich terminal at the outer Seam
src/web.py           Flask web Adapter (Audit + Log screens)
src/templates/       audit.html, log.html (server-rendered)
src/static/          style.css, app.js (filter, search, detail)
scripts/seed.py      demo data    scripts/benchmark.py  evidence
tests/               one file per Seam (31 tests)
docs/DESIGN.md       Seam placement, sync rule, honest trade-offs
```

## Web frontend

Two screens sharing the same JSON file as the terminal, so both stay in sync:

* `/` — Audit: demerit-ordered table, minimum-demerits filter with
  whole-number validation, first 10 matches shown; per-row
  detail panel with violation history. Empty, loading, and error states inline.
* `/log` — Log violation: search-as-you-type by name or ID, violation picker
  from the catalog, instant consequence banner; inline registration form.

JSON endpoints: `GET /api/audit?min_demerits=&limit=&order=` (defaults: min 0,
limit 10, order asc; min must be 0 or higher; order asc|desc),
`GET /api/students?q=`, `GET /api/students/<id>`,
`POST /api/students` (accepts parent_name, emergency_contact),
`POST /api/violations` (accepts reporter, location),
`GET /api/cases` (Dean→Guidance queue, highest first),
`POST /api/cases/<id>/approve` (requires `{"confirm":"yes"}`),
`POST /api/cases/<id>/meeting`, `POST /api/cases/<id>/counseling`,
`GET /api/cases/<id>/letter`.
Errors map 1:1 from the ledger (400 bad code/payload, 404 unknown student,
409 duplicate).

Design: full Neumorphism club world (teal `#006666` on warm-gray `#E7E5E4`,
self-hosted Space Mono / JetBrains Mono) — extruded surfaces, pressed inputs,
no flat base. The tour tooltip floats in the same soft shadow as the
spotlight highlight, with no stroke.
Readable by default: 18px base, 44px+ targets, skip link, visible focus
rings. Every text/background pair is AA-verified via
`scripts/check_contrast.py`.

First visit auto-starts a brief guided tour (3 steps per screen, spotlight +
one-line descriptions, skippable, replayable via the header Tour button,
remembered per browser). The audit tour hands off to the Log tour, which
drives a real demo search; the tour never creates or edits records.

## Measured behaviour (N=1000/5000, this machine)

RB insert ≈ 3–4× faster than AVL insert (fewer rotations).
Full ordered audit ties (both O(n) traversals); AVL's edge is
shallower point lookup, not full scans. See `docs/DESIGN.md`.
