import collections
from typing import List, Dict, Tuple, Set, Any, Optional


class TrafficFlowException(Exception):
    """Base exception for traffic flow errors."""
    pass


class InvalidNodeError(TrafficFlowException):
    """Invalid node configuration."""
    pass


class InvalidEdgeError(TrafficFlowException):
    """Invalid edge configuration."""
    pass


class InvalidStrategyError(TrafficFlowException):
    """Invalid flow strategy."""
    pass


class InvalidMultiplierError(TrafficFlowException):
    """Invalid time multiplier."""
    pass


class InvalidCommodityError(TrafficFlowException):
    """Invalid commodity configuration."""
    pass


class NoPathError(TrafficFlowException):
    """No path exists from source to sink."""
    pass


class InvalidRestrictionError(TrafficFlowException):
    """Invalid restriction configuration."""
    pass


class Edge:
    """Represents a directed edge in the flow network."""
    
    def __init__(self, u: int, v: int, capacity: int, idx: int):
        """Initialize edge."""
        self.u = u
        self.v = v
        self.capacity = capacity
        self.idx = idx
        self.commodity_flows = {}
        self.total_flow = 0
        self.rev = None


    def get_residual(self) -> int:
        """Get residual capacity."""
        return self.capacity - self.total_flow


    def add_flow(self, commodity_id: int, flow: int):
        """Add flow for a commodity."""
        if commodity_id not in self.commodity_flows:
            self.commodity_flows[commodity_id] = 0
        self.commodity_flows[commodity_id] += flow
        self.total_flow += flow


    def remove_flow(self, commodity_id: int, flow: int):
        """Remove flow for a commodity."""
        if commodity_id in self.commodity_flows:
            self.commodity_flows[commodity_id] -= flow
            self.total_flow -= flow


    def get_commodity_flow(self, commodity_id: int) -> int:
        """Get flow for specific commodity."""
        return self.commodity_flows.get(commodity_id, 0)


    def is_saturated(self) -> bool:
        """Check if edge is at full capacity."""
        return self.total_flow == self.capacity


    def has_residual(self) -> bool:
        """Check if edge has available capacity."""
        return self.get_residual() > 0


    def __repr__(self):
        return f"Edge({self.u}->{self.v}, cap={self.capacity}, flow={self.total_flow})"


class MultiCommodityNetwork:
    """Multi-commodity flow network."""
    
    def __init__(self, nodes: List[int], edges: List[List[int]], multipliers: List[float], num_commodities: int):
        """Initialize network."""
        self.nodes = nodes
        self.n = len(nodes)
        self.num_commodities = num_commodities
        self.adj: Dict[int, List[Edge]] = {node: [] for node in nodes}
        self.edges = []
        self.edge_index_map = {}
        
        for idx, (u, v, cap) in enumerate(edges):
            adjusted_cap = int(cap * multipliers[idx])
            if adjusted_cap < 1:
                raise InvalidMultiplierError(f"Edge {idx} capacity after multiplier < 1")
            
            forward_edge = Edge(u, v, adjusted_cap, idx)
            backward_edge = Edge(v, u, 0, idx)
            
            forward_edge.rev = backward_edge
            backward_edge.rev = forward_edge
            
            self.adj[u].append(forward_edge)
            self.adj[v].append(backward_edge)
            self.edges.append(forward_edge)
            self.edge_index_map[(u, v, idx)] = forward_edge


    def get_edge_by_index(self, idx: int) -> Optional[Edge]:
        """Get edge by original index."""
        for edge in self.edges:
            if edge.idx == idx:
                return edge
        return None


    def get_total_capacity(self) -> int:
        """Calculate total network capacity."""
        return sum(edge.capacity for edge in self.edges)


    def get_total_flow(self) -> int:
        """Calculate total flow in network."""
        return sum(edge.total_flow for edge in self.edges)


    def reset_flows(self):
        """Reset all edge flows to zero."""
        for node in self.adj:
            for edge in self.adj[node]:
                edge.commodity_flows = {}
                edge.total_flow = 0


    def get_node_count(self) -> int:
        """Get number of nodes."""
        return self.n


    def get_edge_count(self) -> int:
        """Get number of edges."""
        return len(self.edges)


    def __repr__(self):
        return f"MultiCommodityNetwork(nodes={self.n}, edges={len(self.edges)}, commodities={self.num_commodities})"


