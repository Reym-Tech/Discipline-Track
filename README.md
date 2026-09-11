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

| Choice | Action |
|---|---|
| 1 | Register student (ID, name, course) |
| 2 | Log violation (code + description) |
| 3 | Lookup student + history |
| 4 | Full audit, ordered by (demerits, ID) |
| 5 | High-risk filter (min demerits) |
| 6 / 0 | Save (autosaves after every mutation) |

Violation codes: `SMOKE` 1, `NOID` 1, `CUTTING` 2, `CHEAT` 3,
`PLAGIARISM` 4, `HACK` 5.

Consequence matrix: 0 Good Standing · 1 Warned (Written Warning) ·
2 Probation (Parent Conference) · 3 Suspended (3-Day Suspension + zero) ·
4 Lab Banned (subject failure + lab ban) · 5+ Expelled.

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

* `/` — Audit: demerit-ordered table, severity/row-limit filter, per-row
  detail panel with violation history. Empty, loading, and error states inline.
* `/log` — Log violation: search-as-you-type by name or ID, violation picker
  from the catalog, instant consequence banner; inline registration form.

JSON endpoints: `GET /api/audit?min_demerits=&limit=`,
`GET /api/students?q=`, `GET /api/students/<id>`,
`POST /api/students`, `POST /api/violations`.
Errors map 1:1 from the ledger (400 bad code/payload, 404 unknown student,
409 duplicate).

Design: Neumorphism club world (`.agents/frontend` tokens — teal `#006666`
on warm-gray `#E7E5E4`, self-hosted Space Mono / JetBrains Mono, tactile
extruded surfaces). Elderly and low-vision support: 18px base with A / A+ /
A++ text-size control, high-contrast toggle, 44px+ targets, skip link,
visible focus rings, keyboard-first controls — all persisted locally.
Every text/background pair is AA-verified via `scripts/check_contrast.py`.

## Measured behaviour (N=1000/5000, this machine)

RB insert ≈ 3–4× faster than AVL insert (fewer rotations).
Full ordered audit ties (both O(n) traversals); AVL's edge is
shallower point lookup, not full scans. See `docs/DESIGN.md`.
