from typing import Dict, Any, List, Optional, Union


def update_topological_order(
    graph: Dict[str, Dict[str, int]],
    node_states: Dict[str, Dict[str, Any]],
    updates: List[Dict[str, Any]],
    reconcile_policy: str = "abort_on_conflict"
) -> Union[List[str], str]:
    """Updates the topological ordering based on complex multi-state changes.

    This function contains the full implementation nested here to satisfy
    the prompt constraint that the implementation live inside a single
    top-level function. Module-level imports are allowed above.
    
    Returns:
        Union[List[str], str]: Either a list of node IDs in topological order,
        or an error string in the format "{ExceptionType}: {error_message}"
    """

    # Basic type validations (graph, node_states, updates)
    # Strictly require string keys per prompt.md specification
    if not isinstance(graph, dict):
        return "TypeError: InvalidInputError: 'graph' must be Dict[str, Dict[str, int]]"
    # Validate shape - require str keys only
    for k, v in graph.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            return "TypeError: InvalidInputError: 'graph' must be Dict[str, Dict[str, int]]"
        for nk, cap in v.items():
            if not isinstance(nk, str) or not isinstance(cap, int):
                return "TypeError: InvalidInputError: 'graph' must be Dict[str, Dict[str, int]]"

    if not isinstance(node_states, dict):
        return "TypeError: InvalidInputError: 'node_states' must be Dict[str, Dict[str, Any]]"
    for nk, ns in node_states.items():
        if not isinstance(nk, str) or not isinstance(ns, dict):
            return "TypeError: InvalidInputError: 'node_states' must be Dict[str, Dict[str, Any]]"

    if not isinstance(updates, list):
        return "TypeError: InvalidInputError: 'updates' must be a list of update records"

    # reconcile_policy validation
    if reconcile_policy not in ("abort_on_conflict", "ignore_with_skip"):
        return "ValueError: InvalidInputError: reconcile_policy must be 'abort_on_conflict' or 'ignore_with_skip'"

    # Ensure every node in graph has node_states entry
    for node_id in graph.keys():
        if node_id not in node_states:
            return f"KeyError: InvalidInputError: missing node_states entry for node {node_id}"

    # Size limit validation
    n = len(graph)
    m = sum(len(nbrs) for nbrs in graph.values())
    if n > 10 or m > 10:
        return f"ValueError: InputSizeError: graph has {n} nodes and {m} edges; limits are max_nodes=10, max_edges=10"

    # Validate update record shapes (but not semantic existence which is batch-ordered)
    allowed_ops = {"add_edge", "remove_edge", "capacity_change", "change_state"}
    for i, upd in enumerate(updates):
        if not isinstance(upd, dict):
            return f"TypeError: InvalidUpdateError: update at index {i} must be a dict"
        op = upd.get("op")
        if not isinstance(op, str) or op not in allowed_ops:
            return f"ValueError: InvalidUpdateError: update at index {i} has invalid op '{op}'"
        # src required for all ops - must be string
        if "src" not in upd or not isinstance(upd["src"], str):
            return f"TypeError: InvalidUpdateError: update at index {i} missing or invalid 'src'"
        if op in ("add_edge", "remove_edge", "capacity_change"):
            if "dst" not in upd or not isinstance(upd.get("dst"), str):
                return f"TypeError: InvalidUpdateError: update at index {i} missing or invalid 'dst'"
        # value type checks
        if "value" in upd and upd["value"] is not None:
            if op == "capacity_change" and not isinstance(upd["value"], int):
                return f"TypeError: InvalidUpdateError: update at index {i} has invalid 'value' for op '{op}'"
            if op == "change_state" and not isinstance(upd["value"], dict):
                return f"TypeError: InvalidUpdateError: update at index {i} change_state 'value' must be a dict"
        if "ts" in upd and not (isinstance(upd["ts"], int) or isinstance(upd["ts"], float)):
            return f"TypeError: InvalidUpdateError: update at index {i} has invalid 'ts' type; must be int or float"

    # Working with string keys only - no normalization needed
    working_graph: Dict[str, Dict[str, int]] = {}
    for u, nbrs in graph.items():
        working_graph[u] = {nk: int(cap) for nk, cap in nbrs.items()}

    # Copy node_states
    working_node_states: Dict[str, Dict[str, Any]] = {}
    for n, s in node_states.items():
        working_node_states[n] = dict(s)

    # Snapshot for rollback on abort_on_conflict
    snapshot_graph: Dict[str, Dict[str, int]] = {u: dict(v) for u, v in working_graph.items()}
    snapshot_node_states: Dict[str, Dict[str, Any]] = {n: dict(s) for n, s in working_node_states.items()}

    # Helper to detect cycle and return list of nodes in a cycle if any
    def find_cycle(g: Dict[str, Dict[str, int]]) -> Optional[List[str]]:
        visited = set()
        stack = []

        def dfs(u, path_set, path_list):
            visited.add(u)
            path_set.add(u)
            path_list.append(u)
            for v in g.get(u, {}):
                if v not in visited:
                    res = dfs(v, path_set, path_list)
                    if res:
                        return res
                elif v in path_set:
                    # cycle found; extract cycle nodes starting from v
                    idx = path_list.index(v)
                    return path_list[idx:]
            path_set.remove(u)
            path_list.pop()
            return None

        for node in g.keys():
            if node not in visited:
                res = dfs(node, set(), [])
                if res:
                    return res
        return None

    # Apply updates in order, handling semantic errors according to reconcile_policy
    error_msg = None
    for i, upd in enumerate(updates):
        op = upd["op"]
        src = upd.get("src")
        dst = upd.get("dst")
        val = upd.get("value")

        # Semantic checks: node existence (keys are already strings)
        if src not in working_graph:
            msg = f"RuntimeError: InvalidUpdateError: update at index {i} references unknown node {src}"
            if reconcile_policy == "abort_on_conflict":
                error_msg = msg
                break
            else:
                continue
        if op in ("add_edge", "remove_edge", "capacity_change") and dst not in working_graph:
            msg = f"RuntimeError: InvalidUpdateError: update at index {i} references unknown node {dst}"
            if reconcile_policy == "abort_on_conflict":
                error_msg = msg
                break
            else:
                continue

        if op == "add_edge":
            # add or overwrite edge
            working_graph.setdefault(src, {})
            working_graph[src][dst] = int(val) if val is not None else 0
            # check for cycles
            cycle = find_cycle(working_graph)
            if cycle:
                msg = f"RuntimeError: CycleDetectedError: batch creates cycle involving nodes {cycle}; failed_update_index={i}"
                if reconcile_policy == "abort_on_conflict":
                    error_msg = msg
                    break
                else:
                    # revert only this update for ignore_with_skip
                    working_graph[src].pop(dst, None)
                    # skip silently
                    continue

        elif op == "capacity_change":
            if dst not in working_graph.get(src, {}):
                msg = f"RuntimeError: InvalidUpdateError: update at index {i} references non-existent edge {src}->{dst}"
                if reconcile_policy == "abort_on_conflict":
                    error_msg = msg
                    break
                else:
                    # skip silently
                    continue
            working_graph[src][dst] = int(val)

        elif op == "remove_edge":
            if dst not in working_graph.get(src, {}):
                msg = f"RuntimeError: InvalidUpdateError: update at index {i} references non-existent edge {src}->{dst}"
                if reconcile_policy == "abort_on_conflict":
                    error_msg = msg
                    break
                else:
                    # skip silently
                    continue
            working_graph[src].pop(dst, None)

        elif op == "change_state":
            if not isinstance(val, dict):
                msg = f"TypeError: InvalidUpdateError: update at index {i} change_state 'value' must be a dict"
                if reconcile_policy == "abort_on_conflict":
                    error_msg = msg
                    break
                else:
                    # skip silently
                    continue
            working_node_states[src].update(val)

    # If error occurred under abort_on_conflict, return error string
    if error_msg is not None and reconcile_policy == "abort_on_conflict":
        return error_msg

    # After applying all updates, compute deterministic topological ordering
    # Build indegree map (on normalized string keys)
    indegree: Dict[str, int] = {n: 0 for n in working_graph.keys()}
    for u, nbrs in working_graph.items():
        for v in nbrs.keys():
            indegree[v] = indegree.get(v, 0) + 1

    order: List[str] = []
    zero = [n for n, d in indegree.items() if d == 0]

    def priority_key(node_id: str):
        pr = working_node_states.get(node_id, {}).get("priority", 0)
        try:
            pr_val = int(pr)
        except Exception:
            pr_val = 0
        return (pr_val, node_id)

    while zero:
        zero.sort(key=priority_key)
        u = zero.pop(0)
        order.append(u)
        for v in list(working_graph.get(u, {}).keys()):
            indegree[v] -= 1
            if indegree[v] == 0:
                zero.append(v)

    if len(order) != len(working_graph):
        # fallback cycle detection
        cycle = find_cycle(working_graph) or []
        return f"RuntimeError: CycleDetectedError: batch creates cycle involving nodes {cycle}; failed_update_index=-1"

    # Return string node IDs as per prompt specification
    return order