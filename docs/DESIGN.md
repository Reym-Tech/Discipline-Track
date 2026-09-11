# Design note: Seams, Depth, and honest trade-offs

## Modules and Seams

- **DisciplineLedger** is the deep Module. Interface: `register_student`,
  `log_violation`, `get_student`, `audit_report(descending=False)`,
  `list_by_severity(min, descending=False)`, `pending_cases`,
  `approve_case`, `schedule_meeting`, `save_counseling_note`, `sign_letter`,
  `to_dict/from_dict`. Everything else is hidden Implementation.
- **ConsequenceEngine** (`consequences.evaluate`) and **ViolationCatalog**
  (`catalog.lookup`) are pure Modules: return results, no side effects.
- **AVLTree** and **RBTree** expose only
  `insert / search / delete / inorder / len`. Rotations and fixups are
  private. Tests assert behaviour (sorted order, invariants), never internals.
- **Persistence Seam**: `InMemory` (live ledger) vs `JsonFile`
  (`stores.save_json/load_json`). Two Adapters, so a real Seam.
  The ledger never touches files.
- **Outer Seam**: `cli.py` calls only the ledger Interface.

## Sync rule (the load-bearing decision)

The same `StudentRecord` object sits in both trees.
RB key never changes (`student_id`); AVL key does
(`(total_demerits, student_id)` composite — required because demerits
alone are not unique). On `log_violation`:

1. `old = (rec.total_demerits, sid)`
2. `rec.apply_violation(...)` (bumps total, recomputes status)
3. `avl.delete(old)` → `avl.insert((new_total, sid), rec)`

RB needs no structural change (same object reference).
Deletion test: delete the ledger and every caller reimplements
sync + balancing + consequences — it earns its keep.

## What we claim (and don't)

- RB ingestion is measurably cheaper: ~3–4× faster bulk insert at
  N=1000–5000 (fewer rotations per insert). Confirmed by
  `scripts/benchmark.py`.
- Full ordered audit ties between trees: inorder traversal is O(n)
  either way. AVL's strict balance pays off in point/range lookup
  height, not full scans. We report the tie honestly.
- At department scale (hundreds) both answer instantly; the split is a
  comparative study with a clean Seam, not a production bottleneck fix.

## Workflow statuses (proposal decision: overwrite)

`evaluate(total)` stays pure (`5+ → Expelled` recommendation). The record's
`status` diverges to route human work: `log_violation` to 5+ sets
`Pending Disciplinary Review`; `approve_case` (Dean `yes`) sets
`Pending Disciplinary Meeting`. Legacy `Expelled` rows still count in
`pending_cases()` so old JSON routes. Never filter the queue by
`status == "Expelled"` — use `pending_cases()` (highest first).

Audit ordering: stored ascending by `(demerits, ID)`; Dean/Guidance views
request `descending=True` so the highest-risk flashes on top with
`PROPOSAL: <STATUS> — <sanction>`.

## Error modes

`DuplicateStudentError` (re-register), `StudentNotFoundError` (log for
unknown ID), `UnknownViolationError` (bad code). All raised through the
ledger Interface; CLI renders them as messages. `approve_case` raises
`ValueError` when the student is not expulsion-level.
