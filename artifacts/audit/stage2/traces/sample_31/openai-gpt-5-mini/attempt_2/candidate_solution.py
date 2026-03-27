def __init__(self):
        self.adj = defaultdict(list)
        self.cap = {}
        self.cost = {}
        self.flow = {}
        self.nodes = set()

    def add_edge(self, u, v, capacity, cost):
        if capacity <= 0:
            return
        self.nodes.add(u); self.nodes.add(v)
        self.adj[u].append(v)
        self.adj[v].append(u)
        self.cap[(u, v)] = capacity
        self.cap[(v, u)] = self.cap.get((v, u), 0)
        self.cost[(u, v)] = cost
        self.cost[(v, u)] = -cost
        self.flow[(u, v)] = 0
        self.flow[(v, u)] = 0

    def bellman_ford(self, s):
        dist = {node: float('inf') for node in self.nodes}
        dist[s] = 0
        for _ in range(len(self.nodes) - 1):
            updated = False
            for u in list(self.nodes):
                if dist[u] == float('inf'): continue
                for v in self.adj[u]:
                    if (u, v) in self.cost:
                        if dist[v] > dist[u] + self.cost[(u, v)]:
                            dist[v] = dist[u] + self.cost[(u, v)]
                            updated = True
            if not updated:
                break
        potential = {node: (dist[node] if dist[node] < float('inf') else 0) for node in self.nodes}
        return potential

    def min_cost_flow(self, s, t, maxf=float('inf')):
        flow = 0
        cost = 0
        potential = self.bellman_ford(s)
        while flow < maxf:
            dist = {node: float('inf') for node in self.nodes}
            prev = {}
            dist[s] = 0
            heap = [(0, s)]
            visited = set()
            while heap:
                d, u = heapq.heappop(heap)
                if u in visited: continue
                visited.add(u)
                for v in self.adj[u]:
                    cap = self.cap.get((u, v), 0)
                    f = self.flow.get((u, v), 0)
                    if cap - f <= 0:
                        continue
                    rcost = self.cost[(u, v)] + potential.get(u, 0) - potential.get(v, 0)
                    nd = dist[u] + rcost
                    if nd < dist[v]:
                        dist[v] = nd
                        prev[v] = u
                        heapq.heappush(heap, (nd, v))
            if dist.get(t, float('inf')) == float('inf'):
                break
            for node in self.nodes:
                if dist.get(node, float('inf')) < float('inf'):
                    potential[node] = potential.get(node, 0) + dist[node]
            increment = maxf - flow
            v = t
            while v != s:
                u = prev[v]
                residual = self.cap[(u, v)] - self.flow[(u, v)]
                if residual < increment:
                    increment = residual
                v = u
            v = t
            while v != s:
                u = prev[v]
                self.flow[(u, v)] += increment
                self.flow[(v, u)] -= increment
                cost += self.cost[(u, v)] * increment
                v = u
            flow += increment
        return flow, cost

class SegmentTree:
    def __init__(self, n):
        self.n = n
        if n <= 0:
            self.tree = []
            self.lazy = []
            return
        self.size = 4 * n
        self.tree = [0] * self.size
        self.lazy = [0] * self.size

    def _push(self, node):
        if self.lazy[node] != 0:
            for child in (2*node, 2*node+1):
                self.tree[child] += self.lazy[node]
                self.lazy[child] += self.lazy[node]
            self.lazy[node] = 0

    def _update(self, node, l, r, ql, qr, val):
        if self.n == 0: return
        if ql > r or qr < l:
            return
        if ql <= l and r <= qr:
            self.tree[node] += val
            self.lazy[node] += val
            return
        self._push(node)
        mid = (l + r) // 2
        self._update(2*node, l, mid, ql, qr, val)
        self._update(2*node+1, mid+1, r, ql, qr, val)
        self.tree[node] = min(self.tree[2*node], self.tree[2*node+1])

    def update(self, ql, qr, val):
        if self.n == 0: return
        ql = max(0, ql); qr = min(self.n-1, qr)
        if ql > qr: return
        self._update(1, 0, self.n-1, ql, qr, val)

    def _query(self, node, l, r, ql, qr):
        if self.n == 0: return float('inf')
        if ql > r or qr < l:
            return float('inf')
        if ql <= l and r <= qr:
            return self.tree[node]
        self._push(node)
        mid = (l + r) // 2
        return min(self._query(2*node, l, mid, ql, qr),
                   self._query(2*node+1, mid+1, r, ql, qr))

    def query(self, ql, qr):
        if self.n == 0: return float('inf')
        ql = max(0, ql); qr = min(self.n-1, qr)
        if ql > qr: return float('inf')
        return self._query(1, 0, self.n-1, ql, qr)

