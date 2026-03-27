import heapq
from typing import List, Dict, Any
import itertools

def find_emergency_route(graph_nodes: List[int], uncertain_edges: List[Dict], 
                        start_node: int, end_node: int) -> Dict[str, Any]:
    
    if not isinstance(graph_nodes, list):
        return {"error": "Input is not valid"}
    
    if not graph_nodes:
        return {"error": "Empty graph provided"}
    
    if not isinstance(uncertain_edges, list):
        return {"error": "Input is not valid"}
    
    if not isinstance(start_node, int) or not isinstance(end_node, int):
        return {"error": "Input is not valid"}
    
    if start_node not in graph_nodes or end_node not in graph_nodes:
        return {"error": "Start or end node not in graph"}
    
    for node in graph_nodes:
        if not isinstance(node, int) or node < 1 or node > 500:
            return {"error": "Input is not valid"}
    
    edge_ids = set()
    
    for edge in uncertain_edges:
        if not isinstance(edge, dict):
            return {"error": "Input is not valid"}
        
        required_keys = ['from_node', 'to_node', 'scenarios', 'edge_id']
        for key in required_keys:
            if key not in edge:
                return {"error": "Input is not valid"}
        
        if edge['edge_id'] in edge_ids:
            return {"error": "Input is not valid"}
        edge_ids.add(edge['edge_id'])
        
        if not isinstance(edge['from_node'], int) or not isinstance(edge['to_node'], int):
            return {"error": "Input is not valid"}
        
        if edge['from_node'] not in graph_nodes or edge['to_node'] not in graph_nodes:
            return {"error": "Invalid node ID"}
        
        if not isinstance(edge['scenarios'], list) or not edge['scenarios']:
            return {"error": f"Invalid scenario data for edge {edge['edge_id']}"}
        
        prob_sum = 0.0
        for scenario in edge['scenarios']:
            if not isinstance(scenario, dict):
                return {"error": "Input is not valid"}
            if 'travel_time' not in scenario or 'probability' not in scenario:
                return {"error": "Input is not valid"}
            if not isinstance(scenario['travel_time'], (int, float)) or not isinstance(scenario['probability'], (int, float)):
                return {"error": "Input is not valid"}
            
            prob_sum += scenario['probability']
            
            if scenario['travel_time'] < 0.5 or scenario['travel_time'] > 120.0:
                return {"error": "Input is not valid"}
            if scenario['probability'] < 0.01 or scenario['probability'] > 1.0:
                return {"error": "Input is not valid"}
        
        if abs(prob_sum - 1.0) > 0.001:
            return {"error": "Edge probabilities do not sum to 1.0"}
    
    graph = {}
    edge_properties = {}
    
    for node in graph_nodes:
        graph[node] = []
    
    for edge in uncertain_edges:
        from_node = edge['from_node']
        to_node = edge['to_node']
        edge_id = edge['edge_id']
        scenarios = edge['scenarios']
        
        expected_time = sum(scenario['travel_time'] * scenario['probability'] for scenario in scenarios)
        
        threshold = 1.25 * expected_time
        qualifying_scenarios = [s for s in scenarios if s['travel_time'] <= threshold]
        
        if qualifying_scenarios:
            reliability = sum(scenario['probability'] for scenario in qualifying_scenarios)
        else:
            reliability = 1.0
        
        edge_properties[edge_id] = {
            'from_node': from_node,
            'to_node': to_node,
            'expected_time': expected_time,
            'reliability': reliability,
            'scenarios': scenarios,
            'edge_id': edge_id
        }
        
        graph[from_node].append({
            'to_node': to_node,
            'expected_time': expected_time,
            'reliability': reliability,
            'edge_id': edge_id,
            'scenarios': scenarios
        })
    
    def validate_scenario_consistency(path_edges_list, total_expected_time):
        if not path_edges_list or total_expected_time <= 0:
            return True
        
        max_allowed = 2.0 * total_expected_time
        
        edge_scenarios = []
        for edge_id in path_edges_list:
            edge_scenarios.append(edge_properties[edge_id]['scenarios'])
        
        for scenario_combination in itertools.product(*edge_scenarios):
            total_time = sum(scenario['travel_time'] for scenario in scenario_combination)
            if total_time > max_allowed:
                return False
        
        return True
    
    path_scores = {node: float('inf') for node in graph_nodes}
    path_scores[start_node] = 0.0
    expected_times = {node: float('inf') for node in graph_nodes}
    expected_times[start_node] = 0.0
    path_reliabilities = {node: 1.0 for node in graph_nodes}
    predecessors = {}
    path_edges = {}
    
    priority_queue = [(0.0, [start_node], start_node, 1.0, [], 0.0)]
    visited = set()
    
    while priority_queue:        
        _, node_sequence, current_node, current_reliability, current_edges, current_expected = heapq.heappop(priority_queue)
        
        if current_node in visited:
            continue
        
        visited.add(current_node)
        
        if current_node == end_node:
            break
        
        for neighbor_info in graph[current_node]:
            neighbor = neighbor_info['to_node']
            edge_expected_time = neighbor_info['expected_time']
            edge_reliability = neighbor_info['reliability']
            edge_id = neighbor_info['edge_id']
            
            if neighbor in visited:
                continue
            
            new_expected_time = current_expected + edge_expected_time
            new_path_reliability = current_reliability * edge_reliability
            new_edges = current_edges + [edge_id]
            new_node_sequence = node_sequence + [neighbor]
            
            reliability_penalty = 50.0
            path_score = new_expected_time + (reliability_penalty * (1 - new_path_reliability))
            
            valid_path = validate_scenario_consistency(new_edges, new_expected_time)
            
            if valid_path:
                is_better = False
                if path_score < path_scores[neighbor]:
                    is_better = True
                elif path_score == path_scores[neighbor]:
                    current_best_sequence = []
                    if neighbor in predecessors:
                        temp_path = []
                        temp_node = neighbor
                        while temp_node != start_node:
                            temp_path.append(temp_node)
                            temp_node = predecessors[temp_node]
                        temp_path.append(start_node)
                        current_best_sequence = temp_path[::-1]
                    
                    if not current_best_sequence or new_node_sequence < current_best_sequence:
                        is_better = True
                
                if is_better:
                    path_scores[neighbor] = path_score
                    expected_times[neighbor] = new_expected_time
                    path_reliabilities[neighbor] = new_path_reliability
                    predecessors[neighbor] = current_node
                    path_edges[neighbor] = new_edges
                    
                    heapq.heappush(priority_queue, (path_score, new_node_sequence, neighbor, new_path_reliability, new_edges, new_expected_time))
    
    if end_node not in predecessors and end_node != start_node:
        return {"error": "No path exists between start and end nodes"}
    
    if start_node == end_node:
        path = [start_node]
        final_edges = []
    else:
        path = []
        current = end_node
        while current is not None:
            path.append(current)
            current = predecessors.get(current)
        path.reverse()
        final_edges = path_edges[end_node]
    
    expected_travel_time = expected_times[end_node]
    path_reliability = path_reliabilities[end_node]
    reliability_penalty = 50.0
    total_path_score = expected_travel_time + (reliability_penalty * (1 - path_reliability))
    
    edge_details = []
    for edge_id in final_edges:
        edge_info = edge_properties[edge_id]
        edge_details.append({
            "from_node": edge_info['from_node'],
            "to_node": edge_info['to_node'],
            "expected_time": round(edge_info['expected_time'], 1),
            "reliability": round(edge_info['reliability'], 3),
            "edge_id": edge_info['edge_id']
        })
    
    if final_edges:
        scenario_times = []
        
        def calculate_all_scenarios(edge_idx, current_time, current_prob):
            if edge_idx >= len(final_edges):
                scenario_times.append((current_time, current_prob))
                return
            
            edge_id = final_edges[edge_idx]
            scenarios = edge_properties[edge_id]['scenarios']
            
            for scenario in scenarios:
                new_time = current_time + scenario['travel_time']
                new_prob = current_prob * scenario['probability']
                calculate_all_scenarios(edge_idx + 1, new_time, new_prob)
        
        calculate_all_scenarios(0, 0.0, 1.0)
        
        best_case_time = min(time for time, _ in scenario_times)
        worst_case_time = max(time for time, _ in scenario_times)
        
        expected_sq = sum(time * time * prob for time, prob in scenario_times)
        variance = expected_sq - (expected_travel_time * expected_travel_time)
    else:
        best_case_time = 0.0
        worst_case_time = 0.0
        variance = 0.0
    
    scenario_analysis = {
        "best_case_time": round(best_case_time, 1),
        "worst_case_time": round(worst_case_time, 1),
        "variance": round(variance, 2)
    }
    
    return {
        "path": path,
        "expected_travel_time": round(expected_travel_time, 1),
        "path_reliability": round(path_reliability, 3),
        "total_path_score": round(total_path_score, 1),
        "scenario_analysis": scenario_analysis,
        "edge_details": edge_details
    }

