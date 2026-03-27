# main.py
from typing import Dict, List, Tuple
from collections import deque


class CapacityConstrainedGraph:
    """
    Represents an undirected graph with capacity constraints on edges and demands on nodes.
    """

    def __init__(self, adjacency_list: Dict[int, List[int]],
                 capacity_map: Dict[Tuple[int, int], int],
                 demand_map: Dict[int, int]):
        """
        Initialize the capacity-constrained graph.

        Args:
            adjacency_list: Dictionary mapping node IDs to lists of adjacent nodes
            capacity_map: Dictionary mapping edge tuples to their capacities
            demand_map: Dictionary mapping node IDs to their population demands
        """
        self.adjacency_list = adjacency_list
        self.capacity_map = self._normalize_capacity_map(capacity_map)
        self.demand_map = demand_map
        self.nodes = sorted(adjacency_list.keys())

    def _normalize_capacity_map(self, capacity_map: Dict[Tuple[int, int], int]) -> Dict[Tuple[int, int], int]:
        """
        Ensure capacity map is bidirectional (undirected graph).

        Args:
            capacity_map: Original capacity mapping

        Returns:
            Normalized capacity map with both directions for each edge
        """
        normalized = {}
        for (u, v), capacity in capacity_map.items():
            normalized[(u, v)] = capacity
            normalized[(v, u)] = capacity
        return normalized

    def get_capacity(self, u: int, v: int) -> int:
        """Get capacity of edge between u and v."""
        return self.capacity_map.get((u, v), 0)

    def get_demand(self, node: int) -> int:
        """Get population demand of a node."""
        return self.demand_map.get(node, 0)

    def get_neighbors(self, node: int) -> List[int]:
        """Get list of neighboring nodes."""
        return self.adjacency_list.get(node, [])


class CapacityAwarePathfinder:
    """
    Implements capacity-constrained pathfinding algorithms.

    Uses BFS-based approach to compute shortest paths while respecting
    edge capacity constraints for delivering demands from a hub to all nodes.
    """

    def __init__(self, graph: CapacityConstrainedGraph):
        """
        Initialize pathfinder with a capacity-constrained graph.

        Args:
            graph: The CapacityConstrainedGraph instance
        """
        self.graph = graph

    def compute_distances_from_hub(self, hub: int) -> Dict[int, int]:
        """
        Compute shortest path distances from hub to all reachable nodes using BFS.

        Args:
            hub: The node ID of the potential hub

        Returns:
            Dictionary mapping node IDs to their shortest path distances from hub
        """
        # If hub doesn't exist in the graph, return empty distances
        if hub not in self.graph.nodes:
            return {}
        
        distances = {hub: 0}
        queue = deque([hub])

        while queue:
            current = queue.popleft()
            current_dist = distances[current]

            for neighbor in self.graph.get_neighbors(current):
                if neighbor not in distances:
                    distances[neighbor] = current_dist + 1
                    queue.append(neighbor)

        return distances

    def is_hub_feasible(self, hub: int) -> bool:
        """
        Check if a hub can serve all nodes within capacity constraints.

        This method uses a flow-based approach to verify that the hub can deliver
        to all nodes without exceeding edge capacities. It simulates demand routing
        from the hub to each node using a greedy path selection strategy.

        Args:
            hub: The node ID of the potential hub

        Returns:
            True if hub can feasibly serve all nodes, False otherwise
        """
        # Track residual capacity for each edge during flow simulation
        residual_capacity = dict(self.graph.capacity_map)

        # Get all nodes except the hub
        target_nodes = [node for node in self.graph.nodes if node != hub]

        # Try to route demand from hub to each target node
        for target in target_nodes:
            demand = self.graph.get_demand(target)

            # Find a path from hub to target with sufficient capacity
            path = self._find_capacity_path(hub, target, demand, residual_capacity)

            if path is None:
                # Cannot route demand to this target
                return False

            # Update residual capacities along the path
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                residual_capacity[(u, v)] -= demand
                residual_capacity[(v, u)] -= demand

        return True

    def _find_capacity_path(self, source: int, target: int, demand: int,
                            residual_capacity: Dict[Tuple[int, int], int]) -> List[int]:
        """
        Find a path from source to target with sufficient capacity for demand.

        Uses BFS to find shortest path that can accommodate the required demand.

        Args:
            source: Starting node
            target: Destination node
            demand: Required capacity along the path
            residual_capacity: Current residual capacities of edges

        Returns:
            List of nodes forming the path, or None if no feasible path exists
        """
        if source == target:
            return [source]

        # BFS with path tracking
        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            current, path = queue.popleft()

            for neighbor in self.graph.get_neighbors(current):
                if neighbor in visited:
                    continue

                # Check if edge has sufficient residual capacity
                if residual_capacity.get((current, neighbor), 0) < demand:
                    continue

                new_path = path + [neighbor]

                if neighbor == target:
                    return new_path

                visited.add(neighbor)
                queue.append((neighbor, new_path))

        return None

    def compute_total_weighted_distance(self, hub: int, distances: Dict[int, int]) -> int:
        """
        Compute total weighted distance from hub to all nodes.

        The weighted distance is: sum(distance[node] * demand[node]) for all nodes.

        Args:
            hub: The hub node
            distances: Dictionary of shortest path distances from hub

        Returns:
            Total weighted distance
        """
        total = 0
        for node in self.graph.nodes:
            if node == hub:
                continue

            distance = distances.get(node, float('inf'))

            # If node is unreachable, return infinity
            if distance == float('inf'):
                return float('inf')

            demand = self.graph.get_demand(node)
            total += distance * demand

        return total


