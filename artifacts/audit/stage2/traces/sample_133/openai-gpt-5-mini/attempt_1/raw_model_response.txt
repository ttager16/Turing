def find_minimal_vertex_cover(graph: dict, queries: list) -> list:
    from itertools import combinations

    # Parse layers: map layer_id -> dict(node -> set(dest))
    layers = {}
    for k, dests in graph.items():
        # keys are strings like "[1, 1]" or could be list/list-like; handle string form
        if isinstance(k, str):
            try:
                # safe parse assuming format "[node, layer]"
                s = k.strip()
                if s.startswith('[') and s.endswith(']'):
                    a, b = s[1:-1].split(',')
                    node = int(a.strip())
                    layer = int(b.strip())
                else:
                    continue
            except Exception:
                continue
        elif isinstance(k, (list, tuple)) and len(k) == 2:
            node, layer = int(k[0]), int(k[1])
        else:
            continue
        layers.setdefault(layer, {}).setdefault(node, set()).update(int(v) for v in dests)

    results = []

    for q_nodes, q_updates in queries:
        # set of nodes referenced in query (initial)
        qnode_set = set(int(x) for x in q_nodes)
        # collect edges from any layer that contains at least one node referenced by the query
        directed_edges = set()
        # include edges from layers where any layer node is in qnode_set
        for layer_dict in layers.values():
            # if any node in this layer_dict intersects qnode_set
            if any(node in qnode_set for node in layer_dict.keys()):
                for u, dests in layer_dict.items():
                    for v in dests:
                        directed_edges.add((int(u), int(v)))
        # apply query updates (add edges)
        for e in q_updates:
            if not e:
                continue
            u, v = int(e[0]), int(e[1])
            directed_edges.add((u, v))
            # ensure temporarily added nodes are considered
            qnode_set.add(u)
            qnode_set.add(v)
        # build undirected edge set
        undirected = set()
        nodes_set = set()
        for u, v in directed_edges:
            a, b = (u, v) if u <= v else (v, u)
            undirected.add((a, b))
            nodes_set.add(u); nodes_set.add(v)
        # also ensure nodes from q_nodes present even if isolated
        nodes_set.update(qnode_set)

        # If no edges, minimal cover is empty list
        if not undirected:
            results.append([])
            continue

        n = len(nodes_set)
        # Map nodes to indices for bitmasking if small
        nodes_list = sorted(nodes_set)
        idx = {node: i for i, node in enumerate(nodes_list)}

        # If small (<=40), do exact via bitmask search (branch and bound over increasing size)
        if n <= 40:
            # Precompute edge masks
            edge_masks = []
            for u, v in undirected:
                m = (1 << idx[u]) | (1 << idx[v])
                edge_masks.append(m)
            total_edges = len(edge_masks)

            # Try increasing sizes
            found_cover = None
            for k in range(0, n + 1):
                # iterate combinations of indices of size k
                for comb in combinations(range(n), k):
                    mask = 0
                    for i in comb:
                        mask |= (1 << i)
                    ok = True
                    for em in edge_masks:
                        if (mask & em) == 0:
                            ok = False
                            break
                    if ok:
                        found_cover = [nodes_list[i] for i in comb]
                        break
                if found_cover is not None:
                    break
            results.append(found_cover if found_cover is not None else [])
        else:
            # Approximation 2-approx via greedy maximal matching
            remaining = set(undirected)
            cover = set()
            # build adjacency for quick removal
            adj = {}
            for u, v in undirected:
                adj.setdefault(u, set()).add(v)
                adj.setdefault(v, set()).add(u)
            while remaining:
                # take arbitrary edge
                u, v = next(iter(remaining))
                cover.add(u); cover.add(v)
                # remove all edges incident to u or v
                to_remove = []
                for x, y in list(remaining):
                    if x == u or x == v or y == u or y == v:
                        remaining.discard((x, y))
                # continue
            results.append(sorted(cover))
    return results