class EdmondsKarpSolver:
    """Edmonds-Karp algorithm for multi-commodity flow."""
    
    def __init__(self, network: MultiCommodityNetwork):
        """Initialize solver."""
        self.network = network
        self.augmenting_paths_count = 0
        self.paths_per_commodity = {}


    def bfs_augment(self, source: int, sink: int, commodity_id: int, restrictions: Set[int]) -> Tuple[Optional[List[Edge]], int]:
        """Find augmenting path using BFS."""
        parent = {node: None for node in self.network.nodes}
        visited = {node: False for node in self.network.nodes}
        queue = collections.deque([source])
        visited[source] = True
        
        while queue:
            u = queue.popleft()
            
            for edge in self.network.adj[u]:
                v = edge.v
                
                if edge.idx in restrictions and edge.capacity > 0:
                    continue
                
                residual = edge.get_residual()
                
                if not visited[v] and residual > 0:
                    visited[v] = True
                    parent[v] = (u, edge)
                    
                    if v == sink:
                        path = []
                        current = sink
                        min_residual = float('inf')
                        
                        while current != source:
                            prev_node, prev_edge = parent[current]
                            path.append(prev_edge)
                            min_residual = min(min_residual, prev_edge.get_residual())
                            current = prev_node
                        
                        path.reverse()
                        return path, min_residual
                    
                    queue.append(v)
        
        return None, 0


    def solve_commodity(self, source: int, sink: int, commodity_id: int, demand: int, restrictions: Set[int]) -> int:
        """Solve max flow for single commodity."""
        total_flow = 0
        paths_found = 0
        
        while total_flow < demand:
            path, flow = self.bfs_augment(source, sink, commodity_id, restrictions)
            
            if flow == 0:
                break
            
            flow = min(flow, demand - total_flow)
            
            for edge in path:
                edge.add_flow(commodity_id, flow)
                edge.rev.remove_flow(commodity_id, flow)
            
            total_flow += flow
            paths_found += 1
            self.augmenting_paths_count += 1
        
        self.paths_per_commodity[commodity_id] = paths_found
        return total_flow


    def get_statistics(self) -> Dict[str, Any]:
        """Get solver statistics."""
        return {
            "total_paths": self.augmenting_paths_count,
            "paths_per_commodity": self.paths_per_commodity
        }


class CapacityScalingSolver:
    """Capacity scaling algorithm for multi-commodity flow."""
    
    def __init__(self, network: MultiCommodityNetwork):
        """Initialize solver."""
        self.network = network
        self.augmenting_paths_count = 0
        self.paths_per_commodity = {}
        self.scaling_phases = 0


    def dfs_augment(self, u: int, sink: int, bottleneck: int, visited: Set[int], 
                    commodity_id: int, restrictions: Set[int]) -> Tuple[int, List[Edge]]:
        """DFS to find path with minimum bottleneck capacity."""
        if u == sink:
            return bottleneck, []
        
        visited.add(u)
        
        for edge in self.network.adj[u]:
            if edge.idx in restrictions and edge.capacity > 0:
                continue
            
            residual = edge.get_residual()
            
            if edge.v not in visited and residual >= bottleneck:
                flow, path = self.dfs_augment(edge.v, sink, bottleneck, visited, commodity_id, restrictions)
                
                if flow > 0:
                    return flow, [edge] + path
        
        return 0, []


    def solve_commodity(self, source: int, sink: int, commodity_id: int, demand: int, restrictions: Set[int]) -> int:
        """Solve max flow using capacity scaling."""
        max_capacity = max(edge.capacity for edge in self.network.edges)
        delta = 1 << (max_capacity.bit_length() - 1)
        total_flow = 0
        paths_found = 0
        
        while delta >= 1 and total_flow < demand:
            self.scaling_phases += 1
            
            while total_flow < demand:
                visited = set()
                flow, path = self.dfs_augment(source, sink, delta, visited, commodity_id, restrictions)
                
                if flow == 0:
                    break
                
                flow = min(flow, demand - total_flow)
                
                for edge in path:
                    edge.add_flow(commodity_id, flow)
                    edge.rev.remove_flow(commodity_id, flow)
                
                total_flow += flow
                paths_found += 1
                self.augmenting_paths_count += 1
            
            delta //= 2
        
        self.paths_per_commodity[commodity_id] = paths_found
        return total_flow


    def get_statistics(self) -> Dict[str, Any]:
        """Get solver statistics."""
        return {
            "total_paths": self.augmenting_paths_count,
            "scaling_phases": self.scaling_phases,
            "paths_per_commodity": self.paths_per_commodity
        }


