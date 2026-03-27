def optimize_network_mst(
    nodes: List[str],
    edges: List[Dict[str, Any]],
    bandwidth_threshold: int,
    latency_threshold: int,
    reliability_threshold: float
) -> List[Dict[str, str]]:
    EPS = 1e-9
    if not nodes or len(nodes) <= 1:
        return []
    node_index = {name: i for i, name in enumerate(nodes)}
    n = len(nodes)
    # Validate and filter edges
    best_edge_per_pair = {}  # key: (u_idx,v_idx) with u<v -> (cost, original start, end)
    for e in edges:
        try:
            a = e.get('start')
            b = e.get('end')
            if a is None or b is None:
                continue
            if a == b:
                continue
            if a not in node_index or b not in node_index:
                continue
            cost = float(e.get('cost', 0))
            bw = float(e.get('bandwidth', 0))
            lat = float(e.get('latency', 0))
            rel = float(e.get('reliability', 0.0))
        except Exception:
            continue
        # Validation rules
        if bw <= 0:
            continue
        if lat < 0 or lat >= 1e9:
            continue
        if bw < bandwidth_threshold:
            continue
        if lat > latency_threshold:
            continue
        if rel + EPS < reliability_threshold:
            continue
        u = node_index[a]
        v = node_index[b]
        if u > v:
            u, v = v, u
            a, b = b, a  # normalize direction for deterministic output later
        key = (u, v)
        # Tie-breaker: choose lower cost; if equal cost, deterministic by (start,end) lexicographic
        prev = best_edge_per_pair.get(key)
        if prev is None:
            best_edge_per_pair[key] = (cost, a, b)
        else:
            prev_cost, prev_a, prev_b = prev
            if cost < prev_cost - 1e-12:
                best_edge_per_pair[key] = (cost, a, b)
            elif abs(cost - prev_cost) <= 1e-12:
                if (a, b) < (prev_a, prev_b):
                    best_edge_per_pair[key] = (cost, a, b)
    if not best_edge_per_pair:
        return []
    # Build edge list for Kruskal: (cost, u, v, start_name, end_name)
    edge_list = []
    for (u, v), (cost, a, b) in best_edge_per_pair.items():
        edge_list.append((cost, u, v, a, b))
    # Sort by cost, tie-breaker deterministic by node names
    edge_list.sort(key=lambda x: (x[0], x[3], x[4]))
    # Union-Find
    parent = list(range(n))
    rank = [0]*n
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        rx = find(x); ry = find(y)
        if rx == ry:
            return False
        if rank[rx] < rank[ry]:
            parent[rx] = ry
        else:
            parent[ry] = rx
            if rank[rx] == rank[ry]:
                rank[rx] += 1
        return True
    mst = []
    for cost, u, v, a, b in edge_list:
        if union(u, v):
            mst.append({'start': a, 'end': b})
            if len(mst) == n - 1:
                break
    if len(mst) != n - 1:
        return []
    return mst