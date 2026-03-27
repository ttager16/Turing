from typing import Dict, List, Tuple, Set, Optional
import heapq


class FuelStation:
    def __init__(self, city: int, availability_windows: List[Tuple[float, float]], 
                 refuel_time: float = 5.0):
        self.city = city
        self.availability_windows = sorted(availability_windows) if availability_windows else [(0.0, float('inf'))]
        self.refuel_time = refuel_time
    
    def is_available_at_time(self, time: float) -> bool:
        for start, end in self.availability_windows:
            if start <= time <= end:
                return True
        return False
    
    def next_available_time(self, current_time: float) -> Optional[float]:
        for start, end in self.availability_windows:
            if current_time <= end:
                if current_time < start:
                    return start
                return current_time
        return None
    
    def get_wait_time(self, arrival_time: float) -> Optional[float]:
        next_time = self.next_available_time(arrival_time)
        if next_time is None:
            return None
        return max(0.0, next_time - arrival_time)


class State:
    def __init__(self, city: int, fuel: float, inspections_done: Set[int], 
                 current_time: float):
        self.city = city
        self.fuel = max(0.0, fuel)
        self.inspections_done = frozenset(inspections_done)
        self.current_time = current_time
    
    def __eq__(self, other):
        return (self.city == other.city and 
                abs(self.fuel - other.fuel) < 1e-6 and 
                self.inspections_done == other.inspections_done and
                abs(self.current_time - other.current_time) < 1e-6)
    
    def __hash__(self):
        return hash((self.city, round(self.fuel, 2), 
                    self.inspections_done, round(self.current_time, 2)))
    
    def __repr__(self):
        return f"State(city={self.city}, fuel={self.fuel:.2f}, " \
               f"inspections={set(self.inspections_done)}, time={self.current_time:.2f})"


class PriorityQueue:
    def __init__(self):
        self.heap = []
        self.counter = 0
    
    def push(self, priority: float, item: Tuple):
        heapq.heappush(self.heap, (priority, self.counter, item))
        self.counter += 1
    
    def pop(self) -> Optional[Tuple]:
        if self.heap:
            return heapq.heappop(self.heap)[2]
        return None
    
    def is_empty(self) -> bool:
        return len(self.heap) == 0


class PathReconstructor:
    def __init__(self):
        self.parent_map = {}
    
    def record_parent(self, state: State, parent_state: Optional[State]):
        self.parent_map[state] = parent_state
    
    def reconstruct_path(self, final_state: State) -> List[int]:
        if final_state is None:
            return []
        
        path = []
        current = final_state
        visited_in_path = set()
        
        while current is not None:
            if id(current) in visited_in_path:
                break
            visited_in_path.add(id(current))
            path.append(current.city)
            current = self.parent_map.get(current, None)
        
        path.reverse()
        
        unique_path = []
        for city in path:
            if not unique_path or city != unique_path[-1]:
                unique_path.append(city)
        
        return unique_path


class DynamicFuelManager:
    def __init__(self, fuel_stations_config: Dict[int, Dict], 
                 vehicle_capacity: float, average_speed: float = 50.0):
        self.vehicle_capacity = vehicle_capacity
        self.average_speed = average_speed
        self.stations = {}
        
        for city, config in fuel_stations_config.items():
            windows = config.get('availability_windows', [(0.0, float('inf'))])
            refuel_time = config.get('refuel_time', 5.0)
            self.stations[city] = FuelStation(city, windows, refuel_time)
    
    def has_station(self, city: int) -> bool:
        return city in self.stations
    
    def is_station_available(self, city: int, time: float) -> bool:
        if city not in self.stations:
            return False
        return self.stations[city].is_available_at_time(time)
    
    def get_refuel_options(self, city: int, current_fuel: float, 
                          arrival_time: float, enable_partial: bool = True) -> List[Tuple[float, float, float]]:
        if city not in self.stations:
            return [(current_fuel, 0.0, arrival_time)]
        
        station = self.stations[city]
        wait_time = station.get_wait_time(arrival_time)
        
        if wait_time is None:
            return [(current_fuel, 0.0, arrival_time)]
        
        options = []
        refuel_start_time = arrival_time + wait_time
        
        if not station.is_available_at_time(refuel_start_time):
            return [(current_fuel, 0.0, arrival_time)]
        
        max_refuel = self.vehicle_capacity - current_fuel
        
        if max_refuel < 1e-6:
            return [(current_fuel, wait_time, refuel_start_time)]
        
        if enable_partial:
            refuel_amounts = [0.0]
            num_steps = 4
            for i in range(1, num_steps + 1):
                refuel_amounts.append((max_refuel * i) / num_steps)
        else:
            refuel_amounts = [max_refuel]
        
        for refuel_amount in refuel_amounts:
            if refuel_amount < -1e-6:
                continue
            
            refuel_amount = max(0.0, refuel_amount)
            new_fuel = min(current_fuel + refuel_amount, self.vehicle_capacity)
            
            if refuel_amount < 1e-6:
                refuel_duration = 0.0
            else:
                refuel_duration = (refuel_amount / self.vehicle_capacity) * station.refuel_time
            
            total_time = wait_time + refuel_duration
            departure_time = refuel_start_time + refuel_duration
            
            options.append((new_fuel, total_time, departure_time))
        
        if not options:
            options.append((current_fuel, 0.0, arrival_time))
        
        return options
    
    def calculate_travel_time(self, distance: float) -> float:
        if distance <= 0:
            return 0.0
        return distance / self.average_speed


