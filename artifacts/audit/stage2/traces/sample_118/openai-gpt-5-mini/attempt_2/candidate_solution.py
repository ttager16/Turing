def optimize_water_flow(
    graph: Dict[str, List[List]],
    source: str,
    target: str,
    capacity_changes: List[List]
) -> int:
    # Validation of top-level types
    if not isinstance(graph, dict) or not isinstance(capacity_changes, list):
        return 0
    if graph == {} and capacity_changes == []:
        return 0
    # Validate source and target types
    if not isinstance(source, str) or not isinstance(target, str) or source == "" or target == "":
        return 0
    # Build internal edge map: (u,v) -> capacity (int). Start from graph input.
    edges = {}  # (u,v) -> capacity
    nodes = set()
    # Validate graph structure
    for u, nbrs in graph.items():
        if not isinstance(u, str) or u == "":
            return 0
        if not isinstance(nbrs, list):
            return 0
        nodes.add(u)
        seen = set()
        for entry in nbrs:
            if not isinstance(entry, list) or len(entry) != 2:
                return 0
            v, cap = entry[0], entry[1]
            if not isinstance(v, str) or v == "":
                return 0
            if not isinstance(cap, int) or cap < 0:
                return 0
            if v in seen:
                return 0
            seen.add(v)
            nodes.add(v)
            if cap == 0:
                continue  # treat as absent
            key = (u, v)
            if key in edges:
                return 0  # duplicate edges in input after considering non-zero edges
            edges[key] = cap
            # self-loop check
            if u == v:
                return 0
    # Validate capacity_changes schema and apply sequentially
    for upd in capacity_changes:
        if not isinstance(upd, list) or len(upd) != 3:
            return 0
        u, v, delta = upd[0], upd[1], upd[2]
        if not isinstance(u, str) or u == "" or not isinstance(v, str) or v == "":
            return 0
        if not isinstance(delta, int):
            return 0
        # self-loop update invalid
        if u == v:
            return 0
        nodes.add(u); nodes.add(v)
        key = (u, v)
        if key in edges:
            newcap = edges[key] + delta
            if newcap < 0:
                return 0
            if newcap == 0:
                # set to zero and will be dropped later; keep as zero for now
                edges[key] = 0
            else:
                edges[key] = newcap
        else:
            # edge doesn't exist
            if delta < 0:
                return 0
            if delta == 0:
                # do nothing
                pass
            else:
                edges[key] = delta
    # After all updates, drop edges with capacity == 0
    edges = {k: v for k, v in edges.items() if v != 0}
    # After dropping zeros, check duplicates: our dict keys ensure uniqueness.
    # Need to ensure no duplicate edges per (u,v) pair — satisfied.
    # Validate source and target existence and reachability
    if source not in nodes or target not in nodes:
        return 0
    # Build adjacency lists for the residual graph from edges
    # We'll need deterministic neighbor ordering: when iterating neighbors, sort by string v.
    # Quick reachability check from source to target using directed edges
    adj = {}
    for (u, v), cap in edges.items():
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, [])  # ensure node present
    # Include isolated nodes
    for n in nodes:
        adj.setdefault(n, [])
    # Remove nodes with no outgoing entries if not in nodes already done
    # BFS for reachability (deterministic order)
    def reachable(src, tgt):
        visited = set()
        q = deque()
        q.append(src)
        visited.add(src)
        while q:
            cur = q.popleft()
            if cur == tgt:
                return True
            neighs = sorted(adj.get(cur, []), key=lambda x: x)
            for nb in neighs:
                if nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        return False
    if not reachable(source, target):
        return 0
    # Prepare residual capacities
    # Residual graph represented as dict of dicts: res[u][v] = cap
    def build_residual():
        res = {}
        for n in nodes:
            res.setdefault(n, {})
        for (u, v), cap in edges.items():
            res[u][v] = cap
            # reverse edges implicit with 0 if not present
            if v not in res or u not in res[v]:
                res.setdefault(v, {})
                res[v].setdefault(u, 0)
        return res
    # Deterministic BFS to find augmenting path with lexicographic neighbor expansion and when equal bottleneck choose lexicographically smallest full path.
    # We'll implement a layered BFS that tracks path and bottleneck. For deterministic tie-breaking among equal bottleneck, we collect all augmenting paths found by BFS (classic Edmonds-Karp finds shortest in edges; here we need lexicographic among equal bottleneck).
    # But requirement: When multiple augmenting paths have equal bottleneck capacity, always select the lexicographically smallest full path.
    # We'll implement repeated search: find all simple paths via BFS layering that reach target (with parents tracked deterministically), but to be efficient, perform BFS that records for each node the best (bottleneck, path) seen where better means larger bottleneck, tie-breaker lexicographically smaller path.
    # However need deterministic expansion order.
    def find_augmenting(res):
        # For every search, fresh structures
        # We'll do modified Dijkstra-like (maximin path) with deterministic neighbor ordering; since capacities are integers, we can use BFS-like with priority by (-bottleneck, path) but must be deterministic.
        # Use a queue exploring nodes in order of decreasing bottleneck, and for equal bottleneck expand nodes in lexicographic path order.
        # We'll maintain for each node the best bottleneck and corresponding path (list of nodes).
        best = {}  # node -> (bottleneck, path)
        # initialize
        best[source] = (float('inf'), [source])
        # frontier as list of nodes to expand; will pick next by highest bottleneck then lexicographic path
        frontier = [source]
        while frontier:
            # select node to expand
            frontier.sort(key=lambda n: (-best[n][0], best[n][1]))
            cur = frontier.pop(0)
            cur_bottle, cur_path = best[cur]
            if cur == target:
                return cur_bottle, cur_path
            # expand neighbors in lexicographic string order
            neighs = sorted(res.get(cur, {}).keys(), key=lambda x: x)
            for nb in neighs:
                cap = res[cur].get(nb, 0)
                if cap <= 0:
                    continue
                new_bottle = min(cur_bottle, cap)
                new_path = cur_path + [nb]
                if nb not in best:
                    best[nb] = (new_bottle, new_path)
                    frontier.append(nb)
                else:
                    prev_bottle, prev_path = best[nb]
                    if new_bottle > prev_bottle:
                        best[nb] = (new_bottle, new_path)
                        if nb not in frontier:
                            frontier.append(nb)
                    elif new_bottle == prev_bottle:
                        # tie-breaker: choose lexicographically smaller full path (compare lists of strings)
                        if new_path < prev_path:
                            best[nb] = (new_bottle, new_path)
                            if nb not in frontier:
                                frontier.append(nb)
        return None  # no augmenting path
    total_flow = 0
    # main loop
    while True:
        res = build_residual()
        found = find_augmenting(res)
        if not found:
            break
        bottle, path = found
        if bottle <= 0:
            break
        # augment along path: adjust residual capacities
        # Fresh residual modifications only based on current edges
        # Build res again to mutate
        res = build_residual()
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            # reduce forward
            res[u][v] = res[u].get(v, 0) - bottle
            # increase reverse
            res[v][u] = res[v].get(u, 0) + bottle
        # Commit changes back to edges structure: edges only store forward edges; reverse edges not stored
        # Update edges dict accordingly: for any (u,v) forward original edge present or created, set to res[u][v] (if >0) or remove if <=0
        new_edges = {}
        # For all pairs in res where original direction might be considered forward if original edges had it OR if reverse has positive that's fine but we only store forward real edges.
        # We'll reconstruct forward edges by checking res[u][v] and whether this corresponds to an original or possible forward edge.
        # To be deterministic, consider all node pairs where res[u][v] > 0 and where original edges may exist or reverse positive should not create new forward edges arbitrarily.
        # The forward edges are those with original in edges or those whose original was absent but had been created earlier; we track via current edges variable: use previous 'edges' keys to determine which directions are forward-capacity-bearing.
        # We'll update edges by applying changes: For each original key in edges, compute new cap = res[u][v] if present else 0.
        for (u,v) in list(edges.keys()):
            newcap = res.get(u, {}).get(v, 0)
            if newcap < 0:
                return 0
            if newcap > 0:
                new_edges[(u,v)] = newcap
        edges = new_edges
        total_flow += bottle
        # After augmentation, check if source and target still exist/reachable; if not reachable, break and return 0 per constraints? The constraint was to check initial reachability; during flow we continue until no augmenting path.
        # Continue loop
    return total_flow