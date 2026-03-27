from typing import Dict, Optional, Any, List, Tuple, Union


class PMap:
    __slots__ = ("base", "chg")
    def __init__(self, base: Optional["PMap"] = None, chg: Optional[Dict[Any, Any]] = None):
        self.base = base
        self.chg = chg if chg is not None else {}

    def get(self, key: Any, default: Any = None):
        node = self
        while node is not None:
            if key in node.chg:
                return node.chg[key]
            node = node.base
        return default

    def set(self, key: Any, value: Any) -> "PMap":
        return PMap(self, {key: value})

    def bulk_set(self, items: Dict[Any, Any]) -> "PMap":
        return PMap(self, dict(items))


# ------------------------------------------------------------
# Version: persistent state for one timeline node.
# - parent, depth
# - up[k], minc[k], maxc[k] for binary lifting path attributes
# - edges: persistent edge log (child->parent) with capacities
# ------------------------------------------------------------
class Version:
    __slots__ = ("parent", "depth", "up", "minc", "maxc", "edges")
    def __init__(self, LOG: int):
        self.parent: PMap = PMap()
        self.depth:  PMap = PMap()
        self.up:     List[PMap] = [PMap() for _ in range(LOG)]
        self.minc:   List[PMap] = [PMap() for _ in range(LOG)]
        self.maxc:   List[PMap] = [PMap() for _ in range(LOG)]
        self.edges:  PMap = PMap()

    def fork_from(self, other: "Version"):
        self.parent = other.parent
        self.depth  = other.depth
        self.up     = other.up[:]
        self.minc   = other.minc[:]
        self.maxc   = other.maxc[:]
        self.edges  = other.edges


