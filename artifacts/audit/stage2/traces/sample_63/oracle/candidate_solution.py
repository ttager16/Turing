# main.py
from typing import List, Tuple, Dict, Any, Set
from collections import defaultdict, deque
from heapq import heappush, heappop


class UnionFind:
    """
    Advanced Multi-Layer Road Network Management System
    Using enhanced Union-Find with capacity tracking, geometric operations,
    priority-based merging, and optimization metrics.
    """
    def __init__(self):
        self.parent: Dict[int, int] = {}
        self.rank: Dict[int, int] = {}
        self.capacity: Dict[int, int] = {}
        self.metadata: Dict[int, Dict[str, Any]] = {}
        self.component_size: Dict[int, int] = {}
        self.merge_history: List[Tuple[int, int, int]] = []  # (node1, node2, timestamp)
        self.max_tree_depth: int = 0  # Track maximum tree depth encountered

    def make_set(self, node: int, capacity: int = 1) -> None:
        """Initialize a new set with a single node."""
        if node not in self.parent:
            self.parent[node] = node
            self.rank[node] = 0
            self.capacity[node] = capacity
            self.metadata[node] = {}
            self.component_size[node] = 1

    def find(self, node: int) -> int:
        """Find the root of the set containing node with path compression."""
        if node not in self.parent:
            self.make_set(node)

        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])  # Path compression
        return self.parent[node]

    def union(self, node1: int, node2: int) -> bool:
        """
        Unite two sets containing node1 and node2.
        Returns True if union was performed, False if already in same set.
        """
        root1 = self.find(node1)
        root2 = self.find(node2)

        if root1 == root2:
            return False

        # Record merge in history
        self.merge_history.append((node1, node2, len(self.merge_history)))

        # Union by rank with size tracking
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
            self.capacity[root2] += self.capacity[root1]
            self.component_size[root2] += self.component_size[root1]
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
            self.capacity[root1] += self.capacity[root2]
            self.component_size[root1] += self.component_size[root2]
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1
            self.capacity[root1] += self.capacity[root2]
            self.component_size[root1] += self.component_size[root2]

        # Update max tree depth
        self.max_tree_depth = max(self.max_tree_depth, self.rank[root1] if self.rank[root1] > self.rank[root2] else self.rank[root2])

        return True

    def connected(self, node1: int, node2: int) -> bool:
        """Check if two nodes are in the same set."""
        return self.find(node1) == self.find(node2)

    def get_all_components(self) -> List[Set[int]]:
        """Return all connected components as a list of sets."""
        components: Dict[int, Set[int]] = defaultdict(set)
        for node in self.parent:
            root = self.find(node)
            components[root].add(node)
        return list(components.values())

    def get_component_size(self, node: int) -> int:
        """Get the size of the component containing node."""
        root = self.find(node)
        return self.component_size.get(root, 1)

    def get_merge_count(self) -> int:
        """Get total number of merges performed."""
        return len(self.merge_history)

    def get_max_tree_depth(self) -> int:
        """Get maximum tree depth across all components."""
        return self.max_tree_depth

    def get_component_capacities(self) -> Dict[int, int]:
        """Get total capacity for each component (by root)."""
        capacities = {}
        for node in self.parent:
            root = self.find(node)
            if root not in capacities:
                capacities[root] = self.capacity[root]
        return capacities


