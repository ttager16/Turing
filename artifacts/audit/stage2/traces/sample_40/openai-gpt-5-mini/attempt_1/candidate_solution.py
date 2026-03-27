def optimize_fleet_scheduling(
    cities: List[List[Union[str, int, int]]],
    vehicles: List[List[Union[int, int]]],
    traffic_data: Dict[str, int],
    demands: Optional[Dict[str, int]] = None,
    hub_capacity: Optional[Dict[str, int]] = None,
    updates: Optional[List[List[Union[str, Optional[int]]]]] = None,
    phases: Optional[List[Dict[str, int]]] = None
) -> Dict[str, VehicleEntry]:
    # Normalize inputs
    city_windows: Dict[str, Tuple[int,int]] = {}
    city_list = []
    for name, s, e in cities:
        city_list.append(name)
        city_windows[name] = (int(s*60), int(e*60))  # hours->minutes
    # Apply updates deterministically: removals before additions/changes, order by key
    if updates:
        # group by key, process None removals first
        updates_sorted = sorted(updates, key=lambda x: (x[0], 0 if x[1] is None else 1))
        for key, val in updates_sorted:
            if val is None:
                traffic_data.pop(key, None)
            else:
                traffic_data[key] = int(val)
    # Build directed graph adjacency
    adj = defaultdict(list)
    for k,v in traffic_data.items():
        if '-' in k:
            a,b = k.split('-',1)
            if isinstance(v,int) and v>=0:
                adj[a].append((b,int(v)))
    # Helper: shortest path times and parents using Dijkstra
    def dijkstra(src):
        dist = {src:0}
        prev = {}
        h = [(0,src)]
        while h:
            d,u = heapq.heappop(h)
            if d!=dist[u]: continue
            for v,w in adj.get(u,[]):
                nd = d + w
                if v not in dist or nd < dist[v]:
                    dist[v]=nd
                    prev[v]=u
                    heapq.heappush(h,(nd,v))
        return dist, prev
    # reconstruct path
    def path_from(prev, src, dst):
        if dst==src: return [src]
        if dst not in prev and dst!=src: 
            return None
        cur=dst
        p=[cur]
        while cur!=src:
            cur=prev.get(cur)
            if cur is None:
                return None
            p.append(cur)
        return list(reversed(p))
    # fuel cost formula
    def fuel_cost(minutes, capacity):
        if minutes<=0: return 0
        base_rate=0.1
        eff = 1 + capacity/200.0
        cost = base_rate * minutes * eff
        c = int(cost)  # truncation
        if c<1: c=1
        return c
    # Candidate routes per vehicle: single-city stays + shortest paths between ordered pairs
    # Precompute all-pairs shortest paths for cities present
    all_prev = {}
    all_dist = {}
    for c in city_list:
        d,p = dijkstra(c)
        all_dist[c]=d
        all_prev[c]=p
    # Build candidate list per vehicle (same for all, capacity only affects scoring)
    candidate_routes = {}
    # Candidate routes are limited to single-city stay and shortest paths between ordered city pairs where reachable
    routes = []
    for src in city_list:
        # single stay
        routes.append([src])
        for dst in city_list:
            if src==dst: continue
            if dst in all_dist[src]:
                p = path_from(all_prev[src], src, dst)
                if p:
                    routes.append(p)
    # deduplicate
    uniq = []
    seen = set()
    for r in routes:
        key = tuple(r)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    routes = uniq
    # scoring function per vehicle
    def route_value(route, capacity):
        # number_of_cities_visited counts unique cities visited
        num = len(route)
        # travel time sum along path edges
        tt = 0
        for i in range(len(route)-1):
            a,b = route[i], route[i+1]
            # find edge time
            found = None
            for v,w in adj.get(a,[]):
                if v==b:
                    found=w; break
            if found is None:
                tt += 0
            else:
                tt += found
        fc = fuel_cost(tt, capacity)
        val = 10 * num - fc
        return val, tt, fc
    # Prepare vehicles sorted ascending by (capacity, id)
    vehicles_sorted = sorted([(int(v[1]), int(v[0])) for v in vehicles], key=lambda x:(x[0], x[1]))
    # limit candidates per vehicle to top 30 by value
    def top_routes_for_capacity(cap):
        scored = []
        for r in routes:
            val,tt,fc = route_value(r, cap)
            scored.append(( -val, r, tt, fc, val))
        scored.sort()
        res=[]
        for i,item in enumerate(scored[:30]):
            _, r, tt, fc, val = item
            res.append((r, tt, fc, val))
        return res
    # Decide DP vs greedy
    small_instance = (len(city_list) <= 18 and len(vehicles_sorted) <= 12)
    assigned = {}  # vehicleid -> (route, tt, fc)
    used_cities = set()
    # phases handling: if phases provided, vehicles keep first chosen route across phases; demands/hub_capacity allow multiple vehicles per city
    vehicle_persistent = {}
    # If small: DP over subset of cities per vehicle? We'll implement simplified DP: for each vehicle choose best route not conflicting with already chosen cities (unless demands or phases present)
    if small_instance:
        # brute force per vehicle order (capacity,id) choose best combination via DP across vehicles to maximize sum of route_values with conflict constraint (no city visited by more than one vehicle unless demands or phases)
        n = len(vehicles_sorted)
        cap_ids = vehicles_sorted
        # precompute top candidates per vehicle
        cand_list = []
        for cap, vid in cap_ids:
            cands = top_routes_for_capacity(cap)
            # include empty route
            cands = [ ([], 0, 0, 0) ] + cands
            cand_list.append(cands)
        # DP by iterative map of used_cities set bitmask is infeasible; instead backtracking with pruning
        best_assign = {}
        best_score = -10**9
        def backtrack(i, used, score, assign):
            nonlocal best_score, best_assign
            if i==n:
                if score>best_score:
                    best_score=score
                    best_assign=assign.copy()
                return
            cap, vid = cap_ids[i]
            for r,tt,fc,val in cand_list[i]:
                cities_in = set(r)
                conflict = False
                if (demands or phases or demands is not None):
                    conflict = False
                else:
                    if used & set(cities_in):
                        conflict = True
                if conflict:
                    continue
                assign[vid]=(r,tt,fc,val)
                backtrack(i+1, used | set(cities_in), score+val, assign)
                assign.pop(vid,None)
            # also option to assign none already covered by empty candidate
        backtrack(0, set(), 0, {})
        # fill assigned
        for cap,vid in cap_ids:
            if vid in best_assign:
                r,tt,fc,_ = best_assign[vid]
                assigned[vid]=(r,tt,fc)
            else:
                assigned[vid]=([],0,0)
    else:
        # greedy heuristic: process vehicles in ascending (capacity,id), pick highest-value non-overlapping candidate route; if none, empty
        for cap, vid in vehicles_sorted:
            cands = top_routes_for_capacity(cap)
            chosen = None
            for r,tt,fc,val in sorted(cands, key=lambda x:-x[3]):
                cities_in = set(r)
                if not (demands or phases or demands is not None):
                    if used_cities & cities_in:
                        continue
                chosen = (r,tt,fc,val)
                break
            if chosen:
                r,tt,fc,_ = chosen
                assigned[vid]=(r,tt,fc)
                if not (demands or phases or demands is not None):
                    used_cities |= set(r)
            else:
                assigned[vid]=([],0,0)
    # Build schedules: arrival times: initial arrival at max(0, start_window). For a route, starting city arrival is its window start or 0, but spec: initial arrival is max(0, start_window)
    output: Dict[str, VehicleEntry] = {}
    for cap, vid in vehicles_sorted:
        r, tt, fc = assigned.get(vid, ([],0,0))
        entry = VehicleEntry()
        entry['Route']=r.copy()
        entry['TravelTime']=int(tt)
        entry['FuelCost']=int(fc)
        # build schedule
        sched = []
        if not r:
            entry['Schedule']=[]
        else:
            # start at first city's window start (in minutes) or 0
            cur_time = max(0, city_windows.get(r[0], (0,0))[0])
            sched.append([r[0], round(cur_time/60.0,2)])
            for i in range(len(r)-1):
                a,b = r[i], r[i+1]
                edge_time = None
                for v,w in adj.get(a,[]):
                    if v==b:
                        edge_time=w; break
                if edge_time is None:
                    edge_time = 0
                cur_time += edge_time
                # upon arrival may need to wait until window start
                win = city_windows.get(b,(0,0))
                arr = max(cur_time, win[0])
                cur_time = arr
                sched.append([b, round(cur_time/60.0,2)])
        entry['Schedule']=sched
        output[f"Vehicle{vid}"]=entry
    # Ensure vehicles not in vehicles_sorted (shouldn't happen) are included as empty
    existing = set(v for _,v in vehicles_sorted)
    for v in vehicles:
        vid = int(v[0])
        if vid not in existing:
            output[f"Vehicle{vid}"] = VehicleEntry({'Route':[],'TravelTime':0,'FuelCost':0,'Schedule':[]})
    return output