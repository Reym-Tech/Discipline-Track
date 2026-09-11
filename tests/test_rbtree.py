"""Red-Black seam spec: insert/search/delete/inorder + RB invariants."""
import random


def _check_rb(tree):
    RED, BLACK = True, False
    NIL = getattr(tree, "NIL", None)

    def is_leaf(node):
        return node is None or (NIL is not None and node is NIL)

    def left_of(node):
        l = node.left
        return None if (l is None or (NIL is not None and l is NIL)) else l

    def right_of(node):
        r = node.right
        return None if (r is None or (NIL is not None and r is NIL)) else r

    root = tree.root
    if root is None or (NIL is not None and root is NIL):
        return
    assert root.color == BLACK, "root must be black"

    def rec(node):
        if node is None or (NIL is not None and node is NIL):
            return 1  # null/sentinel leaves count as black
        if node.color == RED:
            l, r = left_of(node), right_of(node)
            if l is not None:
                assert l.color == BLACK, "red-red violation (left)"
            if r is not None:
                assert r.color == BLACK, "red-red violation (right)"
        lh = rec(node.left if node.left is not NIL else None) if NIL is not None else rec(node.left)
        rh = rec(node.right if node.right is not NIL else None) if NIL is not None else rec(node.right)
        assert lh == rh, f"black-height mismatch at {node.key}: {lh} vs {rh}"
        return lh + (1 if node.color == BLACK else 0)

    rec(root)


def test_rb_inorder_sorted_and_searchable():
    from src.rbtree import RBTree

    t = RBTree()
    for k in [1003, 1001, 1002, 1005, 1004]:
        t.insert(k, f"s{k}")
    assert [k for k, _ in t.inorder()] == [1001, 1002, 1003, 1004, 1005]
    assert t.search(1002) == "s1002"
    assert t.search(9999) is None
    _check_rb(t)


def test_rb_duplicate_key_upserts_value():
    from src.rbtree import RBTree

    t = RBTree()
    t.insert(7, "a")
    t.insert(7, "b")
    assert t.search(7) == "b"
    assert len(t) == 1


def test_rb_delete_keeps_invariants():
    from src.rbtree import RBTree

    t = RBTree()
    for k in [20, 10, 30, 5, 15, 25, 35]:
        t.insert(k, k)
    t.delete(10)
    t.delete(30)
    assert [k for k, _ in t.inorder()] == [5, 15, 20, 25, 35]
    _check_rb(t)


def test_rb_random_stress():
    from src.rbtree import RBTree

    rng = random.Random(7)
    keys = rng.sample(range(10_000), 300)
    t = RBTree()
    for k in keys:
        t.insert(k, k)
    assert [k for k, _ in t.inorder()] == sorted(keys)
    _check_rb(t)
    for k in keys:
        assert t.search(k) == k
