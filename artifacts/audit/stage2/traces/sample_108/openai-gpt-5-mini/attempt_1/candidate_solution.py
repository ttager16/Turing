def calculate_total_cost(
        demand_schedule: List[float],
        usines: List[Dict[str, Any]],
        on_off_schedule: List[List[bool]]
) -> float:
    T = len(demand_schedule)
    if T != len(on_off_schedule):
        return float('inf')
    M = len(usines)
    for row in on_off_schedule:
        if len(row) != M:
            return float('inf')
    # Preprocess ramping curves: sort by steps
    ramp_maps = []
    for u in usines:
        rc = sorted(u.get('ramping_curve', []), key=lambda x: x[0])
        ramp_maps.append(rc)
    # check T_on / T_off constraints by scanning transitions
    # compute for each plant its consecutive on/off counters across time
    cons_on = [[0]*M for _ in range(T)]
    cons_off = [[0]*M for _ in range(T)]
    for i in range(M):
        for t in range(T):
            on = on_off_schedule[t][i]
            if on:
                cons_on[t][i] = 1 + (cons_on[t-1][i] if t>0 else 0)
                cons_off[t][i] = 0
            else:
                cons_off[t][i] = 1 + (cons_off[t-1][i] if t>0 else 0)
                cons_on[t][i] = 0
    # Verify T_on / T_off: when a start event occurs at time t (on and previous off), must remain on for T_on
    for i,u in enumerate(usines):
        T_on = u.get('t_on', 0)
        T_off = u.get('t_off', 0)
        for t in range(T):
            prev_on = on_off_schedule[t-1][i] if t>0 else False
            cur_on = on_off_schedule[t][i]
            if cur_on and not prev_on:
                # started at t: must have cons_on at least T_on from t through t+T_on-1
                if T_on > 0:
                    end = t + T_on - 1
                    if end >= T:
                        return float('inf')
                    for tt in range(t, end+1):
                        if not on_off_schedule[tt][i]:
                            return float('inf')
            if not cur_on and prev_on:
                # stopped at t: must have cons_off at least T_off from t through t+T_off-1
                if T_off > 0:
                    end = t + T_off - 1
                    if end >= T:
                        return float('inf')
                    for tt in range(t, end+1):
                        if on_off_schedule[tt][i]:
                            return float('inf')
    total_cost = 0.0
    # For each time, determine available plants, their p_min and effective p_max based on cons_on
    for t in range(T):
        demand = demand_schedule[t]
        # collect available plants
        avail = []
        for i,u in enumerate(usines):
            if on_off_schedule[t][i]:
                # determine consecutive on up to t
                k = cons_on[t][i]
                # find ramp entry with largest steps <= k
                eff_pmax = u.get('p_max', 0)
                rc = ramp_maps[i]
                chosen = None
                for steps, val in rc:
                    if steps <= k:
                        chosen = val
                    else:
                        break
                if chosen is not None:
                    eff_pmax = min(eff_pmax, chosen)
                else:
                    # if no entry with steps<=k, then before first entry, no capacity? assume 0
                    # but reasonable to treat as 0 effective max
                    eff_pmax = 0
                p_min = u.get('p_min', 0)
                # if eff_pmax < p_min -> infeasible if on
                if eff_pmax + 1e-9 < p_min:
                    return float('inf')
                avail.append((u.get('cost_per_kwh', 0), i, p_min, eff_pmax))
        # Economic dispatch: sort by cost ascending
        avail.sort(key=lambda x: x[0])
        remaining = demand
        production = [0.0]*M
        # First ensure sum of p_min of selected on plants could be <= demand; but must assign >= p_min to any on plant
        # We must assign at least p_min to each on plant.
        total_pmin = sum(item[2] for item in avail)
        total_pmax = sum(item[3] for item in avail)
        # If demand not in [total_pmin..total_pmax] -> infeasible
        if remaining + 1e-9 < total_pmin or remaining > total_pmax + 1e-9:
            return float('inf')
        # Start by assigning p_min to all on plants
        for cost,i,pmin,pmax in avail:
            production[i] = pmin
            remaining -= pmin
        # Then allocate remaining to cheapest first up to p_max
        for cost,i,pmin,pmax in avail:
            if remaining <= 1e-9:
                break
            headroom = pmax - production[i]
            add = min(headroom, remaining)
            production[i] += add
            remaining -= add
        if abs(remaining) > 1e-6:
            return float('inf')
        # compute cost
        for cost,i,_,_ in avail:
            total_cost += production[i] * cost
    return total_cost