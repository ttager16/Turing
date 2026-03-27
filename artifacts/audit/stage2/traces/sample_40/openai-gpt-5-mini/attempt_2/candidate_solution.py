def optimize_fleet_scheduling(
    cities: List[List[Union[str, int, int]]],
    vehicles: List[List[Union[int, int]]],
    traffic_data: Dict[str, int],
    demands: Optional[Dict[str, int]] = None,
    hub_capacity: Optional[Dict[str, int]] = None,
    updates: Optional[List[List[Union[str, Optional[int]]]]] = None,
    phases: Optional[List[Dict[str, int]]] = None
) -> Dict[str, VehicleEntry]:
    # Helper parse
    city_windows = {}
    city_list = []
    for c in cities:
        name = c[0]
        start_h = float(c[1])
        end_h = float(c[2])
        city_windows[name] = (int(start_h*60), int(end_h*60))
        city_list.append(name)
    city_set = set(city_list)

    # Apply updates deterministically: sort by route key; removals (None) before additions/changes
    if updates:
        sorted_updates = sorted(updates, key=lambda x: (x[0], 0 if x[1] is None else 1))
        for key, val in sorted_updates:
            if val is None:
                if key in traffic_data:
                    del traffic_data[key]
            else:
                traffic_data[key] = int(val)

    # Build adjacency
    adj = defaultdict(list)
    for k, t in traffic_data.items():
        if '-' in k:
            a, b = k.split('-', 1)
            if a in city_set and b in city_set and isinstance(t, int) and t >= 0:
                adj[a].append((b, t))

    # Vehicles sorted by (capacity, id)
    vehicles_sorted = sorted(vehicles, key=lambda x: (int(x[1]), int(x[0])))

    # Candidate routes: single-city stays and shortest paths between ordered pairs
    # Dijkstra for each source to get shortest paths and times and parents
    def dijkstra(src):
        dist = {src: 0}
        prev = {}
        pq = [(0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d != dist.get(u, None):
                continue
            for v, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, 10**18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    shortest_paths = {}
    parents = {}
    for src in city_list:
        dist, prev = dijkstra(src)
        shortest_paths[src] = dist
        parents[src] = prev

    def reconstruct_path(src, dst, prev):
        if dst == src:
            return [src]
        if dst not in prev:
            return None
        path = []
        cur = dst
        while cur != src:
            path.append(cur)
            cur = prev.get(cur)
            if cur is None:
                return None
        path.append(src)
        path.reverse()
        return path

    # Fuel cost formula
    def fuel_cost(minutes, capacity):
        if minutes <= 0:
            return 0
        base_rate = 0.1
        eff = 1.0 + capacity / 200.0
        cost = base_rate * minutes * eff
        cost_int = int(cost)
        if cost_int < 1:
            cost_int = 1
        return cost_int

    # Route value
    def route_value(num_cities, fuelc):
        return 10 * num_cities - fuelc

    # Generate candidate options per vehicle: up to 30 after scoring
    all_candidates = {}
    for v in vehicles_sorted:
        vid, cap = int(v[0]), int(v[1])
        cand = []
        # single-city stays
        for city in city_list:
            travel = 0
            fuel = fuel_cost(travel, cap)
            val = route_value(1, fuel)
            cand.append((val, travel, [city], fuel))
        # shortest paths between ordered pairs
        for src in city_list:
            dist = shortest_paths.get(src, {})
            prev = parents.get(src, {})
            for dst, t in dist.items():
                if dst == src:
                    continue
                path = reconstruct_path(src, dst, prev)
                if not path:
                    continue
                travel = t
                fuel = fuel_cost(travel, cap)
                val = route_value(len(path), fuel)
                cand.append((val, travel, path, fuel))
        # sort by value desc then travel asc then lex path
        cand_sorted = sorted(cand, key=lambda x: (-x[0], x[1], x[2]))
        cand_trunc = cand_sorted[:30]
        all_candidates[vid] = cand_trunc

    # Decide small or large instance
    small_instance = (len(city_list) <= 18 and len(vehicles_sorted) <= 12)

    assigned = {}  # vid -> chosen tuple (val, travel, path, fuel)
    used_cities = set()
    # If demands or phases present, multiple vehicles may serve same city; else restrict to at most one per city
    allow_multi_city = bool(demands) or bool(phases)

    if small_instance:
        # Dynamic programming: for each vehicle independently choose best route respecting non-overlap of cities if not allow_multi_city
        # We'll perform simple DP assigning vehicles in order, respecting used_cities constraint
        # DP state: index of vehicle, frozenset of used cities -> total value and assignment
        vlist = [int(v[0]) for v in vehicles_sorted]
        cand_map = all_candidates

        from functools import lru_cache

        @lru_cache(None)
        def dp(i, used_key):
            used = set(used_key.split('|')) if used_key else set()
            if i >= len(vlist):
                return 0, {}
            vid = vlist[i]
            best_total = -10**18
            best_assign = {}
            # Try each candidate including empty route
            # empty route
            val0 = 0
            total0, assign0 = dp(i+1, '|'.join(sorted(used)) if used else '')
            best_total = total0
            best_assign = dict(assign0)
            best_assign[vid] = (0, 0, [], 0)
            for cand in cand_map[vid]:
                val, travel, path, fuel = cand
                path_cities = set(path)
                if not allow_multi_city and used & path_cities:
                    continue
                new_used = used | path_cities
                new_used_key = '|'.join(sorted(new_used)) if new_used else ''
                sub_total, sub_assign = dp(i+1, new_used_key)
                total = val + sub_total
                if total > best_total:
                    best_total = total
                    best_assign = dict(sub_assign)
                    best_assign[vid] = (val, travel, path, fuel)
            return best_total, best_assign

        _, final_assign = dp(0, '')
        for vid in final_assign:
            assigned[vid] = final_assign[vid]
    else:
        # Greedy heuristic: process vehicles in ascending (capacity,id) order already sorted
        for v in vehicles_sorted:
            vid, cap = int(v[0]), int(v[1])
            chosen = None
            for cand in all_candidates[vid]:
                val, travel, path, fuel = cand
                path_cities = set(path)
                if not allow_multi_city and (used_cities & path_cities):
                    continue
                chosen = cand
                break
            if chosen is None:
                assigned[vid] = (0, 0, [], 0)
            else:
                assigned[vid] = chosen
                if not allow_multi_city:
                    used_cities.update(chosen[2])

    # Across phases, vehicle's first chosen route persists. If phases provided, we ignore reassigning.
    # Build schedules: arrival times considering time windows. Start at max(0, start_window) of first city.
    result = {}
    for v in vehicles_sorted:
        vid, cap = int(v[0]), int(v[1])
        key = f"Vehicle{vid}"
        val, travel, path, fuel = assigned.get(vid, (0,0,[],0))
        travel_time = int(travel)
        fuel_c = int(fuel)
        entry = {'Route': path.copy(), 'TravelTime': travel_time, 'FuelCost': fuel_c}
        if path:
            schedule = []
            # arrival at first city is max(0, start_window)
            first = path[0]
            start_min = max(0, city_windows.get(first, (0, 24*60))[0])
            arrival = start_min
            schedule.append([first, round(arrival/60.0, 2)])
            # traverse edges along path
            for i in range(len(path)-1):
                a = path[i]; b = path[i+1]
                keyedge = f"{a}-{b}"
                tt = traffic_data.get(keyedge)
                if tt is None:
                    # If no direct edge (shouldn't happen), set large and break
                    tt = shortest_paths.get(a, {}).get(b, 0)
                arrival += int(tt)
                # enforce city window: arrival must be at least start window
                start_w = city_windows.get(b, (0, 24*60))[0]
                if arrival < start_w:
                    arrival = start_w
                schedule.append([b, round(arrival/60.0, 2)])
            entry['Schedule'] = schedule
        else:
            entry['Schedule'] = []
        result[key] = entry

    # Ensure deterministic order of keys not required but content deterministic
    return result