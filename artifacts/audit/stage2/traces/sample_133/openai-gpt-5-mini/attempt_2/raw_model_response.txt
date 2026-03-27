def find_minimal_vertex_cover(graph: dict, queries: list) -> list:
    from itertools import combinations
    # parse input graph: keys like "[node, layer]" -> edges node->v
    layer_edges = []
    for k, vs in graph.items():
        try:
            s = k.strip()
            if s.startswith("[") and s.endswith("]"):
                inside = s[1:-1]
                node_str, layer_str = inside.split(",")
                node = int(node_str.strip())
            else:
                node = int(k)
        except Exception:
            continue
        layer_edges.append((node, list(vs)))
    results = []
    for qnodes, qedges in queries:
        # collect relevant layers: any layer containing at least one node referenced by qnodes
        qset = set(qnodes)
        edges_set = set()
        nodes_set = set(qnodes)
        for src, vs in layer_edges:
            if src in qset:
                for v in vs:
                    edges_set.add((min(src, v), max(src, v)))
                    nodes_set.add(src); nodes_set.add(v)
            else:
                # also if any destination in vs is in qset, the layer contains that node as key? spec says layer entry recorded as [node,layer]: [v1...]
                # only include layers that contain at least one node referenced by the query; that includes src in qset
                pass
        # apply query updates (directed edges) add as undirected pairs, add nodes if new
        for u, v in qedges:
            nodes_set.add(u); nodes_set.add(v)
            edges_set.add((min(u, v), max(u, v)))
        # build adjacency list undirected
        nodes = sorted(nodes_set)
        idx = {n:i for i,n in enumerate(nodes)}
        n = len(nodes)
        adj = [set() for _ in range(n)]
        for a,b in edges_set:
            if a==b: continue
            ia, ib = idx[a], idx[b]
            adj[ia].add(ib); adj[ib].add(ia)
        # If no edges, cover is empty
        if all(len(ne)==0 for ne in adj):
            results.append([])
            continue
        # If small graph (<=40 nodes) attempt exact minimal vertex cover via bitmask or backtracking
        if n <= 40:
            best = None
            # list edges as index pairs
            edge_list = []
            for i in range(n):
                for j in adj[i]:
                    if i<j:
                        edge_list.append((i,j))
            m = len(edge_list)
            # try increasing sizes
            for ksize in range(0, n+1):
                found = False
                for comb in combinations(range(n), ksize):
                    s = set(comb)
                    ok = True
                    for u,v in edge_list:
                        if u not in s and v not in s:
                            ok = False; break
                    if ok:
                        best = [nodes[i] for i in sorted(s)]
                        found = True
                        break
                if found:
                    break
            results.append(best if best is not None else [])
        else:
            # 2-approx via maximal matching
            matched = [False]*n
            cover = set()
            for u in range(n):
                if matched[u]: continue
                for v in adj[u]:
                    if not matched[v]:
                        matched[u]=matched[v]=True
                        cover.add(nodes[u]); cover.add(nodes[v])
                        break
            results.append(sorted(cover))
    return results