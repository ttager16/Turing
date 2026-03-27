def optimize_multicommodity_flow(
    graph: dict[str, dict[str, list[int]]],
    demands: dict[str, dict[str, list[int]]],
    source: str,
    sinks: list[str],
    commodities: list[str]
) -> dict[str, dict[str, int]] | dict[str, str]:
    if not isinstance(graph, dict) or not isinstance(demands, dict) or not isinstance(source, str) or not isinstance(sinks, list) or not isinstance(commodities, list):
        return {'error': 'Invalid input type'}
    for s in sinks:
        if not isinstance(s, str) or isinstance(s, bool):
            return {'error': 'Invalid input type'}
    for c in commodities:
        if not isinstance(c, str) or isinstance(c, bool):
            return {'error': 'Invalid input type'}
    if not graph or not demands or not sinks or not commodities:
        return {'error': 'Empty input data'}
    nodes = set([source])
    for edge_key, edge_data in graph.items():
        if not isinstance(edge_key, str):
            return {'error': 'Invalid input type'}
        parts = edge_key.split(',')
        if len(parts) != 2:
            return {'error': 'Invalid edge format'}
        u, v = parts
        if u == v:
            return {'error': 'Constraint violation'}
        nodes.add(u); nodes.add(v)
        if not isinstance(edge_data, dict):
            return {'error': 'Invalid input type'}
        for comm, vals in edge_data.items():
            if not isinstance(vals, list) or len(vals) != 2:
                return {'error': 'Invalid input type'}
            cap, cost = vals
            if isinstance(cap, bool) or isinstance(cost, bool):
                return {'error': 'Invalid input type'}
            if not isinstance(cap, int) or not isinstance(cost, int):
                return {'error': 'Invalid input type'}
            if cap < 1 or cost < 1:
                return {'error': 'Constraint violation'}
    if len(nodes) < 2:
        return {'error': 'Constraint violation'}
    for sink, sink_demands in demands.items():
        if not isinstance(sink, str) or not isinstance(sink_demands, dict):
            return {'error': 'Invalid input type'}
        for comm, dr in sink_demands.items():
            if not isinstance(dr, list) or len(dr) != 2:
                return {'error': 'Invalid input type'}
            mn, mx = dr
            if isinstance(mn, bool) or isinstance(mx, bool):
                return {'error': 'Invalid input type'}
            if not isinstance(mn, int) or not isinstance(mx, int):
                return {'error': 'Invalid input type'}
            if mn < 0 or mn > mx:
                return {'error': 'Constraint violation'}
    
    def build_graph_for_commodity(commodity):
        G = {}
        def add_edge(a, b, cap, cost):
            if a not in G: G[a] = []
            if b not in G: G[b] = []
            G[a].append([b, cap, cost, len(G[b])])
            G[b].append([a, 0, -cost, len(G[a]) - 1])
        for edge_key, edge_data in graph.items():
            if commodity in edge_data:
                u, v = edge_key.split(',')
                cap, cost = edge_data[commodity]
                add_edge(u, v, cap, cost)
        return G
    
    from collections import deque
    
    def max_flow_only(G, s, t):
        if s not in G or t not in G:
            return 0
        total_flow = 0
        flow_graph = {}
        for node in G:
            flow_graph[node] = []
            for edge in G[node]:
                flow_graph[node].append(list(edge))
        while True:
            parent = {s: None}
            parent_edge = {}
            q = deque([s])
            while q and t not in parent:
                u = q.popleft()
                for ei, edge in enumerate(flow_graph[u]):
                    v, cap, cost, rev = edge
                    if cap > 0 and v not in parent:
                        parent[v] = u
                        parent_edge[v] = ei
                        q.append(v)
            if t not in parent:
                break
            path_flow = float('inf')
            v = t
            while v != s:
                u = parent[v]
                ei = parent_edge[v]
                path_flow = min(path_flow, flow_graph[u][ei][1])
                v = u
            v = t
            while v != s:
                u = parent[v]
                ei = parent_edge[v]
                rev = flow_graph[u][ei][3]
                flow_graph[u][ei][1] -= path_flow
                flow_graph[v][rev][1] += path_flow
                v = u
            total_flow += path_flow
        return total_flow
    
    def min_cost_flow_with_target(G, s, t, target_flow):
        if s not in G or t not in G:
            return 0, 0
        flow = 0
        cost = 0
        while flow < target_flow:
            dist = {node: float('inf') for node in G}
            inq = {node: False for node in G}
            parent = {node: None for node in G}
            parent_edge = {}
            dist[s] = 0
            q = deque([s])
            inq[s] = True
            while q:
                u = q.popleft()
                inq[u] = False
                for ei, e in enumerate(G[u]):
                    v, cap, cst, rev = e
                    if cap > 0 and dist[v] > dist[u] + cst:
                        dist[v] = dist[u] + cst
                        parent[v] = u
                        parent_edge[v] = ei
                        if not inq[v]:
                            q.append(v)
                            inq[v] = True
            if parent[t] is None:
                break
            addf = target_flow - flow
            v = t
            while v != s:
                u = parent[v]
                ei = parent_edge[v]
                addf = min(addf, G[u][ei][1])
                v = u
            v = t
            while v != s:
                u = parent[v]
                ei = parent_edge[v]
                rev = G[u][ei][3]
                G[u][ei][1] -= addf
                G[v][rev][1] += addf
                cost += G[u][ei][2] * addf
                v = u
            flow += addf
        return flow, cost
    
    result = {}
    for sink in sinks:
        if sink not in demands:
            continue
        result[sink] = {}
        for commodity in commodities:
            if commodity not in demands[sink]:
                continue
            mn, mx = demands[sink][commodity]
            G = build_graph_for_commodity(commodity)
            max_flow = max_flow_only(G, source, sink)
            if max_flow == 0 or max_flow < mn:
                result[sink][commodity] = mn
                continue
            if max_flow > mx:
                target_flow = mx
            else:
                target_flow = max_flow
            G = build_graph_for_commodity(commodity)
            flow, _ = min_cost_flow_with_target(G, source, sink, target_flow)
            result[sink][commodity] = flow
    return result