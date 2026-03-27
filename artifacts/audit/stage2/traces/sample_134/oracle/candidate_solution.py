import heapq

def evaluate_traffic_impact(edges, node_signal_delay, base_blocked, queries):
    """
    edges: list of dicts:
      {"from": int, "to": int, "lanes": [{"mode": str, "travel_time": int, "capacity": int}]}
    node_signal_delay: dict {node_id: delay_int} (keys may be str or int; normalized to int)
    base_blocked: dict {node_id: list_of_blocked_modes} (keys may be str or int; normalized to int)
    queries: list of dicts, each:
      {
        "src": int,
        "dst": int,
        "block": [{"node": int, "mode": str}],
        "unblock": [{"node": int, "mode": str}],
        "delay_updates": [{"node": int, "delta": int}],
        "reset": bool,
        "k": int
      }
    Returns: list of dicts, each:
      {
        "query": {"src": int, "dst": int},
        "alternative_routes": list_of_routes,
        "impact": str  # "disconnected" or "cost=<c>; max_delay=<d>; modes=<m>"
      }
    """

    # ---- Normalize inputs ----
    adj = {}  # u -> list of {"to": v, "lanes": [...]}
    for e in edges:
        u = int(e["from"]); v = int(e["to"])
        adj.setdefault(u, []).append({"to": v, "lanes": list(e["lanes"])})
    for e in edges:
        v = int(e["to"])
        adj.setdefault(v, [])

    delay_default = {}
    for k_node, val in node_signal_delay.items():
        delay_default[int(k_node)] = int(val)
    for node in adj.keys():
        delay_default.setdefault(node, 0)

    base_blocked_norm = {}
    for k_node, modes in base_blocked.items():
        base_blocked_norm[int(k_node)] = set(modes)

    # Working state (mutable across queries; reset if query.reset True)
    current_blocked = {n: set(m) for n, m in base_blocked_norm.items()}
    current_delay = dict(delay_default)

    # ---- Helpers ----
    def allowed_edge_cost_and_mode(u, v, lanes, blocked_map):
        """
        Among lanes on edge (u->v), pick the usable lane with:
        - minimum travel_time
        - tie-break by lexicographically smaller mode
        A lane is usable iff capacity>=1 and its mode is not blocked at u or v.
        Returns (time, mode) or (None, None) if no usable lane.
        """
        best_time = None
        best_mode = None
        blocked_u = blocked_map.get(u, set())
        blocked_v = blocked_map.get(v, set())
        for lane in lanes or []:
            mode = lane["mode"]
            cap = int(lane.get("capacity", 0))
            if cap < 1:
                continue
            if mode in blocked_u or mode in blocked_v:
                continue
            t = int(lane["travel_time"])
            if (best_time is None or t < best_time or
                (t == best_time and (best_mode is None or mode < best_mode))):
                best_time = t
                best_mode = mode
        if best_time is None:
            return None, None
        return best_time, best_mode

    def dijkstra_shortest_path(src, dst, blocked_map, node_delay_map, forbidden_nodes=None):
        """
        Dijkstra with custom tie-breakers:
        - primary: total cost (edge time + interior node delays)
        - secondary: fewer hops
        - tertiary: lexicographically smaller path
        forbidden_nodes (interior only) are disallowed (but src/dst may still be visited).
        Returns (path_list, total_cost_including_interior_delays) or (None, None).
        """
        if forbidden_nodes is None:
            forbidden_nodes = set()

        def forbidden(n):
            # Forbid only interior nodes; never forbid src/dst
            return (n in forbidden_nodes) and (n != src) and (n != dst)

        if src not in adj or dst not in adj or forbidden(src) or forbidden(dst):
            return None, None

        # (cost, hops, path_list, node)
        heap = [(0, 0, [src], src)]
        # best_state[node] = (cost, hops, path_list)
        best_state = {}

        while heap:
            cost, hops, path, u = heapq.heappop(heap)

            prev = best_state.get(u)
            if prev:
                pc, ph, pp = prev
                if (cost > pc) or (cost == pc and (hops > ph or (hops == ph and path >= pp))):
                    continue
            best_state[u] = (cost, hops, path)

            if u == dst:
                return path, cost

            for e in adj.get(u, []):
                v = e["to"]
                if forbidden(v):
                    continue
                t_cost, _mode = allowed_edge_cost_and_mode(u, v, e["lanes"], blocked_map)
                if t_cost is None:
                    continue
                # Add interior delay for v (not for dst)
                add_delay = node_delay_map.get(v, 0) if v != dst else 0
                new_cost = cost + t_cost + add_delay
                new_path = path + [v]
                new_hops = hops + 1

                prev = best_state.get(v)
                should_push = False
                if not prev:
                    should_push = True
                else:
                    pc, ph, pp = prev
                    if (new_cost < pc) or (new_cost == pc and (new_hops < ph or (new_hops == ph and new_path < pp))):
                        should_push = True
                if should_push:
                    heapq.heappush(heap, (new_cost, new_hops, new_path, v))

        return None, None

    def modes_and_max_delay_for_path(path, blocked_map, node_delay_map):
        """
        Single pass to compute:
        - distinct modes used along path (by picking best usable lane per edge)
        - max interior node delay
        """
        if not path or len(path) < 2:
            return 0, 0
        modes = set()
        max_d = 0
        for i in range(len(path) - 1):
            a = path[i]
            b = path[i + 1]
            # modes
            lanes = None
            for e in adj.get(a, []):
                if e["to"] == b:
                    lanes = e["lanes"]; break
            _, mode = allowed_edge_cost_and_mode(a, b, lanes, blocked_map)
            if mode is not None:
                modes.add(mode)
            # interior delay tracking
            if i != 0 and i != len(path) - 1:  # this 'a' is interior, but we need delay for node at index i
                max_d = max(max_d, int(node_delay_map.get(a, 0)))
        # also consider interior delay at the node before dst
        if len(path) > 2:
            penultimate = path[-2]
            max_d = max(max_d, int(node_delay_map.get(penultimate, 0)))
        return len(modes), max_d

    def find_k_node_disjoint(src, dst, k, blocked_map, node_delay_map):
        """
        Repeatedly find shortest path; after each path, forbid its interior nodes.
        Returns up to k node-disjoint paths (may be fewer if graph cannot supply more).
        """
        paths = []
        forbidden = set()
        k = max(1, int(k))
        for _ in range(k):
            p, c = dijkstra_shortest_path(src, dst, blocked_map, node_delay_map, forbidden_nodes=forbidden)
            if not p:
                break
            paths.append((p, c))
            for node in p[1:-1]:
                forbidden.add(node)
        return paths

    results = []

    # ---- Process queries ----
    for q in queries:
        src = int(q["src"])
        dst = int(q["dst"])
        reset = bool(q.get("reset", False))
        k = int(q.get("k", 1))
        if k < 1:
            k = 1

        if reset:
            current_blocked = {n: set(m) for n, m in base_blocked_norm.items()}
            current_delay = dict(delay_default)

        # ensure all nodes present
        for node in adj.keys():
            current_blocked.setdefault(node, set())
            current_delay.setdefault(node, 0)

        # apply blocks/unblocks
        for op in q.get("block", []):
            node = int(op["node"]); mode = op["mode"]
            current_blocked.setdefault(node, set()).add(mode)
        for op in q.get("unblock", []):
            node = int(op["node"]); mode = op["mode"]
            if node in current_blocked and mode in current_blocked[node]:
                current_blocked[node].remove(mode)

        # apply delay updates (clamped at 0)
        for upd in q.get("delay_updates", []):
            node = int(upd["node"]); delta = int(upd["delta"])
            current_delay[node] = max(0, int(current_delay.get(node, 0)) + delta)

        # find up to k node-disjoint paths
        found = find_k_node_disjoint(src, dst, k, current_blocked, current_delay)

        if not found:
            results.append({
                "query": {"src": src, "dst": dst},
                "alternative_routes": [],
                "impact": "disconnected"
            })
            continue

        # primary result is the first path; cost already includes interior delays
        primary_path, primary_cost = found[0]
        modes_count, max_delay = modes_and_max_delay_for_path(primary_path, current_blocked, current_delay)

        results.append({
            "query": {"src": src, "dst": dst},
            "alternative_routes": [p for p, _ in found],
            "impact": f"cost={primary_cost}; max_delay={max_delay}; modes={modes_count}"
        })

    return results