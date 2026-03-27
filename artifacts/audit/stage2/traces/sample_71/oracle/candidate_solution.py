from typing import Dict, List
import heapq

def manage_traffic_graph(
    city_map: Dict[str, Dict[str, int]],
    updates: List[List],
    start: str,
    end: str
) -> List[str]:
    
    SINK_PENALTY = 10**6
    
    if city_map is None:
        return []
    if updates is None or not isinstance(updates, list):
        return []
    for update in updates:
        if not isinstance(update, list) or len(update) != 3:
            return []
        source, target, weight = update
        if not (isinstance(source, str) and isinstance(target, str)):
            return []
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
            return []
    if not city_map and not updates:
        return []
    for source, neighbors in (city_map or {}).items():
        for target in neighbors.keys():
            if source == target:
                return []
    for source, target, _ in updates:
        if source == target:
            return []

    graph = {}
    if city_map:
        for source, neighbors in city_map.items():
            graph[source] = {}
            for target, weight in neighbors.items():
                graph[source][target] = weight

    for source in list(graph.keys()):
        for target in graph[source].keys():
            if target not in graph:
                graph[target] = {}

    for source, target, weight in updates:
        if source not in graph:
            graph[source] = {}
        if target not in graph:
            graph[target] = {}
        graph[source][target] = weight

    if start not in graph or end not in graph:
        return []

    def is_sink(node):
        return not any(weight > 0 for weight in graph.get(node, {}).values())

    sink_nodes = {node for node in graph.keys() if is_sink(node)}

    best_paths = {}
    start_path = (start,)
    best_paths[start] = (0, 0, start_path)
    priority_queue = [(0, 0, start_path, start)]

    while priority_queue:
        current_cost, hop_count, current_path, current_node = heapq.heappop(priority_queue)

        if best_paths.get(current_node) != (current_cost, hop_count, current_path):
            continue

        if current_node == end:
            return list(current_path)

        for neighbor, travel_time in graph.get(current_node, {}).items():
            if travel_time <= 0:
                continue
            penalty = SINK_PENALTY if (neighbor in sink_nodes and neighbor != end) else 0
            total_cost = current_cost + travel_time + penalty
            new_hop_count = hop_count + 1
            new_path = current_path + (neighbor,)

            candidate = (total_cost, new_hop_count, new_path)
            previous_best = best_paths.get(neighbor)

            if previous_best is None or candidate < previous_best:
                best_paths[neighbor] = candidate
                heapq.heappush(priority_queue, (total_cost, new_hop_count, new_path, neighbor))

    return []

if __name__ == "__main__":
    city_map = {
        "A": {"B": 5, "C": 2},
        "B": {"D": 3, "E": 1},
        "C": {"B": 8, "F": 2},
        "D": {"G": 4},
        "E": {"F": 6},
        "F": {"G": 5},
        "G": {"A": 10}
    }
    updates = [
        ["B", "E", 10],
        ["E", "F", 0],
        ["C", "B", 12]
    ]
    start = "A"
    end = "G"
    print(manage_traffic_graph(city_map, updates, start, end))