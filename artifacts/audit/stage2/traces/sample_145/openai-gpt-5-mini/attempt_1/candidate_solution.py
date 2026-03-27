def optimize_delivery_route(
    graph: Dict[str, List[List[float]]],
    fuel_stations: List[int],
    vehicle_capacity: float,
    fuel_consumption: float,
    start: int,
    destination: int,
    inspections: List[int]
) -> List[int]:
    # Normalize graph keys to int
    int_graph = {}
    for k, v in graph.items():
        try:
            ik = int(k)
        except:
            continue
        int_graph[ik] = [(int(dst), float(dist)) for dst, dist in v]
    # ensure nodes exist in graph
    nodes = set(int_graph.keys())
    for lst in int_graph.values():
        for dst, _ in lst:
            nodes.add(dst)
    for n in nodes:
        int_graph.setdefault(n, [])
    stations = set(fuel_stations)
    inspections_set = set(inspections)
    # Represent inspection progress as bitmask for efficiency
    inspection_list = sorted(list(inspections_set))
    idx_map = {node: i for i, node in enumerate(inspection_list)}
    target_ins_mask = 0
    for node in inspection_list:
        target_ins_mask |= (1 << idx_map[node])
    # Dijkstra over state: (distance_so_far, node, fuel_remaining, ins_mask)
    # To avoid continuous fuel states, quantize fuel to small epsilon to allow float handling.
    # Use continuous floats but maintain visited with best-known fuel for (node, ins_mask) at given distance.
    # We'll store visited as dict mapping (node, ins_mask) -> best distance seen for some fuel; and track seen with fuel threshold.
    # Use priority queue ordered by total distance traveled.
    start_fuel = vehicle_capacity
    start_mask = 0
    if start in idx_map:
        start_mask |= (1 << idx_map[start])
    pq = []
    # state: (total_distance, node, fuel_remaining, ins_mask, parent_state_id)
    # We'll store parent pointers keyed by unique ids
    state_id = 0
    parents = {}  # id -> (prev_id, node)
    states = {}   # id -> (node, fuel, mask, dist)
    entry_id = state_id
    heapq.heappush(pq, (0.0, state_id))
    states[state_id] = (start, start_fuel, start_mask, 0.0)
    parents[state_id] = (None, None)
    state_id += 1
    # For pruning: best_known[(node, mask, fuel_rounded)] = best distance; but fuel continuous so we keep for (node,mask) the max fuel seen at <= distance
    # Instead, keep for (node,mask) best distance found; if we reach same (node,mask) with larger distance and less/equal fuel, skip.
    best = {}  # (node,mask) -> list of tuples (dist, fuel)
    while pq:
        dist_so_far, sid = heapq.heappop(pq)
        node, fuel, mask, dist_recorded = states[sid]
        # if popped outdated (distance mismatch), skip
        if abs(dist_so_far - dist_recorded) > 1e-9:
            continue
        # Check if reached destination with all inspections done
        if node == destination and mask == target_ins_mask:
            # reconstruct path
            path = []
            cur = sid
            while cur is not None:
                n = states[cur][0]
                path.append(n)
                cur = parents[cur][0]
            return list(reversed(path))
        # Prune using best list
        key = (node, mask)
        prune = False
        if key in best:
            to_remove = []
            for (bdist, bfuel) in best[key]:
                # if there's a previous state with <= distance and >= fuel, current is dominated
                if bdist <= dist_so_far + 1e-9 and bfuel >= fuel - 1e-9:
                    prune = True
                    break
                # if current dominates previous, mark previous for removal
                if dist_so_far <= bdist + 1e-9 and fuel >= bfuel - 1e-9:
                    to_remove.append((bdist, bfuel))
            if prune:
                continue
            for item in to_remove:
                best[key].remove(item)
            best[key].append((dist_so_far, fuel))
        else:
            best[key] = [(dist_so_far, fuel)]
        # Option to refuel if station present: we assume refueling fills to full instantly (no time cost), and station availability is static per problem input
        if node in stations and fuel < vehicle_capacity - 1e-9:
            new_fuel = vehicle_capacity
            new_mask = mask
            if node in idx_map:
                new_mask = mask | (1 << idx_map[node])
            new_dist = dist_so_far
            sid_new = state_id
            states[sid_new] = (node, new_fuel, new_mask, new_dist)
            parents[sid_new] = (sid, None)  # parent pointer to previous state id
            state_id += 1
            heapq.heappush(pq, (new_dist, sid_new))
        # Explore outgoing edges
        for (dst, d) in int_graph.get(node, []):
            fuel_needed = d * fuel_consumption
            if fuel + 1e-9 < fuel_needed:
                continue
            new_fuel = fuel - fuel_needed
            new_mask = mask
            if dst in idx_map:
                new_mask = mask | (1 << idx_map[dst])
            new_dist = dist_so_far + d
            sid_new = state_id
            states[sid_new] = (dst, new_fuel, new_mask, new_dist)
            parents[sid_new] = (sid, None)
            state_id += 1
            heapq.heappush(pq, (new_dist, sid_new))
    return []