def update_topological_order(
    graph: Dict[str, Dict[str, int]],
    node_states: Dict[str, Dict[str, Any]],
    updates: List[Dict[str, Any]],
    reconcile_policy: str = "abort_on_conflict"
) -> Union[List[str], str]:
    # Nested helpers
    def err(s: str) -> str:
        return s

    # Validate graph type
    if not isinstance(graph, dict) or not all(isinstance(k, str) and isinstance(v, dict) for k, v in graph.items()):
        return err("TypeError: InvalidInputError: 'graph' must be Dict[str, Dict[str, int]]")
    # Count nodes and edges
    n_nodes = len(graph)
    n_edges = sum(len(v) for v in graph.values())
    if n_nodes > 10 or n_edges > 10:
        return err(f"ValueError: InputSizeError: graph has {n_nodes} nodes and {n_edges} edges; limits are max_nodes=10, max_edges=10")
    # Validate node_states
    if not isinstance(node_states, dict) or not all(isinstance(k, str) and isinstance(v, dict) for k, v in node_states.items()):
        return err("TypeError: InvalidInputError: 'node_states' must be Dict[str, Dict[str, Any]]")
    for node in graph:
        if node not in node_states:
            return err(f"KeyError: InvalidInputError: missing node_states entry for node {node}")
    # reconcile_policy
    if reconcile_policy not in ("abort_on_conflict", "ignore_with_skip"):
        return err("ValueError: InvalidInputError: reconcile_policy must be 'abort_on_conflict' or 'ignore_with_skip'")

    # Validate updates list
    if not isinstance(updates, list):
        return err("TypeError: InvalidInputError: 'updates' must be a list of update records")
    for i, up in enumerate(updates):
        if not isinstance(up, dict):
            return err(f"TypeError: InvalidUpdateError: update at index {i} must be a dict")
        op = up.get("op")
        if not isinstance(op, str) or op not in ("add_edge", "remove_edge", "capacity_change", "change_state"):
            return err(f"ValueError: InvalidUpdateError: update at index {i} has invalid op '{op}'")
        # src required for edge and state ops
        if op in ("add_edge", "remove_edge", "capacity_change", "change_state"):
            src = up.get("src", None)
            if not isinstance(src, str):
                return err(f"TypeError: InvalidUpdateError: update at index {i} missing or invalid 'src'")
        # dst required for edge ops
        if op in ("add_edge", "remove_edge", "capacity_change"):
            dst = up.get("dst", None)
            if not isinstance(dst, str):
                return err(f"TypeError: InvalidUpdateError: update at index {i} missing or invalid 'dst'")
        # value types
        if op == "capacity_change":
            if "value" not in up or not isinstance(up.get("value", None), int):
                return err(f"TypeError: InvalidUpdateError: update at index {i} has invalid 'value' for op '{op}'")
        if op == "change_state":
            if "value" not in up:
                return err(f"TypeError: InvalidUpdateError: update at index {i} has invalid 'value' for op '{op}'")
            if not isinstance(up.get("value", None), dict):
                return err(f"TypeError: InvalidUpdateError: update at index {i} change_state 'value' must be a dict")
        # ts if present
        if "ts" in up and not isinstance(up["ts"], (int, float)):
            return err(f"TypeError: InvalidUpdateError: update at index {i} has invalid 'ts' type; must be int or float")

    # Work on copies for transactional behavior
    g = {k: dict(v) for k, v in graph.items()}
    ns = {k: dict(v) for k, v in node_states.items()}

    # Helper to detect unknown node
    def unknown_node(i, node_id):
        return f"RuntimeError: InvalidUpdateError: update at index {i} references unknown node {node_id}"

    # Apply updates atomically unless ignore_with_skip
    applied_ops = []
    for i, up in enumerate(updates):
        op = up["op"]
        src = up.get("src")
        dst = up.get("dst")
        val = up.get("value")
        # check nodes exist
        if op in ("add_edge", "remove_edge", "capacity_change"):
            if src not in g:
                if reconcile_policy == "abort_on_conflict":
                    return err(unknown_node(i, src))
                else:
                    continue
            if dst not in g:
                if reconcile_policy == "abort_on_conflict":
                    return err(unknown_node(i, dst))
                else:
                    continue
        if op == "change_state":
            if src not in g:
                if reconcile_policy == "abort_on_conflict":
                    return err(unknown_node(i, src))
                else:
                    continue
            if not isinstance(val, dict):
                if reconcile_policy == "abort_on_conflict":
                    return err(f"TypeError: InvalidUpdateError: update at index {i} change_state 'value' must be a dict")
                else:
                    continue
        # Semantic checks
        if op == "add_edge":
            # add or overwrite capacity
            g[src][dst] = val if isinstance(val, int) else (up.get("value") if isinstance(up.get("value"), int) else 0)
            applied_ops.append(("add_edge", src, dst))
        elif op == "remove_edge":
            if dst not in g[src]:
                if reconcile_policy == "abort_on_conflict":
                    return err(f"RuntimeError: InvalidUpdateError: update at index {i} references non-existent edge {src}->{dst}")
                else:
                    continue
            del g[src][dst]
            applied_ops.append(("remove_edge", src, dst))
        elif op == "capacity_change":
            if dst not in g[src]:
                if reconcile_policy == "abort_on_conflict":
                    return err(f"RuntimeError: InvalidUpdateError: update at index {i} references non-existent edge {src}->{dst}")
                else:
                    continue
            g[src][dst] = val
            applied_ops.append(("capacity_change", src, dst, val))
        elif op == "change_state":
            # merge provided keys into node state
            ns[src].update(val)
            applied_ops.append(("change_state", src, val))
        # After each update, check sizes constraints
        total_edges = sum(len(v) for v in g.values())
        if len(g) > 10 or total_edges > 10:
            return err(f"ValueError: InputSizeError: graph has {len(g)} nodes and {total_edges} edges; limits are max_nodes=10, max_edges=10")

    # After applying batch, detect cycles. Use Kahn's algorithm but produce deterministic ordering by priority then id.
    # Build in-degree
    nodes = list(g.keys())
    indeg = {node: 0 for node in nodes}
    for u in nodes:
        for v in g[u]:
            indeg[v] = indeg.get(v, 0) + 1
    # Prepare priority and stable ordering keys
    def node_key(n):
        pr = ns.get(n, {}).get("priority", 0)
        return (pr, int(n) if n.isdigit() else n)
    # Kahn's algorithm deterministic: pick nodes with indeg 0 sorted by priority then id
    zero = [n for n in nodes if indeg[n] == 0]
    zero.sort(key=node_key)
    order = []
    q = deque(zero)
    while q:
        u = q.popleft()
        order.append(u)
        for v in list(g[u].keys()):
            indeg[v] -= 1
            if indeg[v] == 0:
                # insert maintaining order: append and then stable sort not efficient but small sizes
                q.append(v)
        # maintain deterministic queue order by sorting current queue by key
        q = deque(sorted(list(q), key=node_key))
    if len(order) != len(nodes):
        # find cycle nodes via nodes with indeg>0
        cycle_nodes = [n for n in nodes if indeg[n] > 0]
        cycle_nodes_sorted = sorted(cycle_nodes, key=lambda x: (ns.get(x, {}).get("priority", 0), int(x) if x.isdigit() else x))
        if reconcile_policy == "abort_on_conflict":
            # find failed_update_index: approximate as first update that if removed would avoid cycle.
            # For spec, report failed_update_index as index of last applied op (simpler)
            failed_index = 0
            # Try to find which update introduced cycle: simulate incremental application to empty base graph
            base_g = {k: dict(v) for k, v in graph.items()}
            base_ns = {k: dict(v) for k, v in node_states.items()}
            for idx, up in enumerate(updates):
                op = up["op"]
                src = up.get("src")
                dst = up.get("dst")
                val = up.get("value")
                # apply with same skip semantics for unknowns etc.
                if op in ("add_edge", "remove_edge", "capacity_change"):
                    if src not in base_g or dst not in base_g:
                        # skip semantics
                        if reconcile_policy == "abort_on_conflict":
                            failed_index = idx
                            break
                        else:
                            continue
                if op == "add_edge":
                    base_g[src][dst] = val if isinstance(val, int) else (up.get("value") if isinstance(up.get("value"), int) else 0)
                elif op == "remove_edge":
                    if dst not in base_g[src]:
                        if reconcile_policy == "abort_on_conflict":
                            failed_index = idx
                            break
                        else:
                            continue
                    del base_g[src][dst]
                elif op == "capacity_change":
                    if dst not in base_g[src]:
                        if reconcile_policy == "abort_on_conflict":
                            failed_index = idx
                            break
                        else:
                            continue
                    base_g[src][dst] = val
                elif op == "change_state":
                    if src not in base_ns:
                        if reconcile_policy == "abort_on_conflict":
                            failed_index = idx
                            break
                        else:
                            continue
                    base_ns[src].update(val)
                # check cycle quick
                indeg_b = {n:0 for n in base_g}
                for u in base_g:
                    for v in base_g[u]:
                        indeg_b[v] = indeg_b.get(v,0)+1
                qz = [n for n in base_g if indeg_b[n]==0]
                # attempt topo
                cnt=0
                qq=deque(sorted(qz, key=lambda x:(base_ns.get(x,{}).get("priority",0), int(x) if x.isdigit() else x)))
                while qq:
                    uu=qq.popleft(); cnt+=1
                    for vv in base_g[uu]:
                        indeg_b[vv]-=1
                        if indeg_b[vv]==0:
                            qq.append(vv)
                    qq=deque(sorted(list(qq), key=lambda x:(base_ns.get(x,{}).get("priority",0), int(x) if x.isdigit() else x)))
                if cnt != len(base_g):
                    failed_index = idx
                    break
            return err(f"RuntimeError: CycleDetectedError: batch creates cycle involving nodes {cycle_nodes_sorted}; failed_update_index={failed_index}")
        else:
            # ignore_with_skip shouldn't reach here because we applied skip semantics earlier; but return ordering of acyclic reachable nodes
            # As per requirement, produce consistent ordering or clear error. Here, return error string describing inconsistency.
            return err(f"RuntimeError: CycleDetectedError: batch creates cycle involving nodes {cycle_nodes_sorted}; failed_update_index=0")

    return order