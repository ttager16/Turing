from typing import List, Dict, Any, Tuple, Union
from collections import defaultdict
import heapq

class Edge:
    """Represents an edge in the flow network with capacity and cost tracking."""
    def __init__(self, to: int, cost: float, capacity: float = float('inf')):
        self.to = to
        self.cost = cost
        self.capacity = capacity
        self.flow = 0.0
        self.degradation_factor = 1.0
        self.original_capacity = capacity
        self.original_cost = cost

class FlowNetwork:
    """Advanced flow network with layered structure and dynamic capacity management."""
    def __init__(self, base_graph: List[List[List[Union[int, float]]]], node_caps: List[float]):
        self.n = len(base_graph)
        self.edges = [[] for _ in range(self.n)]
        self.node_caps = node_caps
        self.commodity_flows = defaultdict(list)
        self.priority_order = {"electronics": 1, "pharmaceuticals": 2, "perishables": 3, "textiles": 4, "chemicals": 5}
        self.incompatible_types = {"chemicals": {"perishables", "pharmaceuticals"}, "perishables": {"chemicals"}}
        
        for u, neighbors in enumerate(base_graph):
            for v, cost in neighbors:
                edge = Edge(v, cost, float('inf'))
                edge.original_capacity = float('inf')
                edge.original_cost = cost
                self.edges[u].append(edge)
    
    def set_edge_capacities_from_daily_changes(self, daily_capacity_changes: List[float], current_day: int):
        """Set edge capacities based on daily_capacity_changes for the current day, respecting existing flows."""
        if not daily_capacity_changes or current_day >= len(daily_capacity_changes):
            return
        
        capacity_value = daily_capacity_changes[current_day]
        for u in range(self.n):
            for edge in self.edges[u]:
                # Only set capacity if it hasn't been set yet (preserves shared resource principle)
                if edge.original_capacity == float('inf'):
                    edge.capacity = capacity_value
                    edge.original_capacity = capacity_value
                else:
                    # For edges already used by higher-priority commodities, 
                    # ensure capacity reflects available capacity (total - used)
                    edge.capacity = max(0, edge.original_capacity - edge.flow)

    def get_priority(self, commodity_type: str) -> int:
        """Get priority level for commodity type."""
        return self.priority_order.get(commodity_type, 6)

    def can_share_node(self, type1: str, type2: str) -> bool:
        """Check if two commodity types can share the same node."""
        return type2 not in self.incompatible_types.get(type1, set())

    def apply_path_specific_degradation(self, path: List[int], days_in_transit: int):
        """Apply capacity degradation to edges along a specific path based on days in transit."""
        degradation_factor = max(0.1, 1.0 - (days_in_transit * 0.1))
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            for edge in self.edges[u]:
                if edge.to == v:
                    edge.capacity = edge.original_capacity * degradation_factor
                    break

    def find_augmenting_path(self, source: int, sink: int, commodity_type: str, demand: float) -> List[int]:
        """Find augmenting path using modified Dijkstra with priority and compatibility constraints."""
        dist = [float('inf')] * self.n
        parent = [-1] * self.n
        dist[source] = 0.0
        pq = [(0.0, source)]
        
        while pq:
            d, u = heapq.heappop(pq)
            if u == sink:
                break
            if d > dist[u]:
                continue
                
            for edge in self.edges[u]:
                v = edge.to
                if edge.flow >= edge.capacity:
                    continue
                
                if not self._can_use_node(v, commodity_type):
                    continue
                
                new_dist = dist[u] + edge.cost
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    parent[v] = u
                    heapq.heappush(pq, (new_dist, v))
        
        if parent[sink] == -1:
            return []
            
        path = []
        v = sink
        while v != -1:
            path.append(v)
            v = parent[v]
        return path[::-1]
    
    def _can_use_node(self, node: int, commodity_type: str) -> bool:
        """Check if a node can be used by a commodity type considering cross-contamination."""
        for existing_type, flows in self.commodity_flows.items():
            if not self.can_share_node(commodity_type, existing_type):
                for u, v, flow in flows:
                    if flow > 0:
                        if v == node:
                            return False
                        if self._are_nodes_adjacent(node, u) or self._are_nodes_adjacent(node, v):
                            return False
        return True
    
    def _are_nodes_adjacent(self, node1: int, node2: int) -> bool:
        """Check if two nodes are directly adjacent (connected by an edge) in the graph."""
        for edge in self.edges[node1]:
            if edge.to == node2:
                return True
        for edge in self.edges[node2]:
            if edge.to == node1:
                return True
        return False
    
    def _reset_commodity_flows(self, commodity_type: str):
        """Reset flows only for the specified commodity, preserving other commodity flows."""
        commodity_flows = self.commodity_flows.get(commodity_type, [])
        
        for u, v, flow_amount in commodity_flows:
            for edge in self.edges[u]:
                if edge.to == v:
                    edge.flow -= flow_amount
                    break

    def send_flow(self, path: List[int], flow_amount: float, commodity_type: str):
        """Send flow along the given path."""
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            for edge in self.edges[u]:
                if edge.to == v:
                    edge.flow += flow_amount
                    self.commodity_flows[commodity_type].append((u, v, flow_amount))
                    break

    def compute_max_flow(self, source: int, sink: int, commodity_type: str, demand: float, time_window: Tuple[int, int] = None) -> float:
        """Compute maximum flow for a single commodity using layered approach with dynamic degradation."""
        total_flow = 0.0
        min_flow_threshold = demand * 0.2
        
        while total_flow < demand:
            path = self.find_augmenting_path(source, sink, commodity_type, demand - total_flow)
            if not path:
                break
            
            if time_window:
                start_day, end_day = time_window
                current_day = start_day + int(total_flow / demand * (end_day - start_day)) if demand > 0 else start_day
                days_in_transit = current_day - start_day
                self.apply_path_specific_degradation(path, days_in_transit)
                
            min_capacity = float('inf')
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                for edge in self.edges[u]:
                    if edge.to == v:
                        min_capacity = min(min_capacity, edge.capacity - edge.flow)
                        break
            
            if min_capacity <= 0:
                break
                
            flow_to_send = min(min_capacity, demand - total_flow)
            self.send_flow(path, flow_to_send, commodity_type)
            total_flow += flow_to_send
            
            if total_flow < min_flow_threshold and len(path) == 0:
                break
                
        return total_flow

    def calculate_total_cost(self) -> float:
        """Calculate total cost including transportation and storage."""
        total_cost = 0.0
        
        for u in range(self.n):
            for edge in self.edges[u]:
                total_cost += edge.flow * edge.original_cost
        
        for commodity_type, flows in self.commodity_flows.items():
            if not flows:
                continue
                
            # Get the source and sink for this commodity
            source = flows[0][0] if flows else 0
            sink = flows[-1][1] if flows else 0
            
            # Find all nodes used by this commodity
            nodes_used = set()
            for u, v, flow in flows:
                if flow > 0:
                    nodes_used.add(u)
                    nodes_used.add(v)
            
            # Apply storage cost to intermediate nodes (not source or sink)
            for node in nodes_used:
                if node != source and node != sink:
                    # Calculate flow through this intermediate node (count each flow only once)
                    node_flow = 0.0
                    for u, v, flow in flows:
                        if flow > 0 and v == node:  # Only count incoming flow to avoid double-counting
                            node_flow += flow
                    storage_cost = node_flow * 0.1
                    total_cost += storage_cost
        
        return total_cost

    def get_flow_matrix(self, num_commodities: int, commodity_order: List[str]) -> List[List[float]]:
        """Get flow matrix representation for all commodities in the specified order."""
        total_edges = sum(len(neighbors) for neighbors in self.edges)
        flow_matrix = [[0.0 for _ in range(total_edges)] for _ in range(num_commodities)]
        
        edge_idx = 0
        for u in range(self.n):
            for edge in self.edges[u]:
                for commodity_idx, commodity_type in enumerate(commodity_order):
                    flows = self.commodity_flows.get(commodity_type, [])
                    for flow_u, flow_v, flow_amount in flows:
                        if flow_u == u and flow_v == edge.to:
                            flow_matrix[commodity_idx][edge_idx] += flow_amount
                edge_idx += 1
                    
        return flow_matrix

