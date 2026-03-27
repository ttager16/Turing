def optimize_multicommodity_flow(
    graph: dict[str, dict[str, list[int]]],
    demands: dict[str, dict[str, list[int]]],
    source: str,
    sinks: list[str],
    commodities: list[str]
) -> dict[str, dict[str, int]] | dict[str, str]:
    # Validation types
    if not isinstance(graph, dict) or not isinstance(demands, dict) or not isinstance(source, str) or not isinstance(sinks, list) or not isinstance(commodities, list):
        return {'error': 'Invalid input type'}
    if not graph or not demands or not sinks or not commodities:
        return {'error': 'Empty input data'}
    # Validate edges and build adjacency per commodity
    adj_by_comm = {c: {} for c in commodities}
    nodes = set()
    for edge_key, val in graph.items():
        if not isinstance(edge_key, str) or edge_key.count(",") != 1:
            return {'error': 'Invalid edge format'}
        u, v = edge_key.split(",", 1)
        if u == v:
            return {'error': 'Constraint violation'}
        nodes.add(u); nodes.add(v)
        if not isinstance(val, dict):
            return {'error': 'Invalid input type'}
        for c, pair in val.items():
            if not isinstance(c, str) or not isinstance(pair, list) or len(pair) != 2:
                return {'error': 'Invalid input type'}
            cap, cost = pair
            if not (isinstance(cap, int) and isinstance(cost, int)):
                return {'error': 'Invalid input type'}
            if cap < 1 or cost < 1:
                return {'error': 'Constraint violation'}
            if c in commodities:
                adj_by_comm[c].setdefault(u, []).append((v, cap, cost))
    # Validate demands structure and ranges
    for sink, dmap in demands.items():
        if not isinstance(sink, str) or not isinstance(dmap, dict):
            return {'error': 'Invalid input type'}
        for c, pair in dmap.items():
            if not isinstance(c, str) or not isinstance(pair, list) or len(pair) != 2:
                return {'error': 'Invalid input type'}
            mn, mx = pair
            if not (isinstance(mn, int) and isinstance(mx, int)):
                return {'error': 'Invalid input type'}
            if mn < 0 or mn > mx:
                return {'error': 'Constraint violation'}
    # Helper: find all simple paths from source to sink up to reasonable limit using DFS
    def find_paths(adj, s, t, limit=1000, max_len=20):
        paths = []
        stack = [(s, [s])]
        visited_sets = set()
        while stack and len(paths) < limit:
            node, path = stack.pop()
            if len(path) > max_len:
                continue
            if node == t:
                paths.append(path)
                continue
            for nei, _, _ in adj.get(node, []):
                if nei not in path:  # simple path
                    stack.append((nei, path + [nei]))
        return paths
    # For each commodity and sink, compute max deliverable within capacities with min cost among max delivery.
    # We'll treat edges independently per commodity (no coupling across commodities).
    result = {}
    for sink in sinks:
        result[sink] = {}
        for c in commodities:
            # default fallback min demand if sink not in demands or commodity not specified
            mn = 0
            mx = 0
            if sink in demands and c in demands[sink]:
                mn, mx = demands[sink][c]
            else:
                # If not specified, treat as 0..0
                mn, mx = 0, 0
            # Build adjacency for commodity c
            adj = adj_by_comm.get(c, {})
            # If source or sink not in nodes of this commodity graph, unreachable
            if source not in adj and all(source != u for u in adj):
                # still maybe source has no outgoing edges for this commodity
                # check reachability via edges
                pass
            # Find simple paths
            paths = find_paths(adj, source, sink, limit=200, max_len=20)
            if not paths:
                # unreachable, assign min demand
                result[sink][c] = mn
                continue
            # For each path, compute bottleneck capacity and path cost per unit
            path_infos = []
            for p in paths:
                # derive sequence of edges u->v
                bottleneck = float('inf')
                total_cost = 0
                valid = True
                for i in range(len(p)-1):
                    u = p[i]; v = p[i+1]
                    # find edge entry in adj[u] for v
                    found = False
                    for nei, cap, cost in adj.get(u, []):
                        if nei == v:
                            found = True
                            bottleneck = min(bottleneck, cap)
                            total_cost += cost
                            break
                    if not found:
                        valid = False
                        break
                if valid and bottleneck > 0:
                    path_infos.append({'path': p, 'cap': bottleneck, 'cost': total_cost})
            if not path_infos:
                result[sink][c] = mn
                continue
            # We want to push flow along multiple edge-disjoint? edges share capacities; need simple greedy augmentation:
            # We'll treat edges capacities and allow multiple paths to share edges reducing caps.
            # Greedy: repeatedly pick path with lowest cost per unit and push as much as possible up to remaining demand and path bottleneck.
            # Initialize residual capacities dict per edge (u,v)
            residual = {}
            for edge_key, val in graph.items():
                u,v = edge_key.split(",",1)
                if c in val:
                    residual[(u,v)] = val[c][0]
            delivered = 0
            assign = {}
            # sort path_infos by cost ascending
            path_infos.sort(key=lambda x: x['cost'])
            # attempt to reach up to mx, but at least mn if possible
            target = mx
            for info in path_infos:
                if delivered >= target:
                    break
                p = info['path']
                # compute current path bottleneck from residual
                cur_bottleneck = float('inf')
                for i in range(len(p)-1):
                    e = (p[i], p[i+1])
                    cap = residual.get(e, 0)
                    cur_bottleneck = min(cur_bottleneck, cap)
                if cur_bottleneck <= 0:
                    continue
                take = min(cur_bottleneck, target - delivered)
                # apply
                for i in range(len(p)-1):
                    e = (p[i], p[i+1])
                    residual[e] = residual.get(e, 0) - take
                delivered += take
                assign[tuple(p)] = assign.get(tuple(p), 0) + take
            # After greedy, if delivered < mn but there exists any path (we already had), we might try to push more even if cost higher:
            if delivered < mn:
                # try any remaining capacity regardless of cost to reach mn
                for info in sorted(path_infos, key=lambda x: x['cost']):
                    if delivered >= mn:
                        break
                    p = info['path']
                    cur_bottleneck = float('inf')
                    for i in range(len(p)-1):
                        e = (p[i], p[i+1])
                        cap = residual.get(e, 0)
                        cur_bottleneck = min(cur_bottleneck, cap)
                    if cur_bottleneck <= 0:
                        continue
                    take = min(cur_bottleneck, mn - delivered)
                    for i in range(len(p)-1):
                        e = (p[i], p[i+1])
                        residual[e] = residual.get(e, 0) - take
                    delivered += take
                    assign[tuple(p)] = assign.get(tuple(p), 0) + take
            # If still < mn, fallback to mn per spec (assign min)
            if delivered < mn:
                result[sink][c] = mn
            else:
                # delivered is between mn and mx
                result[sink][c] = delivered
    return result