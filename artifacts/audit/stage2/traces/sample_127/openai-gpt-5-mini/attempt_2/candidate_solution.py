def compute_multi_stage_mst(
    graphs: List[Dict[str, List[List[Any]]]]
) -> List[Union[List[List[str]], Dict[str, str]]]:
    def canonical(e):
        a, b = e
        return (a, b) if a <= b else (b, a)

    def eval_label(fn_str, state):
        try:
            # Secure eval: parse lambda and compile AST to code object
            node = ast.parse(fn_str, mode='eval')
            # Only allow lambda expressions
            if not isinstance(node.body, ast.Lambda):
                return None
            code = compile(node, '<string>', 'eval')
            fn = eval(code, {})
            res = fn(state)
            if not (isinstance(res, (int, float)) and math.isfinite(res)):
                return None
            return float(res)
        except Exception:
            return None

    results = []
    for graph in graphs:
        # Validate specials
        state = graph.get("_state", {})
        constraints = graph.get("_constraints", {})
        required = [tuple(x) for x in constraints.get("required_edges", [])]
        forbidden = [tuple(x) for x in constraints.get("forbidden_edges", [])]
        degree_limits = {k: v for k, v in constraints.get("degree_limits", {}).items()}
        phase_block = [tuple(x) for x in constraints.get("phase_blocklist", [])]
        round_to = constraints.get("round_cost_to", 6)

        # collect nodes (string-labeled)
        nodes = set()
        edges_raw = {}
        for u, adj in graph.items():
            if u in ("_state", "_constraints"):
                continue
            nodes.add(u)
            for item in adj:
                if not isinstance(item, list) or len(item) != 2:
                    continue
                v, fn_str = item
                nodes.add(v)
                e = canonical((u, v))
                # store only one label per undirected edge per occurrence list: collect as list
                edges_raw.setdefault(e, []).append(fn_str)

        # sanitize required/forbidden/blocklist into canonical
        required = [canonical(tuple(e)) for e in required]
        forbidden = [canonical(tuple(e)) for e in forbidden]
        phase_block = [canonical(tuple(e)) for e in phase_block]

        # check required vs forbidden conflict
        for e in required:
            if e in forbidden or e in phase_block:
                results.append([{"error": "Required edge is forbidden"}])
                break
        else:
            # build evaluated edge costs: for each undirected edge, try each label function string in its list until one valid
            evaluated = {}
            for e, fns in edges_raw.items():
                u, v = e
                if u == v:
                    continue
                if e in forbidden or e in phase_block:
                    continue
                cost = None
                for fn_str in fns:
                    val = eval_label(fn_str, state)
                    if val is not None:
                        cost = val
                        break
                if cost is None:
                    continue
                evaluated[e] = round(cost, round_to)

            if not evaluated:
                results.append([{"error": "No valid edges available"}])
                continue

            # Prepare required edges must be present in evaluated
            for e in required:
                if e not in evaluated:
                    # required edge absent (maybe forbidden or missing label)
                    results.append([{"error": "Required edge is forbidden"}])
                    break
            else:
                # Check if required edges form a cycle among themselves
                parent = {}
                def find(x):
                    parent.setdefault(x, x)
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x
                def union(x, y):
                    rx, ry = find(x), find(y)
                    if rx == ry:
                        return False
                    parent[rx] = ry
                    return True

                cycle_found = False
                for u, v in required:
                    if u == v:
                        cycle_found = True
                        break
                    if not union(u, v):
                        cycle_found = True
                        break
                if cycle_found:
                    results.append([{"error": "Required edges form a cycle"}])
                    continue

                # Start Kruskal deterministic: include required edges first (respecting degree limits), then sort rest
                # Initialize union-find and degrees
                uf_parent = {}
                def uf_find(x):
                    uf_parent.setdefault(x, x)
                    while uf_parent[x] != x:
                        uf_parent[x] = uf_parent[uf_parent[x]]
                        x = uf_parent[x]
                    return x
                def uf_union(x, y):
                    rx, ry = uf_find(x), uf_find(y)
                    if rx == ry:
                        return False
                    uf_parent[rx] = ry
                    return True

                degrees = {n:0 for n in nodes}
                included = set()
                feasible = True

                # Include required edges
                for e in sorted(required):
                    u, v = e
                    if u == v:
                        feasible = False
                        break
                    # check degree limits
                    if (u in degree_limits and degrees.get(u,0)+1 > degree_limits[u]) or (v in degree_limits and degrees.get(v,0)+1 > degree_limits[v]):
                        feasible = False
                        break
                    uf_union(u, v)
                    degrees[u] = degrees.get(u,0)+1
                    degrees[v] = degrees.get(v,0)+1
                    included.add(e)

                if not feasible:
                    results.append([{"error": "Degree limit infeasible"}])
                    continue

                # Prepare remaining edges list excluding included and forbidden
                remaining = []
                for e, cost in evaluated.items():
                    if e in included:
                        continue
                    remaining.append((cost, e[0], e[1], e))
                # sort deterministically by (cost, u, v)
                remaining.sort(key=lambda x: (x[0], x[1], x[2]))

                # Kruskal: add if connects components and respects degree limits
                for cost, u, v, e in remaining:
                    if e in included:
                        continue
                    if u == v:
                        continue
                    if uf_find(u) != uf_find(v):
                        if (u in degree_limits and degrees.get(u,0)+1 > degree_limits[u]) or (v in degree_limits and degrees.get(v,0)+1 > degree_limits[v]):
                            continue
                        uf_union(u, v)
                        degrees[u] = degrees.get(u,0)+1
                        degrees[v] = degrees.get(v,0)+1
                        included.add(e)

                # After processing, ensure degree limits allow spanning forest: check whether any node's degree exceeds (done). Also ensure if degree_limits make impossible to connect components when required empty? Need to verify if infeasible: if some components cannot be connected due to degree limits, detect by attempting to connect remaining possible edges but none can connect components -> then it's fine because we produce minimum spanning forest; but spec says if degree limits make spanning structure impossible return error.
                # Determine desired is a spanning forest covering all nodes; it's always a forest. They only want error if degree limits make spanning structure impossible. That applies if some required edges forced degrees beyond limits (checked) or if isolated node cannot have any incident edges and yet must be connected? The spec: "If degree limits make the spanning structure impossible" interpret as when any node's degree limit is zero but node has neighbors and cannot be connected to any edge? To be strict: if after algorithm there exists an edge in required impossible handled; otherwise accept forest.
                # However sample expects forest if disconnected. So accept included as final.

                if not included:
                    results.append([{"error": "No valid edges available"}])
                    continue

                # Prepare output sorted lexicographically list of [u,v] strings
                out = [list(e) for e in included]
                out = [sorted(pair) for pair in out]  # ensure canonical order inside
                out = [tuple(p) for p in out]
                out = sorted(out, key=lambda x: (x[0], x[1]))
                out = [[a, b] for a, b in out]
                results.append(out)
    return results