import math
from typing import List, Dict, Any, Tuple, Optional

def optimize_ride_matching(driver_profiles: List[Dict], passenger_requests: List[Dict], 
                         service_zones: List[Dict], temporal_constraints: Dict) -> Dict[str, Any]:
    
    if not passenger_requests:
        return {"error": "No passenger requests provided"}
    
    validation_result = validate_inputs(driver_profiles, passenger_requests, service_zones, temporal_constraints)
    if validation_result:
        return validation_result
    
    zone_lookup = {zone['zone_id']: zone for zone in service_zones}
    
    current_time = temporal_constraints['current_system_time']
    available_zones = get_available_zones(service_zones, temporal_constraints, current_time)
    
    graph_edges = build_bipartite_graph(driver_profiles, passenger_requests, available_zones, 
                                      zone_lookup, current_time)
    
    surge_zones = calculate_surge_zones(driver_profiles, passenger_requests, available_zones, 
                                      temporal_constraints['surge_threshold'])
    
    adjusted_edges = apply_surge_adjustments(graph_edges, surge_zones)
    
    matches = find_maximum_weight_matching(adjusted_edges, driver_profiles, passenger_requests)
    
    metrics = calculate_system_metrics(matches, driver_profiles, passenger_requests, 
                                     available_zones, current_time)
    
    return prepare_output(matches, metrics, driver_profiles, passenger_requests, surge_zones)

