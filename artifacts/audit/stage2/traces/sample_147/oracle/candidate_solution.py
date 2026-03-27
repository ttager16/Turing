from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
import heapq
from dataclasses import dataclass

@dataclass
class EdgeInfo:
    """Edge information"""
    time: int
    capacity: int
    cost: int

@dataclass
class RouteState:
    """Complete state for dynamic programming"""
    node: int
    path: Tuple[int, ...]
    time: int
    capacity: int
    cost: int
    checkpoints_visited: Tuple[int, ...]  # Ordered checkpoints visited so far
    
    def __lt__(self, other):
        return self.cost < other.cost
    
    def state_key(self) -> Tuple:
        """Unique state for memoization"""
        return (self.node, self.checkpoints_visited, self.time, self.capacity)

class GraphBuilder:
    """Builds and manages graph with conditional edges"""
    
    def __init__(self, num_nodes: int, edges: List[List[int]]):
        self.num_nodes = num_nodes
        self.graph = defaultdict(list)
        self.edge_map = {}
        self._build_graph(edges)
    
    def _build_graph(self, edges: List[List[int]]) -> None:
        """Build graph with validation"""
        for edge in edges:
            if len(edge) < 5:
                continue
            
            src, dst, time, capacity, cost = edge[:5]
            
            # Validate edge parameters
            if not self._validate_edge_params(src, dst, time, capacity, cost):
                continue
                
            self.graph[src].append(dst)
            self.edge_map[(src, dst)] = EdgeInfo(time, capacity, cost)
    
    def _validate_edge_params(self, src: int, dst: int, time: int, 
                         capacity: int, cost: int) -> bool:
        """Validate all edge parameters"""
        if not (0 <= src < self.num_nodes and 0 <= dst < self.num_nodes):
            return False
        if not (0 < time <= 1_000_000 and 0 < capacity <= 1_000_000):
            return False
        if not (0 < cost <= 1_000_000):
            return False
        return True
    
    def get_neighbors(self, node: int) -> List[int]:
        return self.graph.get(node, [])
    
    def get_edge_info(self, src: int, dst: int) -> Optional[EdgeInfo]:
        return self.edge_map.get((src, dst))

class OptimalRouteFinder:
    """Finds optimal routes with all constraints"""
    
    def __init__(self, graph: GraphBuilder, max_time: int, max_capacity: int,
             mandatory_checkpoints: List[int]):
        self.graph = graph
        self.max_time = max_time
        self.max_capacity = max_capacity
        self.mandatory_checkpoints = tuple(mandatory_checkpoints)
        self.checkpoint_indices = {cp: idx for idx, cp in enumerate(mandatory_checkpoints)}
    
    def find_optimal_single_route(self, start: int) -> Optional[RouteState]:
        """Find single route covering all checkpoints in order"""
        if not self.mandatory_checkpoints:
            return self._find_best_simple_route(start)
        
        # Priority queue: (cost, RouteState)
        pq = [RouteState(start, (start,), 0, 0, 0, ())]
        
        # Memoization: state_key -> minimum cost to reach that state
        visited = {}
        best_complete = None
        
        iterations = 0
        max_iterations = 100000  # Prevent infinite loops
        
        while pq and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(pq)
            
            state_key = current.state_key()
            
            # Skip if we've seen better state
            if state_key in visited and visited[state_key] <= current.cost:
                continue
            visited[state_key] = current.cost
            
            # Check if all checkpoints visited in order
            if self._all_checkpoints_covered(current.checkpoints_visited):
                if best_complete is None or current.cost < best_complete.cost:
                    best_complete = current
                continue  # Don't expand further
            
            # Expand neighbors
            for neighbor in self.graph.get_neighbors(current.node):
                new_state = self._expand_neighbor(current, neighbor)
                if new_state:
                    heapq.heappush(pq, new_state)
        
        return best_complete
    
    def _expand_neighbor(self, current: RouteState, neighbor: int) -> Optional[RouteState]:
        """Expand to neighbor with all constraint checks"""
        edge = self.graph.get_edge_info(current.node, neighbor)
        if not edge:
            return None
        
        new_time = current.time + edge.time
        new_capacity = current.capacity + edge.capacity
        new_cost = current.cost + edge.cost
        
        # Check global constraints
        if new_time > self.max_time or new_capacity > self.max_capacity:
            return None
        
        # Allow node revisits - no cycle prevention
        # State-based pruning in the main search loop handles redundancy
        
        new_path = current.path + (neighbor,)
        
        # Update checkpoints visited
        new_checkpoints = current.checkpoints_visited
        if self.mandatory_checkpoints:
            new_checkpoints = self._update_checkpoints(current.checkpoints_visited, neighbor)
            if new_checkpoints is None:  # Invalid checkpoint order
                return None
        
        return RouteState(neighbor, new_path, new_time, new_capacity, 
                        new_cost, new_checkpoints)
        
    def _update_checkpoints(self, visited: Tuple[int, ...], node: int) -> Optional[Tuple[int, ...]]:
        """Update checkpoints maintaining sequential order"""
        if node not in self.checkpoint_indices:
            return visited
        
        expected_index = len(visited)
        actual_index = self.checkpoint_indices[node]
        
        # Must visit checkpoints in order
        if actual_index != expected_index:
            return None
        
        return visited + (node,)
    
    def _all_checkpoints_covered(self, visited: Tuple[int, ...]) -> bool:
        """Check if all checkpoints visited"""
        return len(visited) == len(self.mandatory_checkpoints)
    
    def _find_best_simple_route(self, start: int) -> Optional[RouteState]:
        """Find best route when no checkpoints required"""
        pq = [RouteState(start, (start,), 0, 0, 0, ())]
        visited = {}
        best = None
        
        iterations = 0
        max_iterations = 10000
        
        while pq and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(pq)
            
            # Update best if this is a valid multi-node path
            if len(current.path) >= 2:
                if best is None or current.cost < best.cost:
                    best = current
            
            state_key = (current.node, current.time, current.capacity)
            if state_key in visited:
                continue
            visited[state_key] = True
            
            # Stop expanding if path too long
            if len(current.path) >= min(10, self.graph.num_nodes):
                continue
            
            for neighbor in self.graph.get_neighbors(current.node):
                new_state = self._expand_neighbor(current, neighbor)
                if new_state:
                    heapq.heappush(pq, new_state)
        
        return best

