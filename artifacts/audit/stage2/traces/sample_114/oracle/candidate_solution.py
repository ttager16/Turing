# main.py
from collections import deque, defaultdict


class LayeredGraph:
    """
    Multi-layer flow graph representation with dynamic capacity management.
    """

    def __init__(self, graph_data: dict) -> None:
        """
        Initialize layered graph from input data.
        graph_data: Dict mapping node_id (str) to list of [neighbor, capacity, cost]
        """
        self.graph = defaultdict(list)
        self.nodes = set()
        self.layers = defaultdict(list)

        # Parse graph and identify layers
        for node_str, edges in graph_data.items():
            node = int(node_str)
            self.nodes.add(node)

            for edge in edges:
                neighbor, capacity, cost = edge[0], edge[1], edge[2]
                self.graph[node].append({
                    'neighbor': neighbor,
                    'capacity': capacity,
                    'cost': cost,
                    'original_capacity': capacity
                })
                self.nodes.add(neighbor)

        # Assign layers using topological ordering
        self._assign_layers()

    def _assign_layers(self) -> None:
        """Assign nodes to layers using BFS-based topological ordering with cycle handling."""
        if not self.nodes:
            return

        # Calculate in-degree
        in_degree = defaultdict(int)
        for node in self.nodes:
            for edge in self.graph[node]:
                in_degree[edge['neighbor']] += 1

        # Find source nodes (in-degree 0)
        sources = [node for node in self.nodes if in_degree[node] == 0]
        if not sources:
            # If no sources, use minimum node as source
            sources = [min(self.nodes)]

        # BFS to assign layers with cycle detection and prevention
        queue = deque([(s, 0) for s in sources])
        layer_assignment = {}
        max_iterations = len(self.nodes) * len(self.nodes)  # Prevent infinite loops
        iteration = 0

        while queue and iteration < max_iterations:
            iteration += 1
            node, layer = queue.popleft()

            # Update to maximum layer if visited multiple times
            if node in layer_assignment:
                if layer > layer_assignment[node]:
                    # Limit layer growth to prevent infinite cycles
                    if layer - layer_assignment[node] > len(self.nodes):
                        continue  # Skip excessive layer growth
                    layer_assignment[node] = layer
                else:
                    continue  # Skip if we've already processed this node at a higher or equal layer
            else:
                layer_assignment[node] = layer

            for edge in self.graph[node]:
                neighbor = edge['neighbor']
                new_layer = layer + 1
                # Only add to queue if it would result in a reasonable layer assignment
                if neighbor not in layer_assignment or (new_layer > layer_assignment[neighbor] and new_layer < len(self.nodes) * 2):
                    queue.append((neighbor, new_layer))

        # Organize nodes by layer
        for node, layer in layer_assignment.items():
            self.layers[layer].append(node)

        # Handle nodes not reached in BFS - place one layer beyond current maximum
        unreachable_nodes = [node for node in self.nodes if node not in layer_assignment]
        if unreachable_nodes:
            max_layer = max(self.layers.keys()) if self.layers else 0
            for node in unreachable_nodes:
                self.layers[max_layer + 1].append(node)

    def get_capacity(self, node: int, neighbor: int) -> float:
        """Get current capacity of edge from node to neighbor."""
        for edge in self.graph[node]:
            if edge['neighbor'] == neighbor:
                return edge['capacity']
        return 0

    def get_edge_cost(self, node: int, neighbor: int) -> float:
        """Get cost of edge from node to neighbor."""
        for edge in self.graph[node]:
            if edge['neighbor'] == neighbor:
                return edge['cost']
        return float('inf')


