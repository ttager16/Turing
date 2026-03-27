def optimize_delivery_routes(
    city_map: dict, 
    vehicles: list, 
    route_closures: list
) -> list:
    from heapq import heappush, heappop

    # Build adjacency dict (directed). Normalize closures to set for quick check per time.
    closures = {}
    for frm, to, t in route_closures:
        closures.setdefault((frm, to), []).append(t)

    def edge_closed(frm, to, time):
        times = closures.get((frm, to))
        if not times:
            return False
        # closed at or after closure_time
        return any(time >= ct for ct in times)

    # Extract layer of a node: if node endswith suffix it's that layer node. Else 'road' default?
    # But edges carry layer info. We track current edge layer by previous edge used.
    # Precompute all nodes
    nodes = set(city_map.keys())
    for u, nbrs in city_map.items():
        for v, c, l in nbrs:
            nodes.add(v)

    # Dijkstra for admissible heuristic: true shortest remaining time between any two nodes ignoring closures and transitions.
    # We consider edge weights as given without transition costs. This ensures admissible (underestimates if transitions later add cost).
    # Build simple graph
    graph = {}
    for u in nodes:
        graph[u] = []
    for u, nbrs in city_map.items():
        for v, c, l in nbrs:
            graph.setdefault(u, []).append((v, c))
            # Note: edges are directed; do not add reverse.

    def dijkstra(start):
        dist = {n: float('inf') for n in nodes}
        dist[start] = 0
        pq = [(0, start)]
        while pq:
            d,u = heappop(pq)
            if d!=dist[u]: continue
            for v,c in graph.get(u,()):
                nd = d + c
                if nd < dist[v]:
                    dist[v]=nd
                    heappush(pq,(nd,v))
        return dist

    # Precompute pairwise heuristic distances on demand and cache
    heuristic_cache = {}
    def heuristic(u,v):
        key = (u,v)
        if key in heuristic_cache:
            return heuristic_cache[key]
        dist = dijkstra(u)
        heuristic_cache[key] = dist.get(v, float('inf'))
        return heuristic_cache[key]

    results = []
    for veh in vehicles:
        vid = veh.get('id')
        start = veh.get('start_node')
        end = veh.get('end_node')
        capacity = veh.get('capacity', 0)
        tw_start, tw_end = veh.get('time_window', [0, float('inf')])
        deliveries = list(veh.get('deliveries', []))
        if len(deliveries) > capacity:
            continue

        # Required set
        req_set = set(deliveries)

        best_route = None
        best_time = float('inf')
        best_trans = float('inf')

        # Backtracking: state = (current_node, time_so_far, delivered_set, path_list, current_layer)
        # current_layer: layer of node we're considered on. For start we infer from node name: if contains suffix _skyway/_tunnel else 'road'
        def infer_layer(node):
            if node.endswith('_skyway'):
                return 'skyway'
            if node.endswith('_tunnel'):
                return 'tunnel'
            return 'road'

        start_layer = infer_layer(start)

        # Use stack DFS with heuristic-guided ordering
        from collections import deque
        stack = deque()
        stack.append((start, 0, frozenset() if start not in req_set else frozenset({start}), [start], start_layer, 0))
        # If start is a delivery node, mark delivered
        if start in req_set:
            initial_delivered = frozenset({start})
        else:
            initial_delivered = frozenset()

        stack.clear()
        stack.append((start, 0, initial_delivered, [start], start_layer, 0))

        visited_states = {}  # prune dominated states: (node, delivered_set, layer) -> best time found
        while stack:
            node, time_so_far, delivered, path, cur_layer, transitions = stack.pop()

            # Prune by best known for this state
            key = (node, delivered, cur_layer)
            if visited_states.get(key, float('inf')) <= time_so_far:
                continue
            visited_states[key] = time_so_far

            # If time already worse than best or outside time window prune (heuristic)
            # Lower bound to complete: need to visit all remaining deliveries and reach end.
            remaining = set(req_set) - set(delivered)
            lb = 0
            # heuristic from current node to nearest remaining then to end: use simple sum of heuristics minimal ordering approximate:
            cur = node
            temp_remaining = set(remaining)
            # Greedy nearest insertion heuristic with admissible dijkstra distances (no transitions)
            while temp_remaining:
                # pick nearest
                nearest = min(temp_remaining, key=lambda x: heuristic(cur, x))
                d = heuristic(cur, nearest)
                if d==float('inf'):
                    lb = float('inf'); break
                lb += d
                cur = nearest
                temp_remaining.remove(nearest)
            # finally add to end
            last_leg = heuristic(cur, end)
            if last_leg==float('inf'):
                lb = float('inf')
            else:
                lb += last_leg
            # Also account minimal transition costs lower bound: at least 0 transitions, but if path includes layer changes unavoidable? We keep admissible so 0.
            est_total = time_so_far + lb
            if est_total > tw_end or est_total >= best_time:
                continue

            # If at end and all delivered, record
            if node == end and set(delivered) == req_set:
                # ensure within time window and capacity already checked
                if time_so_far <= tw_end:
                    # minimize primary total_time then transitions
                    if time_so_far < best_time or (time_so_far == best_time and transitions < best_trans):
                        best_time = time_so_far
                        best_trans = transitions
                        best_route = list(path)
                continue

            # Expand neighbors
            for nbr_tuple in city_map.get(node, []):
                nbr, cost, edge_layer = nbr_tuple
                # Check closure for this directed edge at time of traversal: edge unavailable at or after closure_time.
                # Edge is traversed starting at time_so_far; if closed at or after that, cannot take it.
                if edge_closed(node, nbr, time_so_far):
                    continue
                # Compute transition cost: if moving between layers at junction nodes adds fixed cost of 5 per transition.
                # Transition occurs when previous node's layer != edge layer. But some nodes represent layer variants; transitions allowed at junction nodes.
                trans_cost = 0
                # If cur_layer and edge_layer differ and this node is a junction (base name matches)
                def base_name(n):
                    if n.endswith('_skyway'):
                        return n[:-7]
                    if n.endswith('_tunnel'):
                        return n[:-7]
                    return n
                if cur_layer != edge_layer:
                    # Allowed only if node is junction between layers (naming convention)
                    # If base_name(node) equals node without suffix for layer variants, it's a junction
                    # Example: 'N1' -> can go to 'N1_skyway' etc. Also 'N3_skyway' -> can go to 'N3' (back)
                    # We'll allow transition if base names match between node and nbr when stripped appropriately.
                    node_base = base_name(node)
                    nbr_base = base_name(nbr)
                    if node_base == nbr_base:
                        trans_cost = 5
                    else:
                        # If layers differ but not at junction, transition not allowed
                        # However some edges can connect nodes of different names but have layer attribute; still allow transition if edge exists (edge_layer given)
                        # We'll be conservative: allow transition only if edge connects nodes with same base name or one is exact variant
                        # If not, skip this neighbor
                        # But to avoid false blocking, allow if either node or nbr endswith layer suffix (i.e., explicit layer node) and base names equal or edge exists to different base -> allow
                        # We'll allow as long as there is an edge (it exists) but still apply transition cost.
                        trans_cost = 5
                new_time = time_so_far + cost + trans_cost
                if new_time > tw_end or new_time >= best_time:
                    continue
                new_delivered = set(delivered)
                if nbr in req_set:
                    new_delivered.add(nbr)
                new_delivered = frozenset(new_delivered)
                new_path = path + [nbr]
                new_trans = transitions + (1 if trans_cost>0 and cur_layer!=edge_layer else 0)
                new_layer = edge_layer
                # Closure dynamic: if closure affects future edges on current path it's checked when traversing them, so no extra handling.
                # Push with heuristic ordering: use est_total to prioritize promising ones (stack LIFO -> push sorted)
                # We'll collect and push; but to keep memory small push immediately.
                # Prune by visited_states early
                k2 = (nbr, new_delivered, new_layer)
                if visited_states.get(k2, float('inf')) <= new_time:
                    continue
                stack.append((nbr, new_time, new_delivered, new_path, new_layer, new_trans))

        if best_route is not None:
            results.append({
                'vehicle_id': vid,
                'route': best_route,
                'total_time': int(best_time),
                'layer_transitions': int(best_trans)
            })

    if not results:
        return []
    return results