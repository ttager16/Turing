from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict, deque
import heapq
import sys


class Edge:
    """Represents a directed edge with capacity, cost, priority, and flow."""
    
    def __init__(self, to: int, capacity: int, cost: int, priority: int, reverse_idx: int, edge_id: int):
        self.to = to
        self.capacity = capacity
        self.cost = cost
        self.priority = priority
        self.flow = 0
        self.reverse_idx = reverse_idx
        self.edge_id = edge_id
        self.original_capacity = capacity
        self.commodity_flows = {}


class MinCostMaxFlowSolver:
    """Optimized Min-Cost Max-Flow solver using Dijkstra with binary heap."""
    
    def __init__(self, n: int):
        self.n = n
        self.graph = [[] for _ in range(n)]
        self.potential = [0] * n
        self.flow_computed = False
        
    def add_edge(self, from_node: int, to_node: int, capacity: int, cost: int, priority: int, edge_id: int):
        """Add edge with cost and priority tracking."""
        forward_edge = Edge(to_node, capacity, cost, priority, len(self.graph[to_node]), edge_id)
        backward_edge = Edge(from_node, 0, -cost, priority, len(self.graph[from_node]), edge_id)
        self.graph[from_node].append(forward_edge)
        self.graph[to_node].append(backward_edge)
    
    def _bellman_ford(self, source: int):
        """Initialize potentials using Bellman-Ford to handle negative costs."""
        dist = [sys.maxsize] * self.n
        dist[source] = 0
        
        for _ in range(self.n - 1):
            updated = False
            for u in range(self.n):
                if dist[u] == sys.maxsize:
                    continue
                for edge in self.graph[u]:
                    if edge.capacity > edge.flow:
                        new_dist = dist[u] + edge.cost
                        if new_dist < dist[edge.to]:
                            dist[edge.to] = new_dist
                            updated = True
            if not updated:
                break
        
        self.potential = dist
    
    def _dijkstra_heap(self, source: int, sink: int) -> Tuple[List[int], List[Tuple[int, int]]]:
        """Optimized Dijkstra using binary heap with reduced costs."""
        dist = [sys.maxsize] * self.n
        parent = [(-1, -1)] * self.n
        dist[source] = 0
        
        heap = [(0, source)]
        visited = [False] * self.n
        
        while heap:
            d, u = heapq.heappop(heap)
            
            if visited[u]:
                continue
            visited[u] = True
            
            if u == sink:
                break
            
            for idx, edge in enumerate(self.graph[u]):
                if edge.capacity > edge.flow:
                    reduced_cost = edge.cost + self.potential[u] - self.potential[edge.to]
                    priority_factor = -edge.priority * 0.001
                    effective_cost = reduced_cost + priority_factor
                    
                    new_dist = dist[u] + effective_cost
                    if new_dist < dist[edge.to]:
                        dist[edge.to] = new_dist
                        parent[edge.to] = (u, idx)
                        heapq.heappush(heap, (new_dist, edge.to))
        
        return dist, parent
    
    def min_cost_max_flow(self, source: int, sink: int) -> Tuple[int, int]:
        """Compute min-cost max-flow using successive shortest paths."""
        self._bellman_ford(source)
        
        max_flow = 0
        min_cost = 0
        
        while True:
            dist, parent = self._dijkstra_heap(source, sink)
            
            if dist[sink] == sys.maxsize:
                break
            
            for v in range(self.n):
                if dist[v] < sys.maxsize:
                    self.potential[v] += dist[v]
            
            path_flow = sys.maxsize
            v = sink
            while v != source:
                u, edge_idx = parent[v]
                edge = self.graph[u][edge_idx]
                path_flow = min(path_flow, edge.capacity - edge.flow)
                v = u
            
            v = sink
            while v != source:
                u, edge_idx = parent[v]
                forward_edge = self.graph[u][edge_idx]
                backward_edge = self.graph[v][forward_edge.reverse_idx]
                
                forward_edge.flow += path_flow
                backward_edge.flow -= path_flow
                
                v = u
            
            max_flow += path_flow
            min_cost += path_flow * (self.potential[sink] - self.potential[source])
        
        self.flow_computed = True
        return max_flow, min_cost
    
    def get_residual_capacity(self, u: int, edge_idx: int) -> int:
        """Get remaining capacity on edge."""
        edge = self.graph[u][edge_idx]
        return edge.capacity - edge.flow


