from typing import List, Optional
from threading import Lock


class LNode:
    __slots__ = ("l", "r", "sum", "mn", "mx", "len", "lc", "rc", "tag_assign", "tag_a_num", "tag_a_den", "tag_b")
    def __init__(self, l: int, r: int):
        self.l = l
        self.r = r
        self.len = r - l + 1
        self.sum = 0
        self.mn = 0
        self.mx = 0
        self.lc: Optional["LNode"] = None
        self.rc: Optional["LNode"] = None
        self.tag_assign: Optional[int] = None
        self.tag_a_num = 1
        self.tag_a_den = 1
        self.tag_b = 0


class PLazySegTree:
    def __init__(self, arr: List[int]):
        self.n = len(arr)
        self.root = self._build(0, self.n - 1, arr)

    @classmethod
    def from_root(cls, n: int, root: LNode) -> "PLazySegTree":
        obj = cls.__new__(cls)
        obj.n = n
        obj.root = root
        return obj

    def _build(self, l: int, r: int, arr: List[int]) -> LNode:
        node = LNode(l, r)
        if l == r:
            v = arr[l]
            node.sum = v
            node.mn = v
            node.mx = v
            return node
        m = (l + r) // 2
        node.lc = self._build(l, m, arr)
        node.rc = self._build(m + 1, r, arr)
        self._pull(node)
        return node

    def _clone(self, x: LNode) -> LNode:
        y = LNode(x.l, x.r)
        y.sum = x.sum
        y.mn = x.mn
        y.mx = x.mx
        y.len = x.len
        y.lc = x.lc
        y.rc = x.rc
        y.tag_assign = x.tag_assign
        y.tag_a_num = x.tag_a_num
        y.tag_a_den = x.tag_a_den
        y.tag_b = x.tag_b
        return y

    def _pull(self, x: LNode):
        x.sum = x.lc.sum + x.rc.sum
        x.mn = min(x.lc.mn, x.rc.mn)
        x.mx = max(x.lc.mx, x.rc.mx)

    def _apply_assign(self, x: LNode, c: int):
        x.tag_assign = c
        x.tag_a_num = 1
        x.tag_a_den = 1
        x.tag_b = 0
        x.sum = c * x.len
        x.mn = c
        x.mx = c

    def _apply_affine(self, x: LNode, a_num: int, a_den: int, b: int):
        x.sum = (a_num * x.sum) // a_den + b * x.len
        if a_num >= 0:
            x.mn = (a_num * x.mn) // a_den + b
            x.mx = (a_num * x.mx) // a_den + b
            if x.mn > x.mx:
                x.mn, x.mx = x.mx, x.mn
        else:
            lo = (a_num * x.mx) // a_den + b
            hi = (a_num * x.mn) // a_den + b
            x.mn = min(lo, hi)
            x.mx = max(lo, hi)
        if x.tag_assign is not None:
            c = x.tag_assign
            c = (a_num * c) // a_den + b
            self._apply_assign(x, c)
        else:
            oa_num, oa_den, ob = x.tag_a_num, x.tag_a_den, x.tag_b
            na_num = a_num * oa_num
            na_den = a_den * oa_den
            nb = (a_num * ob) // a_den + b
            x.tag_a_num, x.tag_a_den, x.tag_b = na_num, na_den, nb

    def _push(self, x: LNode):
        if x.l == x.r:
            x.tag_assign = None
            x.tag_a_num = 1
            x.tag_a_den = 1
            x.tag_b = 0
            return
        if x.lc is None or x.rc is None:
            return
        if x.tag_assign is not None:
            c = x.tag_assign
            x.lc = self._clone(x.lc)
            x.rc = self._clone(x.rc)
            self._apply_assign(x.lc, c)
            self._apply_assign(x.rc, c)
            x.tag_assign = None
        if not (x.tag_a_num == 1 and x.tag_a_den == 1 and x.tag_b == 0):
            a_num, a_den, b = x.tag_a_num, x.tag_a_den, x.tag_b
            x.lc = self._clone(x.lc)
            x.rc = self._clone(x.rc)
            self._apply_affine(x.lc, a_num, a_den, b)
            self._apply_affine(x.rc, a_num, a_den, b)
            x.tag_a_num = 1
            x.tag_a_den = 1
            x.tag_b = 0

    def _range_assign(self, x: LNode, l: int, r: int, c: int) -> LNode:
        x = self._clone(x)
        if l <= x.l and x.r <= r:
            self._apply_assign(x, c)
            return x
        self._push(x)
        m = (x.l + x.r) // 2
        if l <= m:
            x.lc = self._range_assign(x.lc, l, r, c)
        if r > m:
            x.rc = self._range_assign(x.rc, l, r, c)
        self._pull(x)
        return x

    def _range_affine(self, x: LNode, l: int, r: int, a_num: int, a_den: int, b: int) -> LNode:
        x = self._clone(x)
        if l <= x.l and x.r <= r:
            self._apply_affine(x, a_num, a_den, b)
            return x
        self._push(x)
        m = (x.l + x.r) // 2
        if l <= m:
            x.lc = self._range_affine(x.lc, l, r, a_num, a_den, b)
        if r > m:
            x.rc = self._range_affine(x.rc, l, r, a_num, a_den, b)
        self._pull(x)
        return x

    def _point_get(self, x: LNode, idx: int) -> int:
        if x.l == x.r:
            return x.sum
        self._push(x)
        m = (x.l + x.r) // 2
        if idx <= m:
            return self._point_get(x.lc, idx)
        return self._point_get(x.rc, idx)

    def _range_sum(self, x: LNode, l: int, r: int) -> int:
        if r < x.l or l > x.r:
            return 0
        if l <= x.l and x.r <= r:
            return x.sum
        self._push(x)
        return self._range_sum(x.lc, l, r) + self._range_sum(x.rc, l, r)

    def _range_min(self, x: LNode, l: int, r: int) -> int:
        if r < x.l or l > x.r:
            return float("inf")
        if l <= x.l and x.r <= r:
            return x.mn
        self._push(x)
        return min(self._range_min(x.lc, l, r), self._range_min(x.rc, l, r))

    def _range_max(self, x: LNode, l: int, r: int) -> int:
        if r < x.l or l > x.r:
            return float("-inf")
        if l <= x.l and x.r <= r:
            return x.mx
        self._push(x)
        return max(self._range_max(x.lc, l, r), self._range_max(x.rc, l, r))

    def point_assign(self, idx: int, val: int) -> "PLazySegTree":
        root = self._range_assign(self.root, idx, idx, val)
        return PLazySegTree.from_root(self.n, root)

    def range_assign(self, l: int, r: int, val: int) -> "PLazySegTree":
        root = self._range_assign(self.root, l, r, val)
        return PLazySegTree.from_root(self.n, root)

    def range_affine(self, l: int, r: int, a_num: int, a_den: int, b: int = 0) -> "PLazySegTree":
        root = self._range_affine(self.root, l, r, a_num, a_den, b)
        return PLazySegTree.from_root(self.n, root)

    def range_query(self, l: int, r: int, mode: str) -> int:
        if l > r or l < 0 or r >= self.n:
            return 0
        if mode == "sum":
            return self._range_sum(self.root, l, r)
        elif mode == "max":
            res = self._range_max(self.root, l, r)
            return res if res != float("-inf") else 0
        elif mode == "min":
            res = self._range_min(self.root, l, r)
            return res if res != float("inf") else 0
        elif mode == "avg":
            total = self._range_sum(self.root, l, r)
            cnt = r - l + 1
            return total // cnt
        return 0

    def get_value(self, idx: int) -> int:
        if idx < 0 or idx >= self.n:
            return 0
        return self._point_get(self.root, idx)


