from typing import List, Dict, Any
from collections import defaultdict, deque
import heapq


EPSILON = 1e-6
FLOW_TOLERANCE = 1e-3
MIN_FLOW = 1e-9
MIN_PRIORITY_WEIGHT = 0.1

# This is a factor to multiply the number of nodes and edges to get the maximum number of iterations
MAX_ITERATION_FACTOR = 1


def find_optimal_multilayer_network(
    layer_graphs: List[Dict[str, Any]],
    critical_nodes: Dict[str, float]
) -> List[Dict[str, int]]:
    """
    Solves a minimum-cost maximum-flow problem on a multi-layer network.
    
    Finds the set of edges across multiple layers that satisfies all supply/demand
    constraints, respects capacity limits, ensures critical node connectivity, and
    minimizes total cost using priority-adjusted edge costs.
    
    The algorithm uses a successive shortest path min-cost flow approach with
    Dijkstra's algorithm (enhanced with node potentials to handle residual graph
    negative costs). Each layer's edges are tracked separately to correctly attribute
    flow back to specific layers in the output.
    
    Args:
        layer_graphs: List of layer definitions. Each layer is a dictionary with:
            - "layer_id": Integer or string identifying the layer
            - "nodes": Dictionary mapping node_id (int or str) to balance (float)
                      Positive values = supply, negative = demand, zero = relay
            - "edges": List of dictionaries with keys:
                      {"from": node_id, "to": node_id, "cost": float, "capacity": float}
        
        critical_nodes: Dictionary mapping node_id (str) to priority weight (float).
            Higher priority values result in lower effective edge costs for edges
            connecting to these nodes, making them preferentially selected.
            Default priority for non-critical nodes is 1.0.
    
    Returns:
        List of dictionaries with keys {"layer_id", "from", "to"} representing the
        selected edges that form the optimal solution. Returns empty list [] if no
        feasible solution exists (e.g., supply ≠ demand, insufficient capacity, or
        critical nodes cannot be connected to supply nodes).
    
    Example:
        >>> layer_graphs = [{
        ...     "layer_id": 0,
        ...     "nodes": {1: 10.0, 2: -10.0},
        ...     "edges": [{"from": 1, "to": 2, "cost": 1.0, "capacity": 10.0}]
        ... }]
        >>> result = find_optimal_multilayer_network(layer_graphs, {})
        >>> # Returns: [{"layer_id": 0, "from": 1, "to": 2}]
    """
    
    if not layer_graphs:
        return []
    
    total_supply = 0.0
    total_demand = 0.0
    node_balance = defaultdict(float)
    
    for layer in layer_graphs:
        if not layer.get('nodes'):
            continue
        for node_id, value in layer['nodes'].items():
            node_id = int(node_id) if isinstance(node_id, str) else node_id
            node_balance[node_id] += value
            if value > 0:
                total_supply += value
            elif value < 0:
                total_demand += abs(value)
    
    if abs(total_supply - total_demand) > EPSILON:
        return []
    
    edge_registry = {}
    unified_graph = defaultdict(list)
    all_nodes_in_layers = set()
    
    for layer in layer_graphs:
        nodes = layer.get('nodes', {})
        node_ids = [int(k) if isinstance(k, str) else k for k in nodes.keys()]
        all_nodes_in_layers.update(node_ids)
    
    for layer in layer_graphs:
        layer_id = layer.get('layer_id', 0)
        edges = layer.get('edges', [])
        
        for edge in edges:
            if isinstance(edge, dict):
                u = edge.get('from')
                v = edge.get('to')
                cost = edge.get('cost')
                capacity = edge.get('capacity')
                if u is None or v is None or cost is None or capacity is None:
                    continue
            elif isinstance(edge, (list, tuple)) and len(edge) >= 4:
                u, v, cost, capacity = edge[0], edge[1], edge[2], edge[3]
            else:
                continue
            
            edge_key = (layer_id, u, v)
            edge_registry[edge_key] = {
                'cost': cost,
                'capacity': capacity,
                'layer': layer_id,
                'nodes': (u, v)
            }
            
            unified_graph[u].append((v, layer_id, cost, capacity))
            unified_graph[v].append((u, layer_id, cost, capacity))
    
    if not edge_registry:
        return []
    
    sources = [node for node, balance in node_balance.items() if balance > EPSILON]
    sinks = [node for node, balance in node_balance.items() if balance < -EPSILON]
    
    if not sources or not sinks:
        return []
    
    critical_node_ids = [int(k) if isinstance(k, str) else k for k in critical_nodes.keys()]
    super_source = max(max(node_balance.keys(), default=0), 
                       max(critical_node_ids, default=0)) + 1
    super_sink = super_source + 1
    
    critical_nodes_normalized = {
        int(k) if isinstance(k, str) else k: v 
        for k, v in critical_nodes.items()
    }
    
    flow_graph = defaultdict(lambda: defaultdict(list))
    
    for node in sources:
        supply = node_balance[node]
        flow_graph[super_source][node].append({
            'capacity': supply,
            'cost': 0.0,
            'layer_id': None,
            'reverse': False
        })
    
    for node in sinks:
        demand = abs(node_balance[node])
        flow_graph[node][super_sink].append({
            'capacity': demand,
            'cost': 0.0,
            'layer_id': None,
            'reverse': False
        })
    
    for (layer_id, u, v), info in edge_registry.items():
        cost = info['cost']
        capacity = info['capacity']
        
        priority_weight_u = max(MIN_PRIORITY_WEIGHT, critical_nodes_normalized.get(u, 1.0))
        priority_weight_v = max(MIN_PRIORITY_WEIGHT, critical_nodes_normalized.get(v, 1.0))
        
        priority_factor = 1.0 / (priority_weight_u * priority_weight_v)
        
        adjusted_cost = cost * priority_factor
        
        flow_graph[u][v].append({
            'capacity': capacity,
            'cost': adjusted_cost,
            'layer_id': layer_id,
            'reverse': False,
            'original_nodes': (u, v)
        })
        
        flow_graph[v][u].append({
            'capacity': capacity,
            'cost': adjusted_cost,
            'layer_id': layer_id,
            'reverse': True,
            'original_nodes': (u, v)
        })
    
    edge_flows = defaultdict(float)
    potential = defaultdict(float)
    
    all_nodes = set([super_source, super_sink])
    all_nodes.update(node_balance.keys())
    for node in all_nodes:
        potential[node] = 0.0
    
    def dijkstra_with_potential(source, sink, flow_graph, edge_flows, potential):
        dist = {source: 0.0}
        parent = {}
        parent_edge = {}
        pq = [(0.0, source)]
        visited = set()
        
        while pq:
            d, u = heapq.heappop(pq)
            
            if u in visited:
                continue
            visited.add(u)
            
            if u == sink:
                break
            
            for v in flow_graph[u]:
                for edge_idx, edge in enumerate(flow_graph[u][v]):
                    edge_id = (u, v, edge_idx)
                    residual_capacity = edge['capacity'] - edge_flows[edge_id]
                    
                    if residual_capacity > MIN_FLOW and v not in visited:
                        cost = edge['cost']
                        reduced_cost = cost + potential[u] - potential[v]
                        
                        if v not in dist or dist[u] + reduced_cost < dist[v]:
                            dist[v] = dist[u] + reduced_cost
                            parent[v] = u
                            parent_edge[v] = edge_id
                            heapq.heappush(pq, (dist[v], v))
        
        if sink not in parent and sink != source:
            return None, float('inf'), []
        
        for node in dist:
            potential[node] += dist[node]
        
        path = []
        current = sink
        while current in parent:
            prev = parent[current]
            edge_id = parent_edge[current]
            path.append((prev, current, edge_id))
            current = prev
        path.reverse()
        
        if not path:
            return None, float('inf'), []
        
        min_capacity = float('inf')
        for prev, curr, edge_id in path:
            u, v, edge_idx = edge_id
            edge = flow_graph[u][v][edge_idx]
            residual = edge['capacity'] - edge_flows[edge_id]
            min_capacity = min(min_capacity, residual)
        
        return path, min_capacity, path
    
    num_nodes = len(node_balance) + 2
    num_edges = len(edge_registry)
    max_iterations = MAX_ITERATION_FACTOR * num_nodes * num_edges
    iteration = 0
    
    while iteration < max_iterations:
        path, capacity, _ = dijkstra_with_potential(super_source, super_sink, flow_graph, edge_flows, potential)
        
        if path is None or capacity < MIN_FLOW:
            break
        
        for prev, curr, edge_id in path:
            edge_flows[edge_id] += capacity
        
        iteration += 1
    
    total_flow_out = 0.0
    for node in flow_graph[super_source]:
        for idx in range(len(flow_graph[super_source][node])):
            edge_id = (super_source, node, idx)
            total_flow_out += edge_flows[edge_id]
    
    if abs(total_flow_out - total_supply) > FLOW_TOLERANCE:
        return []
    
    selected_edges = []
    
    edge_usage = defaultdict(float)
    
    for edge_id, flow_val in edge_flows.items():
        if flow_val < EPSILON:
            continue
        
        u, v, edge_idx = edge_id
        if u == super_source or u == super_sink or v == super_source or v == super_sink:
            continue
        
        edge = flow_graph[u][v][edge_idx]
        layer_id = edge.get('layer_id')
        
        if layer_id is None:
            continue
        
        if edge.get('reverse'):
            orig_u, orig_v = edge['original_nodes']
            edge_key = (layer_id, orig_u, orig_v)
            edge_usage[edge_key] -= flow_val
        else:
            edge_key = (layer_id, u, v)
            edge_usage[edge_key] += flow_val
    
    for (layer_id, u, v), net_flow in edge_usage.items():
        if abs(net_flow) > EPSILON:
            if net_flow > 0:
                selected_edges.append({"layer_id": layer_id, "from": u, "to": v})
            else:
                selected_edges.append({"layer_id": layer_id, "from": v, "to": u})
    
    
    if critical_nodes:
        critical_nodes_requiring_connection = [
            n for n in critical_nodes_normalized
            if n in node_balance and abs(node_balance[n]) > MIN_FLOW
        ]
        
        if critical_nodes_requiring_connection:
            forward_graph = defaultdict(set)
            backward_graph = defaultdict(set)
            for edge in selected_edges:
                u, v = edge["from"], edge["to"]
                forward_graph[u].add(v)
                backward_graph[v].add(u)
            
            for node in critical_nodes_requiring_connection:
                if node in sources:
                    continue
                
                visited = set()
                queue = deque([node])
                visited.add(node)
                found_source = False
                
                while queue and not found_source:
                    curr = queue.popleft()
                    if curr in sources:
                        found_source = True
                        break
                    for neighbor in backward_graph.get(curr, []):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                
                if not found_source:
                    return []
    
    selected_edges.sort(key=lambda x: (x["layer_id"], x["from"], x["to"]))
    return selected_edges

if __name__ == "__main__":
    layer_graphs = [
        {
            "layer_id": 0,
            "nodes": {1: 9.0, 2: -3.0, 3: -2.0},
            "edges": [
                {"from": 1, "to": 2, "cost": 2.5, "capacity": 10.0},
                {"from": 2, "to": 3, "cost": 3.0, "capacity": 5.0},
                {"from": 1, "to": 3, "cost": 4.0, "capacity": 7.0}
            ]
        },
        {
            "layer_id": 1,
            "nodes": {3: 0.0, 4: -4.0},
            "edges": [
                {"from": 3, "to": 4, "cost": 1.0, "capacity": 8.0}
            ]
        }
    ]
    critical_nodes = {"1": 2.0, "4": 1.5}
    result = find_optimal_multilayer_network(layer_graphs, critical_nodes)
    print(result)