if __name__ == "__main__":
    graph_nodes = [1, 2, 3, 4, 5]

    uncertain_edges = [
        {
            "from_node": 1,
            "to_node": 2,
            "scenarios": [
                {"travel_time": 4.0, "probability": 0.8},
                {"travel_time": 8.0, "probability": 0.2}
            ],
            "edge_id": 101
        },
        {
            "from_node": 1,
            "to_node": 3,
            "scenarios": [
                {"travel_time": 6.0, "probability": 0.9},
                {"travel_time": 12.0, "probability": 0.1}
            ],
            "edge_id": 102
        },
        {
            "from_node": 2,
            "to_node": 4,
            "scenarios": [
                {"travel_time": 3.0, "probability": 0.7},
                {"travel_time": 7.0, "probability": 0.3}
            ],
            "edge_id": 103
        },
        {
            "from_node": 3,
            "to_node": 4,
            "scenarios": [
                {"travel_time": 2.0, "probability": 0.6},
                {"travel_time": 5.0, "probability": 0.4}
            ],
            "edge_id": 104
        },
        {
            "from_node": 4,
            "to_node": 5,
            "scenarios": [
                {"travel_time": 4.0, "probability": 0.8},
                {"travel_time": 6.0, "probability": 0.2}
            ],
            "edge_id": 105
        }
    ]

    start_node = 1
    end_node = 5
    result = find_emergency_route(graph_nodes, uncertain_edges, start_node, end_node)
    print(result)