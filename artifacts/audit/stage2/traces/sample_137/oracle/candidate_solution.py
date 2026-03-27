import heapq
from typing import List, Dict

# Floating-point precision tolerance
EPSILON = 1e-9

# Energy and time constraints
MAX_ENERGY = 1000.0
MAX_WAIT_TIME = 24.0

# Path length constraints
MAX_PATH_LENGTH = 50

# Battery and energy parameters
DEGRADATION_FACTOR = 0.001
REGEN_DECAY_FACTOR = 0.85
MAX_REGEN_COUNT = 10

# Charging strategy multipliers
CHARGE_MULTIPLIER_LOW = 1.2
CHARGE_MULTIPLIER_MID = 1.5
CHARGE_MULTIPLIER_HALF_MAX = 0.5
CHARGE_MULTIPLIER_FULL = 1.0

# Time-dependent cost parameters
RUSH_HOUR_MORNING_START = 7
RUSH_HOUR_MORNING_END = 9
RUSH_HOUR_EVENING_START = 17
RUSH_HOUR_EVENING_END = 19
OFF_PEAK_NIGHT_START = 22
OFF_PEAK_MORNING_END = 6
RUSH_HOUR_MULTIPLIER = 1.5
OFF_PEAK_MULTIPLIER = 0.8
STANDARD_MULTIPLIER = 1.0

# Iteration limit calculation parameters
CHARGING_OPTIONS_COUNT = 5
TIME_STATES_FACTOR = 100
MIN_ITERATION_LIMIT = 10000

