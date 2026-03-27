from typing import List

def analyze_road_network(edges: List[List[int]]) -> List:
    """
    edges: list of [u, v, layer_id] triples (ints)

    Returns a three-element list:
      [physical_layered_articulation_nodes,
       per_layer_articulation_pairs,
       layer_bridging_list]

    - physical_layered_articulation_nodes: List[int]
      Sorted list of node ids whose physical removal disconnects at least one layer.

    - per_layer_articulation_pairs: List[List[int]]
      Each entry is [node, layer_id]; sorted lexicographically by node then layer_id.

    - layer_bridging_list: List[List]
      Each entry is [[u, v], affected_layers_list]. [u, v] are sorted endpoints (u <= v)
      and affected_layers_list is a sorted List[int] of layer ids. The outer list is
      sorted lexicographically by [u, v].
    """

    def _edge_key(u: int, v: int) -> tuple:
        return (u, v) if u <= v else (v, u)
    
    def _count_components(layer_adj_dict, excluded_nodes=None):
        """Count connected components in a layer, optionally excluding nodes."""
        if excluded_nodes is None:
            excluded_nodes = set()
        visited = set()
        component_count = 0
        
        for node in layer_adj_dict.keys():
            if node in excluded_nodes or node in visited:
                continue
            # BFS to mark component
            queue = [node]
            visited.add(node)
            while queue:
                u = queue.pop(0)
                for v in layer_adj_dict.get(u, set()):
                    if v not in excluded_nodes and v not in visited:
                        visited.add(v)
                        queue.append(v)
            component_count += 1
        
        return component_count

    # Initialize structures
    layer_adj = {}  # layer -> node -> set(neighbors)
    layer_pair_count = {}  # (layer, u, v) where u<=v -> count
    edge_layers_map = {}  # (u,v) -> set(layers)

    # Validation: reject adjacency dict, require edge-list only
    if isinstance(edges, dict):
        return "analyze_road_network: input must be an edge-list; convert adjacency dict to edge-list before calling"
    
    if not isinstance(edges, list):
        return "analyze_road_network: edges must be a list of [u, v, layer_id] integer triples"
    
    for i, edge in enumerate(edges):
        if not isinstance(edge, list):
            return f"analyze_road_network: edge at index {i} must be a list of three integers [u, v, layer_id]"
        if len(edge) != 3:
            return f"analyze_road_network: edge at index {i} has invalid length {len(edge)}; expected 3"
        u, v, layer_id = edge
        # type checks
        if not isinstance(u, int):
            return f"analyze_road_network: edge at index {i} contains non-integer component {u!r}"
        if not isinstance(v, int):
            return f"analyze_road_network: edge at index {i} contains non-integer component {v!r}"
        if not isinstance(layer_id, int):
            return f"analyze_road_network: edge at index {i} contains non-integer component {layer_id!r}"
        if layer_id < 0:
            return f"analyze_road_network: edge at index {i} has invalid layer_id {layer_id}; must be >= 0"
        uk, vk = _edge_key(u, v)
        # build adjacency for the layer
        layer_adj.setdefault(layer_id, {}).setdefault(uk, set()).add(vk)
        layer_adj[layer_id].setdefault(vk, set()).add(uk)
        layer_pair_count[(layer_id, uk, vk)] = layer_pair_count.get((layer_id, uk, vk), 0) + 1
        edge_layers_map.setdefault((uk, vk), set()).add(layer_id)

    # Collect all nodes across all layers
    all_nodes = set()
    for layer_dict in layer_adj.values():
        all_nodes.update(layer_dict.keys())

    # Physical articulation nodes: test removal of each node from ALL layers
    physical_articulation_nodes = []
    for node in sorted(all_nodes):
        is_articulation = False
        for layer_id, adj_dict in layer_adj.items():
            if node not in adj_dict:
                continue
            # Count components before and after removing this node
            original_count = _count_components(adj_dict)
            new_count = _count_components(adj_dict, excluded_nodes={node})
            if new_count > original_count:
                is_articulation = True
                break
        if is_articulation:
            physical_articulation_nodes.append(node)

    # Per-layer articulation nodes (for second output)
    per_layer_articulation_pairs = []
    for layer_id, adj_dict in layer_adj.items():
        for node in sorted(adj_dict.keys()):
            original_count = _count_components(adj_dict)
            new_count = _count_components(adj_dict, excluded_nodes={node})
            if new_count > original_count:
                per_layer_articulation_pairs.append([node, layer_id])

    # Layer-bridging roads: test removal of each physical road from ALL layers
    layer_bridging_list = []
    for (u, v) in sorted(edge_layers_map.keys()):
        affected_layers = []
        for layer_id in sorted(edge_layers_map[(u, v)]):
            # Create temporary adjacency without edge (u,v)
            temp_adj = {}
            for node, neighbors in layer_adj[layer_id].items():
                temp_adj[node] = neighbors.copy()
            
            # Remove edge (u,v) from temp adjacency
            if u in temp_adj and v in temp_adj[u]:
                temp_adj[u].discard(v)
            if v in temp_adj and u in temp_adj[v]:
                temp_adj[v].discard(u)
            
            # Check if multiplicity > 1 (parallel edges in same layer)
            multiplicity = layer_pair_count.get((layer_id, u, v), 0)
            if multiplicity > 1:
                # Still connected via parallel edge, not a bridge
                continue
            
            # Count components before and after
            original_count = _count_components(layer_adj[layer_id])
            new_count = _count_components(temp_adj)
            
            if new_count > original_count:
                affected_layers.append(layer_id)
        
        layer_bridging_list.append([[u, v], affected_layers])

    return [physical_articulation_nodes, per_layer_articulation_pairs, layer_bridging_list]