from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict, deque
import copy

def optimize_water_distribution(source_nodes: List[Dict], pipe_segments: List[Dict], 
                               demand_zones: List[Dict], reservoir_nodes: List[Dict]) -> Dict[str, Any]:    
    if not demand_zones:
        return {"error": "No demand zones provided"}
    
    all_node_ids = set()
    
    for source in source_nodes:
        if source['source_id'] < 0 or source['source_id'] > 49:
            return {"error": "Input is not valid"}
        if len(source['location_coordinates']) != 2:
            return {"error": "Input is not valid"}
        x, y = source['location_coordinates']
        if x < 0 or x > 2000 or y < 0 or y > 2000:
            return {"error": f"Invalid coordinates for source {source['source_id']}"}
        if source['max_output_capacity'] < 1000 or source['max_output_capacity'] > 10000:
            return {"error": "Input is not valid"}
        if source['current_production_rate'] < 500 or source['current_production_rate'] > 9000:
            return {"error": "Input is not valid"}
        if source['current_production_rate'] > source['max_output_capacity']:
            return {"error": f"Source production exceeds maximum capacity for source {source['source_id']}"}
        if source['source_type'] not in ["primary", "secondary", "emergency", "backup"]:
            return {"error": "Input is not valid"}
        if source['operational_cost'] < 0.01 or source['operational_cost'] > 0.50:
            return {"error": "Input is not valid"}
        all_node_ids.add(source['source_id'])
    
    for reservoir in reservoir_nodes:
        if reservoir['reservoir_id'] < 0 or reservoir['reservoir_id'] > 99:
            return {"error": "Input is not valid"}
        if reservoir['current_water_level'] < 100 or reservoir['current_water_level'] > 10000:
            return {"error": "Input is not valid"}
        if reservoir['max_storage_capacity'] < 1000 or reservoir['max_storage_capacity'] > 50000:
            return {"error": "Input is not valid"}
        if reservoir['overflow_threshold'] < 900 or reservoir['overflow_threshold'] > 45000:
            return {"error": "Input is not valid"}
        if reservoir['current_water_level'] > reservoir['overflow_threshold']:
            return {"error": f"Reservoir {reservoir['reservoir_id']} exceeds overflow threshold"}
        if reservoir['inlet_capacity'] < 500 or reservoir['inlet_capacity'] > 8000:
            return {"error": "Input is not valid"}
        if reservoir['outlet_capacity'] < 400 or reservoir['outlet_capacity'] > 7000:
            return {"error": "Input is not valid"}
        all_node_ids.add(reservoir['node_id'])
    
    for zone in demand_zones:
        if zone['zone_id'] < 0 or zone['zone_id'] > 199:
            return {"error": "Input is not valid"}
        if zone['priority_level'] < 1 or zone['priority_level'] > 5:
            return {"error": f"Invalid priority level for zone {zone['zone_id']}"}
        if zone['minimum_flow_requirement'] < 50 or zone['minimum_flow_requirement'] > 2000:
            return {"error": "Input is not valid"}
        if zone['target_flow_requirement'] < 100 or zone['target_flow_requirement'] > 3000:
            return {"error": "Input is not valid"}
        if zone['minimum_flow_requirement'] > zone['target_flow_requirement']:
            return {"error": f"Invalid flow requirements for zone {zone['zone_id']}"}
        if zone['zone_type'] not in ["residential", "commercial", "industrial", "hospital", "school"]:
            return {"error": "Input is not valid"}
        if zone['population_served'] < 100 or zone['population_served'] > 50000:
            return {"error": "Input is not valid"}
        all_node_ids.add(zone['node_id'])
    
    for pipe in pipe_segments:
        if pipe['pipe_id'] < 0 or pipe['pipe_id'] > 999:
            return {"error": "Input is not valid"}
        if pipe['start_node_id'] not in all_node_ids:
            return {"error": f"Invalid node reference in pipe {pipe['pipe_id']}"}
        if pipe['end_node_id'] not in all_node_ids:
            return {"error": f"Invalid node reference in pipe {pipe['pipe_id']}"}
        if pipe['max_flow_capacity'] < 100 or pipe['max_flow_capacity'] > 5000:
            return {"error": "Input is not valid"}
        if pipe['current_flow_rate'] < 0 or pipe['current_flow_rate'] > 4500:
            return {"error": "Input is not valid"}
        if pipe['current_flow_rate'] > pipe['max_flow_capacity']:
            return {"error": f"Current flow exceeds pipe capacity for pipe {pipe['pipe_id']}"}
        if pipe['pipe_diameter'] < 50 or pipe['pipe_diameter'] > 500:
            return {"error": "Input is not valid"}
        if pipe['maintenance_status'] not in ["active", "maintenance", "degraded", "critical"]:
            return {"error": f"Invalid maintenance status for pipe {pipe['pipe_id']}"}
        if pipe['installation_year'] < 1950 or pipe['installation_year'] > 2023:
            return {"error": "Input is not valid"}
    
    graph = defaultdict(list)
    pipe_map = {}
    
    for pipe in pipe_segments:
        graph[pipe['start_node_id']].append({
            'target': pipe['end_node_id'],
            'pipe_id': pipe['pipe_id'],
            'pipe': pipe
        })
        pipe_map[pipe['pipe_id']] = pipe
    
    zone_nodes = {zone['node_id'] for zone in demand_zones}
    source_node_ids = {source['source_id'] for source in source_nodes}
    
    for zone_node in zone_nodes:
        reachable = False
        for source_id in source_node_ids:
            if is_reachable(graph, source_id, zone_node, pipe_segments):
                reachable = True
                break
        if not reachable:
            return {"error": "Network contains unreachable demand zones"}
    
    working_pipe_segments = copy.deepcopy(pipe_segments)
    
    cycles_info = detect_cycles(graph, all_node_ids)
    
    if cycles_info['cycles_detected'] > 0:
        redistributed_flow = redistribute_cycle_flow(graph, cycles_info['cycle_paths'], working_pipe_segments)
        cycles_info['redistributed_flow'] = redistributed_flow
    else:
        cycles_info['redistributed_flow'] = 0
    
    sorted_zones = sorted(demand_zones, key=lambda x: (x['priority_level'], x['zone_id']))
    
    flow_optimizer = FordFulkersonMinFlowOptimizer(source_nodes, working_pipe_segments, reservoir_nodes)
    optimized_flows, zone_satisfaction, updated_reservoirs = flow_optimizer.optimize_minimum_flow_allocation(sorted_zones, graph, pipe_map)
    
    flow_conservation_valid = validate_flow_conservation(graph, optimized_flows, source_nodes, zone_satisfaction, updated_reservoirs)
    if not flow_conservation_valid:
        return {"error": "Flow conservation constraint violated at intermediate nodes"}
    
    flow_allocation = {}
    for pipe in pipe_segments:
        allocated_flow = optimized_flows.get(pipe['pipe_id'], 0)
        effective_cap = calculate_effective_capacity(pipe, allocated_flow)
        utilization = (allocated_flow / pipe['max_flow_capacity']) * 100 if pipe['max_flow_capacity'] > 0 else 0
        
        flow_allocation[pipe['pipe_id']] = {
            'allocated_flow_rate': allocated_flow,
            'utilization_percentage': round(utilization, 1),
            'effective_capacity': effective_cap,
            'pressure_status': get_pressure_status(allocated_flow, pipe['max_flow_capacity'])
        }
    
    reservoir_status = []
    for reservoir in updated_reservoirs:
        utilization_rate = round(reservoir['current_water_level'] / reservoir['max_storage_capacity'], 2)
        overflow_risk = reservoir['current_water_level'] > reservoir['overflow_threshold'] * 0.9
        
        reservoir_status.append({
            'reservoir_id': reservoir['reservoir_id'],
            'final_water_level': reservoir['current_water_level'],
            'overflow_risk': overflow_risk,
            'utilization_rate': utilization_rate
        })
    
    total_flow_delivered = sum(zone['flow_delivered'] for zone in zone_satisfaction)
    
    total_available_capacity = 0
    for source in source_nodes:
        source_id = source['source_id']
        for edge in graph[source_id]:
            pipe = pipe_map[edge['pipe_id']]
            if pipe['maintenance_status'] == 'active':
                total_available_capacity += pipe['max_flow_capacity']
    
    priority_satisfaction_bonus = 0
    zone_lookup = {zone['zone_id']: zone for zone in demand_zones}
    for zone_result in zone_satisfaction:
        zone_id = zone_result['zone_id']
        original_zone = zone_lookup[zone_id]
        priority_satisfaction_bonus += zone_result['flow_delivered'] * (6 - original_zone['priority_level']) * 10
    
    cycle_penalty = cycles_info['cycles_detected'] * 50
    
    network_efficiency_score = round(
        (total_flow_delivered / total_available_capacity) * 100 + 
        priority_satisfaction_bonus - cycle_penalty, 1
    )
    
    total_production_cost = round(sum(
        source['current_production_rate'] * source['operational_cost'] 
        for source in source_nodes
    ), 1)
    
    bottleneck_pipes = [
        pipe_id for pipe_id, allocation in flow_allocation.items()
        if allocation['utilization_percentage'] > 95
    ]
    
    underutilized_capacity = sum(
        pipe['max_flow_capacity'] - optimized_flows.get(pipe['pipe_id'], 0)
        for pipe in pipe_segments
        if (optimized_flows.get(pipe['pipe_id'], 0) / pipe['max_flow_capacity']) < 0.5
    )
    
    return {
        "optimal_flow_allocation": [
            {
                "pipe_id": pipe_id,
                "allocated_flow_rate": allocation['allocated_flow_rate'],
                "utilization_percentage": allocation['utilization_percentage'],
                "effective_capacity": allocation['effective_capacity'],
                "pressure_status": allocation['pressure_status']
            }
            for pipe_id, allocation in sorted(flow_allocation.items())
        ],
        "zone_satisfaction": zone_satisfaction,
        "network_efficiency_score": network_efficiency_score,
        "cycle_analysis": cycles_info,
        "reservoir_status": reservoir_status,
        "system_metrics": {
            "total_flow_delivered": total_flow_delivered,
            "total_production_cost": total_production_cost,
            "bottleneck_pipes": sorted(bottleneck_pipes),
            "underutilized_capacity": underutilized_capacity
        }
    }


