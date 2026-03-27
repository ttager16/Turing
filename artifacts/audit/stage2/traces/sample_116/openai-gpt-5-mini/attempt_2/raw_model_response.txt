def optimize_multicommodity_flow(
    graph: dict[str, dict[str, list[int]]],
    demands: dict[str, dict[str, list[int]]],
    source: str,
    sinks: list[str],
    commodities: list[str]
) -> dict[str, dict[str, int]] | dict[str, str]:
    # Validation
    if not isinstance(graph, dict) or not isinstance(demands, dict) or not isinstance(source, str) \
       or not isinstance(sinks, list) or not isinstance(commodities, list):
        return {'error': 'Invalid input type'}
    if not graph or not demands or not sinks or not commodities:
        return {'error': 'Empty input data'}
    # parse edges and build adjacency per commodity
    adj = {}  # node -> list of (neighbor, commodity, capacity, cost)
    nodes = set([source])
    for ekey, cmap in graph.items():
        if not isinstance(ekey, str) or ekey.count(',') != 1:
            return {'error': 'Invalid edge format'}
        u, v = ekey.split(',', 1)
        if u == v:
            return {'error': 'Constraint violation'}
        nodes.add(u); nodes.add(v)
        if not isinstance(cmap, dict):
            return {'error': 'Invalid input type'}
        for com, vals in cmap.items():
            if not isinstance(com, str) or not isinstance(vals, list) or len(vals) != 2:
                return {'error': 'Invalid input type'}
            cap, cost = vals
            if not (isinstance(cap, int) and isinstance(cost, int)):
                return {'error': 'Invalid input type'}
            if cap < 1 or cost < 1:
                return {'error': 'Constraint violation'}
            adj.setdefault(u, []).append((v, com, cap, cost))
    # validate demands structure
    for sink, cmap in demands.items():
        if not isinstance(sink, str) or not isinstance(cmap, dict):
            return {'error': 'Invalid input type'}
        for com, vals in cmap.items():
            if com not in commodities:
                # allow extra but ignore later; still validate format
                pass
            if not isinstance(vals, list) or len(vals) != 2:
                return {'error': 'Invalid input type'}
            mn, mx = vals
            if not (isinstance(mn, int) and isinstance(mx, int)):
                return {'error': 'Invalid input type'}
            if mn < 0 or mn > mx:
                return {'error': 'Constraint violation'}
    # For each commodity and each sink, try to find the minimum-cost max-flow from source to sink
    # Since standard libraries only: implement successive shortest augmenting path with capacities per edge per commodity independent.
    # For unreachable sinks for a commodity, deliver min demand.
    result = {}
    # Build per-commodity graph capacities and costs; edges are independent per commodity as given.
    # For each commodity and each sink compute max-flow up to demand max, minimizing cost.
    from collections import deque
    for sink in sinks:
        result[sink] = {}
        for com in commodities:
            # demand bounds
            mn = demands.get(sink, {}).get(com, [0, 0])[0]
            mx = demands.get(sink, {}).get(com, [0, 0])[1]
            if mn is None or mx is None:
                mn = 0; mx = 0
            # Build residual graph nodes: adjacency with capacities and costs
            # Represent edges as dict: u -> list of edges each as [v, cap, cost, rev_index]
            G = {}
            def add_edge(u, v, cap, cost):
                G.setdefault(u, []).append([v, cap, cost, len(G.get(v, []))])
                G.setdefault(v, []).append([u, 0, -cost, len(G[u]) - 1])
            for u, lst in adj.items():
                for (v, cc, cost) in [(t[0], t[2], t[3]) for t in lst if t[1] == com]:
                    add_edge(u, v, cc, cost)
            # If no path edges for commodity, return mn
            if source not in G:
                result[sink][com] = mn
                continue
            if sink not in G:
                # sink may be isolated; check reachability via BFS ignoring capacities
                # quick check: if sink not in nodes or no incoming edges for commodity, treat unreachable
                reachable = False
                # check if any u->sink exists in G keys
                for u in G:
                    for e in G.get(u, []):
                        if e[0] == sink and (e[1] > 0 or e[2] <= 0):
                            reachable = True; break
                    if reachable: break
                if not reachable:
                    result[sink][com] = mn
                    continue
            flow = 0
            cost = 0
            max_needed = mx
            # Successive shortest augmenting path with SPFA for potentials
            while flow < max_needed:
                # Bellman-Ford/SPFA for shortest path from source to sink in residual graph
                dist = {node: float('inf') for node in G}
                inq = {node: False for node in G}
                prev = {}
                dist[source] = 0
                q = deque([source]); inq[source] = True
                while q:
                    u = q.popleft(); inq[u] = False
                    for i, e in enumerate(G[u]):
                        v, cap, ecost, rev = e
                        if cap > 0 and dist[v] > dist[u] + ecost:
                            dist[v] = dist[u] + ecost
                            prev[v] = (u, i)
                            if not inq[v]:
                                inq[v] = True
                                q.append(v)
                if sink not in dist or dist[sink] == float('inf'):
                    break
                # find bottleneck
                increment = max_needed - flow
                v = sink
                while v != source:
                    u, i = prev[v]
                    increment = min(increment, G[u][i][1])
                    v = u
                # apply
                v = sink
                while v != source:
                    u, i = prev[v]
                    e = G[u][i]
                    e[1] -= increment
                    rev = e[3]
                    G[v][rev][1] += increment
                    v = u
                flow += increment
                cost += increment * dist[sink]
            if flow == 0:
                # unreachable
                result[sink][com] = mn
            else:
                # ensure at least mn; if flow < mn then fallback to mn per spec? Spec: maximize within demand range; if no path assign min as fallback.
                if flow < mn:
                    result[sink][com] = mn
                else:
                    result[sink][com] = flow
    return result