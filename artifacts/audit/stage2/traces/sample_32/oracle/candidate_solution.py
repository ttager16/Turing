from typing import Dict, List, Tuple, Any, Set, Optional
from collections import deque, defaultdict
import heapq

def optimize_delivery_routes(
    city_map: Dict[str, List[List[Any]]],       # <- lists, not tuples
    vehicles: List[Dict[str, Any]],
    route_closures: List[List[Any]]             # <- lists, not tuples
) -> List[Dict[str, Any]]:

    if not vehicles or not city_map:
        return []

    closure_map = defaultdict(dict)
    for from_node, to_node, closure_time in route_closures:
        closure_map[from_node][to_node] = closure_time

    all_nodes = set(city_map.keys())
    for neighbors in city_map.values():
        for neighbor, _, _ in neighbors:
            all_nodes.add(neighbor)

    results = []

    for vehicle in vehicles:
        vehicle_id = vehicle['id']
        start_node = vehicle['start_node']
        end_node = vehicle['end_node']
        capacity = vehicle['capacity']
        time_window = vehicle['time_window']      # now a list [start, end]
        deliveries = vehicle.get('deliveries', [])

        if capacity < len(deliveries):
            continue

        if start_node not in city_map and start_node not in all_nodes:
            continue

        if end_node not in all_nodes:
            continue

        skip_vehicle = False
        for delivery in deliveries:
            if delivery not in all_nodes:
                skip_vehicle = True
                break
        
        if skip_vehicle:
            continue

        route_result = find_best_route(
            city_map, start_node, end_node, deliveries,
            time_window, closure_map, capacity
        )

        if route_result is None:
            continue

        route, total_time, layer_transitions = route_result

        if total_time > time_window[1]:
            continue

        results.append({
            'vehicle_id': vehicle_id,
            'route': route,
            'total_time': total_time,
            'layer_transitions': layer_transitions
        })

    return results

def extract_base_node(node: str) -> str:
    parts = node.split('_')
    if parts:
        return parts[0]
    return node

def get_layer(node: str) -> str:
    if '_skyway' in node:
        return 'skyway'
    elif '_tunnel' in node:
        return 'tunnel'
    else:
        return 'road'

def is_junction_transition(from_node: str, to_node: str) -> bool:
    from_base = extract_base_node(from_node)
    to_base = extract_base_node(to_node)
    from_layer = get_layer(from_node)
    to_layer = get_layer(to_node)
    return from_base == to_base and from_layer != to_layer

def heuristic_distance(city_map: Dict[str, List[List[Any]]], current: str, goal: str) -> float:
    if current == goal:
        return 0
    
    distances = {current: 0}
    priority_queue = [(0, current)]
    visited = set()
    
    while priority_queue:
        current_dist, node = heapq.heappop(priority_queue)
        
        if node in visited:
            continue
        
        visited.add(node)
        
        if node == goal:
            return current_dist
        
        if node in city_map:
            for neighbor, cost, _ in city_map[node]:
                new_dist = current_dist + cost
                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    heapq.heappush(priority_queue, (new_dist, neighbor))
    
    return float('inf')

def find_best_route(
    city_map: Dict[str, List[List[Any]]],
    start: str,
    end: str,
    deliveries: List[str],
    time_window: List[int],                               # <- list [start, end]
    closure_map: Dict[str, Dict[str, int]],
    capacity: int
) -> Optional[Tuple[List[str], int, int]]:

    if not deliveries:
        return backtrack_simple_route(city_map, start, end, time_window[0], closure_map)

    best_solution = None
    best_cost = float('inf')
    best_transitions = float('inf')

    def backtrack(current_node: str, remaining_deliveries: Set[str], 
                  current_path: List[str], current_time: int, current_transitions: int):
        nonlocal best_solution, best_cost, best_transitions

        if current_time > time_window[1]:
            return

        if current_time + heuristic_distance(city_map, current_node, end) > time_window[1]:
            return

        estimated_total_cost = current_time + heuristic_distance(city_map, current_node, end)
        if estimated_total_cost > best_cost:
            return

        if not remaining_deliveries:
            path_to_end = backtrack_simple_route(city_map, current_node, end, current_time, closure_map)
            if path_to_end:
                final_path, final_time, final_transitions = path_to_end
                complete_path = current_path + final_path[1:]
                complete_time = current_time + final_time
                complete_transitions = current_transitions + final_transitions

                if complete_time <= time_window[1]:
                    if complete_time < best_cost or (complete_time == best_cost and complete_transitions < best_transitions):
                        best_cost = complete_time
                        best_transitions = complete_transitions
                        best_solution = (complete_path, complete_time, complete_transitions)
            return

        delivery_distances = []
        for delivery in remaining_deliveries:
            dist = heuristic_distance(city_map, current_node, delivery)
            delivery_distances.append((dist, delivery))

        delivery_distances.sort()

        for _, next_delivery in delivery_distances:
            min_time_to_delivery = heuristic_distance(city_map, current_node, next_delivery)
            if current_time + min_time_to_delivery >= best_cost:
                continue

            path_to_delivery = backtrack_simple_route(city_map, current_node, next_delivery, current_time, closure_map)

            if path_to_delivery:
                delivery_path, delivery_time, delivery_transitions = path_to_delivery
                new_path = current_path + delivery_path[1:]
                new_time = current_time + delivery_time
                new_transitions = current_transitions + delivery_transitions
                new_remaining = remaining_deliveries - {next_delivery}

                backtrack(next_delivery, new_remaining, new_path, new_time, new_transitions)

    backtrack(start, set(deliveries), [start], 0, 0)
    return best_solution

def backtrack_simple_route(
    city_map: Dict[str, List[List[Any]]],
    start: str,
    goal: str,
    current_time: int,
    closure_map: Dict[str, Dict[str, int]]
) -> Optional[Tuple[List[str], int, int]]:

    if start == goal:
        return ([start], 0, 0)

    best_path = None
    best_time = float('inf')
    best_transitions = float('inf')
    visited = {}

    def backtrack_path(current_node: str, path: List[str], time: int, transitions: int):
        nonlocal best_path, best_time, best_transitions

        if time >= best_time:
            return

        remaining_distance = heuristic_distance(city_map, current_node, goal)
        if time + remaining_distance >= best_time:
            return

        if current_node in visited:
            if visited[current_node] <= (time, transitions):
                return

        visited[current_node] = (time, transitions)

        if current_node == goal:
            if time < best_time or (time == best_time and transitions < best_transitions):
                best_time = time
                best_transitions = transitions
                best_path = path.copy()
            return

        if current_node in city_map:
            neighbors_with_cost = []
            for neighbor, edge_cost, layer in city_map[current_node]:
                if neighbor in path:
                    continue

                if current_node in closure_map and neighbor in closure_map[current_node]:
                    edge_arrival_time = current_time + time + edge_cost
                    if edge_arrival_time >= closure_map[current_node][neighbor]:
                        continue

                heuristic_dist = heuristic_distance(city_map, neighbor, goal)
                neighbors_with_cost.append((heuristic_dist, neighbor, edge_cost, layer))

            neighbors_with_cost.sort()

            for _, neighbor, edge_cost, layer in neighbors_with_cost:
                new_time = time + edge_cost
                new_transitions = transitions

                if is_junction_transition(current_node, neighbor):
                    new_time += 5
                    new_transitions += 1

                backtrack_path(neighbor, path + [neighbor], new_time, new_transitions)

    backtrack_path(start, [start], 0, 0)

    if best_path:
        return (best_path, best_time, best_transitions)
    return None