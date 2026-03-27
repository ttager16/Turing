from typing import Dict, List, Iterable
from collections import deque, defaultdict

BalanceRatio = 1.2
CANDIDATE_CAP_K3 = 100


def find_planar_separators(
    graph: Dict[str, List[str]],
    queries: List[List]
) -> List[List[int]]:
    """
    Processes an evolving simple undirected graph and a batch of list-encoded operations:
      ["add", u, v], ["remove", u, v], ["query", [v1, v2, ..., vk]] (k≥2).
    For each query, returns a deterministic, locally-minimal separator list (ascending) that
    separates all listed targets into distinct connected components and, when possible under
    bounded search, satisfies the 1.2 balance ratio. Uses only Python's standard library.
    """
    
    def _to_int(x):
        try:
            return int(x)
        except Exception:
            return x

    
    _tmp = {}
    for k, nbrs in (graph or {}).items():
        u = _to_int(k)
        _tmp.setdefault(u, set())
        for w in (nbrs or []):
            v = _to_int(w)
            if v != u:
                _tmp[u].add(v)
                _tmp.setdefault(v, set()).add(u)

    
    adj = defaultdict(set)
    for u, nbrs in _tmp.items():
        for v in nbrs:
            adj[u].add(v)
            adj[v].add(u)

    # Normalize queries -> int node IDs; ignore malformed safely
    _norm_queries = []
    for op in (queries or []):
        if not isinstance(op, list) or not op:
            continue
        t = op[0]
        if t == "query" and len(op) == 2 and isinstance(op[1], list):
            _norm_queries.append(["query", [_to_int(x) for x in op[1]]])
        elif t in ("add", "remove") and len(op) >= 3:
            _norm_queries.append([t, _to_int(op[1]), _to_int(op[2])])
        else:
            # ignore malformed/no-op
            continue
    queries = _norm_queries

    def add_edge(u: int, v: int) -> None:
        if u != v:
            adj[u].add(v)
            adj[v].add(u)

    def remove_edge(u: int, v: int) -> None:
        adj[u].discard(v)
        adj[v].discard(u)

    out: List[List[int]] = []
    for op in (queries or []):
        if not isinstance(op, list) or not op:
            continue
        t = op[0]
        if t == "add" and len(op) == 3:
            u = int(op[1]); v = int(op[2])
            add_edge(u, v)
        elif t == "remove" and len(op) == 3:
            u = int(op[1]); v = int(op[2])
            remove_edge(u, v)
        elif t == "query" and len(op) == 2:
            trg_raw = op[1]
            if not isinstance(trg_raw, list):
                try:
                    trg_raw = list(trg_raw)
                except Exception:
                    trg_raw = []
            # Robust cast: keep ints; accept digit-strings
            targets = [
                int(x) for x in trg_raw
                if isinstance(x, (int, bool)) or (isinstance(x, str) and x.isdigit())
            ]
            out.append(_find_separator_for_query(adj, targets))
    return out

def _find_separator_for_query(adj: Dict[int, Iterable[int]], targets: List[int]) -> List[int]:
    if len(targets) < 2:
        return []
    all_nodes = set(adj.keys()) | {x for vs in adj.values() for x in vs}
    present_targets = [t for t in targets if t in all_nodes]
    if len(present_targets) < 2:
        return []
    aps = _articulation_points_iter(adj, all_nodes)
    near = _near_path_nodes(adj, present_targets, pair_cap=6, hop_cap=2)
    hood = _neighborhood_nodes(adj, present_targets, radius=2, cap=500)
    candidates = sorted((aps | near | hood) - set(present_targets))
    for size in (1, 2, 3):
        sep = _first_balanced_separator(adj, all_nodes, present_targets, candidates, size)
        if sep is not None:
            return sep
    sep_unbalanced = _smallest_unbalanced_separator(adj, all_nodes, present_targets, candidates, max_k=3)
    if sep_unbalanced is not None:
        return sep_unbalanced
    sep_greedy = _greedy_multiway_cut(adj, all_nodes, present_targets, candidates)
    if sep_greedy:
        return _make_locally_minimal(adj, all_nodes, sep_greedy, present_targets, enforce_balance=False)
    return []


