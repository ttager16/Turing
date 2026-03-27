def optimize_routes(
    vehicle_data: List[Dict],
    traffic_data: List[Dict],
    road_closures: List[Dict],
    priority_changes: List[Dict]
) -> List[Dict]:
    # Build latest traffic map (last-update-wins per (u,v))
    traffic_map: Dict[Tuple[str,str], Dict[str, Any]] = {}
    for t in traffic_data:
        traffic_map[(t['u'], t['v'])] = t
    # Build closures map (last entry wins)
    closures: Dict[Tuple[str,str], bool] = {}
    for c in road_closures:
        closures[(c['u'], c['v'])] = bool(c.get('closed', False))
    # Build priority map (last entry wins)
    priorities: Dict[str, int] = {}
    for p in priority_changes:
        priorities[p['vehicle_id']] = int(p['priority'])
    results = []
    # Precompute adjacency
    adj: Dict[str, List[str]] = {}
    for (u,v), info in traffic_map.items():
        if closures.get((u,v), False):
            continue
        adj.setdefault(u, []).append(v)
    # For determinism sort adjacency
    for k in adj:
        adj[k].sort()
    # Helper to get edge info; returns None if closed or missing
    def edge_info(u,v):
        if closures.get((u,v), False):
            return None
        return traffic_map.get((u,v))
    # For each vehicle compute route
    for veh in vehicle_data:
        vid = veh['vehicle_id']
        cps = veh.get('checkpoints', [])
        if not cps:
            results.append({'vehicle_id': vid, 'optimized_route': [], 'estimated_time': 0, 'fuel_consumption': 0})
            continue
        # group checkpoints by group in ascending lex order
        groups: Dict[str, List[Dict]] = {}
        for cp in cps:
            groups.setdefault(cp['group'], []).append(cp.copy())
        group_keys = sorted(groups.keys())
        # sort within group not required; greedy chooses order
        # initial node is first checkpoint's node
        start_node = cps[0]['node']
        cur_node = start_node
        total_time = 0.0
        total_fuel = 0.0
        route_nodes = [cur_node]
        vehicle_priority = priorities.get(vid, 2)  # default medium
        failed = False
        # Process groups
        for gk in group_keys:
            remaining = groups[gk][:]
            # While there are checkpoints in this group
            while remaining:
                # We need to run Dijkstra-style from cur_node to any of remaining targets,
                # with score as cumulative score defined over edges.
                targets = set([r['node'] for r in remaining])
                # frontier entries: (cum_score, total_time_so_far, total_fuel_so_far, current_node, path_list)
                # tie-break order uses these fields
                start_entry = (0.0, total_time, total_fuel, cur_node, tuple([cur_node]))
                heap = [start_entry]
                # visited map to store best-known tuple per node for pruning: map node -> best key tuple
                visited_best: Dict[Tuple[str,float,float], float] = {}
                found = None  # will be (entry, target_checkpoint_dict, arrival_time, fuel_added, path)
                # Dijkstra-style expansion
                while heap:
                    cum_score, ttime, tfuel, node, path = heapq.heappop(heap)
                    # prune if we have seen a strictly better for same node
                    key = (node, round(ttime,6), round(tfuel,6))
                    prev_best = visited_best.get((node,0,0))
                    # Note: we don't have a single comparable metric; we use cum_score primary; but using visited_best simplistic
                    # For determinism and correctness keep minimal cum_score per node
                    vb = visited_best.get((node,0,0))
                    if vb is None:
                        visited_best[(node,0,0)] = cum_score
                    else:
                        if cum_score > vb + 1e-9:
                            continue
                    # If node is one of targets, pick corresponding checkpoint(s) with that node that are still remaining.
                    if node in targets:
                        # find matching checkpoint(s). choose the one with earliest latest window? But spec: arrival later penalized; greedy picks path to checkpoint node; we select first matching cp in remaining with node==node using deterministic order (window then service)
                        candidates = [r for r in remaining if r['node'] == node]
                        # choose deterministic one: sort by (window latest, window earliest, service)
                        candidates.sort(key=lambda x: (x['window'][1], x['window'][0], x['service']))
                        cpick = candidates[0]
                        arrival_time = ttime
                        # compute waiting if early
                        earliest, latest = cpick['window'][0], cpick['window'][1]
                        wait = 0.0
                        if arrival_time < earliest:
                            wait = earliest - arrival_time
                            arrival_time = earliest
                        # Check lateness: arrival_time > latest -> allowed but penalized? Problem says late arrivals are penalized in score; but also failure rule: "If any required subroute is impossible (respecting closures and windows)" and "If any arrival must exceed its latest window, return failure". So late is not permitted: arrival must not exceed latest.
                        if arrival_time > latest + 1e-9:
                            # This path yields late arrival -> treat as invalid; continue search for other paths
                            # Do not accept; continue expansion
                            pass
                        else:
                            # successful leg found
                            service = cpick.get('service', 0)
                            total_arrival_time = arrival_time + service
                            # fuel added is tfuel - total_fuel
                            fuel_added = tfuel - total_fuel
                            found = (cum_score, ttime, tfuel, node, path, cpick, wait, service, fuel_added)
                            break
                    # expand neighbors
                    for nbr in adj.get(node, []):
                        info = edge_info(node, nbr)
                        if info is None:
                            continue
                        edge_time = float(info['time'])
                        edge_cong = float(info['congestion'])
                        edge_fuel = float(info['fuel'])
                        age_min = int(info.get('age_min', 0))
                        max_age_min = int(info.get('max_age_min', 0))
                        stale = STALE_PENALTY if age_min > max_age_min else 0.0
                        base_score = (0.6 * edge_time) + (0.3 * edge_cong) + (0.1 * edge_fuel)
                        final_edge_score = (base_score + stale) / max(1, vehicle_priority)
                        new_cum_score = cum_score + final_edge_score
                        new_time = ttime + edge_time
                        new_fuel = tfuel + edge_fuel
                        new_path = path + (nbr,)
                        entry = (new_cum_score, new_time, new_fuel, nbr, new_path)
                        heapq.heappush(heap, entry)
                if not found:
                    failed = True
                    break
                # apply the found leg to update totals and route
                _, leg_time_before_service, leg_fuel_before_service, node, path, cpick, wait, service, fuel_added = found
                # Append path nodes excluding current node duplicate
                path_list = list(path)
                # path_list starts with cur_node; append subsequent nodes
                to_append = path_list[1:]
                route_nodes.extend(to_append)
                # Update totals: time increases by travel time to arrival (already in leg_time_before_service - total_time) plus waiting plus service
                travel_time = leg_time_before_service - total_time
                if travel_time < 0:
                    travel_time = 0.0
                total_time += travel_time
                # waiting
                total_time += wait
                # service
                total_time += service
                # fuel increases by fuel_added
                total_fuel += fuel_added
                # Move cur_node
                cur_node = cpick['node']
                # Remove selected checkpoint from remaining (only one with same node and same parameters)
                removed = False
                for i,r in enumerate(remaining):
                    if r['node'] == cpick['node'] and r['group'] == cpick['group'] and r['window'] == cpick['window'] and r['service'] == cpick['service']:
                        remaining.pop(i)
                        removed = True
                        break
                if not removed:
                    # fallback remove first matching node
                    for i,r in enumerate(remaining):
                        if r['node'] == cpick['node']:
                            remaining.pop(i)
                            break
            if failed:
                break
        if failed:
            results.append({'vehicle_id': vid, 'optimized_route': [], 'estimated_time': 0, 'fuel_consumption': 0})
        else:
            # Round estimated_time and fuel to reasonable numeric (keep as numbers)
            results.append({'vehicle_id': vid, 'optimized_route': route_nodes, 'estimated_time': total_time, 'fuel_consumption': total_fuel})
    return results