class RouteValidator:
    def __init__(self, graph: Dict[int, List[List[float]]], 
                 required_inspections: List[int]):
        self.graph = graph
        self.required_inspections = set(required_inspections) if required_inspections else set()
    
    def validate_graph(self) -> bool:
        if not self.graph:
            return False
        
        for city, edges in self.graph.items():
            if not isinstance(edges, list):
                return False
            for edge in edges:
                if not isinstance(edge, list) or len(edge) < 2:
                    return False
                try:
                    distance = float(edge[1])
                    if distance < 0:
                        return False
                except (ValueError, TypeError):
                    return False
        
        return True
    
    def is_valid_destination_state(self, state: State, destination: int) -> bool:
        if state.city != destination:
            return False
        
        return self.required_inspections.issubset(state.inspections_done)
    
    def can_reach_neighbor(self, current_fuel: float, distance: float, 
                          fuel_consumption: float) -> bool:
        if distance < 0:
            return False
        
        if distance == 0:
            return True
        
        fuel_needed = distance * fuel_consumption
        return current_fuel >= fuel_needed - 1e-6
    
    def is_inspection_point(self, city: int) -> bool:
        return city in self.required_inspections
    
    def get_missing_inspections(self, completed: Set[int]) -> Set[int]:
        return self.required_inspections - completed


class StateSpaceExplorer:
    def __init__(self, graph: Dict[int, List[List[float]]], 
                 fuel_manager: DynamicFuelManager,
                 validator: RouteValidator,
                 fuel_consumption: float,
                 enable_partial_refuel: bool = True):
        self.graph = graph
        self.fuel_manager = fuel_manager
        self.validator = validator
        self.fuel_consumption = fuel_consumption
        self.enable_partial_refuel = enable_partial_refuel
        self.visited_states = {}
    
    def get_initial_state(self, start: int, initial_fuel: float) -> State:
        initial_inspections = set()
        if self.validator.is_inspection_point(start):
            initial_inspections.add(start)
        
        return State(start, initial_fuel, initial_inspections, 0.0)
    
    def generate_next_states(self, current_state: State) -> List[Tuple[float, State]]:
        next_states = []
        current_city = current_state.city
        
        if current_city not in self.graph:
            return next_states
        
        refuel_options = self.fuel_manager.get_refuel_options(
            current_city, current_state.fuel, current_state.current_time, 
            self.enable_partial_refuel)
        
        if not refuel_options:
            refuel_options = [(current_state.fuel, 0.0, current_state.current_time)]
        
        edges = self.graph[current_city]
        if not edges:
            return next_states
        
        for neighbor_info in edges:
            if not isinstance(neighbor_info, list) or len(neighbor_info) < 2:
                continue
            
            try:
                neighbor_city = int(neighbor_info[0])
                distance = float(neighbor_info[1])
            except (ValueError, TypeError, IndexError):
                continue
            
            if distance < 0:
                continue
            
            if distance == 0:
                new_inspections = set(current_state.inspections_done)
                if self.validator.is_inspection_point(neighbor_city):
                    new_inspections.add(neighbor_city)
                
                new_state = State(neighbor_city, current_state.fuel, 
                                new_inspections, current_state.current_time)
                next_states.append((0.0, new_state))
                continue
            
            travel_time = self.fuel_manager.calculate_travel_time(distance)
            
            for refueled_fuel, delay_time, departure_time in refuel_options:
                if not self.validator.can_reach_neighbor(
                    refueled_fuel, distance, self.fuel_consumption):
                    continue
                
                fuel_after_travel = refueled_fuel - (distance * self.fuel_consumption)
                
                if fuel_after_travel < -1e-6:
                    continue
                
                fuel_after_travel = max(0.0, fuel_after_travel)
                
                arrival_time = departure_time + travel_time
                
                new_inspections = set(current_state.inspections_done)
                if self.validator.is_inspection_point(neighbor_city):
                    new_inspections.add(neighbor_city)
                
                new_state = State(neighbor_city, fuel_after_travel, 
                                new_inspections, arrival_time)
                
                time_cost_factor = 0.01
                total_cost = distance + (delay_time * time_cost_factor)
                
                next_states.append((total_cost, new_state))
        
        return next_states
    
    def should_update_state(self, state: State, new_distance: float) -> bool:
        state_key = (state.city, round(state.fuel, 1), state.inspections_done)
        
        if state_key not in self.visited_states:
            return True
        
        old_distance, old_time, old_fuel = self.visited_states[state_key]
        
        if new_distance < old_distance - 1e-6:
            return True
        
        if abs(new_distance - old_distance) < 1e-6:
            if state.current_time < old_time - 1e-6:
                return True
            if abs(state.current_time - old_time) < 1e-6 and state.fuel > old_fuel + 1e-6:
                return True
        
        return False
    
    def mark_state_visited(self, state: State, distance: float):
        state_key = (state.city, round(state.fuel, 1), state.inspections_done)
        self.visited_states[state_key] = (distance, state.current_time, state.fuel)