def validate_inputs(driver_profiles: List[Dict], passenger_requests: List[Dict], 
                   service_zones: List[Dict], temporal_constraints: Dict) -> Optional[Dict]:
    
    for driver in driver_profiles:
        if 'driver_id' not in driver or driver['driver_id'] < 0 or driver['driver_id'] > 499:
            return {"error": "Input is not valid"}
        
        if 'current_location' not in driver:
            return {"error": "Input is not valid"}
        
        location = driver['current_location']
        if ('x' not in location or 'y' not in location or 
            location['x'] < 0 or location['x'] > 2000 or 
            location['y'] < 0 or location['y'] > 2000):
            return {"error": f"Invalid coordinates for driver {driver['driver_id']}"}
        
        if ('vehicle_capacity' not in driver or driver['vehicle_capacity'] < 1 or 
            driver['vehicle_capacity'] > 8):
            return {"error": "Input is not valid"}
        
        if ('availability_start' not in driver or 'availability_end' not in driver or
            driver['availability_start'] < 0 or driver['availability_start'] > 1440 or
            driver['availability_end'] < 0 or driver['availability_end'] > 1440):
            return {"error": "Input is not valid"}
        
        if driver['availability_start'] >= driver['availability_end']:
            return {"error": f"Invalid driver availability window for driver {driver['driver_id']}"}
        
        if 'service_zones' not in driver or not driver['service_zones']:
            return {"error": f"Driver {driver['driver_id']} has no valid service zones"}
        
        for zone_id in driver['service_zones']:
            if zone_id < 1 or zone_id > 50:
                return {"error": "Input is not valid"}
        
        if ('current_passenger_count' not in driver or 
            driver['current_passenger_count'] < 0 or 
            driver['current_passenger_count'] > driver['vehicle_capacity']):
            return {"error": f"Current passenger count exceeds vehicle capacity for driver {driver['driver_id']}"}
        
        if ('driver_rating' not in driver or driver['driver_rating'] < 3.0 or 
            driver['driver_rating'] > 5.0):
            return {"error": "Input is not valid"}
    
    for passenger in passenger_requests:
        if ('passenger_id' not in passenger or passenger['passenger_id'] < 0 or 
            passenger['passenger_id'] > 999):
            return {"error": "Input is not valid"}
        
        if 'pickup_location' not in passenger or 'destination_location' not in passenger:
            return {"error": "Input is not valid"}
        
        pickup = passenger['pickup_location']
        destination = passenger['destination_location']
        
        if ('x' not in pickup or 'y' not in pickup or 
            pickup['x'] < 0 or pickup['x'] > 2000 or 
            pickup['y'] < 0 or pickup['y'] > 2000):
            return {"error": "Input is not valid"}
        
        if ('x' not in destination or 'y' not in destination or 
            destination['x'] < 0 or destination['x'] > 2000 or 
            destination['y'] < 0 or destination['y'] > 2000):
            return {"error": "Input is not valid"}
        
        if ('priority_level' not in passenger or passenger['priority_level'] < 1 or 
            passenger['priority_level'] > 5):
            return {"error": "Input is not valid"}
        
        if ('request_time' not in passenger or passenger['request_time'] < 0 or 
            passenger['request_time'] > 1440):
            return {"error": f"Invalid passenger request time for passenger {passenger['passenger_id']}"}
        
        if 'max_wait_time' not in passenger or passenger['max_wait_time'] <= 0 or passenger['max_wait_time'] > 60:
            return {"error": f"Invalid passenger request time for passenger {passenger['passenger_id']}"}
        
        if passenger['max_wait_time'] < 5:
            return {"error": f"Invalid passenger request time for passenger {passenger['passenger_id']}"}
        
        if ('service_zone' not in passenger or passenger['service_zone'] < 1 or 
            passenger['service_zone'] > 50):
            return {"error": "Input is not valid"}
        
        if 'group_size' not in passenger or passenger['group_size'] <= 0 or passenger['group_size'] > 4:
            return {"error": f"Invalid group size for passenger {passenger['passenger_id']}"}
    
    zone_ids = set()
    for zone in service_zones:
        if 'zone_id' not in zone or zone['zone_id'] < 1 or zone['zone_id'] > 50:
            return {"error": "Input is not valid"}
        
        zone_ids.add(zone['zone_id'])
        
        if 'zone_boundaries' not in zone:
            return {"error": "Input is not valid"}
        
        boundaries = zone['zone_boundaries']
        if ('min_x' not in boundaries or 'max_x' not in boundaries or 
            'min_y' not in boundaries or 'max_y' not in boundaries):
            return {"error": "Input is not valid"}
        
        if (boundaries['min_x'] < 0 or boundaries['max_x'] > 2000 or
            boundaries['min_y'] < 0 or boundaries['max_y'] > 2000):
            return {"error": "Input is not valid"}
        
        if boundaries['min_x'] >= boundaries['max_x'] or boundaries['min_y'] >= boundaries['max_y']:
            return {"error": f"Invalid zone boundaries for zone {zone['zone_id']}"}
        
        if ('congestion_level' not in zone or zone['congestion_level'] < 0.5 or 
            zone['congestion_level'] > 3.0):
            return {"error": "Input is not valid"}
        
        if ('max_pickup_distance' not in zone or zone['max_pickup_distance'] < 100 or 
            zone['max_pickup_distance'] > 1000):
            return {"error": "Input is not valid"}
        
        if ('base_fare_multiplier' not in zone or zone['base_fare_multiplier'] < 1.0 or 
            zone['base_fare_multiplier'] > 3.0):
            return {"error": "Input is not valid"}
    
    for passenger in passenger_requests:
        if passenger['service_zone'] not in zone_ids:
            return {"error": f"Invalid service zone reference for passenger {passenger['passenger_id']}"}
    
    if ('current_system_time' not in temporal_constraints or 
        temporal_constraints['current_system_time'] < 0 or 
        temporal_constraints['current_system_time'] > 1440):
        return {"error": "Input is not valid"}
    
    if 'peak_hours' not in temporal_constraints:
        return {"error": "Input is not valid"}
    
    for peak_period in temporal_constraints['peak_hours']:
        if ('start_time' not in peak_period or 'end_time' not in peak_period or
            peak_period['start_time'] < 0 or peak_period['start_time'] > 1440 or
            peak_period['end_time'] < 0 or peak_period['end_time'] > 1440):
            return {"error": "Input is not valid"}
        
        if peak_period['start_time'] >= peak_period['end_time']:
            return {"error": "Invalid peak hours configuration"}
    
    if 'maintenance_windows' not in temporal_constraints:
        return {"error": "Input is not valid"}
    
    for maintenance in temporal_constraints['maintenance_windows']:
        if ('zone_id' not in maintenance or 'start_time' not in maintenance or 
            'end_time' not in maintenance):
            return {"error": "Input is not valid"}
        
        if (maintenance['zone_id'] < 1 or maintenance['zone_id'] > 50 or
            maintenance['start_time'] < 0 or maintenance['start_time'] > 1440 or
            maintenance['end_time'] < 0 or maintenance['end_time'] > 1440):
            return {"error": "Input is not valid"}
    
    if ('surge_threshold' not in temporal_constraints or 
        temporal_constraints['surge_threshold'] < 1.5 or 
        temporal_constraints['surge_threshold'] > 5.0):
        return {"error": "Input is not valid"}
    
    return None

