def __init__(self):
        self.adj = defaultdict(list)  # list of neighbors
        self.cap = {}  # (u,v) -> capacity
        self.cost = {}  # (u,v) -> cost
        self.flow = {}  # (u,v) -> flow
        self.nodes = set()

    def add_edge(self, u, v, capacity, cost):
        if capacity <= 0:
            return
        self.nodes.add(u); self.nodes.add(v)
        if (u, v) not in self.cap:
            self.adj[u].append(v)
            self.adj[v].append(u)
            self.cap[(u, v)] = capacity
            self.cost[(u, v)] = cost
            self.flow[(u, v)] = 0
            # reverse edge
            if (v, u) not in self.cap:
                self.cap[(v, u)] = 0
                self.cost[(v, u)] = -cost
                self.flow[(v, u)] = 0
        else:
            self.cap[(u, v)] += capacity

    def bellman_ford_potential(self, s):
        potential = {n: float('inf') for n in self.nodes}
        if s not in potential:
            return {n:0 for n in self.nodes}
        potential[s] = 0
        V = len(self.nodes)
        for _ in range(V - 1):
            updated = False
            for (u, v), c in list(self.cost.items()):
                if self.cap.get((u, v), 0) - self.flow.get((u, v), 0) <= 0:
                    continue
                if potential[u] + c < potential[v]:
                    potential[v] = potential[u] + c
                    updated = True
            if not updated:
                break
        for n in self.nodes:
            if potential[n] == float('inf'):
                potential[n] = 0
        return potential

    def min_cost_flow(self, s, t, maxf=float('inf')):
        flow = 0
        cost = 0
        potential = self.bellman_ford_potential(s)
        while flow < maxf:
            dist = {n: float('inf') for n in self.nodes}
            parent = {}
            dist[s] = 0
            heap = [(0, s)]
            visited = set()
            while heap:
                d, u = heapq.heappop(heap)
                if u in visited: 
                    continue
                visited.add(u)
                for v in self.adj[u]:
                    if self.cap.get((u, v), 0) - self.flow.get((u, v), 0) <= 0:
                        continue
                    rcost = self.cost[(u, v)] + potential.get(u, 0) - potential.get(v, 0)
                    nd = d + rcost
                    if nd < dist[v]:
                        dist[v] = nd
                        parent[v] = u
                        heapq.heappush(heap, (nd, v))
            if t not in parent and t != s:
                break
            # update potentials
            for n in self.nodes:
                if dist.get(n, float('inf')) < float('inf'):
                    potential[n] = potential.get(n, 0) + dist[n]
            # find augment
            increment = maxf - flow
            v = t
            if v == s:
                break
            while v != s:
                u = parent.get(v)
                if u is None:
                    increment = 0
                    break
                increment = min(increment, self.cap[(u, v)] - self.flow[(u, v)])
                v = u
            if increment == 0:
                break
            v = t
            while v != s:
                u = parent[v]
                self.flow[(u, v)] += increment
                self.flow[(v, u)] = self.flow.get((v, u), 0) - increment
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
        size = 4 * n
        self.tree = [0] * size
        self.lazy = [0] * size

    def _apply(self, node, val):
        self.tree[node] += val
        self.lazy[node] += val

    def _push(self, node):
        if self.lazy[node] != 0:
            self._apply(2*node, self.lazy[node])
            self._apply(2*node+1, self.lazy[node])
            self.lazy[node] = 0

    def _update(self, node, l, r, ql, qr, val):
        if l > r or ql > r or qr < l:
            return
        if ql <= l and r <= qr:
            self._apply(node, val)
            return
        self._push(node)
        mid = (l + r) // 2
        self._update(2*node, l, mid, ql, qr, val)
        self._update(2*node+1, mid+1, r, ql, qr, val)
        self.tree[node] = min(self.tree[2*node], self.tree[2*node+1])

    def update(self, l, r, val):
        if self.n == 0:
            return
        l = max(0, l); r = min(self.n - 1, r)
        if l > r:
            return
        self._update(1, 0, self.n - 1, l, r, val)

    def _query(self, node, l, r, ql, qr):
        if self.n == 0:
            return float('inf')
        if l > r or ql > r or qr < l:
            return float('inf')
        if ql <= l and r <= qr:
            return self.tree[node]
        self._push(node)
        mid = (l + r) // 2
        left = self._query(2*node, l, mid, ql, qr)
        right = self._query(2*node+1, mid+1, r, ql, qr)
        return min(left, right)

    def query(self, l, r):
        if self.n == 0:
            return float('inf')
        l = max(0, l); r = min(self.n - 1, r)
        if l > r:
            return float('inf')
        return self._query(1, 0, self.n - 1, l, r)

