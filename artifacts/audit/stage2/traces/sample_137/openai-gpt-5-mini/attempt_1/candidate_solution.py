def _clamp_positive(x: float, minv: float = 1e-6) -> float:
    if x <= 0.0:
        return minv
    return x

def _time_in_windows(t: float, windows: List[List[float]]) -> bool:
    for a, b in windows:
        if a - EPSILON <= t <= b + EPSILON:
            return True
    return False

def _next_open_time(t: float, windows: List[List[float]]) -> float:
    # returns t if already open, else earliest open >= t, or inf
    best = math.inf
    for a, b in windows:
        if a - EPSILON <= t <= b + EPSILON:
            return t
        if a > t and a < best:
            best = a
    return best

def _energy_multiplier_time_of_day(t: float) -> float:
    # simple smooth transitions for rush/off-peak:
    # rush 7-9 cost 1.5x, off-peak 22-6 cost 0.8x, linear ramps 1 hour
    day_t = t % 24.0
    def ramp(center, width, low, high):
        # triangular ramp centered at center, total width
        half = width / 2.0
        d = abs((day_t - center + 12) % 24 - 12)
        if d >= half:
            return low
        return low + (high - low) * (1 - d / half)
    mult = 1.0
    mult = max(mult, ramp(8.0, 2.0, 1.0, 1.5))   # rush 7-9
    # off-peak centered at 2 (22-6)
    mult = min(mult, ramp(2.0, 8.0, 0.8, 1.0))
    return mult