def optimize_delivery_route(graph: dict, start: str, end: str, initial_energy: float) -> list:
    """
    Find the optimal delivery route that minimizes travel time while respecting energy constraints.
    
    This function implements a modified Dijkstra's algorithm with state-space search to find
    feasible routes through a multi-constraint network of electric vehicle charging stations.
    The algorithm considers energy consumption, charging requirements, time windows, and
    station capacity constraints.
    
    Args:
        graph (dict): A dictionary representing the road network where each key is a node identifier
                     (str) and each value is a dict containing:
                     - 'neighbors' (list): List of neighbor dictionaries, each with:
                         * 'node' (str): Identifier of the neighbor node
                         * 'energy_cost' (float): Energy required to travel to this neighbor
                         * 'travel_time' (float): Time required to travel to this neighbor
                     - 'station_constraints' (dict): Charging station properties (optional):
                         * 'charge_rate' (float): Energy units recharged per time unit (default: 0.0)
                         * 'capacity' (int): Number of vehicles that can charge simultaneously (default: 0)
                         * 'open_windows' (list): List of [start_time, end_time] pairs when station
                           is open for charging (default: [])
        
        start (str): Identifier of the starting node in the graph
        
        end (str): Identifier of the destination node in the graph
        
        initial_energy (float): Starting energy level of the vehicle (must be >= 0)
    
    Returns:
        list: Ordered list of node identifiers representing the optimal path from start to end.
              Returns an empty list [] if:
              - No feasible path exists given energy constraints
              - Start or end node is not in the graph
              - Graph is empty
              - Energy constraints cannot be satisfied even with charging
              
              Returns [start] if start equals end and the node exists in the graph.
    
    Notes:
        - The algorithm prioritizes minimizing total travel time
        - Handles multiple charging strategies at each station
        - Supports time window constraints for station availability
        - Manages floating-point precision with epsilon comparisons
        - Prevents infinite loops through cycle detection and iteration limits
        - Energy costs can be negative (representing regeneration zones)
    
    """
    if not graph or start not in graph or end not in graph:
        return []
    
    if start == end:
        return [start]
    
    has_time_dependent_costs = any(
        any(n.get('time_dependent', False) for n in node.get('neighbors', []))
        for node in graph.values()
    )
    
    has_cascading_failures = any(
        node.get('station_constraints', {}).get('fail_time') is not None
        for node in graph.values()
    )
    
    has_reservations = any(
        node.get('station_constraints', {}).get('reservations')
        for node in graph.values()
    )
    
    has_regeneration = any(
        any(n.get('energy_cost', 0) < 0 for n in node.get('neighbors', []))
        for node in graph.values()
    )
    
    has_degradation = any(
        node.get('station_constraints', {}).get('degradation_enabled', False)
        for node in graph.values()
    )
    
    use_advanced_features = (has_time_dependent_costs or has_cascading_failures or 
                            has_reservations or has_regeneration or has_degradation)
    
    def is_in_time_window(time: float, windows: List[List[float]]) -> bool:
        for window in windows:
            if window[0] - EPSILON <= time <= window[1] + EPSILON:
                return True
        return False
    
    def find_next_window_start(time: float, windows: List[List[float]]) -> float:
        min_wait = float('inf')
        for window in windows:
            if window[0] > time:
                min_wait = min(min_wait, window[0] - time)
        return min_wait if min_wait != float('inf') else None
    
    def get_charging_time(current_energy: float, target_energy: float, charge_rate: float) -> float:
        if charge_rate <= EPSILON:
            return float('inf')
        return max(0.0, (target_energy - current_energy) / charge_rate)
    
    def get_time_multiplier(time: float) -> float:
        if not has_time_dependent_costs:
            return STANDARD_MULTIPLIER
        hour = time % 24
        if (RUSH_HOUR_MORNING_START <= hour < RUSH_HOUR_MORNING_END or 
            RUSH_HOUR_EVENING_START <= hour < RUSH_HOUR_EVENING_END):
            return RUSH_HOUR_MULTIPLIER
        elif OFF_PEAK_NIGHT_START <= hour or hour < OFF_PEAK_MORNING_END:
            return OFF_PEAK_MULTIPLIER
        return STANDARD_MULTIPLIER
    
    def apply_degradation(base_cost: float, cumulative_distance: float) -> float:
        if not has_degradation:
            return base_cost
        multiplier = 1.0 + DEGRADATION_FACTOR * cumulative_distance
        return base_cost * multiplier
    
    def calculate_regeneration(base_regen: float, regen_count: int) -> float:
        if regen_count >= MAX_REGEN_COUNT:
            return 0.0
        return base_regen * (REGEN_DECAY_FACTOR ** regen_count)
    
    def is_station_failed(node: str, time: float, failures: Dict[str, float]) -> bool:
        return node in failures and time >= failures[node]
    
    def get_cascading_failures() -> Dict[str, float]:
        if not has_cascading_failures:
            return {}
        
        initial_failures = {}
        for node, data in graph.items():
            station = data.get('station_constraints', {})
            if station.get('fail_time') is not None:
                initial_failures[node] = station.get('fail_time', 0)
        
        all_failures = initial_failures.copy()
        for node, fail_time in list(all_failures.items()):
            node_data = graph.get(node, {})
            neighbors = node_data.get('neighbors', [])
            for neighbor_info in neighbors:
                next_node = neighbor_info.get('node')
                cascade_delay = neighbor_info.get('cascade_delay', 0)
                if cascade_delay > 0:
                    cascade_time = fail_time + cascade_delay
                    if next_node not in all_failures or cascade_time < all_failures[next_node]:
                        all_failures[next_node] = cascade_time
        return all_failures
    
    def check_reservation_conflict(node: str, arrival_time: float, charging_duration: float) -> bool:
        if not has_reservations or node not in reservations:
            return False
        departure_time = arrival_time + charging_duration
        for res_start, res_end in reservations[node]:
            if not (departure_time <= res_start + EPSILON or arrival_time >= res_end - EPSILON):
                return True
        return False
    
    cascading_failures = get_cascading_failures()
    
    reservations = {}
    if has_reservations:
        for node, data in graph.items():
            station = data.get('station_constraints', {})
            node_reservations = station.get('reservations', [])
            if node_reservations:
                reservations[node] = node_reservations
    
    if use_advanced_features:
        priority_queue = [(0.0, 0.0, 0.0, initial_energy, start, [start], 0.0, 0, {})]
    else:
        priority_queue = [(0.0, 0.0, 0.0, initial_energy, start, [start])]
    
    visited = {}
    best_cost = {}
    
    num_nodes = len(graph)
    num_edges = sum(len(node.get('neighbors', [])) for node in graph.values())
    iteration_limit = max(
        num_nodes * num_edges * CHARGING_OPTIONS_COUNT * TIME_STATES_FACTOR,
        MIN_ITERATION_LIMIT
    )
    iterations = 0
    
    while priority_queue and iterations < iteration_limit:
        iterations += 1
        
        if use_advanced_features:
            (total_cost, distance, current_time, current_energy, current_node, 
             path, cumulative_distance, regen_count, energy_at_nodes) = heapq.heappop(priority_queue)
        else:
            total_cost, distance, current_time, current_energy, current_node, path = heapq.heappop(priority_queue)
            cumulative_distance = 0.0
            regen_count = 0
            energy_at_nodes = {}
        
        if current_node == end:
            return path
        
        if use_advanced_features:
            state_key = (current_node, round(current_time, 6), round(cumulative_distance, 3))
        else:
            state_key = (current_node, round(current_time, 6))
        
        energy_at_state = visited.get(state_key, -float('inf'))
        
        if current_energy <= energy_at_state + EPSILON:
            continue
        
        visited[state_key] = current_energy
        
        if has_cascading_failures and is_station_failed(current_node, current_time, cascading_failures):
            continue
        
        if has_regeneration and len(path) > 2:
            if current_node in energy_at_nodes:
                if current_energy > energy_at_nodes[current_node] + EPSILON:
                    continue
        
        node_data = graph.get(current_node, {})
        neighbors = node_data.get('neighbors', [])
        station = node_data.get('station_constraints', {})
        
        charge_rate = max(0.0, float(station.get('charge_rate', 0.0)))
        capacity = int(station.get('capacity', 0))
        open_windows = station.get('open_windows', [])
        
        charging_options = [0.0]
        if charge_rate > EPSILON and capacity > 0 and open_windows:
            if not (has_cascading_failures and is_station_failed(current_node, current_time, cascading_failures)):
                charge_targets = [
                    current_energy * CHARGE_MULTIPLIER_LOW,
                    current_energy * CHARGE_MULTIPLIER_MID,
                    MAX_ENERGY * CHARGE_MULTIPLIER_HALF_MAX,
                    MAX_ENERGY * CHARGE_MULTIPLIER_FULL
                ]
                for charge_target in charge_targets:
                    if charge_target > current_energy + EPSILON:
                        charging_options.append(charge_target)
        
        for target_energy in charging_options:
            time_after_action = current_time
            energy_after_action = current_energy
            
            if target_energy > current_energy + EPSILON:
                charge_time_needed = get_charging_time(current_energy, target_energy, charge_rate)
                
                if charge_time_needed == float('inf'):
                    continue
                
                charge_start_time = current_time
                if not is_in_time_window(charge_start_time, open_windows):
                    wait_time = find_next_window_start(charge_start_time, open_windows)
                    if wait_time is None or wait_time > MAX_WAIT_TIME:
                        continue
                    charge_start_time += wait_time
                
                charge_end_time = charge_start_time + charge_time_needed
                
                if has_reservations and check_reservation_conflict(current_node, charge_start_time, charge_time_needed):
                    continue
                
                can_charge = False
                for window in open_windows:
                    if window[0] - EPSILON <= charge_start_time and charge_end_time <= window[1] + EPSILON:
                        can_charge = True
                        break
                
                if not can_charge:
                    continue
                
                time_after_action = charge_end_time
                energy_after_action = min(target_energy, MAX_ENERGY)
            
            for neighbor_info in neighbors:
                next_node = neighbor_info.get('node')
                base_energy_cost = neighbor_info.get('energy_cost', 0.0)
                travel_time = max(EPSILON, neighbor_info.get('travel_time', 0.0))
                
                if next_node not in graph:
                    continue
                
                if next_node in path:
                    if len(path) < MAX_PATH_LENGTH:
                        pass
                    else:
                        continue
                
                arrival_time = time_after_action + travel_time
                
                if has_cascading_failures and is_station_failed(next_node, arrival_time, cascading_failures):
                    continue
                
                time_multiplier = get_time_multiplier(arrival_time)
                energy_cost = base_energy_cost * time_multiplier
                
                if energy_cost >= 0:
                    energy_cost = apply_degradation(energy_cost, cumulative_distance)
                    energy_cost = max(EPSILON, energy_cost)
                    new_regen_count = regen_count
                elif has_regeneration:
                    regen_amount = calculate_regeneration(abs(energy_cost), regen_count)
                    energy_cost = -regen_amount
                    new_regen_count = regen_count + 1
                else:
                    energy_cost = max(EPSILON, energy_cost)
                    new_regen_count = regen_count
                
                if energy_after_action < energy_cost - EPSILON:
                    continue
                
                new_energy = min(energy_after_action - energy_cost, MAX_ENERGY)
                new_time = arrival_time
                new_distance = distance + travel_time
                new_cumulative_distance = cumulative_distance + travel_time
                new_path = path + [next_node]
                
                heuristic = 0.0
                new_total_cost = new_distance + heuristic
                
                if use_advanced_features:
                    next_state_key = (next_node, round(new_time, 6), round(new_cumulative_distance, 3))
                    new_energy_at_nodes = energy_at_nodes.copy()
                    new_energy_at_nodes[next_node] = new_energy
                else:
                    next_state_key = (next_node, round(new_time, 6))
                
                if new_energy > best_cost.get(next_state_key, -float('inf')) + EPSILON:
                    best_cost[next_state_key] = new_energy
                    if use_advanced_features:
                        heapq.heappush(priority_queue, (
                            new_total_cost,
                            new_distance,
                            new_time,
                            new_energy,
                            next_node,
                            new_path,
                            new_cumulative_distance,
                            new_regen_count,
                            new_energy_at_nodes
                        ))
                    else:
                        heapq.heappush(priority_queue, (
                            new_total_cost,
                            new_distance,
                            new_time,
                            new_energy,
                            next_node,
                            new_path
                        ))
    
    return []


