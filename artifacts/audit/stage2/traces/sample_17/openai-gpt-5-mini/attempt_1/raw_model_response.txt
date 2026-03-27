def find_nearest_depot(depots, target_distance, offline_depots=None, zero_capacity_depots=None, 
                      priority_levels=None, operating_hours=None, load_capacities=None, current_hour=12,
                      weather_affected_depots=None, service_types=None, required_service_type=None,
                      maintenance_schedules=None, depot_zones=None, allowed_zones=None, 
                      depot_costs=None, max_budget=None):
    """Return index of nearest valid depot or -1."""
    # Normalize "empty as None"
    def none_if_empty(x):
        if x is None:
            return None
        if isinstance(x, dict) and len(x) == 0:
            return None
        if isinstance(x, (list, tuple)) and len(x) == 0:
            return None
        if isinstance(x, (int, float)) and x == 0:
            return None
        return x
    offline_depots = none_if_empty(offline_depots)
    zero_capacity_depots = none_if_empty(zero_capacity_depots)
    priority_levels = none_if_empty(priority_levels)
    operating_hours = none_if_empty(operating_hours)
    load_capacities = none_if_empty(load_capacities)
    weather_affected_depots = none_if_empty(weather_affected_depots)
    service_types = none_if_empty(service_types)
    maintenance_schedules = none_if_empty(maintenance_schedules)
    depot_zones = none_if_empty(depot_zones)
    allowed_zones = none_if_empty(allowed_zones)
    depot_costs = none_if_empty(depot_costs)
    max_budget = none_if_empty(max_budget)

    n = len(depots)
    # Defaults
    if offline_depots is None:
        offline_set = set()
    else:
        offline_set = set(offline_depots)
    if zero_capacity_depots is None:
        zero_capacity_set = set()
    else:
        zero_capacity_set = set(zero_capacity_depots)
    if priority_levels is None:
        priority_levels = [1] * n
    if operating_hours is None:
        operating_hours = [[0, 24]] * n
    if load_capacities is None:
        load_capacities = [float('inf')] * n
    if weather_affected_depots is None:
        weather_set = set()
    else:
        weather_set = set(weather_affected_depots)
    if service_types is None:
        service_types = [None] * n
    if maintenance_schedules is None:
        maintenance_schedules = [None] * n
    if depot_zones is None:
        depot_zones = [None] * n
    if allowed_zones is None:
        allowed_zones_set = None
    else:
        allowed_zones_set = set(allowed_zones)
    if depot_costs is None:
        depot_costs = [None] * n
    if max_budget is None:
        max_budget_val = None
    else:
        max_budget_val = max_budget

    # Helper: check if depot i is valid
    def is_valid(i):
        if i < 0 or i >= n:
            return False
        if i in offline_set:
            return False
        if i in zero_capacity_set:
            return False
        # capacity numeric check
        cap = load_capacities[i] if i < len(load_capacities) else float('inf')
        if cap is None:
            cap = float('inf')
        if cap <= 0:
            return False
        if i in weather_set:
            return False
        # operating hours
        oh = operating_hours[i] if i < len(operating_hours) else [0, 24]
        if oh is None:
            oh = [0, 24]
        try:
            start_h, end_h = int(oh[0]), int(oh[1])
        except Exception:
            start_h, end_h = 0, 24
        # treat end_h==start_h as full day if both 0 or 24, else empty
        if not (start_h == end_h == 0 or start_h == end_h == 24):
            if start_h <= end_h:
                if not (start_h <= current_hour < end_h):
                    return False
            else:
                # overnight window
                if not (current_hour >= start_h or current_hour < end_h):
                    return False
        # maintenance
        ms = maintenance_schedules[i] if i < len(maintenance_schedules) else None
        if ms:
            try:
                mstart, mend = int(ms[0]), int(ms[1])
                if mstart <= mend:
                    if mstart <= current_hour < mend:
                        return False
                else:
                    if current_hour >= mstart or current_hour < mend:
                        return False
            except Exception:
                pass
        # service type
        st = service_types[i] if i < len(service_types) else None
        if required_service_type is not None:
            if st is not None and st != required_service_type:
                return False
            if st is None:
                # assume supports all if unspecified
                pass
        # zone
        zone = depot_zones[i] if i < len(depot_zones) else None
        if allowed_zones_set is not None:
            if zone is None:
                # unspecified zone -> treat as allowed
                pass
            elif zone not in allowed_zones_set:
                return False
        # budget
        cost = depot_costs[i] if i < len(depot_costs) else None
        if max_budget_val is not None:
            if cost is None:
                # unspecified cost -> treat as allowed
                pass
            else:
                try:
                    if cost > max_budget_val:
                        return False
                except Exception:
                    pass
        return True

    # Because depots are near-sorted (displaced up to ±2), but with updates may be more,
    # we still need global scan due to many constraints. We'll scan all depots keeping best.
    best_idx = -1
    best_key = None  # tuple (distance_diff, -priority, index)
    for i, d in enumerate(depots):
        if not is_valid(i):
            continue
        try:
            dist = abs(int(d) - int(target_distance))
        except Exception:
            try:
                dist = abs(float(d) - float(target_distance))
            except Exception:
                continue
        pr = priority_levels[i] if i < len(priority_levels) and priority_levels[i] is not None else 1
        # selection key
        key = (dist, -int(pr), i)
        if best_key is None or key < best_key:
            best_key = key
            best_idx = i
    return best_idx