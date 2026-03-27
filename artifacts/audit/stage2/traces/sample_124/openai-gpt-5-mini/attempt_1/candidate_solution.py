def design_metro_system(
    demand_matrix: List[List[int]],
    cost_matrix: List[List[int]],
    budget: int,
    max_avg_time: float
) -> bool:
    n = len(demand_matrix)
    # Quick checks
    total_demand = 0
    for i in range(n):
        for j in range(n):
            total_demand += demand_matrix[i][j]
    if total_demand == 0:
        return True  # no passengers, trivially meets requirement
    if budget <= 0:
        # If any demand between different stations, impossible
        for i in range(n):
            for j in range(n):
                if i != j and demand_matrix[i][j] > 0:
                    return False
        return True

    # Candidate edges with benefit score:
    # Estimate benefit of an edge (u,v) as demand served by making direct connection:
    # sum over all pairs (i,j) of decreased hop count if edge added approximated by
    # considering paths that go through u-v as 1 hop between u and v.
    # Simpler heuristic: weight edge by total demand involving its endpoints.
    edges = []
    for i in range(n):
        for j in range(i+1, n):
            c = cost_matrix[i][j]
            if c <= 0:
                continue
            demand_endpoints = 0
            for k in range(n):
                demand_endpoints += demand_matrix[i][k] + demand_matrix[k][i] + demand_matrix[j][k] + demand_matrix[k][j]
            # avoid zero demand edges getting priority; add small epsilon
            score = demand_endpoints / c
            edges.append(( -score, c, i, j ))  # negative for sorting descending

    edges.sort()
    # Build graph greedily by score, but ensure we don't exceed budget.
    built = [[0]*n for _ in range(n)]
    remaining_budget = budget
    for negscore, c, u, v in edges:
        if c <= remaining_budget:
            # add edge
            built[u][v] = built[v][u] = 1
            remaining_budget -= c

    # After initial build, ensure connectivity for demanded pairs.
    # If some demanded pair disconnected, try to add cheapest path edges between components.
    def bfs_components(adj):
        comp = [-1]*n
        cid = 0
        for i in range(n):
            if comp[i] != -1:
                continue
            q = deque([i])
            comp[i] = cid
            while q:
                x = q.popleft()
                for y in range(n):
                    if adj[x][y] and comp[y] == -1:
                        comp[y] = cid
                        q.append(y)
            cid += 1
        return comp, cid

    adj = built
    comp, comp_count = bfs_components(adj)
    # Try to connect components with cheapest inter-component edges until either all demanded pairs in same comp or budget exhausted.
    # Build list of potential inter-component edges sorted by cost
    while True:
        # Check if any demanded pair lies in different components
        need_connection = False
        for i in range(n):
            for j in range(n):
                if demand_matrix[i][j] > 0 and comp[i] != comp[j]:
                    need_connection = True
                    break
            if need_connection:
                break
        if not need_connection:
            break
        # find cheapest edge connecting two different components
        best = None
        for i in range(n):
            for j in range(i+1, n):
                if comp[i] != comp[j]:
                    c = cost_matrix[i][j]
                    if c <= remaining_budget:
                        if best is None or c < best[0]:
                            best = (c, i, j)
        if best is None:
            return False
        c, u, v = best
        if c > remaining_budget:
            return False
        adj[u][v] = adj[v][u] = 1
        remaining_budget -= c
        comp, comp_count = bfs_components(adj)

    # Now compute all-pairs shortest path lengths (in hops) using BFS from each node
    dist = [[None]*n for _ in range(n)]
    for s in range(n):
        d = [-1]*n
        q = deque([s])
        d[s] = 0
        while q:
            x = q.popleft()
            for y in range(n):
                if adj[x][y] and d[y] == -1:
                    d[y] = d[x] + 1
                    q.append(y)
        for t in range(n):
            dist[s][t] = d[t]

    # If any demanded pair unreachable, fail
    total_time = 0
    for i in range(n):
        for j in range(n):
            if demand_matrix[i][j] > 0:
                if dist[i][j] == -1 or dist[i][j] is None:
                    return False
                total_time += demand_matrix[i][j] * dist[i][j]

    avg_time = total_time / total_demand
    return avg_time <= max_avg_time