class RoadNetwork:
    """
    Multi-layer road network management system with:
    - Dynamic connectivity tracking
    - Capacity management with priority queues
    - Geometric proximity-based merging
    - Real-time updates and reclassification
    - Traffic flow optimization metrics
    """

    def __init__(self):
        self.uf = UnionFind()
        self.road_map: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.node_to_roads: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)
        self.all_nodes: Set[int] = set()
        self.priority_queue: List[Tuple[int, Tuple[int, int]]] = []  # (priority, road)
        self.traffic_metrics: Dict[str, int] = {'total_capacity': 0, 'active_roads': 0}
        self.update_counter: int = 0
        self.deactivation_log: List[Tuple[Tuple[int, int], int]] = []  # (road, timestamp)

    def add_road(self, road: Tuple[int, int], capacity: int = 1, priority: int = 0) -> None:
        """Add a road to the network with optional priority."""
        node1, node2 = road
        self.uf.make_set(node1, capacity)
        self.uf.make_set(node2, capacity)
        self.uf.union(node1, node2)

        # Normalize road representation (smaller node first)
        normalized_road = tuple(sorted(road))
        self.road_map[normalized_road] = {
            'capacity': capacity,
            'active': True,
            'priority': priority,
            'timestamp': self.update_counter
        }

        # Add to priority queue (negative for max-heap behavior)
        heappush(self.priority_queue, (-priority, normalized_road))

        self.node_to_roads[node1].add(normalized_road)
        self.node_to_roads[node2].add(normalized_road)
        self.all_nodes.add(node1)
        self.all_nodes.add(node2)

        # Update metrics
        self.traffic_metrics['total_capacity'] += capacity
        self.traffic_metrics['active_roads'] += 1
        self.update_counter += 1

    def add_intersection(self, intersection: Tuple[int, int]) -> None:
        """
        Add an intersection between two nodes.
        This creates a connection between previously separate roads.
        """
        node1, node2 = intersection
        self.uf.make_set(node1)
        self.uf.make_set(node2)
        self.uf.union(node1, node2)

        self.all_nodes.add(node1)
        self.all_nodes.add(node2)

    def reclassify_road(self, road: Tuple[int, int], new_capacity: int) -> None:
        """Update the capacity of a road with metrics tracking."""
        normalized_road = tuple(sorted(road))
        if normalized_road in self.road_map:
            old_capacity = self.road_map[normalized_road]['capacity']
            self.road_map[normalized_road]['capacity'] = new_capacity
            self.traffic_metrics['total_capacity'] += (new_capacity - old_capacity)

        # Note: Road capacity is stored in road_map, not in union-find node capacities
        # The union-find tracks component connectivity, not individual road capacities

        self.update_counter += 1

    def expand_road(self, original_road: Tuple[int, int], extended_road: Tuple[int, int]) -> None:
        """
        Expand a road by adding an extension.
        The extended road shares one node with the original and extends to a new node.
        """
        # Add the new road segment
        self.add_road(extended_road)

        # Ensure connectivity between original and extended roads
        # Find common node
        orig_nodes = set(original_road)
        ext_nodes = set(extended_road)
        common_nodes = orig_nodes & ext_nodes

        if common_nodes:
            # Already connected through common node
            pass
        else:
            # Connect the closest nodes if not already connected
            for n1 in original_road:
                for n2 in extended_road:
                    if not self.uf.connected(n1, n2):
                        self.uf.union(n1, n2)

    def merge_by_proximity(self, road1: Tuple[int, int], road2: Tuple[int, int],
                           distance_threshold: float) -> None:
        """
        Merge two roads if they are within a geometric distance threshold.
        Uses BFS-style propagation for multi-hop connectivity.
        """
        if distance_threshold > 0:
            # Use BFS to ensure all reachable nodes are connected
            queue = deque([(n1, n2) for n1 in road1 for n2 in road2])
            visited = set()

            while queue:
                n1, n2 = queue.popleft()
                if (n1, n2) in visited:
                    continue
                visited.add((n1, n2))

                if self.uf.union(n1, n2):
                    # If union was successful, propagate to neighbors
                    for neighbor1 in self._get_neighbors(n1):
                        for neighbor2 in self._get_neighbors(n2):
                            if (neighbor1, neighbor2) not in visited:
                                queue.append((neighbor1, neighbor2))

        self.update_counter += 1

    def _get_neighbors(self, node: int) -> Set[int]:
        """Get all neighboring nodes connected to the given node."""
        neighbors = set()
        for road in self.node_to_roads.get(node, set()):
            neighbors.update(road)
        neighbors.discard(node)
        return neighbors

    def close_partial(self, road: Tuple[int, int], lanes_closed: int) -> None:
        """
        Partially close a road by reducing its effective capacity.
        If all lanes are closed, we don't disconnect but mark as inactive.
        """
        normalized_road = tuple(sorted(road))
        if normalized_road in self.road_map:
            current_capacity = self.road_map[normalized_road].get('capacity', 1)
            new_capacity = max(0, current_capacity - lanes_closed)

            # Update metrics
            self.traffic_metrics['total_capacity'] -= (current_capacity - new_capacity)

            self.road_map[normalized_road]['capacity'] = new_capacity

            if new_capacity == 0:
                self.road_map[normalized_road]['active'] = False
                self.traffic_metrics['active_roads'] -= 1
                self.deactivation_log.append((normalized_road, self.update_counter))

        self.update_counter += 1

    def get_components(self) -> List[Set[int]]:
        """Get all connected components in the network."""
        return self.uf.get_all_components()

    def get_optimization_score(self) -> float:
        """
        Calculate network optimization score based on connectivity and capacity.
        Higher score indicates better network efficiency.
        """
        components = self.get_components()
        if not components:
            return 0.0

        # Penalize fragmentation, reward high capacity
        num_components = len(components)
        avg_component_size = sum(len(c) for c in components) / num_components
        capacity_factor = self.traffic_metrics['total_capacity'] / max(1, len(self.all_nodes))

        # Score: higher for fewer components, larger avg size, and higher capacity
        score = (avg_component_size * capacity_factor) / max(1, num_components)
        return round(score, 2)

    def get_high_priority_roads(self, k: int = 5) -> List[Tuple[int, int]]:
        """Get top k roads by priority."""
        # Extract from priority queue without modifying it
        temp_heap = self.priority_queue.copy()
        result = []
        for _ in range(min(k, len(temp_heap))):
            _, road = heappop(temp_heap)
            if road in self.road_map and self.road_map[road]['active']:
                result.append(road)
        return result

    def get_fragmentation_index(self) -> float:
        """Calculate network fragmentation: ratio of components to total nodes."""
        if len(self.all_nodes) == 0:
            return 0.0
        components = self.get_components()
        return round(len(components) / len(self.all_nodes), 4)