class GraphMedianFinder:
    """
    Main class for finding the optimal graph median with capacity constraints.
    """

    def __init__(self, graph: CapacityConstrainedGraph):
        """
        Initialize the median finder.

        Args:
            graph: The CapacityConstrainedGraph instance
        """
        self.graph = graph
        self.pathfinder = CapacityAwarePathfinder(graph)

    def find_optimal_hub(self) -> int:
        """
        Find the node that serves as the optimal transportation hub.

        The optimal hub minimizes total weighted distance while satisfying
        all capacity constraints.

        Returns:
            Node ID of the optimal hub
        """
        best_hub = None
        best_cost = float('inf')

        for candidate_hub in self.graph.nodes:
            # Check capacity feasibility
            if not self.pathfinder.is_hub_feasible(candidate_hub):
                continue

            # Compute distances from this hub
            distances = self.pathfinder.compute_distances_from_hub(candidate_hub)

            # Check if all nodes are reachable
            if len(distances) != len(self.graph.nodes):
                continue

            # Compute total weighted distance
            total_cost = self.pathfinder.compute_total_weighted_distance(
                candidate_hub, distances
            )

            # Update best hub if this is better
            if total_cost < best_cost:
                best_cost = total_cost
                best_hub = candidate_hub

        # If no feasible hub found, return the first node as fallback
        if best_hub is None:
            return self.graph.nodes[0] if self.graph.nodes else 0

        return best_hub


def find_graph_median(city_graph: Dict[int, List[int]],
                      capacity_map: Dict[str, int],
                      demand_map: Dict[str, int]) -> Dict:
    """
    Find the optimal transportation hub in a capacity-constrained city network.

    The algorithm:
    1. Builds a capacity-constrained graph representation
    2. For each node, checks if it can serve as a feasible hub
    3. Computes weighted distances (distance * demand) from feasible hubs
    4. Selects the hub with minimum total weighted distance

    Args:
        city_graph: Adjacency list representation {node_id: [neighbor_ids]}
        capacity_map: Edge capacities {"u,v": capacity_value}
        demand_map: Node demands {"node_id": demand_value}

    Returns:
        Dictionary containing:
            - "optimal_hub": The selected hub node ID
            - "total_weighted_distance": Total cost from this hub
            - "feasible_hubs": List of all feasible hub candidates
            - "graph_connected": Whether the graph is fully connected
    """
    # Convert string keys to appropriate types
    parsed_capacity_map = {}
    for edge_str, capacity in capacity_map.items():
        u, v = map(int, edge_str.split(','))
        parsed_capacity_map[(u, v)] = capacity

    parsed_demand_map = {int(k): int(v) if isinstance(v, str) else v for k, v in demand_map.items()}

    # Build the capacity-constrained graph
    graph = CapacityConstrainedGraph(
        adjacency_list=city_graph,
        capacity_map=parsed_capacity_map,
        demand_map=parsed_demand_map
    )

    # Find optimal hub
    finder = GraphMedianFinder(graph)
    optimal_hub = finder.find_optimal_hub()

    # Compute additional metrics for the result
    pathfinder = CapacityAwarePathfinder(graph)
    distances = pathfinder.compute_distances_from_hub(optimal_hub)
    total_weighted_distance = pathfinder.compute_total_weighted_distance(
        optimal_hub, distances
    )

    # Find all feasible hubs
    feasible_hubs = []
    for node in graph.nodes:
        if pathfinder.is_hub_feasible(node):
            feasible_hubs.append(node)

    # Check if graph is fully connected
    # Empty graphs (0 nodes) are considered connected (vacuous truth)
    if len(graph.nodes) == 0:
        graph_connected = True
    else:
        graph_connected = len(distances) == len(graph.nodes)

    return {
        "optimal_hub": optimal_hub,
        "total_weighted_distance": int(total_weighted_distance) if total_weighted_distance != float('inf') else None,
        "feasible_hubs": feasible_hubs,
        "graph_connected": graph_connected
    }


