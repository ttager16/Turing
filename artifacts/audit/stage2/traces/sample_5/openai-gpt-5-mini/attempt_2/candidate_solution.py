def optimize_order_flow_graph(
    nodes: int,
    edges: list,
    trades: list
) -> dict:
    # Build adjacency with edge objects; use decimals for precision
    class Edge:
        __slots__ = ('u','v','cap','cost','rev')
        def __init__(self,u,v,cap,cost,rev=None):
            self.u=u; self.v=v; self.cap=Decimal(cap); self.cost=Decimal(cost); self.rev=rev

    def build_graph(edges_list):
        g = [[] for _ in range(nodes)]
        edge_map = {}  # key (u,v,idx)->edge reference for reporting (sum flows)
        for idx, e in enumerate(edges_list):
            u, v, cap, cost = e
            if cap < 0 or cost < 0:
                # guard: treat negative as zero to avoid invalid
                cap = max(0.0, cap)
                cost = max(0.0, cost)
            # create forward and backward edges
            fwd = Edge(u,v,cap,cost,None)
            bwd = Edge(v,u,Decimal('0'), -Decimal(cost), None)
            fwd.rev = bwd
            bwd.rev = fwd
            g[u].append(fwd)
            g[v].append(bwd)
            edge_map[(u,v,idx)] = fwd
        return g, edge_map

    # Deep copy original edges for baseline
    original_edges = copy.deepcopy(edges)
    graph, edge_map = build_graph(original_edges)
    # Keep copies after each trade
    intermediate_graphs = []
    total_flow = Decimal('0')
    total_cost = Decimal('0')
    flow_distribution = defaultdict(Decimal)
    partial_fills = []

    # Helper: min-cost augment using successive shortest path (Bellman-Ford for potentials)
    def min_cost_flow(g, s, t, demand):
        flow = Decimal('0')
        cost = Decimal('0')
        n = len(g)
        # initialize potentials with Bellman-Ford to handle negative costs from residuals safely
        potential = [Decimal('0')] * n
        # Bellman-Ford from source to set potentials (handles negative edge costs)
        dist = [Decimal('Infinity')] * n
        dist[s] = Decimal('0')
        for _ in range(n-1):
            updated = False
            for u in range(n):
                if dist[u] == Decimal('Infinity'):
                    continue
                for e in g[u]:
                    if e.cap > 0 and dist[e.v] > dist[u] + e.cost:
                        dist[e.v] = dist[u] + e.cost
                        updated = True
            if not updated:
                break
        for i in range(n):
            if dist[i] != Decimal('Infinity'):
                potential[i] = dist[i]

        while demand > Decimal('0'):
            # Dijkstra-like with costs adjusted by potentials (use simple Dijkstra via lists since n small)
            dist = [Decimal('Infinity')] * n
            inqueue = [False]*n
            prev = [None]*n
            prev_edge = [None]*n
            dist[s] = Decimal('0')
            # Use deque as simple priority queue by exploring smallest dist each time (inefficient but okay)
            # Implement simple loop scanning for min dist (deterministic)
            visited = [False]*n
            while True:
                u = None
                mind = Decimal('Infinity')
                for i in range(n):
                    if not visited[i] and dist[i] < mind:
                        mind = dist[i]; u = i
                if u is None:
                    break
                visited[u] = True
                for e in g[u]:
                    if e.cap <= 0:
                        continue
                    # reduced cost
                    rcost = e.cost + potential[u] - potential[e.v]
                    nd = dist[u] + rcost
                    if dist[e.v] > nd:
                        dist[e.v] = nd
                        prev[e.v] = u
                        prev_edge[e.v] = e
            if dist[t] == Decimal('Infinity'):
                break  # no more augmenting path
            # update potentials
            for i in range(n):
                if dist[i] < Decimal('Infinity'):
                    potential[i] += dist[i]
            # find bottleneck
            addf = demand
            v = t
            while v != s:
                e = prev_edge[v]
                if e is None:
                    addf = Decimal('0'); break
                if e.cap < addf:
                    addf = e.cap
                v = prev[v]
            if addf == Decimal('0'):
                break
            # apply flow
            v = t
            path_cost = Decimal('0')
            while v != s:
                e = prev_edge[v]
                e.cap -= addf
                e.rev.cap += addf
                path_cost += e.cost
                v = prev[v]
            flow += addf
            cost += addf * path_cost
            demand -= addf
        return flow, cost

    # Process each trade sequentially, updating graph between trades; use copies for integrity
    for trade in trades:
        # validate trade
        vol = trade.get("volume")
        src = trade.get("source")
        tgt = trade.get("target")
        try:
            vol = Decimal(vol)
        except Exception:
            # invalid, skip
            continue
        if vol <= 0 or not (0 <= src < nodes) or not (0 <= tgt < nodes):
            # report as fully unfilled for invalid volumes per safety
            partial_fills.append({"volume_unfilled": float(vol if vol>0 else 0.0), "source": src, "target": tgt})
            continue
        # copy current graph for isolation
        g_copy = copy.deepcopy(graph)
        # attempt to fulfill volume
        f, c = min_cost_flow(g_copy, src, tgt, vol)
        # update main graph to residuals from g_copy (apply differences)
        # Approach: for each node u, for each edge in original graph[u], find corresponding edge in g_copy by matching u->v and cost
        # Because we used deep copies of Edge objects, but graph and g_copy edges align by positions; create mapping by u,v,cost
        # Build helper map from (u,v,cost) -> list edges in g_copy
        gc_map = defaultdict(list)
        for u in range(len(g_copy)):
            for e in g_copy[u]:
                # store forward edges that were originally forward or created as residuals; use cost and endpoints
                gc_map[(e.u,e.v,float(e.cost))].append(e)
        # For each original forward edge in graph, find matching edge in g_copy and set graph edge cap to that cap
        for u in range(len(graph)):
            for idx_e, e in enumerate(graph[u]):
                # Only update forward edges that were part of initial construction: those may have positive initial cap OR were reverses created; we update all by matching u,v,cost
                key = (e.u, e.v, float(e.cost))
                lst = gc_map.get(key)
                if lst:
                    # pop one to align
                    matched = lst.pop(0)
                    e.cap = Decimal(matched.cap)
                    # update reverse cap as well to keep consistency
                    # find reverse in graph[u].rev exists
                    if e.rev is not None:
                        # Find corresponding rev in g_copy
                        rev_key = (e.rev.u, e.rev.v, float(e.rev.cost))
                        rev_list = gc_map.get(rev_key)
                        if rev_list:
                            rev_matched = rev_list.pop(0)
                            e.rev.cap = Decimal(rev_matched.cap)
        # swap graph to updated state
        graph = copy.deepcopy(graph)
        # record intermediate state
        intermediate_graphs.append(copy.deepcopy(graph))
        # record flows and totals: compute difference between original edge capacities and current capacities to get used flow
        # We'll compute per original edges list to ensure keys match requirement "[u,v]"
        used_this_round = defaultdict(Decimal)
        for idx, e in enumerate(original_edges):
            u,v,init_cap,_ = e
            # find in current graph an edge from u to v with original cost to compute residual
            found = None
            for eg in graph[u]:
                if eg.v == v:
                    # match approximately by init cap + reverse cap possibly; use presence
                    found = eg
                    break
            if found is not None:
                used = Decimal(init_cap) - found.cap
                if used > 0:
                    used_this_round[(u,v)] += used
        # accumulate into global flow distribution
        for (u,v), val in used_this_round.items():
            flow_distribution[f"[{u},{v}]"] += val
        total_flow += f
        total_cost += c
        # if partial
        if f < Decimal(trade.get("volume")):
            unfilled = Decimal(trade.get("volume")) - f
            partial_fills.append({"volume_unfilled": float(unfilled), "source": src, "target": tgt})

    # Final formatting: convert Decimals to floats
    fd_out = {}
    # Remove zero flows
    for k, v in flow_distribution.items():
        fv = float(v)
        if fv > 0:
            fd_out[k] = fv

    result = {
        "total_flow": float(total_flow),
        "total_cost": float(total_cost),
        "flow_distribution": fd_out,
        "partial_fills": partial_fills
    }
    return result