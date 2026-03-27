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
    # Build adjacency, compute per-edge stats
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
        # Validate probabilities
        prob_sum = 0.0
        for s in scenarios:
            if ("travel_time" not in s) or ("probability" not in s):
                return {"error": f"Invalid scenario data for edge {eid}"}
            prob_sum += float(s["probability"])
        if abs(prob_sum - 1.0) > 0.001:
            return {"error": "Edge probabilities do not sum to 1.0"}
        # compute expected time
        expected = 0.0
        for s in scenarios:
            expected += float(s["travel_time"]) * float(s["probability"])
        threshold = 1.25 * expected
        reliability = 0.0
        for s in scenarios:
            if float(s["travel_time"]) <= threshold:
                reliability += float(s["probability"])
        if reliability == 0.0:
            reliability = 1.0
        # store
        info = {
            "from": u, "to": v, "scenarios": [(float(s["travel_time"]), float(s["probability"])) for s in scenarios],
            "expected": expected, "reliability": reliability, "edge_id": eid
        }
        adj[u].append(info)
        edge_info[(u,v,eid)] = info
    # Modified Dijkstra: state holds cumulative expected time, cumulative reliability(product), path, edge list
    REL_PENALTY = 50.0
    # For visited maintain best score found to node with given path reliability maybe composite; to ensure correctness we store best total_path_score and tie-break by lexicographic path
    # Priority queue by (total_path_score, expected_time, -path_reliability, path_tuple)
    heap = []
    start_state = (0.0, 1.0, (start_node,), [])  # expected_sum, reliability_prod, path nodes, edges list (infos)
    start_score = 0.0 + REL_PENALTY * (1 - 1.0)
    heapq.heappush(heap, (start_score, 0.0, -1.0, (start_node,), []))
    # visited: node -> dict mapping (expected_time rounded, reliability rounded) to best score to prune; but keep simple: best score per node and path tuple for lexicographic tie
    visited_best = {}
    valid_paths = []
    # Helper: scenario consistency check for a path (list of edge infos)
    def path_scenario_consistent(edge_infos, expected_total):
        # generate all combinations of one scenario per edge
        # If too many combos, we can early abort if combos exceed 20000 to avoid explosion; but problem expects up to small paths. Implement safe cap.
        combos = 1
        for ei in edge_infos:
            combos *= len(ei["scenarios"])
            if combos > 20000:
                # fallback conservative: sample extremes by taking min and max combos; here perform full check by bounding sums: compute max_possible and if max_possible <= 2*expected_total okay; if min_possible > 2*expected_total fail; else do partial check by sampling combinations including extremes
                max_possible = sum(max(t for t,p in ei["scenarios"]) for ei in edge_infos)
                min_possible = sum(min(t for t,p in ei["scenarios"]) for ei in edge_infos)
                if max_possible <= 2*expected_total:
                    return True
                if min_possible > 2*expected_total:
                    return False
                # sample combinations including all max/min per edge and some mixed
                # check all combos of choosing either min or max for each edge (2^k)
                k = len(edge_infos)
                for mask in range(1<<k):
                    s = 0.0
                    for i in range(k):
                        times = [t for t,p in edge_infos[i]["scenarios"]]
                        if (mask>>i)&1:
                            s += max(times)
                        else:
                            s += min(times)
                    if s > 2*expected_total:
                        return False
                return True
        # if combos manageable, iterate all
        for prod in itertools.product(*[ei["scenarios"] for ei in edge_infos]):
            s = sum(p[0] for p in prod)
            if s > 2*expected_total:
                return False
        return True

    while heap:
        total_score, exp_sum, neg_rel, path_tuple, edge_list = heapq.heappop(heap)
        rel_prod = -neg_rel
        current = path_tuple[-1]
        # prune by visited_best
        key = (current, tuple(path_tuple))
        if key in visited_best and visited_best[key] <= total_score:
            continue
        visited_best[key] = total_score
        # If reached end, validate scenario consistency and record
        if current == end_node:
            # validate scenario consistency
            if path_scenario_consistent(edge_list, exp_sum):
                valid_paths.append((total_score, exp_sum, rel_prod, list(path_tuple), list(edge_list)))
                # continue exploring to find possibly better lexicographic tie
                # but we can continue; do not early return
        # expand neighbors
        for ei in adj.get(current, []):
            v = ei["to"]
            new_exp = exp_sum + ei["expected"]
            new_rel = rel_prod * ei["reliability"]
            new_score = new_exp + REL_PENALTY * (1 - new_rel)
            new_path = path_tuple + (v,)
            new_edges = edge_list + [ei]
            # quick pruning: if visited node with same path tuple exists better skip handled by visited_best
            # push
            heapq.heappush(heap, (new_score, new_exp, -new_rel, new_path, new_edges))
    if not valid_paths:
        return {"error": "No path exists between start and end nodes"}
    # choose best: minimal total_score, tie-break expected_time, then lexicographic path
    valid_paths.sort(key=lambda x: (round(x[0], 10), round(x[1], 10), x[3]))
    best = valid_paths[0]
    total_score, exp_sum, rel_prod, path_nodes, edge_list = best
    # scenario analysis: best_case = sum min times per edge, worst_case = sum max, variance across all combinations
    times_lists = [ [t for t,p in ei["scenarios"]] for ei in edge_list ]
    best_case = sum(min(lst) for lst in times_lists) if times_lists else 0.0
    worst_case = sum(max(lst) for lst in times_lists) if times_lists else 0.0
    # compute distribution of path times: combine scenario probabilities
    # compute all combinations (cap high combos similar to above)
    combos = 1
    for ei in edge_list:
        combos *= len(ei["scenarios"])
    mean = exp_sum
    variance = 0.0
    if combos <= 20000:
        # compute expected of square and then variance
        exp_sq = 0.0
        for prod in itertools.product(*[ei["scenarios"] for ei in edge_list]):
            prob = 1.0
            tsum = 0.0
            for t,p in prod:
                tsum += t
                prob *= p
            exp_sq += (tsum*tsum) * prob
        variance = exp_sq - mean*mean
    else:
        # approximate variance by assuming independence and using sum of variances since edges independent
        var_sum = 0.0
        for ei in edge_list:
            # edge variance
            e_mean = ei["expected"]
            e_exp_sq = sum((t*t)*p for t,p in ei["scenarios"])
            var_sum += (e_exp_sq - e_mean*e_mean)
        variance = var_sum
    # assemble edge_details
    edge_details = []
    for ei in edge_list:
        edge_details.append({
            "from_node": ei["from"],
            "to_node": ei["to"],
            "expected_time": round(ei["expected"], 6),
            "reliability": round(ei["reliability"], 6),
            "edge_id": ei["edge_id"]
        })
    result = {
        "path": list(path_nodes),
        "expected_travel_time": round(exp_sum, 6),
        "path_reliability": round(rel_prod, 6),
        "total_path_score": round(total_score, 6),
        "scenario_analysis": {
            "best_case_time": round(best_case, 6),
            "worst_case_time": round(worst_case, 6),
            "variance": round(variance, 6)
        },
        "edge_details": edge_details
    }
    return result