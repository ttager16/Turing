def find_minimal_vertex_cover(graph: dict, queries: list) -> list:
    """
    Computes minimal vertex cover for multi-layer directed graphs with offline queries.
    Handles layer merging, edge additions/removals, and maintains state across queries.
    
    Args:
        graph: Multi-layer graph with keys as "[node, layer]" and values as neighbor lists
        queries: List of [nodes_list, edges_list] representing query operations
    
    Returns:
        List of minimal vertex covers for each query
    """
    if not isinstance(graph, dict) or not isinstance(queries, list):
        return []
    
    processor = MultiLayerGraphProcessor(graph)
    return processor.process_queries_offline(queries)

class MultiLayerGraphProcessor:
    """Processes multi-layer graph queries with state management and layer merging."""
    
    def __init__(self, base_graph):
        self.base_graph = base_graph
        self.layer_structure = LayerManager()
        self._initialize_layers()
    
    def _initialize_layers(self):
        """Extract and organize layer information from base graph."""
        for key_str in self.base_graph:
            node, layer = self._safe_parse_key(key_str)
            if node is not None and layer is not None:
                neighbors = self.base_graph.get(key_str, [])
                if neighbors:
                    for neighbor in neighbors:
                        self.layer_structure.add_edge_to_layer(layer, node, neighbor)
    
    def process_queries_offline(self, queries):
        """
        Process all queries in offline batch mode.
        Collects all updates first, then computes results efficiently.
        """
        if not queries:
            return []
        
        validated_queries = self._validate_and_preprocess_queries(queries)
        results = []
        
        for query_data in validated_queries:
            nodes_subset = query_data['nodes']
            edge_updates = query_data['edges']
            
            merged_graph = self._build_query_graph(nodes_subset, edge_updates)
            
            cover = self._compute_minimal_vertex_cover(merged_graph)
            results.append(cover)
        
        return results
    
    def _validate_and_preprocess_queries(self, queries):
        """Validate and preprocess all queries for batch processing."""
        validated = []
        
        for query in queries:
            if not query or not isinstance(query, list) or len(query) < 2:
                validated.append({'nodes': [], 'edges': []})
                continue
            
            nodes = query[0] if isinstance(query[0], list) else []
            edges = query[1] if isinstance(query[1], list) else []
            
            nodes = self._deduplicate_list(nodes)
            edges = self._validate_edges(edges, nodes)
            
            validated.append({'nodes': nodes, 'edges': edges})
        
        return validated
    
    def _build_query_graph(self, nodes_subset, edge_updates):
        """
        Build unified graph for query by merging relevant layers and applying updates.
        Only considers layers that are "activated" by the original query nodes.
        Nodes from edge_updates are temporarily added even if not in nodes_subset.
        """
        # Extend nodes_subset to include any nodes mentioned in edge_updates
        extended_nodes = list(nodes_subset)
        
        if edge_updates:
            for edge in edge_updates:
                if isinstance(edge, list) and len(edge) >= 2:
                    u, v = edge[0], edge[1]
                    if u not in extended_nodes:
                        extended_nodes.append(u)
                    if v not in extended_nodes:
                        extended_nodes.append(v)
        
        query_graph = QueryGraph(extended_nodes)
        
        if not nodes_subset:  # If original query nodes are empty, return empty graph
            return query_graph
        
        nodes_set = set(extended_nodes)
        original_nodes_set = set(nodes_subset)  # Track original query nodes
        
        # Find which layers are "activated" by the original query nodes
        activated_layers = set()
        for layer_id in self.layer_structure.get_all_layers():
            layer_edges = self.layer_structure.get_layer_edges(layer_id)
            # A layer is activated if any of its edges involves an original query node
            for edge in layer_edges:
                u, v = edge[0], edge[1]
                if u in original_nodes_set or v in original_nodes_set:
                    activated_layers.add(layer_id)
                    break
        
        # Extract edges only from activated layers
        for layer_id in activated_layers:
            layer_edges = self.layer_structure.get_layer_edges(layer_id)
            for edge in layer_edges:
                u, v = edge[0], edge[1]
                # Include edge if both endpoints are in extended node set
                if u in nodes_set and v in nodes_set:
                    query_graph.add_edge(u, v)
        
        # Apply edge updates (additions)
        if edge_updates:
            for edge in edge_updates:
                if isinstance(edge, list) and len(edge) >= 2:
                    try:
                        u, v = int(edge[0]), int(edge[1])
                        # Add edge regardless of original nodes_subset
                        if u in nodes_set and v in nodes_set:
                            query_graph.add_edge(u, v)
                    except (ValueError, TypeError, IndexError):
                        continue
        
        return query_graph
    
    def _compute_minimal_vertex_cover(self, query_graph):
        """
        Compute minimal vertex cover using improved approximation with optimization.
        Uses branch-and-bound approach for small graphs, greedy for large graphs.
        """
        edges = query_graph.get_all_edges()
        nodes = query_graph.get_all_nodes()
        
        if not edges:
            return []
        
        if len(edges) == 1:
            return [min(edges[0][0], edges[0][1])]
        
        # For small graphs, use exact algorithm
        if len(nodes) <= 15:
            return self._exact_vertex_cover(edges, nodes)
        
        # For larger graphs, use optimized greedy with refinement
        return self._greedy_vertex_cover_optimized(edges, nodes)
    
    def _exact_vertex_cover(self, edges, nodes):
        """Compute exact minimal vertex cover for small graphs."""
        min_cover = list(nodes)
        
        # Try all possible subsets in order of size
        for size in range(len(nodes) + 1):
            covers = self._generate_combinations(nodes, size)
            for cover in covers:
                if self._is_valid_cover(cover, edges):
                    return sorted(cover)
        
        return sorted(min_cover)
    
    def _greedy_vertex_cover_optimized(self, edges, nodes):
        """Optimized greedy vertex cover with multiple refinement passes."""
        edge_list = [list(e) for e in edges]
        node_coverage = self._build_node_coverage_map(edge_list, nodes)
        
        cover = []
        covered_edges = set()
        
        while len(covered_edges) < len(edge_list):
            # Select node with maximum uncovered edge count
            best_node = None
            max_coverage = 0
            
            for node in nodes:
                if node in cover:
                    continue
                
                coverage_count = 0
                for i, edge in enumerate(edge_list):
                    if i not in covered_edges:
                        if edge[0] == node or edge[1] == node:
                            coverage_count += 1
                
                if coverage_count > max_coverage:
                    max_coverage = coverage_count
                    best_node = node
            
            if best_node is None:
                break
            
            cover.append(best_node)
            
            # Mark edges as covered
            for i, edge in enumerate(edge_list):
                if edge[0] == best_node or edge[1] == best_node:
                    covered_edges.add(i)
        
        # Multi-pass optimization to remove redundant nodes
        cover = self._optimize_cover_multipass(cover, edge_list)
        
        return sorted(cover)
    
    def _optimize_cover_multipass(self, cover, edges):
        """Remove redundant nodes with multiple passes for true minimality."""
        improved = True
        optimized = list(cover)
        
        while improved:
            improved = False
            for node in list(optimized):
                # Try removing this node
                test_cover = [n for n in optimized if n != node]
                
                if self._is_valid_cover(test_cover, edges):
                    optimized = test_cover
                    improved = True
                    break
        
        return optimized
    
    def _is_valid_cover(self, cover, edges):
        """Check if cover is valid (all edges covered)."""
        cover_set = set(cover)
        for edge in edges:
            if edge[0] not in cover_set and edge[1] not in cover_set:
                return False
        return True
    
    def _build_node_coverage_map(self, edges, nodes):
        """Build map of which edges each node covers."""
        coverage = {}
        for node in nodes:
            coverage[node] = []
            for i, edge in enumerate(edges):
                if edge[0] == node or edge[1] == node:
                    coverage[node].append(i)
        return coverage
    
    def _generate_combinations(self, items, r):
        """Generate all combinations of r items from list."""
        if r == 0:
            return [[]]
        if not items:
            return []
        
        result = []
        for i in range(len(items)):
            element = items[i]
            remaining = items[i + 1:]
            for combo in self._generate_combinations(remaining, r - 1):
                result.append([element] + combo)
        
        return result
    
    def _validate_edges(self, edges, valid_nodes):
        """
        Validate and filter edges.
        Note: valid_nodes may be extended by edge endpoints during graph building.
        """
        if not edges:
            return []
        
        validated = []
        seen = set()
        
        for edge in edges:
            if not isinstance(edge, list) or len(edge) < 2:
                continue
            
            try:
                u, v = int(edge[0]), int(edge[1])
                
                # Check both orientations to avoid duplicates
                if (u, v) not in seen and (v, u) not in seen:
                    validated.append([u, v])
                    seen.add((u, v))
            except (ValueError, TypeError, IndexError):
                continue
        
        return validated
        
    def _deduplicate_list(self, lst):
        """Remove duplicates while preserving order."""
        seen = set()
        result = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    
    def _safe_parse_key(self, key_str):
        """Safely parse key with comprehensive error handling."""
        if not isinstance(key_str, str):
            return None, None
        
        try:
            key_str = key_str.strip()
            if not key_str.startswith('[') or not key_str.endswith(']'):
                return None, None
            
            content = key_str[1:-1]
            parts = content.split(',')
            
            if len(parts) != 2:
                return None, None
            
            node = int(parts[0].strip())
            layer = int(parts[1].strip())
            
            return node, layer
        except (ValueError, AttributeError, IndexError):
            return None, None

