def build_minimum_spanning_tree(n: int, edges: List[List[int]]) -> Union[Dict[str, Any], None]:
    if n <= 0:
        return None
    if n == 1:
        return {
            'mst_edges': [],
            'statistics': {
                'total_cost': 0,
                'num_edges': 0,
                'max_edge_weight': 0,
                'min_edge_weight': 0,
                'positive_cost_sum': 0,
                'negative_cost_sum': 0,
                'num_positive_edges': 0,
                'num_negative_edges': 0,
                'avg_edge_weight': 0,
                'edge_weight_range': 0,
                'second_best_total_cost': None,
                'min_swap_delta': None,
                'max_swap_delta': None,
                'bridges_count': 0,
                'edge_weight_median': 0,
                'cost_stddev': 0.00
            }
        }
    # Normalize edges: ignore self-loops, keep minimum weight for undirected pair
    edge_map = {}
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        if u == v:
            continue
        if not (0 <= u < n and 0 <= v < n):
            continue
        a, b = (u, v) if u < v else (v, u)
        key = (a, b)
        if key not in edge_map or w < edge_map[key]:
            edge_map[key] = w
    # If no edges at all and n>1, disconnected
    if not edge_map:
        return None
    # Build adjacency for bridge detection and connectivity
    all_edges_list = []
    for (u, v), w in edge_map.items():
        all_edges_list.append((u, v, w))
        adj[u].append((v, w))
        adj[v].append((u, w))
    # Check connectivity via BFS using edges (ignoring isolated nodes count as disconnected)
    visited = [False]*n
    from collections import deque
    dq = deque([0])
    visited[0] = True
    while dq:
        x = dq.popleft()
        for y,_ in adj[x]:
            if not visited[y]:
                visited[y] = True
                dq.append(y)
    if not all(visited):
        return None
    # Count bridges using Tarjan on the original graph (using edge_map)
    sys.setrecursionlimit(max(1000000, n+10))
    g = [[] for _ in range(n)]
    edge_id = {}
    eid = 0
    for (u,v), w in edge_map.items():
        g[u].append((v, eid))
        g[v].append((u, eid))
        edge_id[eid] = (u, v)
        eid += 1
    tin = [-1]*n
    low = [0]*n
    timer = 0
    bridges = set()
    def dfs(u, peid):
        nonlocal timer
        tin[u] = low[u] = timer
        timer += 1
        for v, eidn in g[u]:
            if eidn == peid:
                continue
            if tin[v] != -1:
                low[u] = min(low[u], tin[v])
            else:
                dfs(v, eidn)
                low[u] = min(low[u], low[v])
                if low[v] > tin[u]:
                    bridges.add(eidn)
    dfs(0, -1)
    bridges_count = len(bridges)
    # Kruskal with tie-breaking to ensure lexicographically smallest edge list among equal-cost MSTs.
    # To ensure deterministic lexicographic MST, sort edges by (weight, u, v)
    sorted_edges = sorted(all_edges_list, key=lambda x: (x[2], x[0], x[1]))
    parent = list(range(n))
    rank = [0]*n
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra==rb:
            return False
        if rank[ra]<rank[rb]:
            parent[ra]=rb
        else:
            parent[rb]=ra
            if rank[ra]==rank[rb]:
                rank[ra]+=1
        return True
    mst_edges = []
    mst_edge_weights = {}
    total_cost = 0
    for u,v,w in sorted_edges:
        if union(u,v):
            mst_edges.append((u,v))
            mst_edge_weights[(u,v)] = w
            total_cost += w
            if len(mst_edges) == n-1:
                break
    if len(mst_edges) != n-1:
        return None
    # Ensure mst_edges sorted lexicographically (they already with tie-breaker but sort to be safe)
    mst_edges = sorted([tuple(sorted(e)) for e in mst_edges], key=lambda x: (x[0], x[1]))
    # Build MST adjacency for cycle queries
    mst_adj = [[] for _ in range(n)]
    for u,v in mst_edges:
        w = mst_edge_weights.get((u,v), mst_edge_weights.get((v,u)))
        mst_adj[u].append((v,w))
        mst_adj[v].append((u,w))
    # Preprocess for LCA to find max edge on path between two nodes quickly (binary lifting)
    LOG = (n-1).bit_length() + 1
    up = [[-1]*n for _ in range(LOG)]
    maxw = [[-10**18]*n for _ in range(LOG)]
    depth = [0]*n
    def dfs2(u, p):
        for v,w in mst_adj[u]:
            if v==p: continue
            depth[v]=depth[u]+1
            up[0][v]=u
            maxw[0][v]=w
            dfs2(v,u)
    # root at 0
    up[0][0] = -1
    maxw[0][0] = -10**18
    dfs2(0,-1)
    for k in range(1, LOG):
        for v in range(n):
            if up[k-1][v] != -1:
                up[k][v] = up[k-1][up[k-1][v]]
                maxw[k][v] = max(maxw[k-1][v], maxw[k-1][up[k-1][v]])
            else:
                up[k][v] = -1
                maxw[k][v] = maxw[k-1][v]
    def max_on_path(a,b):
        if a==b:
            return -10**18
        if depth[a] < depth[b]:
            a,b = b,a
        diff = depth[a]-depth[b]
        curmax = -10**18
        k = 0
        while diff:
            if diff & 1:
                curmax = max(curmax, maxw[k][a])
                a = up[k][a]
            diff >>= 1
            k += 1
        if a==b:
            return curmax
        for k in range(LOG-1, -1, -1):
            if up[k][a] != -1 and up[k][a] != up[k][b]:
                curmax = max(curmax, maxw[k][a], maxw[k][b])
                a = up[k][a]
                b = up[k][b]
        curmax = max(curmax, maxw[0][a], maxw[0][b])
        return curmax
    # Compute swap deltas for all non-MST edges
    mst_set = set(mst_edges)
    non_mst_edges = []
    for (u,v), w in edge_map.items():
        e = tuple(sorted((u,v)))
        if e not in mst_set:
            non_mst_edges.append((e[0], e[1], w))
    swap_deltas = []
    second_best_candidates = []
    for u,v,w in non_mst_edges:
        mx = max_on_path(u,v)
        # if mx is -inf, should not happen
        delta = w - mx
        # The alternative tree cost = total_cost + delta
        alt_cost = total_cost + delta
        second_best_candidates.append(alt_cost)
        if delta > 0:
            swap_deltas.append(delta)
    # second_best_total_cost: minimal alt_cost strictly greater than total_cost
    second_best = None
    for val in second_best_candidates:
        if val > total_cost:
            if second_best is None or val < second_best:
                second_best = val
    min_swap = None
    max_swap = None
    if swap_deltas:
        min_swap = min(swap_deltas)
        max_swap = max(swap_deltas)
    # Compute statistics
    weights = [mst_edge_weights.get(e, mst_edge_weights.get((e[1], e[0]))) for e in mst_edges]
    num_edges = len(weights)
    total_cost = sum(weights)
    if num_edges == 0:
        return None
    max_edge_weight = max(weights)
    min_edge_weight = min(weights)
    pos_sum = sum(w for w in weights if w>0)
    neg_sum = sum(w for w in weights if w<0)
    num_pos = sum(1 for w in weights if w>0)
    num_neg = sum(1 for w in weights if w<0)
    avg_edge_weight = round(total_cost / num_edges)
    edge_weight_range = max_edge_weight - min_edge_weight
    # median
    sorted_w = sorted(weights)
    m = num_edges
    if m % 2 == 1:
        median = sorted_w[m//2]
    else:
        median = round((sorted_w[m//2 - 1] + sorted_w[m//2]) / 2)
    # population standard deviation
    mean = total_cost / num_edges
    var = sum((w - mean)**2 for w in weights) / num_edges
    stddev = round(math.sqrt(var) + 1e-12, 2)
    # Prepare output edges as [u,v] with u<v sorted lexicographically
    out_edges = [[u,v] for u,v in mst_edges]
    result = {
        'mst_edges': out_edges,
        'statistics': {
            'total_cost': total_cost,
            'num_edges': num_edges,
            'max_edge_weight': max_edge_weight,
            'min_edge_weight': min_edge_weight,
            'positive_cost_sum': pos_sum,
            'negative_cost_sum': neg_sum,
            'num_positive_edges': num_pos,
            'num_negative_edges': num_neg,
            'avg_edge_weight': avg_edge_weight,
            'edge_weight_range': edge_weight_range,
            'second_best_total_cost': second_best,
            'min_swap_delta': min_swap,
            'max_swap_delta': max_swap,
            'bridges_count': bridges_count,
            'edge_weight_median': median,
            'cost_stddev': stddev
        }
    }
    return result