def optimize_ev_charging_schedule(traffic_data: list, ev_data: list, station_data: list) -> list:
    if not ev_data or not station_data:
        return []
    # build maps
    traffic_map = {loc: cong for loc, cong in (tuple(x) for x in traffic_data)}
    station_map = {s['id']: s.copy() for s in station_data}
    ev_map = {e['id']: e.copy() for e in ev_data}
    # filter EVs with traffic info
    feasible_evs = []
    for e in ev_data:
        if e['location_id'] not in traffic_map:
            continue
        # nearby filter
        nearby = [s for s in station_data if abs(s['location_id'] - e['location_id']) <= 5]
        if not nearby:
            continue
        feasible_evs.append(e)
    if not feasible_evs:
        return []

    max_time = 1000
    station_trees = {}
    station_occupancy = {}
    for s in station_data:
        loc = s['location_id']
        cong = traffic_map.get(loc, 0)
        effective_capacity = int(s['capacity'])
        if cong > 7:
            effective_capacity = int(s['capacity'] * 0.6)
        station_occupancy[s['id']] = 0
        station_trees[s['id']] = SegmentTree(max_time)
        # initialize trees with capacity per time slot
        if max_time > 0:
            # each time slot value is capacity; set root to capacity via update
            station_trees[s['id']].update(0, max_time-1, effective_capacity)

    # priority queue
    pq = []
    def battery_priority(b):
        if b < 20: return 0
        if b < 50: return 1
        if b < 80: return 2
        return 3
    for e in feasible_evs:
        heapq.heappush(pq, (battery_priority(e['battery_level']), e['id'], e))

    # build flow graph
    G = FlowGraph()
    source = 'source'; sink = 'sink'
    # add source->ev
    ev_nodes = []
    station_nodes = set()
    # gather feasible edges info
    ev_station_info = defaultdict(list)  # ev_id -> list of (station_id, cost, arrival_time, duration)
    for _, ev_id, e in pq:
        ev_node = f"ev_{e['id']}"
        ev_nodes.append(ev_node)
        G.add_edge(source, ev_node, 1, 0)
        # feasible stations
        for s in station_data:
            if abs(s['location_id'] - e['location_id']) > 5:
                continue
            if e['location_id'] not in traffic_map:
                continue
            distance = abs(e['location_id'] - s['location_id'])
            if distance > 5:
                continue
            congestion = traffic_map.get(e['location_id'], 0)
            travel_time = distance * (1 + congestion / 10)
            arrival_time = int(0 + int(travel_time))
            duration = int(e['desired_charge'] // s['max_power'])
            if duration <= 0:
                duration = 1
            # peak capacity handled via station_trees initial set
            # capacity ratio
            cap = s['capacity']
            used = station_occupancy.get(s['id'], 0)
            effective_cap = int(cap)
            if congestion > 7:
                effective_cap = int(cap * 0.6)
            if effective_cap <= 0:
                continue
            capacity_ratio = used / cap if cap > 0 else 1.0
            base_cost = 1
            if capacity_ratio >= 0.9:
                c = base_cost * 3
            elif capacity_ratio >= 0.6:
                c = base_cost * 2
            else:
                c = base_cost
            if e['battery_level'] < 20:
                c *= 0.1
            if e['battery_level'] > 80:
                c *= 2.0
            total_cost = c + travel_time
            scaled = int(total_cost * 100)
            ev_station_info[e['id']].append((s['id'], scaled, arrival_time, duration))
            ev_node = f"ev_{e['id']}"
            station_node = f"station_{s['id']}"
            station_nodes.add(station_node)
            G.add_edge(ev_node, station_node, 1, scaled)
    # add station->sink edges
    for s in station_data:
        node = f"station_{s['id']}"
        # capacity after occupancy
        cong = traffic_map.get(s['location_id'], 0)
        eff = int(s['capacity'])
        if cong > 7:
            eff = int(s['capacity'] * 0.6)
        if eff <= 0:
            continue
        G.add_edge(node, sink, eff, 0)

    # if no edges from source to stations then empty
    if not any(u == source for u in G.adj):
        return []

    # run min cost flow
    flow, _ = G.min_cost_flow(source, sink, maxf=len(feasible_evs))
    # extract assignments from flows
    assignments = {}
    for (u, v), f in list(G.flow.items()):
        if u.startswith("ev_") and v.startswith("station_") and f > 0:
            ev_id = u.split("_",1)[1]
            station_id = v.split("_",1)[1]
            # find earliest slot
            info_list = ev_station_info.get(ev_id, [])
            sel = None
            for sid, cost, arrival, duration in info_list:
                if sid == station_id:
                    sel = (arrival, duration)
                    break
            if sel is None:
                continue
            arrival, duration = sel
            # find earliest slot
            tree = station_trees[station_id]
            start = None
            attempts = 0
            t = arrival
            while attempts < 50 and t <= arrival + 500:
                if tree.query(t, min(t+duration-1, max_time-1)) >= 1:
                    start = t
                    break
                t += 1
                attempts += 1
            if start is None:
                continue
            # assign
            assignments[ev_id] = {'ev_id': ev_id, 'station_id': station_id, 'start_time': start}
            station_trees[station_id].update(start, min(start+duration-1, max_time-1), -1)
            station_occupancy[station_id] += 1

    if not assignments:
        return []

    # iterative refinement exactly 2 iterations
    for _ in range(2):
        # try to improve each assignment by testing alternatives
        for prio, ev_id, e in list(pq):
            if ev_id not in assignments:
                continue
            current = assignments[ev_id]
            current_station = current['station_id']
            # compute current cost
            best_cost = None
            info_list = ev_station_info.get(ev_id, [])
            for sid, cost, arrival, duration in info_list:
                if sid == current_station:
                    best_cost = cost
                    cur_arrival = arrival; cur_duration = duration
                    break
            if best_cost is None:
                continue
            # try alternatives
            for sid, cost, arrival, duration in info_list:
                if sid == current_station:
                    continue
                # temporarily remove current assignment
                station_trees[current_station].update(current['start_time'], min(current['start_time']+cur_duration-1, max_time-1), +1)
                station_occupancy[current_station] = max(0, station_occupancy[current_station]-1)
                # find earliest for alternative
                start_alt = None
                attempts = 0
                t = arrival
                while attempts < 50 and t <= arrival + 500:
                    if station_trees[sid].query(t, min(t+duration-1, max_time-1)) >= 1:
                        start_alt = t
                        break
                    t += 1
                    attempts += 1
                if start_alt is None:
                    # restore original
                    station_trees[current_station].update(current['start_time'], min(current['start_time']+cur_duration-1, max_time-1), -1)
                    station_occupancy[current_station] += 1
                    continue
                # check improvement threshold
                if cost < best_cost * 0.9:
                    # commit switch
                    assignments[ev_id] = {'ev_id': ev_id, 'station_id': sid, 'start_time': start_alt}
                    station_trees[sid].update(start_alt, min(start_alt+duration-1, max_time-1), -1)
                    station_occupancy[sid] += 1
                    # original already freed
                    break
                else:
                    # restore original
                    station_trees[current_station].update(current['start_time'], min(current['start_time']+cur_duration-1, max_time-1), -1)
                    station_occupancy[current_station] += 1

    # prepare ordered output by priority (low battery first)
    result = []
    ordered = sorted(assignments.values(), key=lambda x: battery_priority(ev_map[x['ev_id']]['battery_level']))
    for a in ordered:
        result.append({'ev_id': a['ev_id'], 'station_id': a['station_id'], 'start_time': int(a['start_time'])})
    return result