def solve_transportation_hub_problem(input_data: Dict) -> Dict:
    """
    Main trigger function for solving the capacity-constrained graph median problem.

    This function serves as the primary entry point accepting JSON-serializable input
    and returning a comprehensive JSON-serializable result dictionary.

    Args:
        input_data: Dictionary containing:
            - "city_graph": Adjacency list {node_id: [neighbor_ids]}
            - "capacity_map": Edge capacities {"u,v": capacity_value}
            - "demand_map": Node demands {"node_id": demand_value}

    Returns:
        Dictionary containing:
            - "optimal_hub": The selected hub node ID
            - "total_weighted_distance": Total cost from this hub
            - "feasible_hubs": List of all feasible hub candidates
            - "graph_connected": Whether the graph is fully connected
            - "num_nodes": Total number of nodes in the graph
            - "num_edges": Total number of edges in the graph
            - "error": Error message if input is invalid
    """
    # Validate inputs
    if not isinstance(input_data, dict):
        return {"error": "Invalid input format"}

    city_graph = input_data.get("city_graph")
    capacity_map = input_data.get("capacity_map")
    demand_map = input_data.get("demand_map")

    # Validate input types
    if not isinstance(city_graph, dict):
        return {"error": "Invalid city_graph format"}
    if not isinstance(capacity_map, dict):
        return {"error": "Invalid capacity_map format"}
    if not isinstance(demand_map, dict):
        return {"error": "Invalid demand_map format"}

    # Convert string keys to integers for city_graph if needed
    # Also convert neighbor values to integers
    if city_graph:
        # Check if keys need conversion
        first_key = next(iter(city_graph.keys()))
        if isinstance(first_key, str):
            # Convert both keys and neighbor values
            city_graph = {int(k): [int(n) if isinstance(n, str) else n for n in v] for k, v in city_graph.items()}
        else:
            # Keys are already integers, but neighbors might be strings
            city_graph = {k: [int(n) if isinstance(n, str) else n for n in v] for k, v in city_graph.items()}

    result = find_graph_median(city_graph, capacity_map, demand_map)

    # Add additional statistics
    result["num_nodes"] = len(city_graph)
    result["num_edges"] = len(capacity_map)

    return result


# Example usage
if __name__ == "__main__":
    input_data = {
        "city_graph": {
            "0": [1, 2],
            "1": [0, 3, 6],
            "2": [0, 4],
            "3": [1, 5],
            "4": [2, 5],
            "5": [3, 4],
            "6": [1]
        },
        "capacity_map": {
            "0,1": 20,
            "0,2": 10,
            "1,3": 15,
            "1,6": 5,
            "2,4": 12,
            "3,5": 18,
            "4,5": 20
        },
        "demand_map": {
            "0": 3,
            "1": 2,
            "2": 5,
            "3": 4,
            "4": 7,
            "5": 10,
            "6": 1
        }
    }
    result = solve_transportation_hub_problem(input_data)
    print(result)