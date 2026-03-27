def find_optimal_multilayer_network(
    layer_graphs: List[Dict[str, Any]],
    critical_nodes: Dict[str, float]
) -> List[Dict[str, int]]:
    # Build aggregated nodes balances and edges with layer info
    node_balance = defaultdict(float)
    edges = []  # list of (layer_id, u, v, base_cost, capacity)
    node_layers = defaultdict(set)
    for layer in layer_graphs:
        lid = layer.get("layer_id")
        nodes = layer.get("nodes", {})
        for n, b in nodes.items():
            node_balance[n] += float(b)
            node_layers[n].add(lid)
        for e in layer.get("edges", []):
            u = e["from"]; v = e["to"]
            cost = float(e["cost"])
            cap = float(e["capacity"])
            edges.append((lid, u, v, cost, cap))
            node_layers[u].add(lid); node_layers[v].add(lid)
    # Check global supply==demand
    total_supply = sum(v for v in node_balance.values() if v > 0)
    total_demand = -sum(v for v in node_balance.values() if v < 0)
    if abs(total_supply - total_demand) > 1e-9:
        return []
    # Build adjusted costs
    def priority_weight(node):
        w = critical_nodes.get(str(node), critical_nodes.get(node, None))
        if w is None:
            return 1.0
        try:
            w = float(w)
        except:
            w = 1.0
        return max(0.1, w)
    adj_edges = []  # store with id
    for idx, (lid, u, v, base_cost, cap) in enumerate(edges):
        pu = priority_weight(u); pv = priority_weight(v)
        factor = 1.0 / (pu * pv) if (pu * pv) != 0 else 1.0
        adj_cost = base_cost * factor
        adj_edges.append({
            "id": idx, "layer_id": lid, "u": u, "v": v,
            "cost": adj_cost, "cap": cap, "base_cost": base_cost
        })
    # Build flow network with super source/sink: create directed edges as given (no reverse direction unless present)
    # We'll implement min-cost flow via successive shortest augmenting paths (Dijkstra potentials)
    # Nodes: all unique node ids plus 'S' and 'T'
    nodes = set(node_balance.keys())
    S = "__src__"; T = "__sink__"
    # Assign demands: supply nodes -> edge from S to node with capacity = supply, cost 0
    # demand nodes -> edge from node to T with capacity = -demand, cost 0
    # Also include original edges u->v with capacity and cost
    # Build adjacency with residual edges
    class Edge:
        __slots__ = ("to","rev","cap","cost","orig_id","layer_id","u","v")
        def __init__(self, to, rev, cap, cost, orig_id=None, layer_id=None, u=None, v=None):
            self.to = to; self.rev = rev; self.cap = cap; self.cost = cost
            self.orig_id = orig_id; self.layer_id = layer_id; self.u = u; self.v = v
    graph = defaultdict(list)
    def add_edge(frm, to, cap, cost, orig_id=None, layer_id=None, u=None, v=None):
        graph[frm].append(Edge(to, len(graph[to]), cap, cost, orig_id, layer_id, u, v))
        graph[to].append(Edge(frm, len(graph[frm]) - 1, 0.0, -cost, None, None, None, None))
    # Add supply/demand edges
    for n, bal in node_balance.items():
        if bal > 0:
            add_edge(S, n, bal, 0.0)
        elif bal < 0:
            add_edge(n, T, -bal, 0.0)
    # If there are no supplies and demands, trivial empty selection
    if total_supply == 0 and total_demand == 0:
        return []
    # Add network edges
    for e in adj_edges:
        if e["cap"] <= 0:
            continue
        add_edge(e["u"], e["v"], e["cap"], e["cost"], orig_id=e["id"], layer_id=e["layer_id"], u=e["u"], v=e["v"])
    # Feasibility quick check: capacity from S must reach T via residual capacities (maxflow)
    # compute maxflow via Dinic-like BFS/DFS without costs (simple Edmonds-Karp using BFS)
    def maxflow_bfs_capacity():
        # clone capacities
        cap_graph = {}
        for u, lst in graph.items():
            cap_graph[u] = [edge.cap for edge in lst]
        flow = 0.0
        while True:
            parent = {S: (None, None)}
            q = deque([S])
            while q and T not in parent:
                u = q.popleft()
                for i, e in enumerate(graph[u]):
                    if cap_graph[u][i] > 1e-12 and e.to not in parent:
                        parent[e.to] = (u, i)
                        q.append(e.to)
            if T not in parent:
                break
            # find bottleneck
            v = T; bott = float("inf")
            while v != S:
                u, i = parent[v]
                bott = min(bott, cap_graph[u][i])
                v = u
            v = T
            while v != S:
                u, i = parent[v]
                cap_graph[u][i] -= bott
                rev = graph[u][i].rev
                # find index of reverse edge in graph[v] is graph[v][rev]
                cap_graph[v][rev] += bott
                v = u
            flow += bott
        return flow
    mf = maxflow_bfs_capacity()
    if abs(mf - total_supply) > 1e-8:
        return []
    # Min-cost flow from S to T for flow = total_supply
    N = list(graph.keys())
    potential = {n:0.0 for n in graph}
    flow_needed = total_supply
    flow = 0.0
    cost = 0.0
    parent = {}
    while flow < flow_needed - 1e-12:
        # Dijkstra
        dist = {n: math.inf for n in graph}
        dist[S] = 0.0
        prev = {n: None for n in graph}
        prev_edge = {n: None for n in graph}
        h = [(0.0, S)]
        while h:
            d,u = heapq.heappop(h)
            if d > dist[u] + 1e-15: continue
            for i, e in enumerate(graph[u]):
                if e.cap > 1e-12:
                    v = e.to
                    nd = d + e.cost + potential[u] - potential[v]
                    if nd + 1e-15 < dist[v]:
                        dist[v] = nd
                        prev[v] = u
                        prev_edge[v] = i
                        heapq.heappush(h, (nd, v))
        if dist[T] == math.inf:
            return []
        for n in graph:
            if dist[n] < math.inf:
                potential[n] += dist[n]
        # augment
        addf = flow_needed - flow
        v = T
        while v != S:
            u = prev[v]
            eidx = prev_edge[v]
            e = graph[u][eidx]
            addf = min(addf, e.cap)
            v = u
        v = T
        while v != S:
            u = prev[v]
            eidx = prev_edge[v]
            e = graph[u][eidx]
            re = graph[v][e.rev]
            e.cap -= addf
            re.cap += addf
            cost += addf * e.cost
            v = u
        flow += addf
    # After flow, check critical nodes connectivity: each critical node with non-zero balance must be connected to at least one supply node in used edges
    # Build graph of used edges with positive flow (i.e., reverse residual cap > 0 on original edges)
    used_adj = defaultdict(set)
    used_edge_records = {}  # key (layer,u,v) -> flow
    for u, lst in graph.items():
        for e in lst:
            if e.orig_id is not None:
                # original forward edge; residual reverse edge at e.to list index e.rev has cap = flow sent
                rev_edge = graph[e.to][e.rev]
                flow_sent = rev_edge.cap  # because reverse edge cap increased by flow
                if flow_sent > 1e-12:
                    used_adj[e.u].add(e.v)
                    key = (e.layer_id, e.u, e.v)
                    used_edge_records[key] = used_edge_records.get(key, 0.0) + flow_sent
    # Determine supply nodes that actually supplied >0
    supply_nodes_supplied = set()
    for e in graph[S]:
        rev = graph[e.to][e.rev]
        supplied = rev.cap  # flow sent from S to node is now in reverse cap
        if supplied > 1e-12:
            supply_nodes_supplied.add(e.to)
    # For each critical node with non-zero balance, check reachability from any supply node in used_adj via BFS/DFS (across node ids)
    for c, w in critical_nodes.items():
        # c may be string or number; try to match keys in node_balance
        try:
            if c in node_balance:
                cn = c
            else:
                # try numeric
                cn = int(c) if isinstance(c, str) and c.isdigit() else c
                if cn not in node_balance:
                    # try float key
                    cn = float(c) if isinstance(c, str) else c
            if cn not in node_balance:
                continue
        except:
            cn = c
            if cn not in node_balance:
                continue
        if abs(node_balance[cn]) < 1e-12:
            continue
        # BFS from any supply node to see if can reach cn
        found = False
        visited = set()
        dq = deque(supply_nodes_supplied)
        while dq:
            x = dq.popleft()
            if x in visited: continue
            visited.add(x)
            if x == cn:
                found = True; break
            for y in used_adj.get(x, ()):
                if y not in visited:
                    dq.append(y)
        if not found:
            return []
    # Prepare output: list unique used edges (layer_id, from, to)
    result = []
    for (layer_id, u, v), fval in used_edge_records.items():
        if fval > 1e-12:
            result.append({"layer_id": layer_id, "from": u, "to": v})
    return result