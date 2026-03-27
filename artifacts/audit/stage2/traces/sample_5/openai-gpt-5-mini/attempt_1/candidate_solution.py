def optimize_order_flow_graph(
    nodes: int,
    edges: list,
    trades: list
) -> dict:
    # Build adjacency with edge objects and residual graph
    class Edge:
        __slots__ = ("u","v","cap","cost","rev")
        def __init__(self,u,v,cap,cost,rev):
            self.u=u; self.v=v; self.cap=Decimal(cap); self.cost=Decimal(cost); self.rev=rev

    def build_graph(edge_list):
        g=[[] for _ in range(nodes)]
        for e in edge_list:
            try:
                u=int(e[0]); v=int(e[1])
                cap=max(Decimal(e[2]), Decimal(0))
                cost=max(Decimal(e[3]), Decimal(0))
            except Exception:
                continue
            # allow self-loops and zero-cap edges (they just won't carry flow)
            forward=Edge(u,v,cap,cost,None)
            backward=Edge(v,u,Decimal(0),-cost,None)
            forward.rev=len(g[v])
            backward.rev=len(g[u])
            g[u].append(forward)
            g[v].append(backward)
        return g

    # Deep copy original edges list
    original_edges = copy.deepcopy(edges)
    orig_graph = build_graph(original_edges)

    # Current working graph (residual) copy
    graph = build_graph(copy.deepcopy(edges))

    # Track flows per original directed edge key "[u,v]" aggregated
    flow_distribution = defaultdict(Decimal)
    total_flow = Decimal(0)
    total_cost = Decimal(0)
    partial_fills = []

    # Helper: min-cost augment using successive shortest paths with potentials (Dijkstra with decimals via SPFA-like since small)
    def min_cost_flow(source, sink, demand):
        nonlocal graph
        flow = Decimal(0)
        cost = Decimal(0)
        # potentials for reduced costs (initialize with 0)
        potential = [Decimal(0)] * nodes
        while flow < demand:
            # Dijkstra (using simple Bellman-Ford/SPFA to handle non-negative costs and possible negative from residual)
            dist = [Decimal('Infinity')] * nodes
            inq = [False]*nodes
            prevnode = [-1]*nodes
            prevedge = [-1]*nodes
            dist[source]=Decimal(0)
            dq=deque([source])
            inq[source]=True
            while dq:
                u=dq.popleft()
                inq[u]=False
                for i, e in enumerate(graph[u]):
                    if e.cap <= Decimal(0):
                        continue
                    v=e.v
                    # reduced cost with potentials
                    rc = e.cost + potential[u] - potential[v]
                    nd = dist[u] + rc
                    if nd < dist[v]:
                        dist[v]=nd
                        prevnode[v]=u
                        prevedge[v]=i
                        if not inq[v]:
                            inq[v]=True
                            dq.append(v)
            if dist[sink] == Decimal('Infinity'):
                break
            # update potentials
            for v in range(nodes):
                if dist[v] < Decimal('Infinity'):
                    potential[v] += dist[v]
            # determine augment
            push = demand - flow
            v = sink
            path_edges = []
            while v != source:
                u = prevnode[v]
                if u == -1:
                    push = Decimal(0)
                    break
                e = graph[u][prevedge[v]]
                if e.cap < push:
                    push = e.cap
                path_edges.append((u, prevedge[v], e))
                v = u
            if push <= Decimal(0):
                break
            # apply push
            v = sink
            path_cost = Decimal(0)
            while v != source:
                u = prevnode[v]
                ei = prevedge[v]
                e = graph[u][ei]
                # reduce capacity
                e.cap -= push
                # increase reverse capacity
                rev = graph[e.v][e.rev]
                rev.cap += push
                path_cost += e.cost
                v = u
            flow += push
            cost += push * path_cost
        return float(flow), float(cost), graph

    # Process trades sequentially
    # Keep copies of graph state after each trade (intermediate snapshots)
    intermediate_states = []
    for trade in trades:
        # validate trade
        try:
            vol = Decimal(trade.get("volume", 0))
            src = int(trade.get("source", 0))
            tgt = int(trade.get("target", 0))
        except Exception:
            continue
        if vol <= Decimal(0):
            # invalid or zero volume -> skip
            continue
        # snapshot before processing
        intermediate_states.append(copy.deepcopy(graph))
        # compute min cost flow for this trade
        f, c, graph = (lambda s=src, t=tgt, d=vol: (lambda f,c,g: (f,c,g))(*min_cost_flow(s,t,d)))()
        f_dec = Decimal(str(f))
        c_dec = Decimal(str(c))
        # record totals
        total_flow += f_dec
        total_cost += c_dec
        # update flow_distribution by comparing residual graph snapshot differences:
        # To track flow along original forward edges, we can accumulate from reverse edge capacities in graph.
        # Reconstruct mapping of original edges by scanning original_edges list and checking residuals.
        # We'll compute current used = original cap - current forward cap
        # Build a helper graph of original to current forward caps
        # First, build a fresh graph from original_edges to know original capacities
        base = build_graph(original_edges)
        # Create map from (u,v) to total used capacity by comparing base and current graph forward edges' caps
        # For each u, iterate base[u] edges and find matching in current graph[u] by v and cost
        # Because multiple parallel edges could exist, match by sequence: iterate pairs
        # Build lists of edges for quick matching
        for u in range(nodes):
            base_edges = base[u]
            cur_edges = graph[u]
            # iterate through base edges and try to match by v and cost; consume matches
            used_indices = [False]*len(cur_edges)
            for be in base_edges:
                target_v = be.v
                target_cost = be.cost
                orig_cap = be.cap
                # find matching current edge
                match_idx = -1
                for idx, ce in enumerate(cur_edges):
                    if used_indices[idx]:
                        continue
                    if ce.v == target_v and ce.cost == target_cost:
                        match_idx = idx
                        used_indices[idx]=True
                        break
                if match_idx == -1:
                    continue
                ce = cur_edges[match_idx]
                # used = orig_cap - current_forward_cap (reverse cap holds accum)
                used = orig_cap - ce.cap
                if used > Decimal(0):
                    key = f"[{u},{target_v}]"
                    flow_distribution[key] = max(flow_distribution.get(key, Decimal(0)), Decimal(0)) + used
        # if partial fill
        if f_dec < vol:
            partial_fills.append({
                "volume_unfilled": float(vol - f_dec),
                "source": src,
                "target": tgt
            })
    # final snapshot
    final_state = copy.deepcopy(graph)

    # Convert flow_distribution decimals to floats and aggregate identical keys (already aggregated)
    fd_out = {}
    for k, v in flow_distribution.items():
        # round small negatives to zero
        val = float(v) if v >= Decimal(0) else 0.0
        fd_out[k] = val

    result = {
        "total_flow": float(total_flow),
        "total_cost": float(total_cost),
        "flow_distribution": fd_out,
        "partial_fills": partial_fills
    }
    return result