class IntervalSet:
    def __init__(self):
        self.intervals: List[List[int]] = []

    def add(self, idx: int):
        ivals = self.intervals
        if not ivals:
            ivals.append([idx, idx])
            return
        lo, hi = 0, len(ivals)
        while lo < hi:
            mid = (lo + hi) // 2
            if ivals[mid][0] < idx:
                lo = mid + 1
            else:
                hi = mid
        left = lo - 1
        right = lo
        newL, newR = idx, idx
        if left >= 0 and ivals[left][1] + 1 >= idx:
            newL = ivals[left][0]
            newR = max(ivals[left][1], idx)
            ivals.pop(left)
            lo -= 1
        if right < len(ivals) and ivals[right][0] - 1 <= newR:
            newR = max(newR, ivals[right][1])
            newL = min(newL, ivals[right][0])
            ivals.pop(right)
        ivals.insert(lo if lo >= 0 else 0, [newL, newR])

    def remove(self, idx: int):
        ivals = self.intervals
        for k, interval in enumerate(ivals):
            L, R = interval[0], interval[1]
            if L <= idx <= R:
                ivals.pop(k)
                if L <= idx - 1:
                    ivals.insert(k, [L, idx - 1])
                    k += 1
                if idx + 1 <= R:
                    ivals.insert(k, [idx + 1, R])
                return

    def merge_from(self, other: "IntervalSet"):
        for interval in other.intervals:
            L, R = interval[0], interval[1]
            for i in range(L, R + 1):
                self.add(i)

    def ranges(self) -> List[List[int]]:
        return self.intervals[:]


