def optimize_delivery_routes(
    network: List[List[Union[int, float]]],         # [u:int, v:int, capacity:float, base_cost:float, base_time:float]
    deliveries: List[Dict[str, Union[int, float, str]]],           # {"src":int,"dst":int,"type":str,"amount":float}
    priority_deliveries: List[Dict[str, Union[int, float, str]]],  # {"type":str,"src":int,"dst":int,"deadline":float,"required":float}
    traffic_variance: Dict[str, float],             # "u-v" (directed) -> variance (time^2)
    vehicle_capacity: Dict[str, float],             # vehicle -> capacity (amount per driver-hour)
    driver_constraints: Dict[str, float],           # vehicle -> driver-hours budget
    congestion_factor: float,                       # scales cost & time; variance scales by factor^2
    hash_seed: int,                                 # deterministic tie-breaking seed
    probabilistic_threshold: float                  # on-time probability threshold for priority deliveries
) -> Dict[str, Any]:
    # Build graph
    adj = {}
    edge_info = {}  # (u,v) -> (capacity, base_cost, base_time)
    for u, v, cap, cost, time in network:
        u = int(u); v = int(v)
        adj.setdefault(u, []).append(v)
        edge_info[(u, v)] = (float(cap), float(cost), float(time))
    # vehicles sorted
    vehicles = sorted(vehicle_capacity.keys())
    # state
    remaining_capacity = {e: edge_info[e][0] for e in edge_info}
    remaining_driver = {veh: float(driver_constraints.get(veh, 0.0)) for veh in vehicles}
    resource_usage = {veh: 0.0 for veh in vehicles}
    routes = []
    delivery_status = []
    metrics_paths = 0
    metrics_ties = 0

    # helper: normal CDF
    def Phi(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    # find k-shortest simple paths? For simplicity, use Dijkstra on expected cost weights to get single best path.
    # To be deterministic and consider ties, when multiple neighbors, sort adjacency.
    for k in adj:
        adj[k].sort()
    # Precompute shortest path by expected cost (base_cost * congestion_factor)
    def shortest_path(src, dst):
        nonlocal metrics_paths
        # Dijkstra
        pq = []
        heapq.heappush(pq, (0.0, 0, [src], src))
        visited = {}
        while pq:
            cost, edges_cnt, path, node = heapq.heappop(pq)
            if node == dst:
                metrics_paths += 1
                return path, cost, edges_cnt
            if node in visited and visited[node] <= cost:
                continue
            visited[node] = cost
            for nbr in adj.get(node, []):
                e = (node, nbr)
                if e not in edge_info:
                    continue
                add = edge_info[e][1] * congestion_factor
                new_cost = cost + add
                new_edges = edges_cnt + 1
                new_path = path + [nbr]
                heapq.heappush(pq, (new_cost, new_edges, new_path, nbr))
        metrics_paths += 1
        return None, float('inf'), 0

    # tie jitter using sha256
    def jitter_value(key_str):
        h = hashlib.sha256((str(hash_seed) + "|" + key_str).encode()).digest()
        # take first 8 bytes
        val = int.from_bytes(h[:8], 'big') / (1 << 64)
        return (val * 1e-6)

    # vehicle chooser: highest remaining budget ratio = remaining_driver / driver_constraints
    def choose_vehicle_for_path(path, amount):
        # compute required driver-hours per vehicle = sum(base_time * congestion_factor * amount) / vehicle_capacity[veh]
        total_base_time = 0.0
        for i in range(len(path)-1):
            e = (path[i], path[i+1])
            total_base_time += edge_info[e][2] * congestion_factor
        best = None
        best_key = None
        for veh in vehicles:
            cap = vehicle_capacity[veh]
            if cap <= 0:
                continue
            req_driver_hours = (total_base_time * amount) / cap
            rem = remaining_driver.get(veh, 0.0)
            if req_driver_hours <= rem + 1e-12:
                ratio = (rem / driver_constraints[veh]) if driver_constraints[veh] > 0 else 0.0
                key = ( -ratio, veh )  # negative so max ratio becomes min key
                if best is None or key < best_key:
                    best = (veh, req_driver_hours)
                    best_key = key
                elif key == best_key:
                    # tie by lexicographic veh because vehicles sorted ensures deterministic
                    pass
        return best  # (veh, req_driver_hours) or None

    # process deliveries: priority first sorted deterministically by (type, src, dst, required)
    def sort_priority_list(lst):
        return sorted(lst, key=lambda x: (str(x.get('type','')), int(x.get('src',0)), int(x.get('dst',0)), float(x.get('required',0.0))))
    def sort_normal_list(lst):
        return sorted(lst, key=lambda x: (str(x.get('type','')), int(x.get('src',0)), int(x.get('dst',0)), float(x.get('amount',0.0))))
    priority_sorted = sort_priority_list(priority_deliveries)
    normal_sorted = sort_normal_list(deliveries)

    # helper to evaluate path feasibility for priority: compute on-time probability
    def path_on_time_prob(path, deadline):
        mu = 0.0
        var = 0.0
        for i in range(len(path)-1):
            e = (path[i], path[i+1])
            base_time = edge_info[e][2]
            mu += base_time * congestion_factor
            key = f"{e[0]}-{e[1]}"
            v = traffic_variance.get(key, 0.0)
            var += v * (congestion_factor ** 2)
        sigma = math.sqrt(var) if var > 0 else 0.0
        if sigma == 0.0:
            return 1.0 if deadline >= mu - 1e-12 else 0.0
        return Phi((deadline - mu) / sigma)

    expected_cost = 0.0

    # assign function shared
    def assign_delivery_entry(deliv, is_priority=False):
        nonlocal expected_cost, metrics_ties
        src = int(deliv.get('src'))
        dst = int(deliv.get('dst'))
        amount = float(deliv.get('required' if is_priority else 'amount', 0.0))
        dtype = str(deliv.get('type'))
        deadline = float(deliv.get('deadline', 0.0)) if is_priority else 0.0
        # find shortest path
        path, cost_val, edges_cnt = shortest_path(src, dst)
        if path is None:
            delivered = 0.0
            on_time = 0.0 if is_priority else 1.0
            delivery_status.append({
                "delivery_type": dtype,
                "src": src,
                "dst": dst,
                "requested": amount,
                "delivered": delivered,
                "is_priority": is_priority,
                "deadline": deadline,
                "on_time_probability": on_time,
                "route": []
            })
            return
        # check priority feasibility
        if is_priority:
            on_time = path_on_time_prob(path, deadline)
            if on_time + 1e-12 < probabilistic_threshold:
                # cannot satisfy priority -> deliver zero
                delivery_status.append({
                    "delivery_type": dtype,
                    "src": src,
                    "dst": dst,
                    "requested": amount,
                    "delivered": 0.0,
                    "is_priority": True,
                    "deadline": deadline,
                    "on_time_probability": on_time,
                    "route": []
                })
                return
        else:
            on_time = 1.0
        # check edge capacities
        bottleneck = float('inf')
        for i in range(len(path)-1):
            e = (path[i], path[i+1])
            bottleneck = min(bottleneck, remaining_capacity[e])
        deliverable = min(amount, bottleneck)
        if deliverable <= 0.0:
            delivery_status.append({
                "delivery_type": dtype,
                "src": src,
                "dst": dst,
                "requested": amount,
                "delivered": 0.0,
                "is_priority": is_priority,
                "deadline": deadline,
                "on_time_probability": on_time,
                "route": []
            })
            return
        # choose vehicle
        veh_choice = choose_vehicle_for_path(path, deliverable)
        if veh_choice is None:
            # try reduce amount to fit some vehicle: find max amount that any vehicle can support by driver-hours and capacity
            total_base_time = 0.0
            for i in range(len(path)-1):
                e = (path[i], path[i+1])
                total_base_time += edge_info[e][2] * congestion_factor
            max_deliverable = 0.0
            chosen = None
            for veh in vehicles:
                cap = vehicle_capacity[veh]
                rem = remaining_driver.get(veh, 0.0)
                if cap <= 0:
                    continue
                max_amount = (rem * cap) / total_base_time if total_base_time > 0 else 0.0
                # also capacity edges
                for i in range(len(path)-1):
                    e = (path[i], path[i+1])
                    max_amount = min(max_amount, remaining_capacity[e])
                if max_amount > max_deliverable + 1e-12:
                    max_deliverable = max_amount
                    chosen = (veh, (total_base_time * max_amount) / cap if cap>0 else 0.0)
            if chosen is None or max_deliverable <= 0.0:
                delivery_status.append({
                    "delivery_type": dtype,
                    "src": src,
                    "dst": dst,
                    "requested": amount,
                    "delivered": 0.0,
                    "is_priority": is_priority,
                    "deadline": deadline,
                    "on_time_probability": on_time,
                    "route": []
                })
                return
            deliverable = max_deliverable
            veh, req_hours = chosen
        else:
            veh, req_hours = veh_choice
        # finalize assign
        # update edges
        for i in range(len(path)-1):
            e = (path[i], path[i+1])
            remaining_capacity[e] -= deliverable
        remaining_driver[veh] -= req_hours
        resource_usage[veh] += req_hours
        # expected cost add: sum(base_cost * amount * congestion_factor)
        path_cost = 0.0
        for i in range(len(path)-1):
            e = (path[i], path[i+1])
            path_cost += edge_info[e][1] * congestion_factor * deliverable
        expected_cost += path_cost
        # append route entry: u v delivery_type amount vehicle, but requirement uses per-edge entries in routes list?
        # Problem demands route entries as single entry per delivery using path edges. The Output format shows u,v per route (single-edge path).
        # For multi-edge, produce one route per edge with same delivery_type/amount/vehicle in order u->v.
        for i in range(len(path)-1):
            routes.append({"u": path[i], "v": path[i+1], "delivery_type": dtype, "amount": deliverable, "vehicle": veh})
        delivery_status.append({
            "delivery_type": dtype,
            "src": src,
            "dst": dst,
            "requested": amount,
            "delivered": deliverable,
            "is_priority": is_priority,
            "deadline": deadline,
            "on_time_probability": on_time,
            "route": path
        })

    # process priority then normal
    for p in priority_sorted:
        assign_delivery_entry(p, is_priority=True)
    for d in normal_sorted:
        assign_delivery_entry(d, is_priority=False)

    # ensure sorted dicts
    resource_usage_sorted = {k: resource_usage[k] for k in sorted(resource_usage.keys())}
    metrics = {"paths_considered": metrics_paths, "ties_broken": metrics_ties}
    # final expected_cost rounded to reasonable floating representation
    return {
        "routes": routes,
        "expected_cost": expected_cost,
        "delivery_status": delivery_status,
        "resource_usage": resource_usage_sorted,
        "metrics": metrics
    }