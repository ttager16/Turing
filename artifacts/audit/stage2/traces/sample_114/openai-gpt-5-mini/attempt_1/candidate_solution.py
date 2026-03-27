def optimize_logistics_network(graph_input: dict) -> dict:
    # Input validation
    if not isinstance(graph_input, dict) or 'graph' not in graph_input:
        return {"error": "Invalid input format"}
    graph_raw = graph_input.get('graph')
    if not isinstance(graph_raw, dict):
        return {"error": "Graph data must be a dictionary"}
    for k, v in graph_raw.items():
        if not isinstance(k, str) or not isinstance(v, list):
            return {"error": "Graph data must map string node IDs to lists of edges"}
        for e in v:
            if not (isinstance(e, list) and len(e) == 3):
                return {"error": "Graph data must map string node IDs to lists of edges"}
    source = graph_input.get('source', 0)
    sink = graph_input.get('sink', None)
    analyze_all_paths = graph_input.get('analyze_all_paths', False)
    if not isinstance(analyze_all_paths, bool):
        return {"error": "analyze_all_paths must be a boolean"}
    # Convert node ids to ints
    nodes_set = set()
    edges = []
    for k, v in graph_raw.items():
        try:
            ni = int(k)
        except:
            return {"error": "Graph data must map string node IDs to lists of edges"}
        nodes_set.add(ni)
        for nb, cap, cost in v:
            try:
                nb_i = int(nb)
            except:
                return {"error": "Graph data must map string node IDs to lists of edges"}
            nodes_set.add(nb_i)
            edges.append((ni, nb_i, int(cap), int(cost)))
    if sink is None:
        sink = max(nodes_set) if nodes_set else 0
    try:
        source = int(source)
        sink = int(sink)
    except:
        return {"error": "Source node not found in graph"}
    if source not in nodes_set:
        return {"error": "Source node not found in graph"}
    if sink not in nodes_set:
        return {"error": "Sink node not found in graph"}
    nodes = sorted(nodes_set)
    node_count = len(nodes)
    # Build adjacency original graph map for cost lookup and capacities
    orig_adj = defaultdict(list)
    total_edges = 0
    for u, v, c, w in edges:
        orig_adj[u].append((v, c, w))
        total_edges += 1
    # Layer assignment using BFS-based topological ordering with in-degree
    indeg = defaultdict(int)
    for u in nodes:
        indeg[u] = 0
    for u in orig_adj:
        for v, c, w in orig_adj[u]:
            indeg[v] += 1
    zero_indeg = [n for n in nodes if indeg.get(n, 0) == 0]
    if not zero_indeg:
        start_nodes = [min(nodes)]
    else:
        start_nodes = sorted(zero_indeg)
    layers_map = {}
    layer_of = {n: -1 for n in nodes}
    q = deque()
    for s in start_nodes:
        q.append((s, 0))
        layer_of[s] = 0
    iterations = 0
    max_iters = node_count * node_count if node_count > 0 else 1
    while q and iterations < max_iters:
        iterations += 1
        u, l = q.popleft()
        # safeguard
        if l > node_count * 2:
            continue
        if layer_of.get(u, -1) < l:
            layer_of[u] = l
        for v, c, w in orig_adj.get(u, []):
            new_layer = l + 1
            if new_layer - layer_of.get(v, -1) > node_count:
                continue
            if new_layer > layer_of.get(v, -1):
                layer_of[v] = new_layer
                if new_layer < node_count * 2:
                    q.append((v, new_layer))
    # Place unreachable nodes one beyond current max
    current_max_layer = max([lv for lv in layer_of.values() if lv >= 0], default=-1)
    for n in nodes:
        if layer_of[n] == -1:
            layer_of[n] = current_max_layer + 1
    # Build layers dict
    layers = defaultdict(list)
    for n, l in layer_of.items():
        layers[l].append(n)
    layers_out = {}
    for l in sorted(layers.keys()):
        layers_out[str(l)] = sorted(layers[l])
    num_layers = len(layers_out)
    # Build residual graph: nested dict {u: {v: [cap, cost]}}
    residual = defaultdict(dict)
    for u, v, c, w in edges:
        if c > 0:
            residual[u][v] = [c, w]
    # DFS to find augmenting path returning path and bottleneck
    def dfs_find_path(u, t, visited):
        if u == t:
            return [t], float('inf')
        visited.add(u)
        for v, (cap, cost) in list(residual.get(u, {}).items()):
            if cap <= 0 or v in visited:
                continue
            res = dfs_find_path(v, t, visited)
            if res is not None:
                path, bottleneck = res
                bottleneck = min(bottleneck, cap)
                return [u] + path, bottleneck
        visited.remove(u)
        return None
    # Exhaustively collect all augmenting paths in each FF iteration
    max_throughput = 0
    augmenting_paths_taken = []  # list of (path, flow, cost)
    # We'll iterate until no augmenting path exists
    while True:
        # Collect all possible distinct augmenting paths via repeated DFS while not modifying residual
        found = []
        visited_set = set()
        # We'll perform multiple DFS searches marking visited differently to find different paths.
        # A simple approach: repeatedly find one path using dfs_find_path, then simulate reducing its capacity in a temp residual copy to find more in same iteration.
        temp_res = {u: dict((v, [cap, cost]) for v, (cap, cost) in residual[u].items()) for u in residual}
        def dfs_temp(u, t, visited):
            if u == t:
                return [t], float('inf')
            visited.add(u)
            for v, (cap, cost) in list(temp_res.get(u, {}).items()):
                if cap <= 0 or v in visited:
                    continue
                res = dfs_temp(v, t, visited)
                if res is not None:
                    path, bottleneck = res
                    bottleneck = min(bottleneck, cap)
                    return [u] + path, bottleneck
            visited.remove(u)
            return None
        while True:
            res = dfs_temp(source, sink, set())
            if not res:
                break
            path, bottleneck = res
            # compute path cost from original graph
            cost_sum = 0
            for i in range(len(path)-1):
                u = path[i]; v = path[i+1]
                # find cost in original
                found_cost = None
                for vv, cc, ww in orig_adj.get(u, []):
                    if vv == v:
                        found_cost = ww
                        break
                cost_sum += found_cost if found_cost is not None else 0
            found.append((path, bottleneck, cost_sum))
            # reduce temp_res along path
            for i in range(len(path)-1):
                u = path[i]; v = path[i+1]
                temp_res[u][v][0] -= bottleneck
                if temp_res[u][v][0] <= 0:
                    del temp_res[u][v]
                # add reverse
                if v not in temp_res:
                    temp_res[v] = {}
                if u in temp_res[v]:
                    temp_res[v][u][0] += bottleneck
                else:
                    # find original cost for reverse as negated cost per requirements
                    rev_cost = 0
                    for vv, cc, ww in orig_adj.get(u, []):
                        if vv == v:
                            rev_cost = -ww
                            break
                    temp_res[v][u] = [bottleneck, rev_cost]
        if not found:
            break
        # choose best path: sort by flow desc then cost asc
        found.sort(key=lambda x: (-x[1], x[2]))
        chosen = found[0]
        path_chosen, flow_chosen, cost_chosen = chosen
        # Apply to real residual
        for i in range(len(path_chosen)-1):
            u = path_chosen[i]; v = path_chosen[i+1]
            # reduce forward
            if u in residual and v in residual[u]:
                residual[u][v][0] -= flow_chosen
                if residual[u][v][0] <= 0:
                    del residual[u][v]
            # add reverse
            if v not in residual:
                residual[v] = {}
            if u in residual[v]:
                residual[v][u][0] += flow_chosen
            else:
                # find original forward cost to negate
                rev_cost = 0
                for vv, cc, ww in orig_adj.get(u, []):
                    if vv == v:
                        rev_cost = -ww
                        break
                residual[v][u] = [flow_chosen, rev_cost]
        max_throughput += flow_chosen
        augmenting_paths_taken.append((path_chosen, flow_chosen, cost_chosen))
    # Determine optimal_path per requirement: augmenting path with largest flow; ties lowest cost
    if not augmenting_paths_taken:
        optimal_path = []
        optimal_flow = 0
        total_cost = 0
    else:
        best = sorted(augmenting_paths_taken, key=lambda x: (-x[1], x[2]))[0]
        optimal_path, optimal_flow, total_cost = best[0], best[1], best[2]
    # total_cost must be sum of edge costs along optimal_path using original graph costs
    if optimal_path:
        total_cost = 0
        for i in range(len(optimal_path)-1):
            u = optimal_path[i]; v = optimal_path[i+1]
            found_cost = 0
            for vv, cc, ww in orig_adj.get(u, []):
                if vv == v:
                    found_cost = ww
                    break
            total_cost += found_cost
    # Bottleneck nodes: source nodes of edges matching minimum edge capacity on optimal_path
    bottleneck_nodes = []
    if optimal_path and len(optimal_path) >= 2:
        capacities = []
        for i in range(len(optimal_path)-1):
            u = optimal_path[i]; v = optimal_path[i+1]
            capv = None
            for vv, cc, ww in orig_adj.get(u, []):
                if vv == v:
                    capv = cc
                    break
            if capv is None:
                capv = 0
            capacities.append((u, capv))
        min_cap = min([c for _, c in capacities]) if capacities else 0
        bottleneck_nodes = [u for u, c in capacities if c == min_cap]
    else:
        capacities = []
        min_cap = 0
    # Metrics calculations
    # capacity_utilization_percent: optimal_path flow * edge count / total path capacity as percentage
    if not optimal_path or len(optimal_path) < 2 or sum(c for _, c in capacities) == 0:
        capacity_utilization_percent = 0.0
    else:
        edge_count = len(optimal_path)-1
        total_path_capacity = sum(c for _, c in capacities)
        if total_path_capacity == 0:
            capacity_utilization_percent = 0.0
        else:
            capacity_utilization_percent = round((optimal_flow * edge_count / total_path_capacity) * 100, 2)
    # cost_efficiency_ratio: max_throughput / total_cost
    if total_cost == 0 or source == sink:
        cost_efficiency_ratio = None
    else:
        cost_efficiency_ratio = round(max_throughput / total_cost, 4)
    # path_length
    if not optimal_path or len(optimal_path) < 2:
        path_length = 0
    else:
        path_length = len(optimal_path)-1
    # avg_edge_capacity
    if not capacities:
        avg_edge_capacity = 0.0
    else:
        avg_edge_capacity = round(sum(c for _, c in capacities)/len(capacities), 2)
    # flow_efficiency_percent: optimal path flow as percentage of theoretical maximum (minimum edge capacity on that path)
    if not capacities or min_cap == 0:
        flow_efficiency_percent = 0.0
    else:
        flow_efficiency_percent = round((optimal_flow / min_cap) * 100, 2) if min_cap > 0 else 0.0
    # network_density: total graph edges / total nodes
    if node_count == 0:
        network_density = 0.0
    else:
        network_density = round(total_edges / node_count, 2)
    # cost_per_hop
    if path_length == 0:
        cost_per_hop = 0.0
    else:
        cost_per_hop = round(total_cost / path_length, 2)
    # bottleneck_severity_percent: how much min capacity restricts flow relative to average capacity as percentage
    if not capacities or avg_edge_capacity == 0:
        bottleneck_severity_percent = 0.0
    else:
        bottleneck_severity_percent = round(((avg_edge_capacity - min_cap) / avg_edge_capacity) * 100, 2) if avg_edge_capacity != 0 else 0.0
    # path_resilience_score: total feasible paths found via exhaustive search when analyze_all_paths enabled; else 0
    path_resilience_score = 0
    alternative_paths = []
    if analyze_all_paths:
        # exhaustive DFS with backtracking counting feasible paths and collecting up to many paths
        all_paths = []
        def dfs_all(u, t, visited, path, bottleneck, cost):
            if u == t:
                all_paths.append((list(path), bottleneck if bottleneck != float('inf') else 0, cost))
                return
            for v, c, w in orig_adj.get(u, []):
                if v in visited or c <= 0:
                    continue
                visited.add(v)
                path.append(v)
                new_b = min(bottleneck, c)
                dfs_all(v, t, visited, path, new_b, cost + w)
                path.pop()
                visited.remove(v)
        visited = set([source])
        dfs_all(source, sink, visited, [source], float('inf'), 0)
        path_resilience_score = len(all_paths)
        # sort by cost ascending and limit 5, include capacities
        all_paths.sort(key=lambda x: (x[2], -x[1]))
        for p, cap, cst in all_paths[:5]:
            alternative_paths.append({'path': p, 'capacity': cap, 'cost': cst})
    # layer_distribution: min, max, avg nodes per layer
    if num_layers == 0:
        layer_distribution = {'min_nodes_per_layer': 0, 'max_nodes_per_layer': 0, 'avg_nodes_per_layer': 0.0}
    else:
        counts = [len(layers_out[k]) for k in layers_out]
        mn = min(counts) if counts else 0
        mx = max(counts) if counts else 0
        avg = round(sum(counts)/len(counts), 2) if counts else 0.0
        layer_distribution = {'min_nodes_per_layer': mn, 'max_nodes_per_layer': mx, 'avg_nodes_per_layer': avg}
    metrics = {
        'capacity_utilization_percent': capacity_utilization_percent,
        'cost_efficiency_ratio': cost_efficiency_ratio,
        'path_length': path_length,
        'avg_edge_capacity': avg_edge_capacity,
        'flow_efficiency_percent': flow_efficiency_percent,
        'network_density': network_density,
        'cost_per_hop': cost_per_hop,
        'bottleneck_severity_percent': bottleneck_severity_percent,
        'path_resilience_score': path_resilience_score,
        'layer_distribution': layer_distribution
    }
    result = {
        'optimal_path': optimal_path,
        'max_throughput': max_throughput,
        'total_cost': total_cost,
        'layers': layers_out,
        'num_layers': num_layers,
        'bottleneck_nodes': bottleneck_nodes,
        'metrics': metrics
    }
    if analyze_all_paths:
        result['alternative_paths'] = alternative_paths
    return result