class DinicSolver:
    """Dinic's algorithm for multi-commodity max flow."""
    
    def __init__(self, network: MultiCommodityNetwork):
        """Initialize solver."""
        self.network = network
        self.augmenting_paths_count = 0
        self.level = {}
        self.paths_per_commodity = {}
        self.blocking_flow_iterations = 0


    def bfs_level_graph(self, source: int, sink: int, commodity_id: int, restrictions: Set[int]) -> bool:
        """Build level graph using BFS."""
        self.level = {node: -1 for node in self.network.nodes}
        queue = collections.deque([source])
        self.level[source] = 0
        
        while queue:
            u = queue.popleft()
            
            for edge in self.network.adj[u]:
                if edge.idx in restrictions and edge.capacity > 0:
                    continue
                
                residual = edge.get_residual()
                
                if self.level[edge.v] < 0 and residual > 0:
                    self.level[edge.v] = self.level[u] + 1
                    queue.append(edge.v)
        
        return self.level[sink] >= 0


    def dfs_blocking_flow(self, u: int, sink: int, flow: int, ptr: Dict[int, int], 
                         commodity_id: int, restrictions: Set[int]) -> Tuple[int, List[Edge]]:
        """Send blocking flow using DFS."""
        if u == sink:
            return flow, []
        
        while ptr[u] < len(self.network.adj[u]):
            edge = self.network.adj[u][ptr[u]]
            
            if edge.idx in restrictions and edge.capacity > 0:
                ptr[u] += 1
                continue
            
            residual = edge.get_residual()
            
            if self.level[edge.v] == self.level[u] + 1 and residual > 0:
                pushed = min(flow, residual)
                result_flow, path = self.dfs_blocking_flow(edge.v, sink, pushed, ptr, commodity_id, restrictions)
                
                if result_flow > 0:
                    return result_flow, [edge] + path
            
            ptr[u] += 1
        
        return 0, []


    def solve_commodity(self, source: int, sink: int, commodity_id: int, demand: int, restrictions: Set[int]) -> int:
        """Solve max flow using Dinic's algorithm."""
        total_flow = 0
        paths_found = 0
        
        while total_flow < demand and self.bfs_level_graph(source, sink, commodity_id, restrictions):
            ptr = {node: 0 for node in self.network.nodes}
            self.blocking_flow_iterations += 1
            
            while total_flow < demand:
                flow, path = self.dfs_blocking_flow(source, sink, float('inf'), ptr, commodity_id, restrictions)
                
                if flow == 0:
                    break
                
                flow = min(flow, demand - total_flow)
                
                for edge in path:
                    edge.add_flow(commodity_id, flow)
                    edge.rev.remove_flow(commodity_id, flow)
                
                total_flow += flow
                paths_found += 1
                self.augmenting_paths_count += 1
        
        self.paths_per_commodity[commodity_id] = paths_found
        return total_flow


    def get_statistics(self) -> Dict[str, Any]:
        """Get solver statistics."""
        return {
            "total_paths": self.augmenting_paths_count,
            "blocking_flow_iterations": self.blocking_flow_iterations,
            "paths_per_commodity": self.paths_per_commodity
        }