def optimize_delivery_route(graph: dict, start: str, end: str, initial_energy: float) -> list:
    # Basic validation
    if start not in graph or end not in graph:
        return []
    if start == end:
        # If same node, check if station_constraints require anything (none for travel)
        return [start]
    # Normalize graph entries
    for n, v in graph.items():
        if 'neighbors' not in v:
            v['neighbors'] = []
        if 'station_constraints' not in v:
            v['station_constraints'] = {'charge_rate': 0.0, 'capacity': 0, 'open_windows': [[0, 24]]}
        sc = v['station_constraints']
        sc.setdefault('charge_rate', 0.0)
        sc.setdefault('capacity', 0)
        sc.setdefault('open_windows', [[0, 24]])
    initial_energy = min(max(initial_energy, 0.0), MAX_ENERGY)

    # State: (time_so_far, node, energy_remaining, path_list, battery_degradation_factor)
    # Use priority queue by time
    heap = []
    start_state = (0.0, start, float(initial_energy), tuple([start]), 1.0, 0.0)  # last: cumulative_distance or usage proxy
    heapq.heappush(heap, (0.0, start_state))
    # visited: dict of node -> list of (rounded_time, energy, degr) best known to prune
    visited = dict()
    iterations = 0

    while heap and iterations < ITERATION_LIMIT:
        iterations += 1
        _, (cur_time, node, energy, path, degr, usage) = heapq.heappop(heap)
        # prune by visited
        key = (node)
        tkey = round(cur_time, 6)
        recs = visited.setdefault(key, {})
        prev_e = recs.get(tkey)
        if prev_e is not None and prev_e + EPSILON >= energy:
            continue
        recs[tkey] = energy

        if node == end:
            return list(path)

        node_data = graph.get(node, {})
        sc = node_data.get('station_constraints', {})
        windows = sc.get('open_windows', [[0,24]])
        charge_rate = sc.get('charge_rate', 0.0)
        capacity = sc.get('capacity', 0)

        # Option 1: try to depart immediately along neighbors if energy allows
        for nb in node_data.get('neighbors', []):
            nnode = nb['node']
            # validate values
            ecost = float(nb.get('energy_cost', 0.0))
            tcost = float(nb.get('travel_time', 0.0))
            ecost = _clamp_positive(ecost)
            tcost = _clamp_positive(tcost)
            # dynamic multipliers
            mult = _energy_multiplier_time_of_day(cur_time)
            ecost_adj = ecost * mult * degr
            # battery degradation rule: increase degr after usage threshold (simulate)
            new_usage = usage + ecost_adj
            new_degr = degr
            if new_usage > 100.0:
                # degrade by 10% after each 100 units
                steps = int(new_usage // 100)
                new_degr = degr * (1.0 + 0.10 * steps)
            # check if energy suffices
            if energy + EPSILON >= ecost_adj:
                arrive_time = cur_time + tcost
                arrive_energy = energy - ecost_adj
                # check arrival node windows and capacity (we assume capacity affects charging, not entry)
                # push state
                new_path = path + (nnode,)
                heapq.heappush(heap, (arrive_time, (arrive_time, nnode, arrive_energy, new_path, new_degr, new_usage)))
            else:
                # need to consider charging here before departing
                # can we charge at this node? must be within open window and capacity>0
                if capacity <= 0 or charge_rate <= EPSILON:
                    # cannot charge here, skip this neighbor via charging
                    continue
                # compute earliest time charging can occur (station open)
                open_t = _next_open_time(cur_time, windows)
                if open_t == math.inf or open_t - cur_time > MAX_WAIT_TIME + EPSILON:
                    continue
                wait_time = max(0.0, open_t - cur_time)
                # try charging enough energy to make ecost_adj reachable
                needed = ecost_adj - energy
                # clamp
                needed = max(0.0, needed)
                # account for non-linear charging curve: diminishing when near max battery
                # simple model: effective_charge_rate = charge_rate * (1 - energy/MAX_ENERGY)^2
                def charge_time_for(amount, start_energy):
                    if amount <= EPSILON:
                        return 0.0
                    # integrate approximate diminishing returns by incremental approach
                    e = start_energy
                    rem = amount
                    dt = 0.0
                    steps = 0
                    while rem > EPSILON and steps < 1000:
                        eff = charge_rate * max(0.0, (1.0 - e / MAX_ENERGY))**2
                        eff = max(eff, 1e-6)
                        take = min(rem, eff * 0.1)
                        dt += take / eff
                        e += take
                        rem -= take
                        steps += 1
                    return dt
                # limit charging to MAX_WAIT_TIME
                charge_t = charge_time_for(needed, energy)
                if wait_time + charge_t > MAX_WAIT_TIME + EPSILON:
                    # maybe partial charge to reach minimal viable (clamp)
                    # skip if cannot reach
                    continue
                depart_time = cur_time + wait_time + charge_t
                depart_energy = min(MAX_ENERGY, energy + needed)
                # consume edge
                arrive_time = depart_time + tcost
                arrive_energy = depart_energy - ecost_adj
                new_path = path + (nnode,)
                heapq.heappush(heap, (arrive_time, (arrive_time, nnode, arrive_energy, new_path, new_degr, new_usage)))

        # Option 2: optionally wait/charge at current node without moving, to improve future options
        if capacity > 0 and charge_rate > EPSILON:
            # attempt discrete waits: small increments up to MAX_WAIT_TIME
            increments = [0.25, 0.5, 1.0, 2.0, 4.0]  # hours
            for inc in increments:
                if inc > MAX_WAIT_TIME + EPSILON:
                    continue
                new_time = cur_time + inc
                if new_time - cur_time > MAX_WAIT_TIME + EPSILON:
                    continue
                # check windows: must be in open window for charging during interval midpoint
                mid = (cur_time + new_time) / 2.0
                if not _time_in_windows(mid, windows):
                    # can only wait until next open
                    next_open = _next_open_time(cur_time, windows)
                    if next_open == math.inf or next_open - cur_time > MAX_WAIT_TIME + EPSILON:
                        continue
                    # schedule to next_open then small charge
                    new_time = next_open + inc
                    mid = (cur_time + new_time) / 2.0
                    if not _time_in_windows(mid, windows):
                        continue
                # approximate charged energy over inc with non-linear curve
                e = energy
                gained = 0.0
                dt = inc
                # simple numeric approx: split into 10 steps
                steps = 10
                for i in range(steps):
                    eff = charge_rate * max(0.0, (1.0 - e / MAX_ENERGY))**2
                    eff = max(eff, 1e-6)
                    de = eff * (dt / steps)
                    gained += de
                    e += de
                    if e >= MAX_ENERGY:
                        e = MAX_ENERGY
                        break
                new_energy = min(MAX_ENERGY, energy + gained)
                if new_energy > energy + EPSILON:
                    heapq.heappush(heap, (new_time, (new_time, node, new_energy, path, degr, usage)))
        else:
            # Option: wait for station to open if it's currently closed and waiting may help due to time-of-day costs
            next_open = _next_open_time(cur_time, windows)
            if next_open != math.inf and 0.0 < next_open - cur_time <= MAX_WAIT_TIME + EPSILON:
                heapq.heappush(heap, (next_open, (next_open, node, energy, path, degr, usage)))

    return []