class PersistentDisjointSet:
    """
    Persistent (versioned) DSU with:
      - union(a,b,cap): add a single tree edge, new version
      - split(a,b): cut a direct parent-child edge, new version
      - branch(from_version): clone version, new version
      - merge_versions(vX, vY): replay vY's surviving edges on a clone of vX, new version (bool success)
      - find(a,b): connectivity in the given version
      - attributes(a,b): [min_cap, max_cap] on the (unique) tree path; [] if disconnected.
    Conventions:
      - Each version is a forest (no cycles per version).
      - attributes(a,a) returns [0, 0].
    """
    def __init__(self, max_nodes_hint: int = 10**5):
        LOG = 17
        while (1 << LOG) <= max(2, max_nodes_hint):
            LOG += 1
        self.LOG = LOG

        self.versions: List[Version] = []
        v0 = Version(self.LOG)
        self.versions.append(v0)

    # ---------- per-version accessors ----------
    def _get_parent(self, ver: Version, x: int) -> Optional[int]:
        return ver.parent.get(x, None)

    def _get_depth(self, ver: Version, x: int) -> int:
        return ver.depth.get(x, 0)

    def _get_up(self, ver: Version, k: int, x: int) -> Optional[int]:
        return ver.up[k].get(x, None)

    def _get_minc(self, ver: Version, k: int, x: int) -> Optional[int]:
        return ver.minc[k].get(x, None)

    def _get_maxc(self, ver: Version, k: int, x: int) -> Optional[int]:
        return ver.maxc[k].get(x, None)

    def _set_parent(self, ver: Version, x: int, p: Optional[int]):
        ver.parent = ver.parent.set(x, p)

    def _set_depth(self, ver: Version, x: int, d: int):
        ver.depth = ver.depth.set(x, d)

    def _set_up0_and_cap(self, ver: Version, x: int, p: Optional[int], cap: Optional[int]):
        ver.up[0] = ver.up[0].set(x, p)
        ver.minc[0] = ver.minc[0].set(x, None if cap is None else cap)
        ver.maxc[0] = ver.maxc[0].set(x, None if cap is None else cap)

    def _rebuild_lift_for_node(self, ver: Version, x: int):
        for k in range(1, self.LOG):
            mid = self._get_up(ver, k-1, x)
            if mid is None:
                ver.up[k]   = ver.up[k].set(x, None)
                ver.minc[k] = ver.minc[k].set(x, None)
                ver.maxc[k] = ver.maxc[k].set(x, None)
            else:
                top = self._get_up(ver, k-1, mid)
                ver.up[k]   = ver.up[k].set(x, top)

                a = self._get_minc(ver, k-1, x)
                b = self._get_minc(ver, k-1, mid)
                cmin = a if b is None or (a is not None and a < b) else b

                a2 = self._get_maxc(ver, k-1, x)
                b2 = self._get_maxc(ver, k-1, mid)
                cmax = a2 if b2 is None or (a2 is not None and a2 > b2) else b2

                ver.minc[k] = ver.minc[k].set(x, cmin)
                ver.maxc[k] = ver.maxc[k].set(x, cmax)

    def _root(self, ver: Version, x: int) -> int:
        while True:
            p = self._get_parent(ver, x)
            if p is None:
                return x
            x = p

    def _connected(self, ver: Version, a: int, b: int) -> bool:
        return self._root(ver, a) == self._root(ver, b)

    # ---------- LCA / path attributes ----------
    def _lift(self, ver: Version, x: int, steps: int):
        mn, mx = None, None
        k = 0
        while steps > 0:
            if steps & 1:
                upk = self._get_up(ver, k, x)
                if upk is None:
                    return None, mn, mx
                emn = self._get_minc(ver, k, x)
                emx = self._get_maxc(ver, k, x)
                if emn is not None:
                    mn = emn if mn is None else min(mn, emn)
                if emx is not None:
                    mx = emx if mx is None else max(mx, emx)
                x = upk
            steps >>= 1
            k += 1
        return x, mn, mx

    def _path_attributes(self, ver: Version, a: int, b: int) -> List[int]:
        if not self._connected(ver, a, b):
            return []
        if a == b:
            return [0, 0]

        da = self._get_depth(ver, a)
        db = self._get_depth(ver, b)
        mn, mx = None, None

        if da > db:
            a, mna, mxa = self._lift(ver, a, da - db)
            if a is None:
                return []
            if mna is not None:
                mn = mna if mn is None else min(mn, mna)
            if mxa is not None:
                mx = mxa if mx is None else max(mx, mxa)
        elif db > da:
            b, mnb, mxb = self._lift(ver, b, db - da)
            if b is None:
                return []
            if mnb is not None:
                mn = mnb if mn is None else min(mn, mnb)
            if mxb is not None:
                mx = mxb if mx is None else max(mx, mxb)

        if a == b:
            return [mn if mn is not None else 0, mx if mx is not None else 0]

        for k in range(self.LOG - 1, -1, -1):
            ua = self._get_up(ver, k, a)
            ub = self._get_up(ver, k, b)
            if ua is None or ub is None or ua == ub:
                continue
            mna = self._get_minc(ver, k, a)
            mxa = self._get_maxc(ver, k, a)
            mnb = self._get_minc(ver, k, b)
            mxb = self._get_maxc(ver, k, b)
            if mna is not None:
                mn = mna if mn is None else min(mn, mna)
            if mxa is not None:
                mx = mxa if mx is None else max(mx, mxa)
            if mnb is not None:
                mn = mnb if mn is None else min(mn, mnb)
            if mxb is not None:
                mx = mxb if mx is None else max(mx, mxb)
            a, b = ua, ub

        mna0 = self._get_minc(ver, 0, a)
        mxa0 = self._get_maxc(ver, 0, a)
        mnb0 = self._get_minc(ver, 0, b)
        mxb0 = self._get_maxc(ver, 0, b)
        if mna0 is not None:
            mn = mna0 if mn is None else min(mn, mna0)
        if mxa0 is not None:
            mx = mxa0 if mx is None else max(mx, mxa0)
        if mnb0 is not None:
            mn = mnb0 if mn is None else min(mn, mnb0)
        if mxb0 is not None:
            mx = mxb0 if mx is None else max(mx, mxb0)

        return [mn if mn is not None else 0, mx if mx is not None else 0]

    # ---------- version creation helpers ----------
    def _clone_version(self, from_version: int) -> int:
        base = self.versions[from_version]
        newv = Version(self.LOG)
        newv.fork_from(base)
        self.versions.append(newv)
        return len(self.versions) - 1

    def branch(self, from_version: int) -> int:
        return self._clone_version(from_version)

    def _edge_key(self, u: int, v: int) -> Tuple[int, int]:
        return (u, v)  # child->parent

    # ---------- mutating ops ----------
    def union(self, a: int, b: int, version: int, capacity: int) -> int:
        nv = self._clone_version(version)
        ver = self.versions[nv]
    
        ra = self._root(ver, a)
        rb = self._root(ver, b)
    
        if ra == rb:
            pa = self._get_parent(ver, a)
            pb = self._get_parent(ver, b)
            if pa == b:
                self._set_up0_and_cap(ver, a, b, capacity)
                self._rebuild_lift_for_node(ver, a)
                ver.edges = ver.edges.set(self._edge_key(a, b), capacity)
            elif pb == a:
                self._set_up0_and_cap(ver, b, a, capacity)
                self._rebuild_lift_for_node(ver, b)
                ver.edges = ver.edges.set(self._edge_key(b, a), capacity)
            return nv
    
        parent_of_new_child = a
        self._set_parent(ver, rb, parent_of_new_child)
        self._set_depth(ver, rb, self._get_depth(ver, parent_of_new_child) + 1)
        self._set_up0_and_cap(ver, rb, parent_of_new_child, capacity)
        self._rebuild_lift_for_node(ver, rb)
        ver.edges = ver.edges.set(self._edge_key(rb, parent_of_new_child), capacity)
        return nv
    
    def split(self, a: int, b: int, version: int) -> int:
        nv = self._clone_version(version)
        ver = self.versions[nv]

        pa = self._get_parent(ver, a)
        pb = self._get_parent(ver, b)
        if pa == b:  # cut a->b
            self._set_parent(ver, a, None)
            self._set_up0_and_cap(ver, a, None, None)
            self._rebuild_lift_for_node(ver, a)
            ver.edges = ver.edges.set(self._edge_key(a, b), None)
        elif pb == a:  # cut b->a
            self._set_parent(ver, b, None)
            self._set_up0_and_cap(ver, b, None, None)
            self._rebuild_lift_for_node(ver, b)
            ver.edges = ver.edges.set(self._edge_key(b, a), None)
        # else: no-op, still new version
        return nv

    def merge_versions(self, vX: int, vY: int) -> Tuple[int, bool]:
        """
        Clone vX, then replay vY's surviving tree edges (child->parent) subject to constraints:
          - capacity >= 0
          - if the exact edge (u->p) exists in vX with capacity capX and vY has capY != capX -> CONFLICT -> fail.
          - skip edges that would create cycles or conflict with an existing *different* parent.
        On failure, return (new_version_id, False) where the new version equals vX (unchanged clone).
        On success, return (new_version_id, True).
        """
        nv = self._clone_version(vX)
        ver = self.versions[nv]

        # collect last-set values for each edge key in vY
        seen = set()
        collected: List[Tuple[int, int, int]] = []
        node = self.versions[vY].edges
        while node is not None:
            for k, val in node.chg.items():
                if k in seen:
                    continue
                seen.add(k)
                if val is not None:
                    u, p = k
                    cap = val
                    # base constraint: non-negative
                    if cap < 0:
                        return nv, False
                    collected.append((u, p, cap))
            node = node.base

        # First pass: detect hard conflicts against the base (vX clone)
        for u, p, capY in collected:
            curr_parent = self._get_parent(ver, u)
            if curr_parent == p:
                # Check existing capacity on (u->p) in base (k=0)
                capX = self._get_minc(ver, 0, u)
                if capX is not None and capX != capY:
                    # Same edge, different capacities -> conflict
                    return nv, False
                # equal cap or unknown capX is fine (will re-set to same value below)
            # If u already has some other parent, we treat it as a structural conflict but not a hard failure;
            # we'll just skip applying this edge in the second pass.

        # Second pass: apply edges oldest-first (reconstruct order)
        for u, p, cap in reversed(collected):
            if self._get_parent(ver, u) == p:
                # same edge; ensure capacity is set (idempotent)
                self._set_up0_and_cap(ver, u, p, cap)
                self._rebuild_lift_for_node(ver, u)
                ver.edges = ver.edges.set(self._edge_key(u, p), cap)
                continue
            if self._get_parent(ver, u) is not None:
                # already attached elsewhere; skip
                continue
            if self._connected(ver, u, p):
                # would form a cycle; skip
                continue
            # attach u under p
            self._set_parent(ver, u, p)
            self._set_depth(ver, u, self._get_depth(ver, p) + 1)
            self._set_up0_and_cap(ver, u, p, cap)
            self._rebuild_lift_for_node(ver, u)
            ver.edges = ver.edges.set(self._edge_key(u, p), cap)

        return nv, True

    # ---------- public driver ----------
    def run(self, operations: List[Tuple[str, Optional[int], Optional[int], Optional[int], Optional[Any]]]
            ) -> List[Union[bool, List[int]]]:
        """
        operations entries (must match the prompt!):
          ("union", a, b, version, capacity)
          ("split", a, b, version, None)
          ("branch", None, None, from_version, None)
          ("find", a, b, version, None)
          ("attributes", a, b, version, None)
          ("merge_versions", None, None, vX, vY)

        Returns:
          - bool for find
          - [min_capacity, max_capacity] for attributes
          - bool for merge_versions success
        """
        out: List[Union[bool, List[int]]] = []
        for op, a, b, version, extra in operations:
            if op == "union":
                self.union(int(a), int(b), int(version), int(extra))
            elif op == "split":
                self.split(int(a), int(b), int(version))
            elif op == "branch":
                # per prompt: a==None, b==None, version==from_version
                self.branch(int(version))
            elif op == "find":
                ver = self.versions[int(version)]
                out.append(self._connected(ver, int(a), int(b)))
            elif op == "attributes":
                ver = self.versions[int(version)]
                out.append(self._path_attributes(ver, int(a), int(b)))
            elif op == "merge_versions":
                # per prompt: version==vX, extra==vY
                _, ok = self.merge_versions(int(version), int(extra))
                out.append(ok)
            else:
                raise ValueError(f"Unknown op: {op}")
        return out


# --------- adapter to match the required function signature ---------
def persistent_disjoint_set(
    operations: List[Tuple[str, Optional[int], Optional[int], Optional[int], Optional[Any]]]
) -> List[Union[bool, List[int]]]:
    """
    Entrypoint as defined in the prompt.
    """
    engine = PersistentDisjointSet(max_nodes_hint=200000)
    return engine.run(operations)


# --------------------------- sanity check ---------------------------
if __name__ == "__main__":
    # Sample from the hard prompt (exact tuple shapes):
    operations = [
        ("union", 1, 2, 0, 8),                 # v1
        ("union", 2, 3, 1, 5),                 # v2
        ("attributes", 1, 3, 2, None),         # -> [5, 8]
        ("branch", None, None, 1, None),       # v3
        ("union", 3, 4, 3, 12),                # v4
        ("merge_versions", None, None, 2, 4),  # v5
        ("find", 1, 4, 5, None),               # -> True
        ("split", 2, 3, 5, None),              # v6
        ("find", 1, 3, 6, None),               # -> False
    ]
    print(persistent_disjoint_set(operations))  # [[5, 8], True, True, False]