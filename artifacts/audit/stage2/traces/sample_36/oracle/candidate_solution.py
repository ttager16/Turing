from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Set, Any, Union
from collections import defaultdict
from threading import Lock, Thread
import heapq

class RouteDecompositionBase(ABC):
    """Abstract base class for route decomposition and optimization."""
    
    @abstractmethod
    def decompose_network(self, graph: Dict[str, List[Tuple[str, float]]]) -> List[Any]:
        """Decompose network into manageable segments."""
        ...
    
    @abstractmethod
    def verify_capacity(self, segment: Any, constraints: Dict[str, float]) -> bool:
        """Verify segment satisfies capacity constraints."""
        ...
    
    @abstractmethod
    def recalculate_state(self, event: Dict[str, Any]) -> None:
        """Recalculate state for real-time events."""
        ...
    
    @abstractmethod
    def compute_inter_segment_flow(self, segments: List[Any]) -> Dict[str, float]:
        """Compute flow constraints between segments."""
        ...
    
    @abstractmethod
    def merge_partial_solutions(self, solutions: List[Any]) -> Any:
        """Merge partial solutions from segments."""
        ...
    
    @abstractmethod
    def acquire_resource_lock(self) -> None:
        """Acquire resource lock for thread safety."""
        ...
    
    @abstractmethod
    def release_resource_lock(self) -> None:
        """Release resource lock."""
        ...


class HeavyLightDecomposition:
    """Heavy-Light Decomposition for graph partitioning."""
    
    def __init__(self, graph: Dict[str, List[Tuple[str, float]]]):
        self.graph = graph
        self.parent = {}
        self.depth = {}
        self.heavy_child = {}
        self.chain_head = {}
        self.chain_id = {}
        self.subtree_size = {}
        self.current_chain = 0
        self.chains = defaultdict(list)
        
    def build_tree(self, root: str, visited: Set[str]) -> str:
        """Build spanning tree using DFS."""
        if not self.graph or root not in self.graph:
            return root
            
        stack = [(root, None, 0)]
        tree_root = root
        
        while stack:
            node, par, dep = stack.pop()
            if node in visited:
                continue
                
            visited.add(node)
            self.parent[node] = par
            self.depth[node] = dep
            
            for neighbor, _ in self.graph.get(node, []):
                if neighbor not in visited:
                    stack.append((neighbor, node, dep + 1))
        
        return tree_root
    
    def calculate_subtree_sizes(self, node: str, visited: Set[str]) -> int:
        """Calculate subtree sizes."""
        if node in visited:
            return 0
            
        visited.add(node)
        size = 1
        max_subtree = 0
        heavy = None
        
        for neighbor, _ in self.graph.get(node, []):
            if neighbor not in visited and self.parent.get(neighbor) == node:
                subtree_size = self.calculate_subtree_sizes(neighbor, visited)
                size += subtree_size
                if subtree_size > max_subtree:
                    max_subtree = subtree_size
                    heavy = neighbor
        
        self.subtree_size[node] = size
        if heavy:
            self.heavy_child[node] = heavy
            
        return size
    
    def decompose(self, root: str) -> Dict[int, List[str]]:
        """Perform HLD decomposition."""
        visited = set()
        root = self.build_tree(root, visited)
        
        visited.clear()
        self.calculate_subtree_sizes(root, visited)
        
        self._build_chains(root, root)
        
        return dict(self.chains)
    
    def _build_chains(self, node: str, head: str) -> None:
        """Build HLD chains."""
        if node is None:
            return
            
        self.chain_head[node] = head
        self.chain_id[node] = self.current_chain
        self.chains[self.current_chain].append(node)
        
        if node in self.heavy_child:
            self._build_chains(self.heavy_child[node], head)
        
        for neighbor, _ in self.graph.get(node, []):
            if self.parent.get(neighbor) == node and neighbor != self.heavy_child.get(node):
                self.current_chain += 1
                self._build_chains(neighbor, neighbor)


