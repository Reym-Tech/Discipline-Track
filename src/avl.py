"""AVLTree: strict-balance index. Internal implementation of DisciplineLedger.

Interface (small): insert(key, value) upserts, search(key) -> value|None,
delete(key), inorder() -> [(key, value)] ascending, len(), contains.
Keys must be mutually comparable (int, or (demerits, student_id) tuples).
"""
from __future__ import annotations

from typing import Any, Generic, Iterator, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class _Node(Generic[K, V]):
    __slots__ = ("key", "value", "left", "right", "height")

    def __init__(self, key: K, value: V):
        self.key = key
        self.value = value
        self.left: Optional["_Node[K, V]"] = None
        self.right: Optional["_Node[K, V]"] = None
        self.height = 1


class AVLTree(Generic[K, V]):
    def __init__(self) -> None:
        self.root: Optional[_Node[K, V]] = None
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: K) -> bool:
        return self._contains_key(key)

    def _contains_key(self, key: K) -> bool:
        node = self.root
        while node is not None:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    # -- queries ---------------------------------------------------------
    def search(self, key: K) -> Optional[V]:
        node = self.root
        while node is not None:
            if key == node.key:
                return node.value
            node = node.left if key < node.key else node.right
        return None

    def inorder(self) -> list[tuple[K, V]]:
        out: list[tuple[K, V]] = []
        self._inorder(self.root, out)
        return out

    def _inorder(self, node: Optional[_Node[K, V]], out: list) -> None:
        if node is None:
            return
        self._inorder(node.left, out)
        out.append((node.key, node.value))
        self._inorder(node.right, out)

    def __iter__(self) -> Iterator[tuple[K, V]]:
        return iter(self.inorder())

    # -- mutation --------------------------------------------------------
    def insert(self, key: K, value: V) -> None:
        existed = self._contains_key(key)
        self.root = self._insert(self.root, key, value)
        if not existed:
            self._size += 1

    def _insert(self, node: Optional[_Node[K, V]], key: K, value: V) -> _Node[K, V]:
        if node is None:
            return _Node(key, value)
        if key == node.key:
            node.value = value
            return node
        if key < node.key:
            node.left = self._insert(node.left, key, value)
        else:
            node.right = self._insert(node.right, key, value)
        return self._rebalance(node)

    def delete(self, key: K) -> bool:
        if not self._contains_key(key):
            return False
        self.root = self._delete(self.root, key)
        self._size -= 1
        return True

    def _delete(self, node: Optional[_Node[K, V]], key: K) -> Optional[_Node[K, V]]:
        if node is None:
            return None
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            succ = self._min_node(node.right)
            node.key, node.value = succ.key, succ.value
            node.right = self._delete(node.right, succ.key)
        return self._rebalance(node) if node is not None else None

    @staticmethod
    def _min_node(node: _Node[K, V]) -> _Node[K, V]:
        while node.left is not None:
            node = node.left
        return node

    # -- balancing (private) ---------------------------------------------
    @staticmethod
    def _h(node: Optional[_Node]) -> int:
        return node.height if node else 0

    def _rebalance(self, node: _Node[K, V]) -> _Node[K, V]:
        node.height = 1 + max(self._h(node.left), self._h(node.right))
        balance = self._h(node.left) - self._h(node.right)
        # Left heavy
        if balance > 1:
            assert node.left is not None
            if self._h(node.left.left) < self._h(node.left.right):
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)
        # Right heavy
        if balance < -1:
            assert node.right is not None
            if self._h(node.right.right) < self._h(node.right.left):
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)
        return node

    @staticmethod
    def _rotate_right(y: _Node[K, V]) -> _Node[K, V]:
        assert y.left is not None
        x = y.left
        t2 = x.right
        x.right = y
        y.left = t2
        y.height = 1 + max(AVLTree._h(y.left), AVLTree._h(y.right))
        x.height = 1 + max(AVLTree._h(x.left), AVLTree._h(x.right))
        return x

    @staticmethod
    def _rotate_left(x: _Node[K, V]) -> _Node[K, V]:
        assert x.right is not None
        y = x.right
        t2 = y.left
        y.left = x
        x.right = t2
        x.height = 1 + max(AVLTree._h(x.left), AVLTree._h(x.right))
        y.height = 1 + max(AVLTree._h(y.left), AVLTree._h(y.right))
        return y

    def __repr__(self) -> str:  # pragma: no cover
        return f"AVLTree(size={self._size})"

    # test helper: allow Any value checks without confusion
    def get(self, key: K, default: Any = None) -> Any:
        found = self.search(key)
        return default if found is None and not self._contains_key(key) else found
