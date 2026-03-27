def find_graph_center(graph: Dict[str, List[List[int]]]) -> int:
    INF = 10**30
    # Validate top-level
    if not isinstance(graph, dict) or len(graph) == 0:
        return -1
    # parse node ids: keys must be strings that are integers
    nodes = {}
    try:
        for k in graph.keys():
            if not isinstance(k, str):
                return -1
            ik = int(k)  # may raise
            nodes[k] = ik
    except Exception:
        return -1
    # build undirected deduped adjacency: dict[int] -> dict[int]->weight
    adjmap = {}
    for k, ik in nodes.items():
        adjmap.setdefault(ik, {})
    try:
        for k, neighs in graph.items():
            u = nodes[k]
            if not isinstance(neighs, list):
                return -1
            for item in neighs:
                if (not isinstance(item, list)) or len(item) != 2:
                    return -1
                v_raw, w = item
                # neighbor id must be int (not string); spec says neighbor IDs that are not integers invalid
                if not isinstance(v_raw, int):
                    return -1
                if not isinstance(w, int) or w < 0:
                    return -1
                v = v_raw
                # ignore self-loops
                if v == u:
                    continue
                # add nodes if not present yet
                if v not in adjmap:
                    adjmap.setdefault(v, {})
                # undirected: keep min weight for unordered pair
                prev = adjmap[u].get(v)
                if prev is None or w < prev:
                    adjmap[u][v] = w
                prev2 = adjmap[v].get(u)
                if prev2 is None or w < prev2:
                    adjmap[v][u] = w
    except Exception:
        return -1
    # now have adjmap. gather all node ids as ints
    all_nodes = sorted(adjmap.keys())
    if len(all_nodes) == 0:
        return -1
    # iterative DFS to label components
    comp_of = {}
    comps = []
    visited = set()
    for s in all_nodes:
        if s in visited:
            continue
        stack = [s]
        comp_nodes = []
        visited.add(s)
        while stack:
            u = stack.pop()
            comp_nodes.append(u)
            for v in adjmap.get(u, {}).keys():
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        comps.append(sorted(comp_nodes))
        for v in comp_nodes:
            comp_of[v] = len(comps)-1
    # determine if all singletons
    singleton_flags = [1 if len(c)==1 else 0 for c in comps]
    all_singletons = all(singleton_flags)
    # function: unweighted iterative DFS farthest heuristic
    def unweighted_farthest(start, comp_set):
        stack = [start]
        parent = {start: None}
        order = []
        while stack:
            u = stack.pop()
            order.append(u)
            for v in adjmap.get(u, {}).keys():
                if v in comp_set and v not in parent:
                    parent[v] = u
                    stack.append(v)
        if not order:
            return start
        return order[-1]
    # Dijkstra
    def dijkstra(src, comp_set):
        dist = {v: INF for v in comp_set}
        dist[src] = 0
        h = [(0, src)]
        while h:
            d,u = heapq.heappop(h)
            if d != dist[u]:
                continue
            for v,w in adjmap.get(u, {}).items():
                if v not in comp_set:
                    continue
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(h, (nd, v))
        return dist
    # For each component (non-singleton unless all singletons), pick candidates and evaluate with pruning
    best_global = None  # tuple (ecc, node_id)
    for comp in comps:
        comp_set = set(comp)
        if len(comp) == 1 and not all_singletons:
            continue
        # candidates: farthest heuristic a,b from arbitrary s
        s = comp[0]
        a = unweighted_farthest(s, comp_set)
        b = unweighted_farthest(a, comp_set)
        # highest-degree node and smallest-ID node
        deg_node = comp[0]
        maxdeg = -1
        for v in comp:
            deg = len(adjmap.get(v, {}))
            if deg > maxdeg or (deg == maxdeg and v < deg_node):
                maxdeg = deg
                deg_node = v
        smallest = min(comp)
        candidates = {a, b, deg_node, smallest}
        # bounds init
        LB = {v: 0 for v in comp}
        UB = {v: INF for v in comp}
        evaluated = {}
        current_best_ecc = INF
        best_in_comp = None  # (ecc,node)
        # run Dijkstra from each candidate in sequence, updating bounds and pruning nodes
        for src in candidates:
            dist = dijkstra(src, comp_set)
            evaluated[src] = dist
            # update LB/UB: ecc(v) >= dist_max_from_src - (max dist from src to any) ??? Landmark bounds:
            # For source s, we know ecc(v) >= max_u dist(s,u) - dist(s,v)
            # and ecc(v) <= max_u dist(s,u) + dist(s,v)
            maxd_s = 0
            for u in comp:
                d = dist[u]
                if d < INF and d > maxd_s:
                    maxd_s = d
            for v in comp:
                dv = dist[v]
                if dv >= INF:
                    # disconnected within comp shouldn't happen
                    continue
                lb = maxd_s - dv
                if lb > LB[v]:
                    LB[v] = lb
                ub = maxd_s + dv
                if ub < UB[v]:
                    UB[v] = ub
            # update best_in_comp from source itself (we can compute its exact eccentricity if we have distances to all nodes finite)
            # eccentricity of src given current dist as exact if we have distances from src to all nodes (we do)
            ecc_src = max(dist[u] for u in comp if dist[u] < INF)
            if ecc_src < current_best_ecc or (ecc_src == current_best_ecc and (best_in_comp is None or src < best_in_comp[1])):
                current_best_ecc = ecc_src
                best_in_comp = (ecc_src, src)
            # prune candidates: check other nodes whose LB >= current_best_ecc skip full evaluation
        # Now consider remaining promising nodes: those with LB < current_best_ecc
        # We'll evaluate by running Dijkstra from them as needed, but avoid re-running for already evaluated nodes.
        # Sort nodes by LB ascending, tie by smaller id to find potentially better centers earlier.
        remaining = sorted(comp, key=lambda x: (LB[x], x))
        for v in remaining:
            if v in evaluated:
                # we can compute ecc from existing dist map
                distv = evaluated[v]
                eccv = max(distv[u] for u in comp if distv[u] < INF)
                if eccv < current_best_ecc or (eccv == current_best_ecc and v < best_in_comp[1]):
                    current_best_ecc = eccv
                    best_in_comp = (eccv, v)
                continue
            if LB[v] >= current_best_ecc:
                continue
            distv = dijkstra(v, comp_set)
            evaluated[v] = distv
            eccv = max(distv[u] for u in comp if distv[u] < INF)
            # update bounds using this source
            maxd_v = max(distv[u] for u in comp if distv[u] < INF)
            for x in comp:
                dx = distv[x]
                lb = maxd_v - dx
                if lb > LB[x]:
                    LB[x] = lb
                ub = maxd_v + dx
                if ub < UB[x]:
                    UB[x] = ub
            if eccv < current_best_ecc or (eccv == current_best_ecc and v < best_in_comp[1]):
                current_best_ecc = eccv
                best_in_comp = (eccv, v)
        if best_in_comp is None:
            continue
        # compare globally
        if best_global is None or best_in_comp[0] < best_global[0] or (best_in_comp[0] == best_global[0] and best_in_comp[1] < best_global[1]):
            best_global = best_in_comp
    # If no non-singleton components considered (all singletons), return smallest node id
    if best_global is None:
        return min(all_nodes)
    return best_global[1]