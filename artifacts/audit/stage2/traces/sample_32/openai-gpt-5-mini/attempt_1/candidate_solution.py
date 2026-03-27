def optimize_delivery_routes(
    city_map: Dict[str, List[List[Any]]], 
    vehicles: List[Dict[str, Any]], 
    route_closures: List[List[Any]]
) -> List[Dict[str, Any]]:
    # Build adjacency dict (directed) and closure lookup
    adj = {}
    for u, edges in city_map.items():
        adj.setdefault(u, [])
        for v, cost, layer in edges:
            adj[u].append((v, int(cost), layer))
    closures = {}  # key (u,v) -> closure_time
    for c in route_closures:
        if len(c) >= 3:
            closures[(c[0], c[1])] = c[2]

    # Precompute nodes list
    nodes = set(adj.keys())
    for u in adj:
        for v, _, _ in adj[u]:
            nodes.add(v)
    nodes = list(nodes)

    # Dijkstra for admissible heuristic: shortest time ignoring closures and transitions
    # We'll compute shortest path distances between all nodes on base graph (edge costs only)
    def dijkstra(source: str) -> Dict[str, int]:
        dist = {n: float('inf') for n in nodes}
        dist[source] = 0
        pq = [(0, source)]
        while pq:
            d,u = heapq.heappop(pq)
            if d!=dist[u]: continue
            for v,c,_ in adj.get(u, []):
                nd = d + c
                if nd < dist.get(v, float('inf')):
                    dist[v]=nd
                    heapq.heappush(pq,(nd,v))
        return dist
    # Precompute dists from every node used as heuristic on demand (cache)
    dcache: Dict[str, Dict[str,int]] = {}
    def get_dist(u: str, v: str) -> int:
        if u not in dcache:
            dcache[u] = dijkstra(u)
        d = dcache[u].get(v, float('inf'))
        return d if d!=float('inf') else 10**9

    results = []
    for veh in vehicles:
        vid = veh.get('id')
        start = veh.get('start_node')
        end = veh.get('end_node')
        capacity = int(veh.get('capacity', 0))
        tw_start, tw_end = veh.get('time_window', [0, 10**9])
        deliveries = list(veh.get('deliveries', []))
        if len(deliveries) > capacity:
            continue  # impossible
        # Required visit set
        req_set = set(deliveries)

        # Best solution trackers
        best = {'time': float('inf'), 'transitions': float('inf'), 'route': None}

        # Backtracking state: current node, visited deliveries set, time elapsed, current layer (None if unknown), transitions count, path list
        # Start layer is layer of start node name if includes suffix, otherwise None. But we determine layer by outgoing edges when moving.
        # We'll represent current layer as string or None.

        # Helper to determine layer of an edge between u->v
        def neighbors(u: str):
            return adj.get(u, [])

        # Check closure for edge at time t (edge unavailable at or after closure_time)
        def is_edge_closed(u: str, v: str, t: int) -> bool:
            ct = closures.get((u,v))
            if ct is None:
                return False
            # if edge unavailable at or after closure_time -> closed when t >= ct
            return t >= ct

        # Admissible heuristic from node u to cover remaining required nodes and finish:
        # Minimal remaining cost = minimal spanning of visiting remaining nodes and end: we approximate by sum of mins: from u to nearest required or end, plus MST lower bound omitted for simplicity but admissible using distances: take min distance to cover each remaining in sequence via minimum matching is complex; simpler admissible heuristic: distance to nearest remaining + sum of zero for others + distance from that remaining to end via precomputed dists. To be safe admissible, use distance from current to nearest of (remaining U {end}).
        def heuristic(u: str, remaining: set) -> int:
            targets = list(remaining) + [end]
            bestd = 10**9
            for t in targets:
                d = get_dist(u, t)
                if d < bestd: bestd = d
            return bestd

        # DFS with pruning
        visited_states = {}  # memoization: (node, frozenset(remaining), layer) -> best_time_seen
        # We need current layer tracked to count transitions; but layer can be None for start.
        def dfs(u: str, rem: set, time_elapsed: int, layer: Any, transitions: int, path: List[str]):
            # Prune time window
            if time_elapsed > tw_end:
                return
            # Heuristic lower bound estimate
            h = heuristic(u, rem)
            est_total = time_elapsed + h
            # Add transition costs minimal possible? Heuristic ignores transitions so admissible.
            if est_total > best['time']:
                return
            key = (u, tuple(sorted(rem)), layer)
            prev_best_time = visited_states.get(key)
            if prev_best_time is not None and prev_best_time <= time_elapsed and transitions >= 0:
                return
            visited_states[key] = time_elapsed

            # If at a delivery node, mark visited
            new_rem = set(rem)
            if u in new_rem:
                new_rem.remove(u)

            # If finished (no remaining and at end)
            if not new_rem and u == end:
                # update best comparing time then transitions
                if time_elapsed < best['time'] or (time_elapsed == best['time'] and transitions < best['transitions']):
                    best['time'] = time_elapsed
                    best['transitions'] = transitions
                    best['route'] = path.copy()
                return

            # Explore neighbors
            for v, cost, edge_layer in neighbors(u):
                # Closure check: if edge closed at time when starting traversal (or at arrival?) Problem says unavailable at or after closure_time, so if starting at time_elapsed and time_elapsed >= ct then can't use.
                if is_edge_closed(u, v, time_elapsed):
                    continue
                # compute layer transition cost if layer changes between previous layer and edge_layer
                add = cost
                add_trans = 0
                next_layer = edge_layer
                if layer is not None and layer != next_layer:
                    add += 5
                    add_trans = 1
                # Also transitions when moving between variants of same base? The node naming uses layer variants; transitions counted when moving between layers via junction nodes; our approach counts when edge layer differs.
                new_time = time_elapsed + add
                # prune by time window and best
                if new_time > tw_end:
                    continue
                # heuristic lower bound from v
                h2 = heuristic(v, new_rem)
                if new_time + h2 > best['time']:
                    continue
                # avoid cycles: simple depth limit by nodes*3
                if len(path) > len(nodes)*3:
                    continue
                path.append(v)
                dfs(v, new_rem, new_time, next_layer, transitions + add_trans, path)
                path.pop()

        # Start DFS
        # initial layer unknown; but if start node name contains suffix, we could infer layer: e.g., 'N1_skyway'
        start_layer = None
        if start.endswith('_skyway'):
            start_layer = 'skyway'
        elif start.endswith('_tunnel'):
            start_layer = 'tunnel'
        elif start.endswith('_road'):
            start_layer = 'road'
        dfs(start, req_set, max(tw_start, 0), start_layer, 0, [start])

        if best['route'] is not None:
            results.append({
                'vehicle_id': vid,
                'route': best['route'],
                'total_time': int(best['time']),
                'layer_transitions': int(best['transitions'])
            })
    if not results:
        return []
    return results