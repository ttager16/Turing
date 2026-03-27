def optimize_supply_chain_routes(distribution_centers: List[Dict], destinations: List[Dict], 
                                 cost_matrix: List[List[float]], time_windows: List) -> Dict[str, Any]:
    # Input validations
    if not isinstance(distribution_centers, list) or not isinstance(destinations, list) or not isinstance(cost_matrix, list) or not isinstance(time_windows, list):
        return {"error": "Input is not valid"}
    if len(destinations) == 0:
        return {"error": "Empty destination list provided"}
    num_dc = len(distribution_centers)
    num_dest = len(destinations)
    # cost_matrix dimensions
    if any(not isinstance(row, list) or len(row) != num_dest for row in cost_matrix) or len(cost_matrix) != num_dc:
        return {"error": "Invalid cost matrix dimensions"}
    # negative cost check
    for row in cost_matrix:
        for v in row:
            try:
                if v < 0:
                    return {"error": "Negative cost detected in cost matrix"}
            except TypeError:
                return {"error": "Input is not valid"}
    # time windows validation length
    if len(time_windows) != num_dest:
        return {"error": "Input is not valid"}
    # validate time windows
    for idx, tw in enumerate(time_windows):
        if (not isinstance(tw, (list, tuple))) or len(tw) != 2:
            return {"error": "Input is not valid"}
        try:
            earliest, latest = int(tw[0]), int(tw[1])
        except Exception:
            return {"error": "Input is not valid"}
        if earliest >= latest:
            dest_id = destinations[idx].get("id", idx)
            return {"error": f"Invalid time window for destination {dest_id}"}
        # also validate range
        if earliest < 0 or latest < 0:
            dest_id = destinations[idx].get("id", idx)
            return {"error": f"Invalid time window for destination {dest_id}"}
    # prepare mappings
    dc_map = {}
    for dc in distribution_centers:
        if not isinstance(dc, dict) or 'id' not in dc or 'capacity' not in dc or 'base_cost' not in dc or 'efficiency_factor' not in dc:
            return {"error": "Input is not valid"}
        dc_map[dc['id']] = {
            'capacity': dc['capacity'],
            'remaining': dc['capacity'],
            'base_cost': float(dc['base_cost']),
            'efficiency_factor': float(dc['efficiency_factor'])
        }
    dest_list = []
    for i, dest in enumerate(destinations):
        if not isinstance(dest, dict) or 'id' not in dest or 'demand' not in dest or 'priority_level' not in dest:
            return {"error": "Input is not valid"}
        dest_list.append({
            'index': i,
            'id': dest['id'],
            'demand': int(dest['demand']),
            'priority_level': int(dest['priority_level'])
        })
    # compute max time window span
    spans = []
    for tw in time_windows:
        earliest, latest = int(tw[0]), int(tw[1])
        spans.append(latest - earliest)
    max_time_span = max(spans) if spans else 0
    urgency_multiplier = 0.75 * max_time_span
    # helper to compute weighted cost
    def compute_cost(dc_idx, dest_idx):
        dc = distribution_centers[dc_idx]
        dest = destinations[dest_idx]
        transportation_cost = float(cost_matrix[dc_idx][dest_idx])
        operational_cost = dc['base_cost'] * dest['demand'] * dc['efficiency_factor']
        total_route_cost = transportation_cost + operational_cost
        priority_level = dest.get('priority_level', 5)
        if priority_level <= 0:
            priority_level = 1
        urgency_weight = urgency_multiplier / (priority_level * 10.0)
        weighted_cost = total_route_cost - urgency_weight
        return {
            'transportation_cost': transportation_cost,
            'operational_cost': operational_cost,
            'total_route_cost': total_route_cost,
            'weighted_cost': weighted_cost
        }
    # assignment loop
    unassigned = set(d['index'] for d in dest_list)
    assignments = []
    # deterministic ordering: process by destination id order when ties
    while unassigned:
        best_option = None  # (weighted_cost, priority_level, dc_id, dest_index, cost_details)
        for dest_idx in list(unassigned):
            dest = destinations[dest_idx]
            demand = int(dest['demand'])
            priority_level = int(dest['priority_level'])
            for dc_idx, dc in enumerate(distribution_centers):
                dc_id = dc['id']
                if dc_id not in dc_map:
                    return {"error": "Input is not valid"}
                remaining = dc_map[dc_id]['remaining']
                if demand > remaining:
                    continue
                # compute cost
                cost_det = compute_cost(dc_idx, dest_idx)
                wc = cost_det['weighted_cost']
                # tie-breaker: lower priority_level preferred (i.e., 1 better than 2)
                key = (wc, priority_level, dc_id, dest['id'])
                if best_option is None or key < best_option[0]:
                    best_option = (key, dc_id, dest_idx, cost_det)
        if best_option is None:
            # no feasible assignments remain
            break
        _, chosen_dc_id, chosen_dest_idx, cost_det = best_option
        # final capacity check and assign
        demand = int(destinations[chosen_dest_idx]['demand'])
        if demand > dc_map[chosen_dc_id]['remaining']:
            return {"error": f"Capacity exceeded for distribution center {chosen_dc_id}"}
        dc_map[chosen_dc_id]['remaining'] -= demand
        # schedule time at midpoint
        earliest, latest = time_windows[chosen_dest_idx]
        scheduled_time = (int(earliest) + int(latest)) // 2
        assignments.append({
            "distribution_center_id": chosen_dc_id,
            "destination_id": destinations[chosen_dest_idx]['id'],
            "transportation_cost": round(cost_det['transportation_cost'], 6),
            "operational_cost": round(cost_det['operational_cost'], 6),
            "total_route_cost": round(cost_det['total_route_cost'], 6),
            "scheduled_delivery_time": scheduled_time
        })
        unassigned.remove(chosen_dest_idx)
    unassigned_dest_ids = [destinations[i]['id'] for i in sorted(unassigned)]
    # If any destination left unassigned due to capacity limits, indicate but do not error unless specification requires error
    total_system_cost = sum(a['total_route_cost'] for a in assignments)
    return {
        "assignments": assignments,
        "total_system_cost": round(total_system_cost, 6),
        "unassigned_destinations": unassigned_dest_ids
    }