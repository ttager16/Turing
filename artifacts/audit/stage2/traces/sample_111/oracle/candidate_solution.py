from typing import Dict, List
from collections import deque, defaultdict


def max_flow_simulator(graph: Dict[str, List[Dict[str, int]]], source: int, sink: int) -> Dict:
    """
    Computes maximum flow using Ford-Fulkerson algorithm with BFS (Edmonds-Karp).
    Handles advanced edge cases: anti-parallel edges, backward edge utilization, and tie-breaking.
    
    Args:
        graph: Dictionary mapping node (as string) -> list of dictionaries with "neighbor" and "capacity" keys
        source: Source node integer
        sink: Sink node integer
    
    Returns:
        Dictionary with total_flow, edge_flows, algorithm_steps, and explanations
    """
    
    def _validate_graph(graph: Dict[int, List[Dict[str, int]]], source: int, sink: int) -> None:
        """Validates graph structure and detects potential issues."""
        all_nodes = set(graph.keys())
        for node, edges in graph.items():
            for edge in edges:
                neighbor = edge["neighbor"]
                capacity = edge["capacity"]
                all_nodes.add(neighbor)
                if capacity < 0:
                    raise ValueError(f"Negative capacity {capacity} on edge ({node}, {neighbor})")
        
        if source not in all_nodes:
            raise ValueError(f"Source node {source} not in graph")
        if sink not in all_nodes:
            raise ValueError(f"Sink node {sink} not in graph")
    
    
    def _build_residual_graph(graph: Dict[int, List[Dict[str, int]]]):
        """
        Builds residual graph and detects anti-parallel edges.
        Handles bidirectional flow by maintaining separate capacities for each direction.
        Returns: (residual_graph, original_capacities, anti_parallel_edges)
        """
        residual = defaultdict(lambda: defaultdict(int))
        original_capacities = {}
        anti_parallel_edges = set()
        
        for node, edges in graph.items():
            for edge in edges:
                neighbor = edge["neighbor"]
                capacity = edge["capacity"]
                residual[node][neighbor] = capacity
                edge_key = f"{node}->{neighbor}"
                original_capacities[edge_key] = capacity
                
                reverse_key = f"{neighbor}->{node}"
                if reverse_key in original_capacities:
                    anti_parallel_edges.add(f"{min(node, neighbor)}<->{max(node, neighbor)}")
                
                if neighbor not in residual:
                    residual[neighbor] = defaultdict(int)
        
        return residual, original_capacities, anti_parallel_edges
    
    
    def _identify_backward_edges(path: List[Dict[str, int]], original_capacities: Dict[str, int]) -> List[Dict[str, int]]:
        """
        Identifies backward edges in the path (edges not in original graph).
        These represent flow being rerouted through the residual graph.
        """
        backward_edges = []
        for edge in path:
            edge_key = f"{edge['from']}->{edge['to']}"
            if edge_key not in original_capacities:
                backward_edges.append(edge)
        return backward_edges
    
    
    def _bfs_find_path(residual_graph: Dict[int, Dict[int, int]], source: int, sink: int):
        """
        Uses BFS to find augmenting path from source to sink.
        Ensures deterministic tie-breaking by sorting neighbors.
        Returns: (path as list of dicts, parent dict) or (None, parent dict)
        """
        parent = {source: None}
        queue = deque([source])
        
        while queue:
            current = queue.popleft()
            
            if current == sink:
                path = []
                node = sink
                while parent[node] is not None:
                    prev = parent[node]
                    path.append({"from": prev, "to": node})
                    node = prev
                return list(reversed(path)), parent
            
            neighbors = sorted(residual_graph[current].items())
            for neighbor, capacity in neighbors:
                if capacity > 0 and neighbor not in parent:
                    parent[neighbor] = current
                    queue.append(neighbor)
        
        return None, parent
    
    
    def _compute_bottleneck(residual_graph: Dict[int, Dict[int, int]], path: List[Dict[str, int]]) -> int:
        """Computes bottleneck capacity along the path."""
        return min(residual_graph[edge["from"]][edge["to"]] for edge in path)
    
    
    def _update_flow(residual_graph: Dict[int, Dict[int, int]], flow_graph: Dict[int, Dict[int, int]], 
                     path: List[Dict[str, int]], bottleneck: int) -> None:
        """
        Updates residual graph and flow graph with bottleneck flow.
        Handles anti-parallel edges by maintaining separate flow values for each direction.
        Creates backward edges in residual graph to enable flow rerouting.
        """
        for edge in path:
            u = edge["from"]
            v = edge["to"]
            residual_graph[u][v] -= bottleneck
            residual_graph[v][u] += bottleneck
            flow_graph[u][v] += bottleneck
            flow_graph[v][u] -= bottleneck
    
    
    def _create_step_info(step: int, path: List[Dict[str, int]], bottleneck: int, 
                          flow_increase: int, residual_graph: Dict[int, Dict[int, int]], 
                          original_capacities: Dict[str, int],
                          backward_edges: List[Dict[str, int]]) -> Dict:
        """
        Creates algorithm step information dictionary.
        Includes information about backward edges for advanced edge case analysis.
        """
        residual_edges = []
        for edge_key, original_capacity in original_capacities.items():
            # Parse edge key "u->v"
            u, v = map(int, edge_key.split("->"))
            residual_capacity = residual_graph[u][v]
            if residual_capacity > 0:
                residual_edges.append({"from": u, "to": v, "residual": residual_capacity})
        
        step_info = {
            "step": step,
            "path": path,
            "bottleneck": bottleneck,
            "flow_increase": flow_increase,
            "residual_edges": residual_edges
        }
        
        if backward_edges:
            step_info["backward_edges"] = backward_edges
        
        return step_info
    
    
    def _generate_explanation(step: int, path: List[Dict[str, int]], bottleneck: int, 
                             total_flow: int, residual_graph: Dict[int, Dict[int, int]], 
                             original_capacities: Dict[str, int],
                             source: int, sink: int, backward_edges: List[Dict[str, int]]) -> str:
        """
        Generates human-readable explanation for algorithm step.
        Includes information about backward edge utilization.
        """
        if path:
            path_str = str(path[0]["from"]) + "→" + "→".join(str(edge["to"]) for edge in path)
        else:
            path_str = ""
        
        capacities_in_path = [residual_graph[edge["from"]][edge["to"]] + bottleneck for edge in path]
        capacities_str = ", ".join(str(c) for c in capacities_in_path)
        
        updated_edges = []
        for edge in path:
            u = edge["from"]
            v = edge["to"]
            residual_cap = residual_graph[u][v]
            updated_edges.append(f"{u}→{v} ({residual_cap})")
        
        updated_str = ", ".join(updated_edges)
        
        has_more_paths = _check_for_more_paths(residual_graph, source, sink)
        no_more_msg = "" if has_more_paths else " No further augmenting paths exist."
        
        backward_msg = ""
        if backward_edges:
            backward_str = ", ".join(f"{edge['from']}→{edge['to']}" for edge in backward_edges)
            backward_msg = f" Used backward edges ({backward_str}) to reroute flow."
        
        explanation = (
            f"Step {step}: Selected augmenting path {path_str} with bottleneck capacity {bottleneck} "
            f"(min of {capacities_str}). Increased flow by {bottleneck} units. "
            f"Updated residual capacities: {updated_str}. Total flow: {total_flow}.{backward_msg}{no_more_msg}"
        )
        
        return explanation
    
    
    def _check_for_more_paths(residual_graph: Dict[int, Dict[int, int]], source: int, sink: int) -> bool:
        """Checks if more augmenting paths exist."""
        path, _ = _bfs_find_path(residual_graph, source, sink)
        return path is not None
    
    
    def _compute_edge_flows(graph: Dict[int, List[Dict[str, int]]], 
                           flow_graph: Dict[int, Dict[int, int]], 
                           residual_graph: Dict[int, Dict[int, int]], 
                           original_capacities: Dict[str, int]) -> Dict[str, Dict]:
        """Computes final edge flows and residual capacities."""
        edge_flows = {}
        
        for node, edges in graph.items():
            for edge in edges:
                neighbor = edge["neighbor"]
                original_capacity = edge["capacity"]
                flow = max(0, flow_graph[node][neighbor])
                residual_capacity = residual_graph[node][neighbor]
                
                edge_key = f"{node}->{neighbor}"
                edge_flows[edge_key] = {
                    "flow": flow,
                    "residual_capacity": residual_capacity
                }
        
        return edge_flows
    
    
    def _create_empty_result(graph: Dict[int, List[Dict[str, int]]]) -> Dict:
        """Creates result for edge case where source equals sink."""
        edge_flows = {}
        for node, edges in graph.items():
            for edge in edges:
                neighbor = edge["neighbor"]
                capacity = edge["capacity"]
                edge_key = f"{node}->{neighbor}"
                edge_flows[edge_key] = {
                    "flow": 0,
                    "residual_capacity": capacity
                }
        
        return {
            "total_flow": 0,
            "edge_flows": edge_flows,
            "algorithm_steps": [],
            "explanations": []
        }
    
    # Main function logic starts here
    # Convert string keys to integers for internal processing
    int_graph = {int(k): v for k, v in graph.items()}
    
    if source == sink:
        return _create_empty_result(int_graph)
    
    _validate_graph(int_graph, source, sink)
    
    residual_graph, original_capacities, anti_parallel_edges = _build_residual_graph(int_graph)
    flow_graph = defaultdict(lambda: defaultdict(int))
    total_flow = 0
    algorithm_steps = []
    explanations = []
    step_number = 0
    
    while True:
        path, parent = _bfs_find_path(residual_graph, source, sink)
        
        if not path:
            break
        
        step_number += 1
        bottleneck = _compute_bottleneck(residual_graph, path)
        backward_edges = _identify_backward_edges(path, original_capacities)
        _update_flow(residual_graph, flow_graph, path, bottleneck)
        total_flow += bottleneck
        
        step_info = _create_step_info(
            step_number, path, bottleneck, bottleneck, 
            residual_graph, original_capacities, backward_edges
        )
        algorithm_steps.append(step_info)
        
        explanation = _generate_explanation(
            step_number, path, bottleneck, total_flow,
            residual_graph, original_capacities, source, sink, backward_edges
        )
        explanations.append(explanation)
    
    edge_flows = _compute_edge_flows(int_graph, flow_graph, residual_graph, original_capacities)
    
    return {
        "total_flow": total_flow,
        "edge_flows": edge_flows,
        "algorithm_steps": algorithm_steps,
        "explanations": explanations
    }