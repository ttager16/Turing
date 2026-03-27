from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, deque
import heapq


class UnionFind:
    """Efficient union-find with path compression and union by rank."""
    
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.components = n
    
    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int) -> bool:
        root_x, root_y = self.find(x), self.find(y)
        if root_x == root_y:
            return False
        if self.rank[root_x] < self.rank[root_y]:
            root_x, root_y = root_y, root_x
        self.parent[root_y] = root_x
        if self.rank[root_x] == self.rank[root_y]:
            self.rank[root_x] += 1
        self.components -= 1
        return True
    
    def is_connected(self) -> bool:
        return self.components == 1


class ReliabilityCalculator:
    """Calculates and maintains reliability scores using the formula R_i = αS_i + β(1-F_i) + γC_i."""
    
    def __init__(self, alpha: float = 0.4, beta: float = 0.3, gamma: float = 0.3):
        if abs(alpha + beta + gamma - 1.0) > 1e-6:
            raise ValueError("Coefficients must sum to 1.0")
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.stability_factors = {}
        self.failure_rates = {}
        self.connectivity_strengths = {}
    
    def update_factors(self, node: int, stability: float, failure_rate: float, connectivity: float):
        """Update individual factors for reliability calculation."""
        self.stability_factors[node] = max(0.0, min(1.0, stability))
        self.failure_rates[node] = max(0.0, min(1.0, failure_rate))
        self.connectivity_strengths[node] = max(0.0, min(1.0, connectivity))
    
    def compute_reliability(self, node: int) -> float:
        """Compute reliability score for a node using the formula."""
        S_i = self.stability_factors.get(node, 0.5)
        F_i = self.failure_rates.get(node, 0.5)
        C_i = self.connectivity_strengths.get(node, 0.5)
        return self.alpha * S_i + self.beta * (1 - F_i) + self.gamma * C_i
    
    def derive_factors_from_reliability(self, node: int, reliability: float):
        """Derive normalized factors from a given reliability score."""
        reliability = max(0.0, min(1.0, reliability / 10.0))
        self.stability_factors[node] = reliability
        self.failure_rates[node] = 1.0 - reliability
        self.connectivity_strengths[node] = reliability


