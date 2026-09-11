"""RBTree: relaxed-balance index keyed by student_id. Internal implementation.

Interface (small): insert(key, value) upserts, search(key) -> value|None,
delete(key) -> bool, inorder() -> [(key, value)] ascending, len().
CLRS sentinel-based implementation; null leaves are the shared NIL (black).
"""
from __future__ import annotations

from typing import Generic, Iterator, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")

RED = True
BLACK = False


class _Node(Generic[K, V]):
    __slots__ = ("key", "value", "color", "left", "right", "parent")

    def __init__(self, key: K = None, value: V = None, color: bool = BLACK):  # type: ignore[assignment]
        self.key = key
        self.value = value
        self.color = color
        self.left: "_Node[K, V]" = self  # type: ignore[assignment]
        self.right: "_Node[K, V]" = self  # type: ignore[assignment]
        self.parent: "_Node[K, V]" = self  # type: ignore[assignment]


class RBTree(Generic[K, V]):
    def __init__(self) -> None:
        self.NIL: _Node[K, V] = _Node()
        self.NIL.left = self.NIL.right = self.NIL.parent = self.NIL
        self.root: _Node[K, V] = self.NIL
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: K) -> bool:
        return self._find(key) is not self.NIL

    # -- queries ---------------------------------------------------------
    def _find(self, key: K) -> _Node[K, V]:
        node = self.root
        while node is not self.NIL:
            if key == node.key:
                return node
            node = node.left if key < node.key else node.right  # type: ignore[operator]
        return self.NIL

    def search(self, key: K) -> Optional[V]:
        node = self._find(key)
        return None if node is self.NIL else node.value

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        node = self._find(key)
        return default if node is self.NIL else node.value

    def inorder(self) -> list[tuple[K, V]]:
        out: list[tuple[K, V]] = []
        self._inorder(self.root, out)
        return out

    def _inorder(self, node: _Node[K, V], out: list) -> None:
        if node is self.NIL:
            return
        self._inorder(node.left, out)
        out.append((node.key, node.value))
        self._inorder(node.right, out)

    def __iter__(self) -> Iterator[tuple[K, V]]:
        return iter(self.inorder())

    # -- mutation --------------------------------------------------------
    def insert(self, key: K, value: V) -> None:
        existing = self._find(key)
        if existing is not self.NIL:
            existing.value = value  # upsert, no structural change
            return
        z: _Node[K, V] = _Node(key, value, RED)
        z.left = z.right = self.NIL
        y = self.NIL
        x = self.root
        while x is not self.NIL:
            y = x
            x = x.left if z.key < x.key else x.right  # type: ignore[operator]
        z.parent = y
        if y is self.NIL:
            self.root = z
        elif z.key < y.key:  # type: ignore[operator]
            y.left = z
        else:
            y.right = z
        self._size += 1
        self._insert_fixup(z)

    def delete(self, key: K) -> bool:
        z = self._find(key)
        if z is self.NIL:
            return False
        self._delete_node(z)
        self._size -= 1
        return True

    # -- CLRS internals (private) ----------------------------------------
    def _left_rotate(self, x: _Node[K, V]) -> None:
        y = x.right
        x.right = y.left
        if y.left is not self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is self.NIL:
            self.root = y
        elif x is x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _right_rotate(self, y: _Node[K, V]) -> None:
        x = y.left
        y.left = x.right
        if x.right is not self.NIL:
            x.right.parent = y
        x.parent = y.parent
        if y.parent is self.NIL:
            self.root = x
        elif y is y.parent.right:
            y.parent.right = x
        else:
            y.parent.left = x
        x.right = y
        y.parent = x

    def _insert_fixup(self, z: _Node[K, V]) -> None:
        while z.parent.color == RED:
            if z.parent is z.parent.parent.left:
                y = z.parent.parent.right
                if y.color == RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.right:
                        z = z.parent
                        self._left_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                y = z.parent.parent.left
                if y.color == RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._left_rotate(z.parent.parent)
        self.root.color = BLACK

    def _transplant(self, u: _Node[K, V], v: _Node[K, V]) -> None:
        if u.parent is self.NIL:
            self.root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def _minimum(self, node: _Node[K, V]) -> _Node[K, V]:
        while node.left is not self.NIL:
            node = node.left
        return node

    def _delete_node(self, z: _Node[K, V]) -> None:
        y = z
        y_original_color = y.color
        if z.left is self.NIL:
            x = z.right
            self._transplant(z, z.right)
        elif z.right is self.NIL:
            x = z.left
            self._transplant(z, z.left)
        else:
            y = self._minimum(z.right)
            y_original_color = y.color
            x = y.right
            if y.parent is z:
                x.parent = y
            else:
                self._transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self._transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color
        if y_original_color == BLACK:
            self._delete_fixup(x)

    def _delete_fixup(self, x: _Node[K, V]) -> None:
        while x is not self.root and x.color == BLACK:
            if x is x.parent.left:
                w = x.parent.right
                if w.color == RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._left_rotate(x.parent)
                    w = x.parent.right
                if w.left.color == BLACK and w.right.color == BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.right.color == BLACK:
                        w.left.color = BLACK
                        w.color = RED
                        self._right_rotate(w)
                        w = x.parent.right
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.right.color = BLACK
                    self._left_rotate(x.parent)
                    x = self.root
            else:
                w = x.parent.left
                if w.color == RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._right_rotate(x.parent)
                    w = x.parent.left
                if w.right.color == BLACK and w.left.color == BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.left.color == BLACK:
                        w.right.color = BLACK
                        w.color = RED
                        self._left_rotate(w)
                        w = x.parent.left
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.left.color = BLACK
                    self._right_rotate(x.parent)
                    x = self.root
        x.color = BLACK

    def __repr__(self) -> str:  # pragma: no cover
        return f"RBTree(size={self._size})"