class FordFulkersonMinFlowOptimizer:
    def __init__(self, sources: List[Dict], pipes: List[Dict], reservoirs: List[Dict]):
        self.sources = sources
        self.pipes = pipes
        self.reservoirs = copy.deepcopy(reservoirs)
        self.source_nodes = {s['source_id'] for s in sources}
        self.reservoir_nodes = {r['node_id']: r for r in self.reservoirs}
        self.pipe_flows = {pipe['pipe_id']: 0 for pipe in pipes}
    
    def optimize_minimum_flow_allocation(self, sorted_zones: List[Dict], graph: Dict, pipe_map: Dict) -> Tuple[Dict[int, int], List[Dict], List[Dict]]:
        zone_satisfaction = []
        
        for zone in sorted_zones:
            zone_node = zone['node_id']
            target_flow = zone['target_flow_requirement']
            min_flow = zone['minimum_flow_requirement']
            
            delivered_flow = self.ford_fulkerson_minimum_flow(graph, pipe_map, zone_node, target_flow)
            
            satisfaction_percentage = round((delivered_flow / target_flow) * 100, 1)
            priority_met = delivered_flow >= min_flow
            
            zone_satisfaction.append({
                'zone_id': zone['zone_id'],
                'flow_delivered': delivered_flow,
                'satisfaction_percentage': satisfaction_percentage,
                'priority_met': priority_met
            })
        
        return self.pipe_flows, zone_satisfaction, self.reservoirs
    
    def ford_fulkerson_minimum_flow(self, graph: Dict, pipe_map: Dict, sink: int, target_flow: int) -> int:
        flow_network = self.build_residual_network(graph, pipe_map)
        total_flow = 0
        
        while total_flow < target_flow:
            path, min_capacity = self.find_augmenting_path(flow_network, sink)
            if not path or min_capacity == 0:
                break
            
            actual_flow = min(min_capacity, target_flow - total_flow)
            self.update_flows_along_path(path, actual_flow, graph)
            self.update_residual_network(flow_network, path, actual_flow)
            
            total_flow += actual_flow
        
        return total_flow
    
    def build_residual_network(self, graph: Dict, pipe_map: Dict) -> Dict[int, Dict[int, int]]:
        network = defaultdict(lambda: defaultdict(int))
        
        for start_node, edges in graph.items():
            for edge in edges:
                end_node = edge['target']
                pipe_id = edge['pipe_id']
                pipe = pipe_map[pipe_id]
                
                if pipe['maintenance_status'] == 'active':
                    current_flow = self.pipe_flows[pipe_id]
                    effective_capacity = self.calculate_dynamic_effective_capacity_with_pressure_drop(pipe, current_flow)
                    
                    reservoir_limit = self.get_reservoir_flow_limit(end_node, current_flow)
                    available_capacity = min(effective_capacity - current_flow, reservoir_limit)
                    
                    if available_capacity > 0:
                        network[start_node][end_node] = available_capacity
        
        return network
    
    def calculate_dynamic_effective_capacity_with_pressure_drop(self, pipe: Dict, current_flow: int) -> int:
        base_capacity = pipe['max_flow_capacity']
        utilization_rate = current_flow / base_capacity if base_capacity > 0 else 0
        
        if utilization_rate > 0.9:
            effective_capacity = int(base_capacity * 0.8)
        elif utilization_rate > 0.8:
            effective_capacity = int(base_capacity * 0.9)
        else:
            effective_capacity = base_capacity
        
        if pipe['maintenance_status'] == "maintenance":
            effective_capacity = int(effective_capacity * 0.7)
        elif pipe['maintenance_status'] == "degraded":
            effective_capacity = int(effective_capacity * 0.5)
        
        return effective_capacity
    
    def get_reservoir_flow_limit(self, node_id: int, additional_flow: int) -> int:
        if node_id not in self.reservoir_nodes:
            return float('inf')
        
        reservoir = self.reservoir_nodes[node_id]
        
        remaining_capacity = reservoir['overflow_threshold'] - reservoir['current_water_level']
        if remaining_capacity <= 0:
            alternative_reservoir = self.find_alternative_reservoir()
            if alternative_reservoir:
                return alternative_reservoir['inlet_capacity']
            return 0
        
        max_inflow = min(remaining_capacity, reservoir['inlet_capacity'])
        return max(0, max_inflow - additional_flow)
    
    def find_alternative_reservoir(self) -> Dict:
        for reservoir in self.reservoirs:
            remaining_capacity = reservoir['overflow_threshold'] - reservoir['current_water_level']
            if remaining_capacity > reservoir['inlet_capacity'] * 0.1:
                return reservoir
        return None
    
    def find_augmenting_path(self, network: Dict, sink: int) -> Tuple[List[int], int]:
        visited = set()
        queue = deque()
        
        for source_id in self.source_nodes:
            queue.append((source_id, [source_id], float('inf')))
            visited.add(source_id)
        
        while queue:
            current, path, min_capacity = queue.popleft()
            
            if current == sink:
                return path, min_capacity
            
            neighbors = sorted(network[current].items(), key=lambda x: x[1])
            
            for neighbor, capacity in neighbors:
                if neighbor not in visited and capacity > 0:
                    visited.add(neighbor)
                    new_capacity = min(min_capacity, capacity)
                    queue.append((neighbor, path + [neighbor], new_capacity))
        
        return [], 0
    
    def update_flows_along_path(self, path: List[int], flow: int, graph: Dict):
        reservoir_flow_changes = defaultdict(int)
        
        for i in range(len(path) - 1):
            start_node, end_node = path[i], path[i + 1]
            
            for edge in graph[start_node]:
                if edge['target'] == end_node:
                    pipe_id = edge['pipe_id']
                    self.pipe_flows[pipe_id] += flow
                    
                    # Track reservoir inflows
                    if end_node in self.reservoir_nodes:
                        reservoir_flow_changes[end_node] += flow
                    
                    # Track reservoir outflows  
                    if start_node in self.reservoir_nodes:
                        reservoir_flow_changes[start_node] -= flow
                    break
        
        # Update reservoir water levels based on net flow
        for reservoir_node, net_flow in reservoir_flow_changes.items():
            if net_flow != 0:
                volume_change = net_flow / 1000 
                self.reservoir_nodes[reservoir_node]['current_water_level'] += int(volume_change)
    
    def update_residual_network(self, network: Dict, path: List[int], flow: int):
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            network[u][v] -= flow
            network[v][u] += flow


