def high_frequency_arbitrage_engine(
    edges: List[Tuple[int, int, float]],
    initial_prices: List[float],
    updates: List[Tuple[int, float]],
    queries: List[Tuple[int, int]],
) -> List[float]:
    # Apply updates
    prices = initial_prices[:]  # copy
    for idx, p in updates:
        prices[idx] = p

    n = len(prices)
    adj = [[] for _ in range(n)]
    rev = [[] for _ in range(n)]
    direct_fee = {}
    for u, v, w in edges:
        adj[u].append((v, w))
        rev[v].append((u, w))
        # store direct edge fee if multiple, prefer smallest fee for direct-edge preference when same u->v
        if (u, v) not in direct_fee or w < direct_fee[(u, v)]:
            direct_fee[(u, v)] = w

    # We need shortest path fees from u to v (sum of fees). Edges can be negative.
    # For queries, if direct edge exists use that fee. Otherwise need min-path fee or detect +inf/-inf.
    # Strategy: group queries by source u where no direct edge; run Bellman-Ford from each such source,
    # detect nodes influenced by negative cycles reachable from source.
    results = []
    # Precompute which queries require full path search
    need_bf = {}
    for qi, (u, v) in enumerate(queries):
        if (u, v) in direct_fee:
            need_bf[qi] = None  # direct available
        else:
            need_bf[qi] = (u, v)

    # Map source -> list of query indices needing BF from that source
    src_to_qs = defaultdict(list)
    for qi, val in need_bf.items():
        if val is not None:
            u, v = val
            src_to_qs[u].append(qi)

    # Cache BF results per source: dist list or None if unreachable; also negcycle reachable set
    bf_cache = {}

    def run_bf(src):
        # Bellman-Ford to get min fee sums from src, detect nodes reachable from src that can be improved by negative cycles.
        dist = [math.inf] * n
        dist[src] = 0.0
        # relax n-1 times
        for _ in range(n - 1):
            updated = False
            for u in range(n):
                if dist[u] == math.inf:
                    continue
                for v, w in adj[u]:
                    nd = dist[u] + w
                    if nd < dist[v]:
                        dist[v] = nd
                        updated = True
            if not updated:
                break
        # detect nodes in or affected by negative cycles reachable from src
        neg = [False] * n
        for u in range(n):
            if dist[u] == math.inf:
                continue
            for v, w in adj[u]:
                if dist[u] + w < dist[v]:
                    neg[v] = True
        # Propagate neg flags through graph (any node reachable from a flagged node is also affected)
        if any(neg):
            dq = deque([i for i, f in enumerate(neg) if f])
            visited = neg[:]
            while dq:
                u = dq.popleft()
                for v, _ in adj[u]:
                    if not visited[v]:
                        visited[v] = True
                        dq.append(v)
            neg = visited
        else:
            neg = [False] * n
        bf_cache[src] = (dist, neg)
        return dist, neg

    for qi, (u, v) in enumerate(queries):
        # Use direct edge if present
        if (u, v) in direct_fee:
            fee = direct_fee[(u, v)]
            diff = prices[v] - prices[u] - fee
            results.append(diff)
            continue
        # Else need BF from u
        if u not in bf_cache:
            run_bf(u)
        dist, neg = bf_cache[u]
        if dist[v] == math.inf:
            results.append(float('-inf'))
        elif neg[v]:
            results.append(float('inf'))
        else:
            fee = dist[v]
            diff = prices[v] - prices[u] - fee
            results.append(diff)

    return results