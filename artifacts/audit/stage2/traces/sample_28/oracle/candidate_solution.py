from typing import List, Dict, Any
import copy

def simulate_decision_tree(
    suppliers: List[Dict[str, Any]],
    distribution_centers: List[Dict[str, Any]],
    warehouses: List[Dict[str, Any]],
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    
    if not suppliers or not distribution_centers:
        return {}
    
    num_phases = len(suppliers[0]['inventory']) if suppliers else 1
    
    supplier_map = {s['id']: s for s in suppliers}
    dc_map = {dc['id']: dc for dc in distribution_centers}
    warehouse_map = {w['id']: w for w in warehouses}
    
    best_solution = None
    best_cost = float('inf')
    best_time = float('inf')
    
    def get_coalition_discount(supplier_id: str, route_cost: int, route_time: int) -> tuple:
        supplier = supplier_map.get(supplier_id)
        if supplier and supplier.get('coalition_id'):
            discounted_cost = int(route_cost * 0.85)
            discounted_time = int(route_time * 0.80)
            return discounted_cost, discounted_time, supplier['coalition_id']
        return route_cost, route_time, None
    
    def apply_events_to_network(phase_idx: int, working_suppliers: List[Dict], working_warehouses: List[Dict]) -> None:
        phase_num = phase_idx + 1
        
        for event in events:
            if event['phase'] > phase_num:
                continue
                
            action = event['action']
            details = event['details']
            
            if action == 'route_closure':
                from_node = details['from']
                to_node = details['to']
                
                for s in working_suppliers:
                    if s['id'] == from_node and to_node in s.get('routes', {}):
                        del s['routes'][to_node]
                
                for w in working_warehouses:
                    if w['id'] == from_node and to_node in w.get('routes', {}):
                        del w['routes'][to_node]
            
            elif action == 'capacity_change':
                w_id = details['warehouse_id']
                new_cap = details['new_capacity']
                
                for w in working_warehouses:
                    if w['id'] == w_id:
                        for p in range(event['phase'] - 1, len(w['capacity'])):
                            w['capacity'][p] = new_cap
    
    def brute_force_phase_simulation(
        phase_idx: int,
        phase_suppliers: List[Dict],
        phase_warehouses: List[Dict],
        dc_demands: Dict[str, int]
    ) -> List[Dict]:
        phase_supplier_inventory = {s['id']: s['inventory'][phase_idx] if phase_idx < len(s['inventory']) else 0 for s in phase_suppliers}
        phase_warehouse_capacity = {w['id']: w['capacity'][phase_idx] if phase_idx < len(w['capacity']) else 0 for w in phase_warehouses}
        
        best_phase_routes = []
        best_phase_cost = float('inf')
        
        def brute_force_route_evaluation():
            nonlocal best_phase_routes, best_phase_cost
            
            remaining_suppliers = phase_supplier_inventory.copy()
            remaining_capacity = phase_warehouse_capacity.copy()
            remaining_demand = dc_demands.copy()
            
            current_routes = []
            current_cost = 0
            max_iterations = sum(dc_demands.values()) + 1
            iteration_count = 0
            
            while iteration_count < max_iterations:
                iteration_count += 1
                best_route = None
                best_route_cost = float('inf')
                
                for supplier in phase_suppliers:
                    s_id = supplier['id']
                    if remaining_suppliers.get(s_id, 0) <= 0:
                        continue
                    
                    for w_id, s_route in supplier.get('routes', {}).items():
                        if remaining_capacity.get(w_id, 0) <= 0:
                            continue
                        
                        warehouse = next((w for w in phase_warehouses if w['id'] == w_id), None)
                        if not warehouse:
                            continue
                        
                        for dc_id, w_route in warehouse.get('routes', {}).items():
                            if remaining_demand.get(dc_id, 0) <= 0:
                                continue
                            
                            total_route_cost = s_route['cost'] + w_route['cost']
                            total_route_time = s_route['time'] + w_route['time']
                            
                            adj_cost, adj_time, coalition = get_coalition_discount(s_id, total_route_cost, total_route_time)
                            
                            max_units = min(
                                remaining_suppliers[s_id],
                                remaining_capacity[w_id],
                                remaining_demand[dc_id]
                            )
                            
                            if max_units <= 0:
                                continue
                            
                            cost_per_unit = adj_cost / max_units
                            
                            if cost_per_unit < best_route_cost:
                                best_route_cost = cost_per_unit
                                best_route = {
                                    'path': [s_id, w_id, dc_id],
                                    'units_shipped': max_units,
                                    'coalition_used': coalition,
                                    'phase_cost': adj_cost,
                                    'phase_time': adj_time
                                }
                
                if not best_route:
                    break
                
                current_routes.append(best_route)
                current_cost += best_route['phase_cost']
                
                s_id, w_id, dc_id = best_route['path']
                units = best_route['units_shipped']
                
                remaining_suppliers[s_id] -= units
                remaining_capacity[w_id] -= units
                remaining_demand[dc_id] -= units
            
            if current_cost < best_phase_cost:
                best_phase_cost = current_cost
                best_phase_routes = current_routes
        
        brute_force_route_evaluation()
        return best_phase_routes
    
    def sequential_phase_solver(
        phase_idx: int,
        current_routes: List[Dict],
        supplier_remaining: List[Dict[str, int]],
        working_suppliers: List[Dict],
        working_warehouses: List[Dict],
        current_cost: int,
        current_time: int
    ) -> None:
        nonlocal best_solution, best_cost, best_time
        
        if phase_idx >= num_phases:
            if current_cost < best_cost or (current_cost == best_cost and current_time < best_time):
                best_cost = current_cost
                best_time = current_time
                best_solution = {
                    'multi_phase_routes': current_routes.copy(),
                    'total_cost': current_cost,
                    'total_time': current_time
                }
            return
        
        phase_suppliers = copy.deepcopy(working_suppliers)
        phase_warehouses = copy.deepcopy(working_warehouses)
        apply_events_to_network(phase_idx, phase_suppliers, phase_warehouses)
        
        dc_demands = {}
        for dc in distribution_centers:
            if phase_idx < len(dc['demand']):
                dc_demands[dc['id']] = dc['demand'][phase_idx]
        
        phase_routes = brute_force_phase_simulation(phase_idx, phase_suppliers, phase_warehouses, dc_demands)
        
        phase_cost = sum(route['phase_cost'] for route in phase_routes)
        phase_time = sum(route['phase_time'] for route in phase_routes)
        
        phase_data = {
            'phase': phase_idx + 1,
            'routes': phase_routes
        }
        
        new_routes = current_routes + [phase_data]
        new_cost = current_cost + phase_cost
        new_time = current_time + phase_time
        
        new_supplier_remaining = []
        for p in range(num_phases):
            if p == phase_idx:
                new_supplier_remaining.append({s['id']: s['inventory'][p] if p < len(s['inventory']) else 0 for s in phase_suppliers})
            else:
                new_supplier_remaining.append(supplier_remaining[p].copy())
        
        sequential_phase_solver(
            phase_idx + 1,
            new_routes,
            new_supplier_remaining,
            phase_suppliers,
            phase_warehouses,
            new_cost,
            new_time
        )
    
    supplier_remaining = []
    for phase in range(num_phases):
        supplier_remaining.append({s['id']: s['inventory'][phase] if phase < len(s['inventory']) else 0 for s in suppliers})
    
    sequential_phase_solver(
        0,
        [],
        supplier_remaining,
        copy.deepcopy(suppliers),
        copy.deepcopy(warehouses),
        0,
        0
    )
    
    if best_solution is None:
        return {}
    
    unmet_demand_dict = {}
    for dc in distribution_centers:
        dc_id = dc['id']
        total_demand = sum(dc['demand'])
        total_delivered = 0
        
        for phase_data in best_solution['multi_phase_routes']:
            for route in phase_data['routes']:
                if route['path'][-1] == dc_id:
                    total_delivered += route['units_shipped']
        
        unmet = max(0, total_demand - total_delivered)
        unmet_demand_dict[dc_id] = unmet
    
    best_solution['unmet_demand'] = unmet_demand_dict
    
    return best_solution