def advanced_multi_commodity_flow_solver(
    base_graph: List[List[List[Union[int, float]]]],
    commodities: List[Dict[str, Any]],
    time_windows: List[List[Union[int, int]]],
    node_storage_caps: List[float]
) -> List[Union[List[List[float]], float]]:
    """Solve multi-commodity flow problem with advanced constraints and optimizations."""
    network = FlowNetwork(base_graph, node_storage_caps)
    
    original_commodity_order = [commodity["type_of_good"] for commodity in commodities]
    
    sorted_commodities = sorted(commodities, key=lambda x: network.get_priority(x["type_of_good"]))
    
    for i, commodity in enumerate(sorted_commodities):
        source = commodity["source"]
        sink = commodity["sink"]
        demand = commodity["demand"]
        commodity_type = commodity["type_of_good"]
        
        if i < len(time_windows):
            start_day, end_day = time_windows[i]
            time_pressure = max(1.0, (end_day - start_day + 1) / 3.0)
            if commodity_type == "perishables" and end_day - start_day < 2:
                for u in range(network.n):
                    for edge in network.edges[u]:
                        edge.capacity = edge.capacity * 0.5
                        edge.cost = edge.cost * 1.5
            elif commodity_type == "pharmaceuticals" and end_day - start_day < 3:
                for u in range(network.n):
                    for edge in network.edges[u]:
                        edge.capacity = edge.capacity * 0.8
                        edge.cost = edge.cost * 1.2
        
        daily_changes = commodity.get("daily_capacity_changes", [])
        if daily_changes and i < len(time_windows):
            start_day, end_day = time_windows[i]
            network.set_edge_capacities_from_daily_changes(daily_changes, start_day)
        
        time_window = time_windows[i] if i < len(time_windows) else None
        max_flow = network.compute_max_flow(source, sink, commodity_type, demand, time_window)
        
        min_flow_threshold = demand * 0.2
        if max_flow < min_flow_threshold:
            network._reset_commodity_flows(commodity_type)
            network.commodity_flows[commodity_type] = []
        else:
            current_flow = sum(flow for _, _, flow in network.commodity_flows[commodity_type])
            if current_flow < min_flow_threshold:
                additional_flow = min_flow_threshold - current_flow
                additional_path = network.find_augmenting_path(source, sink, commodity_type, additional_flow)
                if additional_path:
                    network.send_flow(additional_path, additional_flow, commodity_type)
    
    flow_matrix = network.get_flow_matrix(len(commodities), original_commodity_order)
    total_cost = network.calculate_total_cost()
    
    return [flow_matrix, total_cost]

if __name__ == '__main__':
    base_graph = [
        [[1, 2.0], [2, 5.0]],
        [[2, 1.5], [3, 3.0]],
        [[3, 2.0]],
        []
    ]
    commodities = [
        {"source": 0, "sink": 3, "demand": 15.0, "type_of_good": "electronics", "daily_capacity_changes": [20, 20, 5]},
        {"source": 0, "sink": 2, "demand": 10.0, "type_of_good": "perishables", "daily_capacity_changes": [10, 10, 10]}
    ]
    time_windows = [[0, 1], [0, 2]]
    node_storage_caps = [10.0, 5.0, 20.0, 0.0]
    
    result = advanced_multi_commodity_flow_solver(base_graph, commodities, time_windows, node_storage_caps)
    print("Flow Matrix:", result[0])
    print("Total Cost:", result[1])