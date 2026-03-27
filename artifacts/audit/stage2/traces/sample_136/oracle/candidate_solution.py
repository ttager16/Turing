from typing import Dict, List, Tuple, Any
import heapq
from collections import defaultdict

# Environmental hazard cost multiplier: When an edge has environmental hazards
# (e.g., flooding, ice) that are currently active, the edge traversal cost is
# multiplied by this factor. A value of 2.0 indicates that hazardous conditions
# double the cost, representing increased time, risk, and resource consumption.
HAZARD_COST_MULTIPLIER = 2.0

# Minimum path length for multi-node routes: A valid route with edges requires
# at least 2 nodes (start and end) to form a traversable path. Single-node paths
# (where start == end) are handled as a special case and always valid.
MIN_VALID_PATH_LENGTH = 2


def compute_multilayer_min_cost_route(
    layered_graph: Dict[str, List[Dict[str, Any]]],
    vehicle_type: str,
    start_node: int,
    end_node: int,
    current_time: int,
    environment_state: Dict[str, Any],
    concurrency_tracker: Dict[str, int]
) -> List[int]:
    """
    Calculate a minimum-cost route through a multi-layer DAG under:
    1) Vehicle-type access restrictions.
    2) Time-window constraints.
    3) Reactive capacity updates tracked in concurrency_tracker.
    4) Dynamic environmental hazards.

    Returns a list of node IDs forming the optimized path.
    """
    
    if layered_graph and isinstance(next(iter(layered_graph.keys())), str):
        layered_graph = {int(k): v for k, v in layered_graph.items()}
    
    start_node = int(start_node) if isinstance(start_node, str) else start_node
    end_node = int(end_node) if isinstance(end_node, str) else end_node
    current_time = int(current_time) if isinstance(current_time, str) else current_time
    
    if concurrency_tracker:
        first_key = next(iter(concurrency_tracker.keys()))
        if ',' in first_key:
            concurrency_tracker = {k.replace(',', '_'): v for k, v in concurrency_tracker.items()}
    
    normalized_graph = {}
    for node, edges in layered_graph.items():
        normalized_edges = []
        for edge in edges:
            if isinstance(edge, list):
                neighbor, edge_attrs = edge[0], edge[1]
                normalized_edge = {'neighbor': neighbor, **edge_attrs}
                normalized_edges.append(normalized_edge)
            else:
                normalized_edges.append(edge)
        normalized_graph[node] = normalized_edges
    layered_graph = normalized_graph
    
    def is_edge_accessible(edge_data: Dict[str, Any], from_node: int, to_node: int) -> Tuple[bool, float]:
        if not _check_vehicle_access(edge_data):
            return False, float('inf')
        
        if not _check_time_window(edge_data):
            return False, float('inf')
        
        if not _check_capacity(edge_data, from_node, to_node):
            return False, float('inf')
        
        cost = _calculate_edge_cost(edge_data)
        return True, cost
    
    def _check_vehicle_access(edge_data: Dict[str, Any]) -> bool:
        vehicle_access = edge_data.get('vehicle_access', [])
        return vehicle_type in vehicle_access
    
    def _check_time_window(edge_data: Dict[str, Any]) -> bool:
        time_windows = edge_data.get('time_windows', [])
        if not time_windows:
            return True
        
        for start_time, end_time in time_windows:
            if start_time <= current_time <= end_time:
                return True
        return False
    
    def _check_capacity(edge_data: Dict[str, Any], from_node: int, to_node: int) -> bool:
        capacity = edge_data.get('capacity', float('inf'))
        edge_key = f'{from_node}_{to_node}'
        current_usage = concurrency_tracker.get(edge_key, 0)
        return current_usage < capacity
    
    def _calculate_edge_cost(edge_data: Dict[str, Any]) -> float:
        base_cost = edge_data.get('base_cost', 1)
        cost = base_cost
        
        env_limits = edge_data.get('env_limits', {})
        # Apply cost multiplier when edge requires a hazard AND that hazard is active
        for hazard, required in env_limits.items():
            if required and environment_state.get(hazard, False):
                cost *= HAZARD_COST_MULTIPLIER
        
        return cost
    
    distances = {node: float('inf') for node in layered_graph}
    distances[start_node] = 0
    
    previous = {node: None for node in layered_graph}
    
    priority_queue = [(0, start_node)]
    visited = set()
    
    while priority_queue:
        current_cost, current_node = heapq.heappop(priority_queue)
        
        if current_node in visited:
            continue
        
        visited.add(current_node)
        
        if current_node == end_node:
            break
        
        if current_cost > distances[current_node]:
            continue
        
        neighbors = layered_graph.get(current_node, [])
        
        for edge_data in neighbors:
            neighbor = edge_data.get('neighbor')
            if neighbor is None:
                continue
            
            accessible, edge_cost = is_edge_accessible(edge_data, current_node, neighbor)
            
            if not accessible:
                continue
            
            new_cost = current_cost + edge_cost
            
            if new_cost < distances[neighbor]:
                distances[neighbor] = new_cost
                previous[neighbor] = current_node
                heapq.heappush(priority_queue, (new_cost, neighbor))
    
    if distances[end_node] == float('inf'):
        return []
    
    path = []
    current = end_node
    while current is not None:
        path.append(current)
        current = previous[current]
    
    path.reverse()
    return path


