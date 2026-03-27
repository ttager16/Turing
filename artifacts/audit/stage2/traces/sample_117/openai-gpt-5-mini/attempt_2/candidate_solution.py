def optimize_logistics_flow(network: List[List[int]], source: int, sink: int) -> List[List[int]]:
    # Build graph with adjacency list; support parallel edges
    # Edge: to, rev_index, cap, cost
    adj: Dict[int, List[Dict]] = defaultdict(list)
    nodes = set()
    for u, v, cap, cost, pr in network:
        nodes.add(u); nodes.add(v)
    max_node = max(nodes) if nodes else 0

    def add_edge(u: int, v: int, cap: int, cost: int):
        adj[u].append({"to": v, "rev": len(adj[v]), "cap": cap, "cost": cost})
        adj[v].append({"to": u, "rev": len(adj[u]) - 1, "cap": 0, "cost": -cost})

    # Incorporate priority into cost as small tie-breaker: effective_cost = cost - epsilon*priority
    # Use integer arithmetic: multiply costs by factor, subtract priority
    # Choose factor large enough to keep primary cost ordering: factor = 100000
    FACTOR = 100000
    for u, v, cap, cost, pr in network:
        eff_cost = cost * FACTOR - pr  # lower is better
        add_edge(u, v, cap, eff_cost)

    # Min-Cost Max-Flow using successive shortest augmenting path with potentials
    N = max_node + 1
    INF = 10**18
    potential = [0] * (N)
    dist = [0] * (N)
    prevnode = [0] * (N)
    prevedge = [0] * (N)

    flow = 0
    cost = 0

    while True:
        # Dijkstra on reduced costs
        for i in range(N):
            dist[i] = INF
        dist[source] = 0
        hq = [(0, source)]
        visited = [False]*N
        while hq:
            d, u = heapq.heappop(hq)
            if d != dist[u]:
                continue
            for i, e in enumerate(adj[u]):
                if e["cap"] <= 0:
                    continue
                v = e["to"]
                nd = d + e["cost"] + potential[u] - potential[v]
                if nd < dist[v]:
                    dist[v] = nd
                    prevnode[v] = u
                    prevedge[v] = i
                    heapq.heappush(hq, (nd, v))
        if dist[sink] == INF:
            break
        for v in range(N):
            if dist[v] < INF:
                potential[v] += dist[v]
        # augment
        addf = INF
        v = sink
        while v != source:
            u = prevnode[v]
            e = adj[u][prevedge[v]]
            addf = min(addf, e["cap"])
            v = u
        v = sink
        while v != source:
            u = prevnode[v]
            e = adj[u][prevedge[v]]
            rev = adj[v][e["rev"]]
            e["cap"] -= addf
            rev["cap"] += addf
            v = u
        flow += addf
        cost += addf * potential[sink]

    # After max-flow found, compute min-cut via reachable from source in residual graph
    visited = [False]*N
    stack = [source]
    while stack:
        u = stack.pop()
        if visited[u]:
            continue
        visited[u] = True
        for e in adj[u]:
            if e["cap"] > 0 and not visited[e["to"]]:
                stack.append(e["to"])
    # Edges from reachable set to non-reachable in original network are critical
    critical = []
    # Need to map original edges; since multiple parallel edges exist, check if any original capacity used up? 
    # We'll consider any original network edge (u->v) such that u reachable and v not reachable as critical.
    seen = set()
    for u, v, cap, cost0, pr in network:
        if (u, v) in seen:
            # keep duplicates only once per expected output format
            pass
        if u < len(visited) and v < len(visited):
            if visited[u] and not visited[v]:
                if (u, v) not in seen:
                    critical.append([u, v])
                    seen.add((u, v))
    return critical