def optimize_ev_charging_schedule(traffic_data: list, ev_data: list, station_data: list) -> list:
    if not ev_data or not station_data:
        return []
    traffic_map = {loc: cong for loc, cong in traffic_data}
    station_map = {s['id']: s for s in station_data}
    ev_map = {e['id']: e for e in ev_data}
    max_time_horizon = 1000
    station_segment_trees = {}
    station_occupancy = {}
    for s in station_data:
        sid = s['id']
        station_occupancy[sid] = 0
        station_segment_trees[sid] = SegmentTree(max_time_horizon)
    feasible_exists = False
    # Priority queue
    heap = []
    for ev in ev_data:
        if ev['location_id'] not in traffic_map:
            continue
        # feasible nearby filter
        nearby = []
        for s in station_data:
            if abs(ev['location_id'] - s['location_id']) <= 5:
                nearby.append(s)
        if not nearby:
            continue
        feasible_exists = True
        lvl = ev['battery_level']
        if lvl < 20:
            p = 0
        elif lvl < 50:
            p = 1
        elif lvl < 80:
            p = 2
        else:
            p = 3
        heapq.heappush(heap, (p, ev['id'], ev))
    if not feasible_exists:
        return []
    # Build flow graph
    G = FlowGraph()
    src = 'source'; sink = 'sink'
    for _, ev_id, ev in heap:
        ev_node = f"ev_{ev_id}"
        G.add_edge(src, ev_node, 1, 0)
    for s in station_data:
        sid = s['id']
        eff_cap = s['capacity']
        # compute peak hour effect by station location congestion
        cong = traffic_map.get(s['location_id'], 0)
        if cong > 7:
            eff_cap = int(eff_cap * 0.6)
        if eff_cap <= 0:
            continue
        G.add_edge(f"station_{sid}", sink, eff_cap, 0)
    # EV to station edges with costs
    for _, ev_id, ev in heap:
        ev_node = f"ev_{ev_id}"
        ev_loc = ev['location_id']
        if ev_loc not in traffic_map:
            continue
        cong_ev = traffic_map[ev_loc]
        for s in station_data:
            if abs(ev_loc - s['location_id']) > 5:
                continue
            if s['location_id'] not in traffic_map:
                continue
            cong_station = traffic_map[s['location_id']]
            distance = abs(ev_loc - s['location_id'])
            if distance > 5:
                continue
            travel_time = distance * (1 + cong_station / 10)
            arrival_time = int(travel_time)
            duration = int(ev['desired_charge'] / s['max_power']) if s['max_power'] > 0 else 0
            if arrival_time + duration > 500:
                continue
            # dynamic cost
            base_cost = 1
            # capacity ratio
            cap = s['capacity']
            cap_eff = int(cap * 0.6) if traffic_map.get(s['location_id'],0) > 7 else cap
            cap_ratio = 0.0
            if cap > 0:
                cap_ratio = min(1.0, station_occupancy[s['id']] / cap)
            if cap_ratio >= 0.9:
                c = base_cost * 3
            elif cap_ratio >= 0.6:
                c = base_cost * 2
            else:
                c = base_cost
            if ev['battery_level'] < 20:
                c *= 0.1
            if ev['battery_level'] > 80:
                c *= 2.0
            total_cost = c + travel_time
            scaled = int(total_cost * 100)
            G.add_edge(ev_node, f"station_{s['id']}", 1, scaled)
    # Run flow
    flow, _ = G.min_cost_flow(src, sink)
    if flow == 0:
        return []
    # Extract assignments from flows
    assignments = {}
    for (u, v), fval in list(G.flow.items()):
        if fval > 0 and u.startswith("ev_") and v.startswith("station_"):
            ev_id = u.split("_",1)[1]
            sid = v.split("_",1)[1]
            assignments[ev_id] = {'station_id': sid}
    # Time slot allocation using segment trees, process by priority order
    result = []
    processing = []
    while heap:
        processing.append(heapq.heappop(heap))
    processing.sort()  # ensures priority order
    for p, ev_id, ev in processing:
        if ev_id not in assignments:
            continue
        sid = assignments[ev_id]['station_id']
        s = station_map[sid]
        ev_loc = ev['location_id']
        if ev_loc not in traffic_map:
            continue
        cong_station = traffic_map.get(s['location_id'], 0)
        distance = abs(ev_loc - s['location_id'])
        travel_time = distance * (1 + cong_station / 10)
        arrival_time = int(travel_time)
        duration = int(ev['desired_charge'] / s['max_power']) if s['max_power'] > 0 else 0
        seg = station_segment_trees[sid]
        start_time = None
        attempts = 0
        t = arrival_time
        while attempts < 50 and t <= arrival_time + 500:
            if duration == 0:
                if seg.query(t, t) >= 0:
                    start_time = t
                    break
            else:
                if seg.query(t, t+duration-1) >= 0:
                    start_time = t
                    break
            attempts += 1
            t += 1
        if start_time is None:
            # fallback unscheduled
            continue
        # apply occupancy and segment tree update
        if duration > 0:
            seg.update(start_time, start_time+duration-1, 1)
        station_occupancy[sid] += 1
        result.append({'ev_id': ev_id, 'station_id': sid, 'start_time': start_time})
    if not result:
        return []
    # Iterative refinement: 2 iterations
    for _ in range(2):
        improved = False
        for i, assign in enumerate(list(result)):
            ev_id = assign['ev_id']
            current_sid = assign['station_id']
            ev = ev_map[ev_id]
            cur_start = assign['start_time']
            s_cur = station_map[current_sid]
            duration_cur = int(ev['desired_charge'] / s_cur['max_power']) if s_cur['max_power']>0 else 0
            # remove current assignment temporarily
            if duration_cur > 0:
                station_segment_trees[current_sid].update(cur_start, cur_start+duration_cur-1, -1)
            station_occupancy[current_sid] = max(0, station_occupancy[current_sid]-1)
            best_option = (None, None, None)  # sid, start_time, cost
            # evaluate alternatives
            for s in station_data:
                sid = s['id']
                if abs(ev['location_id'] - s['location_id']) > 5:
                    continue
                if s['location_id'] not in traffic_map:
                    continue
                cong_station = traffic_map[s['location_id']]
                distance = abs(ev['location_id'] - s['location_id'])
                travel_time = distance * (1 + cong_station / 10)
                arrival_time = int(travel_time)
                duration = int(ev['desired_charge'] / s['max_power']) if s['max_power']>0 else 0
                if arrival_time + duration > 500:
                    continue
                seg = station_segment_trees[sid]
                t = arrival_time
                attempts = 0
                found_start = None
                while attempts < 50 and t <= arrival_time + 500:
                    if duration == 0:
                        if seg.query(t, t) >= 0:
                            found_start = t; break
                    else:
                        if seg.query(t, t+duration-1) >= 0:
                            found_start = t; break
                    attempts += 1
                    t += 1
                if found_start is None:
                    continue
                # cost estimate similar to before
                base_cost = 1
                cap_ratio = 0.0
                cap = s['capacity']
                if cap > 0:
                    cap_ratio = min(1.0, station_occupancy[sid] / cap)
                if cap_ratio >= 0.9:
                    c = base_cost * 3
                elif cap_ratio >= 0.6:
                    c = base_cost * 2
                else:
                    c = base_cost
                if ev['battery_level'] < 20:
                    c *= 0.1
                if ev['battery_level'] > 80:
                    c *= 2.0
                total_cost = c + travel_time
                if best_option[0] is None or total_cost < best_option[2]:
                    best_option = (sid, found_start, total_cost)
            # compute current cost
            s = s_cur
            cong_station = traffic_map.get(s['location_id'], 0)
            travel_time_cur = abs(ev['location_id'] - s['location_id']) * (1 + cong_station / 10)
            base_cost = 1
            cap_ratio_cur = 0.0
            if s['capacity']>0:
                cap_ratio_cur = min(1.0, station_occupancy.get(current_sid,0)/s['capacity'])
            if cap_ratio_cur >= 0.9:
                ccur = base_cost * 3
            elif cap_ratio_cur >= 0.6:
                ccur = base_cost * 2
            else:
                ccur = base_cost
            if ev['battery_level'] < 20:
                ccur *= 0.1
            if ev['battery_level'] > 80:
                ccur *= 2.0
            current_cost = ccur + travel_time_cur
            # decide switch
            if best_option[0] is not None and best_option[2] < current_cost * 0.9:
                # apply new
                new_sid, new_start, _ = best_option
                new_dur = int(ev['desired_charge'] / station_map[new_sid]['max_power']) if station_map[new_sid]['max_power']>0 else 0
                if new_dur > 0:
                    station_segment_trees[new_sid].update(new_start, new_start+new_dur-1, 1)
                station_occupancy[new_sid] = station_occupancy.get(new_sid,0)+1
                result[i] = {'ev_id': ev_id, 'station_id': new_sid, 'start_time': new_start}
                improved = True
            else:
                # restore old
                if duration_cur > 0:
                    station_segment_trees[current_sid].update(cur_start, cur_start+duration_cur-1, 1)
                station_occupancy[current_sid] = station_occupancy.get(current_sid,0)+1
        if not improved:
            break
    # order by priority (low battery first)
    def priority_of(ev_id):
        lvl = ev_map[ev_id]['battery_level']
        if lvl < 20: return 0
        if lvl < 50: return 1
        if lvl < 80: return 2
        return 3
    result.sort(key=lambda x: (priority_of(x['ev_id']), x['ev_id']))
    return result