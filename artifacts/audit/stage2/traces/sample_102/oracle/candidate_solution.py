from typing import List, Dict, Any
from collections import defaultdict, deque
import math

def optimize_truck_route_matching(trucks: List[Dict], routes: List[Dict], 
                                dependencies: List[Dict], operational_constraints: Dict) -> Dict[str, Any]:
    """
    Optimizes truck-to-route assignments using Dependent Matching algorithm.
    Returns: Dictionary with optimal assignments and efficiency metrics
    """
    
    # Input validation
    if not trucks:
        return {"error": "No trucks provided"}
    
    if not routes:
        return {"error": "Input is not valid"}
    
    # Validate trucks
    for truck in trucks:
        if truck['truck_id'] < 0 or truck['truck_id'] > 199:
            return {"error": "Input is not valid"}
        
        if truck['capacity'] < 100 or truck['capacity'] > 2000:
            return {"error": f"Invalid truck capacity for truck {truck['truck_id']}"}
        
        if truck['operational_hours'] < 8 or truck['operational_hours'] > 16:
            return {"error": f"Invalid operational hours for truck {truck['truck_id']}"}
        
        if truck['base_cost_per_hour'] < 50 or truck['base_cost_per_hour'] > 200:
            return {"error": "Input is not valid"}
        
        if truck['maintenance_window']['start_hour'] < 0 or truck['maintenance_window']['start_hour'] > 23:
            return {"error": "Input is not valid"}
        
        if truck['maintenance_window']['end_hour'] < 0 or truck['maintenance_window']['end_hour'] > 23:
            return {"error": "Input is not valid"}
        
        if truck['truck_type'] not in ["light", "medium", "heavy", "specialized"]:
            return {"error": "Input is not valid"}
        
        if (truck['current_location']['x'] < 0 or truck['current_location']['x'] > 1000 or
            truck['current_location']['y'] < 0 or truck['current_location']['y'] > 1000):
            return {"error": f"Invalid coordinates for truck {truck['truck_id']}"}
    
    # Validate routes
    route_ids = set()
    max_truck_capacity = max(truck['capacity'] for truck in trucks)
    
    for route in routes:
        if route['route_id'] < 0 or route['route_id'] > 999:
            return {"error": "Input is not valid"}
        
        route_ids.add(route['route_id'])
        
        if route['load_requirement'] < 50 or route['load_requirement'] > 1500:
            return {"error": "Input is not valid"}
        
        if route['load_requirement'] > max_truck_capacity:
            return {"error": f"Invalid route load requirement for route {route['route_id']}"}
        
        if route['estimated_duration'] < 2 or route['estimated_duration'] > 12:
            return {"error": "Input is not valid"}
        
        if route['priority_level'] < 1 or route['priority_level'] > 5:
            return {"error": f"Invalid priority level for route {route['route_id']}"}
        
        if route['start_time_window'] < 0 or route['start_time_window'] > 23:
            return {"error": "Input is not valid"}
        
        if route['end_time_window'] < 0 or route['end_time_window'] > 23:
            return {"error": "Input is not valid"}
        
        if route['start_time_window'] >= route['end_time_window']:
            return {"error": f"Invalid time window for route {route['route_id']}"}
        
        if route['base_assignment_cost'] < 100 or route['base_assignment_cost'] > 1000:
            return {"error": "Input is not valid"}
        
        if route['route_complexity'] < 1.0 or route['route_complexity'] > 3.0:
            return {"error": "Input is not valid"}
        
        if (route['destination_coordinates']['x'] < 0 or route['destination_coordinates']['x'] > 1000 or
            route['destination_coordinates']['y'] < 0 or route['destination_coordinates']['y'] > 1000):
            return {"error": "Input is not valid"}
    
    # Validate dependencies
    for dependency in dependencies:
        if dependency['dependency_id'] < 0 or dependency['dependency_id'] > 499:
            return {"error": "Input is not valid"}
        
        if dependency['prerequisite_route_id'] not in route_ids:
            return {"error": f"Invalid route reference in dependency {dependency['dependency_id']}"}
        
        if dependency['dependent_route_id'] not in route_ids:
            return {"error": f"Invalid route reference in dependency {dependency['dependency_id']}"}
        
        if dependency['dependency_type'] not in ["sequential", "resource", "location", "regulatory"]:
            return {"error": "Input is not valid"}
        
        if dependency['minimum_gap_hours'] < 0 or dependency['minimum_gap_hours'] > 8:
            return {"error": "Input is not valid"}
    
    # Validate operational constraints
    if (operational_constraints['max_routes_per_truck'] < 1 or 
        operational_constraints['max_routes_per_truck'] > 10):
        return {"error": "Input is not valid"}
    
    if (operational_constraints['fuel_cost_per_km'] < 0.5 or 
        operational_constraints['fuel_cost_per_km'] > 2.0):
        return {"error": "Input is not valid"}
    
    if (operational_constraints['overtime_multiplier'] < 1.2 or 
        operational_constraints['overtime_multiplier'] > 2.5):
        return {"error": "Input is not valid"}
    
    if (operational_constraints['priority_weight_factor'] < 0.5 or 
        operational_constraints['priority_weight_factor'] > 2.0):
        return {"error": "Input is not valid"}
    
    # Check for circular dependencies
    circular_check = detect_circular_dependencies(dependencies, route_ids)
    if circular_check:
        return {"error": f"Circular dependency detected involving routes {circular_check}"}
    
    # Step 1: Dependency Analysis - Build dependency graph and perform topological sorting
    dependency_graph = defaultdict(list)
    reverse_dependency_graph = defaultdict(list)
    
    for dependency in dependencies:
        prereq = dependency['prerequisite_route_id']
        dependent = dependency['dependent_route_id']
        dependency_graph[prereq].append(dependency)
        reverse_dependency_graph[dependent].append(dependency)
    
    # Perform topological sorting to get dependency-respecting order
    topological_order = topological_sort(route_ids, dependencies)
    
    # Step 2: Priority Sorting while maintaining dependency constraints
    # Create route lookup for easy access
    route_lookup = {route['route_id']: route for route in routes}
    
    # Sort routes respecting both topological order and priority
    sorted_routes = sort_routes_with_dependencies(routes, topological_order)
    
    # Initialize assignment tracking
    truck_assignments = {truck['truck_id']: {
        'routes': [], 
        'cost': 0.0, 
        'utilization': 0.0, 
        'start_times': [], 
        'efficiency_score': 0.0,
        'total_distance': 0.0,
        'total_duration': 0.0
    } for truck in trucks}
    
    assigned_routes = set()
    unassigned_routes = []
    resolved_dependencies = []
    unresolved_dependencies = []
    constraint_violations = []

    # Process routes in dependency-aware priority order
    for route in sorted_routes:
        route_id = route['route_id']
        
        # Check if dependencies are satisfied
        unresolved_deps = check_unresolved_dependencies(route_id, reverse_dependency_graph, assigned_routes)
        
        if unresolved_deps:
            # Dependencies not satisfied - add to unresolved and skip for now
            unassigned_routes.append(route_id)
            for dep_id in unresolved_deps:
                if dep_id not in unresolved_dependencies:
                    unresolved_dependencies.append(dep_id)
        else:
            # All dependencies satisfied, find best assignment
            best_assignment = find_best_truck_assignment(
                route, trucks, truck_assignments, operational_constraints, 
                0, dependency_graph, assigned_routes, routes
            )
            
            if best_assignment:
                truck_id, start_time, efficiency_score, total_cost = best_assignment
                
                violation = check_assignment_constraints(
                    truck_id, route, start_time, trucks, truck_assignments, operational_constraints
                )
                
                if not violation:
                    make_assignment(truck_id, route, start_time, efficiency_score, total_cost,
                                  truck_assignments, assigned_routes, trucks, routes)
                    
                    # Mark dependencies as resolved
                    for dep in dependency_graph.get(route_id, []):
                        resolved_dependencies.append(dep['dependency_id'])
                else:
                    constraint_violations.append(violation)
                    unassigned_routes.append(route_id)
            else:
                unassigned_routes.append(route_id)
    
    # Calculate system metrics
    total_system_cost = sum(assignment['cost'] for assignment in truck_assignments.values())
    capacity_utilizations = [assignment['utilization'] for assignment in truck_assignments.values() 
                           if assignment['routes']]
    average_capacity_utilization = sum(capacity_utilizations) / len(capacity_utilizations) if capacity_utilizations else 0.0
    
    # Build dependency chain analysis
    dependency_chain_analysis = {}
    for dependency in dependencies:
        prereq = dependency['prerequisite_route_id']
        dependent = dependency['dependent_route_id']
        if prereq not in dependency_chain_analysis:
            dependency_chain_analysis[prereq] = []
        dependency_chain_analysis[prereq].append(dependent)
    
    # Calculate optimization summary
    total_efficiency = sum(assignment['efficiency_score'] for assignment in truck_assignments.values())
    dependency_resolution_rate = len(resolved_dependencies) / len(dependencies) if dependencies else 1.0
    
    # Format optimal assignments
    optimal_assignments = []
    for truck_id, assignment in truck_assignments.items():
        if assignment['routes']:
            optimal_assignments.append({
                "truck_id": truck_id,
                "assigned_routes": assignment['routes'],
                "total_assignment_cost": round(assignment['cost'], 1),
                "total_load_utilization": round(assignment['utilization'], 3),
                "scheduled_start_times": assignment['start_times'],
                "assignment_efficiency_score": round(assignment['efficiency_score'], 2)
            })
    
    return {
        "optimal_assignments": optimal_assignments,
        "dependency_satisfaction": {
            "resolved_dependencies": sorted(resolved_dependencies),
            "unresolved_dependencies": sorted(unresolved_dependencies),
            "dependency_chain_analysis": dependency_chain_analysis
        },
        "system_metrics": {
            "total_system_cost": round(total_system_cost, 1),
            "average_capacity_utilization": round(average_capacity_utilization, 3),
            "unassigned_routes": sorted(unassigned_routes),
            "constraint_violations": constraint_violations
        },
        "optimization_summary": {
            "assignment_efficiency": round(total_efficiency, 2),
            "dependency_resolution_rate": round(dependency_resolution_rate, 1),
            "resource_utilization_score": round(average_capacity_utilization, 3)
        }
    }