def get_available_zones(service_zones: List[Dict], temporal_constraints: Dict, 
                       current_time: int) -> List[Dict]:
    available_zones = []
    maintenance_windows = temporal_constraints['maintenance_windows']
    
    for zone in service_zones:
        zone_available = True
        for maintenance in maintenance_windows:
            if (maintenance['zone_id'] == zone['zone_id'] and
                maintenance['start_time'] <= current_time <= maintenance['end_time']):
                zone_available = False
                break
        
        if zone_available:
            available_zones.append(zone)
    
    return available_zones

def euclidean_distance(point1: Dict, point2: Dict) -> float:
    return math.sqrt((point2['x'] - point1['x'])**2 + (point2['y'] - point1['y'])**2)

def is_location_in_zone(location: Dict, zone: Dict) -> bool:
    boundaries = zone['zone_boundaries']
    return (boundaries['min_x'] <= location['x'] <= boundaries['max_x'] and
            boundaries['min_y'] <= location['y'] <= boundaries['max_y'])

def calculate_time_window_overlap(driver: Dict, passenger: Dict, current_time: int) -> float:
    availability_start = driver['availability_start']
    availability_end = driver['availability_end']
    request_time = passenger['request_time']
    max_wait_time = passenger['max_wait_time']
    
    passenger_deadline = request_time + max_wait_time
    
    overlap_start = max(availability_start, request_time)
    overlap_end = min(availability_end, passenger_deadline)
    
    if overlap_start >= overlap_end:
        return 0.0
    
    overlap_duration = overlap_end - overlap_start
    return overlap_duration

def calculate_match_quality_score(driver: Dict, passenger: Dict, zone: Dict, 
                                current_time: int) -> float:
    
    pickup_distance = euclidean_distance(driver['current_location'], passenger['pickup_location'])
    base_distance_cost = pickup_distance
    
    overlap_duration = calculate_time_window_overlap(driver, passenger, current_time)
    max_wait_time = passenger['max_wait_time']
    time_window_overlap_bonus = (overlap_duration / max_wait_time) * 100 if max_wait_time > 0 else 0
    
    priority_weight = (6 - passenger['priority_level']) * 15
    
    zone_efficiency_factor = (1.0 / zone['congestion_level']) * 20
    
    capacity_utilization = (driver['current_passenger_count'] / driver['vehicle_capacity']) * 10
    
    match_quality_score = (base_distance_cost + 
                          (time_window_overlap_bonus * priority_weight) + 
                          (zone_efficiency_factor * capacity_utilization))
    
    return match_quality_score

def build_bipartite_graph(driver_profiles: List[Dict], passenger_requests: List[Dict], 
                         available_zones: List[Dict], zone_lookup: Dict, 
                         current_time: int) -> List[Tuple]:
    edges = []
    zone_lookup_available = {zone['zone_id']: zone for zone in available_zones}
    
    for driver in driver_profiles:
        for passenger in passenger_requests:
            if passenger['service_zone'] not in zone_lookup_available:
                continue
            
            zone = zone_lookup_available[passenger['service_zone']]
            
            if passenger['service_zone'] not in driver['service_zones']:
                continue
            
            overlap = calculate_time_window_overlap(driver, passenger, current_time)
            if overlap <= 0:
                continue
            
            remaining_capacity = driver['vehicle_capacity'] - driver['current_passenger_count']
            if passenger['group_size'] > remaining_capacity:
                continue
            
            pickup_distance = euclidean_distance(driver['current_location'], passenger['pickup_location'])
            if pickup_distance > zone['max_pickup_distance']:
                continue
            
            if not is_location_in_zone(passenger['pickup_location'], zone):
                continue
            
            match_score = calculate_match_quality_score(driver, passenger, zone, current_time)
            
            edges.append((driver['driver_id'], passenger['passenger_id'], match_score, 
                         pickup_distance, zone['zone_id']))
    
    return edges