def validate_inputs(nodes: List[int], edges: List[List[int]], sources: List[int], 
                   sink: int, commodities: List[int], restrictions: List[List[int]], 
                   time_multipliers: List[float], strategy: str):
    """Validate all input parameters against constraints."""
    if not (6 <= len(nodes) <= 80):
        raise InvalidNodeError(f"Node count {len(nodes)} violates constraint [6, 80]")
    
    if not (6 <= len(edges) <= 400):
        raise InvalidEdgeError(f"Edge count {len(edges)} violates constraint [6, 400]")
    
    if not (2 <= len(commodities) <= 8):
        raise InvalidCommodityError(f"Commodity count {len(commodities)} violates constraint [2, 8]")
    
    node_set = set(nodes)
    
    for node in nodes:
        if not (isinstance(node, int) and 0 <= node < 1000):
            raise InvalidNodeError(f"Node {node} violates constraint [0, 1000)")
    
    if len(sources) != len(commodities):
        raise InvalidCommodityError(f"Sources count {len(sources)} != commodities count {len(commodities)}")
    
    for source in sources:
        if source not in node_set:
            raise InvalidNodeError(f"Source {source} not in nodes")
    
    if sink not in node_set:
        raise InvalidNodeError(f"Sink {sink} not in nodes")
    
    if len(sources) != len(set(sources)):
        raise InvalidNodeError("Source nodes must be distinct")
    
    if sink in sources:
        raise InvalidNodeError("Sink cannot be a source")
    
    for idx, edge in enumerate(edges):
        if len(edge) != 3:
            raise InvalidEdgeError(f"Edge {idx} must have 3 elements")
        
        u, v, cap = edge
        
        if u == v:
            raise InvalidEdgeError(f"Self-loop not allowed: edge {idx}")
        
        if u not in node_set or v not in node_set:
            raise InvalidEdgeError(f"Edge {idx} references non-existent node")
        
        if not (isinstance(cap, int) and 5 <= cap <= 800):
            raise InvalidEdgeError(f"Edge {idx} capacity {cap} violates constraint [5, 800]")
    
    if len(time_multipliers) != len(edges):
        raise InvalidMultiplierError(f"Multiplier count {len(time_multipliers)} != edge count {len(edges)}")
    
    for idx, mult in enumerate(time_multipliers):
        if not (isinstance(mult, (int, float)) and 0.2 <= mult <= 1.8):
            raise InvalidMultiplierError(f"Multiplier {idx} value {mult} violates constraint [0.2, 1.8]")
    
    for commodity in commodities:
        if not (isinstance(commodity, int) and 1 <= commodity <= 100):
            raise InvalidCommodityError(f"Commodity {commodity} violates constraint [1, 100]")
    
    if len(restrictions) != len(commodities):
        raise InvalidRestrictionError(f"Restrictions count {len(restrictions)} != commodity count {len(commodities)}")
    
    for idx, restriction_list in enumerate(restrictions):
        if not isinstance(restriction_list, list):
            raise InvalidRestrictionError(f"Restriction {idx} must be a list")
        
        for edge_idx in restriction_list:
            if not (isinstance(edge_idx, int) and 0 <= edge_idx < len(edges)):
                raise InvalidRestrictionError(f"Restriction {idx} references invalid edge {edge_idx}")
    
    if strategy not in {"edmonds_karp", "capacity_scaling", "dinic"}:
        raise InvalidStrategyError(f"Strategy '{strategy}' not in allowed set")
    
    adjacency = collections.defaultdict(list)
    for u, v, cap in edges:
        adjacency[u].append(v)
    
    for source_idx, source in enumerate(sources):
        restriction_set = set(restrictions[source_idx])
        queue = collections.deque([source])
        visited = {source}
        
        while queue:
            u = queue.popleft()
            if u == sink:
                break
            
            # Check each edge considering restrictions
            for edge_idx, (edge_u, edge_v, cap) in enumerate(edges):
                if edge_u == u and edge_idx not in restriction_set:
                    if edge_v not in visited:
                        visited.add(edge_v)
                        queue.append(edge_v)
        
        if sink not in visited:
            raise NoPathError(f"Commodity {source_idx} from source {source} to sink {sink} has no valid path (restricted edges: {restriction_set})")


