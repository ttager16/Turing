def optimize_drone_routes(
    drones: List[Dict],
    destinations: List[Dict],
    weather_data: Dict,
    traffic_data: Dict
) -> Dict[str, List[Union[str, Dict]]]:
    # Prepare outputs
    result = {d['id']: [] for d in (drones or [])}
    if not drones:
        return {}
    if not destinations:
        return result

    # Helpers
    def fuel_required_for(priority, workload):
        return 20.0 * (1.0 + (priority - 1) * 0.15) * (1.0 + workload * 0.1)

    # Environmental constraints
    current_wind = weather_data.get('current', {}).get('wind_speed', 0.0)
    forecast = weather_data.get('forecast', [])
    restricted_now = set(weather_data.get('current', {}).get('restricted_zones', []))

    hub_connectivity = traffic_data.get('hub_connectivity') or {}
    # available hubs not in current restricted zones
    available_hubs = [h for h in hub_connectivity.keys() if h not in restricted_now]
    if available_hubs:
        # select hub with most connections, tie by name
        max_conn = max((len(hub_connectivity[h]) for h in available_hubs), default=0)
        hubs_with_max = sorted([h for h in available_hubs if len(hub_connectivity[h]) == max_conn])
        selected_hub = hubs_with_max[0] if hubs_with_max else None
    else:
        selected_hub = None

    # traffic congestion levels across lanes
    congestion_levels = [lane.get('congestion_level', '').lower() for lane in traffic_data.get('air_lanes', [])]
    traffic_limits_one = any(c in ('high', 'medium') for c in congestion_levels)

    # Preprocess drones state
    drones_state = {}
    for d in drones:
        did = d['id']
        fuel_level = float(d.get('fuel_level', 0.0))
        max_fuel = float(d.get('max_fuel', 0.0))
        wt = float(d.get('wind_tolerance', 0.0))
        # grounded if current wind > tolerance + 3.0
        grounded = current_wind > (wt + 3.0)
        # forecast limit: if any forecast wind > tolerance then limited to 1 delivery
        forecast_limit = any(f.get('wind_speed', 0.0) > wt for f in forecast)
        drones_state[did] = {
            'id': did,
            'fuel_level': fuel_level,
            'max_fuel': max_fuel,
            'wind_tolerance': wt,
            'grounded': grounded,
            'forecast_limit': forecast_limit,
            'workload': 0,
            'assigned': [],
            'refueled': False
        }

    # If all grounded -> return all empty
    if all(s['grounded'] for s in drones_state.values()):
        return result

    # Sort destinations by priority asc then penalty desc within same priority
    def dest_sort_key(dest):
        p = dest.get('priority', 99)
        return (p, -dest.get('penalty', 0))
    sorted_dest = sorted(destinations, key=dest_sort_key)

    # Main loop
    for dest in sorted_dest:
        dest_id = dest['id']
        priority = dest.get('priority', 3)
        # Determine per-destination traffic/forecast limiting
        # traffic_limits_one is global
        # For each drone, Exception applies if forecast_limit AND traffic_limits_one
        # Step 1: Filter operational drones with fuel capability
        candidates = []
        for s in drones_state.values():
            if s['grounded']:
                continue
            if s['fuel_level'] <= 0 and s['max_fuel'] <= 0:
                continue
            # compute required fuel based on current workload (before assignment)
            fr = fuel_required_for(priority, s['workload'])
            if (s['fuel_level'] >= fr) or (s['max_fuel'] >= fr):
                candidates.append(s)
        if not candidates:
            continue

        # Step 2: Filter by workload
        min_workload = min(c['workload'] for c in candidates)
        if priority in (1, 2):
            candidates = [c for c in candidates if c['workload'] <= min_workload + 1]
        else:
            candidates = [c for c in candidates if c['workload'] == min_workload]
        if not candidates:
            continue

        # Step 3: Categorize by refueling need (Standard Case only)
        needing_refuel = []
        not_needing_refuel = []
        for c in candidates:
            fuel_percentage = (c['fuel_level'] / c['max_fuel'] * 100.0) if c['max_fuel'] > 0 else 0.0
            fr = fuel_required_for(priority, c['workload'])
            needs = (fuel_percentage <= 60.0) or (c['fuel_level'] < fr)
            if needs:
                needing_refuel.append(c)
            else:
                not_needing_refuel.append(c)

        # Step 4: Select best drone based on priority rules
        def sort_min(lst, keyfunc):
            return sorted(lst, key=keyfunc)[0]

        selected = None
        if priority == 1:
            if needing_refuel:
                # key = (-wind_tolerance, -fuel_percentage, drone_id) minimal => more negative first so use tuple
                def k(c):
                    fp = (c['fuel_level'] / c['max_fuel'] * 100.0) if c['max_fuel'] > 0 else 0.0
                    return (-c['wind_tolerance'], -fp, c['id'])
                selected = sort_min(needing_refuel, k)
            else:
                def k(c):
                    return (-c['fuel_level'], c['id'])
                selected = sort_min(candidates, k)
        elif priority == 2:
            if needing_refuel:
                def k(c):
                    fp = (c['fuel_level'] / c['max_fuel'] * 100.0) if c['max_fuel'] > 0 else 0.0
                    return (fp, c['id'])
                selected = sort_min(needing_refuel, k)
            else:
                def k(c):
                    return (-c['fuel_level'], c['id'])
                selected = sort_min(candidates, k)
        else:
            if not_needing_refuel:
                def k(c):
                    return (-c['fuel_level'], c['id'])
                selected = sort_min(not_needing_refuel, k)
            else:
                def k(c):
                    return (-c['fuel_level'], c['id'])
                selected = sort_min(needing_refuel, k)

        if not selected:
            continue

        # Before assignment, evaluate refueling decision (Exception or Standard)
        s = selected
        exception_case = (s['forecast_limit'] and traffic_limits_one)
        fuel_percentage = (s['fuel_level'] / s['max_fuel'] * 100.0) if s['max_fuel'] > 0 else 0.0
        fr = fuel_required_for(priority, s['workload'])
        will_refuel = False
        if exception_case:
            if s['fuel_level'] < fr:
                will_refuel = True
            elif abs(fuel_percentage - 50.0) < 1e-9:
                will_refuel = False
            elif fuel_percentage < 50.0:
                will_refuel = True
            elif fuel_percentage <= 60.0:
                will_refuel = True
            else:
                will_refuel = False
        else:
            if (fuel_percentage <= 60.0) or (s['fuel_level'] < fr):
                will_refuel = True
            else:
                will_refuel = False

        # If will_refuel but no hubs available, only allow if sufficient without refuel
        if will_refuel and not selected_hub:
            if s['fuel_level'] < fr:
                # cannot perform delivery
                continue
            else:
                will_refuel = False

        # Also enforce per-drone limits: if forecast_limit then max 1 delivery
        # If traffic_limits_one then max 1 delivery for all
        per_drone_limit = 1 if (s['forecast_limit'] or traffic_limits_one) else None
        if per_drone_limit is not None and s['workload'] >= per_drone_limit:
            continue

        # Final check fuel sufficiency post-refuel decision
        if will_refuel:
            # Refuel at selected_hub (already ensured exists)
            s['fuel_level'] = s['max_fuel']
            s['refueled'] = True
            # add hub stop if not already present
            # Only add refuel stop at start of route (before first delivery)
            if not s['assigned']:
                if selected_hub:
                    result[s['id']].append({'hub': selected_hub, 'refuel': True})
        # After possible refuel, ensure fuel still enough
        fr = fuel_required_for(priority, s['workload'])
        if s['fuel_level'] < fr:
            continue

        # Assign destination
        result[s['id']].append(dest_id)
        s['assigned'].append(dest_id)
        # reduce fuel
        s['fuel_level'] -= fr
        if s['fuel_level'] < 0:
            s['fuel_level'] = 0.0
        s['workload'] += 1

    # Ensure all drones present in result
    for did in drones_state.keys():
        if did not in result:
            result[did] = []

    return result