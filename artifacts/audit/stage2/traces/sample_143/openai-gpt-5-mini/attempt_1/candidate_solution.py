def prioritized_topological_sort(n: int, edges: List[List[int]], importance: List[int]) -> Optional[Dict[str, Any]]:
    # Input validation
    if not isinstance(n, int):
        return {'error': 'n must be an integer'}
    if n < 1 or n > 100_000:
        return {'error': 'n out of range'}
    if not isinstance(edges, list):
        return {'error': 'edges must be a list of lists'}
    for e in edges:
        if not (isinstance(e, list) and len(e) == 2):
            return {'error': 'edges must be a list of lists'}
        u, v = e
        if not (isinstance(u, int) and isinstance(v, int)):
            return {'error': 'edge must be a list of two integers'}
        if not (0 <= u < n and 0 <= v < n):
            return {'error': 'node id out of range'}
        if u == v:
            # self-loop implies cycle; but still valid input unless they want immediate None.
            # We'll allow and detect cycle later; input validation passes.
            pass
    if not isinstance(importance, list) or not all(isinstance(x, int) for x in importance):
        return {'error': 'importance must be a list of integers'}
    if len(importance) != n:
        return {'error': 'importance length mismatch'}

    # Canonicalize edges (remove duplicates)
    adj = [[] for _ in range(n)]
    out_deg = [0] * n
    in_deg = [0] * n
    seen = set()
    for u, v in edges:
        key = (u, v)
        if key in seen:
            continue
        seen.add(key)
        adj[u].append(v)
        out_deg[u] += 1
        in_deg[v] += 1

    num_sources = sum(1 for d in in_deg if d == 0)
    num_sinks = sum(1 for d in out_deg if d == 0)

    # Prepare Kahn with priority: use heap of [-importance[i], i] as lists per spec.
    heap = []
    for i in range(n):
        if in_deg[i] == 0:
            heapq.heappush(heap, [-importance[i], i])

    max_parallel_frontier = len(heap)
    frontier_max_importance_sum = sum(importance[i] for (_, i) in heap)
    if heap:
        frontier_max_importance_sum = sum(importance[i] for (_, i) in heap)
    else:
        frontier_max_importance_sum = 0
    priority_score = 0
    order = []
    processed = 0
    levels = [0] * n
    current_in = in_deg[:]  # copy to avoid mutating input
    tie_breaks = 0

    # For tracking longest path lengths from sources (top-down): dp_len[node]= longest distance (in edges) from any source to node
    dp_len = [0] * n

    # To compute longest path to sinks later, build reverse adjacency
    rev_adj = [[] for _ in range(n)]
    for u in range(n):
        for v in adj[u]:
            rev_adj[v].append(u)

    # For tracking frontier importance sums we need to compute each step before selection
    # But heap stores [-importance, id] as lists; we must not rely on internal heap order to compute sum.
    # We'll maintain current frontier sum variable updated when pushing/popping.
    frontier_sum = sum(importance[i] for i in range(n) if current_in[i] == 0)
    frontier_max_importance_sum = frontier_sum

    while heap:
        # update max frontier size
        if len(heap) > max_parallel_frontier:
            max_parallel_frontier = len(heap)
        # compute frontier sum already tracked
        if frontier_sum > frontier_max_importance_sum:
            frontier_max_importance_sum = frontier_sum

        item = heapq.heappop(heap)
        # Per spec, items pushed as lists of two integers; ensure type is list
        # Some Python heapq may return tuple if pushed as tuple, but we pushed lists.
        imp_neg, node = item
        # Tie-break count: need to detect if multiple available tasks had same importance and we chose smaller id.
        # We can check if after pop there was any other available with same importance.
        if heap:
            top_imp_neg, top_id = heap[0]
            if top_imp_neg == imp_neg:
                # since heap order ensures smaller id at top if same importance, we popped the smallest id among equals?
                # But we popped item which must be the smallest id among equals; a tie_break is counted when there existed
                # multiple tasks with same importance and we chose smaller id. That is whenever prior to popping, count of nodes
                # in frontier with same importance >1 and chosen id is smallest among them. We'll approximate by checking if any other
                # had same importance (heap[0] has same imp_neg) then it's a tie resolved by smaller id.
                # However if heap[0] is same imp_neg but has larger id, impossible. So we count tie once when there exists any same importance.
                tie_breaks += 1
        # update frontier_sum
        frontier_sum -= importance[node]

        order.append(node)
        priority_score += importance[node] * (n - processed)
        processed += 1

        # process neighbors
        for v in adj[node]:
            # reduce in-degree
            current_in[v] -= 1
            # update level: when node removed, if it reduces neighbor's in-degree to 0, set level[v] = max(level[v], level[node]+1)
            if levels[v] < levels[node] + 1:
                # but only meaningful when becomes zero later; still set now so max works when zero occurs
                levels[v] = max(levels[v], levels[node] + 1)
            if current_in[v] == 0:
                heapq.heappush(heap, [-importance[v], v])
                frontier_sum += importance[v]
        # track dp_len for longest path from sources: for each neighbor, dp_len[neighbor] = max(dp_len[neighbor], dp_len[node]+1)
        for v in adj[node]:
            if dp_len[v] < dp_len[node] + 1:
                dp_len[v] = dp_len[node] + 1

    if processed < n:
        return None

    # longest path length is max dp_len over all nodes
    longest_path_length = max(dp_len) if n > 0 else 0

    # levels are already set, but ensure nodes with initial in-degree 0 are level 0
    # (they are initialized to 0). Level widths
    max_level = max(levels) if levels else 0
    level_widths = [0] * (max_level + 1)
    for lv in levels:
        level_widths[lv] += 1

    # topo_positions: for each node id i, index j where order[j] == i
    topo_positions = [0] * n
    for idx, node in enumerate(order):
        topo_positions[node] = idx

    # cumulative_importance_prefix: prefix sums along order
    cum = []
    s = 0
    for node in order:
        s += importance[node]
        cum.append(s)

    # latest_levels: need longest distance to any sink for each node (in edges)
    # compute longest distance to sink using dp on reverse topological order
    # First compute list of nodes in topological order (we have 'order'), process reversed
    longest_to_sink = [0] * n
    for node in reversed(order):
        best = 0
        for v in adj[node]:
            if longest_to_sink[v] + 1 > best:
                best = longest_to_sink[v] + 1
        longest_to_sink[node] = best
    makespan = longest_path_length
    latest_levels = [makespan - longest_to_sink[i] for i in range(n)]
    slack = [latest_levels[i] - levels[i] for i in range(n)]

    statistics = {
        'is_dag': True,
        'processed_count': processed,
        'max_parallel_frontier': max_parallel_frontier,
        'priority_score': priority_score,
        'levels': levels,
        'longest_path_length': longest_path_length,
        'num_sources': num_sources,
        'num_sinks': num_sinks,
        'in_degrees': in_deg,
        'out_degrees': out_deg,
        'level_widths': level_widths,
        'latest_levels': latest_levels,
        'slack': slack,
        'topo_positions': topo_positions,
        'cumulative_importance_prefix': cum,
        'frontier_max_importance_sum': frontier_max_importance_sum,
        'tie_breaks_count': tie_breaks
    }

    return {'order': order, 'statistics': statistics}