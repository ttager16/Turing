def optimize_resource_allocation(graph: dict, forbidden_patterns: list) -> list:
    # Helper to check node constraints: node_attrs is dict
    def node_matches_constraints(node_attrs, constraints):
        for cond in constraints:
            match = True
            for k, v in cond.items():
                if k not in node_attrs:
                    match = False
                    break
                av = node_attrs[k]
                # if v is dict with min/max
                if isinstance(v, dict):
                    mn = v.get("min", float("-inf"))
                    mx = v.get("max", float("inf"))
                    try:
                        if not (mn <= av <= mx):
                            match = False
                            break
                    except Exception:
                        match = False
                        break
                else:
                    if av != v:
                        match = False
                        break
            if match:
                return True
        return False

    # Helper to check edge constraints: edge_attrs is dict
    def edge_matches_constraints(edge_attrs, constraints):
        for cond in constraints:
            match = True
            for k, v in cond.items():
                if k not in edge_attrs:
                    match = False
                    break
                av = edge_attrs[k]
                if isinstance(v, dict):
                    mn = v.get("min", float("-inf"))
                    mx = v.get("max", float("inf"))
                    try:
                        if not (mn <= av <= mx):
                            match = False
                            break
                    except Exception:
                        match = False
                        break
                else:
                    if av != v:
                        match = False
                        break
            if match:
                return True
        return False

    if not graph:
        return []

    # Build node attribute lookup: graph adjacency entries may not include node-level attrs explicitly.
    # We consider node constraints apply if any adjacency entry's attributes match (interpreting node attrs as adjacency attrs lacking neighbor-specific keys).
    # But typical node attributes may be absent; we'll treat node-level matches only if node has an 'attributes' dict under a special key; since not specified, assume none.
    node_forbidden = set()
    edge_forbidden = set()  # store frozenset({u,v}) with possible multiple edges keyed by (min(u,v),max(u,v),index) but adjacency likely symmetric single edge
    # Preprocess forbidden patterns into lists
    node_constraints_list = []
    edge_constraints_list = []
    for pat in forbidden_patterns:
        node_constraints_list.extend(pat.get("node_constraints", []))
        edge_constraints_list.extend(pat.get("edge_constraints", []))

    # Iterate edges, decide forbidden edges and mark nodes if node constraints matched (not typical here)
    # Also compute cost for allowed edges
    edges = []  # tuples (u, v, cost)
    seen_pairs = set()
    for u_str, adj in graph.items():
        try:
            u = int(u_str)
        except:
            u = u_str
        for entry in adj:
            if not isinstance(entry, list) and not isinstance(entry, tuple):
                continue
            if len(entry) < 2:
                continue
            v = entry[0]
            attrs = entry[1] or {}
            try:
                v_int = int(v)
            except:
                v_int = v
            a_u = u
            a_v = v_int
            key = (min(a_u, a_v), max(a_u, a_v))
            # Avoid duplicate processing if symmetric adjacency
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            # Check edge constraints
            forbidden_edge = False
            if edge_constraints_list:
                if edge_matches_constraints(attrs, edge_constraints_list):
                    forbidden_edge = True
            # Check node constraints: we don't have node attrs; however if node constraints are present, we check if any adjacency attribute matches them and then mark node forbidden.
            if node_constraints_list:
                if node_matches_constraints(attrs, node_constraints_list):
                    node_forbidden.add(a_u)
                    node_forbidden.add(a_v)
            if forbidden_edge:
                edge_forbidden.add(key)
                continue
            # compute cost
            tc = attrs.get("time_cost", {})
            cost = None
            if isinstance(tc, dict):
                day = tc.get("day", None)
                night = tc.get("night", None)
                if day is not None and night is not None:
                    cost = (day + night) / 2.0
                elif day is not None:
                    cost = float(day)
                elif night is not None:
                    cost = float(night)
            # If no time_cost, skip edge (cannot compute cost)
            if cost is None:
                continue
            edges.append((a_u, a_v, cost))

    # Filter edges touching forbidden nodes or forbidden edges
    filtered_edges = []
    for u, v, c in edges:
        key = (min(u, v), max(u, v))
        if key in edge_forbidden:
            continue
        if u in node_forbidden or v in node_forbidden:
            continue
        filtered_edges.append((u, v, c))

    if not filtered_edges:
        return []

    # Build graph for matching: as general graph maximum cardinality minimum weight matching.
    # We'll use greedy augmenting with sorting by cost to produce maximal matching with minimum total cost among maximal matchings heuristically.
    # Given constraints and no external libs, implement greedy: sort edges by cost ascending, break ties by lex order, and add if both endpoints free.
    # This yields maximal matching not necessarily maximum cardinality in all graphs, but works for many; to improve, attempt greedy twice: once by cost, once by degree-aware tie-breaking, choose better cardinality then cost.
    def greedy_match(edge_list):
        matched = set()
        result = []
        for u, v, c in edge_list:
            if u in matched or v in matched:
                continue
            matched.add(u)
            matched.add(v)
            a, b = sorted((u, v))
            result.append([a, b])
        return result

    # Prepare sorting key
    def edge_sort_key(e):
        u, v, c = e
        a, b = sorted((u, v))
        return (c, a, b)

    edges_sorted = sorted(filtered_edges, key=edge_sort_key)
    matching1 = greedy_match(edges_sorted)

    # Alternative: sort by (cost, min(deg)) to try get larger matching
    deg = {}
    for u, v, _ in filtered_edges:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1
    def edge_sort_key2(e):
        u, v, c = e
        a, b = sorted((u, v))
        mindeg = min(deg.get(u, 0), deg.get(v, 0))
        return (c, -mindeg, a, b)
    edges_sorted2 = sorted(filtered_edges, key=edge_sort_key2)
    matching2 = greedy_match(edges_sorted2)

    # Choose maximal by size, then by total cost, then lex order
    def total_cost(match):
        s = 0.0
        for a, b in match:
            # find cost
            for u, v, c in filtered_edges:
                if (u == a and v == b) or (u == b and v == a):
                    s += c
                    break
        return s

    candidates = [matching1, matching2]
    # Ensure each sorted pairs lex order
    for m in candidates:
        for p in m:
            p.sort()
    # Select best
    best = None
    for m in candidates:
        if best is None:
            best = m
            continue
        if len(m) > len(best):
            best = m
        elif len(m) == len(best):
            tc_m = total_cost(m)
            tc_b = total_cost(best)
            if abs(tc_m - tc_b) > 1e-9:
                if tc_m < tc_b:
                    best = m
            else:
                # tie-break lex
                if sorted(m) < sorted(best):
                    best = m
    if best is None:
        return []
    # final sort pairs lexicographically by first then second to have deterministic output
    best_sorted = sorted([sorted(p) for p in best], key=lambda x: (x[0], x[1]))
    return best_sorted

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