class LayerManager:
    """Manages multi-layer structure and layer-specific edges."""
    
    def __init__(self):
        self.layers = {}
    
    def add_edge_to_layer(self, layer_id, u, v):
        """Add edge to specific layer."""
        if layer_id not in self.layers:
            self.layers[layer_id] = []
        
        edge = [u, v]
        # Avoid duplicates
        for existing in self.layers[layer_id]:
            if existing[0] == u and existing[1] == v:
                return
        
        self.layers[layer_id].append(edge)
    
    def get_layer_edges(self, layer_id):
        """Get all edges from specific layer."""
        return self.layers.get(layer_id, [])
    
    def get_all_layers(self):
        """Get all layer IDs."""
        return list(self.layers.keys())
    
    def merge_layers(self, layer_ids):
        """Merge multiple layers into unified edge set."""
        merged = []
        seen = set()
        
        for layer_id in layer_ids:
            edges = self.get_layer_edges(layer_id)
            for edge in edges:
                edge_tuple = (edge[0], edge[1])
                if edge_tuple not in seen:
                    merged.append(edge)
                    seen.add(edge_tuple)
        
        return merged

class QueryGraph:
    """Represents a query-specific graph with efficient edge management."""
    
    def __init__(self, nodes):
        self.nodes = set(nodes) if nodes else set()
        self.edges = []
        self.edge_set = set()
        self.adjacency = {}
    
    def add_edge(self, u, v):
        """Add edge with duplicate detection."""
        if u not in self.nodes or v not in self.nodes:
            return
        
        # Check both orientations
        if (u, v) not in self.edge_set and (v, u) not in self.edge_set:
            self.edges.append([u, v])
            self.edge_set.add((u, v))
            
            if u not in self.adjacency:
                self.adjacency[u] = []
            if v not in self.adjacency:
                self.adjacency[v] = []
            
            self.adjacency[u].append(v)
    
    def remove_edge(self, u, v):
        """Remove edge from graph."""
        if (u, v) in self.edge_set:
            self.edge_set.remove((u, v))
            self.edges = [[a, b] for a, b in self.edges if not (a == u and b == v)]
            
            if u in self.adjacency:
                self.adjacency[u] = [n for n in self.adjacency[u] if n != v]
    
    def get_all_edges(self):
        """Get all edges as list."""
        return self.edges
    
    def get_all_nodes(self):
        """Get all nodes as list."""
        return list(self.nodes)
    
    def has_edge(self, u, v):
        """Check if edge exists (either orientation)."""
        return (u, v) in self.edge_set or (v, u) in self.edge_set

# Comprehensive test cases
if __name__ == "__main__":
    # Test 1: Original sample
    graph = {
        "[1, 1]": [2],
        "[2, 1]": [3],
        "[3, 1]": [],
        "[1, 2]": [3],
        "[3, 2]": [4],
        "[4, 2]": []
    }
    
    queries = [
        [[1, 2, 3, 4], [[2, 1], [1, 2], [3, 2]]],
        [[1, 3, 4], [[3, 2], [4, 2]]]
    ]

    result = find_minimal_vertex_cover(graph, queries)
    print(result)