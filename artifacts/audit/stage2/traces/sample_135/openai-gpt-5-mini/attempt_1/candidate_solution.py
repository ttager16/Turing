def find_emergency_route(graph_nodes: List[int], uncertain_edges: List[Dict],
                        start_node: int, end_node: int) -> Dict[str, Any]:
    # Input validations
    if not isinstance(graph_nodes, list):
        return {"error": "Input is not valid"}
    if len(graph_nodes) == 0:
        return {"error": "Empty graph provided"}
    node_set = set(graph_nodes)
    if start_node not in node_set or end_node not in node_set:
        return {"error": "Start or end node not in graph"}
    # Build adjacency and compute per-edge stats
    adj = {n: [] for n in graph_nodes}
    edge_info = {}
    for e in uncertain_edges:
        try:
            u = e["from_node"]; v = e["to_node"]; scenarios = e["scenarios"]; eid = e["edge_id"]
        except Exception:
            return {"error": "Input is not valid"}
        if u not in node_set or v not in node_set:
            return {"error": "Invalid node ID"}
        if not isinstance(scenarios, list) or len(scenarios) == 0:
            return {"error": f"Invalid scenario data for edge {eid}"}
        # probability sum check
        prob_sum = 0.0
        for s in scenarios:
            if "probability" not in s or "travel_time" not in s:
                return {"error": f"Invalid scenario data for edge {eid}"}
            prob_sum += float(s["probability"])
        if abs(prob_sum - 1.0) > 0.001:
            return {"error": "Edge probabilities do not sum to 1.0"}
        # compute expected
        expected = sum(float(s["travel_time"]) * float(s["probability"]) for s in scenarios)
        threshold = 1.25 * expected
        reliability = sum(float(s["probability"]) for s in scenarios if float(s["travel_time"]) <= threshold)
        if reliability == 0.0:
            reliability = 1.0
        # store
        edge_rec = {
            "from_node": u, "to_node": v, "scenarios": [(float(s["travel_time"]), float(s["probability"])) for s in scenarios],
            "expected_time": expected, "reliability": reliability, "edge_id": eid
        }
        adj[u].append(edge_rec)
        edge_info[(u, v, eid)] = edge_rec
    # Helper to compute path metrics and scenario validation
    RELIABILITY_PENALTY = 50.0
    def compute_path_metrics(path_edges):
        # path_edges: list of edge_rec in order
        exp_total = sum(e["expected_time"] for e in path_edges)
        path_reliability = 1.0
        for e in path_edges:
            path_reliability *= e["reliability"]
        total_score = exp_total + RELIABILITY_PENALTY * (1.0 - path_reliability)
        return exp_total, path_reliability, total_score
    def scenario_consistent(path_edges):
        # build list of scenario lists
        scen_lists = [e["scenarios"] for e in path_edges]
        if len(scen_lists) == 0:
            return True
        expected_sum = sum(e["expected_time"] for e in path_edges)
        limit = 2.0 * expected_sum
        # iterate combinations, but cutoff if too many combinations: limit to 100000 combos for performance
        total_combos = 1
        for sl in scen_lists:
            total_combos *= len(sl)
            if total_combos > 100000:
                break
        # If too many combos, do probabilistic pruning: check worst-case only (max sum) and a sample of combos
        if total_combos > 100000:
            max_sum = sum(max(t for t,p in sl) for sl in scen_lists)
            if max_sum > limit:
                return False
            # sample some combos (deterministic: take first elements, last elements, and pairs)
            samples = []
            # all-min
            samples.append(tuple(sl[0] for sl in scen_lists))
            # all-max
            samples.append(tuple(sl[-1] for sl in scen_lists))
            # mixed: for i cycle take max at i
            for i in range(len(scen_lists)):
                comb = []
                for j, sl in enumerate(scen_lists):
                    if i == j:
                        comb.append(sl[-1])
                    else:
                        comb.append(sl[0])
                samples.append(tuple(comb))
            for comb in samples:
                ssum = sum(t for t,p in comb)
                if ssum > limit:
                    return False
            return True
        # exact check
        for prod in itertools.product(*scen_lists):
            ssum = sum(t for t,p in prod)
            if ssum > limit:
                return False
        return True
    # Modified Dijkstra: state is node with path (sequence). We maintain best seen by (score, path lexicographic)
    # Use heap of (score, path_as_tuple, expected_time, -reliability, node, path_edges_list)
    heap = []
    # initial
    heapq.heappush(heap, (0.0, (start_node,), 0.0, -1.0, start_node, []))
    visited_best = {}  # (node, path_tuple) -> score not needed; we keep best score per node with lexicographic tie
    final_candidates = []
    while heap:
        score, path_tuple, exp_time_so_far, neg_rel, node, path_edges = heapq.heappop(heap)
        # if path_tuple not consistent with last node, continue
        if path_tuple[-1] != node:
            continue
        # If reached end, validate scenario consistency and record
        if node == end_node:
            if scenario_consistent(path_edges):
                exp_total, path_rel, total_score = compute_path_metrics(path_edges)
                final_candidates.append((total_score, path_tuple, exp_total, path_rel, path_edges))
                # continue search to find possibly better lexicographic same score
                # do not break
        # Explore neighbors
        for e in adj.get(node, []):
            v = e["to_node"]
            if v in path_tuple:
                # avoid cycles
                continue
            new_path_edges = path_edges + [e]
            # quick compute expected and reliability incrementally
            new_exp = exp_time_so_far + e["expected_time"]
            # compute partial path metrics for priority
            # compute path_reliability product
            # reconstruct reliability product from neg_rel
            prev_rel = -neg_rel if neg_rel != -1.0 else 1.0
            new_rel = prev_rel * e["reliability"]
            new_score = new_exp + RELIABILITY_PENALTY * (1.0 - new_rel)
            new_path_tuple = path_tuple + (v,)
            # scenario consistency check early: compute expected_total for path and test combinations
            # Only if consistent, push
            if scenario_consistent(new_path_edges):
                heapq.heappush(heap, (new_score, new_path_tuple, new_exp, -new_rel, v, new_path_edges))
    if not final_candidates:
        return {"error": "No path exists between start and end nodes"}
    # select best by score then lexicographic path
    final_candidates.sort(key=lambda x: (x[0], list(x[1])))
    best = final_candidates[0]
    total_score, path_tuple, exp_total, path_rel, path_edges = best
    # scenario analysis: compute all combinations stats (best, worst, variance)
    scen_lists = [e["scenarios"] for e in path_edges]
    times = []
    probs = []
    total_combos = 1
    for sl in scen_lists:
        total_combos *= len(sl)
        if total_combos > 100000:
            break
    if total_combos > 100000:
        # approximate by sampling deterministic combinations: all-min, all-max, and per-edge variations weighted by probabilities
        # build a weighted distribution by convolution approximated via pairwise combining but limited
        # fallback: compute expected variance via sum of variances if independence assumed
        # compute mean = exp_total
        mean = exp_total
        var = 0.0
        for e in path_edges:
            # edge variance
            ex = e["expected_time"]
            v = sum(((t - ex) ** 2) * p for t,p in e["scenarios"])
            var += v
        best_time = sum(min(t for t,p in e["scenarios"]) for e in path_edges)
        worst_time = sum(max(t for t,p in e["scenarios"]) for e in path_edges)
        variance = var
    else:
        combs = list(itertools.product(*scen_lists))
        times = [sum(t for t,p in comb) for comb in combs]
        probs = [1.0]
        # compute combined probabilities
        probs = [1.0 for _ in combs]
        for idx, comb in enumerate(combs):
            p = 1.0
            for t,p_s in comb:
                p *= p_s
            probs[idx] = p
        # normalize (should sum to 1)
        # compute mean, variance
        mean = sum(t * p for t,p in zip(times, probs))
        variance = sum(((t - mean) ** 2) * p for t,p in zip(times, probs))
        best_time = min(times)
        worst_time = max(times)
    # assemble edge_details
    edge_details = []
    for e in path_edges:
        edge_details.append({
            "from_node": e["from_node"],
            "to_node": e["to_node"],
            "expected_time": round(e["expected_time"], 6),
            "reliability": round(e["reliability"], 6),
            "edge_id": e["edge_id"]
        })
    result = {
        "path": list(path_tuple),
        "expected_travel_time": round(exp_total, 6),
        "path_reliability": round(path_rel, 6),
        "total_path_score": round(total_score, 6),
        "scenario_analysis": {
            "best_case_time": round(best_time, 6),
            "worst_case_time": round(worst_time, 6),
            "variance": round(variance, 6)
        },
        "edge_details": edge_details
    }
    return result