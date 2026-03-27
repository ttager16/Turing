def optimize_supply_chain_flow(
    graph: Dict[str, Dict[str, int]],
    user_adjustments: List[List]
) -> Dict[str, Dict[str, int]]:
    # Validate types
    if not isinstance(graph, dict) or not isinstance(user_adjustments, list):
        return {}
    # If both empty -> {}
    if graph == {} and user_adjustments == []:
        return {}
    # Validate graph structure and collect nodes
    nodes = set()
    for src, out in graph.items():
        if not isinstance(src, str) or src == "" or not isinstance(out, dict):
            return {}
        if src != src.upper() or any(ch < 'A' or ch > 'Z' for ch in src):
            return {}
        nodes.add(src)
        for dst, cap in out.items():
            if not isinstance(dst, str) or dst == "" or not isinstance(cap, int):
                return {}
            if dst != dst.upper() or any(ch < 'A' or ch > 'Z' for ch in dst):
                return {}
            if src == dst:
                return {}
            if cap < 0:
                return {}
            nodes.add(dst)
    # Validate adjustments and aggregate deltas
    deltas = {}  # (src,dst)->int
    adjusted_pairs = set()
    for item in user_adjustments:
        if not isinstance(item, list) or len(item) != 3:
            return {}
        src, dst, delta = item
        if not isinstance(src, str) or src == "" or not isinstance(dst, str) or dst == "":
            return {}
        if src != src.upper() or any(ch < 'A' or ch > 'Z' for ch in src):
            return {}
        if dst != dst.upper() or any(ch < 'A' or ch > 'Z' for ch in dst):
            return {}
        if not isinstance(delta, int):
            return {}
        if src == dst:
            return {}
        nodes.add(src); nodes.add(dst)
        key = (src, dst)
        deltas[key] = deltas.get(key, 0) + delta
        adjusted_pairs.add(key)
    # Build base capacities copy
    base = {}
    for n in graph:
        base[n] = dict(graph[n])  # shallow copy
    # Ensure nodes with no outgoing in original exist in base
    for n in nodes:
        if n not in base:
            base[n] = {}
    # Apply aggregated deltas
    # For each adjusted pair, compute current (0 if absent) + aggregated delta
    for (src, dst), agg in deltas.items():
        current = base.get(src, {}).get(dst, 0)
        final = current + agg
        if agg == 0:
            # no effective change; leave as-is (even if edge absent)
            continue
        if final <= 0:
            # remove edge if existed or added (only if affected by non-zero aggregated delta)
            if dst in base.get(src, {}):
                del base[src][dst]
        else:
            # set/add edge with final capacity
            base.setdefault(src, {})[dst] = final
    # Verify untouched pre-existing zero-capacity edges remain (already preserved)
    # Ensure lexicographic ordering: build new dicts sorted
    out = {}
    for src in sorted(nodes):
        edges = base.get(src, {})
        if not isinstance(edges, dict):
            return {}
        inner = {}
        for dst in sorted(edges.keys()):
            cap = edges[dst]
            if not isinstance(dst, str) or dst == "" or not isinstance(cap, int):
                return {}
            inner[dst] = cap
        out[src] = inner
    return out