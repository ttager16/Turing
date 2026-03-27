def compute_multi_stage_mst(
    graphs: List[Dict[str, List[List[Any]]]]
) -> List[Union[List[List[str]], Dict[str, str]]]:
    def canonical_edge(a, b):
        return (a, b) if a <= b else (b, a)

    def parse_lambda(expr):
        # safe eval for "lambda s: ..." returning a callable
        try:
            node = ast.parse(expr, mode='eval')
            # Only allow lambda expressions
            if not isinstance(node.body, ast.Lambda):
                return None
            code = compile(node, '<string>', 'eval')
            fn = eval(code, {})
            if not callable(fn):
                return None
            return fn
        except Exception:
            return None

    results = []
    for graph in graphs:
        # Validate special keys
        state = graph.get("_state", {})
        constraints = graph.get("_constraints", {})
        required_edges_raw = constraints.get("required_edges", [])
        forbidden_edges_raw = constraints.get("forbidden_edges", [])
        degree_limits = constraints.get("degree_limits", {})
        phase_blocklist_raw = constraints.get("phase_blocklist", [])
        round_cost_to = constraints.get("round_cost_to", 6)

        # collect nodes (string-labeled nodes only)
        nodes = [k for k in graph.keys() if not k.startswith("_")]
        nodes_set = set(nodes)

        # helper to canonicalize lists of edges
        def canon_list(edge):
            if len(edge) >= 2:
                return canonical_edge(str(edge[0]), str(edge[1]))
            return None

        required_edges = []
        for e in required_edges_raw:
            c = canon_list(e)
            if c: required_edges.append(c)
        forbidden_edges = set()
        for e in forbidden_edges_raw:
            c = canon_list(e)
            if c: forbidden_edges.add(c)
        phase_blocklist = set()
        for e in phase_blocklist_raw:
            c = canon_list(e)
            if c: phase_blocklist.add(c)

        # check required vs forbidden conflict
        for e in required_edges:
            if e in forbidden_edges:
                results = [{"error": "Required edge is forbidden"}]
                return results

        # build edge list evaluating label functions
        edge_map = {}  # (u,v) -> list of label expr strings (from one side)
        for u in nodes:
            adj = graph.get(u, [])
            for item in adj:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                v = str(item[0])
                expr = item[1]
                if u == v:
                    continue
                e = canonical_edge(str(u), v)
                edge_map.setdefault(e, []).append(expr)

        evaluated_edges = []
        for e, exprs in edge_map.items():
            if e in forbidden_edges or e in phase_blocklist:
                continue
            cost = None
            # try each expr until one yields valid numeric
            for expr in exprs:
                if not isinstance(expr, str):
                    continue
                fn = parse_lambda(expr)
                if fn is None:
                    continue
                try:
                    val = fn(state)
                    if val is None:
                        continue
                    if isinstance(val, bool):
                        # allow bool as number? treat as numeric
                        val = float(val)
                    if not isinstance(val, (int, float)):
                        continue
                    if not math.isfinite(val):
                        continue
                    cost = float(val)
                    break
                except Exception:
                    continue
            if cost is None:
                continue
            rounded = round(cost, round_cost_to)
            evaluated_edges.append((rounded, e[0], e[1], cost, e))

        if not evaluated_edges:
            return [{"error": "No valid edges available"}]

        # sort edges deterministically by (rounded_cost, u, v)
        evaluated_edges.sort(key=lambda x: (x[0], x[1], x[2]))

        # union-find
        parent = {}
        rank = {}
        deg = {n: 0 for n in nodes_set}

        def find(x):
            parent.setdefault(x, x)
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            rx = find(x); ry = find(y)
            if rx == ry:
                return False
            if rank.get(rx, 0) < rank.get(ry, 0):
                parent[rx] = ry
            else:
                parent[ry] = rx
                if rank.get(rx, 0) == rank.get(ry, 0):
                    rank[rx] = rank.get(rx, 0) + 1
            return True

        # add required edges first, checking cycles and degree limits
        chosen = set()
        # check cycles among required edges
        temp_parent = {}
        def temp_find(x):
            temp_parent.setdefault(x, x)
            if temp_parent[x] != x:
                temp_parent[x] = temp_find(temp_parent[x])
            return temp_parent[x]
        def temp_union(x,y):
            rx=temp_find(x); ry=temp_find(y)
            if rx==ry:
                return False
            temp_parent[ry]=rx
            return True

        for e in required_edges:
            u, v = e
            if u not in nodes_set or v not in nodes_set:
                # treat as invalid edge leading to infeasibility
                return [{"error": "Required edges form a cycle"}]
            if not temp_union(u, v):
                return [{"error": "Required edges form a cycle"}]

        # check degree limits feasibility baseline: required edges degrees must not exceed limits
        for e in required_edges:
            u, v = e
            deg[u] = deg.get(u, 0) + 1
            deg[v] = deg.get(v, 0) + 1
            chosen.add(e)
            union(u, v)
        for node, limit in degree_limits.items():
            node = str(node)
            if node in deg and limit is not None:
                if deg[node] > limit:
                    return [{"error": "Degree limit infeasible"}]

        # Now attempt to build MST/forest greedily using deterministic Kruskal while respecting:
        # - cannot add forbidden or phase_blocklist edges (already filtered)
        # - must not violate degree limits
        # - must avoid cycles (unless connecting components needed? cycles not allowed)
        for rounded, u, v, cost, e in evaluated_edges:
            if e in chosen:
                continue
            # skip if would form cycle
            if find(u) == find(v):
                continue
            # check degree limits if any
            du = deg.get(u,0)
            dv = deg.get(v,0)
            lim_u = degree_limits.get(u, None)
            lim_v = degree_limits.get(v, None)
            if lim_u is not None and du + 1 > lim_u:
                continue
            if lim_v is not None and dv + 1 > lim_v:
                continue
            # accept edge
            union(u, v)
            deg[u] = du + 1
            deg[v] = dv + 1
            chosen.add(e)

        # After processing, ensure degree limits globally feasible: check if any node's degree > limit
        for node, limit in degree_limits.items():
            node = str(node)
            if limit is not None and deg.get(node,0) > limit:
                return [{"error": "Degree limit infeasible"}]

        # Build result list: must produce minimum spanning forest covering all nodes (string-labeled)
        # Note: if graph disconnected, we've produced forest via Kruskal
        # Prepare output as sorted list of [u,v] strings per edge, canonical form
        out_edges = [ [u, v] for (u, v) in chosen ]
        # ensure canonical order inside edge
        out_edges = [ [str(a), str(b)] if a<=b else [str(b), str(a)] for a,b in out_edges ]
        # lexicographically sort edges
        out_edges.sort()
        results.append(out_edges)
    return results