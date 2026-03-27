def optimize_water_flow(
    graph: Dict[str, List[List]],
    source: str,
    target: str,
    capacity_changes: List[List]
) -> int:
    # Validation: types
    if graph == {} and capacity_changes == []:
        return 0
    if not isinstance(graph, dict):
        return 0
    for k, v in graph.items():
        if not isinstance(k, str):
            return 0
        if not isinstance(v, list):
            return 0
        seen_nei = set()
        for item in v:
            if not isinstance(item, list) or len(item) != 2:
                return 0
            nei, cap = item
            if not isinstance(nei, str) or nei == "":
                return 0
            if not isinstance(cap, int) or cap < 0:
                return 0
            if nei in seen_nei:
                return 0
            seen_nei.add(nei)

    # Validate updates format
    if not isinstance(capacity_changes, list):
        return 0
    for upd in capacity_changes:
        if not isinstance(upd, list) or len(upd) != 3:
            return 0
        u, v, delta = upd
        if not isinstance(u, str) or u == "" or not isinstance(v, str) or v == "":
            return 0
        if not isinstance(delta, int):
            return 0
        if u == v:
            return 0

    if not isinstance(source, str) or not isinstance(target, str):
        return 0

    # Build initial edge map (sum duplicates across different lists allowed? spec forbids duplicates within same list only.
    # But duplicates across graph keys? graph keys are nodes; edges are from node to neighbor; duplicates checked per list above.
    edges = {}  # (u,v) -> cap
    nodes = set(graph.keys())
    for u, lst in graph.items():
        nodes.add(u)
        for nei, cap in lst:
            nodes.add(nei)
            if cap == 0:
                continue
            key = (u, nei)
            if key in edges:
                # duplicate edge across entries -> invalid
                return 0
            edges[key] = cap

    # Apply updates sequentially
    for upd in capacity_changes:
        u, v, delta = upd
        # self-loop handled above
        key = (u, v)
        if key in edges:
            newcap = edges[key] + delta
            if newcap < 0:
                return 0
            if newcap == 0:
                del edges[key]
            else:
                edges[key] = newcap
        else:
            if delta < 0:
                return 0
            if delta == 0:
                pass
            else:
                edges[key] = delta
        nodes.add(u); nodes.add(v)

    # After updates, drop zero caps already handled. Check duplicates: edges dict keys unique so ok.
    # But need to ensure no duplicate edges remain: edges dict ensures single.

    # Ensure source and target present and path exists
    if source not in nodes or target not in nodes:
        return 0

    # Build adjacency list for residual graph representation indices mapping
    node_list = sorted(list(nodes), key=lambda x: x)  # lexicographic string order
    idx = {n: i for i, n in enumerate(node_list)}
    N = len(node_list)

    # Build initial capacity adjacency mapping
    adj_init = {i: {} for i in range(N)}  # i -> {j: cap}
    for (u, v), cap in edges.items():
        if cap == 0:
            continue
        ui = idx[u]; vi = idx[v]
        if vi in adj_init[ui]:
            return 0
        adj_init[ui][vi] = cap

    # Connectivity check: simple BFS on directed graph using existing positive edges, expanding neighbors in lexicographic order
    def reachable():
        s = idx[source]; t = idx[target]
        q = deque([s])
        vis = [False]*N
        vis[s] = True
        while q:
            cur = q.popleft()
            if cur == t:
                return True
            # neighbors in lexicographic order by node id string
            neighs = sorted(adj_init[cur].keys(), key=lambda x: node_list[x])
            for nb in neighs:
                if not vis[nb]:
                    vis[nb] = True
                    q.append(nb)
        return False

    if not reachable():
        return 0

    # Implement Edmonds-Karp but with deterministic tie-breaking:
    # For each augmentation, find augmenting path with maximum possible bottleneck? Requirement: when multiple augmenting paths have equal bottleneck, choose lexicographically smallest full path.
    # To satisfy deterministic selection, perform BFS layered search that finds all shortest (in edges) paths? But requirement is choose among equal bottleneck capacities. Simpler: repeatedly find, via modified BFS that prefers neighbors in lexicographic order, the path with maximum bottleneck using a variant of widest path (maximin) with lexicographic tie-break.
    # We'll implement a deterministic widest-path search using modified Dijkstra (by capacity descending), using buckets via capacities since capacities are ints but could be large. Use priority queue with (-bottleneck, path_as_list_of_strings) to tie-break lexicographically smallest path.
    import heapq

    def find_augmenting_path(res_cap):
        # res_cap: dict u->{v:cap}
        s = idx[source]; t = idx[target]
        # maximin best cap to each node and corresponding lexicographically smallest path achieving it
        best = [(-1, None) for _ in range(N)]  # (cap, path as list of node strings)
        pq = []
        start_path = [node_list[s]]
        best[s] = (10**30, start_path)
        heapq.heappush(pq, (-best[s][0], start_path, s))
        while pq:
            negcap, path, u = heapq.heappop(pq)
            cap_u = -negcap
            # prune if worse than recorded
            if best[u][0] != cap_u or best[u][1] != path:
                continue
            if u == t:
                return cap_u, path
            # expand neighbors in lexicographic order of node ids
            neighs = sorted(res_cap.get(u, {}).keys(), key=lambda x: node_list[x])
            for v in neighs:
                c = res_cap[u][v]
                if c <= 0:
                    continue
                bott = cap_u if cap_u < c else c
                newpath = path + [node_list[v]]
                prev_cap, prev_path = best[v]
                replace = False
                if bott > prev_cap:
                    replace = True
                elif bott == prev_cap and prev_path is not None:
                    # choose lexicographically smaller full path (compare lists of strings)
                    if newpath < prev_path:
                        replace = True
                elif prev_path is None:
                    replace = True
                if replace:
                    best[v] = (bott, newpath)
                    heapq.heappush(pq, (-bott, newpath, v))
        return 0, None

    # Build residual capacities dict
    res_cap = {}
    for u in range(N):
        res_cap[u] = {}
    for u, mapping in adj_init.items():
        for v, c in mapping.items():
            res_cap[u][v] = c
    # reverse edges implicit with 0 capacity initially
    flow = 0
    while True:
        cap_path, path_nodes = find_augmenting_path(res_cap)
        if cap_path == 0 or path_nodes is None:
            break
        # convert path_nodes to indices
        path_idx = [idx[n] for n in path_nodes]
        # apply augmentation
        f = cap_path
        # ensure f is int
        if not isinstance(f, int):
            f = int(f)
        for i in range(len(path_idx)-1):
            u = path_idx[i]; v = path_idx[i+1]
            res_cap[u][v] = res_cap[u].get(v, 0) - f
            if res_cap[u][v] == 0:
                # keep zero edges in residual as per residual semantics (but zero treated non-traversable)
                res_cap[u][v] = 0
            # add reverse
            res_cap[v][u] = res_cap[v].get(u, 0) + f
        flow += f

    return flow