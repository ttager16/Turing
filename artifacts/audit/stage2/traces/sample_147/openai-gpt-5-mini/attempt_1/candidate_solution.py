def optimize_delivery_routes(
    num_nodes: int,
    edges: List[List[int]],
    mandatory_checkpoints: List[int],
    global_max_time: int,
    global_max_capacity: int
) -> List[int]:
    # Build adjacency list: u -> list of (v, time, cap, cost)
    adj: Dict[int, List[Tuple[int,int,int,int]]] = defaultdict(list)
    for u,v,t,capa,cost in edges:
        adj[u].append((v,t,capa,cost))
    # We need to find a single path that visits mandatory checkpoints in order.
    # Model as multi-stage shortest path: between successive checkpoints (including any start node),
    # but start can be any node; the overall path may start anywhere and must visit all checkpoints in order.
    # Strategy: create augmented state (node, idx) where idx is how many mandatory checkpoints satisfied.
    # Start states: any node with idx = 0, cost 0, time 0, cap 0, path [node].
    # Transitions: follow edges; when reaching next mandatory checkpoint value, increment idx if matches next.
    # Enforce cumulative time <= global_max_time and cumulative capacity <= global_max_capacity.
    # Use Dijkstra-like over cost.
    target_idx = len(mandatory_checkpoints)
    # Map for quick check of next required checkpoint
    def next_checkpoint(idx):
        return mandatory_checkpoints[idx] if idx < target_idx else None
    # Priority queue entries: (total_cost, total_time, total_cap, node, idx, path_tuple)
    heap = []
    # For efficiency, initialize starting positions as any node; but we can also start only at nodes
    # that exist in graph or are in checkpoints. Collect candidate starts.
    candidate_starts = set(range(num_nodes))
    # push all starts
    for s in candidate_starts:
        idx = 0
        # if the first mandatory checkpoint is the start node, consider it satisfied
        if target_idx>0 and s == mandatory_checkpoints[0]:
            idx = 1
        heapq.heappush(heap, (0, 0, 0, s, idx, (s,)))
    # visited best-known cost for (node, idx, time, cap) is too big; we keep best cost per (node, idx, time, cap) compressed.
    # We'll keep for each (node, idx, time, cap) minimal cost seen, but to limit size we store minimal cost per (node, idx, time, cap)
    # Instead, store best cost per (node, idx, time, cap) with coarse pruning: for (node, idx) keep list of non-dominated (time, cap, cost)
    best: Dict[Tuple[int,int], List[Tuple[int,int,int]]] = defaultdict(list)
    while heap:
        cost, time_so_far, cap_so_far, node, idx, path = heapq.heappop(heap)
        # If cost is dominated by known bests, skip
        dominated = False
        lst = best[(node, idx)]
        for t,capa,c in lst:
            if t <= time_so_far and capa <= cap_so_far and c <= cost:
                dominated = True
                break
        if dominated:
            continue
        # Record this state and prune dominated entries
        new_lst = []
        for t,capa,c in lst:
            # keep only those not dominated by current
            if not (time_so_far <= t and cap_so_far <= capa and cost <= c):
                new_lst.append((t,capa,c))
        new_lst.append((time_so_far, cap_so_far, cost))
        best[(node, idx)] = new_lst
        # Check goal
        if idx == target_idx:
            # Found a path visiting all checkpoints; return path as list
            return list(path)
        # Expand edges
        for v, t_edge, capa_edge, cost_edge in adj.get(node, []):
            new_time = time_so_far + t_edge
            new_cap = cap_so_far + capa_edge
            if new_time > global_max_time or new_cap > global_max_capacity:
                continue
            new_cost = cost + cost_edge
            new_idx = idx
            nxt = next_checkpoint(idx)
            if nxt is not None and v == nxt:
                new_idx += 1
            new_path = path + (v,)
            # minor loop prevention: avoid extremely long paths by limiting length to num_nodes*3
            if len(new_path) > num_nodes * 3:
                continue
            heapq.heappush(heap, (new_cost, new_time, new_cap, v, new_idx, new_path))
    return []