class MultiCommodityFlowSolver:
    """Handles multiple commodity types with shared capacity constraints."""
    
    def __init__(self, n: int):
        self.n = n
        self.commodities = {}
        self.shared_edges = defaultdict(lambda: {'total_capacity': 0, 'flows': {}})
        
    def add_commodity(self, commodity_id: int, source: int, sink: int, demand: int):
        """Register a commodity type."""
        self.commodities[commodity_id] = {
            'source': source,
            'sink': sink,
            'demand': demand,
            'flow': 0
        }
    
    def solve_multi_commodity(self, base_solver: MinCostMaxFlowSolver, 
                             edge_mapping: Dict[int, Tuple[int, int]]) -> Dict[int, int]:
        """Solve multi-commodity flow with capacity sharing."""
        commodity_flows = {}
        
        for comm_id in sorted(self.commodities.keys()):
            comm = self.commodities[comm_id]
            
            temp_solver = MinCostMaxFlowSolver(self.n)
            for u in range(self.n):
                for edge in base_solver.graph[u]:
                    if edge.capacity > 0:
                        allocated = sum(self.shared_edges[edge.edge_id]['flows'].values())
                        remaining = edge.original_capacity - allocated
                        if remaining > 0:
                            temp_solver.add_edge(u, edge.to, remaining, edge.cost, 
                                               edge.priority, edge.edge_id)
            
            flow, cost = temp_solver.min_cost_max_flow(comm['source'], comm['sink'])
            commodity_flows[comm_id] = flow
            
            for u in range(self.n):
                for idx, edge in enumerate(temp_solver.graph[u]):
                    if edge.flow > 0 and edge.capacity > 0:
                        self.shared_edges[edge.edge_id]['flows'][comm_id] = edge.flow
            
            self.commodities[comm_id]['flow'] = flow
        
        return commodity_flows


class DynamicNetworkManager:
    """Manages dynamic updates without full recomputation."""
    
    def __init__(self, optimizer):
        self.optimizer = optimizer
        self.cached_flows = {}
        self.affected_paths = set()
        
    def invalidate_edge(self, u: int, v: int):
        """Mark edge as unavailable and track affected paths."""
        self.affected_paths.add((u, v))
        
        for node_u in range(self.optimizer.solver.n):
            for edge in self.optimizer.solver.graph[node_u]:
                if node_u == u and edge.to == v:
                    edge.capacity = 0
    
    def restore_edge(self, u: int, v: int, capacity: int):
        """Restore edge capacity."""
        if (u, v) in self.affected_paths:
            self.affected_paths.remove((u, v))
        
        for edge in self.optimizer.solver.graph[u]:
            if edge.to == v:
                edge.capacity = capacity
                edge.original_capacity = capacity
    
    def incremental_update(self, source: int, sink: int) -> int:
        """Incrementally update flow for affected paths only."""
        affected_nodes = set()
        for u, v in self.affected_paths:
            affected_nodes.add(u)
            affected_nodes.add(v)
        
        if not affected_nodes:
            return self.optimizer.solver.min_cost_max_flow(source, sink)[0]
        
        queue = deque(affected_nodes)
        visited = set(affected_nodes)
        
        while queue:
            node = queue.popleft()
            for edge in self.optimizer.solver.graph[node]:
                if edge.to not in visited and edge.flow > 0:
                    visited.add(edge.to)
                    queue.append(edge.to)
        
        for node in visited:
            for edge in self.optimizer.solver.graph[node]:
                edge.flow = 0
        
        additional_flow, _ = self.optimizer.solver.min_cost_max_flow(source, sink)
        return additional_flow


