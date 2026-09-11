"""Benchmark: AVL vs Red-Black insert + ordered-traversal cost.

Fair comparison: same shuffled key order per N, fresh trees each run.
Also exercises the ledger path (register + audit) end to end.

Usage:  python scripts/benchmark.py [--sizes 1000 5000 10000]
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.avl import AVLTree
from src.ledger import DisciplineLedger
from src.rbtree import RBTree

SIZES = [1000, 5000, 10000]


def time_insert(tree_cls, keys):
    tree = tree_cls()
    start = time.perf_counter()
    for k in keys:
        tree.insert(k, k)
    return time.perf_counter() - start, tree


def time_traversal(tree):
    start = time.perf_counter()
    out = tree.inorder()
    return time.perf_counter() - start, len(out)


def time_ledger(n: int, seed: int):
    rng = random.Random(seed)
    ids = rng.sample(range(1_000_000), n)
    ledger = DisciplineLedger()
    start = time.perf_counter()
    for sid in ids:
        ledger.register_student(sid, f"S{sid}")
    ingest = time.perf_counter() - start
    start = time.perf_counter()
    report = ledger.audit_report()
    audit = time.perf_counter() - start
    return ingest, audit, len(report)


def main(sizes):
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
    except ImportError:
        console = None

    rows = []
    for n in sizes:
        keys = random.Random(1234 + n).sample(range(10_000_000), n)
        avl_t, avl = time_insert(AVLTree, keys)
        rb_t, rb = time_insert(RBTree, keys)
        avl_q, _ = time_traversal(avl)
        rb_q, _ = time_traversal(rb)
        led_in, led_au, _ = time_ledger(n, 999 + n)
        rows.append((n, avl_t, rb_t, avl_q, rb_q, led_in, led_au))

    if console:
        table = Table(title="AVL vs Red-Black (seconds, lower is better)")
        for col in ("N", "AVL insert", "RB insert", "AVL audit", "RB audit",
                    "Ledger register", "Ledger audit"):
            table.add_column(col, justify="right")
        for r in rows:
            table.add_row(*[f"{v:.4f}" if isinstance(v, float) else str(v) for v in r])
        console.print(table)
        console.print("Expectation: RB insert <= AVL insert; AVL audit <= RB audit. "
                      "Gaps widen with N; at small N both are instant.")
    else:
        print("N | AVL ins | RB ins | AVL audit | RB audit | Led reg | Led audit")
        for r in rows:
            print(" | ".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in r))


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:] if a.isdigit()] or SIZES
    main(sizes)