def validate_flow_conservation(graph: Dict, flows: Dict[int, int], sources: List[Dict], 
                             zones: List[Dict], reservoirs: List[Dict]) -> bool:
    source_ids = {s['source_id'] for s in sources}
    zone_nodes = {z['zone_id'] for z in zones}
    reservoir_nodes = {r['node_id'] for r in reservoirs}
    
    intermediate_nodes = reservoir_nodes - source_ids
    
    for node in intermediate_nodes:
        inflow = 0
        outflow = 0
        
        for start_node, edges in graph.items():
            for edge in edges:
                pipe_id = edge['pipe_id']
                flow = flows.get(pipe_id, 0)
                
                if edge['target'] == node:
                    inflow += flow
                elif start_node == node:
                    outflow += flow
        
        if abs(inflow - outflow) > 1:
            return False
    
    return True


def is_reachable(graph: Dict, start: int, target: int, pipe_segments: List[Dict]) -> bool:
    visited = set()
    queue = deque([start])
    visited.add(start)
    
    pipe_lookup = {pipe['pipe_id']: pipe for pipe in pipe_segments}
    
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        
        for edge in graph[current]:
            next_node = edge['target']
            pipe_id = edge['pipe_id']
            
            if pipe_id in pipe_lookup:
                pipe = pipe_lookup[pipe_id]
                
                if (next_node not in visited and 
                    pipe['maintenance_status'] == "active" and
                    pipe['max_flow_capacity'] > 0):
                    visited.add(next_node)
                    queue.append(next_node)
    
    return False