def manage_road_network(
    roads: List[List[int]],
    intersections: List[List[int]],
    updates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Manage a complex multi-layer road network with dynamic updates.

    Args:
        roads: List of road segments as [node1, node2] lists
        intersections: List of intersection points connecting separate roads as [node1, node2] lists
        updates: List of update operations to apply to the network

    Returns:
        Dictionary containing:
            - 'components': List of connected component lists (sorted)
            - 'statistics': Dictionary with network statistics including merge count,
                          component sizes, and total capacities

    Update types supported:
        - 'reclassify': Change road capacity
        - 'expand': Extend a road with a new segment
        - 'merge_levels': Merge roads based on proximity threshold
        - 'close_partial': Partially close a road by reducing lanes
        - 'optimize': Trigger optimization analysis and priority-based decisions
    """
    network = RoadNetwork()

    # Step 1: Initialize all roads with priority based on order (earlier = higher priority)
    for idx, road in enumerate(roads):
        priority = len(roads) - idx  # Earlier roads get higher priority
        network.add_road(tuple(road), priority=priority)

    # Step 2: Add all intersections
    for intersection in intersections:
        network.add_intersection(tuple(intersection))

    # Step 3: Process updates sequentially
    for update in updates:
        update_type = update.get('type')

        if update_type == 'reclassify':
            road = update.get('road')
            new_capacity = update.get('new_capacity', 1)
            network.reclassify_road(tuple(road), new_capacity)

        elif update_type == 'expand':
            road = update.get('road')
            extended_road = update.get('extended_road')
            network.expand_road(tuple(road), tuple(extended_road))

        elif update_type == 'merge_levels':
            road = update.get('road')
            adjacent_road = update.get('adjacent_road')
            distance_threshold = update.get('distance_threshold', 0)
            network.merge_by_proximity(tuple(road), tuple(adjacent_road), distance_threshold)

        elif update_type == 'close_partial':
            road = update.get('road')
            lanes_closed = update.get('lanes_closed', 1)
            network.close_partial(tuple(road), lanes_closed)

        elif update_type == 'optimize':
            # Perform optimization analysis
            _ = network.get_optimization_score()
            high_priority = network.get_high_priority_roads(k=update.get('k', 3))

            # Optionally boost capacity on high-priority roads
            if update.get('boost_priority_roads', False):
                for priority_road in high_priority:
                    if priority_road in network.road_map:
                        current_cap = network.road_map[priority_road]['capacity']
                        network.reclassify_road(priority_road, current_cap + 1)

    # Step 4: Return all connected components and statistics
    components = network.get_components()

    # Sort components by size (largest first) then by smallest element
    components.sort(key=lambda s: (-len(s), min(s) if s else float('inf')))

    # Convert components from sets to sorted lists
    components_as_lists = [sorted(list(comp)) for comp in components]

    # Calculate total network capacity from actual roads
    total_network_capacity = sum(
        info['capacity'] for road, info in network.road_map.items()
        if info.get('active', True)
    )

    # Gather component capacities from union-find
    component_capacities = network.uf.get_component_capacities()
    sorted_component_capacities = [component_capacities.get(network.uf.find(min(comp)), 0) for comp in components if comp]

    # Gather statistics using the UnionFind methods
    statistics = {
        'total_merge_count': network.uf.get_merge_count(),
        'num_components': len(components),
        'component_sizes': [network.uf.get_component_size(min(comp)) for comp in components if comp],
        'total_network_capacity': total_network_capacity,
        'max_tree_depth': network.uf.get_max_tree_depth(),
        'fragmentation_index': network.get_fragmentation_index(),
        'deactivated_roads_count': len(network.deactivation_log),
        'component_capacities': sorted_component_capacities
    }

    return {
        'components': components_as_lists,
        'statistics': statistics
    }


# Example usage and validation
if __name__ == "__main__":
    roads = [[1, 2], [2, 3], [3, 4], [7, 8]]
    intersections = [[2, 5], [4, 6]]
    updates = [
        {'type': 'reclassify', 'road': [2, 3], 'new_capacity': 2},
        {'type': 'expand', 'road': [3, 4], 'extended_road': [3, 6]},
        {'type': 'optimize', 'k': 3, 'boost_priority_roads': True},
        {'type': 'merge_levels', 'road': [1, 2], 'adjacent_road': [7, 8], 'distance_threshold': 10},
        {'type': 'close_partial', 'road': [2, 5], 'lanes_closed': 1},
        {'type': 'optimize', 'k': 5, 'boost_priority_roads': False}
    ]

    results = manage_road_network(roads, intersections, updates)
    print(results)