class AdaptiveRoutePlanner:
    def __init__(self, graph: Dict[int, List[List[float]]], 
                 fuel_stations_config: Dict[int, Dict],
                 vehicle_capacity: float,
                 fuel_consumption: float,
                 inspections: List[int],
                 average_speed: float = 50.0,
                 enable_partial_refuel: bool = True):
        
        self.validator = RouteValidator(graph, inspections)
        
        if not self.validator.validate_graph():
            self.is_valid = False
            return
        
        self.is_valid = True
        self.graph = graph
        self.vehicle_capacity = vehicle_capacity
        self.fuel_consumption = fuel_consumption
        self.inspections = inspections
        
        self.fuel_manager = DynamicFuelManager(
            fuel_stations_config, vehicle_capacity, average_speed)
        
        self.explorer = StateSpaceExplorer(
            graph, self.fuel_manager, self.validator, fuel_consumption, enable_partial_refuel)
        
        self.path_builder = PathReconstructor()
    
    def find_optimal_route(self, start: int, destination: int, 
                          initial_fuel: float) -> List[int]:
        
        if not self.is_valid:
            return []
        
        if start not in self.graph:
            return []
        
        if start == destination:
            required_inspections = set(self.inspections) if self.inspections else set()
            
            if not required_inspections:
                return [start]
            
            if start in required_inspections and len(required_inspections) == 1:
                return [start]
            
            return []
        
        if initial_fuel < 0:
            initial_fuel = 0.0
        
        initial_fuel = min(initial_fuel, self.vehicle_capacity)
        
        pq = PriorityQueue()
        initial_state = self.explorer.get_initial_state(start, initial_fuel)
        
        pq.push(0.0, (0.0, initial_state))
        self.explorer.mark_state_visited(initial_state, 0.0)
        self.path_builder.record_parent(initial_state, None)
        
        iterations = 0
        max_iterations = 100000
        
        best_destination_state = None
        best_distance = float('inf')
        
        while not pq.is_empty() and iterations < max_iterations:
            iterations += 1
            
            item = pq.pop()
            if item is None:
                break
            
            current_distance, current_state = item
            
            if current_distance > best_distance + 1e-6:
                continue
            
            if self.validator.is_valid_destination_state(current_state, destination):
                if current_distance < best_distance - 1e-6:
                    best_distance = current_distance
                    best_destination_state = current_state
                continue
            
            next_states = self.explorer.generate_next_states(current_state)
            
            for edge_cost, next_state in next_states:
                new_distance = current_distance + edge_cost
                
                if new_distance > best_distance + 1e-6:
                    continue
                
                if self.explorer.should_update_state(next_state, new_distance):
                    self.explorer.mark_state_visited(next_state, new_distance)
                    self.path_builder.record_parent(next_state, current_state)
                    pq.push(new_distance, (new_distance, next_state))
        
        if best_destination_state is not None:
            return self.path_builder.reconstruct_path(best_destination_state)
        
        return []


def optimize_delivery_route(
    graph: Dict[str, List[List[float]]],
    fuel_stations: List[int],
    vehicle_capacity: float,
    fuel_consumption: float,
    start: int,
    destination: int,
    inspections: List[int]
) -> List[int]:
    
    if graph is None or not isinstance(graph, dict):
        return []
    
    if not graph:
        return []
    
    if vehicle_capacity <= 0 or fuel_consumption <= 0:
        return []
    
    if start is None or destination is None:
        return []
    
    if fuel_stations is None:
        fuel_stations = []
    
    if inspections is None:
        inspections = []
        
    graph = {int(k): v for k, v in graph.items()}
    
    fuel_stations_config = {}
    for station_city in fuel_stations:
        fuel_stations_config[station_city] = {
            'availability_windows': [(0.0, float('inf'))],
            'refuel_time': 5.0
        }
    
    planner = AdaptiveRoutePlanner(
        graph, fuel_stations_config, vehicle_capacity, 
        fuel_consumption, inspections, enable_partial_refuel=True)
    
    if not planner.is_valid:
        return []
    
    initial_fuel = vehicle_capacity
    
    return planner.find_optimal_route(start, destination, initial_fuel)


if __name__ == "__main__":
    graph = {
        "0": [[1, 12.5], [2, 25.0]],
        "1": [[3, 10.0], [4, 15.0]],
        "2": [[5, 18.0]],
        "3": [[6, 22.0]],
        "4": [[6, 5.0]],
        "5": [[6, 30.0]],
        "6": []
    }
    fuel_stations = [0, 1, 2, 4]
    vehicle_capacity = 40.0
    fuel_consumption = 1.0
    start = 0
    destination = 6
    inspections = [4]
    
    result = optimize_delivery_route(
        graph, fuel_stations, vehicle_capacity, 
        fuel_consumption, start, destination, inspections)
    print(f"Route: {result}")