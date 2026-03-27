def optimize_delivery_routes(
    num_nodes: int,
    edges: List[List[int]],
    mandatory_checkpoints: List[int],
    global_max_time: int,
    global_max_capacity: int
) -> List[int]:
    # Build adjacency list: u -> list of (v, time, cap, cost)
    adj = [[] for _ in range(num_nodes)]
    for u, v, t, c, cost in edges:
        if t <= global_max_time and c <= global_max_capacity:
            adj[u].append((v, t, c, cost))

    # We need a path that visits all mandatory_checkpoints in order.
    # We'll treat segments: start from any node, must reach first checkpoint, then next, ... final checkpoint.
    # Use multi-source Dijkstra-like search per segment but tracking cumulative time, capacity, cost.
    # Since nodes can repeat, and constraints are global (sum over entire path), when searching segment k we must
    # start from possible start states coming from previous segment results.
    checkpoints = list(mandatory_checkpoints)
    if not checkpoints:
        return []

    # For initial segment, possible starts are any node (we allow starting at any node).
    # Represent state as (cost, node, time_used, cap_used, path)
    # For first segment, we need to reach checkpoints[0]
    def search_segment(starts: List[Tuple[int,int,int,List[int]]], target: int):
        # starts: list of (node, time_used, cap_used, path)
        # returns list of resulting states at target: (cost, node, time, cap, path)
        results = []
        # We'll run a priority queue over total cost so far
        pq = []
        # visited dictionary to prune: (node, time_used, cap_used) -> best cost
        # But to keep manageable, we store best cost per (node, time_used, cap_used) quantized by exact values.
        visited = dict()
        for node, time_used, cap_used, cost_used, path in starts:
            key = (node, time_used, cap_used)
            prev = visited.get((node, time_used, cap_used))
            if prev is None or cost_used < prev:
                visited[(node, time_used, cap_used)] = cost_used
                heapq.heappush(pq, (cost_used, node, time_used, cap_used, path))
        while pq:
            cost_so_far, u, time_so_far, cap_so_far, path_so_far = heapq.heappop(pq)
            # If this state exceeded stored best, skip
            if visited.get((u, time_so_far, cap_so_far), None) != cost_so_far:
                continue
            if u == target:
                results.append((cost_so_far, u, time_so_far, cap_so_far, path_so_far.copy()))
                # Do not early return: other possibly cheaper states may exist
                continue
            for v, t, c, edge_cost in adj[u]:
                new_time = time_so_far + t
                new_cap = cap_so_far + c
                if new_time > global_max_time or new_cap > global_max_capacity:
                    continue
                new_cost = cost_so_far + edge_cost
                new_path = path_so_far + [v]
                key = (v, new_time, new_cap)
                prev = visited.get(key)
                if prev is None or new_cost < prev:
                    visited[key] = new_cost
                    heapq.heappush(pq, (new_cost, v, new_time, new_cap, new_path))
        return results

    # Initialize starts: all nodes as possible starting positions with zero time/cap/cost and path [node]
    starts = []
    for node in range(num_nodes):
        starts.append((node, 0, 0, 0, [node]))

    # For each checkpoint, run segment search to reach it from any of current starts
    for cp in checkpoints:
        seg_results = search_segment(starts, cp)
        if not seg_results:
            return []
        # Consolidate results: keep only Pareto-efficient states to limit explosion.
        # We'll keep for each (node) a list of states and prune dominated ones.
        new_states = dict()  # key: node -> list of (time, cap, cost, path)
        for cost, node, time_used, cap_used, path in seg_results:
            lst = new_states.setdefault(node, [])
            lst.append((time_used, cap_used, cost, path))
        # prune dominated: a dominates b if time<= and cap<= and cost<= with at least one strict
        starts = []
        for node, lst in new_states.items():
            pruned = []
            for a in lst:
                dominated = False
                for b in lst:
                    if a is b:
                        continue
                    if b[0] <= a[0] and b[1] <= a[1] and b[2] <= a[2] and (b[0] < a[0] or b[1] < a[1] or b[2] < a[2]):
                        dominated = True
                        break
                if not dominated:
                    pruned.append(a)
            for time_used, cap_used, cost_used, path in pruned:
                starts.append((node, time_used, cap_used, cost_used, path))

    # After final checkpoint reached, choose minimal cost among starts
    if not starts:
        return []
    best = min(starts, key=lambda s: s[3])
    return best[4]