def calculate_effective_capacity(pipe: Dict, current_flow: int) -> int:
    base_capacity = pipe['max_flow_capacity']
    utilization_rate = current_flow / base_capacity if base_capacity > 0 else 0
    
    if utilization_rate > 0.9:
        effective_capacity = int(base_capacity * 0.8)
    elif utilization_rate > 0.8:
        effective_capacity = int(base_capacity * 0.9)
    else:
        effective_capacity = base_capacity
    
    if pipe['maintenance_status'] == "maintenance":
        effective_capacity = int(effective_capacity * 0.7)
    elif pipe['maintenance_status'] == "degraded":
        effective_capacity = int(effective_capacity * 0.5)
    
    return effective_capacity


def detect_cycles(graph: Dict, all_nodes: Set[int]) -> Dict[str, Any]:
    visited = set()
    rec_stack = set()
    cycles = []
    
    def dfs(node: int, path: List[int]) -> bool:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for edge in graph[node]:
            neighbor = edge['target']
            
            if neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                if len(cycle) > 2:
                    cycles.append(cycle)
                return True
            elif neighbor not in visited:
                if dfs(neighbor, path.copy()):
                    return True
        
        rec_stack.remove(node)
        return False
    
    for node in all_nodes:
        if node not in visited:
            dfs(node, [])
    
    unique_cycles = []
    for cycle in cycles:
        normalized_cycle = normalize_cycle(cycle)
        if normalized_cycle not in unique_cycles:
            unique_cycles.append(normalized_cycle)
    
    return {
        'cycles_detected': len(unique_cycles),
        'cycle_paths': unique_cycles[:10],
        'redistributed_flow': 0
    }