def calculate_surge_zones(driver_profiles: List[Dict], passenger_requests: List[Dict], 
                         available_zones: List[Dict], surge_threshold: float) -> List[int]:
    surge_zones = []
    
    for zone in available_zones:
        zone_id = zone['zone_id']
        
        passengers_in_zone = 0
        for passenger in passenger_requests:
            if passenger['service_zone'] == zone_id:
                passengers_in_zone += 1
        
        drivers_in_zone = 0
        for driver in driver_profiles:
            if zone_id in driver['service_zones']:
                remaining_capacity = driver['vehicle_capacity'] - driver['current_passenger_count']
                if remaining_capacity > 0:
                    drivers_in_zone += 1
        
        if drivers_in_zone > 0:
            ratio = passengers_in_zone / drivers_in_zone
            if ratio > surge_threshold:
                surge_zones.append(zone_id)
    
    return surge_zones

def apply_surge_adjustments(edges: List[Tuple], surge_zones: List[int]) -> List[Tuple]:
    adjusted_edges = []
    
    for driver_id, passenger_id, score, distance, zone_id in edges:
        if zone_id in surge_zones:
            adjusted_score = score * 0.85
        else:
            adjusted_score = score
        
        adjusted_edges.append((driver_id, passenger_id, adjusted_score, distance, zone_id))
    
    return adjusted_edges

def hungarian_algorithm(cost_matrix: List[List[float]]) -> List[Tuple[int, int]]:
    if not cost_matrix or not cost_matrix[0]:
        return []
    
    n_rows = len(cost_matrix)
    n_cols = len(cost_matrix[0])
    n = max(n_rows, n_cols)
    
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    
    max_val = max(max(row) for row in cost_matrix)
    for i in range(n_rows):
        for j in range(n_cols):
            matrix[i][j] = max_val - cost_matrix[i][j]
    
    for i in range(n_rows, n):
        for j in range(n):
            matrix[i][j] = max_val
    
    for i in range(n):
        for j in range(n_cols, n):
            matrix[i][j] = max_val
    
    row_covered = [False] * n
    col_covered = [False] * n
    marked = [[0 for _ in range(n)] for _ in range(n)]
    
    for i in range(n):
        min_val = min(matrix[i])
        for j in range(n):
            matrix[i][j] -= min_val
    
    for j in range(n):
        min_val = min(matrix[i][j] for i in range(n))
        for i in range(n):
            matrix[i][j] -= min_val
    
    for i in range(n):
        for j in range(n):
            if matrix[i][j] == 0 and not row_covered[i] and not col_covered[j]:
                marked[i][j] = 1
                row_covered[i] = True
                col_covered[j] = True
    
    row_covered = [False] * n
    col_covered = [False] * n
    
    while True:
        for i in range(n):
            for j in range(n):
                if marked[i][j] == 1:
                    col_covered[j] = True
        
        covered_cols = sum(col_covered)
        if covered_cols == n:
            break
        
        row, col = find_uncovered_zero(matrix, row_covered, col_covered)
        if row == -1:
            min_val = float('inf')
            for i in range(n):
                for j in range(n):
                    if not row_covered[i] and not col_covered[j]:
                        min_val = min(min_val, matrix[i][j])
            
            for i in range(n):
                for j in range(n):
                    if row_covered[i]:
                        matrix[i][j] += min_val
                    if not col_covered[j]:
                        matrix[i][j] -= min_val
        else:
            marked[row][col] = 2
            
            star_col = -1
            for j in range(n):
                if marked[row][j] == 1:
                    star_col = j
                    break
            
            if star_col != -1:
                row_covered[row] = True
                col_covered[star_col] = False
            else:
                path = [(row, col)]
                while True:
                    star_row = -1
                    for i in range(n):
                        if marked[i][path[-1][1]] == 1:
                            star_row = i
                            break
                    
                    if star_row == -1:
                        break
                    
                    path.append((star_row, path[-1][1]))
                    
                    prime_col = -1
                    for j in range(n):
                        if marked[star_row][j] == 2:
                            prime_col = j
                            break
                    
                    path.append((star_row, prime_col))
                
                for i in range(0, len(path), 2):
                    r, c = path[i]
                    marked[r][c] = 1
                
                for i in range(1, len(path), 2):
                    r, c = path[i]
                    marked[r][c] = 0
                
                for i in range(n):
                    for j in range(n):
                        if marked[i][j] == 2:
                            marked[i][j] = 0
                
                row_covered = [False] * n
                col_covered = [False] * n
    
    result = []
    for i in range(n_rows):
        for j in range(n_cols):
            if marked[i][j] == 1:
                result.append((i, j))
    
    return result