class NodeMergeManager:
    """Handles dynamic node merging and splitting."""
    
    def __init__(self, n: int):
        self.n = n
        self.merge_map = {}
        self.split_history = []
        
    def merge_nodes(self, node_a: int, node_b: int, new_node: int):
        """Merge two nodes into a new node."""
        self.merge_map[node_a] = new_node
        self.merge_map[node_b] = new_node
        self.split_history.append((new_node, [node_a, node_b]))
    
    def split_node(self, merged_node: int) -> List[int]:
        """Split a merged node back to original components."""
        for node, components in reversed(self.split_history):
            if node == merged_node:
                for comp in components:
                    if comp in self.merge_map:
                        del self.merge_map[comp]
                self.split_history.remove((node, components))
                return components
        return [merged_node]
    
    def apply_mapping(self, node: int) -> int:
        """Get effective node after merging."""
        return self.merge_map.get(node, node)


class MinCutAnalyzer:
    """Enhanced min-cut analysis with bottleneck validation."""
    
    def __init__(self, solver: MinCostMaxFlowSolver):
        self.solver = solver
        self.n = solver.n
    
    def find_min_cut_edges(self, source: int) -> Set[Tuple[int, int]]:
        """Identify true capacity bottlenecks via min-cut."""
        reachable = self._bfs_reachable(source)
        
        min_cut_edges = set()
        for u in range(self.n):
            if u in reachable:
                for edge in self.solver.graph[u]:
                    if edge.to not in reachable and edge.capacity > 0:
                        if self._is_true_bottleneck(u, edge):
                            min_cut_edges.add((u, edge.to))
        
        return min_cut_edges
    
    def _is_true_bottleneck(self, u: int, edge: Edge) -> bool:
        """Verify edge is a true capacity bottleneck, not just low flow."""
        residual = edge.capacity - edge.flow
        return residual < edge.capacity * 0.1
    
    def _bfs_reachable(self, source: int) -> Set[int]:
        """Find reachable nodes in residual graph."""
        reachable = set()
        queue = deque([source])
        reachable.add(source)
        
        while queue:
            u = queue.popleft()
            for edge in self.solver.graph[u]:
                residual = edge.capacity - edge.flow
                if residual > 0 and edge.to not in reachable:
                    reachable.add(edge.to)
                    queue.append(edge.to)
        
        return reachable