def optimize_delivery_routes(
    num_nodes: int,
    edges: List[List[int]],
    mandatory_checkpoints: List[int],
    global_max_time: int,
    global_max_capacity: int,
) -> List[int]:
    """
    Optimizes delivery routes with all constraints.
    
    Args:
        num_nodes: Number of nodes in the graph (1 to 1000)
        edges: List of edges [src, dst, time, capacity, cost, min_load_required(optional)]
        mandatory_checkpoints: Checkpoints to visit in sequential order
        global_max_time: Maximum time constraint (1 to 10^6)
        global_max_capacity: Maximum capacity constraint (1 to 10^6)
    
    Returns:
        Single optimal route as a list of node IDs, or empty list if no valid route exists
    """
    # Input validation
    if not isinstance(num_nodes, int) or num_nodes <= 0 or num_nodes > 1000:
        raise ValueError(f"num_nodes must be between 1 and 1000, got {num_nodes}")
    
    if not isinstance(global_max_time, int) or global_max_time <= 0 or global_max_time > 1_000_000:
        raise ValueError(f"global_max_time must be between 1 and 10^6, got {global_max_time}")
    
    if not isinstance(global_max_capacity, int) or global_max_capacity <= 0 or global_max_capacity > 1_000_000:
        raise ValueError(f"global_max_capacity must be between 1 and 10^6, got {global_max_capacity}")
    
    if not isinstance(edges, list) or len(edges) > 1000:
        raise ValueError(f"edges must be a list with at most 1000 elements")
    
    # Validate checkpoints
    for cp in mandatory_checkpoints:
        if not isinstance(cp, int) or cp < 0 or cp >= num_nodes:
            raise ValueError(f"Invalid checkpoint {cp}, must be in range [0, {num_nodes})")
    
    # Handle edge cases
    if not edges:
        return []
    
    # Build graph
    graph = GraphBuilder(num_nodes, edges)
    
    # Check if graph has any valid edges
    if not graph.edge_map:
        return []
    
    # Find single optimal route from all possible starting nodes
    route_finder = OptimalRouteFinder(
        graph, global_max_time, global_max_capacity,
        mandatory_checkpoints
    )
    
    best_route = None
    best_cost = float('inf')
    
    # Check all possible starting nodes to find globally optimal solution
    for start_node in range(num_nodes):  
        route = route_finder.find_optimal_single_route(start_node)
        
        if route:
            valid = (route.time <= global_max_time and 
                    route.capacity <= global_max_capacity)
            
            if mandatory_checkpoints:
                valid = valid and len(route.checkpoints_visited) == len(mandatory_checkpoints)
            
            if valid and route.cost < best_cost:
                best_route = route
                best_cost = route.cost
    
    return list(best_route.path) if best_route else []

# Example usage and tests
if __name__ == "__main__":
    num_nodes = 5
    edges = [
        [0, 1, 3, 10, 5],
        [1, 2, 2, 5, 3],
        [1, 3, 6, 8, 7],
        [2, 4, 4, 7, 4],
        [3, 4, 5, 5, 6]
    ]
    mandatory_checkpoints = [2, 4]  # Must visit in order
    global_max_time = 15
    global_max_capacity = 25
    
    result = optimize_delivery_routes(
        num_nodes, edges, mandatory_checkpoints,
        global_max_time, global_max_capacity
    )
    print(f"Routes: {result}")