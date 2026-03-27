def optimize_traffic_batch(
    city_network: List[List[Any]],
    historical_data: List[List[Any]],
    current_conditions: Dict[str, Any],
    demands: List[List[Any]]
) -> Dict[str, Any]:
    # Build edges dict and adjacency
    edges = {}  # edge_id -> dict with u,v,base_cost
    adj = {}  # u -> list of (v, edge_id)
    for item in city_network:
        if len(item) < 3:
            continue
        u = str(item[0])
        v = str(item[1])
        try:
            b = float(item[2])
        except Exception:
            continue
        if b <= 0.0:
            continue
        edge_id = f"{u}-{v}"
        edges[edge_id] = {"u": u, "v": v, "base_cost": b}
        adj.setdefault(u, []).append((v, edge_id))
    # Load historical and current signals for edges present
    hist = {}
    for rec in historical_data:
        if not rec:
            continue
        key = str(rec[0])
        try:
            val = float(rec[1])
        except Exception:
            continue
        if key in edges:
            hist[key] = val
    curr = {}
    capacity_map = {}
    if isinstance(current_conditions, dict):
        for k, v in current_conditions.items():
            if k == "capacity_map":
                if isinstance(v, dict):
                    for ek, ev in v.items():
                        if ek in edges:
                            try:
                                capacity_map[ek] = int(ev)
                            except Exception:
                                pass
                continue
            if k in edges:
                try:
                    curr[k] = float(v)
                except Exception:
                    pass
    # Initialize residual capacities
    residual = {}
    for eid in edges:
        residual[eid] = int(capacity_map.get(eid, 1))
    # Working mutable base costs
    base_costs = {eid: edges[eid]["base_cost"] for eid in edges}
    alpha = 0.6
    routes = []
    unserved = 0
    layer_switches = 0
    total_cost = 0.0

    def layer_of(node: str) -> str:
        if not isinstance(node, str):
            return ""
        parts = node.split(":", 1)
        return parts[0] if parts else ""

    # For each demand in order
    for dem in demands:
        if not isinstance(dem, (list, tuple)) or len(dem) < 5:
            # malformed -> treat as unserved
            routes.append([])
            unserved += 1
            continue
        src = str(dem[0])
        dst = str(dem[1])
        # commodity = dem[2] unused
        try:
            units = int(dem[3])
        except Exception:
            units = 0
        try:
            priority = float(dem[4])
        except Exception:
            priority = 0.0
        units = max(units, 0)
        priority = max(0.0, min(1.0, priority))
        # Precompute per-edge cost_for_demand based on current base_costs, hist, curr, layers, priority
        edge_cost_for = {}
        for eid, info in edges.items():
            b = base_costs.get(eid, info["base_cost"])
            h = float(hist.get(eid, 0.0))
            c = float(curr.get(eid, 0.0))
            ema = alpha * c + (1 - alpha) * h
            effective_ema = max(0.0, ema)
            cost_base = b * (1.0 + effective_ema / 100.0)
            u = info["u"]
            v = info["v"]
            layer_u = layer_of(u)
            layer_v = layer_of(v)
            layer_multiplier = 1.55 if layer_u != layer_v else 1.0
            cost_after_layer = cost_base * layer_multiplier
            cost_for_demand = cost_after_layer * (1.0 - 0.4 * priority)
            if cost_for_demand < 1e-6:
                cost_for_demand = 1e-6
            edge_cost_for[eid] = cost_for_demand

        # Modified Dijkstra that respects capacity feasibility: only consider edges with residual >= units
        # Use heap of (cost, path_nodes_list, current_node)
        # To support lexicographic tie-breaking on full path, include path tuple in state comparisons.
        visited_best = {}  # node -> (best_cost, best_path_tuple)
        heap = []
        start_path = (src,)
        heapq.heappush(heap, (0.0, start_path, src))
        found = False
        best_path = None
        best_cost = None
        while heap:
            cost_so_far, path_tuple, node = heapq.heappop(heap)
            # If we have a recorded better for node, skip if worse
            rec = visited_best.get(node)
            if rec is not None:
                rec_cost, rec_path = rec
                if cost_so_far > rec_cost + 1e-12:
                    continue
                if abs(cost_so_far - rec_cost) <= 1e-12 and path_tuple >= rec_path:
                    continue
            visited_best[node] = (cost_so_far, path_tuple)
            if node == dst:
                # first time we pop dst is minimal cost; but there could be equal cost with lexicographically smaller path discovered later?
                # Because we push paths and compare path tuple in visited_best, we ensure lexicographically smallest stored.
                found = True
                best_path = list(path_tuple)
                best_cost = cost_so_far
                break
            for (v, eid) in sorted(adj.get(node, []), key=lambda x: (x[0], x[1])):
                # Check capacity feasibility for this edge
                if residual.get(eid, 0) < units:
                    continue
                ec = edge_cost_for.get(eid)
                if ec is None:
                    continue
                new_cost = cost_so_far + ec
                new_path = path_tuple + (v,)
                rec = visited_best.get(v)
                push = False
                if rec is None:
                    push = True
                else:
                    rec_cost, rec_path = rec
                    if new_cost < rec_cost - 1e-12:
                        push = True
                    elif abs(new_cost - rec_cost) <= 1e-12 and new_path < rec_path:
                        push = True
                if push:
                    heapq.heappush(heap, (new_cost, new_path, v))
        if not found or best_path is None:
            routes.append([])
            unserved += 1
            continue
        # Before accepting, double-check all edges along path have residual >= units (should hold)
        path_nodes = best_path
        path_edges = []
        feasible = True
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            eid = f"{u}-{v}"
            if eid not in edges:
                feasible = False
                break
            if residual.get(eid, 0) < units:
                feasible = False
                break
            path_edges.append(eid)
        if not feasible:
            routes.append([])
            unserved += 1
            continue
        # Accept route: update residuals and base_costs inflation and compute stats
        routes.append(path_nodes)
        # Count layer switches in this route
        for eid in path_edges:
            u = edges[eid]["u"]
            v = edges[eid]["v"]
            if layer_of(u) != layer_of(v):
                layer_switches += 1
        # Sum cost using edge_cost_for values that were in effect when routing
        cost_sum = 0.0
        for eid in path_edges:
            cost_sum += edge_cost_for[eid]
        total_cost += cost_sum
        # Update residuals and base_costs
        if units > 0:
            for eid in path_edges:
                residual[eid] = max(0, residual.get(eid, 0) - units)
            # Inflate stored base costs
            for eid in path_edges:
                old = base_costs.get(eid, edges[eid]["base_cost"])
                base_costs[eid] = old * (1.0 + 0.1 * units)
        else:
            # units == 0: capacities unchanged, inflation factor (1.0) effectively does nothing
            for eid in path_edges:
                old = base_costs.get(eid, edges[eid]["base_cost"])
                base_costs[eid] = old * (1.0 + 0.1 * units)
    # Clamp tiny negative noise
    if not math.isfinite(total_cost) or total_cost < 0 and total_cost > -1e-9:
        total_cost = 0.0
    # Round total_cost not required; keep float
    return {
        "routes": routes,
        "unserved_demands": unserved,
        "layer_switches": layer_switches,
        "total_cost": total_cost
    }