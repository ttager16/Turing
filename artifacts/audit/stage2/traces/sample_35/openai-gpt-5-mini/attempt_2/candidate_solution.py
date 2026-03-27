def optimize_multi_stage_routes(
    nodes: List[List[int]],
    vehicles: int,
    edges: List[List[int]],
    traffic_updates: List[List[int]],
    cross_dock_capacities: Dict[str, int],
    item_demands: Dict[str, List[int]]
) -> List[List[int]]:
    # Build graph
    n = len(nodes)
    adj = defaultdict(list)  # u -> list of (v, cost)
    edge_map = {}
    for u, v, c in edges:
        adj[u].append((v, c))
        edge_map[(u, v)] = c
    # Apply traffic updates
    for u, v, c in traffic_updates:
        if (u, v) in edge_map:
            edge_map[(u, v)] = c
    # Rebuild adj with updated costs and mark impassable
    adj = defaultdict(list)
    impassable = set()
    for (u, v), c in edge_map.items():
        if c >= 500:
            impassable.add((u, v))
        else:
            adj[u].append((v, c))
    # Prepare demands per destination
    total_demand = {}
    for dest_str, items in item_demands.items():
        dest = int(dest_str)
        total_demand[dest] = sum(items)
    # Prioritize destinations by total demand desc, tie by higher node id
    dests = sorted(total_demand.keys(), key=lambda x: (total_demand[x], x), reverse=True)
    # Cross-dock set and capacities
    cross_caps = {int(k): v for k, v in cross_dock_capacities.items()}
    # Vehicle states
    DEFAULT_VCAP = 100
    DEFAULT_FUEL = 1000
    veh_pos = [0] * vehicles
    veh_cap_rem = [DEFAULT_VCAP] * vehicles
    veh_fuel = [DEFAULT_FUEL] * vehicles
    veh_started = [False] * vehicles
    routes = [[0] for _ in range(vehicles)]
    # Track cross-dock heuristic usages (aggregate inbound counts)
    cross_used = defaultdict(int)
    # Helper: dijkstra from a source to all nodes (respecting impassable)
    def dijkstra(src):
        dist = [float('inf')] * n
        prev = [-1] * n
        dist[src] = 0
        h = [(0, src)]
        while h:
            d, u = heapq.heappop(h)
            if d != dist[u]:
                continue
            for v, c in adj.get(u, []):
                if (u, v) in impassable:
                    continue
                nd = d + c
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(h, (nd, v))
        return dist, prev
    # Helper: reconstruct path
    def path_from_prev(prev, tgt):
        if prev[tgt] == -1 and tgt != 0 and prev[tgt] != tgt and prev[tgt] != None and prev[tgt] != -1:
            pass
        path = []
        cur = tgt
        while cur != -1:
            path.append(cur)
            if cur == prev[cur]:
                break
            cur = prev[cur]
            if cur is None:
                break
        path = path[::-1]
        return path
    # More robust reconstruct using prev map
    def reconstruct(prev, src, tgt):
        if prev[tgt] == -1 and tgt != src:
            return None
        cur = tgt
        path = []
        while cur != -1:
            path.append(cur)
            if cur == src:
                break
            cur = prev[cur]
        if path[-1] != src:
            return None
        return list(reversed(path))
    # For path cost and cross-dock count and throughput costs
    def evaluate_path(path, veh_index):
        if path is None:
            return None
        # forward edges sum
        total = 0
        cross_entries = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            if (u, v) in impassable:
                return None
            c = edge_map.get((u, v))
            if c is None:
                # edge missing (shouldn't happen)
                return None
            total += c
            if v in cross_caps:
                cross_entries += 1
        # add depot handling cost if vehicle not yet started and will depart (one-time)
        depot_cost = 0
        if not veh_started[veh_index] and veh_pos[veh_index] == 0 and len(path) > 1:
            depot_cost = 1
        # add throughput costs per cross-dock entry: 1 if cap>=3 else 2
        throughput = 0
        for node in path[1:]:
            if node in cross_caps:
                throughput += 1 if cross_caps[node] >= 3 else 2
        return total + depot_cost + throughput, total, cross_entries
    # For candidate paths: try direct and via up to two cross-docks (1-2). We'll compute shortest paths tree from current vehicle pos and from cross-docks.
    # Precompute all-pairs shortest from all nodes required? We'll compute on demand.
    # Iterate destinations in order
    for dest in dests:
        td = total_demand[dest]
        if td > DEFAULT_VCAP:
            continue  # skip too large demand
        assigned = False
        # For each vehicle in order
        for vi in range(vehicles):
            if td > veh_cap_rem[vi]:
                continue
            # Compute dijkstra from vehicle position
            dist_src, prev_src = dijkstra(veh_pos[vi])
            if dist_src[dest] == float('inf'):
                # try via cross-docks consideration later
                pass
            # We'll collect candidate paths: direct from prev_src; and via one cross-dock or two cross-docks
            candidates = []
            # direct
            direct_path = reconstruct(prev_src, veh_pos[vi], dest)
            eval_direct = evaluate_path(direct_path, vi)
            if eval_direct is not None:
                total_aug, forward_dist, cross_entries = eval_direct
                if forward_dist <= veh_fuel[vi]:
                    candidates.append((total_aug, cross_entries, forward_dist, direct_path))
            # One cross-dock: for each cross-dock node cd, attempt path veh->cd and cd->dest
            for cd in cross_caps.keys():
                # veh -> cd
                if cd == veh_pos[vi] and cd == dest:
                    # same node equal dest handled above
                    continue
                dist_to_cd, prev_to_cd = dijkstra(veh_pos[vi])
                if dist_to_cd[cd] == float('inf'):
                    continue
                dist_from_cd, prev_from_cd = dijkstra(cd)
                if dist_from_cd[dest] == float('inf'):
                    continue
                path1 = reconstruct(prev_to_cd, veh_pos[vi], cd)
                path2 = reconstruct(prev_from_cd, cd, dest)
                if path1 is None or path2 is None:
                    continue
                # combine, avoid duplicate cd
                combined = path1 + path2[1:]
                eval_comb = evaluate_path(combined, vi)
                if eval_comb is not None:
                    total_aug, forward_dist, cross_entries = eval_comb
                    if forward_dist <= veh_fuel[vi]:
                        candidates.append((total_aug, cross_entries, forward_dist, combined))
            # Two cross-docks: cd1 -> cd2
            cds = list(cross_caps.keys())
            for i1 in range(len(cds)):
                for i2 in range(len(cds)):
                    cd1 = cds[i1]
                    cd2 = cds[i2]
                    # allow same if different roles? allow both different
                    dist_a, prev_a = dijkstra(veh_pos[vi])
                    if dist_a[cd1] == float('inf'):
                        continue
                    dist_b, prev_b = dijkstra(cd1)
                    if dist_b[cd2] == float('inf'):
                        continue
                    dist_c, prev_c = dijkstra(cd2)
                    if dist_c[dest] == float('inf'):
                        continue
                    p1 = reconstruct(prev_a, veh_pos[vi], cd1)
                    p2 = reconstruct(prev_b, cd1, cd2)
                    p3 = reconstruct(prev_c, cd2, dest)
                    if p1 is None or p2 is None or p3 is None:
                        continue
                    combined = p1 + p2[1:] + p3[1:]
                    eval_comb = evaluate_path(combined, vi)
                    if eval_comb is not None:
                        total_aug, forward_dist, cross_entries = eval_comb
                        if forward_dist <= veh_fuel[vi]:
                            candidates.append((total_aug, cross_entries, forward_dist, combined))
            if not candidates:
                continue
            # Select best candidate: min total_aug, tie fewer cross_entries, tie deterministic by path string
            candidates.sort(key=lambda x: (x[0], x[1], tuple(x[3])))
            best = candidates[0]
            total_aug, cross_entries, forward_dist, best_path = best
            # Check cross-dock capacity heuristic: ensure for each cross-dock in forward leg, capacity + planned inbound <= cap
            feasible = True
            temp_counts = {}
            for node in best_path[1:]:
                if node in cross_caps:
                    temp_counts[node] = temp_counts.get(node, 0) + 1
            for node, cnt in temp_counts.items():
                if cross_used[node] + cnt > cross_caps[node]:
                    feasible = False
                    break
            if not feasible:
                continue
            # Assign destination to this vehicle
            # Update vehicle route: append path from current pos to dest (excluding starting node to avoid duplicate)
            add_seq = best_path[1:]
            routes[vi].extend(add_seq)
            # Update vehicle state
            veh_cap_rem[vi] -= td
            veh_fuel[vi] -= forward_dist
            if not veh_started[vi]:
                veh_started[vi] = True
            veh_pos[vi] = dest
            # Update cross_dock usage counts
            for node, cnt in temp_counts.items():
                cross_used[node] += cnt
            assigned = True
            break
        # If no vehicle can take it, skip destination
        continue
    # After assignments, ensure each vehicle returns to depot via shortest available path (no fuel limit)
    for vi in range(vehicles):
        if routes[vi] == [0]:
            # unused vehicle must be [0,0]
            routes[vi] = [0, 0]
            continue
        # compute shortest path from current pos to 0
        dist_back, prev_back = dijkstra(veh_pos[vi])
        back_path = reconstruct(prev_back, veh_pos[vi], 0)
        if back_path is None:
            # cannot return: per spec, only use explicit edges; in this case, just append 0 to force return (even if invalid)
            routes[vi].append(0)
        else:
            # append excluding starting node duplicate
            routes[vi].extend(back_path[1:])
    return routes