class GroupUF:
    def __init__(self, n: int, initial: List[int]):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.sum = initial[:]
        self.count = [1] * n
        self.ivals = [IntervalSet() for _ in range(n)]
        for i in range(n):
            self.ivals[i].add(i)

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        self.sum[ra] += self.sum[rb]
        self.count[ra] += self.count[rb]
        self.ivals[ra].merge_from(self.ivals[rb])
        self.ivals[rb] = IntervalSet()
        self.sum[rb] = 0
        self.count[rb] = 0
        return True

    def unlink(self, x: int, val_x: int):
        rx = self.find(x)
        if rx == x and self.count[rx] == 1:
            self.sum[rx] = val_x
            self.count[rx] = 1
            self.ivals[rx] = IntervalSet()
            self.ivals[rx].add(x)
            return
        self.ivals[rx].remove(x)
        self.sum[rx] -= val_x
        self.count[rx] -= 1
        self.parent[x] = x
        self.rank[x] = 0
        self.sum[x] = val_x
        self.count[x] = 1
        self.ivals[x] = IntervalSet()
        self.ivals[x].add(x)

    def group_sum(self, x: int) -> int:
        return self.sum[self.find(x)]

    def group_intervals(self, x: int) -> List[List[int]]:
        return self.ivals[self.find(x)].ranges()

    def touch_value_change(self, x: int, old_val: int, new_val: int):
        r = self.find(x)
        self.sum[r] += (new_val - old_val)


class Version:
    def __init__(self, tree: PLazySegTree, uf: GroupUF):
        self.tree = tree
        self.uf = uf