class DFSFlowOptimizer:
    """
    DFS-based flow optimization with multi-stage analysis.
    Implements path finding and flow calculation across layered graphs.
    """

    def __init__(self, layered_graph: LayeredGraph) -> None:
        self.graph = layered_graph
        self.best_paths = []

    def _dfs_find_paths(self, node: int, target: int, visited: set, path: list, min_capacity: float, total_cost: float) -> None:
        """
        DFS to find all feasible paths from node to target.
        Tracks minimum capacity and total cost along the path.
        """
        visited.add(node)
        path.append(node)

        if node == target:
            # Found a complete path
            self.best_paths.append({
                'path': path[:],
                'capacity': min_capacity,
                'cost': total_cost
            })
        else:
            # Continue exploring
            for edge in self.graph.graph[node]:
                neighbor = edge['neighbor']
                capacity = edge['capacity']
                cost = edge['cost']

                if neighbor not in visited and capacity > 0:
                    new_min_capacity = min(min_capacity, capacity)
                    new_total_cost = total_cost + cost

                    self._dfs_find_paths(
                        neighbor, target, visited, path,
                        new_min_capacity, new_total_cost
                    )

        path.pop()
        visited.remove(node)

    def compute_max_flow_min_cost(self, source: int, sink: int) -> tuple:
        """
        Compute maximum flow with minimum cost using successive augmentation.
        Implements Ford-Fulkerson method with DFS for augmenting paths.

        Returns:
            tuple: (optimal_path, total_flow, optimal_path_flow)
        """
        # Special case: source equals sink
        if source == sink:
            return [source], None, None

        total_flow = 0
        total_cost = 0
        all_augmenting_paths = []

        # Create working copy of graph (residual graph)
        residual = defaultdict(dict)
        for node in self.graph.nodes:
            for edge in self.graph.graph[node]:
                neighbor = edge['neighbor']
                capacity = edge['capacity']
                cost = edge['cost']
                residual[node][neighbor] = {
                    'capacity': capacity,
                    'cost': cost
                }

        max_iterations = 100  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Find all augmenting paths using DFS
            all_paths = self._find_all_augmenting_paths(residual, source, sink)

            if not all_paths:
                break

            # Sort by flow descending, then cost ascending, and choose highest-ranked
            all_paths.sort(key=lambda x: (-x['flow'], x['cost']))
            best_path_info = all_paths[0]

            path = best_path_info['path']
            flow = best_path_info['flow']
            path_cost = best_path_info['cost']

            # Track this augmenting path
            all_augmenting_paths.append({
                'path': path[:],
                'flow': flow,
                'cost': path_cost
            })

            # Update residual graph
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]

                # Get the edge cost for reverse edge
                edge_cost = residual[u][v]['cost']

                # Reduce forward edge capacity
                residual[u][v]['capacity'] -= flow

                # Remove edge if capacity becomes zero
                if residual[u][v]['capacity'] == 0:
                    del residual[u][v]

                # Add reverse edge with negated cost of that specific edge
                if v not in residual:
                    residual[v] = {}
                if u not in residual[v]:
                    residual[v][u] = {'capacity': 0, 'cost': -edge_cost}
                residual[v][u]['capacity'] += flow

            total_flow += flow
            total_cost += flow * path_cost

        # Select the optimal path - the one with highest flow, then lowest cost
        if all_augmenting_paths:
            all_augmenting_paths.sort(key=lambda x: (-x['flow'], x['cost']))
            best_path = all_augmenting_paths[0]['path']
            best_path_flow = all_augmenting_paths[0]['flow']
            return best_path, total_flow, best_path_flow

        return [], 0, 0

    def _find_all_augmenting_paths(self, residual: dict, source: int, sink: int) -> list:
        """Find all augmenting paths in residual graph using DFS."""
        all_paths = []

        def dfs(node: int, target: int, visited: set, path: list, min_cap: float, total_cost: float):
            visited.add(node)
            path.append(node)

            if node == target:
                # Found a complete path
                all_paths.append({
                    'path': path[:],
                    'flow': min_cap,
                    'cost': total_cost
                })
            else:
                if node in residual:
                    for neighbor, edge_info in residual[node].items():
                        capacity = edge_info['capacity']
                        cost = edge_info['cost']

                        if neighbor not in visited and capacity > 0:
                            dfs(neighbor, target, visited, path,
                                min(min_cap, capacity), total_cost + cost)

            path.pop()
            visited.remove(node)

        dfs(source, sink, set(), [], float('inf'), 0)
        return all_paths


