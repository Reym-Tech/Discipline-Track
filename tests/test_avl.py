"""AVL seam spec: insert/search/delete/inorder, balance invariant."""
import math
import random


def _check_balanced(tree):
    def rec(node):
        if node is None:
            return 0
        lh = rec(node.left)
        rh = rec(node.right)
        assert abs(lh - rh) <= 1, f"unbalanced at key {node.key}: {lh} vs {rh}"
        assert node.height == 1 + max(lh, rh)
        return node.height

    if tree.root is not None:
        rec(tree.root)


def test_avl_inorder_sorted_and_searchable():
    from src.avl import AVLTree

    t = AVLTree()
    for k in [30, 20, 40, 10, 25, 35, 50]:
        t.insert(k, f"v{k}")
    assert [k for k, _ in t.inorder()] == [10, 20, 25, 30, 35, 40, 50]
    assert t.search(25) == "v25"
    assert t.search(99) is None
    _check_balanced(t)


def test_avl_duplicate_key_upserts_value():
    from src.avl import AVLTree

    t = AVLTree()
    t.insert(1, "a")
    t.insert(1, "b")
    assert t.search(1) == "b"
    assert len(t) == 1


def test_avl_delete_and_composite_tuple_keys():
    from src.avl import AVLTree

    t = AVLTree()
    keys = [(3, 1002), (1, 1001), (5, 1003), (3, 1001), (1, 1005)]
    for k in keys:
        t.insert(k, k)
    assert [k for k, _ in t.inorder()] == sorted(keys)
    _check_balanced(t)
    t.delete((3, 1002))
    assert t.search((3, 1002)) is None
    assert [k for k, _ in t.inorder()] == sorted(set(keys) - {(3, 1002)})
    _check_balanced(t)


def test_avl_random_stress_stays_balanced_and_sorted():
    from src.avl import AVLTree

    rng = random.Random(42)
    keys = rng.sample(range(10_000), 300)
    t = AVLTree()
    for k in keys:
        t.insert(k, k)
    assert [k for k, _ in t.inorder()] == sorted(keys)
    _check_balanced(t)
    # AVL height bound: h <= ~1.44*log2(n+2)
    assert t.root.height <= 1.45 * math.log2(len(keys) + 2) + 1
    for k in keys:
        assert t.search(k) == k