def normalize_cycle(cycle: List[int]) -> List[int]:
    if not cycle:
        return cycle
    min_idx = cycle.index(min(cycle))
    return cycle[min_idx:] + cycle[:min_idx]


def redistribute_cycle_flow(graph: Dict, cycle_paths: List[List[int]], 
                          pipe_segments: List[Dict]) -> int:
    total_redistributed = 0
    pipe_lookup = {(p['start_node_id'], p['end_node_id']): p for p in pipe_segments}
    
    for cycle in cycle_paths:
        if len(cycle) < 3:
            continue
        
        min_flow = float('inf')
        cycle_pipes = []
        
        for i in range(len(cycle) - 1):
            start_node = cycle[i]
            end_node = cycle[i + 1]
            
            pipe_key = (start_node, end_node)
            if pipe_key in pipe_lookup:
                pipe = pipe_lookup[pipe_key]
                min_flow = min(min_flow, pipe['current_flow_rate'])
                cycle_pipes.append(pipe)
        
        if min_flow != float('inf') and min_flow > 0:
            reduction = int(min_flow * 0.2)
            total_redistributed += reduction
            
            for pipe in cycle_pipes:
                pipe['current_flow_rate'] = max(0, pipe['current_flow_rate'] - reduction)
            
            find_alternative_paths_with_capacity(graph, cycle_pipes, reduction, pipe_segments)
    
    return total_redistributed


