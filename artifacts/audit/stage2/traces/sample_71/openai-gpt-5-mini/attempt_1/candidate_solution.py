def manage_traffic_graph(
    city_map: Dict[str, Dict[str, int]],
    updates: List[List],
    start: str,
    end: str
) -> List[str]:
    # Validate presence of updates parameter
    if updates is None:
        return []
    # If city_map is None -> return []
    if city_map is None:
        return []
    # Work on a deep-copied adjacency dict
    G = {}
    # copy initial city_map
    for u, nbrs in city_map.items():
        if u in G:
            pass
        G[u] = {}
        if isinstance(nbrs, dict):
            for v, w in nbrs.items():
                G[u][v] = int(w)
    # If both empty
    if not G and not updates:
        return []
    # Updates must be a list
    if not isinstance(updates, list):
        return []
    # Apply updates ordered, last-write-wins
    for upd in updates:
        # each update must be list-like of length 3
        if not (isinstance(upd, (list, tuple)) and len(upd) == 3):
            return []
        u, v, w = upd
        if not isinstance(u, str) or not isinstance(v, str):
            return []
        try:
            w = int(w)
        except:
            return []
        # ensure nodes exist
        if u not in G:
            G[u] = {}
        if v not in G:
            G[v] = {}
        # set edge (keep even if zero)
        G[u][v] = w
    # Check for self-loop anywhere -> immediate []
    for u, nbrs in G.items():
        if u in nbrs:
            return []
    # After updates, start and end must exist
    if start not in G or end not in G:
        return []
    # Build set of open outgoing counts to detect sinks (open means w>0)
    # But sinks are dynamic after applying edges; we'll compute as needed.
    # Prepare Dijkstra: (cost, hops, path_tuple, node)
    # For ties, fewer hops preferred, then lexicographically smallest full node sequence.
    # We'll store best seen as dict node -> (cost, hops, path_tuple)
    INF = 10**30
    heap = []
    start_tuple = (start,)
    heapq.heappush(heap, (0, 0, start_tuple, start))
    best = {start: (0, 0, start_tuple)}
    while heap:
        cost_u, hops_u, path_u, u = heapq.heappop(heap)
        # Skip stale
        if best.get(u) != (cost_u, hops_u, path_u):
            continue
        if u == end:
            return list(path_u)
        # iterate neighbors that are present in G[u]
        for v, w in G.get(u, {}).items():
            # skip closed edges (w == 0)
            if w == 0:
                continue
            # compute edge cost; entering a sink that is not end adds penalty
            # determine if v is sink: has no outgoing open edges
            is_sink = True
            for vv, ww in G.get(v, {}).items():
                if ww != 0:
                    is_sink = False
                    break
            add = 0
            if is_sink and v != end:
                add = SINK_PENALTY
            new_cost = cost_u + int(w) + add
            new_hops = hops_u + 1
            new_path = path_u + (v,)
            prev = best.get(v)
            better = False
            if prev is None:
                better = True
            else:
                prev_cost, prev_hops, prev_path = prev
                if new_cost < prev_cost:
                    better = True
                elif new_cost == prev_cost:
                    if new_hops < prev_hops:
                        better = True
                    elif new_hops == prev_hops:
                        if new_path < prev_path:
                            better = True
            if better:
                best[v] = (new_cost, new_hops, new_path)
                heapq.heappush(heap, (new_cost, new_hops, new_path, v))
    # No route found
    return []