def topological_sort(route_ids: set, dependencies: List[Dict]) -> List[int]:
    """Perform topological sorting to determine dependency-respecting order"""
    # Build adjacency list for dependencies
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    
    # Initialize in_degree for all routes
    for route_id in route_ids:
        in_degree[route_id] = 0
    
    # Build graph and calculate in-degrees
    for dependency in dependencies:
        prereq = dependency['prerequisite_route_id']
        dependent = dependency['dependent_route_id']
        graph[prereq].append(dependent)
        in_degree[dependent] += 1
    
    # Kahn's algorithm for topological sorting
    queue = deque()
    
    # Add all routes with no dependencies to queue
    for route_id in route_ids:
        if in_degree[route_id] == 0:
            queue.append(route_id)
    
    result = []
    
    while queue:
        current = queue.popleft()
        result.append(current)
        
        # Reduce in-degree of dependent routes
        for dependent in graph[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    
    return result

def sort_routes_with_dependencies(routes: List[Dict], topological_order: List[int]) -> List[Dict]:
    """Sort routes by priority while respecting dependency constraints"""
        
    # Create position mapping for topological order
    topo_position = {route_id: idx for idx, route_id in enumerate(topological_order)}
    
    # Sort by priority first, then by topological position
    return sorted(routes, key=lambda r: (r['priority_level'], topo_position.get(r['route_id'], float('inf'))))

def calculate_manhattan_distance(point1: Dict, point2: Dict) -> float:
    """Calculate Manhattan distance between two points"""
    return abs(point1['x'] - point2['x']) + abs(point1['y'] - point2['y'])

def calculate_route_duration_with_complexity(route: Dict) -> float:
    """Calculate actual route duration considering complexity factor"""
    return route['estimated_duration'] * route['route_complexity']

def detect_circular_dependencies(dependencies: List[Dict], route_ids: set) -> str:
    """Detect circular dependencies using DFS"""
    graph = defaultdict(list)
    
    for dependency in dependencies:
        prereq = dependency['prerequisite_route_id']
        dependent = dependency['dependent_route_id']
        graph[prereq].append(dependent)
    
    visited = set()
    rec_stack = set()
    
    def dfs(node, path):
        if node in rec_stack:
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            return str(cycle)
        
        if node in visited:
            return None
        
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph[node]:
            result = dfs(neighbor, path)
            if result:
                return result
        
        rec_stack.remove(node)
        path.pop()
        return None
    
    for route_id in route_ids:
        if route_id not in visited:
            result = dfs(route_id, [])
            if result:
                return result
    
    return None

def check_unresolved_dependencies(route_id: int, reverse_dependency_graph: defaultdict,
                                assigned_routes: set) -> List[int]:
    """Check for unresolved dependencies for a route"""
    unresolved = []
    
    for dependency in reverse_dependency_graph[route_id]:
        if dependency['prerequisite_route_id'] not in assigned_routes:
            unresolved.append(dependency['dependency_id'])
    
    return unresolved

def find_best_truck_assignment(route: Dict, trucks: List[Dict], truck_assignments: Dict,
                             operational_constraints: Dict, unresolved_dep_count: int,
                             dependency_graph: defaultdict, assigned_routes: set, routes: List[Dict]):
    """Find the best truck assignment for a route"""
    best_assignment = None
    best_score = float('inf')
    
    for truck in trucks:
        if len(truck_assignments[truck['truck_id']]['routes']) >= operational_constraints['max_routes_per_truck']:
            continue
        
        if truck['capacity'] < route['load_requirement']:
            continue
        
        # Calculate earliest possible start time
        earliest_start = route['start_time_window']
        
        # Check dependency constraints
        for dep_route_id in assigned_routes:
            for dependency in dependency_graph.get(dep_route_id, []):
                if dependency['dependent_route_id'] == route['route_id']:
                    prereq_completion = find_route_completion_time(
                        dep_route_id, truck_assignments, routes
                    )
                    if prereq_completion is not None:
                        required_start = prereq_completion + dependency['minimum_gap_hours']
                        earliest_start = max(earliest_start, required_start)
        
        # Check truck availability
        truck_available_start = calculate_truck_availability(truck_assignments[truck['truck_id']], routes)
        earliest_start = max(earliest_start, truck_available_start)
        
        # Calculate actual route duration with complexity
        actual_duration = calculate_route_duration_with_complexity(route)
        
        # Check if route can be completed within time window
        if earliest_start + actual_duration > route['end_time_window']:
            continue
        
        # Check maintenance window conflicts
        if conflicts_with_maintenance(truck, earliest_start, actual_duration):
            continue
        
        # Calculate total operational cost for this assignment
        total_cost = calculate_total_assignment_cost(
            route, truck, actual_duration, operational_constraints, 
            truck_assignments[truck['truck_id']], unresolved_dep_count
        )
        
        # Calculate assignment efficiency score using CORRECT formula
        efficiency_score = calculate_assignment_efficiency_score(
            route, truck, earliest_start, unresolved_dep_count
        )
        
        if efficiency_score < best_score:
            best_score = efficiency_score
            best_assignment = (truck['truck_id'], earliest_start, efficiency_score, total_cost)
    
    return best_assignment

def calculate_total_assignment_cost(route: Dict, truck: Dict, actual_duration: float, 
                                  operational_constraints: Dict, current_assignment: Dict,
                                  unresolved_dep_count: int) -> float:
    """Calculate total cost including distance, fuel, priority adjustments, dependency penalties, and overtime"""
    
    # Base assignment cost with dependency cost adjustment
    base_cost = route['base_assignment_cost']
    if unresolved_dep_count > 0:
        base_cost = base_cost * (1 + 0.15 * unresolved_dep_count)
    
    # Apply priority weight factor to the (potentially adjusted) base cost
    priority_adjusted_base_cost = base_cost * operational_constraints['priority_weight_factor']
    
    # Distance-based fuel cost
    distance = calculate_manhattan_distance(truck['current_location'], route['destination_coordinates'])
    fuel_cost = distance * operational_constraints['fuel_cost_per_km']
    
    # Operational hour cost
    hour_cost = truck['base_cost_per_hour'] * actual_duration
    
    # Overtime calculation
    current_total_duration = current_assignment['total_duration'] + actual_duration
    overtime_cost = 0.0
    if current_total_duration > truck['operational_hours']:
        overtime_hours = current_total_duration - truck['operational_hours']
        overtime_cost = overtime_hours * truck['base_cost_per_hour'] * (operational_constraints['overtime_multiplier'] - 1)
    
    return priority_adjusted_base_cost + fuel_cost + hour_cost + overtime_cost

def find_route_completion_time(route_id: int, truck_assignments: Dict, routes: List[Dict]) -> float:
    """Find when a route was completed"""
    route_lookup = {route['route_id']: route for route in routes}
    
    for _, assignment in truck_assignments.items():
        if route_id in assignment['routes']:
            route_index = assignment['routes'].index(route_id)
            if route_index < len(assignment['start_times']):
                start_time = assignment['start_times'][route_index]
                duration = calculate_route_duration_with_complexity(route_lookup[route_id])
                return start_time + duration
    return None

def calculate_truck_availability(assignment: Dict, routes: List[Dict]) -> int:
    """Calculate when truck becomes available"""
    if not assignment['start_times'] or not assignment['routes']:
        return 0
    
    route_lookup = {route['route_id']: route for route in routes}
    
    # Find latest scheduled completion
    latest_completion = 0
    for i, route_id in enumerate(assignment['routes']):
        if i < len(assignment['start_times']):
            start_time = assignment['start_times'][i]
            duration = calculate_route_duration_with_complexity(route_lookup[route_id])
            completion_time = start_time + duration
            latest_completion = max(latest_completion, completion_time)
    
    return int(math.ceil(latest_completion))

def conflicts_with_maintenance(truck: Dict, start_time: int, duration: float) -> bool:
    """Check if route conflicts with maintenance window"""
    maintenance_start = truck['maintenance_window']['start_hour']
    maintenance_end = truck['maintenance_window']['end_hour']
    
    route_end = start_time + duration
    
    # Handle maintenance window crossing midnight
    if maintenance_start > maintenance_end:
        return (start_time <= maintenance_end or start_time >= maintenance_start or
                route_end <= maintenance_end or route_end >= maintenance_start)
    else:
        return not (route_end <= maintenance_start or start_time >= maintenance_end)

def calculate_assignment_efficiency_score(route: Dict, truck: Dict, start_time: int,
                                        unresolved_dep_count: int) -> float:
    """Calculate assignment efficiency score using the CORRECT formula from prompt"""
    
    # Base Assignment Cost (NO dependency cost adjustment here - that's for total cost only)
    base_assignment_cost = route['base_assignment_cost']
    
    # Capacity Penalty
    capacity_penalty = 0
    if route['load_requirement'] > truck['capacity'] * 0.8:
        capacity_penalty = (route['load_requirement'] / truck['capacity']) * 100
    
    # Dependency Penalty (this is separate from the dependency cost adjustment)
    dependency_penalty = unresolved_dep_count * 50
    
    # Time Penalty
    time_penalty = 0
    if start_time > route['end_time_window']:
        time_penalty = (start_time - route['end_time_window']) * 10
    
    # Window Urgency
    window_urgency = 200 / (route['end_time_window'] - route['start_time_window'] + 1)
    
    # Assignment Efficiency Score formula from prompt (CORRECTED)
    efficiency_score = base_assignment_cost + capacity_penalty + dependency_penalty + time_penalty + window_urgency
    
    return efficiency_score

def check_assignment_constraints(truck_id: int, route: Dict, start_time: int,
                               trucks: List[Dict], truck_assignments: Dict,
                               operational_constraints: Dict) -> str:
    """Check if assignment violates any constraints"""
    truck = next(t for t in trucks if t['truck_id'] == truck_id)
    assignment = truck_assignments[truck_id]
    
    # Check route limit
    if len(assignment['routes']) >= operational_constraints['max_routes_per_truck']:
        return f"Truck {truck_id} exceeds maximum routes per truck"
    
    # Check capacity
    if truck['capacity'] < route['load_requirement']:
        return f"Truck {truck_id} insufficient capacity for route {route['route_id']}"
    
    # Check operational hours with complexity-adjusted duration (removed hardcoded multiplier)
    actual_duration = calculate_route_duration_with_complexity(route)
    new_total_duration = assignment['total_duration'] + actual_duration
    # Allow reasonable overtime as per operational constraints, not hardcoded values
    max_allowed_duration = truck['operational_hours'] * operational_constraints['overtime_multiplier']
    if new_total_duration > max_allowed_duration:
        return f"Truck {truck_id} exceeds operational hours with overtime limits"
    
    # Check time window
    if start_time + actual_duration > route['end_time_window']:
        return f"Route {route['route_id']} cannot be completed within time window"
    
    return None

def make_assignment(truck_id: int, route: Dict, start_time: int, efficiency_score: float,
                   total_cost: float, truck_assignments: Dict, assigned_routes: set, 
                   trucks: List[Dict], routes: List[Dict]):
    """Make the truck-route assignment"""
    assignment = truck_assignments[truck_id]
    truck = next(t for t in trucks if t['truck_id'] == truck_id)
    
    assignment['routes'].append(route['route_id'])
    assignment['start_times'].append(start_time)
    assignment['cost'] += total_cost
    assignment['efficiency_score'] += efficiency_score
    
    # Update duration tracking
    actual_duration = calculate_route_duration_with_complexity(route)
    assignment['total_duration'] += actual_duration
    
    # Update distance tracking
    distance = calculate_manhattan_distance(truck['current_location'], route['destination_coordinates'])
    assignment['total_distance'] += distance
    
    # Update utilization
    route_lookup = {r['route_id']: r for r in routes}
    total_load = sum(route_lookup[route_id]['load_requirement'] for route_id in assignment['routes'])
    assignment['utilization'] = total_load / truck['capacity']
    
    assigned_routes.add(route['route_id'])

if __name__ == "__main__":
    trucks = [
        {"truck_id": 0, "capacity": 800, "operational_hours": 10, "base_cost_per_hour": 75, "maintenance_window": {"start_hour": 22, "end_hour": 6}, "truck_type": "medium", "current_location": {"x": 200, "y": 300}},
        {"truck_id": 1, "capacity": 1200, "operational_hours": 12, "base_cost_per_hour": 100, "maintenance_window": {"start_hour": 1, "end_hour": 5}, "truck_type": "heavy", "current_location": {"x": 400, "y": 500}},
        {"truck_id": 2, "capacity": 600, "operational_hours": 8, "base_cost_per_hour": 60, "maintenance_window": {"start_hour": 20, "end_hour": 4}, "truck_type": "light", "current_location": {"x": 100, "y": 150}}
    ]
    routes = [
        {"route_id": 0, "load_requirement": 500, "estimated_duration": 4, "priority_level": 1, "start_time_window": 6, "end_time_window": 14, "base_assignment_cost": 300, "route_complexity": 1.5, "destination_coordinates": {"x": 600, "y": 700}},
        {"route_id": 1, "load_requirement": 750, "estimated_duration": 6, "priority_level": 2, "start_time_window": 8, "end_time_window": 18, "base_assignment_cost": 450, "route_complexity": 2.0, "destination_coordinates": {"x": 800, "y": 400}},
        {"route_id": 2, "load_requirement": 400, "estimated_duration": 3, "priority_level": 1, "start_time_window": 10, "end_time_window": 16, "base_assignment_cost": 200, "route_complexity": 1.2, "destination_coordinates": {"x": 300, "y": 600}}
    ]
    dependencies = [
        {"dependency_id": 0, "prerequisite_route_id": 0, "dependent_route_id": 2, "dependency_type": "sequential", "minimum_gap_hours": 2}
    ]
    operational_constraints = {
        "max_routes_per_truck": 3,
        "fuel_cost_per_km": 1.2,
        "overtime_multiplier": 1.5,
        "priority_weight_factor": 1.3
    }
    result = optimize_truck_route_matching(trucks, routes, dependencies, operational_constraints)
    print(result)