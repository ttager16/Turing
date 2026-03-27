def analyze_network_vulnerability(
    network: Dict[str, List[List[int]]],
    vulnerability_scores: Dict[str, float],
    system_types: Dict[str, int],
    privilege_levels: Dict[str, int],
    source_system: int,
    target_systems: List[int],
    vulnerability_threshold: float,
    max_path_length: int,
    threat_model: str,
    use_recursive: bool,
) -> Dict[str, List[List[int]]]:

    # Helper for error response
    def err(msg):
        return {"error": msg}

    # Basic validations
    if str(source_system) not in network:
        return err("Source system not found in network")
    for t in target_systems:
        if str(t) not in network:
            return err("Target system not found in network")
    if threat_model not in ("insider", "external", "apt"):
        return err("Invalid threat model")
    if not (1 <= max_path_length <= 50):
        return err("Invalid max_path_length")
    if vulnerability_threshold < 0:
        return err("Invalid vulnerability_threshold")
    # Validate system_types values
    for sid, st in system_types.items():
        if not (1 <= st <= 5):
            return err("Invalid system_type")
    for sid, pl in privilege_levels.items():
        if not (1 <= pl <= 4):
            return err("Invalid privilege_level")
    # Validate network edge fields and connected nodes presence and their attributes
    for sid, edges in network.items():
        if not isinstance(edges, list):
            continue
        for e in edges:
            if not isinstance(e, list) or len(e) < 3:
                continue
            connected_id = str(e[0])
            conn_sec = e[1]
            trust = e[2]
            if not (isinstance(conn_sec, int) and 1 <= conn_sec <= 5):
                return err("Invalid connection_security_level")
            if not (isinstance(trust, int) and 1 <= trust <= 10):
                return err("Invalid trust_level")
            if connected_id not in vulnerability_scores:
                return err("Connected system not found in vulnerability_scores")
            if connected_id not in system_types:
                return err("Connected system not found in system_types")
            if connected_id not in privilege_levels:
                return err("Connected system not found in privilege_levels")
    # Validate source presence in other dicts
    if str(source_system) not in vulnerability_scores:
        return err("Source system not found in vulnerability_scores")
    if str(source_system) not in system_types:
        return err("Source system not found in system_types")
    if str(source_system) not in privilege_levels:
        return err("Source system not found in privilege_levels")
    # Validate targets in other dicts (after connected checks per spec)
    for t in target_systems:
        ts = str(t)
        if ts not in vulnerability_scores:
            return err("Target system not found in vulnerability_scores")
        if ts not in system_types:
            return err("Target system not found in system_types")
        if ts not in privilege_levels:
            return err("Target system not found in privilege_levels")

    # System type compatibility rules
    def compatible(from_type: int, to_type: int) -> bool:
        # server(1) connects to all types
        if from_type == 1:
            return True
        if from_type == 2:
            return to_type in (1, 3)
        if from_type == 3:
            return to_type in (1, 2)
        if from_type == 4:
            return True
        if from_type == 5:
            return to_type in (1, 4)
        return False

    # Privilege escalation valid for step: prev_priv -> next_priv
    def privilege_ok(prev_p: int, next_p: int) -> bool:
        if prev_p == next_p:
            return True
        if prev_p == 1 and next_p == 2:
            return True
        if prev_p == 2 and next_p == 3:
            return True
        if prev_p == 3 and next_p == 4:
            return True
        # Higher can access lower
        if prev_p > next_p:
            return True
        return False

    # Threat multipliers
    mult = {"insider": 1.5, "external": 0.8, "apt": 2.0}[threat_model]

    source_str = str(source_system)
    target_set = set(str(t) for t in target_systems)

    # Prepare adjacency with validated edges only
    adj: Dict[str, List[List[int]]] = {}
    for sid, edges in network.items():
        lst = []
        if isinstance(edges, list):
            for e in edges:
                if not isinstance(e, list) or len(e) < 3:
                    continue
                lst.append([str(e[0]), int(e[1]), int(e[2])])
        adj[str(sid)] = lst

    results_scores: Dict[str, List[List[float]]] = {}
    for t in target_set:
        results_scores[t] = []

    # DFS implementations
    def calculate_edge_contrib(node_to: str, conn_sec: int, trust: int) -> float:
        vs = vulnerability_scores.get(node_to, 0.0)
        return vs * conn_sec / trust * mult

    # Recursive DFS
    def dfs_recursive(curr: str, path: List[str], visited: Dict[str, bool], cum_score: float):
        if len(path) > max_path_length:
            return
        if curr in target_set and curr != source_str:
            if cum_score >= vulnerability_threshold:
                results_scores[curr].append([cum_score] + [int(x) for x in path])
        for e in adj.get(curr, []):
            nxt = e[0]
            conn_sec = e[1]
            trust = e[2]
            if nxt in visited:
                continue
            # system type compatibility
            if not compatible(system_types.get(curr, 0), system_types.get(nxt, 0)):
                continue
            # privilege escalation
            if not privilege_ok(privilege_levels.get(curr, 0), privilege_levels.get(nxt, 0)):
                continue
            contrib = calculate_edge_contrib(nxt, conn_sec, trust)
            visited[nxt] = True
            path.append(nxt)
            dfs_recursive(nxt, path, visited, cum_score + contrib)
            path.pop()
            del visited[nxt]

    # Iterative DFS
    def dfs_iterative():
        stack = []
        # store: current_node, path_list, visited_set, cum_score, iterator_index
        stack.append([source_str, [source_str], {source_str: True}, 0.0, 0])
        while stack:
            node, path, visited, cum_score, idx = stack.pop()
            if len(path) > max_path_length:
                continue
            if node in target_set and node != source_str:
                if cum_score >= vulnerability_threshold:
                    results_scores[node].append([cum_score] + [int(x) for x in path])
            edges = adj.get(node, [])
            # iterate edges in reverse to mimic DFS order similar to recursive
            for e in reversed(edges):
                nxt = e[0]
                conn_sec = e[1]
                trust = e[2]
                if nxt in visited:
                    continue
                if not compatible(system_types.get(node, 0), system_types.get(nxt, 0)):
                    continue
                if not privilege_ok(privilege_levels.get(node, 0), privilege_levels.get(nxt, 0)):
                    continue
                contrib = calculate_edge_contrib(nxt, conn_sec, trust)
                new_path = path + [nxt]
                new_visited = dict(visited)
                new_visited[nxt] = True
                stack.append([nxt, new_path, new_visited, cum_score + contrib, 0])

    # Run chosen DFS
    if use_recursive:
        visited0 = {source_str: True}
        dfs_recursive(source_str, [source_str], visited0, 0.0)
    else:
        dfs_iterative()

    # Prepare final output: for each target, sort paths by score desc, return lists of ints as lists
    output: Dict[str, List[List[int]]] = {}
    for t in target_set:
        entries = results_scores.get(t, [])
        # entries are [score, path...], where after score we have ints already
        # sort by score desc
        entries.sort(key=lambda x: -float(x[0]))
        # extract paths and filter length constraint again
        paths = []
        for ent in entries:
            path_ints = ent[1:]
            if 1 <= len(path_ints) <= max_path_length:
                paths.append([int(x) for x in path_ints])
        output[str(t)] = paths

    return output