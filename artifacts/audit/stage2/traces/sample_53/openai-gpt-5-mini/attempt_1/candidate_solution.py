def high_frequency_arbitrage_engine(
    edges: List[Tuple[int, int, float]],
    initial_prices: List[float],
    updates: List[Tuple[int, float]],
    queries: List[Tuple[int, int]],
) -> List[float]:
    # Apply updates
    prices = list(initial_prices)
    for idx, p in updates:
        prices[idx] = p

    n = len(prices)
    # Build adjacency lists and direct edge map
    adj: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
    rev_adj: Dict[int, List[int]] = defaultdict(list)
    direct_fee: Dict[Tuple[int, int], float] = {}
    for u, v, w in edges:
        adj[u].append((v, w))
        rev_adj[v].append(u)
        direct_fee[(u, v)] = w

    # Preprocess queries grouping by source node
    queries_by_src: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    for i, (u, v) in enumerate(queries):
        queries_by_src[u].append((i, v))

    results = [0.0] * len(queries)

    # For each unique source, run Bellman-Ford to get min fees paths and detect neg cycles reachable from source
    for src, qlist in queries_by_src.items():
        # If all queries from src are direct-edge preference and direct edges exist for each v,
        # still must consider when direct edge absent -> need shortest path.
        # Run Bellman-Ford for min path weights from src.
        dist = [math.inf] * n
        dist[src] = 0.0
        # relax edges n-1 times
        for _ in range(n - 1):
            updated = False
            for u, v, w in edges:
                if dist[u] != math.inf and dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    updated = True
            if not updated:
                break
        # detect nodes part of or reachable from negative cycles reachable from src
        neg = [False] * n
        for u, v, w in edges:
            if dist[u] != math.inf and dist[u] + w < dist[v]:
                neg[v] = True
        # propagate negativity through graph
        dq = deque([i for i, val in enumerate(neg) if val])
        while dq:
            u = dq.popleft()
            for v, _ in adj.get(u, ()):
                if not neg[v]:
                    neg[v] = True
                    dq.append(v)
        # For each query from this src compute fee(u->v): prefer direct edge if exists
        for qi, v in qlist:
            u = src
            # if direct edge exists, use it
            if (u, v) in direct_fee:
                fee = direct_fee[(u, v)]
                # even if negative cycles exist elsewhere, direct-edge preference means only path fee used
                diff = prices[v] - prices[u] - fee
                results[qi] = float(diff)
            else:
                # no direct edge: need shortest path fee from u to v
                if dist[v] == math.inf:
                    results[qi] = float("-inf")
                elif neg[v]:
                    # negative cycle reachable from u that can reach v
                    results[qi] = float("inf")
                else:
                    fee = dist[v]
                    diff = prices[v] - prices[u] - fee
                    results[qi] = float(diff)
    return results