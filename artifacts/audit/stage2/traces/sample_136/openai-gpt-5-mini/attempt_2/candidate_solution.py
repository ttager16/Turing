def compute_multilayer_min_cost_route(
    layered_graph: Dict[str, List[Dict[str, Any]]],
    vehicle_type: str,
    start_node: int,
    end_node: int,
    current_time: int,
    environment_state: Dict[str, Any],
    concurrency_tracker: Dict[str, int]
) -> List[int]:
    # Helper to check time window
    def time_accessible(time_windows):
        if not time_windows:
            return True
        for s, e in time_windows:
            if s <= current_time <= e:
                return True
        return False

    # Helper to check capacity
    def capacity_available(u, v, cap):
        key = f"{u},{v}"
        used = concurrency_tracker.get(key, 0)
        return used < cap

    # Helper to compute cost with env multiplier
    def compute_cost(base, env_limits):
        multiplier = 1.0
        if env_limits:
            for k, v in env_limits.items():
                if k in environment_state and environment_state[k] == v and v is True:
                    multiplier *= 2.0
        return base * multiplier

    start = str(start_node)
    target = str(end_node)

    # Dijkstra
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    visited = set()

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break
        neighbors = layered_graph.get(u, [])
        for edge in neighbors:
            v = str(edge[0])
            attrs = edge[1]
            # Check vehicle access
            if vehicle_type not in attrs.get('vehicle_access', []):
                continue
            # Check time windows
            if not time_accessible(attrs.get('time_windows', [])):
                continue
            # Check capacity
            if not capacity_available(u, v, attrs.get('capacity', 0)):
                continue
            # Compute cost
            cost = compute_cost(attrs.get('base_cost', 0.0), attrs.get('env_limits', {}))
            nd = d + cost
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if target not in dist:
        return []

    # Reconstruct path
    path = []
    cur = target
    while cur != start:
        path.append(int(cur))
        cur = prev.get(cur)
        if cur is None:
            return []
    path.append(int(start))
    path.reverse()
    return path