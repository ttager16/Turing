from typing import Dict, List, Any, Union, Tuple, Callable
import math
import copy

StageResult = Union[List[List[str]], Dict[str, str]]


def convert_label_functions(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert adjacency label strings like "lambda s: 2" into callables.
    - Works in-place on a shallow copy and returns the converted graph.
    - Safe-ish eval: disallows __builtins__, exposes only a tiny whitelist.
    - If an entry already contains a callable, it is kept as-is.
    - Expects node IDs and neighbor IDs as strings.
    """
    g = copy.deepcopy(graph)

    safe_globals = {
        "__builtins__": {},
        "math": math,
        "min": min,
        "max": max,
        "abs": abs,
    }

    def _compile_label(expr: Any) -> Callable[[Dict[str, Any]], float]:
        if callable(expr):
            return expr
        if not isinstance(expr, str):
            # Fallback: constant cost if a number; else invalid → raise
            if isinstance(expr, (int, float)) and math.isfinite(expr):
                return lambda s, _val=float(expr): _val
            raise ValueError("Label must be a callable, a lambda string, or a finite number.")
        code = expr.strip()
        if not code.startswith("lambda"):
            raise ValueError("Label string must start with 'lambda'.")
        # Evaluate with restricted globals; no locals needed
        fn = eval(code, safe_globals, {})
        if not callable(fn):
            raise ValueError("Compiled label is not callable.")
        return fn

    # Convert adjacency labels
    for node, adj in list(g.items()):
        # skip special keys
        if node.startswith("_"):
            continue
        if not isinstance(adj, list):
            # tolerate malformed graphs lightly
            g[node] = []
            continue
        new_adj: List[List[Any]] = []
        for item in adj:
            # Expect [neighbor, label]
            if not isinstance(item, list) or len(item) < 2:
                # Skip malformed entries
                continue
            v = str(item[0])
            lbl_raw = item[1]
            try:
                lbl_fn = _compile_label(lbl_raw)
            except Exception:
                # If label can't compile, we skip this edge (treated as unusable)
                continue
            new_adj.append([v, lbl_fn])
        g[node] = new_adj

    # Normalize constraints containers if absent
    g.setdefault("_state", {})
    g.setdefault("_constraints", {
        "required_edges": [],
        "forbidden_edges": [],
        "degree_limits": {},
        "phase_blocklist": [],
        "round_cost_to": 3,
    })

    # Ensure constraint node IDs are strings
    cons = g["_constraints"]
    for key in ["required_edges", "forbidden_edges", "phase_blocklist"]:
        if key in cons and isinstance(cons[key], list):
            cons[key] = [[str(u), str(v)] for (u, v) in cons[key]]

    if "degree_limits" in cons and isinstance(cons["degree_limits"], dict):
        cons["degree_limits"] = {str(k): int(v) for k, v in cons["degree_limits"].items()}

    # round_cost_to normalization
    if "_constraints" in g and isinstance(g["_constraints"], dict):
        rct = g["_constraints"].get("round_cost_to", 3)
        try:
            g["_constraints"]["round_cost_to"] = int(rct)
        except Exception:
            g["_constraints"]["round_cost_to"] = 3

    return g


def compute_multi_stage_mst(
    graphs: List[Dict[str, List[List[Any]]]]
) -> List[StageResult]:
    """
    Compute per-stage MST-like spanning structure under constraints.
    - Accepts string node IDs and label functions given as strings.
    - Automatically compiles label strings via convert_label_functions for each stage.
    - Returns, for each stage, either:
        * List of canonical edges as [u, v] with string node IDs, or
        * {"error": "..."} dict for the specified error conditions.

    Error conditions returned (not raised):
      - {"error": "Missing _state/_constraints"}
      - {"error": "Required edge is forbidden"}
      - {"error": "Required edges form a cycle"}
      - {"error": "Degree limit infeasible"}
      - {"error": "No valid edges available"}  
    """

    # -------- Helpers (string-ID aware) --------

    def order_key(x: str) -> Tuple[int, Union[int, str]]:
        """Numeric-aware sort key: ('0', '1', ..., '10') sorted by number; fallback to string."""
        try:
            return (0, int(x))
        except Exception:
            return (1, x)

    def canonical(u: str, v: str) -> Tuple[str, str]:
        """Return (min, max) using numeric-aware ordering."""
        return (u, v) if order_key(u) <= order_key(v) else (v, u)

    class DSU:
        def __init__(self, nodes: List[str]):
            self.parent = {x: x for x in nodes}
            self.rank = {x: 0 for x in nodes}
            self.nodes = set(nodes)

        def find(self, x: str) -> str:
            p = self.parent[x]
            if p != x:
                self.parent[x] = self.find(p)
            return self.parent[x]

        def union(self, a: str, b: str) -> bool:
            ra, rb = self.find(a), self.find(b)
            if ra == rb:
                return False
            if self.rank[ra] < self.rank[rb]:
                ra, rb = rb, ra
            self.parent[rb] = ra
            if self.rank[ra] == self.rank[rb]:
                self.rank[ra] += 1
            return True

        def same(self, a: str, b: str) -> bool:
            return self.find(a) == self.find(b)

        def count_components(self) -> int:
            return len({self.find(x) for x in self.nodes})

    def is_finite(x) -> bool:
        return isinstance(x, (int, float)) and math.isfinite(x)

    def process_graph(raw_g: Dict[str, Any]) -> StageResult:
        # Auto-convert label strings → callables, normalize constraints & node IDs
        try:
            g = convert_label_functions(raw_g)
        except Exception:
            # If conversion itself fails, treat as missing essentials
            return {"error": "Missing _state/_constraints"}

        # Empty stage (no nodes other than special keys)
        if not g:
            return []

        # Mandatory keys
        if "_state" not in g or "_constraints" not in g:
            return {"error": "Missing _state/_constraints"}

        state = g["_state"]
        cons = g["_constraints"]

        # Extract constraints (canonicalized later)
        required_edges = [tuple(map(str, e)) for e in cons.get("required_edges", [])]
        forbidden_edges = [tuple(map(str, e)) for e in cons.get("forbidden_edges", [])]
        phase_blocklist = [tuple(map(str, e)) for e in cons.get("phase_blocklist", [])]
        degree_limits_raw: Dict[str, int] = dict(cons.get("degree_limits", {}))
        round_cost_to: int = int(cons.get("round_cost_to", 3))

        # Canonicalize constraint edges
        req_canon = [canonical(u, v) for (u, v) in required_edges]
        forb_canon = {canonical(u, v) for (u, v) in forbidden_edges}
        block_canon = {canonical(u, v) for (u, v) in phase_blocklist}

        # Node set: all string-labeled keys (excluding special), neighbors, and constraint endpoints
        nodes = set()
        for key in g:
            if isinstance(key, str) and not key.startswith("_"):
                nodes.add(key)
        for u in list(nodes):
            # Neighbors (string IDs)
            for item in g.get(u, []):
                if not isinstance(item, list) or len(item) < 2:
                    continue
                v = str(item[0])
                nodes.add(v)
        # Include endpoints from constraints
        for (u, v) in set(req_canon) | forb_canon | block_canon:
            nodes.add(u)
            nodes.add(v)

        # If there are no user nodes, return empty
        if not nodes:
            return []

        # Conflict: required ∩ (forbidden ∪ blocklist)
        conflict = set(req_canon) & (forb_canon | block_canon)
        if conflict:
            return {"error": "Required edge is forbidden"}

        # Required-edge cycle check
        dsu_req = DSU(sorted(nodes, key=order_key))
        for (u, v) in req_canon:
            if dsu_req.same(u, v):
                return {"error": "Required edges form a cycle"}
            dsu_req.union(u, v)

        # Build candidate edge map keeping MIN rounded cost per undirected pair
        # Skip: self-loops, forbidden, blocklisted, invalid labels
        min_cost_by_edge: Dict[Tuple[str, str], float] = {}
        for u in nodes:
            adj = g.get(u, [])
            for entry in adj:
                if not isinstance(entry, list) or len(entry) < 2:
                    continue
                v, label_fn = str(entry[0]), entry[1]
                if u == v:
                    continue
                e = canonical(u, v)
                if e in forb_canon or e in block_canon:
                    continue
                if not callable(label_fn):
                    # If user forgot to convert and somehow slipped through, skip
                    continue
                try:
                    c = label_fn(state)
                except Exception:
                    continue
                if not is_finite(c):
                    continue
                rc = round(float(c), round_cost_to)
                # keep minimum rounded cost across duplicates
                if e not in min_cost_by_edge or rc < min_cost_by_edge[e]:
                    min_cost_by_edge[e] = rc

        # Sort candidates by (rounded_cost, u, v) deterministically
        candidates = sorted(
            [(c, e[0], e[1]) for e, c in min_cost_by_edge.items()],
            key=lambda t: (t[0], order_key(t[1]), order_key(t[2]))
        )

        # ---------- FIX: handle "all edges invalid" case ----------
        if not candidates:
            # Normalize degree limits keys to strings
            degree_limits: Dict[str, int] = {str(k): int(v) for k, v in degree_limits_raw.items()}

            # If there are no required edges either → nothing to build
            if not req_canon:
                return {"error": "No valid edges available"}

            # Try to realize required edges under degree limits
            dsu_only_req = DSU(sorted(nodes, key=order_key))
            degree = {n: 0 for n in nodes}

            for (u, v) in req_canon:
                if u in degree_limits and degree[u] + 1 > degree_limits[u]:
                    return {"error": "Degree limit infeasible"}
                if v in degree_limits and degree[v] + 1 > degree_limits[v]:
                    return {"error": "Degree limit infeasible"}
                if not dsu_only_req.same(u, v):
                    dsu_only_req.union(u, v)
                degree[u] += 1
                degree[v] += 1

            # If required edges do not connect everything and we have zero candidates to extend → error
            if dsu_only_req.count_components() > 1:
                return {"error": "No valid edges available"}

            # Otherwise, required edges alone form a spanning structure
            edges_req_only = [[u, v] for (u, v) in sorted(set(req_canon), key=lambda e: (order_key(e[0]), order_key(e[1])))]
            return edges_req_only
        # ----------------------------------------------------------

        # Connectivity "possible" ignoring degree limits (but after all filtering)
        dsu_possible = DSU(sorted(nodes, key=order_key))
        for _, u, v in candidates:
            dsu_possible.union(u, v)
        comps_possible = dsu_possible.count_components()

        # Now build spanning structure with required edges + degree caps
        dsu = DSU(sorted(nodes, key=order_key))
        degree = {n: 0 for n in nodes}
        chosen = set()

        # Normalize degree limits keys to strings
        degree_limits: Dict[str, int] = {str(k): int(v) for k, v in degree_limits_raw.items()}

        # Add required edges first, enforcing degree caps
        for (u, v) in req_canon:
            if u in degree_limits and degree[u] + 1 > degree_limits[u]:
                return {"error": "Degree limit infeasible"}
            if v in degree_limits and degree[v] + 1 > degree_limits[v]:
                return {"error": "Degree limit infeasible"}
            if not dsu.same(u, v):
                dsu.union(u, v)
            degree[u] += 1
            degree[v] += 1
            chosen.add((u, v))  # canonical already

        # Kruskal under degree caps
        for _, u, v in candidates:
            e = (u, v)  # canonical from build
            if e in chosen:
                continue
            if dsu.same(u, v):
                continue
            if u in degree_limits and degree[u] + 1 > degree_limits[u]:
                continue
            if v in degree_limits and degree[v] + 1 > degree_limits[v]:
                continue
            dsu.union(u, v)
            degree[u] += 1
            degree[v] += 1
            chosen.add(e)

        # Degree infeasible check:
        comps_actual = dsu.count_components()
        if comps_possible == 1 and comps_actual > 1:
            return {"error": "Degree limit infeasible"}

        # Return lexicographically (numeric-aware) sorted canonical edges as [u, v]
        edges = [[u, v] for (u, v) in sorted(chosen, key=lambda e: (order_key(e[0]), order_key(e[1])))]
        return edges

    # Process each stage independently
    return [process_graph(g) for g in graphs]