def optimize_route_planning(
    graph_data: List[List[Union[int, float]]],
    queries: List[List[Union[str, int, float, None]]]
) -> List[Union[float, bool]]:
    # Validation helpers
    def invalid():
        return []
    def is_valid_node(x):
        return isinstance(x, int) and x >= 1
    def is_valid_weight(w):
        return (isinstance(w, (int, float)) and not (isinstance(w, bool)) and
                math.isfinite(w) and w >= 0)
    def is_valid_arg_for_query(qtype, arg):
        if qtype == "shortest_path":
            return arg is None or (isinstance(arg, (int, float)) and not isinstance(arg, bool) and math.isfinite(arg) and arg >= 0)
        if qtype in ("add_edge", "update_weight", "update_capacity"):
            return (isinstance(arg, (int, float)) and not isinstance(arg, bool) and math.isfinite(arg) and arg >= 0)
        # remove_edge and connectivity_check: arg ignored, allow None or numeric
        return arg is None or isinstance(arg, (int, float))
    # Validate graph_data and queries are lists
    if not isinstance(graph_data, list) or not isinstance(queries, list):
        return invalid()
    # Early empty both
    if graph_data == [] and queries == []:
        return []
    # Edge storage: canonical unordered pair key (min,max) -> {weight, capacity}
    edges = {}
    adj = defaultdict(dict)  # adj[u][v] = weight (canonical)
    # Validate and load initial edges
    for item in graph_data:
        if not (isinstance(item, list) and len(item) == 3):
            return invalid()
        u, v, w = item
        if not is_valid_node(u) or not is_valid_node(v):
            return invalid()
        if u == v:
            return invalid()
        if not is_valid_weight(w):
            return invalid()
        a, b = (u, v) if u < v else (v, u)
        key = (a, b)
        if key in edges:
            # merge: weight = min
            if w < edges[key]['weight']:
                edges[key]['weight'] = float(w)
                adj[a][b] = float(w)
                adj[b][a] = float(w)
        else:
            edges[key] = {'weight': float(w), 'capacity': 0.0}
            adj[a][b] = float(w)
            adj[b][a] = float(w)
    results = []
    # Process queries
    for q in queries:
        if not (isinstance(q, list) and len(q) == 4):
            return invalid()
        qtype, u, v, arg = q
        if not (isinstance(qtype, str) and qtype in ("shortest_path", "connectivity_check", "add_edge", "remove_edge", "update_weight", "update_capacity")):
            return invalid()
        if not is_valid_node(u) or not is_valid_node(v):
            return invalid()
        if qtype == "shortest_path" and arg is None:
            demand = 0.0
        else:
            demand = arg
        if not is_valid_arg_for_query(qtype, arg):
            return invalid()
        # Special u == v cases
        if u == v:
            if qtype == "shortest_path":
                results.append(0.0)
                continue
            if qtype == "connectivity_check":
                results.append(True)
                continue
            # For updates involving self-loop edge, invalid
            if qtype in ("add_edge", "update_weight", "update_capacity"):
                return invalid()
            # remove_edge on self-loop is a no-op (but self-loops shouldn't exist)
            if qtype == "remove_edge":
                continue
        a, b = (u, v) if u < v else (v, u)
        key = (a, b)
        # Handle operations
        if qtype == "add_edge":
            w = float(arg)
            if a == b:
                return invalid()
            if key in edges:
                # merge: weight = min(existing, new), capacity unchanged
                if w < edges[key]['weight']:
                    edges[key]['weight'] = w
                    adj[a][b] = w
                    adj[b][a] = w
            else:
                edges[key] = {'weight': w, 'capacity': 0.0}
                adj[a][b] = w
                adj[b][a] = w
            continue
        if qtype == "remove_edge":
            if key in edges:
                del edges[key]
                # remove from adj
                if b in adj[a]:
                    del adj[a][b]
                if a in adj[b]:
                    del adj[b][a]
                # clean empty dicts optional
                if not adj[a]:
                    adj.pop(a, None)
                if not adj[b]:
                    adj.pop(b, None)
            # no-op if non-existent
            continue
        if qtype == "update_weight":
            if key not in edges:
                return invalid()
            if a == b:
                return invalid()
            w = float(arg)
            edges[key]['weight'] = w
            adj[a][b] = w
            adj[b][a] = w
            continue
        if qtype == "update_capacity":
            if key not in edges:
                return invalid()
            if a == b:
                return invalid()
            c = float(arg)
            edges[key]['capacity'] = c
            continue
        if qtype == "connectivity_check":
            # BFS/DFS ignoring capacities
            visited = set()
            stack = [u]
            visited.add(u)
            found = False
            while stack:
                node = stack.pop()
                if node == v:
                    found = True
                    break
                # neighbors in sorted order
                neighs = sorted(adj.get(node, {}).keys())
                for nb in neighs:
                    if nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            results.append(found)
            continue
        if qtype == "shortest_path":
            # demand normalized
            if demand is None:
                demand = 0.0
            demand = float(demand)
            # Dijkstra with tie-breaking: when pushing neighbors, iterate neighbors sorted by node id
            # Also edges traversable only if capacity >= demand
            # If no path, return -1.0
            # If start==end handled earlier
            # Build neighbor list filtered by capacity
            dist = {}
            prev = {}
            # Use heap of (distance, next_node_sequence for tie? not needed if we ensure neighbor ordering and stable pushes)
            # To ensure determinism, we push (distance, node) and when distances equal, heap pops lower node id first.
            heap = []
            heapq.heappush(heap, (0.0, u))
            dist[u] = 0.0
            visited = set()
            while heap:
                d, node = heapq.heappop(heap)
                if node in visited:
                    continue
                visited.add(node)
                if node == v:
                    break
                # iterate neighbors sorted increasing node id
                for nb in sorted(adj.get(node, {}).keys()):
                    # check capacity on edge (min,node pair)
                    x, y = (node, nb) if node < nb else (nb, node)
                    ekey = (x, y)
                    ed = edges.get(ekey)
                    if ed is None:
                        continue
                    if ed['capacity'] < demand:
                        continue
                    w = ed['weight']
                    nd = d + w
                    prev_dist = dist.get(nb)
                    # deterministic tie-breaking: accept strictly smaller distance or equal distance but previous path leads to lexicographically smaller next node?
                    # Simpler: when nd < prev or (nd == prev and node < prev_nb_from_source?), but prev neighbor tracking complex.
                    # However required tie-breaking: when multiple shortest paths share same total cost, choose path whose next node ID is smallest.
                    # Achieve by Dijkstra visiting neighbors in sorted order and using heap ordering (distance, node id).
                    if (prev_dist is None) or (nd < prev_dist) or (abs(nd - prev_dist) < 1e-12 and node < prev.get(nb, (float('inf'),))[0] if isinstance(prev.get(nb), tuple) else nd < prev_dist):
                        dist[nb] = nd
                        # store predecessor as node to reconstruct next-hop if needed; store predecessor node
                        prev[nb] = node
                        heapq.heappush(heap, (nd, nb))
            if v not in dist:
                results.append(-1.0)
            else:
                results.append(float(dist[v]))
            continue
        # unreachable
        return invalid()
    return results