def _first_balanced_separator(adj, all_nodes, targets, candidates, size: int) -> List[int] | None:
    if size == 1:
        for x in candidates:
            sep = [x]
            if _valid_separator(adj, all_nodes, sep, targets, enforce_balance=True):
                return _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance=True)
        return None
    if size == 2:
        n = len(candidates)
        for i in range(n):
            for j in range(i + 1, n):
                sep = [candidates[i], candidates[j]]
                if _valid_separator(adj, all_nodes, sep, targets, enforce_balance=True):
                    return _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance=True)
        return None
    base = candidates[:CANDIDATE_CAP_K3]
    n = len(base)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                sep = [base[i], base[j], base[k]]
                if _valid_separator(adj, all_nodes, sep, targets, enforce_balance=True):
                    return _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance=True)
    return None


def _smallest_unbalanced_separator(adj, all_nodes, targets, candidates, max_k: int = 3) -> List[int] | None:
    for x in candidates:
        sep = [x]
        if _valid_separator(adj, all_nodes, sep, targets, enforce_balance=False):
            return _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance=False)
    n = len(candidates)
    for i in range(n):
        for j in range(i + 1, n):
            sep = [candidates[i], candidates[j]]
            if _valid_separator(adj, all_nodes, sep, targets, enforce_balance=False):
                return _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance=False)
    base = candidates[:CANDIDATE_CAP_K3]
    nb = len(base)
    if max_k >= 3:
        for i in range(nb):
            for j in range(i + 1, nb):
                for k in range(j + 1, nb):
                    sep = [base[i], base[j], base[k]]
                    if _valid_separator(adj, all_nodes, sep, targets, enforce_balance=False):
                        return _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance=False)
    return None


def _components_over(nodes: Iterable[int], adj: Dict[int, Iterable[int]]) -> List[set]:
    nodes = set(nodes)
    seen, comps = set(), []
    for s in sorted(nodes):
        if s in seen:
            continue
        q = deque([s])
        seen.add(s)
        comp = {s}
        while q:
            u = q.popleft()
            for v in sorted(adj.get(u, ())):
                if v in nodes and v not in seen:
                    seen.add(v)
                    comp.add(v)
                    q.append(v)
        comps.append(comp)
    return comps


def _targets_separated(components: List[set], targets: List[int]) -> bool:
    comp_idx_by_target = {}
    for i, comp in enumerate(components):
        contained = [t for t in targets if t in comp]
        if len(contained) > 1:
            return False
        for t in contained:
            if t in comp_idx_by_target:
                return False
            comp_idx_by_target[t] = i
    present = list(comp_idx_by_target.keys())
    return len(set(comp_idx_by_target.values())) == len(present)


def _balanced(components: List[set]) -> bool:
    if not components:
        return True
    sizes = [len(c) for c in components]
    s_min, s_max = min(sizes), max(sizes)
    if s_min == 0:
        return False
    return (s_max / s_min) <= BalanceRatio


def _valid_separator(adj, all_nodes, separator, targets, enforce_balance: bool) -> bool:
    if set(separator) & set(targets):
        return False
    remaining = all_nodes - set(separator)
    comps = _components_over(remaining, adj)
    if not _targets_separated(comps, targets):
        return False
    return _balanced(comps) if enforce_balance else True


def _make_locally_minimal(adj, all_nodes, sep, targets, enforce_balance: bool) -> List[int]:
    S = sorted(sep)
    changed = True
    while changed:
        changed = False
        for x in list(S):
            trial = [y for y in S if y != x]
            if _valid_separator(adj, all_nodes, trial, targets, enforce_balance):
                S = trial
                changed = True
                break
    return sorted(S)


def _neighborhood_nodes(adj: Dict[int, Iterable[int]], targets: List[int], radius: int = 2, cap: int = 500) -> set:
    out = set()
    for t in sorted(set(targets)):
        if t not in adj:
            continue
        q = deque([(t, 0)])
        seen = {t}
        while q:
            u, d = q.popleft()
            if d == radius:
                continue
            for v in sorted(adj.get(u, ())):
                if v not in seen:
                    seen.add(v)
                    out.add(v)
                    q.append((v, d + 1))
            if len(out) >= cap:
                break
        if len(out) >= cap:
            break
    return out


def _near_path_nodes(adj: Dict[int, Iterable[int]], targets: List[int], pair_cap: int = 6, hop_cap: int = 2) -> set:
    ts = sorted(set(targets))
    picks = []
    for i in range(len(ts)):
        for j in range(i + 1, len(ts)):
            picks.append([ts[i], ts[j]])
            if len(picks) >= pair_cap:
                break
        if len(picks) >= pair_cap:
            break
    out = set()
    for s, t in picks:
        path = _shortest_path(adj, s, t)
        if len(path) > 2:
            out.update(path[1:-1])
            if hop_cap > 0:
                fringe = set(path)
                for _ in range(hop_cap):
                    new = set()
                    for u in list(fringe):
                        for v in sorted(adj.get(u, ())):
                            new.add(v)
                    out.update(new)
                    fringe = new
    return out


