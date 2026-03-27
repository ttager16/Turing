def adaptive_topological_sort(graph_input: dict) -> dict:
    # Input extraction with defaults
    deliveries = graph_input.get("deliveries", None)
    constraints = graph_input.get("constraints", []) or []
    new_constraints = graph_input.get("new_constraints", []) or []
    errors = []

    # Validation 1
    if not deliveries:
        return {"success": False, "errors": ["Deliveries list cannot be empty."]}

    # Validation 2 duplicates
    dup_counts = Counter(deliveries)
    duplicates = sorted([k for k, v in dup_counts.items() if v > 1])
    if duplicates:
        errors.append(f"Duplicate deliveries found: {duplicates}")

    # Validation 3 None values
    if any(d is None for d in deliveries):
        errors.append("Deliveries list contains None values.")

    # Prepare constraints combined
    all_constraints = []
    seen_constraints = set()
    # helper to process list
    def process_constraints_list(clist):
        nonlocal errors, all_constraints, seen_constraints
        for c in clist or []:
            # a.
            if not isinstance(c, (list, tuple)) or len(c) != 2:
                errors.append(f"Constraint {list(c) if not isinstance(c, list) else c} does not have exactly two elements.")
                continue
            a, b = c[0], c[1]
            # b.
            if a == b:
                errors.append(f"Self-loop detected: { [a, b] }")
            # c.
            if a not in deliveries:
                errors.append(f"Predecessor '{a}' not in deliveries.")
            if b not in deliveries:
                errors.append(f"Successor '{b}' not in deliveries.")
            # d. duplicate constraint
            tup = (a, b)
            if tup in seen_constraints:
                errors.append(f"Duplicate constraint: {[a, b]}")
            else:
                seen_constraints.add(tup)
                all_constraints.append([a, b])
    process_constraints_list(constraints)
    process_constraints_list(new_constraints)

    if errors:
        return {"success": False, "errors": errors}

    # Build adjacency lists
    nodes = list(deliveries)
    forward = {n: [] for n in nodes}
    reverse = {n: [] for n in nodes}
    total_edges = 0
    for a, b in all_constraints:
        if a in forward and b in forward:
            forward[a].append(b)
            reverse[b].append(a)
            total_edges += 1

    # Cycle detection via DFS 3-color
    color = {n: 0 for n in nodes}  # 0 white,1 gray,2 black
    parent = {n: None for n in nodes}
    cycle_nodes = []
    found_cycle = False

    def dfs(u, path):
        nonlocal found_cycle, cycle_nodes
        if found_cycle:
            return
        color[u] = 1
        path.append(u)
        for v in sorted(forward.get(u, [])):
            if found_cycle:
                return
            if color[v] == 0:
                parent[v] = u
                dfs(v, path)
            elif color[v] == 1:
                # back edge found
                idx = 0
                try:
                    idx = path.index(v)
                except ValueError:
                    idx = 0
                cyc = path[idx:] + [v]
                unique_nodes = sorted(set(cyc))
                cycle_nodes = unique_nodes
                found_cycle = True
                return
        path.pop()
        color[u] = 2

    for n in sorted(nodes):
        if color[n] == 0:
            dfs(n, [])
        if found_cycle:
            break

    has_cycle = found_cycle

    # Kahn's algorithm if no cycle
    sorted_deliveries = []
    if not has_cycle:
        in_deg = {n: len(reverse[n]) for n in nodes}
        zero_nodes = sorted([n for n, d in in_deg.items() if d == 0])
        dq = deque(zero_nodes)
        while dq:
            u = dq.popleft()
            sorted_deliveries.append(u)
            for v in sorted(forward.get(u, [])):
                in_deg[v] -= 1
                if in_deg[v] == 0:
                    dq.append(v)
        # If not all nodes sorted, would indicate cycle, but we've already checked
        if len(sorted_deliveries) < len(nodes):
            # fallback
            sorted_deliveries = []
    else:
        sorted_deliveries = []

    # Dependency metrics
    in_degree = {n: len(reverse[n]) for n in nodes}
    out_degree = {n: len(forward[n]) for n in nodes}

    # Depth levels BFS from sources
    depth_levels = {n: -1 for n in nodes}
    source_nodes = sorted([n for n in nodes if in_degree[n] == 0])
    dq = deque()
    for s in source_nodes:
        dq.append((s, 0))
        depth_levels[s] = 0
    while dq:
        u, lvl = dq.popleft()
        for v in sorted(forward.get(u, [])):
            if lvl + 1 > depth_levels.get(v, -1):
                depth_levels[v] = lvl + 1
            dq.append((v, lvl + 1))
    for n in nodes:
        if depth_levels[n] == -1:
            depth_levels[n] = 0

    # Independent clusters via undirected components
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
            # bfs
            q = deque([n])
            visited.add(n)
            while q:
                x = q.popleft()
                for y in undirected[x]:
                    if y not in visited:
                        visited.add(y)
                        q.append(y)

    dependency_metrics = {
        "in_degree": dict(sorted(in_degree.items())),
        "out_degree": dict(sorted(out_degree.items())),
        "depth_levels": dict(sorted(depth_levels.items())),
        "independent_clusters": clusters
    }

    # Graph statistics
    total_nodes = len(nodes)
    total_edges = total_edges
    avg_in = round(sum(in_degree.values()) / total_nodes, 4) if total_nodes >= 1 else 0.0
    avg_out = round(sum(out_degree.values()) / total_nodes, 4) if total_nodes >= 1 else 0.0
    max_depth = 0
    if depth_levels:
        max_depth = max(depth_levels.values())
    density = 0.0
    if total_nodes > 1:
        density = round(total_edges / (total_nodes * (total_nodes - 1)), 3)
    else:
        density = 0.0

    # Critical path count: number of nodes with depth == max_depth
    critical_path_count = sum(1 for v in depth_levels.values() if v == max_depth)

    # Degree centralization
    degrees = {n: in_degree[n] + out_degree[n] for n in nodes}
    max_deg = max(degrees.values()) if degrees else 0
    if total_nodes > 1:
        num = sum((max_deg - deg) for deg in degrees.values())
        denom = (total_nodes - 1) * 2 * (total_nodes - 1)
        degree_centralization = round(num / denom if denom != 0 else 0.0, 2)
    else:
        degree_centralization = 0.0

    source_ratio = round(len([1 for v in in_degree.values() if v == 0]) / total_nodes, 5) if total_nodes >= 1 else 0.0
    sink_ratio = round(len([1 for v in out_degree.values() if v == 0]) / total_nodes, 5) if total_nodes >= 1 else 0.0

    # Betweenness centrality (approx exact for small graphs via BFS per node)
    def betweenness():
        bc = dict((n, 0.0) for n in nodes)
        for s in nodes:
            # single-source shortest paths (unweighted)
            S = []
            P = {w: [] for w in nodes}
            sigma = dict((w, 0.0) for w in nodes)
            dist = dict((w, -1) for w in nodes)
            sigma[s] = 1.0
            dist[s] = 0
            q = deque([s])
            while q:
                v = q.popleft()
                S.append(v)
                for w in forward[v]:
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        q.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        P[w].append(v)
            delta = dict((w, 0.0) for w in nodes)
            while S:
                w = S.pop()
                for v in P[w]:
                    if sigma[w] != 0:
                        delta_v = (sigma[v] / sigma[w]) * (1 + delta[w])
                        delta[v] += delta_v
                if w != s:
                    bc[w] += delta[w]
        # normalization: for directed graphs, divide by ((n-1)*(n-2)) if n>2
        if total_nodes > 2:
            scale = 1.0 / ((total_nodes - 1) * (total_nodes - 2))
            for n in nodes:
                bc[n] = bc[n] * scale
        return bc
    bc = betweenness()
    if bc:
        avg_bc = round(sum(bc.values()) / total_nodes, 4)
        max_node = max(bc.items(), key=lambda x: (x[1], x[0]))[0]
        max_score = round(bc[max_node], 4)
    else:
        avg_bc = 0.0
        max_node = ""
        max_score = 0.0

    # PageRank incoming with damping 0.85, 10 iterations
    pr = dict((n, 1.0 / total_nodes) for n in nodes)
    damping = 0.85
    for _ in range(10):
        newpr = dict((n, (1.0 - damping) / total_nodes) for n in nodes)
        for n in nodes:
            if out_degree[n] == 0:
                # distribute to all
                for m in nodes:
                    newpr[m] += damping * pr[n] / total_nodes
            else:
                for m in forward[n]:
                    newpr[m] += damping * pr[n] / out_degree[n]
        pr = newpr
    avg_pr = round(sum(pr.values()) / total_nodes, 6) if total_nodes >= 1 else 0.0
    top_nodes = sorted([(n, pr[n]) for n in nodes], key=lambda x: (-x[1], x[0]))[:3]
    top_nodes = [[n, round(score, 6)] for n, score in top_nodes]

    # Longest path length using DP on topo order (only valid if DAG)
    longest_path_length = 0
    if not has_cycle and sorted_deliveries:
        lp = dict((n, 0) for n in nodes)
        for u in sorted_deliveries:
            for v in forward[u]:
                if lp[u] + 1 > lp[v]:
                    lp[v] = lp[u] + 1
        longest_path_length = max(lp.values()) if lp else 0
    else:
        # estimate via depth_levels
        longest_path_length = max_depth

    # Width metrics
    level_distribution = Counter()
    for n, lv in depth_levels.items():
        level_distribution[str(lv)] += 1
    max_width = max(level_distribution.values()) if level_distribution else 0
    avg_width = round(sum(level_distribution.values()) / len(level_distribution) if level_distribution else 0.0, 2)
    level_dist_sorted = dict(sorted({k: v for k, v in level_distribution.items()}.items(), key=lambda x: int(x[0])))

    # Transitive reduction ratio: count redundant edges (if edge u->v and there's alternative path u->...->v)
    # For each edge, remove and test reachability via BFS
    redundant = 0
    for u in nodes:
        for v in list(forward[u]):
            # BFS from u to v without using direct edge
            q = deque([u])
            seen = set([u])
            found = False
            while q and not found:
                x = q.popleft()
                for y in forward[x]:
                    if x == u and y == v:
                        continue
                    if y == v:
                        found = True
                        break
                    if y not in seen:
                        seen.add(y)
                        q.append(y)
            if found:
                redundant += 1
    transitive_reduction_ratio = round(redundant / total_edges, 4) if total_edges > 0 else 0.0

    # Fan metrics
    fan_in_vals = sorted([in_degree[n] for n in nodes])
    fan_out_vals = sorted([out_degree[n] for n in nodes])
    max_fan_in = fan_in_vals[-1] if fan_in_vals else 0
    max_fan_out = fan_out_vals[-1] if fan_out_vals else 0
    def median(lst):
        l = len(lst)
        if l == 0:
            return 0
        if l % 2 == 1:
            return lst[l//2]
        return (lst[l//2 -1] + lst[l//2]) / 2
    median_fan_in = median(fan_in_vals)
    median_fan_out = median(fan_out_vals)

    # Bottleneck nodes: top 75th percentile by combined degree
    combined = sorted([(n, in_degree[n] + out_degree[n]) for n in nodes], key=lambda x: (-x[1], x[0]))
    if combined:
        vals = [v for _, v in combined]
        threshold_idx = max(0, int(math.ceil(0.75 * len(vals))) - 1)
        threshold = vals[threshold_idx]
        bottlenecks = [n for n, v in combined if v >= threshold]
    else:
        bottlenecks = []
    bottleneck_count = len(bottlenecks)
    bottleneck_nodes = sorted(bottlenecks)[:5]

    # Clustering coefficient undirected average
    def local_clustering(node):
        nbrs = undirected[node]
        k = len(nbrs)
        if k < 2:
            return 0.0
        links = 0
        for a in nbrs:
            for b in nbrs:
                if a != b and b in undirected[a]:
                    links += 1
        # each edge counted twice in directed pair loops
        links = links / 2
        return links / (k * (k - 1) / 2) if k > 1 else 0.0
    clustering_vals = [local_clustering(n) for n in nodes]
    clustering_coefficient = round(sum(clustering_vals) / total_nodes, 4) if total_nodes >= 1 else 0.0

    # Degree variance
    deg_list = [degrees[n] for n in nodes]
    mean_deg = sum(deg_list) / total_nodes if total_nodes >= 1 else 0.0
    variance = sum((d - mean_deg) ** 2 for d in deg_list) / total_nodes if total_nodes >= 1 else 0.0
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
        "betweenness_centrality": {"average": avg_bc, "max_node": max_node, "max_score": max_score},
        "pagerank": {"average": avg_pr, "top_nodes": top_nodes},
        "longest_path_length": longest_path_length,
        "width_metrics": {"max_width": max_width, "average_width": avg_width, "level_distribution": level_dist_sorted},
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
    log_result = "cycle detected" if has_cycle else "reordered successfully"
    for c in new_constraints:
        if isinstance(c, (list, tuple)) and len(c) == 2:
            update_log.append({
                "action": "insert_constraint",
                "constraint": [c[0], c[1]],
                "result": log_result,
                "cycle_detected": has_cycle
            })

    result = {
        "success": True,
        "sorted_deliveries": sorted_deliveries,
        "has_cycle": has_cycle,
        "cycle_nodes": sorted(cycle_nodes),
        "dependency_metrics": dependency_metrics,
        "graph_statistics": graph_statistics,
        "update_log": update_log,
        "errors": []
    }

    return result