def compute_min_cut(network: MultiCommodityNetwork, sources: List[int], sink: int, 
                   commodity_flows: List[int], commodity_demands: List[int]) -> Tuple[List[List[int]], int, List[int], List[int]]:
    """Compute minimum cut distinguishing demand-limited vs capacity-limited flow."""
    
    # Check if flow is demand-limited (all commodities achieved their demands)
    is_demand_limited = all(flow == demand for flow, demand in zip(commodity_flows, commodity_demands))
    
    if is_demand_limited:
        # Demand-limited: no bottleneck exists in residual graph
        return [], 0, sorted(network.nodes), []
    
    # Capacity-limited: find the actual bottleneck cut
    # Find reachable nodes in residual graph
    reachable = set()
    queue = collections.deque(sources)
    reachable.update(sources)
    
    while queue:
        u = queue.popleft()
        for edge in network.adj[u]:
            if edge.get_residual() > 0 and edge.v not in reachable:
                reachable.add(edge.v)
                queue.append(edge.v)
    
    # Find cut edges between reachable and unreachable nodes
    cut_edges = []
    cut_capacity = 0
    
    for u in reachable:
        for edge in network.adj[u]:
            if edge.v not in reachable and edge.capacity > 0:
                cut_edges.append([edge.u, edge.v])
                cut_capacity += edge.capacity
    
    source_partition = sorted(list(reachable))
    sink_partition = sorted([node for node in network.nodes if node not in reachable])
    
    return cut_edges, cut_capacity, source_partition, sink_partition



def compute_flow_assignments(network: MultiCommodityNetwork) -> List[Dict[str, Any]]:
    """Compute flow assignments per edge with commodity breakdown."""
    assignments = []
    
    for edge in network.edges:
        flows = [edge.commodity_flows.get(i, 0) for i in range(network.num_commodities)]
        assignments.append({
            "edge": [edge.u, edge.v],
            "flows": flows,
            "total": edge.total_flow
        })
    
    return assignments


def compute_bottleneck_roads(network: MultiCommodityNetwork) -> List[List[int]]:
    """Identify edges at full capacity."""
    bottlenecks = []
    
    for edge in network.edges:
        if edge.is_saturated():
            bottlenecks.append([edge.u, edge.v])
    
    return bottlenecks


def compute_residual_sum(network: MultiCommodityNetwork) -> int:
    """Calculate total residual capacity across network."""
    total = 0
    
    for edge in network.edges:
        total += edge.get_residual()
    
    return total


