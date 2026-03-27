def optimize_traffic_batch(
    city_network: List[List[Any]],
    historical_data: List[List[Any]],
    current_conditions: Dict[str, Any],
    demands: List[List[Any]]
) -> Dict[str, Any]:
    # Build edges: adjacency list and base_costs, ignore base_cost <= 0
    adj = {}  # u -> list of v
    base_cost = {}  # "u-v" -> cost
    edges_set = set()
    for item in city_network:
        if not item or len(item) < 3:
            continue
        u, v, b = item[0], item[1], item[2]
        try:
            b_val = float(b)
        except Exception:
            continue
        if b_val <= 0.0:
            continue
        eid = f"{u}-{v}"
        edges_set.add(eid)
        base_cost[eid] = b_val
        adj.setdefault(u, []).append(v)
    # capacities
    capacity_map = {}
    cap_override = {}
    if isinstance(current_conditions, dict) and "capacity_map" in current_conditions:
        cm = current_conditions.get("capacity_map")
        if isinstance(cm, dict):
            for k, v in cm.items():
                try:
                    capacity = int(v)
                except Exception:
                    continue
                if k in edges_set:
                    cap_override[k] = capacity
    for eid in edges_set:
        capacity_map[eid] = cap_override.get(eid, 1)
    # parse historical and current signals into dicts, ignoring unknown edges
    hist = {}
    for entry in historical_data:
        if not entry or len(entry) < 2:
            continue
        k, v = entry[0], entry[1]
        if k in edges_set:
            try:
                hist[k] = float(v)
            except Exception:
                hist[k] = 0.0
    curr = {}
    for k, v in current_conditions.items():
        if k == "capacity_map":
            continue
        if k in edges_set:
            try:
                curr[k] = float(v)
            except Exception:
                curr[k] = 0.0
    # helper: layer of node
    def layer_of(node: str) -> str:
        if not isinstance(node, str):
            return ""
        if ":" in node:
            return node.split(":", 1)[0]
        return ""
    # compute cost_for_demand per edge given current base_cost and demand priority
    ALPHA = 0.6
    def compute_edge_cost_for_demand(u: str, v: str, priority: float) -> float:
        eid = f"{u}-{v}"
        b = base_cost.get(eid)
        if b is None:
            return math.inf
        h = hist.get(eid, 0.0)
        c = curr.get(eid, 0.0)
        ema = ALPHA * c + (1.0 - ALPHA) * h
        effective_ema = max(0.0, ema)
        cost_base = b * (1.0 + effective_ema / 100.0)
        layer_multiplier = 1.0 if layer_of(u) == layer_of(v) else 1.55
        cost_after_layer = cost_base * layer_multiplier
        p = priority
        cost_for_demand = cost_after_layer * (1.0 - 0.4 * p)
        if cost_for_demand < 1e-6:
            cost_for_demand = 1e-6
        return float(cost_for_demand)
    # Dijkstra that respects capacities and returns lexicographically smallest path on ties
    def find_shortest_path(src: str, dst: str, units: int, priority: float):
        # if src or dst not in nodes, still attempt (graph might be disconnected)
        # states: (cost, path_list, node)
        # We'll keep best cost per node and best path for tie-breaking
        heap = []
        start_path = [src]
        heapq.heappush(heap, (0.0, start_path, src))
        best_cost = {src: 0.0}
        best_path = {src: start_path}
        while heap:
            cost_u, path_u, u = heapq.heappop(heap)
            # If popped cost is worse than recorded, skip
            if cost_u > best_cost.get(u, float('inf')) + 1e-12:
                continue
            if u == dst:
                return path_u, cost_u
            for v in sorted(adj.get(u, [])):
                eid = f"{u}-{v}"
                # check capacity feasibility: need residual >= units
                if capacity_map.get(eid, 0) < units:
                    continue
                edge_cost = compute_edge_cost_for_demand(u, v, priority)
                new_cost = cost_u + edge_cost
                new_path = path_u + [v]
                prev_cost = best_cost.get(v)
                if prev_cost is None or new_cost < prev_cost - 1e-12 or (abs(new_cost - prev_cost) <= 1e-12 and new_path < best_path.get(v, [])):
                    best_cost[v] = new_cost
                    best_path[v] = new_path
                    heapq.heappush(heap, (new_cost, new_path, v))
        return None, math.inf
    routes = []
    unserved = 0
    layer_switches = 0
    total_cost = 0.0
    # Process demands sequentially
    for dem in demands:
        if not dem or len(dem) < 5:
            # invalid demand treated as unserved
            routes.append([])
            unserved += 1
            continue
        src, dst, commodity, units_raw, priority_raw = dem[0], dem[1], dem[2], dem[3], dem[4]
        # clamp units and priority
        try:
            units = int(units_raw)
        except Exception:
            try:
                units = int(float(units_raw))
            except Exception:
                units = 0
        if units < 0:
            units = 0
        try:
            priority = float(priority_raw)
        except Exception:
            priority = 0.0
        if priority < 0.0:
            priority = 0.0
        if priority > 1.0:
            priority = 1.0
        # find shortest feasible path
        path, path_cost = find_shortest_path(src, dst, units, priority)
        if path is None:
            routes.append([])
            unserved += 1
            continue
        # verify feasibility again (should hold)
        feasible = True
        for i in range(len(path)-1):
            eid = f"{path[i]}-{path[i+1]}"
            if capacity_map.get(eid, 0) < units:
                feasible = False
                break
        if not feasible:
            routes.append([])
            unserved += 1
            continue
        # record route
        routes.append(path)
        # count layer switches
        for i in range(len(path)-1):
            if layer_of(path[i]) != layer_of(path[i+1]):
                layer_switches += 1
        # accumulate total cost using the per-edge cost values at this moment
        route_total = 0.0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            edge_cost = compute_edge_cost_for_demand(u, v, priority)
            route_total += edge_cost
        total_cost += route_total
        # update capacities and inflate base_costs
        if len(path) > 1:
            for i in range(len(path)-1):
                eid = f"{path[i]}-{path[i+1]}"
                # decrement capacity
                capacity_map[eid] = max(0, capacity_map.get(eid, 0) - units)
            # inflate base costs by factor (1 + 0.1 * units)
            factor = 1.0 + 0.1 * units
            if factor != 1.0:
                for i in range(len(path)-1):
                    eid = f"{path[i]}-{path[i+1]}"
                    if eid in base_cost:
                        base_cost[eid] = base_cost[eid] * factor
    # clamp negative tiny noise
    if total_cost < 0 and total_cost > -1e-9:
        total_cost = 0.0
    # prepare output
    return {
        "routes": routes,
        "unserved_demands": unserved,
        "layer_switches": layer_switches,
        "total_cost": float(total_cost)
    }