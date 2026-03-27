def __init__(self, l, r):
        self.l = l; self.r = r
        self.left: Optional['PSTNode'] = None
        self.right: Optional['PSTNode'] = None
        self.sum = 0
        self.mx = 0
        self.mn = 0

def build(arr, l, r):
    node = PSTNode(l, r)
    if l == r:
        v = arr[l]
        node.sum = v; node.mx = v; node.mn = v
        return node
    m = (l + r) // 2
    node.left = build(arr, l, m)
    node.right = build(arr, m+1, r)
    pull(node)
    return node

def pull(node):
    node.sum = node.left.sum + node.right.sum
    node.mx = max(node.left.mx, node.right.mx)
    node.mn = min(node.left.mn, node.right.mn)

def point_update(node: PSTNode, idx: int, val: int) -> PSTNode:
    if idx < node.l or idx > node.r:
        return node
    n = PSTNode(node.l, node.r)
    if node.l == node.r:
        n.left = n.right = None
        n.sum = val; n.mx = val; n.mn = val
        return n
    n.left = node.left; n.right = node.right
    m = (node.l + node.r)//2
    if idx <= m:
        n.left = point_update(node.left, idx, val)
    else:
        n.right = point_update(node.right, idx, val)
    pull(n)
    return n

def range_query(node: PSTNode, l, r):
    if node is None or l > node.r or r < node.l or l>r:
        return (0, -10**18, 10**18, 0)  # sum, max, min, count
    if l <= node.l and node.r <= r:
        cnt = node.r - node.l + 1
        return (node.sum, node.mx, node.mn, cnt)
    s1, M1, m1, c1 = range_query(node.left, l, r)
    s2, M2, m2, c2 = range_query(node.right, l, r)
    return (s1+s2, max(M1,M2), min(m1,m2), c1+c2)

def collect_values(node: PSTNode, l, r, out):
    if node is None or l > node.r or r < node.l or l>r:
        return
    if node.l == node.r:
        if l <= node.l <= r:
            out.append((node.l, node.sum))
        return
    collect_values(node.left, l, r, out)
    collect_values(node.right, l, r, out)

def batch_point_updates(root: PSTNode, updates: List[tuple]) -> PSTNode:
    # apply list of (idx,newval) updates atomically producing new root
    newroot = root
    for idx,val in updates:
        if idx < newroot.l or idx > newroot.r:
            continue
        newroot = point_update(newroot, idx, val)
    return newroot

