def calculate_total_cost(
        demand_schedule: List[float],
        usines: List[Dict[str, Any]],
        on_off_schedule: List[List[bool]]
) -> float:
    T = len(demand_schedule)
    if T != len(on_off_schedule):
        return float('inf')
    N = len(usines)
    for row in on_off_schedule:
        if len(row) != N:
            return float('inf')
    # Preprocess ramping curves: for each usine, map consecutive_on -> effective pmax
    ramp_maps = []
    abs_pmax = []
    for u in usines:
        curve = sorted(u.get('ramping_curve', []), key=lambda x: x[0])
        # Ensure covers increasing keys; we'll treat values for >= last key as last value
        ramp_maps.append(curve)
        abs_pmax.append(u.get('p_max', float('inf')))
    # Check T_on / T_off constraints
    # For each plant, find transitions and lengths
    for i, u in enumerate(usines):
        t_on = u.get('t_on', 1)
        t_off = u.get('t_off', 1)
        prev = False
        run_len = 0
        off_len = 0
        # Determine initial off_len or on run_len from start
        for t in range(T):
            state = bool(on_off_schedule[t][i])
            if state:
                # was off before?
                if not prev:
                    # check off_len >= t_off unless this is start (off_len counts previous consecutive offs)
                    if t > 0 and off_len < t_off:
                        return float('inf')
                    run_len = 1
                else:
                    run_len += 1
                prev = True
                off_len = 0
            else:
                if prev:
                    # was on before, check run_len >= t_on
                    if run_len < t_on:
                        return float('inf')
                    off_len = 1
                else:
                    off_len += 1
                prev = False
                run_len = 0
        # After end, if last state was on, ensure final run_len >= t_on
        if prev and run_len < t_on:
            return float('inf')
        # If last state was off, no need to check trailing off constraint per typical formulation
    total_cost = 0.0
    # For tracking consecutive on counts for ramping
    consec_on = [0]*N
    for t in range(T):
        demand = demand_schedule[t]
        if demand < -1e-9:
            return float('inf')
        # update consec_on based on schedule at time t
        for i in range(N):
            if on_off_schedule[t][i]:
                consec_on[i] += 1
            else:
                consec_on[i] = 0
        # For each plant that is on, determine effective pmin and pmax
        plant_info = []
        for i, u in enumerate(usines):
            is_on = bool(on_off_schedule[t][i])
            if not is_on:
                plant_info.append({'i': i, 'is_on': False, 'pmin': 0.0, 'pmax': 0.0, 'cost': u.get('cost_per_kwh', 0.0)})
                continue
            pmin = float(u.get('p_min', 0.0))
            # Determine ramped pmax from curve based on consec_on[i]
            ramp = ramp_maps[i]
            eff_pmax = None
            k = consec_on[i]
            eff_pmax = None
            for steps, val in ramp:
                if k <= steps:
                    eff_pmax = val
                    break
            if eff_pmax is None:
                # k greater than all keys -> take last value
                if ramp:
                    eff_pmax = ramp[-1][1]
                else:
                    eff_pmax = abs_pmax[i]
            # enforce absolute p_max cap
            eff_pmax = min(eff_pmax, abs_pmax[i])
            # check that pmin <= eff_pmax
            if pmin - eff_pmax > 1e-9:
                return float('inf')
            plant_info.append({'i': i, 'is_on': True, 'pmin': pmin, 'pmax': eff_pmax, 'cost': u.get('cost_per_kwh', 0.0)})
        # Must meet demand exactly using economic dispatch: sort on cost ascending
        # First sum minimum contributions of on plants
        total_min = sum(p['pmin'] for p in plant_info if p['is_on'])
        total_max = sum(p['pmax'] for p in plant_info if p['is_on'])
        if demand + 1e-9 < total_min or demand - 1e-9 > total_max:
            return float('inf')
        # Start by assigning pmin to all on plants, then allocate remaining demand to cheapest up to pmax
        allocation = [0.0]*N
        rem = demand
        # assign mins
        for p in plant_info:
            if p['is_on']:
                allocation[p['i']] = p['pmin']
                rem -= p['pmin']
        # allocate remaining rem >= 0
        # sort indices of on plants by cost then by larger pmax (tie-break)
        on_plants_sorted = sorted([p for p in plant_info if p['is_on']], key=lambda x: (x['cost'], -x['pmax']))
        for p in on_plants_sorted:
            if rem <= 1e-9:
                break
            i = p['i']
            avail = p['pmax'] - allocation[i]
            take = min(avail, rem)
            allocation[i] += take
            rem -= take
        if rem > 1e-6:
            return float('inf')
        # Validate allocations within bounds
        for p in plant_info:
            i = p['i']
            if not p['is_on']:
                if abs(allocation[i]) > 1e-9:
                    return float('inf')
            else:
                if allocation[i] + 1e-9 < p['pmin'] or allocation[i] - 1e-9 > p['pmax']:
                    return float('inf')
        # Compute cost for this time step
        for i in range(N):
            if allocation[i] > 1e-9:
                cost_rate = usines[i].get('cost_per_kwh', 0.0)
                total_cost += allocation[i] * cost_rate
    return total_cost