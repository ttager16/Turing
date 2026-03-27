import time
from typing import List, Dict, Any
from collections import deque

def optimize_delivery_network(graph_nodes: List[Dict], road_segments: List[Dict], 
                            delivery_locations: List[Dict], depot_node_id: int, 
                            traffic_schedule: Dict, max_computation_time: int) -> Dict[str, Any]:
    """
    Optimizes urban delivery routes using Dynamic BFS algorithm.
    Returns: Dictionary with optimal paths and efficiency metrics
    """
    start_time = time.time()
    
    if not delivery_locations:
        return {"error": "No delivery locations provided"}
    
    if max_computation_time < 5 or max_computation_time > 30:
        return {"error": "Input is not valid"}
    
    node_ids = set()
    for node in graph_nodes:
        if node['node_id'] < 0 or node['node_id'] > 99:
            return {"error": "Input is not valid"}
        
        x, y = node['coordinates']
        if x < 0 or x > 1000 or y < 0 or y > 1000:
            return {"error": f"Invalid coordinates for node {node['node_id']}"}
        
        if node['intersection_type'] not in ["residential", "commercial", "industrial", "highway"]:
            return {"error": "Input is not valid"}
        
        if node['base_delay'] < 1 or node['base_delay'] > 10:
            return {"error": "Input is not valid"}
        
        node_ids.add(node['node_id'])
    
    if depot_node_id not in node_ids:
        return {"error": "Invalid depot node reference"}
    
    for segment in road_segments:
        if segment['segment_id'] < 0 or segment['segment_id'] > 999:
            return {"error": "Input is not valid"}
        
        if segment['start_node'] not in node_ids:
            return {"error": f"Invalid node reference in road segment {segment['segment_id']}"}
        
        if segment['end_node'] not in node_ids:
            return {"error": f"Invalid node reference in road segment {segment['segment_id']}"}
        
        if segment['base_travel_time'] < 5 or segment['base_travel_time'] > 60:
            return {"error": "Input is not valid"}
        
        if segment['capacity_limit'] < 10 or segment['capacity_limit'] > 100:
            return {"error": "Input is not valid"}
        
        if segment['traffic_density'] < 0.1 or segment['traffic_density'] > 1.0:
            return {"error": "Input is not valid"}
        
        for window in segment['activation_windows']:
            if window['start_time'] < 0 or window['start_time'] > 1440:
                return {"error": "Input is not valid"}
            if window['end_time'] < 0 or window['end_time'] > 1440:
                return {"error": "Input is not valid"}
            if window['start_time'] >= window['end_time']:
                return {"error": "Input is not valid"}
    
    for location in delivery_locations:
        if location['location_id'] < 0 or location['location_id'] > 199:
            return {"error": "Input is not valid"}
        
        if location['node_id'] not in node_ids:
            return {"error": "Input is not valid"}
        
        if location['priority_level'] < 1 or location['priority_level'] > 5:
            return {"error": "Input is not valid"}
        
        if location['vehicle_load'] < 1 or location['vehicle_load'] > 50:
            return {"error": "Input is not valid"}
        
        if location['earliest_delivery_time'] < 0 or location['earliest_delivery_time'] > 1440:
            return {"error": "Input is not valid"}
        
        if location['latest_delivery_time'] < 0 or location['latest_delivery_time'] > 1440:
            return {"error": "Input is not valid"}
        
        if location['earliest_delivery_time'] >= location['latest_delivery_time']:
            return {"error": f"Invalid delivery time window for location {location['location_id']}"}
    
    if traffic_schedule['weather_impact_factor'] < 1.0 or traffic_schedule['weather_impact_factor'] > 2.0:
        return {"error": "Input is not valid"}
    
    peak_hours = traffic_schedule['peak_hours']
    for peak_period in peak_hours:
        if peak_period['start_time'] < 0 or peak_period['start_time'] > 1440:
            return {"error": "Input is not valid"}
        if peak_period['end_time'] < 0 or peak_period['end_time'] > 1440:
            return {"error": "Input is not valid"}
        if peak_period['start_time'] >= peak_period['end_time']:
            return {"error": "Input is not valid"}
    
    for i in range(len(peak_hours)):
        for j in range(i + 1, len(peak_hours)):
            start1, end1 = peak_hours[i]['start_time'], peak_hours[i]['end_time']
            start2, end2 = peak_hours[j]['start_time'], peak_hours[j]['end_time']
            if not (end1 <= start2 or end2 <= start1):
                return {"error": "Overlapping peak hours detected"}
    
    graph = {}
    segment_map = {}
    for node in graph_nodes:
        graph[node['node_id']] = []
    
    for segment in road_segments:
        start_node = segment['start_node']
        end_node = segment['end_node']
        segment_id = segment['segment_id']
        
        graph[start_node].append({
            'target': end_node,
            'segment_id': segment_id,
            'segment': segment
        })
        segment_map[segment_id] = segment
    
    def check_connectivity():
        all_nodes = set(node_ids)
        
        visited = set()
        start_node = next(iter(all_nodes))
        queue = deque([start_node])
        visited.add(start_node)
        
        while queue:
            node = queue.popleft()
            for edge in graph[node]:
                target = edge['target']
                if target not in visited:
                    visited.add(target)
                    queue.append(target)
        
        if len(visited) != len(all_nodes):
            return False
        
        for location in delivery_locations:
            location_node = location['node_id']
            depot_visited = set()
            queue = deque([depot_node_id])
            depot_visited.add(depot_node_id)
            
            while queue:
                node = queue.popleft()
                for edge in graph[node]:
                    target = edge['target']
                    if target not in depot_visited:
                        depot_visited.add(target)
                        queue.append(target)
            
            if location_node not in depot_visited:
                return False
        
        return True
    
    if not check_connectivity():
        return {"error": "Graph contains disconnected components"}
    
    for location in delivery_locations:
        vehicle_load = location['vehicle_load']
        location_node = location['node_id']
        
        temp_visited = set()
        temp_queue = deque([depot_node_id])
        temp_visited.add(depot_node_id)
        path_exists = False
        
        while temp_queue:
            current_node = temp_queue.popleft()
            
            if current_node == location_node:
                path_exists = True
                break
            
            for edge in graph[current_node]:
                target = edge['target']
                segment = edge['segment']
                
                if target not in temp_visited and vehicle_load <= segment['capacity_limit']:
                    temp_visited.add(target)
                    temp_queue.append(target)
        
        if not path_exists:
            for segment in road_segments:
                if vehicle_load > segment['capacity_limit']:
                    for test_location in delivery_locations:
                        test_visited = set()
                        test_queue = deque([depot_node_id])
                        test_visited.add(depot_node_id)
                        uses_segment = False
                        
                        while test_queue and not uses_segment:
                            test_node = test_queue.popleft()
                            
                            if test_node == test_location['node_id']:
                                break
                            
                            for test_edge in graph[test_node]:
                                test_target = test_edge['target']
                                if test_edge['segment_id'] == segment['segment_id']:
                                    uses_segment = True
                                    break
                                if test_target not in test_visited:
                                    test_visited.add(test_target)
                                    test_queue.append(test_target)
                        
                        if uses_segment and test_location['node_id'] == location_node:
                            return {"error": f"Vehicle load exceeds road capacity for segment {segment['segment_id']}"}
    
    adjusted_segments = {}
    
    for segment in road_segments:
        segment_id = segment['segment_id']
        adjusted_segments[segment_id] = segment.copy()
        
        if segment['traffic_density'] > 0.7:
            adjusted_windows = []
            for window in segment['activation_windows']:
                original_duration = window['end_time'] - window['start_time']
                adjusted_duration = max(1, int(original_duration * 0.8))
                adjusted_end = window['start_time'] + adjusted_duration
                
                if adjusted_end > window['start_time']:
                    adjusted_windows.append({
                        'start_time': window['start_time'],
                        'end_time': min(adjusted_end, window['end_time'])
                    })
            
            adjusted_segments[segment_id]['adjusted_activation_windows'] = adjusted_windows
        else:
            adjusted_segments[segment_id]['adjusted_activation_windows'] = segment['activation_windows']
        
        if segment['start_node'] in traffic_schedule['construction_zones'] or segment['end_node'] in traffic_schedule['construction_zones']:
            adjusted_segments[segment_id]['adjusted_capacity'] = int(segment['capacity_limit'] * 0.5)
        else:
            adjusted_segments[segment_id]['adjusted_capacity'] = segment['capacity_limit']
    
    sorted_locations = sorted(delivery_locations, key=lambda x: (x['priority_level'], x['location_id']))
    
    segment_usage_timeline = {}
    peak_hour_usage_count = 0
    total_deliveries = 0
    
    optimal_paths = []
    undeliverable_locations = []
    total_system_efficiency = 0.0
    
    node_lookup = {node['node_id']: node for node in graph_nodes}
    
    for location in sorted_locations:
        if time.time() - start_time > max_computation_time:
            return {"error": "Computation time exceeded maximum limit"}
        
        path_result = find_optimal_path_dynamic_bfs(
            graph, depot_node_id, location, adjusted_segments, 
            traffic_schedule, node_lookup, start_time, max_computation_time,
            segment_usage_timeline
        )
        
        if path_result is None:
            undeliverable_locations.append(location['location_id'])
        else:
            optimal_paths.append(path_result)
            total_system_efficiency += path_result['path_efficiency_score']
            total_deliveries += 1
            
            cumulative_time = node_lookup[depot_node_id]['base_delay']
            time_window_duration = max(1, (location['latest_delivery_time'] - location['earliest_delivery_time']) // 20)
            
            for i, segment_id in enumerate(path_result['road_segments_used']):
                usage_time = cumulative_time // (time_window_duration // 2 + 1)
                if usage_time not in segment_usage_timeline:
                    segment_usage_timeline[usage_time] = {}
                if segment_id not in segment_usage_timeline[usage_time]:
                    segment_usage_timeline[usage_time][segment_id] = 0
                segment_usage_timeline[usage_time][segment_id] += location['vehicle_load']
                
                segment = adjusted_segments[segment_id]
                travel_time = calculate_actual_travel_time(segment, cumulative_time, traffic_schedule['weather_impact_factor'], traffic_schedule)
                target_node = None
                for edge in graph[depot_node_id if i == 0 else path_result['path_nodes'][i]]:
                    if edge['segment_id'] == segment_id:
                        target_node = edge['target']
                        break
                if target_node:
                    target_delay = node_lookup[target_node]['base_delay']
                    cumulative_time += travel_time + target_delay
            
            delivery_time = path_result['scheduled_delivery_time']
            for peak_period in traffic_schedule['peak_hours']:
                if peak_period['start_time'] <= delivery_time <= peak_period['end_time']:
                    peak_hour_usage_count += 1
                    break
    
    peak_hour_usage = peak_hour_usage_count / total_deliveries if total_deliveries > 0 else 0.0
    
    capacity_utilizations = []
    bottleneck_segments = []
    
    max_utilizations = {}
    for time_point in segment_usage_timeline:
        for segment_id, usage in segment_usage_timeline[time_point].items():
            capacity = adjusted_segments[segment_id]['adjusted_capacity']
            utilization = usage / capacity if capacity > 0 else 0.0
            if segment_id not in max_utilizations or utilization > max_utilizations[segment_id]:
                max_utilizations[segment_id] = utilization
    
    for segment in road_segments:
        segment_id = segment['segment_id']
        utilization = max_utilizations.get(segment_id, 0.0)
        capacity_utilizations.append(utilization)
        
        if utilization > 0.8:
            bottleneck_segments.append(segment_id)
    
    average_capacity_utilization = sum(capacity_utilizations) / len(capacity_utilizations) if capacity_utilizations else 0.0
    
    return {
        "optimal_paths": optimal_paths,
        "total_system_efficiency": round(total_system_efficiency, 1),
        "undeliverable_locations": undeliverable_locations,
        "traffic_utilization_summary": {
            "peak_hour_usage": round(peak_hour_usage, 2),
            "average_capacity_utilization": round(average_capacity_utilization, 2),
            "bottleneck_segments": sorted(bottleneck_segments)
        }
    }

def find_optimal_path_dynamic_bfs(graph, depot_node_id, location, adjusted_segments, 
                                traffic_schedule, node_lookup, start_time, max_computation_time,
                                segment_usage_timeline):
    """Find optimal path using Dynamic BFS algorithm"""
    target_node = location['node_id']
    earliest_time = location['earliest_delivery_time']
    latest_time = location['latest_delivery_time']
    vehicle_load = location['vehicle_load']
    weather_factor = traffic_schedule['weather_impact_factor']
    
    all_feasible_paths = []
    depot_delay = node_lookup[depot_node_id]['base_delay']
    
    queue = deque([(depot_node_id, depot_delay, [], 0)])
    visited_states = set()
    
    max_path_length = len(graph) + 5
    time_granularity = max(1, (latest_time - earliest_time) // 20)
    max_search_iterations = len(graph) * len(graph) * 10
    iteration_count = 0
    
    while queue and iteration_count < max_search_iterations:
        if time.time() - start_time > max_computation_time:
            break
        
        iteration_count += 1
        current_node, current_time, path, total_travel_time = queue.popleft()
        
        time_bucket = current_time // time_granularity
        state_key = (current_node, time_bucket, len(path))
        
        if state_key in visited_states:
            continue
        visited_states.add(state_key)
        
        if current_node == target_node:
            target_delay = node_lookup[current_node]['base_delay']
            arrival_time = current_time - target_delay
            if arrival_time <= latest_time:
                all_feasible_paths.append({
                    'path': path,
                    'arrival_time': arrival_time,
                    'total_travel_time': total_travel_time,
                    'current_time': current_time
                })
            continue
        
        if len(path) > max_path_length:
            continue
        
        neighbors = sorted(graph[current_node], key=lambda x: (x['target'], x['segment_id']))
        
        for edge in neighbors:
            target = edge['target']
            segment_id = edge['segment_id']
            segment = adjusted_segments[segment_id]
            
            if vehicle_load > segment['adjusted_capacity']:
                continue
            
            travel_time = calculate_actual_travel_time(segment, current_time, weather_factor, traffic_schedule)
            
            is_active = False
            for window in segment['adjusted_activation_windows']:
                travel_end_time = current_time + travel_time
                if (window['start_time'] <= current_time <= window['end_time'] and
                    window['start_time'] <= travel_end_time <= window['end_time']):
                    is_active = True
                    break
            
            if not is_active:
                continue
            
            target_delay = node_lookup[target]['base_delay']
            new_time = current_time + travel_time + target_delay
            new_path = path + [edge]
            new_total_travel_time = total_travel_time + travel_time
            
            arrival_time_at_target = new_time - node_lookup[target]['base_delay']
            if arrival_time_at_target > latest_time:
                continue
            
            usage_time_bucket = current_time // (time_granularity // 2 + 1)
            current_usage = segment_usage_timeline.get(usage_time_bucket, {}).get(segment_id, 0)
            if current_usage + vehicle_load > segment['adjusted_capacity']:
                continue
            
            queue.append((target, new_time, new_path, new_total_travel_time))
    
    if not all_feasible_paths:
        return None
    
    best_path = None
    best_score = float('inf')
    
    for path_info in all_feasible_paths:
        path = path_info['path']
        arrival_time = path_info['arrival_time']
        total_travel_time = path_info['total_travel_time']
        
        possible_delivery_times = [max(arrival_time, earliest_time)]
        
        if latest_time > earliest_time:
            mid_time = (earliest_time + latest_time) // 2
            possible_delivery_times.append(max(arrival_time, mid_time))
            if latest_time > arrival_time + 5:
                possible_delivery_times.append(max(arrival_time, latest_time - 5))
        
        for delivery_time in possible_delivery_times:
            if delivery_time > latest_time:
                continue
            
            score = calculate_path_efficiency_score(
                path, delivery_time, location, adjusted_segments, weather_factor, traffic_schedule
            )
            
            if score < best_score:
                best_score = score
                segment_usage_times = []
                cumulative_time = node_lookup[depot_node_id]['base_delay']
                
                for edge in path:
                    segment_usage_times.append(cumulative_time // (time_granularity // 2 + 1))
                    segment = adjusted_segments[edge['segment_id']]
                    travel_time = calculate_actual_travel_time(segment, cumulative_time, weather_factor, traffic_schedule)
                    target_delay = node_lookup[edge['target']]['base_delay']
                    cumulative_time += travel_time + target_delay
                
                total_travel_time_with_delays = total_travel_time + node_lookup[depot_node_id]['base_delay']
                
                best_path = {
                    "delivery_location_id": location['location_id'],
                    "path_nodes": [depot_node_id] + [edge['target'] for edge in path],
                    "total_travel_time": total_travel_time_with_delays,
                    "path_efficiency_score": round(score, 1),
                    "scheduled_delivery_time": delivery_time,
                    "road_segments_used": [edge['segment_id'] for edge in path]
                }
    
    return best_path

def calculate_actual_travel_time(segment, time_point, weather_factor, traffic_schedule):
    """Calculate actual travel time considering peak hours and weather"""
    base_time = segment['base_travel_time']
    travel_time = base_time
    
    for peak_period in traffic_schedule['peak_hours']:
        if peak_period['start_time'] <= time_point <= peak_period['end_time']:
            travel_time = int(travel_time * 1.3)
            break
    
    travel_time = int(travel_time * weather_factor)
    return travel_time

def calculate_path_efficiency_score(path, delivery_time, location, adjusted_segments, weather_factor, traffic_schedule):
    """Calculate path efficiency score using the exact formula from prompt"""
    
    base_travel_cost = 0
    cumulative_time = 0
    
    for edge in path:
        segment = adjusted_segments[edge['segment_id']]
        travel_time = calculate_actual_travel_time(segment, cumulative_time, weather_factor, traffic_schedule)
        base_travel_cost += travel_time
        cumulative_time += travel_time
    
    latest_delivery_time = location['latest_delivery_time']
    time_penalty = max(0, delivery_time - latest_delivery_time)
    
    earliest_delivery_time = location['earliest_delivery_time']
    window_urgency = 100 / (latest_delivery_time - earliest_delivery_time + 1)
    
    vehicle_load = location['vehicle_load']
    min_capacity = float('inf')
    for edge in path:
        segment = adjusted_segments[edge['segment_id']]
        min_capacity = min(min_capacity, segment['adjusted_capacity'])
    
    if min_capacity == float('inf'):
        min_capacity = 1
    
    capacity_utilization_factor = (vehicle_load / min_capacity) * 50
    
    priority_weight = location['priority_level'] * 25
    
    path_efficiency_score = (base_travel_cost + 
                           (time_penalty * window_urgency) + 
                           (capacity_utilization_factor * priority_weight))
    
    return path_efficiency_score

if __name__ == "__main__":
    graph_nodes = [
        {"node_id": 0, "coordinates": (100, 200), "intersection_type": "commercial", "base_delay": 3},
        {"node_id": 1, "coordinates": (300, 400), "intersection_type": "residential", "base_delay": 2},
        {"node_id": 2, "coordinates": (500, 300), "intersection_type": "industrial", "base_delay": 5},
        {"node_id": 3, "coordinates": (700, 600), "intersection_type": "highway", "base_delay": 1}
    ]

    road_segments = [
        {"segment_id": 0, "start_node": 0, "end_node": 1, "base_travel_time": 15, "capacity_limit": 50, "traffic_density": 0.6, "activation_windows": [{"start_time": 0, "end_time": 1440}]},
        {"segment_id": 1, "start_node": 1, "end_node": 2, "base_travel_time": 20, "capacity_limit": 30, "traffic_density": 0.8, "activation_windows": [{"start_time": 0, "end_time": 1440}]},
        {"segment_id": 2, "start_node": 2, "end_node": 3, "base_travel_time": 25, "capacity_limit": 40, "traffic_density": 0.5, "activation_windows": [{"start_time": 0, "end_time": 1440}]},
        {"segment_id": 3, "start_node": 0, "end_node": 2, "base_travel_time": 30, "capacity_limit": 35, "traffic_density": 0.4, "activation_windows": [{"start_time": 0, "end_time": 1440}]}
    ]

    delivery_locations = [
        {"location_id": 0, "node_id": 1, "priority_level": 1, "vehicle_load": 25, "earliest_delivery_time": 60, "latest_delivery_time": 180},
        {"location_id": 1, "node_id": 3, "priority_level": 2, "vehicle_load": 30, "earliest_delivery_time": 120, "latest_delivery_time": 300}
    ]

    depot_node_id = 0

    traffic_schedule = {
        "peak_hours": [{"start_time": 420, "end_time": 540}, {"start_time": 1020, "end_time": 1140}],
        "construction_zones": [2],
        "weather_impact_factor": 1.2
    }

    max_computation_time = 10

    result = optimize_delivery_network(graph_nodes, road_segments, delivery_locations, depot_node_id, traffic_schedule, max_computation_time)
    print(result)