class VersionedRiskAnalytics:
    def __init__(self, initial_data: List[int]):
        self.n = len(initial_data)
        self.lock = Lock()
        self.versions: List[Version] = [Version(PLazySegTree(initial_data), GroupUF(self.n, initial_data))]

    def range_query(self, L: int, R: int, mode: str, ver: int) -> int:
        if ver < 0 or ver >= len(self.versions):
            return 0
        return self.versions[ver].tree.range_query(L, R, mode)

    def update(self, idx: int, new_value: int):
        with self.lock:
            prev = self.versions[-1]
            tree = prev.tree
            uf = GroupUF(self.n, [0]*self.n)
            uf.parent = prev.uf.parent[:]
            uf.rank = prev.uf.rank[:]
            uf.sum = prev.uf.sum[:]
            uf.count = prev.uf.count[:]
            uf.ivals = [IntervalSet() for _ in range(self.n)]
            for i in range(self.n):
                uf.ivals[i].intervals = prev.uf.ivals[i].ranges()

            old_val = tree.get_value(idx)
            root = uf.find(idx)
            intervals = uf.group_intervals(idx)

            if old_val == 0:
                if uf.count[root] > 1:
                    target = None
                    for interval in intervals:
                        L, R = interval[0], interval[1]
                        if idx < L or idx > R:
                            target = L
                            break
                        else:
                            if L <= idx <= R:
                                if L < idx:
                                    target = L
                                    break
                                if idx < R:
                                    target = idx + 1
                                    break
                    if target is None:
                        target = idx
                    old_t = tree.get_value(target)
                    tree = tree.point_assign(target, new_value)
                    uf.touch_value_change(target, old_t, new_value)
                else:
                    tree = tree.point_assign(idx, new_value)
                    uf.touch_value_change(idx, old_val, new_value)
            else:
                tree = tree.point_assign(idx, new_value)
                uf.touch_value_change(idx, old_val, new_value)
                a_num, a_den = new_value, old_val
                for interval in intervals:
                    L, R = interval[0], interval[1]
                    if idx < L or idx > R:
                        tree = tree.range_affine(L, R, a_num, a_den, 0)
                    else:
                        if L <= idx - 1:
                            tree = tree.range_affine(L, idx - 1, a_num, a_den, 0)
                        if idx + 1 <= R:
                            tree = tree.range_affine(idx + 1, R, a_num, a_den, 0)

                gsum = 0
                for interval in intervals:
                    L, R = interval[0], interval[1]
                    gsum += tree.range_query(L, R, "sum")
                uf.sum[root] = gsum

            self.versions.append(Version(tree, uf))

    def link(self, i: int, j: int):
        with self.lock:
            prev = self.versions[-1]
            tree = prev.tree
            uf = GroupUF(self.n, [0]*self.n)
            uf.parent = prev.uf.parent[:]
            uf.rank = prev.uf.rank[:]
            uf.sum = prev.uf.sum[:]
            uf.count = prev.uf.count[:]
            uf.ivals = [IntervalSet() for _ in range(self.n)]
            for k in range(self.n):
                uf.ivals[k].intervals = prev.uf.ivals[k].ranges()
            if uf.union(i, j):
                self.versions.append(Version(tree, uf))

    def unlink(self, i: int):
        with self.lock:
            prev = self.versions[-1]
            tree = prev.tree
            uf = GroupUF(self.n, [0]*self.n)
            uf.parent = prev.uf.parent[:]
            uf.rank = prev.uf.rank[:]
            uf.sum = prev.uf.sum[:]
            uf.count = prev.uf.count[:]
            uf.ivals = [IntervalSet() for _ in range(self.n)]
            for k in range(self.n):
                uf.ivals[k].intervals = prev.uf.ivals[k].ranges()
            val_i = tree.get_value(i)
            uf.unlink(i, val_i)
            self.versions.append(Version(tree, uf))

    def conditional_update(self, L: int, R: int, condition: str, threshold: int, new_value: int, actual_new_value: int = None):
        with self.lock:
            prev = self.versions[-1]
            tree = prev.tree
            uf = prev.uf

            def apply_range(l: int, r: int):
                nonlocal tree
                if condition == "gt":
                    if tree.range_query(l, r, "min") > threshold:
                        tree = tree.range_assign(l, r, new_value)
                        return
                if condition == "lt":
                    if tree.range_query(l, r, "max") < threshold:
                        tree = tree.range_assign(l, r, new_value)
                        return
                if condition == "eq":
                    mn = tree.range_query(l, r, "min")
                    mx = tree.range_query(l, r, "max")
                    if mn == mx == threshold:
                        tree = tree.range_assign(l, r, new_value)
                        return
                if condition == "between":
                    low, high = threshold, new_value
                    target = actual_new_value if actual_new_value is not None else high
                    mn = tree.range_query(l, r, "min")
                    mx = tree.range_query(l, r, "max")
                    if mn >= low and mx <= high:
                        tree = tree.range_assign(l, r, target)
                        return
                if l == r:
                    v = tree.get_value(l)
                    ok = False
                    val = 0
                    if condition == "gt":
                        ok = v > threshold
                        val = new_value
                    elif condition == "lt":
                        ok = v < threshold
                        val = new_value
                    elif condition == "eq":
                        ok = v == threshold
                        val = new_value
                    elif condition == "between":
                        low, high = threshold, new_value
                        ok = low <= v <= high
                        val = actual_new_value if actual_new_value is not None else high
                    if ok:
                        tree = tree.point_assign(l, val)
                    return
                m = (l + r) // 2
                apply_range(l, m)
                apply_range(m + 1, r)

            apply_range(L, R)

            new_uf = GroupUF(self.n, [0]*self.n)
            new_uf.parent = uf.parent[:]
            new_uf.rank = uf.rank[:]
            new_uf.count = uf.count[:]
            new_uf.ivals = [IntervalSet() for _ in range(self.n)]
            for k in range(self.n):
                new_uf.ivals[k].intervals = uf.ivals[k].ranges()
            for i in range(self.n):
                if new_uf.parent[i] == i and new_uf.count[i] > 0:
                    s = 0
                    for interval in new_uf.ivals[i].ranges():
                        a, b = interval[0], interval[1]
                        s += tree.range_query(a, b, "sum")
                    new_uf.sum[i] = s

            self.versions.append(Version(tree, new_uf))

    def group_query(self, idx: int, ver: int) -> int:
        if ver < 0 or ver >= len(self.versions):
            return 0
        return self.versions[ver].uf.group_sum(idx)

    def version_count(self) -> int:
        return len(self.versions)


