# Discipline-Track: Dual-Index Violation Ledger (AVL + Red-Black)

Terminal-based IT Department Student Violation Tracking System.
One record set, two indexes, one owner.

## Run

```bash
pip install -r requirements.txt
python scripts/seed.py            # demo data -> data/records.json
python -m src.cli                 # interactive terminal (Rich tables)
python -m src.cli data/custom.json
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
scripts/seed.py      demo data    scripts/benchmark.py  evidence
tests/               one file per Seam (24 tests)
docs/DESIGN.md       Seam placement, sync rule, honest trade-offs
```

## Measured behaviour (N=1000/5000, this machine)

RB insert ≈ 3–4× faster than AVL insert (fewer rotations).
Full ordered audit ties (both O(n) traversals); AVL's edge is
shallower point lookup, not full scans. See `docs/DESIGN.md`.