class GraphManager:
    """Manages graph structure with capacity constraints and optimal path finding."""
    
    def __init__(self, edges: List[List], num_nodes: int):
        if num_nodes < 1:
            raise ValueError("Number of nodes must be at least 1")
        
        self.num_nodes = num_nodes
        self.adj_list = defaultdict(list)
        self.edge_map = {}
        self.capacity_map = {}
        
        for edge in edges:
            if len(edge) < 3:
                continue
            u, v, cost = int(edge[0]), int(edge[1]), float(edge[2])
            if u < 0 or v < 0 or u >= num_nodes or v >= num_nodes:
                continue
            if u == v:
                continue
            
            capacity = float(edge[3]) if len(edge) > 3 else float('inf')
            
            self.adj_list[u].append((v, cost, capacity))
            self.adj_list[v].append((u, cost, capacity))
            
            edge_key = tuple(sorted([u, v]))
            if edge_key not in self.edge_map or cost < self.edge_map[edge_key]:
                self.edge_map[edge_key] = cost
                self.capacity_map[edge_key] = capacity
    
    def get_cost(self, u: int, v: int) -> Optional[float]:
        edge_key = tuple(sorted([u, v]))
        return self.edge_map.get(edge_key)
    
    def get_capacity(self, u: int, v: int) -> Optional[float]:
        edge_key = tuple(sorted([u, v]))
        return self.capacity_map.get(edge_key)
    
    def validate_connectivity_to_source(self, source: int) -> bool:
        """Validate that source node exists and can reach all nodes."""
        if source < 0 or source >= self.num_nodes:
            return False
        
        visited = set()
        queue = deque([source])
        visited.add(source)
        
        while queue:
            node = queue.popleft()
            for neighbor, _, _ in self.adj_list[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return len(visited) == self.num_nodes
    
    def dijkstra_path(self, source: int, target: int, 
                     excluded_edges: Set[Tuple[int, int]]) -> Optional[Tuple[List[int], float]]:
        """Find minimum-cost path using Dijkstra's algorithm."""
        if source == target:
            return ([source], 0.0)
        
        dist = {source: 0.0}
        parent = {source: None}
        pq = [(0.0, source)]
        visited = set()
        
        while pq:
            curr_dist, node = heapq.heappop(pq)
            
            if node in visited:
                continue
            visited.add(node)
            
            if node == target:
                path = []
                current = target
                while current is not None:
                    path.append(current)
                    current = parent.get(current)
                return (path[::-1], curr_dist)
            
            for neighbor, cost, capacity in self.adj_list[node]:
                edge = tuple(sorted([node, neighbor]))
                if edge in excluded_edges or capacity <= 0:
                    continue
                
                new_dist = curr_dist + cost
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    parent[neighbor] = node
                    heapq.heappush(pq, (new_dist, neighbor))
        
        return None
    
    def find_edge_disjoint_paths_optimal(self, source: int, target: int) -> List[Tuple[List[int], float]]:
        """Find two edge-disjoint minimum-cost paths using successive shortest paths."""
        if source == target:
            return [([source], 0.0)]
        
        path1_result = self.dijkstra_path(source, target, set())
        if not path1_result:
            return []
        
        path1, cost1 = path1_result
        path1_edges = set()
        for i in range(len(path1) - 1):
            edge = tuple(sorted([path1[i], path1[i + 1]]))
            path1_edges.add(edge)
        
        path2_result = self.dijkstra_path(source, target, path1_edges)
        if not path2_result:
            return [(path1, cost1)]
        
        path2, cost2 = path2_result
        return [(path1, cost1), (path2, cost2)]
    
    def compute_connectivity_strength(self, node: int, active_edges: Set[Tuple[int, int]]) -> float:
        """Compute connectivity strength as fraction of maintained links."""
        total_neighbors = len(self.adj_list[node])
        if total_neighbors == 0:
            return 0.0
        
        active_neighbors = 0
        for neighbor, _, _ in self.adj_list[node]:
            edge = tuple(sorted([node, neighbor]))
            if edge in active_edges:
                active_neighbors += 1
        
        return active_neighbors / total_neighbors


class RedundancyManager:
    """Ensures and validates redundancy requirements for high-priority nodes."""
    
    def __init__(self, graph_manager: GraphManager):
        self.graph_manager = graph_manager
    
    def verify_redundancy(self, high_priority_nodes: Set[int], 
                         selected_edges: Set[Tuple[int, int]], source: int = 0) -> Dict[int, bool]:
        """Verify each high-priority node has two disjoint paths to source."""
        verification = {}
        
        for node in high_priority_nodes:
            if node == source:
                verification[node] = True
                continue
            
            paths = self._find_disjoint_paths_in_subgraph(source, node, selected_edges)
            verification[node] = len(paths) >= 2
        
        return verification
    
    def ensure_redundancy_incremental(self, high_priority_nodes: Set[int], 
                                     base_edges: Set[Tuple[int, int]], 
                                     source: int = 0) -> Set[Tuple[int, int]]:
        """Incrementally add edges to ensure redundancy with minimal cost increase."""
        result_edges = set(base_edges)
        
        for node in sorted(high_priority_nodes):
            if node == source:
                continue
            
            paths = self._find_disjoint_paths_in_subgraph(source, node, result_edges)
            
            if len(paths) < 2:
                augmenting_edges = self._find_minimal_augmenting_path(source, node, result_edges)
                result_edges.update(augmenting_edges)
        
        return result_edges
    
    def _find_disjoint_paths_in_subgraph(self, source: int, target: int, 
                                        edges: Set[Tuple[int, int]]) -> List[List[int]]:
        """Find edge-disjoint paths within a specific edge set."""
        temp_adj = defaultdict(list)
        for u, v in edges:
            cost = self.graph_manager.get_cost(u, v) or 1.0
            temp_adj[u].append((v, cost))
            temp_adj[v].append((u, cost))
        
        def dijkstra_in_subgraph(excluded: Set[Tuple[int, int]]) -> Optional[List[int]]:
            if source == target:
                return [source]
            
            dist = {source: 0.0}
            parent = {source: None}
            pq = [(0.0, source)]
            visited = set()
            
            while pq:
                curr_dist, node = heapq.heappop(pq)
                if node in visited:
                    continue
                visited.add(node)
                
                if node == target:
                    path = []
                    current = target
                    while current is not None:
                        path.append(current)
                        current = parent.get(current)
                    return path[::-1]
                
                for neighbor, cost in temp_adj[node]:
                    edge = tuple(sorted([node, neighbor]))
                    if edge in excluded:
                        continue
                    
                    new_dist = curr_dist + cost
                    if neighbor not in dist or new_dist < dist[neighbor]:
                        dist[neighbor] = new_dist
                        parent[neighbor] = node
                        heapq.heappush(pq, (new_dist, neighbor))
            
            return None
        
        paths = []
        excluded = set()
        
        for _ in range(2):
            path = dijkstra_in_subgraph(excluded)
            if not path:
                break
            paths.append(path)
            for i in range(len(path) - 1):
                edge = tuple(sorted([path[i], path[i + 1]]))
                excluded.add(edge)
        
        return paths
    
    def _find_minimal_augmenting_path(self, source: int, target: int, 
                                     current_edges: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """Find minimal cost edges to establish second disjoint path."""
        available_edges = []
        
        for edge_key, cost in self.graph_manager.edge_map.items():
            if edge_key not in current_edges:
                available_edges.append((cost, edge_key))
        
        available_edges.sort()
        
        for cost, edge in available_edges:
            test_edges = current_edges | {edge}
            paths = self._find_disjoint_paths_in_subgraph(source, target, test_edges)
            if len(paths) >= 2:
                return {edge}
        
        best_combination = set()
        min_cost = float('inf')
        
        for i, (cost1, edge1) in enumerate(available_edges[:10]):
            for cost2, edge2 in available_edges[i+1:min(i+11, len(available_edges))]:
                test_edges = current_edges | {edge1, edge2}
                paths = self._find_disjoint_paths_in_subgraph(source, target, test_edges)
                if len(paths) >= 2 and cost1 + cost2 < min_cost:
                    min_cost = cost1 + cost2
                    best_combination = {edge1, edge2}
        
        return best_combination


class CostOptimizer:
    """Optimizes edge selection with dynamic cost rebalancing."""
    
    def __init__(self, graph_manager: GraphManager, reliability_calc: ReliabilityCalculator):
        self.graph_manager = graph_manager
        self.reliability_calc = reliability_calc
        self.rebalanced_costs = {}
    
    def compute_mst_with_reliability(self, priorities: List[List]) -> Set[Tuple[int, int]]:
        """Compute MST considering reliability-weighted costs."""
        edges = []
        for edge_key, base_cost in self.graph_manager.edge_map.items():
            u, v = edge_key
            
            rel_u = self.reliability_calc.compute_reliability(u)
            rel_v = self.reliability_calc.compute_reliability(v)
            avg_reliability = (rel_u + rel_v) / 2.0
            
            adjusted_cost = base_cost / max(0.1, avg_reliability)
            edges.append((adjusted_cost, edge_key))
        
        edges.sort()
        
        uf = UnionFind(self.graph_manager.num_nodes)
        mst_edges = set()
        
        for cost, (u, v) in edges:
            if uf.union(u, v):
                mst_edges.add((u, v))
                if len(mst_edges) >= self.graph_manager.num_nodes - 1:
                    break
        
        return mst_edges
    
    def rebalance_and_reselect(self, edges: Set[Tuple[int, int]], 
                              high_priority_nodes: Set[int], source: int = 0) -> Set[Tuple[int, int]]:
        """Rebalance costs based on shared utilization and reselect optimal edges."""
        edge_usage = defaultdict(int)
        edge_paths = defaultdict(set)
        
        for node in high_priority_nodes:
            if node == source:
                continue
            
            paths = self.graph_manager.find_edge_disjoint_paths_optimal(source, node)
            for path, _ in paths:
                for i in range(len(path) - 1):
                    edge = tuple(sorted([path[i], path[i + 1]]))
                    if edge in edges:
                        edge_usage[edge] += 1
                        edge_paths[edge].add(node)
        
        self.rebalanced_costs = {}
        for edge in edges:
            base_cost = self.graph_manager.get_cost(*edge)
            if base_cost is None:
                continue
            
            usage_count = edge_usage.get(edge, 0)
            if usage_count > 1:
                sharing_factor = 1.0 / usage_count
                self.rebalanced_costs[edge] = base_cost * sharing_factor
            else:
                self.rebalanced_costs[edge] = base_cost
        
        critical_edges = {edge for edge in edges if edge_usage.get(edge, 0) > 0}
        
        non_critical = edges - critical_edges
        sorted_non_critical = sorted(non_critical, 
                                    key=lambda e: self.rebalanced_costs.get(e, float('inf')))
        
        optimized = set(critical_edges)
        
        uf = UnionFind(self.graph_manager.num_nodes)
        for edge in critical_edges:
            uf.union(*edge)
        
        for edge in sorted_non_critical:
            if not uf.is_connected():
                if uf.union(*edge):
                    optimized.add(edge)
        
        return optimized


class DynamicGraphManager:
    """Manages incremental updates without full recomputation."""
    
    def __init__(self, graph_manager: GraphManager, reliability_calc: ReliabilityCalculator):
        self.graph_manager = graph_manager
        self.reliability_calc = reliability_calc
        self.current_edges = set()
        self.current_priorities = {}
        self.high_priority_cache = set()
    
    def initialize(self, priorities: List[List], initial_edges: Set[Tuple[int, int]]):
        """Initialize with baseline state."""
        self.current_edges = set(initial_edges)
        for node, (priority, reliability) in enumerate(priorities):
            self.current_priorities[node] = (priority, reliability)
            if priority == 1:
                self.high_priority_cache.add(node)
            self.reliability_calc.derive_factors_from_reliability(node, reliability)
    
    def apply_update_incremental(self, vertex_id: int, new_priority: int, 
                                 new_reliability: float, redundancy_mgr: RedundancyManager) -> bool:
        """Apply single update incrementally."""
        if vertex_id not in self.current_priorities:
            return False
        
        old_priority, old_reliability = self.current_priorities[vertex_id]
        self.current_priorities[vertex_id] = (new_priority, new_reliability)
        self.reliability_calc.derive_factors_from_reliability(vertex_id, new_reliability)
        
        priority_changed = (old_priority != new_priority)
        
        if priority_changed:
            if new_priority == 1 and vertex_id not in self.high_priority_cache:
                self.high_priority_cache.add(vertex_id)
                
                paths = redundancy_mgr._find_disjoint_paths_in_subgraph(0, vertex_id, self.current_edges)
                if len(paths) < 2:
                    augmenting = redundancy_mgr._find_minimal_augmenting_path(0, vertex_id, self.current_edges)
                    self.current_edges.update(augmenting)
            
            elif new_priority == 0 and vertex_id in self.high_priority_cache:
                self.high_priority_cache.discard(vertex_id)
        
        connectivity = self.graph_manager.compute_connectivity_strength(vertex_id, self.current_edges)
        stability = new_reliability / 10.0
        failure_rate = 1.0 - stability
        self.reliability_calc.update_factors(vertex_id, stability, failure_rate, connectivity)
        
        return True


def prioritize_mst(
    graph: List[List],
    priorities: List[List],
    updates: List[List]
) -> List[List[int]]:
    """
    Maintains dynamic low-cost subgraph with redundancy for high-priority substations.
    
    Implements:
    - Reliability score formula R_i = αS_i + β(1-F_i) + γC_i
    - Capacity constraint validation
    - Incremental update processing
    - Cost rebalancing based on shared utilization
    - Rigorous redundancy verification
    
    Args:
        graph: List of edges [u, v, cost] or [u, v, cost, capacity]
        priorities: List of [priority_level, reliability_score] per node
        updates: List of [vertex_id, new_priority, new_reliability]
    
    Returns:
        List of selected edges [u, v] ensuring connectivity and redundancy
    
    Raises:
        ValueError: If inputs are malformed or graph is disconnected
    """
    if not graph:
        return []
    
    if not priorities:
        return []
    
    num_nodes = len(priorities)
    if num_nodes < 1:
        raise ValueError("Must have at least one node")
    
    try:
        graph_manager = GraphManager(graph, num_nodes)
    except Exception as e:
        raise ValueError(f"Failed to initialize graph: {str(e)}")
    
    if not graph_manager.validate_connectivity_to_source(0):
        raise ValueError("Graph must be connected with node 0 as main source")
    
    reliability_calc = ReliabilityCalculator(alpha=0.4, beta=0.3, gamma=0.3)
    
    for node, (priority, reliability) in enumerate(priorities):
        if priority not in [0, 1]:
            raise ValueError(f"Priority must be 0 or 1 for node {node}")
        reliability_calc.derive_factors_from_reliability(node, reliability)
    
    cost_optimizer = CostOptimizer(graph_manager, reliability_calc)
    redundancy_manager = RedundancyManager(graph_manager)
    dynamic_manager = DynamicGraphManager(graph_manager, reliability_calc)
    
    mst_edges = cost_optimizer.compute_mst_with_reliability(priorities)
    
    high_priority_nodes = {i for i, (priority, _) in enumerate(priorities) if priority == 1}
    
    edges_with_redundancy = redundancy_manager.ensure_redundancy_incremental(
        high_priority_nodes, mst_edges, source=0
    )
    
    dynamic_manager.initialize(priorities, edges_with_redundancy)
    
    for update in updates:
        if len(update) < 3:
            continue
        
        vertex_id = int(update[0])
        new_priority = int(update[1])
        new_reliability = float(update[2])
        
        if vertex_id < 0 or vertex_id >= num_nodes:
            continue
        
        if new_priority not in [0, 1]:
            continue
        
        dynamic_manager.apply_update_incremental(
            vertex_id, new_priority, new_reliability, redundancy_manager
        )
    
    final_edges = dynamic_manager.current_edges
    final_high_priority = dynamic_manager.high_priority_cache
    
    verification = redundancy_manager.verify_redundancy(final_high_priority, final_edges, source=0)
    for node, has_redundancy in verification.items():
        if not has_redundancy:
            augmenting = redundancy_manager._find_minimal_augmenting_path(0, node, final_edges)
            final_edges.update(augmenting)
    
    optimized_edges = cost_optimizer.rebalance_and_reselect(final_edges, final_high_priority, source=0)
    
    uf = UnionFind(num_nodes)
    for edge in optimized_edges:
        uf.union(*edge)
    
    if not uf.is_connected():
        all_edges_sorted = sorted(
            [(cost, tuple(sorted([u, v]))) for (u, v), cost in graph_manager.edge_map.items()],
            key=lambda x: x[0]
        )
        for cost, edge in all_edges_sorted:
            if edge not in optimized_edges:
                if uf.union(*edge):
                    optimized_edges.add(edge)
                    if uf.is_connected():
                        break
    
    return sorted([[u, v] for u, v in optimized_edges])


if __name__ == "__main__":
    graph = [
        [0, 1, 4.2],
        [0, 2, 3.1],
        [1, 3, 2.0],
        [2, 3, 1.9],
        [2, 4, 5.5]
    ]
    
    priorities = [
        [1, 4.5],
        [0, 3.0],
        [1, 2.8],
        [0, 2.0],
        [0, 3.7]
    ]
    
    updates = [
        [1, 1, 5.5],
        [3, 1, 4.1]
    ]
    
    result = prioritize_mst(graph, priorities, updates)
    print(f"Selected Edges: {result}")