def _shortest_path(adj: Dict[int, Iterable[int]], s: int, t: int) -> List[int]:
    if s == t:
        return [s]
    if s not in adj or t not in adj:
        return []
    q = deque([s])
    parent = {s: None}
    while q:
        u = q.popleft()
        for v in sorted(adj.get(u, ())):
            if v in parent:
                continue
            parent[v] = u
            if v == t:
                path = [t]
                cur = u
                while cur is not None:
                    path.append(cur)
                    cur = parent[cur]
                return list(reversed(path))
            q.append(v)
    return []


def _shortest_path_exclude(adj: Dict[int, Iterable[int]], s: int, t: int, blocked: set) -> List[int]:
    if s == t:
        return [s]
    if s not in adj or t not in adj:
        return []
    q = deque([s])
    parent = {s: None}
    seen = {s}
    while q:
        u = q.popleft()
        for v in sorted(adj.get(u, ())):
            if v in blocked or v in seen:
                continue
            seen.add(v)
            parent[v] = u
            if v == t:
                path = [t]
                cur = u
                while cur is not None:
                    path.append(cur)
                    cur = parent[cur]
                return list(reversed(path))
            q.append(v)
    return []


def _articulation_points_iter(adj: Dict[int, Iterable[int]], all_nodes: set) -> set:
    disc, low, parent = {}, {}, {}
    ap = set()
    time = 0
    for start in sorted(all_nodes):
        if start in disc:
            continue
        parent[start] = None
        root_children = 0
        stack = [(start, iter(sorted(adj.get(start, ()))), 0)]
        disc[start] = low[start] = time; time += 1
        while stack:
            u, it, _ = stack.pop()
            try:
                v = next(it)
                stack.append((u, it, 0))
                if v not in disc:
                    parent[v] = u
                    disc[v] = low[v] = time; time += 1
                    if u == start:
                        root_children += 1
                    stack.append((v, iter(sorted(adj.get(v, ()))), 0))
                elif v != parent.get(u):
                    low[u] = min(low[u], disc[v])
            except StopIteration:
                p = parent.get(u)
                if p is not None:
                    low[p] = min(low[p], low[u])
                    if low[u] >= disc[p]:
                        ap.add(p)
                else:
                    if root_children > 1:
                        ap.add(u)
    return ap


def _greedy_multiway_cut(adj: Dict[int, Iterable[int]], all_nodes: set, targets: List[int], candidates: List[int], max_iters: int = 200) -> List[int] | None:
    S: List[int] = []
    iters = 0
    while iters < max_iters:
        iters += 1
        remaining = all_nodes - set(S)
        comps = _components_over(remaining, adj)
        if _targets_separated(comps, targets):
            return sorted(S)
        loc = {}
        for i, c in enumerate(comps):
            for t in targets:
                if t in c:
                    loc[t] = i
        pairs = []
        for i in range(len(targets)):
            for j in range(i + 1, len(targets)):
                a, b = targets[i], targets[j]
                if loc.get(a) == loc.get(b) and loc.get(a) is not None:
                    pairs.append((a, b))
        if not pairs:
            break
        a, b = sorted(pairs)[0]
        path = _shortest_path_exclude(adj, a, b, set(S))
        pick = None
        mids = path[1:-1] if path else []
        for x in sorted(mids):
            if x not in targets:
                pick = x
                break
        if pick is None:
            for x in candidates:
                if x in targets or x in S:
                    continue
                pick = x
                break
        if pick is None:
            return None
        S.append(pick)
    return None


if __name__ == "__main__":
    # Demonstration with JSON-style string keys; normalization will convert to ints.
    city_graph = {
        "1": ["2", "8"],
        "2": ["1", "3", "6"],
        "3": ["2", "4"],
        "4": ["3", "5"],
        "5": ["4", "9"],
        "6": ["2", "7"],
        "7": ["6", "8"],
        "8": ["1", "7"],
        "9": ["5"]
    }
    queries = [
        ["remove", 3, 4],
        ["query", [1, 3, 6]],
        ["add", 2, 9],
        ["query", [6, 9]]
    ]
    print(find_planar_separators(city_graph, queries))