def compute_flow_decomposition(network: MultiCommodityNetwork, sources: List[int], 
                               sink: int, num_commodities: int) -> Dict[str, List[List[List[int]]]]:
    """Decompose commodity flows into paths with actual flow values."""
    decomposition = {}
    
    for commodity_id in range(num_commodities):
        paths = []
        source = sources[commodity_id]
        
        # Create a copy of commodity flows for decomposition
        temp_flows = {}
        for edge in network.edges:
            flow = edge.get_commodity_flow(commodity_id)
            if flow > 0:
                temp_flows[(edge.u, edge.v, edge.idx)] = flow
        
        # Decompose flow into paths using DFS
        while temp_flows:
            # Find a path from source to sink with positive flow
            path = []
            visited = set()
            
            def find_path(u: int, current_path: List[Tuple[int, int, int]]) -> bool:
                """DFS to find a path with positive flow."""
                if u == sink:
                    path.extend(current_path)
                    return True
                
                visited.add(u)
                
                for edge in network.edges:
                    if edge.u == u and (edge.u, edge.v, edge.idx) in temp_flows:
                        flow = temp_flows[(edge.u, edge.v, edge.idx)]
                        if flow > 0 and edge.v not in visited:
                            current_path.append((edge.u, edge.v, edge.idx))
                            if find_path(edge.v, current_path):
                                return True
                            current_path.pop()
                
                visited.remove(u)
                return False
            
            if not find_path(source, []):
                break
            
            if not path:
                break
            
            # Find bottleneck flow for this path
            bottleneck = min(temp_flows[(u, v, idx)] for u, v, idx in path)
            
            # Record path with actual flow value
            path_with_flow = [[u, v, bottleneck] for u, v, idx in path]
            paths.append(path_with_flow)
            
            # Reduce flow on path edges
            for u, v, idx in path:
                temp_flows[(u, v, idx)] -= bottleneck
                if temp_flows[(u, v, idx)] == 0:
                    del temp_flows[(u, v, idx)]
            
            # Limit to 10 paths per commodity
            if len(paths) >= 10:
                break
        
        decomposition[f"commodity_{commodity_id}"] = paths
    
    return decomposition


def compute_critical_nodes(network: MultiCommodityNetwork, sources: List[int], sink: int) -> List[int]:
    """Identify critical bottleneck nodes."""
    critical = set()
    
    for edge in network.edges:
        if edge.is_saturated():
            if edge.u not in sources and edge.u != sink:
                critical.add(edge.u)
            if edge.v not in sources and edge.v != sink:
                critical.add(edge.v)
    
    return sorted(list(critical))


def optimize_traffic_flow(nodes, edges, sources, sink, commodities, restrictions, time_multipliers, strategy):
    """Optimize multi-commodity traffic flow with path restrictions."""
    validate_inputs(nodes, edges, sources, sink, commodities, restrictions, time_multipliers, strategy)
    
    network = MultiCommodityNetwork(nodes, edges, time_multipliers, len(commodities))
    
    if strategy == "edmonds_karp":
        solver = EdmondsKarpSolver(network)
    elif strategy == "capacity_scaling":
        solver = CapacityScalingSolver(network)
    elif strategy == "dinic":
        solver = DinicSolver(network)
    else:
        raise InvalidStrategyError(f"Unknown strategy: {strategy}")
    
    commodity_flows = []
    
    for idx, (source, demand) in enumerate(zip(sources, commodities)):
        restriction_set = set(restrictions[idx])
        flow = solver.solve_commodity(source, sink, idx, demand, restriction_set)
        commodity_flows.append(flow)
    
    total_flow = sum(commodity_flows)
    
    min_cut_edges, min_cut_capacity, source_partition, sink_partition = compute_min_cut(network, sources, sink, commodity_flows, commodities)
    flow_assignments = compute_flow_assignments(network)
    bottleneck_roads = compute_bottleneck_roads(network)
    residual_capacity_sum = compute_residual_sum(network)
    flow_decomposition = compute_flow_decomposition(network, sources, sink, len(commodities))
    critical_nodes = compute_critical_nodes(network, sources, sink)
    
    return {
        "total_flow": total_flow,
        "commodity_flows": commodity_flows,
        "min_cut_capacity": min_cut_capacity,
        "min_cut_edges": min_cut_edges,
        "source_partition": source_partition,
        "sink_partition": sink_partition,
        "flow_assignments": flow_assignments,
        "bottleneck_roads": bottleneck_roads,
        "augmenting_paths_count": solver.augmenting_paths_count,
        "residual_capacity_sum": residual_capacity_sum,
        "flow_decomposition": flow_decomposition,
        "critical_nodes": critical_nodes
    }