class DynamicGraphManager:
    def __init__(self, layered_graph: Dict[str, List[Dict[str, Any]]]):
        self.graph = layered_graph
        self.edge_index = self._build_edge_index()
        self.concurrency_tracker = defaultdict(int)
    
    def _build_edge_index(self) -> Dict[str, Dict[str, Any]]:
        edge_index = {}
        for node, edges in self.graph.items():
            for edge_data in edges:
                neighbor = edge_data.get('neighbor')
                if neighbor is not None:
                    edge_key = f'{node}_{neighbor}'
                    edge_index[edge_key] = edge_data
        return edge_index
    
    def update_edge_attribute(self, from_node: int, to_node: int, 
                             attribute: str, value: Any):
        edge_key = f'{from_node}_{to_node}'
        if edge_key in self.edge_index:
            self.edge_index[edge_key][attribute] = value
    
    def reserve_edge(self, from_node: int, to_node: int) -> bool:
        edge_key = f'{from_node}_{to_node}'
        edge_data = self.edge_index.get(edge_key)
        
        if not edge_data:
            return False
        
        capacity = edge_data.get('capacity', float('inf'))
        current_usage = self.concurrency_tracker[edge_key]
        
        if current_usage < capacity:
            self.concurrency_tracker[edge_key] += 1
            return True
        return False
    
    def release_edge(self, from_node: int, to_node: int):
        edge_key = f'{from_node}_{to_node}'
        if self.concurrency_tracker[edge_key] > 0:
            self.concurrency_tracker[edge_key] -= 1
    
    def find_route(self, vehicle_type: str, start_node: int, end_node: int,
                   current_time: int, environment_state: Dict[str, Any]) -> List[int]:
        return compute_multilayer_min_cost_route(
            self.graph,
            vehicle_type,
            start_node,
            end_node,
            current_time,
            environment_state,
            self.concurrency_tracker
        )
    
    def batch_route_query(self, queries: List[Dict[str, Any]]) -> List[List[int]]:
        results = []
        for query in queries:
            route = self.find_route(
                query['vehicle_type'],
                query['start_node'],
                query['end_node'],
                query['current_time'],
                query['environment_state']
            )
            results.append(route)
        return results


def validate_route(route: List[int], layered_graph: Dict[str, List[Dict[str, Any]]],
                   vehicle_type: str, current_time: int, 
                   environment_state: Dict[str, Any],
                   concurrency_tracker: Dict[str, int]) -> bool:
    if not route or len(route) < MIN_VALID_PATH_LENGTH:
        return len(route) == 1
    
    for i in range(len(route) - 1):
        from_node = route[i]
        to_node = route[i + 1]
        
        neighbors = layered_graph.get(from_node, [])
        edge_found = False
        
        for edge_data in neighbors:
            neighbor = edge_data.get('neighbor')
            if neighbor == to_node:
                edge_found = True
                
                if vehicle_type not in edge_data.get('vehicle_access', []):
                    return False
                
                time_windows = edge_data.get('time_windows', [])
                if time_windows:
                    valid_time = any(start <= current_time <= end 
                                   for start, end in time_windows)
                    if not valid_time:
                        return False
                
                capacity = edge_data.get('capacity', float('inf'))
                edge_key = f'{from_node}_{to_node}'
                current_usage = concurrency_tracker.get(edge_key, 0)
                if current_usage >= capacity:
                    return False
                
                break
        
        if not edge_found:
            return False
    
    return True


def main():
    """
    Example function showing sample usage of compute_multilayer_min_cost_route.

    """
    layered_graph = {
        "0": [
            [1, {
                'vehicle_access': ['electric', 'bicycle'],
                'time_windows': [[0, 5], [10, 15]],
                'env_limits': {'flooded': False},
                'base_cost': 5,
                'capacity': 2
            }],
            [2, {
                'vehicle_access': ['diesel', 'electric'],
                'time_windows': [[0, 24]],
                'env_limits': {'icy': True},
                'base_cost': 7,
                'capacity': 3
            }]
        ],
        "1": [
            [3, {
                'vehicle_access': ['electric'],
                'time_windows': [[10, 20]],
                'env_limits': {'flooded': False},
                'base_cost': 2,
                'capacity': 1
            }]
        ],
        "2": [
            [3, {
                'vehicle_access': ['diesel', 'electric'],
                'time_windows': [[0, 8], [16, 24]],
                'env_limits': {'icy': True},
                'base_cost': 3,
                'capacity': 2
            }]
        ],
        "3": []
    }

    vehicle_type = 'electric'
    start_node = 0
    end_node = 3
    current_time = 11
    environment_state = {'flooded': False, 'icy': True}
    concurrency_tracker = {
        '0,1': 1,
        '0,2': 0,
        '1,3': 0,
        '2,3': 0
    }

    result = compute_multilayer_min_cost_route(
        layered_graph,
        vehicle_type,
        start_node,
        end_node,
        current_time,
        environment_state,
        concurrency_tracker
    )
    
    print(result)


if __name__ == "__main__":
    main()