def find_uncovered_zero(matrix: List[List[float]], row_covered: List[bool], 
                       col_covered: List[bool]) -> Tuple[int, int]:
    for i in range(len(matrix)):
        for j in range(len(matrix[0])):
            if matrix[i][j] == 0 and not row_covered[i] and not col_covered[j]:
                return i, j
    return -1, -1

def find_maximum_weight_matching(edges: List[Tuple], driver_profiles: List[Dict], 
                               passenger_requests: List[Dict]) -> List[Dict]:
    if not edges:
        return []
    
    driver_ids = list(set(edge[0] for edge in edges))
    passenger_ids = list(set(edge[1] for edge in edges))
    
    driver_id_to_index = {driver_id: i for i, driver_id in enumerate(driver_ids)}
    passenger_id_to_index = {passenger_id: i for i, passenger_id in enumerate(passenger_ids)}
    
    cost_matrix = [[-float('inf') for _ in range(len(passenger_ids))] 
                   for _ in range(len(driver_ids))]
    
    edge_info = {}
    
    for driver_id, passenger_id, score, distance, zone_id in edges:
        driver_idx = driver_id_to_index[driver_id]
        passenger_idx = passenger_id_to_index[passenger_id]
        
        if score > cost_matrix[driver_idx][passenger_idx]:
            cost_matrix[driver_idx][passenger_idx] = score
            edge_info[(driver_idx, passenger_idx)] = (driver_id, passenger_id, score, distance, zone_id)
    
    for i in range(len(driver_ids)):
        for j in range(len(passenger_ids)):
            if cost_matrix[i][j] == -float('inf'):
                cost_matrix[i][j] = 0
    
    assignment = hungarian_algorithm(cost_matrix)
    
    matches = []
    
    for driver_idx, passenger_idx in assignment:
        if (driver_idx, passenger_idx) in edge_info:
            driver_id, passenger_id, score, distance, zone_id = edge_info[(driver_idx, passenger_idx)]
            
            passenger = next(p for p in passenger_requests if p['passenger_id'] == passenger_id)
            
            estimated_pickup_time = passenger['request_time'] + int(distance / 30)
            travel_distance = euclidean_distance(passenger['pickup_location'], passenger['destination_location'])
            estimated_travel_time = int(travel_distance / 40)
            
            match = {
                'driver_id': driver_id,
                'passenger_id': passenger_id,
                'pickup_distance': round(distance, 2),
                'match_quality_score': round(score, 2),
                'estimated_pickup_time': estimated_pickup_time,
                'estimated_travel_time': estimated_travel_time,
                'service_zone': zone_id
            }
            
            matches.append(match)
    
    matches.sort(key=lambda x: (-x['match_quality_score'], x['driver_id']))
    
    return matches

def calculate_system_metrics(matches: List[Dict], driver_profiles: List[Dict], 
                           passenger_requests: List[Dict], available_zones: List[Dict], 
                           current_time: int) -> Dict:
    total_matches = len(matches)
    
    total_wait_time = 0
    for match in matches:
        passenger = next(p for p in passenger_requests if p['passenger_id'] == match['passenger_id'])
        wait_time = match['estimated_pickup_time'] - passenger['request_time']
        total_wait_time += max(0, wait_time)
    
    average_wait_time = total_wait_time / total_matches if total_matches > 0 else 0.0
    
    total_quality = sum(match['match_quality_score'] for match in matches)
    average_match_quality = total_quality / total_matches if total_matches > 0 else 0.0
    
    zone_utilization_rates = {}
    for zone in available_zones:
        zone_id = zone['zone_id']
        zone_matches = sum(1 for match in matches if match['service_zone'] == zone_id)
        
        available_drivers_in_zone = 0
        for driver in driver_profiles:
            if zone_id in driver['service_zones']:
                remaining_capacity = driver['vehicle_capacity'] - driver['current_passenger_count']
                if remaining_capacity > 0:
                    available_drivers_in_zone += 1
        
        passengers_requesting_zone = sum(1 for p in passenger_requests if p['service_zone'] == zone_id)
        
        max_possible_matches = min(available_drivers_in_zone, passengers_requesting_zone)
        
        if max_possible_matches > 0:
            zone_utilization_rates[zone_id] = zone_matches / max_possible_matches
        else:
            zone_utilization_rates[zone_id] = 0.0
    
    return {
        'total_matches': total_matches,
        'average_wait_time': round(average_wait_time, 1),
        'average_match_quality': round(average_match_quality, 2),
        'zone_utilization_rates': zone_utilization_rates
    }