if __name__ == "__main__":
    graph = {
        'H1': {
            'neighbors': [
                {'node': 'C2', 'energy_cost': 6.0, 'travel_time': 2.0},
                {'node': 'C3', 'energy_cost': 5.0, 'travel_time': 1.5}
            ],
            'station_constraints': {
                'charge_rate': 5.0,
                'capacity': 2,
                'open_windows': [[0, 10], [12, 24]]
            }
        },
        'C2': {
            'neighbors': [
                {'node': 'C3', 'energy_cost': 2.0, 'travel_time': 1.0},
                {'node': 'D4', 'energy_cost': 7.0, 'travel_time': 3.0}
            ],
            'station_constraints': {
                'charge_rate': 3.0,
                'capacity': 1,
                'open_windows': [[0, 8], [15, 22]]
            }
        },
        'C3': {
            'neighbors': [
                {'node': 'D4', 'energy_cost': 4.0, 'travel_time': 2.0}
            ],
            'station_constraints': {
                'charge_rate': 7.0,
                'capacity': 2,
                'open_windows': [[0, 24]]
            }
        },
        'D4': {
            'neighbors': [],
            'station_constraints': {
                'charge_rate': 0.0,
                'capacity': 0,
                'open_windows': [[0, 24]]
            }
        }
    }
    start = 'H1'
    end = 'D4'
    initial_energy = 10.0
    print(optimize_delivery_route(graph, start, end, initial_energy))