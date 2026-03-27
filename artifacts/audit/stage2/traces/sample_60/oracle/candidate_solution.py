from typing import List, Tuple, Optional
import random

class Node:
    __slots__ = ("key","prio","cnt","left","right","size","minv","maxv","last_ts","volume","risk")
    def __init__(self, key:int, prio:int, cnt:int=1, left=None, right=None, ts:int=0):
        self.key = key
        self.prio = prio
        self.cnt = cnt
        self.left = left
        self.right = right
        self.size = 0
        self.minv = key
        self.maxv = key
        self.last_ts = ts
        self.volume = cnt
        self.risk = 0.0
        pull(self)

def clone(n: Optional[Node]) -> Optional[Node]:
    if n is None:
        return None
    m = Node(n.key, n.prio, n.cnt, n.left, n.right, n.last_ts)
    m.size, m.minv, m.maxv, m.volume, m.risk = n.size, n.minv, n.maxv, n.volume, n.risk
    return m

def sz(t: Optional[Node]) -> int:
    return t.size if t else 0

def pull(t: Node) -> None:
    t.size = t.cnt + sz(t.left) + sz(t.right)
    t.minv = t.left.minv if t.left else t.key
    t.maxv = t.right.maxv if t.right else t.key
    t.volume = t.cnt
    lsz, rsz = sz(t.left), sz(t.right)
    t.risk = abs(lsz - rsz) / (1 + t.size)

def rot_right(t: Node) -> Node:
    t = clone(t)
    x = clone(t.left)
    t.left = x.right
    pull(t)
    x.right = t
    pull(x)
    return x

def rot_left(t: Node) -> Node:
    t = clone(t)
    x = clone(t.right)
    t.right = x.left
    pull(t)
    x.left = t
    pull(x)
    return x

def insert(t: Optional[Node], key:int, ts:int) -> Node:
    if t is None:
        return Node(key, random.randint(1, 2**31-1), 1, None, None, ts)
    t = clone(t)
    if key == t.key:
        t.cnt += 1
        t.last_ts = ts
    elif key < t.key:
        t.left = insert(t.left, key, ts)
        if t.left.prio < t.prio:
            t = rot_right(t)
    else:
        t.right = insert(t.right, key, ts)
        if t.right.prio < t.prio:
            t = rot_left(t)
    pull(t)
    return t

def erase_one(t: Optional[Node], key:int, ts:int) -> Optional[Node]:
    if t is None:
        return None
    t = clone(t)
    if key == t.key:
        if t.cnt > 1:
            t.cnt -= 1
            t.last_ts = ts
        else:
            if not t.left and not t.right:
                return None
            if not t.left:
                t = rot_left(t)
                t.left = erase_one(t.left, key, ts)
            elif not t.right:
                t = rot_right(t)
                t.right = erase_one(t.right, key, ts)
            else:
                if t.left.prio < t.right.prio:
                    t = rot_right(t)
                    t.right = erase_one(t.right, key, ts)
                else:
                    t = rot_left(t)
                    t.left = erase_one(t.left, key, ts)
            if t is None:
                return None
    elif key < t.key:
        t.left = erase_one(t.left, key, ts)
    else:
        t.right = erase_one(t.right, key, ts)
    pull(t)
    return t

def count(t: Optional[Node], key:int) -> int:
    cur = t
    while cur:
        if key == cur.key:
            return cur.cnt
        cur = cur.left if key < cur.key else cur.right
    return 0

def find_le(t: Optional[Node], x:int) -> Optional[int]:
    cur, ans = t, None
    while cur:
        if cur.key <= x:
            ans = cur.key
            cur = cur.right
        else:
            cur = cur.left
    return ans

class PersistentStockTree:
    """Persistent treap with versioned roots; rollback is an O(1) version pointer move."""
    def __init__(self):
        self.versions: List[Optional[Node]] = [None]  # version 0 = empty
        self.cur = 0
        self.ts = 0

    @property
    def root(self) -> Optional[Node]:
        return self.versions[self.cur]

    def _push_version(self, new_root: Optional[Node]) -> None:
        if new_root is self.root:
            return
        if self.cur != len(self.versions) - 1:
            self.versions = self.versions[:self.cur+1]
        self.versions.append(new_root)
        self.cur += 1

    def do_insert(self, v:int) -> None:
        self.ts += 1
        self._push_version(insert(self.root, v, self.ts))

    def do_delete(self, v:int) -> None:
        if count(self.root, v) == 0:
            return  # no effective change → no new version
        self.ts += 1
        self._push_version(erase_one(self.root, v, self.ts))

    def do_bulk_insert(self, pivot:int) -> None:
        # per prompt: default bulk_insert inserts exactly `pivot` once
        self.do_insert(pivot)

    def do_query_le(self, x:int) -> Optional[int]:
        return find_le(self.root, x)

    def do_rollback(self, k:int) -> None:
        if k <= 0:
            return
        self.cur = max(0, self.cur - k)

def update_and_query_stock_tree(operations: List[Tuple[str, int]]) -> List[Optional[float]]:
    pst = PersistentStockTree()
    out: List[Optional[float]] = []
    for op, val in operations:
        if op == 'insert':
            pst.do_insert(val)
            out.append(None)
        elif op == 'delete':
            pst.do_delete(val)
            out.append(None)
        elif op == 'bulk_insert':
            pst.do_bulk_insert(val)
            out.append(None)
        elif op == 'rollback':
            pst.do_rollback(val)
            out.append(None)
        elif op == 'query':
            res = pst.do_query_le(val)
            out.append(float(res) if res is not None else None)
        else:
            raise ValueError(f"Unknown operation: {op}")
    return out