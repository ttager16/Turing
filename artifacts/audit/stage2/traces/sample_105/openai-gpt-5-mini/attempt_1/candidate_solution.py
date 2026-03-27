def analyze_road_network(edges: List[List[int]]) -> List:
    # Input validation
    if not isinstance(edges, list):
        return "analyze_road_network: edges must be a list of [u, v, layer_id] integer triples"
    # detect adjacency-dict like: someone passed a dict disguised as list? specifically check if edges is dict
    if isinstance(edges, dict):
        return "analyze_road_network: input must be an edge-list; convert adjacency dict to edge-list before calling"
    for i, e in enumerate(edges):
        if not isinstance(e, list):
            return f"analyze_road_network: edge at index {i} must be a list of three integers [u, v, layer_id]"
        if len(e) != 3:
            return f"analyze_road_network: edge at index {i} has invalid length {len(e)}; expected 3"
        for comp in e:
            if not isinstance(comp, int):
                return f"analyze_road_network: edge at index {i} contains non-integer component {comp!r}"
        layer_id = e[2]
        if layer_id < 0:
            return f"analyze_road_network: edge at index {i} has invalid layer_id {layer_id}; must be >= 0"

    # Build per-layer graphs and set of nodes and physical roads mapping
    nodes: Set[int] = set()
    layer_edges: Dict[int, Dict[int, Set[int]]] = {}  # layer -> adjacency dict u->set(neigh)
    physical_roads: Dict[Tuple[int,int], Set[int]] = {}  # (u,v) with u<=v -> set of layers present

    for u, v, layer in edges:
        nodes.add(u); nodes.add(v)
        if layer not in layer_edges:
            layer_edges[layer] = {}
        adj = layer_edges[layer]
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)
        a, b = (u, v) if u <= v else (v, u)
        physical_roads.setdefault((a,b), set()).add(layer)

    # helper: articulation points for an undirected graph adjacency dict
    def compute_articulations(adj: Dict[int, Set[int]]) -> Set[int]:
        visited: Set[int] = set()
        disc: Dict[int, int] = {}
        low: Dict[int, int] = {}
        parent: Dict[int, int] = {}
        ap: Set[int] = set()
        time = 0

        def dfs(u: int):
            nonlocal time
            visited.add(u)
            disc[u] = time
            low[u] = time
            time += 1
            children = 0
            for v in adj.get(u, ()):
                if v not in visited:
                    parent[v] = u
                    children += 1
                    dfs(v)
                    low[u] = min(low[u], low[v])
                    if u not in parent and children > 1:
                        ap.add(u)
                    if u in parent and low[v] >= disc[u]:
                        ap.add(u)
                elif parent.get(u) != v:
                    low[u] = min(low[u], disc[v])
        for vertex in adj.keys():
            if vertex not in visited:
                dfs(vertex)
        return ap

    # compute per-layer articulation pairs
    per_layer_art_pairs: List[List[int]] = []
    layer_to_aps: Dict[int, Set[int]] = {}
    for layer, adj in layer_edges.items():
        aps = compute_articulations(adj)
        layer_to_aps[layer] = aps
        for node in aps:
            per_layer_art_pairs.append([node, layer])
    per_layer_art_pairs.sort(key=lambda x: (x[0], x[1]))

    # compute physical_layered_articulation_nodes:
    physical_art_nodes_set: Set[int] = set()
    # A node is physical-articulation if removing it (and all incident edges across all layers)
    # increases component count in at least one layer.
    # For each layer, if node is an articulation in that layer's subgraph (i.e., in layer_to_aps), then it's counted.
    for layer, aps in layer_to_aps.items():
        for n in aps:
            physical_art_nodes_set.add(n)
    physical_layered_articulation_nodes = sorted(physical_art_nodes_set)

    # For layer_bridging_list: for each physical road r=(u,v), compute affected layers where removing r (all instances) increases components in that layer.
    layer_bridging_list: List[List] = []
    # Helper to compute number of components in a layer given adjacency
    def count_components(adj: Dict[int, Set[int]]) -> int:
        visited = set()
        comps = 0
        for node in adj.keys():
            if node not in visited:
                comps += 1
                stack = [node]
                visited.add(node)
                while stack:
                    x = stack.pop()
                    for y in adj.get(x, ()):
                        if y not in visited:
                            visited.add(y)
                            stack.append(y)
        return comps

    for (u, v) in sorted(physical_roads.keys()):
        affected_layers: List[int] = []
        layers_present = physical_roads[(u, v)]
        # For all layers that exist in input (even if this road not present in that layer), removing physical road removes any instances between u,v (none if absent).
        # But definition requires affected layers L such that removing the physical road r increases number of connected components in layer l for each l in L.
        for layer in sorted(layer_edges.keys()):
            # build adjacency copy for this layer with physical road removed
            adj_original = layer_edges[layer]
            # count components before
            comps_before = count_components(adj_original)
            # build modified adjacency: if u-v edge exists in this layer, remove it
            # create shallow copies of adjacency sets
            adj_mod: Dict[int, Set[int]] = {}
            for node, neighs in adj_original.items():
                adj_mod[node] = set(neighs)
            if u in adj_mod and v in adj_mod[u]:
                adj_mod[u].remove(v)
            if v in adj_mod and u in adj_mod[v]:
                adj_mod[v].remove(u)
            comps_after = count_components(adj_mod)
            if comps_after > comps_before:
                affected_layers.append(layer)
        affected_layers.sort()
        layer_bridging_list.append([[u, v], affected_layers])

    # sort outputs as required
    return [physical_layered_articulation_nodes, per_layer_art_pairs, layer_bridging_list]