def optimize_logistics_network(graph_input: dict) -> dict:
    """
    Main entry point for multi-tier logistics network optimization.

    Args:
        graph_input: Dictionary with:
            - 'graph': Dict mapping node_id (str) to list of [neighbor, capacity, cost]
            - Optional: 'source': source node id (default: 0)
            - Optional: 'sink': sink node id (default: max node)
            - Optional: 'analyze_all_paths': boolean to analyze multiple paths

    Returns:
        Dictionary with:
            - 'optimal_path': List of node IDs representing the best path
            - 'max_throughput': Maximum achievable flow value
            - 'total_cost': Total cost of the optimal solution
            - 'layers': Layer assignment of nodes
            - 'num_layers': Total number of layers
            - 'alternative_paths': List of other viable paths (if analyze_all_paths=True)
            - 'bottleneck_nodes': Nodes with critical capacity constraints
            - 'capacity_utilization': Percentage of capacity used on optimal path
            - 'cost_efficiency': Throughput per unit cost ratio
            - 'path_length': Number of hops in optimal path
            - 'avg_edge_capacity': Average capacity across path edges
            - 'layer_distribution': Distribution of nodes across layers
            - 'flow_efficiency': Flow relative to theoretical maximum
    """
    # Parse input
    if isinstance(graph_input, dict) and 'graph' in graph_input:
        graph_data = graph_input['graph']
        source = graph_input.get('source', 0)
        sink = graph_input.get('sink', None)
        analyze_all = graph_input.get('analyze_all_paths', False)
    else:
        return {"error": "Invalid input format"}

    # Validate data
    if not isinstance(graph_data, dict):
        return {"error": "Graph data must be a dictionary"}
    if any(not isinstance(k, str) or not isinstance(v, list) for k, v in graph_data.items()):
        return {"error": "Graph data must map string node IDs to lists of edges"}

    # Collect all nodes including neighbors
    all_nodes = set()
    for node_str, edges in graph_data.items():
        all_nodes.add(int(node_str))
        for edge in edges:
            all_nodes.add(edge[0])

    if source not in all_nodes:
        return {"error": "Source node not found in graph"}
    if sink is not None and sink not in all_nodes:
        return {"error": "Sink node not found in graph"}
    if not isinstance(analyze_all, bool):
        return {"error": "analyze_all_paths must be a boolean"}

    # Build layered graph
    layered_graph = LayeredGraph(graph_data)

    # Determine sink if not provided
    if sink is None:
        if layered_graph.nodes:
            sink = max(layered_graph.nodes)
        else:
            sink = 0

    # Initialize DFS optimizer
    optimizer = DFSFlowOptimizer(layered_graph)

    # Compute optimal flow
    optimal_path, max_flow, optimal_path_flow = optimizer.compute_max_flow_min_cost(source, sink)

    # Calculate total cost
    total_cost = 0
    for i in range(len(optimal_path) - 1):
        u, v = optimal_path[i], optimal_path[i + 1]
        total_cost += layered_graph.get_edge_cost(u, v)

    # Prepare layer information
    layers_dict = {}
    for layer_num in sorted(layered_graph.layers.keys()):
        layers_dict[str(layer_num)] = sorted(layered_graph.layers[layer_num])

    # Analyze bottlenecks
    bottleneck_nodes = []
    min_capacity = float('inf')
    edge_capacities = []

    for i in range(len(optimal_path) - 1):
        u, v = optimal_path[i], optimal_path[i + 1]
        cap = layered_graph.get_capacity(u, v)
        edge_capacities.append(cap)

        if cap < min_capacity:
            min_capacity = cap
            bottleneck_nodes = [u]
        elif cap == min_capacity:
            bottleneck_nodes.append(u)

    # Calculate metrics

    # 1. Capacity Utilization: How much of the path capacity is being used
    total_path_capacity = sum(edge_capacities) if edge_capacities else 0
    # Use the flow that went through the optimal_path, not the total network flow
    path_flow = optimal_path_flow if optimal_path_flow is not None else 0
    capacity_utilization = round((path_flow * len(edge_capacities) / total_path_capacity * 100), 2) if total_path_capacity > 0 else 0.0

    # 2. Cost Efficiency: Throughput per unit cost (using total network flow)
    cost_efficiency = round(max_flow / total_cost, 4) if (total_cost > 0 and max_flow is not None) else None

    # 3. Path Length: Number of hops
    path_length = len(optimal_path) - 1 if len(optimal_path) > 1 else 0

    # 4. Average Edge Capacity: Average capacity across path edges
    avg_edge_capacity = round(sum(edge_capacities) / len(edge_capacities), 2) if edge_capacities else 0.0

    # 5. Layer Distribution: Nodes per layer statistics
    layer_sizes = [len(nodes) for nodes in layered_graph.layers.values()]
    layer_distribution = {
        'min_nodes_per_layer': min(layer_sizes) if layer_sizes else 0,
        'max_nodes_per_layer': max(layer_sizes) if layer_sizes else 0,
        'avg_nodes_per_layer': round(sum(layer_sizes) / len(layer_sizes), 2) if layer_sizes else 0.0
    }

    # 6. Flow Efficiency: Actual flow vs theoretical maximum (min bottleneck)
    theoretical_max = min_capacity if min_capacity != float('inf') else 0
    # Use the flow that went through the optimal_path, not the total network flow
    flow_efficiency = round((path_flow / theoretical_max * 100), 2) if theoretical_max > 0 else 0.0

    # 7. Path Resilience: Number of alternative paths available
    path_resilience_score = 0
    if analyze_all:
        optimizer.best_paths = []
        optimizer._dfs_find_paths(source, sink, set(), [], float('inf'), 0)
        path_resilience_score = len(optimizer.best_paths)

    # 8. Network Connectivity: Ratio of edges to nodes
    total_edges = sum(len(edges) for edges in layered_graph.graph.values())
    total_nodes = len(layered_graph.nodes)
    network_density = round(total_edges / total_nodes, 2) if total_nodes > 0 else 0.0

    # 9. Cost per hop
    cost_per_hop = round(total_cost / path_length, 2) if path_length > 0 else 0.0

    # 10. Bottleneck severity: How much the bottleneck limits flow
    if edge_capacities:
        avg_capacity = sum(edge_capacities) / len(edge_capacities)
        bottleneck_severity = round((1 - min_capacity / avg_capacity) * 100, 2) if avg_capacity > 0 else 0.0
    else:
        bottleneck_severity = 0.0

    result = {
        'optimal_path': optimal_path,
        'max_throughput': max_flow,
        'total_cost': total_cost,
        'layers': layers_dict,
        'num_layers': len(layered_graph.layers),
        'bottleneck_nodes': bottleneck_nodes,
        'metrics': {
            'capacity_utilization_percent': capacity_utilization,
            'cost_efficiency_ratio': cost_efficiency,
            'path_length': path_length,
            'avg_edge_capacity': avg_edge_capacity,
            'flow_efficiency_percent': flow_efficiency,
            'network_density': network_density,
            'cost_per_hop': cost_per_hop,
            'bottleneck_severity_percent': bottleneck_severity,
            'path_resilience_score': path_resilience_score,
            'layer_distribution': layer_distribution
        }
    }

    # Find alternative paths if requested
    if analyze_all:
        # Re-run DFS to find all paths
        optimizer.best_paths = []
        optimizer._dfs_find_paths(source, sink, set(), [], float('inf'), 0)

        if optimizer.best_paths:
            # Sort by cost ascending, limit to top 5
            optimizer.best_paths.sort(key=lambda x: x['cost'])
            alternative_paths = []
            for path_info in optimizer.best_paths[:5]:
                alternative_paths.append({
                    'path': path_info['path'],
                    'capacity': path_info['capacity'],
                    'cost': path_info['cost']
                })

            result['alternative_paths'] = alternative_paths

    return result


# Example usage
if __name__ == "__main__":
    graph_input = {
        "graph": {
            "0": [[1, 5, 2], [2, 10, 5]],
            "1": [[5, 4, 3], [4, 5, 3]],
            "2": [[3, 8, 2]],
            "3": [[6, 6, 6], [4, 2, 2]],
            "4": [[5, 5, 1]],
            "5": [[7, 8, 4]],
            "6": [[7, 7, 2]],
            "7": []
        },
        "source": 0,
        "sink": 7,
        "analyze_all_paths": True
    }

    result = optimize_logistics_network(graph_input)
    print(result)