class VersionedUnionFind:
    def __init__(self, n):
        self.n = n
        self.versions = []  # each version stores parent list and size list
        parent = list(range(n))
        size = [1]*n
        self.versions.append((parent, size))
    def clone_version(self, ver):
        p,s = self.versions[ver]
        return (p.copy(), s.copy())
    def union(self, ver, a, b):
        p,s = self.clone_version(ver)
        ra = self.find_in(p, a)
        rb = self.find_in(p, b)
        if ra == rb: 
            self.versions.append((p,s)); return len(self.versions)-1
        if s[ra] < s[rb]:
            ra,rb = rb,ra
        p[rb] = ra
        s[ra] += s[rb]
        self.versions.append((p,s))
        return len(self.versions)-1
    def unlink(self, ver, x):
        p,s = self.clone_version(ver)
        rx = self.find_in(p, x)
        if p[x] == x and s[rx]==1:
            self.versions.append((p,s)); return len(self.versions)-1
        # make x singleton: reduce size of root, set x parent to itself
        if p[x] == x:
            # root but size>1: need to pick a new root for others: keep same root but decrement size
            s[rx] -= 1
            p[x] = x
        else:
            p[x] = x
            s[rx] -= 1
        self.versions.append((p,s))
        return len(self.versions)-1
    def find_in(self, parent, x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def get_root(self, ver, x):
        p,s = self.versions[ver]
        return self.find_in(p, x)
    def members(self, ver, x):
        p,s = self.versions[ver]
        root = self.find_in(p, x)
        return [i for i in range(self.n) if self.find_in(p,i)==root]

def ultra_advanced_risk_analytics(
    initial_data: List[int],
    queries: List[List]
) -> List[int]:
    n = len(initial_data)
    lock = Lock()
    if n==0:
        return []
    arr = {i: initial_data[i] for i in range(n)}
    root0 = build(arr, 0, n-1)
    roots = [root0]
    uf = VersionedUnionFind(n)
    # initial UF version 0 corresponds to initial segment tree version 0
    # We'll align versions: roots[i] corresponds to uf.versions[i]
    results = []
    for q in queries:
        qt = q[0]
        if qt == "update":
            _, idx, newv = q
            if not (0 <= idx < n):
                # copy previous version
                roots.append(roots[-1]); uf.versions.append(uf.versions[-1][0].copy() if False else uf.versions[-1][0].copy() if False else uf.versions[-1])
                continue
            with lock:
                ver = len(roots)-1
                # operate on latest uf version
                # find group members in latest UF
                members = uf.members(ver, idx)
                updates = []
                oldx = range_query(roots[ver], idx, idx)[0]
                if oldx == 0:
                    # skip cascade, just point update that index
                    updates = [(idx, newv)]
                else:
                    for m in members:
                        oldm = range_query(roots[ver], m, m)[0]
                        if m == idx:
                            updates.append((m, newv))
                        else:
                            # proportional: new = (oldm * newv) // oldx
                            nv = (oldm * newv) // oldx
                            updates.append((m, nv))
                newroot = batch_point_updates(roots[ver], updates)
                roots.append(newroot)
                # UF version unchanged structure - clone previous
                prev_p, prev_s = uf.versions[-1]
                uf.versions.append((prev_p.copy(), prev_s.copy()))
        elif qt == "range_query":
            _, l, r, mode, version = q
            if not (0 <= version < len(roots)) or l>r or l<0 or r>=n:
                results.append(0); continue
            node = roots[version]
            s,mx,mn,c = range_query(node, l, r)
            if mode == "sum":
                results.append(s)
            elif mode == "max":
                results.append(mx if c>0 else 0)
            elif mode == "min":
                results.append(mn if c>0 else 0)
            elif mode == "avg":
                results.append(s//c if c>0 else 0)
            else:
                results.append(0)
        elif qt == "link":
            _, a, b = q
            if not (0<=a<n and 0<=b<n) or a==b:
                # still create new version copies
                roots.append(roots[-1]); prev_p, prev_s = uf.versions[-1]; uf.versions.append((prev_p.copy(), prev_s.copy()))
                continue
            # union on latest version index
            newver_idx = uf.union(len(uf.versions)-1, a, b)
            # ensure roots list aligned: add copy of latest root
            roots.append(roots[-1])
        elif qt == "unlink":
            _, x = q
            if not (0<=x<n):
                roots.append(roots[-1]); prev_p, prev_s = uf.versions[-1]; uf.versions.append((prev_p.copy(), prev_s.copy()))
                continue
            newver_idx = uf.unlink(len(uf.versions)-1, x)
            roots.append(roots[-1])
        elif qt == "conditional_update":
            # ["conditional_update", start, end, condition, threshold, new_value]
            # for between: threshold is lower bound, new_value is upper bound, and actual new_value is in next param
            with lock:
                if len(q) < 6:
                    roots.append(roots[-1]); uf.versions.append((uf.versions[-1][0].copy(), uf.versions[-1][1].copy()))
                    continue
                _, l, r, cond = q[0], q[1], q[2], q[3]
                if not (0<=l<=r<n):
                    roots.append(roots[-1]); uf.versions.append((uf.versions[-1][0].copy(), uf.versions[-1][1].copy()))
                    continue
                ver = len(roots)-1
                node = roots[ver]
                vals = []
                collect_values(node, l, r, vals)
                updates = []
                if cond == "gt":
                    thr = q[4]; newv = q[5]
                    for idx, val in vals:
                        if val > thr:
                            updates.append((idx, newv))
                elif cond == "lt":
                    thr = q[4]; newv = q[5]
                    for idx, val in vals:
                        if val < thr:
                            updates.append((idx, newv))
                elif cond == "eq":
                    thr = q[4]; newv = q[5]
                    for idx, val in vals:
                        if val == thr:
                            updates.append((idx, newv))
                elif cond == "between":
                    low = q[4]; high = q[5]; newv = q[6]
                    for idx, val in vals:
                        if low <= val <= high:
                            updates.append((idx, newv))
                newroot = batch_point_updates(roots[ver], updates)
                roots.append(newroot)
                prev_p, prev_s = uf.versions[-1]
                uf.versions.append((prev_p.copy(), prev_s.copy()))
        elif qt == "group_query":
            _, idx, version = q
            if not (0<=idx<n) or not (0<=version < len(roots)):
                results.append(0); continue
            # get group members at that version (uf version aligned by index)
            if version >= len(uf.versions):
                results.append(0); continue
            members = uf.members(version, idx)
            s = 0
            for m in members:
                s += range_query(roots[version], m, m)[0]
            results.append(s)
        elif qt == "version_count":
            # versions are count of roots (they are aligned with uf.versions)
            results.append(len(roots))
        else:
            # unknown: ignore
            pass
    return results