def ultra_advanced_risk_analytics(initial_data: List[int], queries: List[List]) -> List[int]:
    """
    Process complex queries on versioned segment tree with dynamic connectivity.
    
    Args:
        initial_data: List of initial stock values (positive integers)
        queries: List of query lists with various operation types including updates,
                range queries, linking/unlinking operations, conditional updates,
                group queries, and version counting
    
    Returns:
        List of integers containing results from queries that produce output
        (range_query, group_query, version_count)
    """
    if not initial_data:
        return []
    eng = VersionedRiskAnalytics(initial_data)
    out: List[int] = []
    for q in queries:
        op = q[0]
        if op == "update":
            eng.update(q[1], q[2])
        elif op == "range_query":
            out.append(eng.range_query(q[1], q[2], q[3], q[4]))
        elif op == "link":
            eng.link(q[1], q[2])
        elif op == "unlink":
            eng.unlink(q[1])
        elif op == "conditional_update":
            L, R, cond = q[1], q[2], q[3]
            thr, val = q[4], q[5]
            target = q[6] if len(q) > 6 else None
            eng.conditional_update(L, R, cond, thr, val, target)
        elif op == "group_query":
            out.append(eng.group_query(q[1], q[2]))
        elif op == "version_count":
            out.append(eng.version_count())
    return out


if __name__ == "__main__":
    initial_data = [100, 200, 300, 400, 500]
    queries = [
        ["range_query", 0, 4, "sum", 0],
        ["update", 2, 350],
        ["range_query", 1, 3, "sum", 1],
        ["link", 1, 2],
        ["update", 1, 250],
        ["range_query", 0, 4, "sum", 3],
        ["range_query", 1, 3, "max", 1],
        ["unlink", 2],
        ["update", 2, 320],
        ["group_query", 1, 3],
        ["conditional_update", 0, 4, "gt", 300, 350],
        ["range_query", 0, 4, "avg", 6],
        ["version_count"],
    ]
    print(ultra_advanced_risk_analytics(initial_data, queries))