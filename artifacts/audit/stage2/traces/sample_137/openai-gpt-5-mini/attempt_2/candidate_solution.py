def _clamp_positive(x: float) -> float:
    if x is None:
        return 0.0
    if math.isfinite(x):
        return max(x, EPSILON)
    return 1e12

def _time_in_windows(t: float, windows: List[List[float]]) -> bool:
    for a, b in windows:
        if a - EPSILON <= t <= b + EPSILON:
            return True
    return False

def _next_open_time(t: float, windows: List[List[float]]) -> float:
    # If already open, return t. Else return earliest opening >= t (within MAX_WAIT_TIME)
    best = None
    for a, b in windows:
        if a - EPSILON <= t <= b + EPSILON:
            return t
        if a >= t - EPSILON:
            if best is None or a < best:
                best = a
    if best is None:
        # no future window today -> treat as closed beyond MAX_WAIT_TIME
        return float('inf')
    return best

def optimize_delivery_route(graph: dict, start: str, end: str, initial_energy: float) -> list:
    # Basic validation
    if start not in graph or end not in graph:
        return []
    # Handle trivial case start==end
    if start == end:
        # if no travel needed, just check station accessibility doesn't force failure
        return [start]
    # Preprocess nodes
    nodes = {}
    for n, data in graph.items():
        neigh = data.get('neighbors', [])
        sc = data.get('station_constraints', {})
        windows = sc.get('open_windows', [[0.0, 1e9]])
        # normalize windows as list of (float,float)
        w2 = []
        for w in windows:
            if len(w) >= 2:
                a = float(w[0]); b = float(w[1])
                if b < a:
                    continue
                w2.append((a, b))
        if not w2:
            w2 = [(0.0, 1e9)]
        nodes[n] = {
            'neighbors': [
                {
                    'node': e.get('node'),
                    'energy_cost': float(e.get('energy_cost', 0.0)),
                    'travel_time': float(e.get('travel_time', 0.0))
                } for e in neigh if 'node' in e
            ],
            'charge_rate': float(sc.get('charge_rate', 0.0)),
            'capacity': int(sc.get('capacity', 0)) if sc.get('capacity') is not None else 0,
            'open_windows': w2,
            'reservations': sc.get('reservations', [])  # optional future support
        }
    # Modified Dijkstra: state is (time_so_far, node, energy_remaining, path)
    # We minimize time. Energy must be >= 0 (with EPSILON).
    # We allow charging at nodes if needed and if station open/capacity>0
    initial_energy = float(initial_energy)
    initial_energy = min(initial_energy, MAX_ENERGY)
    pq = []
    # state visited: dict[node] -> best_energy_at_time bucketed -> min_time
    visited = {}
    def state_key(node, energy):
        # quantize energy to reduce state explosion
        return (node, round(energy, 6))
    heapq.heappush(pq, (0.0, start, initial_energy, [start], 0.0))  # (time, node, energy, path, cumulative_distance)
    iterations = 0
    best_goal = None
    best_goal_time = float('inf')
    while pq and iterations < ITERATION_LIMIT:
        iterations += 1
        time_so_far, node, energy, path, cumu = heapq.heappop(pq)
        if time_so_far - EPSILON > best_goal_time:
            continue
        key = state_key(node, energy)
        prev_t = visited.get(key)
        if prev_t is not None and prev_t + EPSILON <= time_so_far:
            continue
        visited[key] = time_so_far
        # If reached end
        if node == end:
            # feasible arrival
            if time_so_far + EPSILON < best_goal_time:
                best_goal_time = time_so_far
                best_goal = path
                # we continue to possibly find equal-time lesser-energy? but we can early prune
            continue
        # expand neighbors
        cur_node_data = nodes.get(node)
        if cur_node_data is None:
            continue
        for edge in cur_node_data['neighbors']:
            nbr = edge['node']
            travel_time = _clamp_positive(edge.get('travel_time', EPSILON))
            energy_cost = edge.get('energy_cost', 0.0)
            # handle negative energy regeneration with diminishing returns: cap per-edge effect
            # clamp invalid values
            if not math.isfinite(travel_time) or travel_time <= 0:
                travel_time = EPSILON
            if not math.isfinite(energy_cost):
                # treat as very large cost -> infeasible
                energy_cost = 1e12
            # variable energy based on time of day (simple smooth multiplier)
            # simulate multiplier: sin-based around 24h
            t_mid = (time_so_far % 24.0)
            # ramp between rush hours: 7-9 multiply 1.4, 17-19 multiply 1.3, night 0.8
            mult = 1.0
            if 6.5 <= t_mid <= 9.5:
                mult = 1.4
            elif 16.5 <= t_mid <= 19.5:
                mult = 1.3
            elif t_mid >= 22.0 or t_mid <= 6.0:
                mult = 0.85
            # smooth transition near edges
            # apply battery degradation: if cumu beyond threshold, increase cost
            degradation = 1.0
            if cumu > 100.0:
                degradation += 0.1 * ((cumu - 100.0) / 100.0)
            eff_energy_cost = energy_cost * mult * degradation
            # negative regeneration diminishing
            if eff_energy_cost < 0:
                eff_energy_cost *= 0.7
            # check energy feasibility: if not enough energy, attempt charging at current node before departing
            need_energy = eff_energy_cost
            energy_after = energy - need_energy
            depart_time = time_so_far
            wait_time = 0.0
            # If energy_after < -EPS, attempt to charge
            if energy_after < -EPSILON:
                sc = cur_node_data
                charge_rate = max(0.0, sc.get('charge_rate', 0.0))
                capacity = max(0, int(sc.get('capacity', 0)))
                windows = sc.get('open_windows', [(0.0, 1e9)])
                # if station closed now, find next window
                next_open = _next_open_time(depart_time, windows)
                if next_open == float('inf') or next_open - depart_time > MAX_WAIT_TIME + EPSILON:
                    continue  # cannot charge here feasibly
                # wait until open if needed
                if next_open > depart_time + EPSILON:
                    wait_time += next_open - depart_time
                    depart_time = next_open
                if capacity <= 0 or charge_rate <= EPSILON:
                    # cannot charge here
                    continue
                # compute required energy to cover deficit, but also consider max battery (set large)
                req = -energy_after
                # incorporate non-linear charging: diminishing as battery approaches cap (we don't have cap; assume MAX_ENERGY)
                # approximate time needed with integral effect -> add 10% overhead
                charge_time = req / charge_rate * 1.10
                if charge_time > MAX_WAIT_TIME + EPSILON:
                    continue
                wait_time += charge_time
                energy_after += req  # now should be >= 0
                depart_time += charge_time
            # ensure time windows at departure node permit leaving (some nodes restrict passage times)
            # if departure node is closed at depart_time, cannot leave until open
            if not _time_in_windows(depart_time, cur_node_data.get('open_windows', [(0.0, 1e9)])):
                next_open = _next_open_time(depart_time, cur_node_data.get('open_windows', [(0.0, 1e9)]))
                if next_open == float('inf') or next_open - depart_time > MAX_WAIT_TIME + EPSILON:
                    continue
                wait_add = next_open - depart_time
                depart_time = next_open
                wait_time += wait_add
            # simulate capacity queue probabilistic effect: if capacity small, add expected queue time
            cap = max(0, cur_node_data.get('capacity', 0))
            if cap == 0:
                # cannot charge here; but if we didn't need to charge it's fine
                if energy_after < -EPSILON:
                    continue
            elif cap == 1:
                # expect small queue factor
                wait_time += 0.05
                depart_time += 0.05
            # now simulate arrival
            arrival_time = depart_time + travel_time
            # arrival node must be reachable in window
            nbr_data = nodes.get(nbr)
            if nbr_data is None:
                continue
            # if arrival node is closed at arrival, we can wait (but limited)
            if not _time_in_windows(arrival_time, nbr_data.get('open_windows', [(0.0, 1e9)])):
                next_open_n = _next_open_time(arrival_time, nbr_data.get('open_windows', [(0.0, 1e9)]))
                if next_open_n == float('inf') or next_open_n - arrival_time > MAX_WAIT_TIME + EPSILON:
                    # cannot enter neighbor within allowed wait
                    continue
                # add waiting (which affects time but not energy)
                arrival_time = next_open_n
            # energy after travel may be slightly negative due to eps; clamp
            if energy_after < 0 and energy_after > -1e-6:
                energy_after = 0.0
            if energy_after < -EPSILON:
                continue
            # compute new cumulative distance for degradation model
            new_cumu = cumu + travel_time
            # prevent cycles with no improvement: if we revisit same node with less energy and more time, skip
            new_key = state_key(nbr, energy_after)
            prev_t2 = visited.get(new_key)
            if prev_t2 is not None and prev_t2 + EPSILON <= arrival_time:
                continue
            # guard iteration explosion
            if iterations > ITERATION_LIMIT:
                break
            new_path = path + [nbr]
            # push to pq
            heapq.heappush(pq, (arrival_time, nbr, energy_after, new_path, new_cumu))
        # Additionally consider charging in-place without moving to change energy/time state (useful for waiting for better time-of-day)
        sc = cur_node_data
        charge_rate = max(0.0, sc.get('charge_rate', 0.0))
        capacity = max(0, sc.get('capacity', 0))
        windows = sc.get('open_windows', [(0.0, 1e9)])
        # allow charging if capacity>0 and station open somewhere soon
        next_open = _next_open_time(time_so_far, windows)
        if charge_rate > EPSILON and capacity > 0 and next_open != float('inf'):
            depart = time_so_far
            if next_open > depart + EPSILON:
                wait = next_open - depart
                if wait <= MAX_WAIT_TIME + EPSILON:
                    depart = next_open
                else:
                    depart = None
            if depart is not None:
                # try small increments to avoid huge branching: simulate charging to fill to certain thresholds
                targets = [initial_energy, initial_energy * 1.5, initial_energy + 10.0, MAX_ENERGY]
                # also try minimal useful amount
                targets = list(dict.fromkeys([t for t in targets if t > energy + EPSILON]))
                for targ in targets[:3]:
                    req = max(0.0, min(targ - energy, MAX_ENERGY - energy))
                    if req <= EPSILON:
                        continue
                    # non-linear charging overhead
                    charge_time = req / charge_rate * 1.08
                    if charge_time > MAX_WAIT_TIME + EPSILON:
                        continue
                    new_time = depart + charge_time
                    new_energy = energy + req
                    if new_energy > MAX_ENERGY:
                        new_energy = MAX_ENERGY
                    new_key = state_key(node, new_energy)
                    prev_t3 = visited.get(new_key)
                    if prev_t3 is not None and prev_t3 + EPSILON <= new_time:
                        continue
                    new_path = list(path)
                    heapq.heappush(pq, (new_time, node, new_energy, new_path, cumu))
    if best_goal is None:
        return []
    return best_goal