class NetworkState:
    """Thread-safe network state tracking."""
    
    def __init__(self):
        self.node_throughput = defaultdict(float)
        self.edge_capacity = {}
        self.edge_usage = defaultdict(float)
        self.future_demands = []
        self.lock = Lock()
        
    def update_throughput(self, node: str, value: float) -> None:
        """Update node throughput."""
        with self.lock:
            self.node_throughput[node] = value
    
    def update_capacity(self, edge: Tuple[str, str], capacity: float) -> None:
        """Update edge capacity."""
        with self.lock:
            self.edge_capacity[edge] = capacity
    
    def get_available_capacity(self, edge: Tuple[str, str]) -> float:
        """Get available edge capacity."""
        with self.lock:
            total = self.edge_capacity.get(edge, float('inf'))
            used = self.edge_usage.get(edge, 0.0)
            return total - used
    
    def reserve_capacity(self, edge: Tuple[str, str], amount: float) -> bool:
        """Reserve edge capacity."""
        with self.lock:
            total = self.edge_capacity.get(edge, float('inf'))
            used = self.edge_usage.get(edge, 0.0)
            available = total - used
            if available >= amount:
                self.edge_usage[edge] += amount
                return True
            return False


class AdvancedRouteOptimizer(RouteDecompositionBase):
    """Route optimizer with decomposition, DP, and backtracking."""
    
    def __init__(self, cities: List[str], routes: List[Tuple[str, str, float]], 
                 traffic_data: Dict[str, float]):
        self.cities = cities
        self.routes = routes
        self.traffic_data = traffic_data
        self.graph = defaultdict(list)
        self.state = NetworkState()
        self.decomposition = None
        self.lock = Lock()
        self.dp_cache = {}
        self.base_weights = {}
        
        self._build_graph()
        self._initialize_state()
    
    def _build_graph(self) -> None:
        """Build adjacency list with traffic multipliers."""
        self.graph.clear()
        
        if not self.base_weights:
            for src, dst, weight in self.routes:
                self.base_weights[(src, dst)] = weight
                if (dst, src) not in self.base_weights:
                    self.base_weights[(dst, src)] = weight
        
        for (src, dst), weight in self.base_weights.items():
            # Ignore self-loops in adjacency
            if src == dst:
                continue
            traffic_key1 = f"{src}-{dst}"
            traffic_key2 = f"{dst}-{src}"
            
            traffic_mult = self.traffic_data.get(traffic_key1, 
                          self.traffic_data.get(traffic_key2, 1.0))
            
            adjusted_weight = weight * traffic_mult
            self.graph[src].append((dst, adjusted_weight))
    
    def _initialize_state(self) -> None:
        """Initialize edge capacities."""
        for src, dst, weight in self.routes:
            # Ignore self-loop capacities
            if src == dst:
                continue
            base_capacity = 1000.0 / weight if weight > 0 else 1000.0
            self.state.update_capacity((src, dst), base_capacity)
            self.state.update_capacity((dst, src), base_capacity)
    
    def _build_capacity_constraints_from_future_demands(self) -> Dict[str, float]:
        """Aggregate required capacities from queued future shipments."""
        constraints: Dict[str, float] = defaultdict(float)
        for demand in self.state.future_demands:
            fr = demand.get('from') or demand.get('src')
            to = demand.get('to') or demand.get('dst')
            volume = demand.get('volume', 0.0)
            try:
                vol = float(volume)
            except Exception:
                vol = 0.0
            if fr and to and vol > 0.0:
                constraints[f"{fr}-{to}"] += vol
        return dict(constraints)
    
    def decompose_network(self, graph: Dict[str, List[Tuple[str, float]]]) -> List[Any]:
        """Decompose network using HLD."""
        if not graph or not self.cities:
            return []
        
        hld = HeavyLightDecomposition(dict(graph))
        
        start_node = self.cities[0]
        chains = hld.decompose(start_node)
        
        segments = []
        for chain_id, nodes in chains.items():
            segment = {
                'chain_id': chain_id,
                'nodes': nodes,
                'subgraph': self._extract_subgraph(nodes, graph),
                'head': nodes[0] if nodes else None
            }
            segments.append(segment)
        
        return segments
    
    def _extract_subgraph(self, nodes: List[str], 
                         graph: Dict[str, List[Tuple[str, float]]]) -> Dict[str, List[Tuple[str, float]]]:
        """Extract subgraph for nodes."""
        subgraph = defaultdict(list)
        node_set = set(nodes)
        
        for node in nodes:
            for neighbor, weight in graph.get(node, []):
                if neighbor in node_set:
                    subgraph[node].append((neighbor, weight))
        
        return dict(subgraph)
    
    def verify_capacity(self, segment: Any, constraints: Dict[str, float]) -> bool:
        """Verify segment capacity constraints."""
        if not segment or not isinstance(segment, dict):
            return True
        
        nodes = segment.get('nodes', [])
        
        for node in nodes:
            for neighbor, _weight in self.graph.get(node, []):
                # Ignore self-loops
                if neighbor == node:
                    continue
                if neighbor in nodes:
                    edge = (node, neighbor)
                    min_capacity = constraints.get(f"{node}-{neighbor}", 0.0)
                    
                    if self.state.get_available_capacity(edge) < min_capacity:
                        return False
        
        return True
    
    def recalculate_state(self, event: Dict[str, Any]) -> None:
        """Handle real-time events: closure, congestion, shipments."""
        event_type = event.get('type')
        
        if event_type == 'closure':
            affected_edge = event.get('edge')
            if affected_edge:
                self.state.update_capacity(affected_edge, 0.0)
                
        elif event_type == 'congestion':
            affected_edge = event.get('edge')
            multiplier = event.get('multiplier', 1.5)
            
            if affected_edge:
                if affected_edge in self.base_weights:
                    self.base_weights[affected_edge] *= multiplier
                
                self._build_graph()
                
        elif event_type == 'new_shipment':
            self.state.future_demands.append(event)
        
        self.dp_cache.clear()
    
    def compute_inter_segment_flow(self, segments: List[Any]) -> Dict[str, float]:
        """Compute inter-segment flow constraints."""
        flow_constraints = {}
        
        for i, seg1 in enumerate(segments):
            for j, seg2 in enumerate(segments):
                if i >= j:
                    continue
                
                nodes1 = set(seg1.get('nodes', []))
                nodes2 = set(seg2.get('nodes', []))
                
                total_flow = 0.0
                
                for node1 in nodes1:
                    for neighbor, _weight in self.graph.get(node1, []):
                        # Ignore self-loops
                        if neighbor == node1:
                            continue
                        if neighbor in nodes2:
                            edge = (node1, neighbor)
                            capacity = self.state.get_available_capacity(edge)
                            total_flow += capacity
                
                if total_flow > 0:
                    key = f"{seg1.get('chain_id')}-{seg2.get('chain_id')}"
                    flow_constraints[key] = total_flow
        
        return flow_constraints
    
    def merge_partial_solutions(self, solutions: List[Any]) -> Any:
        """Merge partial solutions with path stitching."""
        if not solutions:
            return []
        
        all_edges = []
        for solution in solutions:
            if isinstance(solution, list):
                all_edges.extend(solution)
        
        if not all_edges:
            return []
        
        return self._stitch_path_segments(all_edges)
    
    def _stitch_path_segments(self, edges: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Stitch path segments into continuous path."""
        if not edges or not self.cities:
            return edges
        
        # Drop self-loops from partial solutions
        edges = [(src, dst) for (src, dst) in edges if src != dst]

        start = self.cities[0]
        end = self.cities[-1]
        
        edge_graph = defaultdict(list)
        for src, dst in edges:
            edge_graph[src].append(dst)
        
        path = []
        visited = set()
        
        def dfs(current: str, target: str) -> bool:
            if current == target:
                return True
            
            if current in visited:
                return False
            
            visited.add(current)
            
            for next_node in edge_graph.get(current, []):
                path.append((current, next_node))
                if dfs(next_node, target):
                    return True
                path.pop()
            
            return False
        
        if dfs(start, end):
            return path
        
        return self._build_bridge_path(start, end, edges)
    
    def _build_bridge_path(self, start: str, end: str, 
                          partial_edges: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Build bridge path connecting partial segments."""
        partial_nodes = set()
        for src, dst in partial_edges:
            partial_nodes.add(src)
            partial_nodes.add(dst)
        
        if start not in partial_nodes or end not in partial_nodes:
            _, full_path = self._dynamic_programming_route(start, end)
            return full_path
        
        edge_map = defaultdict(set)
        for src, dst in partial_edges:
            edge_map[src].add(dst)
        
        current = start
        result_path = []
        visited = set()
        
        while current != end and len(visited) < len(partial_nodes):
            if current in visited:
                break
            visited.add(current)
            
            if current in edge_map and edge_map[current]:
                next_node = min(edge_map[current], 
                              key=lambda n: self.graph.get(current, [(n, 0)])[0][1] 
                              if any(x[0] == n for x in self.graph.get(current, [])) else float('inf'))
                result_path.append((current, next_node))
                current = next_node
            else:
                break
        
        if current == end:
            return result_path
        
        _, fallback = self._dynamic_programming_route(start, end)
        return fallback
    
    def _dynamic_programming_route(self, start: str, end: str) -> Tuple[float, List[Tuple[str, str]]]:
        """Find optimal route using DP with capacity constraints."""
        cache_key = (start, end)
        if cache_key in self.dp_cache:
            return self.dp_cache[cache_key]
        
        constraints = self._build_capacity_constraints_from_future_demands()
        
        cities_set = set(self.cities)
        dist = {node: float('inf') for node in self.cities}
        dist[start] = 0.0
        predecessor = {}
        
        pq = [(0.0, start)]
        
        while pq:
            current_dist, current = heapq.heappop(pq)
            
            if current_dist > dist[current]:
                continue
            
            if current == end:
                break
            
            for neighbor, weight in self.graph.get(current, []):
                # Ignore self-loops
                if neighbor == current:
                    continue
                if neighbor not in cities_set:
                    continue
                    
                edge = (current, neighbor)
                available_capacity = self.state.get_available_capacity(edge)
                required_capacity = constraints.get(f"{current}-{neighbor}", 0.0)
                
                if available_capacity <= 0 or available_capacity < required_capacity:
                    continue
                
                capacity_penalty = 1.0 / (available_capacity + 1.0)
                adjusted_weight = weight + capacity_penalty
                
                new_dist = current_dist + adjusted_weight
                
                if new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    predecessor[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))
        
        if dist[end] == float('inf'):
            self.acquire_resource_lock()
            try:
                self.dp_cache[cache_key] = (float('inf'), [])
            finally:
                self.release_resource_lock()
            return (float('inf'), [])
        
        path = []
        current = end
        while current in predecessor:
            prev = predecessor[current]
            path.append((prev, current))
            current = prev
        
        path.reverse()
        
        result = (dist[end], path)
        self.acquire_resource_lock()
        try:
            self.dp_cache[cache_key] = result
        finally:
            self.release_resource_lock()
        
        return result
    
    def _backtracking_route(self, start: str, end: str, 
                           forbidden_edges: Set[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Find alternative routes avoiding forbidden edges."""
        path = []
        visited = set()
        
        def backtrack(current: str, target: str) -> bool:
            if current == target:
                return True
            
            if current in visited:
                return False
            
            visited.add(current)
            
            neighbors = [(neighbor, weight) for neighbor, weight in self.graph.get(current, [])]
            neighbors.sort(key=lambda x: x[1])
            
            for neighbor, weight in neighbors:
                edge = (current, neighbor)
                # Ignore self-loops
                if neighbor == current:
                    continue
                
                if edge in forbidden_edges:
                    continue
                
                if neighbor in visited:
                    continue
                
                path.append(edge)
                
                if backtrack(neighbor, target):
                    return True
                
                path.pop()
            
            visited.remove(current)
            return False
        
        if backtrack(start, end):
            return path
        
        return []
    
    def optimize_with_concurrency(self, start: str, end: str) -> List[Tuple[str, str]]:
        """Parallel optimization with threading and flow constraints."""
        segments = self.decompose_network(self.graph)
        
        if not segments:
            _cost, path = self._dynamic_programming_route(start, end)
            return path
        
        flow_constraints = self.compute_inter_segment_flow(segments)
        constraints = self._build_capacity_constraints_from_future_demands()
        
        partial_solutions = []
        threads = []
        
        def process_segment(segment: Any) -> None:
            nodes = segment.get('nodes', [])
            if not nodes or len(nodes) < 2:
                return
            
            # Enforce capacity requirements from future demands on this segment
            if not self.verify_capacity(segment, constraints):
                return
            
            seg_start = nodes[0]
            seg_end = nodes[-1]
            
            for node in nodes:
                throughput = self.state.node_throughput.get(node, 0.0)
                if throughput > 100.0:
                    return
            
            chain_id = segment.get('chain_id')
            min_flow = float('inf')
            for key, flow in flow_constraints.items():
                if str(chain_id) in key:
                    min_flow = min(min_flow, flow)
            
            if min_flow < 1.0:
                return
            
            _cost, path = self._dynamic_programming_route(seg_start, seg_end)
            
            if path:
                self.acquire_resource_lock()
                try:
                    partial_solutions.append(path)
                finally:
                    self.release_resource_lock()
        
        for segment in segments[:5]:
            thread = Thread(target=process_segment, args=(segment,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        if partial_solutions:
            merged = self.merge_partial_solutions(partial_solutions)
            
            if self._is_valid_path(merged, start, end):
                return merged
        
        _cost, path = self._dynamic_programming_route(start, end)
        return path
    
    def _is_valid_path(self, path: List[Tuple[str, str]], start: str, end: str) -> bool:
        """Validate path connectivity."""
        if not path:
            return False
        
        # Disallow any self-loops
        for src, dst in path:
            if src == dst:
                return False

        if path[0][0] != start:
            return False
        
        if path[-1][1] != end:
            return False
        
        for i in range(len(path) - 1):
            if path[i][1] != path[i + 1][0]:
                return False
        
        return True
    
    def acquire_resource_lock(self) -> None:
        """Acquire resource lock."""
        self.lock.acquire()
    
    def release_resource_lock(self) -> None:
        """Release resource lock."""
        self.lock.release()
    
    def adaptive_route_optimization(self, start: str, end: str, 
                                   events: List[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
        """Main optimization with real-time adaptation."""
        if events:
            for event in events:
                self.recalculate_state(event)
        
        cost, initial_path = self._dynamic_programming_route(start, end)
        
        if cost == float('inf'):
            forbidden = set()
            
            for src, dst in [(s, d) for s, d, _ in self.routes]:
                edge = (src, dst)
                if self.state.get_available_capacity(edge) <= 0:
                    forbidden.add(edge)
            
            alternative_path = self._backtracking_route(start, end, forbidden)
            
            if alternative_path:
                return alternative_path
        
        return initial_path


def optimize_delivery_routes(
    cities: List[str],
    routes: List[List[Union[str, float]]],
    traffic_data: Dict[str, float]
) -> List[List[str]]:
    """
    Optimize delivery routes using HLD decomposition and DP.
    
    Args:
        cities: List of cities from start to end
        routes: List[List[Union[str, float]]]
        traffic_data: Traffic multipliers for "src-dst" keys
    
    Returns:
        List of route segments forming optimal path
    """
    if not cities or len(cities) < 2:
        return []
    
    if not routes:
        return []
    
    routes = [tuple(route) for route in routes]
    
    optimizer = AdvancedRouteOptimizer(cities, routes, traffic_data)
    
    start_city = cities[0]
    end_city = cities[-1]
    
    segments = optimizer.decompose_network(optimizer.graph)
    
    if len(segments) > 1:
        concurrent_route = optimizer.optimize_with_concurrency(start_city, end_city)
        
        if concurrent_route and optimizer._is_valid_path(concurrent_route, start_city, end_city):
            return [list(route) for route in concurrent_route]
    
    optimal_route = optimizer.adaptive_route_optimization(start_city, end_city)
    optimal_route = [list(route) for route in optimal_route]
    return optimal_route


if __name__ == "__main__":
    cities = ["A", "B", "C", "D", "E"]
    routes = [
        ["A", "B", 12.0], ["B", "C", 7.5], ["A", "C", 25.0],
        ["C", "D", 3.0],  ["B", "D", 16.0], ["D", "E", 6.0]
    ]
    traffic_data = {
        "A-B": 0.9, "B-C": 1.1, "A-C": 1.3,
        "C-D": 0.5, "B-D": 1.2, "D-E": 0.8
    }
    
    result = optimize_delivery_routes(cities, routes, traffic_data)
    print(result)