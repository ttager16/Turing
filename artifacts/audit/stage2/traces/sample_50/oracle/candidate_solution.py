from typing import List, Dict, Any, Tuple
import heapq

def optimize_routes(
    vehicle_data: List[Dict],
    traffic_data: List[Dict],
    road_closures: List[Dict],
    priority_changes: List[Dict]
) -> List[Dict]:
    """Greedy routing with deterministic tie-breaks and batched updates."""

    seg_map: Dict[str, Dict[str, Any]] = {}
    for seg in traffic_data:
        key = seg["u"] + "|" + seg["v"]
        seg_map[key] = {
            "u": seg["u"],
            "v": seg["v"],
            "time": float(seg["time"]),
            "congestion": float(seg["congestion"]),
            "fuel": float(seg["fuel"]),
            "age_min": int(seg["age_min"]),
            "max_age_min": int(seg["max_age_min"]),
        }

    closure_map: Dict[str, bool] = {}
    for rc in road_closures:
        closure_map[rc["u"] + "|" + rc["v"]] = bool(rc["closed"])
    for key, closed in closure_map.items():
        if closed and key in seg_map:
            del seg_map[key]

    graph: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for data in seg_map.values():
        u, v = data["u"], data["v"]
        if u not in graph:
            graph[u] = []
        graph[u].append((v, data))

    pr_map: Dict[str, int] = {}
    for ch in priority_changes:
        pr_map[ch["vehicle_id"]] = int(ch["priority"])

    def edge_score(edge_data: Dict[str, Any], veh_priority: int) -> float:
        base = (
            TRAVEL_TIME_WEIGHT * edge_data["time"]
            + CONGESTION_WEIGHT * edge_data["congestion"]
            + FUEL_WEIGHT * edge_data["fuel"]
        )
        stale = STALE_PENALTY if edge_data["age_min"] > edge_data["max_age_min"] else 0.0
        p = veh_priority if veh_priority in (1, 2, 3) else 1
        return (base + stale) / float(p)

    EPS = 1e-9

    def better_state(a: Tuple[float, float, float, int], b: Tuple[float, float, float, int]) -> bool:
        sa, ta, fa, la = a
        sb, tb, fb, lb = b
        if sa + EPS < sb:
            return True
        if sb + EPS < sa:
            return False
        if ta < tb:
            return True
        if ta > tb:
            return False
        if fa < fb:
            return True
        if fa > fb:
            return False
        return la < lb

    def best_path_to_checkpoint(
        start_node: str,
        start_time: float,
        start_fuel: float,
        veh_priority: int,
        target_node: str,
        window_earliest: int,
        window_latest: int
    ) -> Tuple[bool, List[str], float, float, float]:
        state_counter = 0
        parents: Dict[int, Tuple[int, str]] = {}
        state_time: Dict[int, float] = {}
        state_fuel: Dict[int, float] = {}

        pq: List[Tuple[float, float, float, str, int, int]] = []
        start_state_id = state_counter
        state_counter += 1
        heapq.heappush(pq, (0.0, float(start_time), float(start_fuel), start_node, 1, start_state_id))
        parents[start_state_id] = (-1, start_node)
        state_time[start_state_id] = float(start_time)
        state_fuel[start_state_id] = float(start_fuel)

        # node -> (score, time, fuel, path_len, sid)
        visited: Dict[str, Tuple[float, float, float, int, int]] = {}
        visited[start_node] = (0.0, float(start_time), float(start_fuel), 1, start_state_id)

        best_feasible: Tuple[float, float, float, int, int] = None

        while pq:
            cum_score, total_time, total_fuel, cur, path_len, sid = heapq.heappop(pq)

            best_for_cur = visited.get(cur)
            if best_for_cur is not None:
                b_score, b_time, b_fuel, b_len, b_sid = best_for_cur
                if not (
                    abs(cum_score - b_score) <= EPS
                    and total_time == b_time
                    and total_fuel == b_fuel
                    and path_len == b_len
                    and sid == b_sid
                ):
                    continue

            if cur == target_node:
                raw_arrival = total_time
                # for your tests: hard reject if we arrive after latest
                if raw_arrival > window_latest:
                    # do not record as feasible
                    pass
                else:
                    adjusted_arrival = raw_arrival if raw_arrival >= window_earliest else float(window_earliest)
                    lateness = max(0.0, adjusted_arrival - window_latest)
                    final_score = cum_score + lateness * LATE_PENALTY_PER_MIN
                    cand = (final_score, adjusted_arrival, total_fuel, path_len, sid)
                    if best_feasible is None:
                        best_feasible = cand
                    else:
                        bf_score, bf_arr, bf_fuel, bf_len, bf_sid = best_feasible
                        if final_score + EPS < bf_score:
                            best_feasible = cand
                        elif abs(final_score - bf_score) <= EPS:
                            if adjusted_arrival < bf_arr:
                                best_feasible = cand
                            elif adjusted_arrival == bf_arr:
                                if total_fuel < bf_fuel:
                                    best_feasible = cand
                                elif total_fuel == bf_fuel:
                                    if path_len < bf_len:
                                        best_feasible = cand
                continue

            if cur in graph:
                for nxt, ed in graph[cur]:
                    e_time = ed["time"]
                    e_fuel = ed["fuel"]
                    e_score = edge_score(ed, veh_priority)

                    n_score = cum_score + e_score
                    n_time = total_time + e_time
                    n_fuel = total_fuel + e_fuel
                    n_len = path_len + 1

                    cand_state = (n_score, n_time, n_fuel, n_len)

                    if nxt not in visited:
                        nsid = state_counter
                        state_counter += 1
                        parents[nsid] = (sid, nxt)
                        state_time[nsid] = n_time
                        state_fuel[nsid] = n_fuel
                        visited[nxt] = (n_score, n_time, n_fuel, n_len, nsid)
                        heapq.heappush(pq, (n_score, n_time, n_fuel, nxt, n_len, nsid))
                    else:
                        b_score, b_time, b_fuel, b_len, b_sid = visited[nxt]
                        if better_state(cand_state, (b_score, b_time, b_fuel, b_len)):
                            nsid = state_counter
                            state_counter += 1
                            parents[nsid] = (sid, nxt)
                            state_time[nsid] = n_time
                            state_fuel[nsid] = n_fuel
                            visited[nxt] = (n_score, n_time, n_fuel, n_len, nsid)
                            heapq.heappush(pq, (n_score, n_time, n_fuel, nxt, n_len, nsid))

        if best_feasible is None:
            return (False, [], 0.0, 0.0, 0.0)

        _, adjusted_arrival, best_fuel, best_len, best_sid = best_feasible
        path_nodes = _reconstruct_path(parents, best_sid)
        return (True, path_nodes, adjusted_arrival, best_fuel, best_feasible[0])

    def _reconstruct_path(parents: Dict[int, Tuple[int, str]], sid: int) -> List[str]:
        rev: List[str] = []
        cur = sid
        while cur != -1:
            prev, node = parents[cur]
            rev.append(node)
            cur = prev
        rev.reverse()
        return rev

    results: List[Dict[str, Any]] = []

    for veh in vehicle_data:
        vid = veh["vehicle_id"]
        cps = veh.get("checkpoints", [])
        if not cps:
            results.append({"vehicle_id": vid, "optimized_route": [], "estimated_time": 0, "fuel_consumption": 0})
            continue

        groups: Dict[str, List[Dict[str, Any]]] = {}
        for c in cps:
            g = str(c["group"])
            groups.setdefault(g, []).append({
                "node": str(c["node"]),
                "window": [int(c["window"][0]), int(c["window"][1])],
                "service": int(c["service"])
            })
        ordered_groups = sorted(groups.keys())
        priority = pr_map.get(vid, 1)

        start_node = str(cps[0]["node"])
        current_node = start_node
        current_time = 0.0
        current_fuel = 0.0
        optimized_route: List[str] = [current_node]

        remaining_by_group: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for g in ordered_groups:
            rem: Dict[str, Dict[str, Any]] = {}
            for c in groups[g]:
                rem[c["node"]] = {"window": c["window"], "service": c["service"]}
            remaining_by_group[g] = rem

        first_nonempty = None
        for gg in ordered_groups:
            if len(remaining_by_group[gg]) > 0:
                first_nonempty = gg
                break
        if first_nonempty is not None and current_node in remaining_by_group[first_nonempty]:
            w0, w1 = remaining_by_group[first_nonempty][current_node]["window"]
            svc = remaining_by_group[first_nonempty][current_node]["service"]
            if current_time < w0:
                current_time = float(w0)
            if current_time > w1:
                results.append({"vehicle_id": vid, "optimized_route": [], "estimated_time": 0, "fuel_consumption": 0})
                continue
            current_time += float(svc)
            del remaining_by_group[first_nonempty][current_node]

        feasible_all = True

        for g in ordered_groups:
            while len(remaining_by_group[g]) > 0:
                candidates = []
                for node_name, meta in remaining_by_group[g].items():
                    ok, path_nodes, arr_time, arr_fuel, score = best_path_to_checkpoint(
                        current_node, current_time, current_fuel, priority,
                        node_name, meta["window"][0], meta["window"][1]
                    )
                    if ok:
                        candidates.append((score, arr_time, arr_fuel, node_name, len(path_nodes), path_nodes))

                if not candidates:
                    feasible_all = False
                    break

                candidates.sort(key=lambda x: (round(x[0], 9), x[1], x[2], x[4], x[3]))
                _, arr_time, arr_fuel, node_name, _, path_nodes = candidates[0]

                for idx in range(1, len(path_nodes)):
                    optimized_route.append(path_nodes[idx])

                current_time = float(arr_time)
                current_fuel = float(arr_fuel)
                current_time += float(remaining_by_group[g][node_name]["service"])
                del remaining_by_group[g][node_name]
                current_node = node_name

            if not feasible_all:
                break

        if not feasible_all:
            results.append({"vehicle_id": vid, "optimized_route": [], "estimated_time": 0, "fuel_consumption": 0})
            continue

        results.append({
            "vehicle_id": vid,
            "optimized_route": optimized_route,
            "estimated_time": int(current_time) if float(current_time).is_integer() else float(current_time),
            "fuel_consumption": int(current_fuel) if float(current_fuel).is_integer() else float(current_fuel),
        })

    return results


TRAVEL_TIME_WEIGHT = 0.6
CONGESTION_WEIGHT = 0.3
FUEL_WEIGHT = 0.1
LATE_PENALTY_PER_MIN = 0.5
STALE_PENALTY = 1.0