def find_alternative_paths_with_capacity(graph: Dict, cycle_pipes: List[Dict], 
                                       redistributed_flow: int, all_pipes: List[Dict]):
    pipe_lookup = {pipe['pipe_id']: pipe for pipe in all_pipes}
    available_pipes = []
    cycle_pipe_ids = {pipe['pipe_id'] for pipe in cycle_pipes}
    
    for _, edges in graph.items():
        for edge in edges:
            pipe_id = edge['pipe_id']
            pipe = pipe_lookup.get(pipe_id)
            
            if (pipe and 
                pipe_id not in cycle_pipe_ids and
                pipe['maintenance_status'] == 'active' and
                pipe['current_flow_rate'] < pipe['max_flow_capacity'] * 0.8):
                available_pipes.append(pipe)
    
    seen_pipe_ids = set()
    unique_available_pipes = []
    for pipe in available_pipes:
        if pipe['pipe_id'] not in seen_pipe_ids:
            unique_available_pipes.append(pipe)
            seen_pipe_ids.add(pipe['pipe_id'])
    
    if unique_available_pipes:
        flow_per_pipe = redistributed_flow // len(unique_available_pipes)
        remaining_flow = redistributed_flow % len(unique_available_pipes)
        
        for i, pipe in enumerate(unique_available_pipes):
            additional_capacity = pipe['max_flow_capacity'] - pipe['current_flow_rate']
            allocation = flow_per_pipe + (1 if i < remaining_flow else 0)
            actual_allocation = min(allocation, additional_capacity)
            
            if actual_allocation > 0:
                pipe['current_flow_rate'] += actual_allocation


def get_pressure_status(current_flow: int, max_capacity: int) -> str:
    if max_capacity == 0:
        return "critical"
    
    utilization = current_flow / max_capacity
    
    if utilization <= 0.8:
        return "normal"
    elif utilization <= 0.9:
        return "reduced"
    else:
        return "critical"


if __name__ == "__main__":
    source_nodes = [
        {"source_id": 0, "location_coordinates": [500, 1000], "max_output_capacity": 5000, "current_production_rate": 4000, "source_type": "primary", "operational_cost": 0.15},
        {"source_id": 1, "location_coordinates": [1500, 800], "max_output_capacity": 3000, "current_production_rate": 2500, "source_type": "secondary", "operational_cost": 0.20}
    ]

    pipe_segments = [
        {"pipe_id": 0, "start_node_id": 0, "end_node_id": 2, "max_flow_capacity": 2000, "current_flow_rate": 1500, "pipe_diameter": 300, "maintenance_status": "active", "installation_year": 2010},
        {"pipe_id": 1, "start_node_id": 1, "end_node_id": 3, "max_flow_capacity": 1500, "current_flow_rate": 1200, "pipe_diameter": 250, "maintenance_status": "active", "installation_year": 2015},
        {"pipe_id": 2, "start_node_id": 2, "end_node_id": 4, "max_flow_capacity": 1000, "current_flow_rate": 800, "pipe_diameter": 200, "maintenance_status": "active", "installation_year": 2018},
        {"pipe_id": 3, "start_node_id": 3, "end_node_id": 5, "max_flow_capacity": 800, "current_flow_rate": 600, "pipe_diameter": 180, "maintenance_status": "active", "installation_year": 2020}
    ]

    demand_zones = [
        {"zone_id": 0, "node_id": 4, "priority_level": 1, "minimum_flow_requirement": 400, "target_flow_requirement": 800, "zone_type": "hospital", "population_served": 5000},
        {"zone_id": 1, "node_id": 5, "priority_level": 2, "minimum_flow_requirement": 300, "target_flow_requirement": 600, "zone_type": "residential", "population_served": 12000}
    ]

    reservoir_nodes = [
        {"reservoir_id": 0, "node_id": 2, "current_water_level": 5000, "max_storage_capacity": 20000, "overflow_threshold": 18000, "inlet_capacity": 3000, "outlet_capacity": 2500},
        {"reservoir_id": 1, "node_id": 3, "current_water_level": 3000, "max_storage_capacity": 15000, "overflow_threshold": 13500, "inlet_capacity": 2000, "outlet_capacity": 1800}
    ]

    result = optimize_water_distribution(source_nodes, pipe_segments, demand_zones, reservoir_nodes)
    print(result)