class LogisticsNetworkOptimizer:
    """Main optimizer coordinating all components."""
    
    def __init__(self, network: List[List[int]], source: int, sink: int):
        self.original_network = network
        self.source = source
        self.sink = sink
        self.node_count = self._compute_node_count()
        self.solver = None
        self.analyzer = None
        self.multi_commodity_solver = None
        self.dynamic_manager = None
        self.node_manager = NodeMergeManager(self.node_count)
        self.edge_mapping = {}
        self.next_edge_id = 0
        
    def _compute_node_count(self) -> int:
        """Calculate total number of nodes."""
        max_node = max(self.source, self.sink)
        for edge in self.original_network:
            if len(edge) >= 2:
                max_node = max(max_node, edge[0], edge[1])
        return max_node + 1
    
    def _build_network(self, excluded_edges: Set[Tuple[int, int]] = None):
        """Build network with proper cost and priority handling."""
        if excluded_edges is None:
            excluded_edges = set()
        
        self.solver = MinCostMaxFlowSolver(self.node_count)
        self.multi_commodity_solver = MultiCommodityFlowSolver(self.node_count)
        
        edge_data = defaultdict(list)
        for edge in self.original_network:
            if len(edge) < 3:
                continue
            
            u = self.node_manager.apply_mapping(edge[0])
            v = self.node_manager.apply_mapping(edge[1])
            capacity = edge[2]
            cost = edge[3] if len(edge) > 3 else 1
            priority = edge[4] if len(edge) > 4 else 1
            
            if (u, v) not in excluded_edges and capacity > 0:
                edge_data[(u, v)].append((capacity, cost, priority))
        
        for (u, v), edges in edge_data.items():
            for capacity, cost, priority in edges:
                edge_id = self.next_edge_id
                self.next_edge_id += 1
                self.solver.add_edge(u, v, capacity, cost, priority, edge_id)
                self.edge_mapping[edge_id] = (u, v)
    
    def optimize(self) -> Tuple[int, int, Set[Tuple[int, int]]]:
        """Run full optimization pipeline."""
        self._build_network()
        
        max_flow, min_cost = self.solver.min_cost_max_flow(self.source, self.sink)
        
        self.analyzer = MinCutAnalyzer(self.solver)
        bottlenecks = self.analyzer.find_min_cut_edges(self.source)
        
        self.dynamic_manager = DynamicNetworkManager(self)
        
        return max_flow, min_cost, bottlenecks
    
    def optimize_multi_commodity(self, commodities: List[Tuple[int, int, int]]) -> Dict[int, int]:
        """Optimize for multiple commodity types."""
        self._build_network()
        
        for idx, (src, snk, demand) in enumerate(commodities):
            self.multi_commodity_solver.add_commodity(idx, src, snk, demand)
        
        return self.multi_commodity_solver.solve_multi_commodity(self.solver, self.edge_mapping)
    
    def update_with_edge_exclusion(self, excluded_edge: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """Dynamically update network when edge becomes unavailable."""
        self.dynamic_manager.invalidate_edge(excluded_edge[0], excluded_edge[1])
        self.dynamic_manager.incremental_update(self.source, self.sink)
        self.analyzer = MinCutAnalyzer(self.solver)
        return self.analyzer.find_min_cut_edges(self.source)
    
    def merge_nodes(self, node_a: int, node_b: int):
        """Merge two distribution centers."""
        new_node = self.node_count
        self.node_count += 1
        self.node_manager.merge_nodes(node_a, node_b, new_node)
        self._build_network()
    
    def get_bottleneck_list(self, bottlenecks: Set[Tuple[int, int]]) -> List[List[int]]:
        """Convert bottleneck set to sorted list."""
        return sorted([[u, v] for u, v in bottlenecks])


def optimize_logistics_flow(network: List[List[int]], source: int, sink: int) -> List[List[int]]:
    """
    Optimize logistics flow and identify critical bottlenecks.
    
    Args:
        network: List of edges [from, to, capacity, cost, priority]
        source: Source node ID
        sink: Sink node ID
    
    Returns:
        List of critical bottleneck edges [[u1, v1], [u2, v2], ...]
    """
    if not network:
        return []
    
    if source < 0 or sink < 0:
        return []
    
    if source == sink:
        return []
    
    valid_network = []
    for edge in network:
        if len(edge) >= 3 and edge[2] > 0:
            valid_network.append(edge)
    
    if not valid_network:
        return []
    
    try:
        optimizer = LogisticsNetworkOptimizer(valid_network, source, sink)
        max_flow, min_cost, bottlenecks = optimizer.optimize()
        
        if max_flow == 0:
            return []
        
        result = optimizer.get_bottleneck_list(bottlenecks)
        return result
    
    except Exception:
        return []


if __name__ == "__main__":
    network = [
        [0, 1, 10, 5, 3],
        [0, 1, 20, 3, 5],
        [1, 2, 5, 10, 2],
        [2, 3, 10, 2, 4],
        [0, 4, 15, 4, 3],
        [4, 2, 10, 6, 1]
    ]
    source = 0
    sink = 3
    
    result = optimize_logistics_flow(network, source, sink)
    print(f"Critical bottleneck edges: {result}")