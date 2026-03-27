# Number of time periods used to compute average cost (day/night)
NUM_TIME_PERIODS = 2

# Default cost when no time_cost info is present
DEFAULT_EDGE_COST = 0.0


def optimize_resource_allocation(graph: dict, forbidden_patterns: list) -> list:
    """
    Select valid low-cost edges while avoiding forbidden motifs and satisfying
    capacity/time constraints.

    - graph: dict mapping node_id -> list of [neighbor_id, attrs]
    - forbidden_patterns: list of dicts containing node_constraints and/or edge_constraints

    Returns: list of matched node pairs [[u, v], ...] chosen greedily by cost with deterministic tie-breaking.
    """

    def violates_node_constraints(node_id, patterns):
        """
        A node is considered violating if:
         - any node_constraint directly references the node_id ({"node_id": X}), OR
         - any incident edge (edges where node_id appears as endpoint) carries an attribute that matches a
           node_constraint key/value (i.e., node-attributes implicitly provided via connected edges).
        """
        sid = str(node_id)
        # direct node id matches
        for pattern in patterns:
            for nc in pattern.get("node_constraints", []):
                for k, v in nc.items():
                    if k == "node_id" and int(node_id) == int(v):
                        return True

        # if node constraints reference an attribute present on incident edges,
        # forbid node if any connected edge has that attribute equal to constraint value.
        for pattern in patterns:
            for nc in pattern.get("node_constraints", []):
                for k, v in nc.items():
                    if k == "node_id":
                        continue
                    # check edges stored under this node
                    for _, edge_attrs in graph.get(sid, []):
                        if edge_attrs.get(k) == v:
                            return True
                    # check edges where node appears as neighbor
                    for other_node, nbrs in graph.items():
                        for nb in nbrs:
                            if not isinstance(nb, list) or len(nb) < 1:
                                continue
                            neigh_id = nb[0]
                            if str(neigh_id) == sid:
                                attrs = nb[1] if len(nb) > 1 else {}
                                if attrs.get(k) == v:
                                    return True
        return False

    def violates_edge_constraints(edge_attrs, patterns):
        """
        For each edge_constraint dict in patterns, if any constraint's key
        matches an attribute in edge_attrs and the attribute value satisfies
        the constraint (range or equality), the edge is forbidden.
        """
        for pattern in patterns:
            for constraint in pattern.get("edge_constraints", []):
                for k, v in constraint.items():
                    if k not in edge_attrs:
                        continue
                    attr_val = edge_attrs[k]
                    if isinstance(v, dict):
                        if "min" in v and "max" in v:
                            try:
                                if v["min"] <= attr_val <= v["max"]:
                                    return True
                            except TypeError:
                                continue
                        elif "min" in v:
                            try:
                                if attr_val >= v["min"]:
                                    return True
                            except TypeError:
                                continue
                        elif "max" in v:
                            try:
                                if attr_val <= v["max"]:
                                    return True
                            except TypeError:
                                continue
                    else:
                        if attr_val == v:
                            return True
        return False

    # Normalize keys
    normalized_graph = {str(k): v for k, v in graph.items()}

    candidates = []
    seen_edges = set()
    forbidden_nodes = set()

    # Identify forbidden nodes
    for node in normalized_graph.keys():
        if violates_node_constraints(node, forbidden_patterns):
            forbidden_nodes.add(int(node))

    # Iterate and collect valid edges
    for u_str, neighbors in normalized_graph.items():
        u_int = int(u_str)
        if u_int in forbidden_nodes:
            continue
        if not isinstance(neighbors, list):
            continue
        for edge in neighbors:
            if not isinstance(edge, list) or len(edge) < 1:
                continue
            v = edge[0]
            attrs = edge[1] if len(edge) > 1 else {}

            v_str = str(v)
            v_int = int(v_str)

            if v_int in forbidden_nodes:
                continue

            key = (min(u_int, v_int), max(u_int, v_int))
            if key in seen_edges:
                continue
            seen_edges.add(key)

            if violates_edge_constraints(attrs, forbidden_patterns):
                continue

            # Compute average or single available cost
            time_cost = attrs.get("time_cost", {})
            day = time_cost.get("day")
            night = time_cost.get("night")
            if day is not None and night is not None:
                cost = (day + night) / NUM_TIME_PERIODS
            else:
                cost = day if day is not None else (night if night is not None else DEFAULT_EDGE_COST)

            candidates.append((cost, key[0], key[1]))

    if not candidates:
        return []

    # Sort for deterministic results
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))

    matched = set()
    matching = []
    for cost, u, v in candidates:
        if u not in matched and v not in matched:
            matched.add(u)
            matched.add(v)
            matching.append([u, v])

    matching.sort()
    return matching