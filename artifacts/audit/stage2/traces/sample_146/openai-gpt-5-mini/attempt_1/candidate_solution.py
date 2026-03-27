def adaptive_topological_sort(graph_input: dict) -> dict:
    deliveries = graph_input.get("deliveries", None)
    constraints = graph_input.get("constraints", [])
    new_constraints = graph_input.get("new_constraints", [])
    errors = []

    # Validation step 1
    if not deliveries:
        return {"success": False, "errors": ["Deliveries list cannot be empty."]}

    # Step 2 duplicates
    dup = [item for item, cnt in Counter(deliveries).items() if cnt > 1]
    if dup:
        errors.append(f"Duplicate deliveries found: {sorted(dup)}")

    # Step 3 None in deliveries
    if any(d is None for d in deliveries):
        errors.append("Deliveries list contains None values.")

    # Step 4 process constraints and new_constraints for validation
    seen_constraints = set()
    all_constraints = []
    for c_list in (constraints or []):
        all_constraints.append(c_list)
    for c_list in (new_constraints or []):
        all_constraints.append(c_list)

    for c in all_constraints:
        if not isinstance(c, (list, tuple)):
            errors.append(f"Constraint {c} does not have exactly two elements.")
            continue
        if len(c) != 2:
            errors.append(f"Constraint {list(c)} does not have exactly two elements.")
            continue
        a, b = c[0], c[1]
        if a == b:
            errors.append(f"Self-loop detected: {list(c)}")
        if a not in deliveries:
            errors.append(f"Predecessor '{a}' not in deliveries.")
        if b not in deliveries:
            errors.append(f"Successor '{b}' not in deliveries.")
        t = (a, b)
        if t in seen_constraints:
            errors.append(f"Duplicate constraint: {list(c)}")
        else:
            seen_constraints.add(t)

    if errors:
        return {"success": False, "errors": errors}

    # Now success validation passed
    success = True

    # Build graph
    nodes = list(deliveries)
    forward = {n: [] for n in nodes}
    reverse = {n: [] for n in nodes}
    total_edges = 0
    combined_constraints = []
    for c in (constraints or []) + (new_constraints or []):
        if not isinstance(c, (list, tuple)) or len(c) != 2:
            continue
        u, v = c[0], c[1]
        if u in forward and v in forward:
            forward[u].append(v)
            reverse[v].append(u)
            total_edges += 1
            combined_constraints.append([u, v])

    # Cycle detection via DFS 3-color
    color = {n: 0 for n in nodes}
    parent = {n: None for n in nodes}
    cycle_nodes = []
    found_cycle = False

    def dfs(u, path):
        nonlocal found_cycle, cycle_nodes
        if found_cycle:
            return
        color[u] = 1
        path.append(u)
        for v in forward.get(u, []):
            if found_cycle:
                return
            if color[v] == 0:
                parent[v] = u
                dfs(v, path)
            elif color[v] == 1:
                # back edge
                if not found_cycle:
                    try:
                        idx = path.index(v)
                        cyc = sorted(set(path[idx:]))
                    except ValueError:
                        cyc = sorted({v, u})
                    cycle_nodes = cyc
                    found_cycle = True
                    return
        path.pop()
        color[u] = 2

    for n in sorted(nodes):
        if color[n] == 0 and not found_cycle:
            dfs(n, [])

    has_cycle = found_cycle
    sorted_deliveries = []

    # Kahn's algorithm if no cycle
    if not has_cycle:
        in_deg = {n: len(reverse[n]) for n in nodes}
        q = deque(sorted([n for n in nodes if in_deg[n] == 0]))
        result = []
        while q:
            u = q.popleft()
            result.append(u)
            for v in sorted(forward.get(u, [])):
                in_deg[v] -= 1
                if in_deg[v] == 0:
                    q.append(v)
        if len(result) == len(nodes):
            sorted_deliveries = result
        else:
            # fallback empty if mismatch
            sorted_deliveries = []
    else:
        sorted_deliveries = []

    # Dependency metrics
    in_degree = {n: len(reverse[n]) for n in nodes}
    out_degree = {n: len(forward[n]) for n in nodes}

    # Depth levels BFS from sources (in-degree 0)
    depth_levels = {n: -1 for n in nodes}
    sources = sorted([n for n in nodes if in_degree[n] == 0])
    dq = deque()
    for s in sources:
        dq.append((s, 0))
        depth_levels[s] = 0
    while dq:
        u, lvl = dq.popleft()
        for v in forward.get(u, []):
            if lvl + 1 > depth_levels[v]:
                depth_levels[v] = lvl + 1
                dq.append((v, lvl + 1))
    # Set unreachable to 0
    for n in nodes:
        if depth_levels[n] == -1:
            depth_levels[n] = 0

    # Independent clusters: undirected connectivity
    undirected = {n: set() for n in nodes}
    for u in nodes:
        for v in forward[u]:
            undirected[u].add(v)
            undirected[v].add(u)
    visited = set()
    clusters = 0
    for n in nodes:
        if n not in visited:
            clusters += 1
            stack = [n]
            visited.add(n)
            while stack:
                x = stack.pop()
                for y in undirected[x]:
                    if y not in visited:
                        visited.add(y)
                        stack.append(y)

    dependency_metrics = {
        "in_degree": dict(sorted(in_degree.items())),
        "out_degree": dict(sorted(out_degree.items())),
        "depth_levels": dict(sorted(depth_levels.items())),
        "independent_clusters": clusters
    }

    # Graph statistics
    total_nodes = len(nodes)
    total_edges = total_edges
    avg_in = round(sum(in_degree.values()) / total_nodes, 4) if total_nodes > 0 else 0.0
    avg_out = round(sum(out_degree.values()) / total_nodes, 4) if total_nodes > 0 else 0.0
    max_depth = max(depth_levels.values()) if depth_levels else 0

    # density = edges / (n*(n-1))
    density = round((total_edges / (total_nodes * (total_nodes - 1))) if total_nodes > 1 else 0.0, 3)

    # critical_path_count: count of nodes having depth == max_depth
    critical_path_count = sum(1 for v in depth_levels.values() if v == max_depth)

    # degree centralization
    degrees = {n: in_degree[n] + out_degree[n] for n in nodes}
    max_deg = max(degrees.values()) if degrees else 0
    if total_nodes > 1:
        denom = ((total_nodes - 1) * 2 * (total_nodes - 1))
        degree_centralization = round(sum((max_deg - d) for d in degrees.values()) / denom, 2)
    else:
        degree_centralization = 0.0

    source_ratio = round(len([n for n in nodes if in_degree[n] == 0]) / total_nodes, 5) if total_nodes > 0 else 0.0
    sink_ratio = round(len([n for n in nodes if out_degree[n] == 0]) / total_nodes, 5) if total_nodes > 0 else 0.0

    # Betweenness centrality (approx exact for small graphs using BFS for all pairs)
    bet = {n: 0.0 for n in nodes}
    for s in nodes:
        # BFS shortest paths count
        S = []
        P = {w: [] for w in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        dist = dict.fromkeys(nodes, -1)
        sigma[s] = 1.0
        dist[s] = 0
        Q = deque([s])
        while Q:
            v = Q.popleft()
            S.append(v)
            for w in forward.get(v, []):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    Q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while S:
            w = S.pop()
            for v in P[w]:
                if sigma[w] != 0:
                    delta_v = (sigma[v] / sigma[w]) * (1.0 + delta[w])
                    delta[v] += delta_v
            if w != s:
                bet[w] += delta[w]
    # normalize? use raw counts
    bet_vals = list(bet.values())
    bet_avg = round(sum(bet_vals) / total_nodes, 4) if total_nodes > 0 else 0.0
    max_b_node = max(bet.items(), key=lambda x: (x[1], x[0])) if bet else (None, 0.0)
    bet_max_node = max_b_node[0] if max_b_node[0] is not None else ""
    bet_max_score = round(max_b_node[1], 4) if max_b_node[0] is not None else 0.0

    # PageRank based on incoming deps
    pr = {n: 1.0 / total_nodes for n in nodes} if total_nodes > 0 else {}
    d = 0.85
    for _ in range(10):
        newpr = {}
        for n in nodes:
            inbound = reverse.get(n, [])
            s = 0.0
            for q in inbound:
                outq = len(forward.get(q, []))
                s += pr[q] / outq if outq > 0 else 0.0
            newpr[n] = (1 - d) / total_nodes + d * s
        pr = newpr
    pr_avg = round(sum(pr.values()) / total_nodes, 6) if total_nodes > 0 else 0.0
    top_nodes = sorted(pr.items(), key=lambda x: (-x[1], x[0]))[:3]
    top_nodes_list = [[n, round(v, 6)] for n, v in top_nodes]

    # Longest path length in DAG using topological order
    longest_path_length = 0
    if sorted_deliveries:
        lp = {n: 0 for n in nodes}
        for u in sorted_deliveries:
            for v in forward.get(u, []):
                if lp[u] + 1 > lp[v]:
                    lp[v] = lp[u] + 1
        longest_path_length = max(lp.values()) if lp else 0
    else:
        # if cycle, approximate as max depth
        longest_path_length = max_depth

    # Width metrics (by depth_levels)
    level_dist = Counter()
    for n, lvl in depth_levels.items():
        level_dist[str(lvl)] += 1
    max_width = max(level_dist.values()) if level_dist else 0
    avg_width = round(sum(level_dist.values()) / len(level_dist) if level_dist else 0.0, 2)
    level_distribution = dict(sorted({k: v for k, v in level_dist.items()}.items(), key=lambda x: int(x[0])))

    # Transitive reduction ratio: compute reachability via floyd-warshall or BFS per node
    reach = {n: set() for n in nodes}
    for n in nodes:
        # BFS
        q = deque([n])
        visited_r = set()
        while q:
            u = q.popleft()
            for v in forward.get(u, []):
                if v not in visited_r:
                    visited_r.add(v)
                    q.append(v)
        reach[n] = visited_r
    # An edge u->v is redundant if there exists a path u->...->v of length >=2 excluding direct edge
    redundant = 0
    for u in nodes:
        for v in list(forward[u]):
            # Temporarily remove direct edge and see if v still reachable
            found = False
            q = deque([u])
            visited_r = set([u])
            while q and not found:
                x = q.popleft()
                for y in forward.get(x, []):
                    if x == u and y == v:
                        continue
                    if y == v:
                        found = True
                        break
                    if y not in visited_r:
                        visited_r.add(y)
                        q.append(y)
            if found:
                redundant += 1
    transitive_reduction_ratio = round(redundant / total_edges if total_edges > 0 else 0.0, 4)

    # Fan metrics
    fin = sorted([in_degree[n] for n in nodes])
    fout = sorted([out_degree[n] for n in nodes])
    def median(lst):
        if not lst:
            return 0
        l = len(lst)
        if l % 2 == 1:
            return lst[l//2]
        return (lst[l//2 -1] + lst[l//2]) / 2
    max_fan_in = max(fin) if fin else 0
    max_fan_out = max(fout) if fout else 0
    median_fan_in = median(fin)
    median_fan_out = median(fout)

    # Bottleneck nodes: top 75th percentile by (in+out)
    deg_list = sorted([(n, in_degree[n] + out_degree[n]) for n in nodes], key=lambda x: -x[1])
    if deg_list:
        threshold_idx = max(0, int(math.ceil(0.75 * total_nodes)) - 1)
        threshold = deg_list[threshold_idx][1]
        bottlenecks = [n for n, d in deg_list if d >= threshold]
    else:
        bottlenecks = []
    bottleneck_count = len(bottlenecks)
    bottleneck_nodes = sorted(bottlenecks)[:5]

    # Clustering coefficient average (undirected)
    clustering_sum = 0.0
    for n in nodes:
        neigh = undirected[n]
        k = len(neigh)
        if k < 2:
            continue
        links = 0
        neigh_list = list(neigh)
        for i in range(len(neigh_list)):
            for j in range(i+1, len(neigh_list)):
                a = neigh_list[i]
                b = neigh_list[j]
                if b in undirected[a]:
                    links += 1
        possible = k * (k - 1) / 2
        clustering_sum += (links / possible) if possible > 0 else 0.0
    clustering_coefficient = round((clustering_sum / total_nodes) if total_nodes > 0 else 0.0, 4)

    # Degree variance
    deg_vals = [in_degree[n] + out_degree[n] for n in nodes]
    mean_deg = sum(deg_vals) / total_nodes if total_nodes > 0 else 0.0
    variance = sum((x - mean_deg) ** 2 for x in deg_vals) / total_nodes if total_nodes > 0 else 0.0
    degree_variance = round(variance, 4)

    # Parallelization factor
    parallelization_factor = round(total_nodes / (max_depth + 1) if (max_depth + 1) > 0 else 0.0, 4)

    graph_statistics = {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "average_in_degree": avg_in,
        "average_out_degree": avg_out,
        "max_depth": max_depth,
        "density": density,
        "critical_path_count": critical_path_count,
        "degree_centralization": degree_centralization,
        "source_ratio": source_ratio,
        "sink_ratio": sink_ratio,
        "betweenness_centrality": {"average": bet_avg, "max_node": bet_max_node, "max_score": bet_max_score},
        "pagerank": {"average": pr_avg, "top_nodes": top_nodes_list},
        "longest_path_length": longest_path_length,
        "width_metrics": {"max_width": max_width, "average_width": avg_width, "level_distribution": level_distribution},
        "transitive_reduction_ratio": transitive_reduction_ratio,
        "fan_metrics": {"max_fan_in": max_fan_in, "max_fan_out": max_fan_out, "median_fan_in": median_fan_in, "median_fan_out": median_fan_out},
        "bottleneck_count": bottleneck_count,
        "bottleneck_nodes": bottleneck_nodes,
        "clustering_coefficient": clustering_coefficient,
        "degree_variance": degree_variance,
        "parallelization_factor": parallelization_factor
    }

    # Update log for each new_constraint with exactly 2 elements
    update_log = []
    final_result_str = "cycle detected" if has_cycle else "reordered successfully"
    for c in (new_constraints or []):
        if isinstance(c, (list, tuple)) and len(c) == 2:
            update_log.append({
                "action": "insert_constraint",
                "constraint": [c[0], c[1]],
                "result": final_result_str,
                "cycle_detected": has_cycle
            })

    out = {
        "success": success,
        "sorted_deliveries": sorted_deliveries,
        "has_cycle": has_cycle,
        "cycle_nodes": sorted(cycle_nodes) if cycle_nodes else [],
        "dependency_metrics": dependency_metrics,
        "graph_statistics": graph_statistics,
        "update_log": update_log,
        "errors": []
    }
    return out