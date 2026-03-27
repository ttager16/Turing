def optimize_routes(
    vehicle_data: List[Dict],
    traffic_data: List[Dict],
    road_closures: List[Dict],
    priority_changes: List[Dict]
) -> List[Dict]:

    # Build latest traffic data per (u,v) - last entry wins
    traffic_map = {}
    for t in traffic_data:
        traffic_map[(t['u'], t['v'])] = {
            'time': float(t['time']),
            'congestion': float(t['congestion']),
            'fuel': float(t['fuel']),
            'age_min': int(t['age_min']),
            'max_age_min': int(t['max_age_min'])
        }

    # Build closures map last entry wins
    closure_map = {}
    for c in road_closures:
        closure_map[(c['u'], c['v'])] = bool(c['closed'])

    # Build priority map last entry wins; default 1 if absent
    priority_map = {}
    for p in priority_changes:
        priority_map[p['vehicle_id']] = int(p['priority'])

    # Build adjacency from traffic_map excluding closed edges
    adj = {}
    for (u, v), info in traffic_map.items():
        if closure_map.get((u, v), False):
            continue
        adj.setdefault(u, []).append((v, info))

    results = []

    # Helper: perform Dijkstra-style search from src to any of targets set,
    # using greedy cumulative score metric; returns best path and accumulated time/fuel and arrival_time before service
    def search_to_targets(src: str, targets: set, start_time: float, priority: int):
        # state: (cum_score, total_time, total_fuel, current_node, path)
        # deterministic tie-break: tuple as described; path_length is len(path)
        heap = []
        # initial state: at src, no added score/time/fuel, path contains src
        heapq.heappush(heap, (0.0, start_time, 0.0, src, [src]))
        # visited best by (node, total_time, total_fuel)? To keep deterministic but allow different times, use best cumulative_score seen per node with time rounding
        best_seen = {}
        while heap:
            cum_score, total_time, total_fuel, node, path = heapq.heappop(heap)
            key = (node, round(total_time, 6))
            if key in best_seen and best_seen[key] <= cum_score:
                continue
            best_seen[key] = cum_score
            if node in targets:
                return {
                    'path': path,
                    'arrival_time': total_time,
                    'total_time': total_time,
                    'total_fuel': total_fuel,
                    'cum_score': cum_score
                }
            # expand neighbors
            for v, info in adj.get(node, []):
                travel_time = info['time']
                congestion = info['congestion']
                fuel = info['fuel']
                age_min = info['age_min']
                max_age_min = info['max_age_min']
                stale = STALE_PENALTY if age_min > max_age_min else 0.0
                base_score = (0.6 * travel_time) + (0.3 * congestion) + (0.1 * fuel)
                edge_score = (base_score + stale) / (priority if priority > 0 else 1)
                new_cum_score = cum_score + edge_score
                new_total_time = total_time + travel_time
                new_total_fuel = total_fuel + fuel
                new_path = path + [v]
                heapq.heappush(heap, (new_cum_score, new_total_time, new_total_fuel, v, new_path))
        return None

    for vehicle in vehicle_data:
        vid = vehicle['vehicle_id']
        cp_list = vehicle.get('checkpoints', [])
        # partition by group lexicographic ascending
        groups = {}
        for cp in cp_list:
            groups.setdefault(cp['group'], []).append(cp)
        ordered_group_keys = sorted(groups.keys())
        priority = priority_map.get(vid, 1)
        # start at first checkpoint node as starting node
        if not cp_list:
            results.append({'vehicle_id': vid, 'optimized_route': [], 'estimated_time': 0, 'fuel_consumption': 0})
            continue
        # starting node is first checkpoint's node
        start_node = cp_list[0]['node']
        current_node = start_node
        optimized_route = [current_node]
        current_time = 0.0  # minutes since batch start
        total_fuel = 0.0
        feasible = True

        for gkey in ordered_group_keys:
            group = groups[gkey]
            # set of remaining target nodes for this group
            remaining = {cp['node'] for cp in group}
            # Need mapping node->checkpoint for window/service
            node_to_cp = {cp['node']: cp for cp in group}
            # If current_node is itself a checkpoint in remaining and not yet served, prefer to "visit" it immediately (0 travel)
            while remaining:
                # targets are remaining nodes
                search_result = search_to_targets(current_node, remaining, current_time, priority)
                if search_result is None:
                    feasible = False
                    break
                path = search_result['path']
                arrival_time = search_result['arrival_time']
                # path starts with current_node; next nodes are path[1:]
                # Choose the target node reached (last node in path that's in remaining)
                reached = None
                for node in reversed(path):
                    if node in remaining:
                        reached = node
                        break
                if reached is None:
                    feasible = False
                    break
                # compute time to reach reached from current_node by summing edges along path
                # accumulate fuel by summing edges
                # We'll walk the path edges to compute exact travel times/fuel and edge score contributions
                ttime = current_time
                tfuel = total_fuel
                # iterate edges
                for i in range(len(path)-1):
                    u = path[i]
                    v = path[i+1]
                    info = traffic_map.get((u, v))
                    if info is None or closure_map.get((u, v), False):
                        # missing edge due to closure or absent
                        feasible = False
                        break
                    ttime += info['time']
                    tfuel += info['fuel']
                if not feasible:
                    break
                arrival = ttime
                cp = node_to_cp[reached]
                window = cp['window']
                service = cp['service']
                earliest, latest = window[0], window[1]
                # If arrival > latest -> lateness; allowed but penalized in score. However failure rule: "If any required subroute is impossible (respecting closures and windows), the vehicle yields an empty route"
                # Interpret as arrival later than latest is considered infeasible per constraints -> fail
                if arrival > latest:
                    feasible = False
                    break
                # If arrival < earliest, wait until earliest
                wait = 0.0
                if arrival < earliest:
                    wait = earliest - arrival
                    arrival = earliest
                    ttime += wait
                # add service time
                ttime += service
                # update optimized route: append intermediate nodes excluding duplicate current_node
                for node in path[1:]:
                    optimized_route.append(node)
                # update states
                current_node = reached
                current_time = ttime
                total_fuel = tfuel
                # mark served
                remaining.remove(reached)
            if not feasible:
                break

        if not feasible:
            results.append({'vehicle_id': vid, 'optimized_route': [], 'estimated_time': 0, 'fuel_consumption': 0})
        else:
            results.append({
                'vehicle_id': vid,
                'optimized_route': optimized_route,
                'estimated_time': int(round(current_time)),
                'fuel_consumption': int(round(total_fuel))
            })

    return results