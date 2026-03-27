from typing import List, Dict, Any

def optimize_supply_chain_routes(distribution_centers: List[Dict], destinations: List[Dict], 
                               cost_matrix: List[List[float]], time_windows: List) -> Dict[str, Any]:
    """
    Optimizes supply chain routes using advanced greedy algorithm.
    
    Returns: Dictionary with route assignments and total cost
    """
        
    if not destinations:
        return {"error":"Empty destination list provided"}

    for dc in distribution_centers:
        if dc['capacity'] < 50 or dc['capacity'] > 500:
            return {"error" : "Input is not valid"}
        if dc['base_cost'] < 0.5 or dc['base_cost'] > 5.0:
            return {"error" : "Input is not valid"}
        if dc['efficiency_factor'] < 0.5 or dc['efficiency_factor'] > 1.5:
            return {"error" : "Input is not valid"}
    
    for dest in destinations:
        if dest['demand'] < 1 or dest['demand'] > 100:
            return {"error" : "Input is not valid"}
        if dest['priority_level'] < 1 or dest['priority_level'] > 5:
            return {"error" : "Input is not valid"}
    
    for i, (earliest, latest) in enumerate(time_windows):
        if earliest < 0 or latest > 168:
            return {"error" : "Input is not valid"}
        if earliest >= latest:
            return {"error" : f"Invalid time window for destination {destinations[i]['id']}"}
    
    if len(cost_matrix) != len(distribution_centers):
        return {"error" :"Invalid cost matrix dimensions" }
    
    for row in cost_matrix:
        if len(row) != len(destinations):
            return {"error" :"Invalid cost matrix dimensions" }
        for cost in row:
            if cost < 0:
                return {"error" : "Negative cost detected in cost matrix"}
            if cost < 10.0 or cost > 50.0:
                return {"error" : "Input is not valid"}
    
    if len(time_windows) != len(destinations):
        return {"error" :"Invalid cost matrix dimensions" }

    max_time_span = 0
    for earliest, latest in time_windows:
        span = latest - earliest
        if span > max_time_span:
            max_time_span = span

    urgency_multiplier = 0.75 * max_time_span

    dc_id_to_idx = {dc['id']: i for i, dc in enumerate(distribution_centers)}
    dest_id_to_idx = {dest['id']: i for i, dest in enumerate(destinations)}

    remaining_capacity = {}
    for dc in distribution_centers:
        remaining_capacity[dc['id']] = dc['capacity']
    
    assigned_destinations = set()
    assignments = []
    total_system_cost = 0.0
    
    dest_priority_map = {}
    for dest in destinations:
        dest_priority_map[dest['id']] = dest['priority_level']
    
    while len(assigned_destinations) < len(destinations):

        best_assignment = None
        best_dc_id = None
        best_dest_id = None
        
        all_possible_assignments = []
        
        for dest in destinations:
            if dest['id'] in assigned_destinations:
                continue
            
            dest_idx = dest_id_to_idx[dest['id']]
            
            for dc in distribution_centers:
                dc_idx = dc_id_to_idx[dc['id']]
                
                if remaining_capacity[dc['id']] < dest['demand']:
                    continue
                
                transportation_cost = cost_matrix[dc_idx][dest_idx]
                operational_cost = dc['base_cost'] * dest['demand'] * dc['efficiency_factor']
                total_route_cost = transportation_cost + operational_cost
                
                urgency_weight = urgency_multiplier / (dest['priority_level'] * 10.0)
                weighted_cost = total_route_cost - urgency_weight
                
                earliest, latest = time_windows[dest_idx]
                scheduled_time = (earliest + latest) // 2
                
                all_possible_assignments.append({
                    'dc_id': dc['id'],
                    'dest_id': dest['id'],
                    'dc_idx': dc_idx,
                    'dest_idx': dest_idx,
                    'transportation_cost': transportation_cost,
                    'operational_cost': operational_cost,
                    'total_route_cost': total_route_cost,
                    'weighted_cost': weighted_cost,
                    'scheduled_time': scheduled_time,
                    'priority': dest['priority_level']
                })
        
        all_possible_assignments.sort(key=lambda x: (x['weighted_cost'], x['priority']))
        
        if all_possible_assignments:
            selected = all_possible_assignments[0]
            best_assignment = {
                "distribution_center_id": selected['dc_id'],
                "destination_id": selected['dest_id'],
                "transportation_cost": selected['transportation_cost'],
                "operational_cost": selected['operational_cost'],
                "total_route_cost": selected['total_route_cost'],
                "scheduled_delivery_time": selected['scheduled_time']
            }
            best_dc_id = selected['dc_id']
            best_dest_id = selected['dest_id']
        
        if best_assignment is None:
            break
        
        demand_for_dest = None
        for dest in destinations:
            if dest['id'] == best_dest_id:
                demand_for_dest = dest['demand']
                break
        
        if demand_for_dest and remaining_capacity[best_dc_id] < demand_for_dest:
            return {"error" : f"Capacity exceeded for distribution center {best_dc_id}" }
        
        assignments.append(best_assignment)
        assigned_destinations.add(best_dest_id)
        
        for dest in destinations:
            if dest['id'] == best_dest_id:
                remaining_capacity[best_dc_id] -= dest['demand']
                break
        
        total_system_cost += best_assignment['total_route_cost']
    
    unassigned_destinations = []
    for dest in destinations:
        if dest['id'] not in assigned_destinations:
            unassigned_destinations.append(dest['id'])
    
    return {
        "assignments": assignments,
        "total_system_cost": round(total_system_cost, 1),
        "unassigned_destinations": unassigned_destinations
    }

if __name__ == "__main__":
    distribution_centers = [
        {"id": 0, "capacity": 150, "base_cost": 2.0, "efficiency_factor": 1.2},
        {"id": 1, "capacity": 200, "base_cost": 1.8, "efficiency_factor": 1.0},
        {"id": 2, "capacity": 180, "base_cost": 2.2, "efficiency_factor": 1.1}
    ]

    destinations = [
        {"id": 0, "demand": 50, "priority_level": 1},
        {"id": 1, "demand": 75, "priority_level": 2},
        {"id": 2, "demand": 60, "priority_level": 1},
        {"id": 3, "demand": 40, "priority_level": 3}
    ]

    cost_matrix = [
        [25.5, 30.0, 35.2, 28.0],
        [32.0, 22.5, 40.0, 35.5],
        [28.5, 35.0, 20.0, 30.0]
    ]

    time_windows = [[0, 24], [12, 36], [24, 48], [0, 72]]

    result = optimize_supply_chain_routes(distribution_centers, destinations, cost_matrix, time_windows)
    print(result)