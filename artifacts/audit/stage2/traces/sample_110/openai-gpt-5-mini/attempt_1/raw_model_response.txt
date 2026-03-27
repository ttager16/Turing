def optimize_resource_allocation(graph: dict, forbidden_patterns: list) -> list:
    # Helper: check node attrs against a constraint dict (all key equality)
    def node_matches_constraints(node_attrs, constraint):
        for k, v in constraint.items():
            if k not in node_attrs or node_attrs[k] != v:
                return False
        return True

    # Helper: check edge attrs against constraint (supports numeric range dicts)
    def edge_matches_constraints(edge_attrs, constraint):
        for k, v in constraint.items():
            if k not in edge_attrs:
                return False
            val = edge_attrs[k]
            if isinstance(v, dict):
                mn = v.get("min", float("-inf"))
                mx = v.get("max", float("inf"))
                try:
                    if not (mn <= val <= mx):
                        return False
                except Exception:
                    return False
            else:
                if val != v:
                    return False
        return True

    if not graph:
        return []

    # Build forbidden node and forbidden edge sets
    forbidden_nodes = set()
    forbidden_edges = set()  # store as tuple (u,v) with u<=v

    # Preprocess node attribute mapping: nodes might not have explicit attrs in graph top-level;
    # assume node attributes appear only in adjacency entries; we consider node-level attrs only via adjacency attributes if present.
    node_attrs_map = {}
    for u_str, adj in graph.items():
        u = int(u_str) if isinstance(u_str, str) else u_str
        # collect attrs from any adjacency that contains node-like keys (e.g., maintenance_mode)
        for nei, attrs in adj:
            if isinstance(attrs, dict):
                # assume node attrs are same across edges if present
                for k in ["maintenance_mode"]:
                    if k in attrs:
                        node_attrs_map.setdefault(u, {})[k] = attrs[k]

    # Evaluate forbidden patterns
    for pattern in forbidden_patterns:
        node_constraints = pattern.get("node_constraints", [])
        edge_constraints = pattern.get("edge_constraints", [])
        # mark nodes
        if node_constraints:
            for u in graph.keys():
                u_id = int(u) if isinstance(u, str) else u
                attrs = node_attrs_map.get(u_id, {})
                for c in node_constraints:
                    if node_matches_constraints(attrs, c):
                        forbidden_nodes.add(u_id)
                        break
        # mark edges: iterate all edges in graph
        if edge_constraints:
            for u_str, adj in graph.items():
                u = int(u_str) if isinstance(u_str, str) else u_str
                for nei, attrs in adj:
                    v = int(nei) if isinstance(nei, str) else nei
                    for c in edge_constraints:
                        if edge_matches_constraints(attrs or {}, c):
                            a, b = (u, v) if u <= v else (v, u)
                            forbidden_edges.add((a, b))
                            break

    # Build list of allowed edges with cost
    edges = {}
    for u_str, adj in graph.items():
        u = int(u_str) if isinstance(u_str, str) else u_str
        for nei, attrs in adj:
            v = int(nei) if isinstance(nei, str) else nei
            a, b = (u, v) if u <= v else (v, u)
            if u in forbidden_nodes or v in forbidden_nodes:
                continue
            if (a, b) in forbidden_edges:
                continue
            # compute cost
            tc = attrs.get("time_cost", {}) if attrs else {}
            day = tc.get("day")
            night = tc.get("night")
            if day is None and night is None:
                # if no time info, skip edge (cannot cost)
                continue
            if day is None:
                cost = float(night)
            elif night is None:
                cost = float(day)
            else:
                cost = (float(day) + float(night)) / 2.0
            # keep minimal cost if multiple parallel edges
            prev = edges.get((a, b))
            if prev is None or cost < prev:
                edges[(a, b)] = cost

    if not edges:
        return []

    # Create adjacency for remaining graph (undirected simple graph)
    adj = {}
    for (u, v), cost in edges.items():
        adj.setdefault(u, []).append((v, cost))
        adj.setdefault(v, []).append((u, cost))

    # Greedy algorithm to find maximal matching while aiming to minimize total cost:
    # Sort all edges by cost asc, then by node ids lexicographically.
    edge_list = []
    for (u, v), cost in edges.items():
        edge_list.append((cost, min(u, v), max(u, v)))
    edge_list.sort(key=lambda x: (x[0], x[1], x[2]))

    matched = set()
    result = []
    for cost, u, v in edge_list:
        if u in matched or v in matched:
            continue
        matched.add(u); matched.add(v)
        result.append([u, v])

    # Ensure maximality: simple greedy by increasing cost yields maximal matching for sorted edges.
    # Sort pairs lexicographically as tie-breaker for deterministic output
    result.sort(key=lambda p: (min(p[0], p[1]), max(p[0], p[1])))
    return result

if __name__ == "__main__":
    def main():
        graph = {
          "1": [[2, {"capacity_peak": 50, "capacity_offpeak": 60, "time_cost": {"day": 5, "night": 3}, "layer": 0}]],
          "2": [[1, {"capacity_peak": 50, "capacity_offpeak": 60, "time_cost": {"day": 5, "night": 3}, "layer": 0}]],
          "3": [[4, {"capacity_peak": 100, "capacity_offpeak": 120, "time_cost": {"day": 6, "night": 4}, "layer": 1, "pollution_factor": 1.8}]],
          "4": [[3, {"capacity_peak": 100, "capacity_offpeak": 120, "time_cost": {"day": 6, "night": 4}, "layer": 1, "pollution_factor": 1.8}]],
          "5": [[6, {"capacity_peak": 40, "capacity_offpeak": 60, "time_cost": {"day": 2, "night": 1}, "layer": 2, "pollution_factor": 0.7}]],
          "6": [[5, {"capacity_peak": 40, "capacity_offpeak": 60, "time_cost": {"day": 2, "night": 1}, "layer": 2, "pollution_factor": 0.7}]]
        }
        forbidden_patterns = [
            {
              "substructure_id": "env_filter",
              "edge_constraints": [{"pollution_factor": {"min": 1.0, "max": 2.0}}]
            }
        ]
        print(optimize_resource_allocation(graph, forbidden_patterns))
    main()