def prepare_output(matches: List[Dict], metrics: Dict, driver_profiles: List[Dict], 
                  passenger_requests: List[Dict], surge_zones: List[int]) -> Dict:
    matched_passengers = set(match['passenger_id'] for match in matches)
    matched_drivers = set(match['driver_id'] for match in matches)
    
    unmatched_passengers = [p['passenger_id'] for p in passenger_requests 
                           if p['passenger_id'] not in matched_passengers]
    
    available_drivers = []
    for driver in driver_profiles:
        if driver['driver_id'] not in matched_drivers:
            remaining_capacity = driver['vehicle_capacity'] - driver['current_passenger_count']
            if remaining_capacity > 0:
                available_drivers.append(driver['driver_id'])
    
    return {
        "successful_matches": matches,
        "system_efficiency_metrics": metrics,
        "unmatched_passengers": sorted(unmatched_passengers),
        "available_drivers": sorted(available_drivers),
        "surge_zones": sorted(surge_zones)
    }

if __name__ == "__main__":
    driver_profiles = [
        {"driver_id": 0, "current_location": {"x": 500, "y": 600}, "vehicle_capacity": 4, 
         "availability_start": 480, "availability_end": 720, "service_zones": [1, 2], 
         "current_passenger_count": 1, "driver_rating": 4.5},
        {"driver_id": 1, "current_location": {"x": 800, "y": 900}, "vehicle_capacity": 2, 
         "availability_start": 420, "availability_end": 660, "service_zones": [2, 3], 
         "current_passenger_count": 0, "driver_rating": 4.2}
    ]
    
    passenger_requests = [
        {"passenger_id": 0, "pickup_location": {"x": 520, "y": 580}, 
         "destination_location": {"x": 700, "y": 800}, "priority_level": 2, 
         "request_time": 500, "max_wait_time": 15, "service_zone": 1, "group_size": 1},
        {"passenger_id": 1, "pickup_location": {"x": 850, "y": 920}, 
         "destination_location": {"x": 1000, "y": 1100}, "priority_level": 1, 
         "request_time": 480, "max_wait_time": 20, "service_zone": 3, "group_size": 2}
    ]
    
    service_zones = [
        {"zone_id": 1, "zone_boundaries": {"min_x": 400, "max_x": 800, "min_y": 500, "max_y": 900}, 
         "congestion_level": 1.2, "max_pickup_distance": 200, "base_fare_multiplier": 1.5},
        {"zone_id": 2, "zone_boundaries": {"min_x": 600, "max_x": 1000, "min_y": 700, "max_y": 1100}, 
         "congestion_level": 2.1, "max_pickup_distance": 150, "base_fare_multiplier": 2.0},
        {"zone_id": 3, "zone_boundaries": {"min_x": 750, "max_x": 1200, "min_y": 850, "max_y": 1250}, 
         "congestion_level": 1.8, "max_pickup_distance": 300, "base_fare_multiplier": 1.8}
    ]
    
    temporal_constraints = {
        "current_system_time": 500,
        "peak_hours": [{"start_time": 480, "end_time": 540}, {"start_time": 1020, "end_time": 1080}],
        "maintenance_windows": [{"zone_id": 2, "start_time": 600, "end_time": 660}],
        "surge_threshold": 2.0
    }
    
    result = optimize_ride_matching(driver_profiles, passenger_requests, service_zones, temporal_constraints)
    print(result)