from typing import List, Tuple, Dict, TypedDict, Union, Set, Optional
from collections import defaultdict
import heapq

class VehicleEntry(TypedDict):
    Route: List[str]
    TravelTime: int
    FuelCost: int
    Schedule: List[List[Union[str, float]]]

def optimize_fleet_scheduling(
    cities: List[List[Union[str, int, int]]],
    vehicles: List[List[Union[int, int]]],
    traffic_data: Dict[str, int],
    demands: Optional[Dict[str, int]] = None,
    hub_capacity: Optional[Dict[str, int]] = None,
    updates: Optional[List[List[Union[str, Optional[int]]]]] = None,
    phases: Optional[List[Dict[str, int]]] = None
) -> Dict[str, VehicleEntry]:
    if not vehicles:
        return {}
    
    validated_cities: List[List[Union[str, int, int]]] = []
    for city_data in cities:
        if not isinstance(city_data, list) or len(city_data) != 3:
            continue
        name, start, end = city_data
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 0 or end < 0:
            continue
        if start > end:
            continue
        validated_cities.append([name, start, end])
    
    if not validated_cities:
        return {f'Vehicle{vid}': {'Route': [], 'TravelTime': 0, 'FuelCost': 0} for vid, _ in vehicles}

    validated_vehicles: List[List[Union[int, int]]] = []
    seen_ids: Set[int] = set()
    for veh in vehicles:
        if not isinstance(veh, list) or len(veh) != 2:
            continue
        vid, cap = veh
        if not isinstance(vid, int) or vid <= 0:
            continue
        if vid in seen_ids:
            continue
        if not isinstance(cap, int) or cap < 0:
            continue
        seen_ids.add(vid)
        validated_vehicles.append([vid, cap])
    
    if not validated_vehicles:
        return {}
    
    validated_vehicles.sort(key=lambda x: (x[1], x[0]))
    
    city_names = sorted([name for name, _, _ in validated_cities])
    # Convert time windows from hours to minutes for internal processing
    windows: Dict[str, List[int]] = {name: [s * 60, e * 60] for name, s, e in validated_cities}
    graph: Dict[str, Dict[str, int]] = defaultdict(dict)
    for route, t in traffic_data.items():
        if not isinstance(route, str) or not isinstance(t, int):
            continue
        if t < 0:
            continue
        parts = route.split('-')
        if len(parts) != 2:
            continue
        a, b = parts
        if a in windows and b in windows:
            graph[a][b] = t

    if updates:
        for upd in sorted(updates, key=lambda x: (x[0], -1 if x[1] is None else x[1])):
            route_key, new_time = upd
            if not isinstance(route_key, str):
                continue
            parts = route_key.split('-')
            if len(parts) != 2:
                continue
            a, b = parts
            if a not in windows or b not in windows:
                continue
            if new_time is None:
                if a in graph and b in graph[a]:
                    del graph[a][b]
                    if not graph[a]:
                        del graph[a]
            elif isinstance(new_time, int) and new_time >= 0:
                graph[a][b] = new_time

    def fuel_cost_of(distance: int, capacity: int) -> int:
        """Calculate fuel cost based on distance (minutes) and vehicle capacity."""
        if distance <= 0:
            return 0
        base_rate = 0.1  # Cost per minute of travel
        efficiency_factor = 1.0 + (capacity / 200.0)  # Larger vehicles use more fuel
        cost = int(distance * base_rate * efficiency_factor)
        return max(1, cost)  # Minimum fuel cost of 1
    
    def route_value(path: List[str], distance: int, capacity: int) -> int:
        """Calculate route value: negative fuel cost + small bonus for visiting cities."""
        fuel_cost = fuel_cost_of(distance, capacity)
        city_bonus = len(path) * 10  # Small bonus for each city visited
        return city_bonus - fuel_cost
    
    def shortest_path(src: str, dst: str) -> Tuple[Optional[int], Optional[List[str]]]:
        if src == dst:
            return 0, [src]
        if src not in graph:
            return None, None
        pq: List[Tuple[int, str, List[str]]] = [(0, src, [src])]
        seen: Dict[str, int] = {}
        while pq:
            dist, node, path = heapq.heappop(pq)
            if node in seen:
                continue
            seen[node] = dist
            if node == dst:
                return dist, path
            for nb in sorted(graph[node].keys()):
                if nb in seen:
                    continue
                heapq.heappush(pq, (dist + graph[node][nb], nb, path + [nb]))
        return None, None

    def feasible_total_travel(path: List[str]) -> Optional[int]:
        if not path:
            return 0
        start0, end0 = windows[path[0]]
        current = max(0, start0)
        if current > end0:
            return None
        total = 0
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if b not in graph.get(a, {}):
                return None
            t = graph[a][b]
            total += t
            current += t
            b_start, b_end = windows[b]
            if current < b_start:
                current = b_start
            if current > b_end:
                return None
        return total

    def build_schedule(path: List[str]) -> List[List[Union[str, int]]]:
        if not path:
            return []
        schedule: List[List[Union[str, int]]] = []
        start0, end0 = windows[path[0]]
        current = max(0, start0)
        if current > end0:
            return []
        schedule.append([path[0], current])
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if b not in graph.get(a, {}):
                return []
            current += graph[a][b]
            b_start, b_end = windows[b]
            if current < b_start:
                current = b_start
            if current > b_end:
                return []
            schedule.append([b, current])
        return schedule

    candidates: List[List[str]] = []
    for name in city_names:
        s, e = windows[name]
        if max(0, s) <= e:
            candidates.append([name])
    for i, a in enumerate(city_names):
        for j, b in enumerate(city_names):
            if i == j:
                continue
            dist, path = shortest_path(a, b)
            if dist is None or path is None:
                continue
            feasible_time = feasible_total_travel(path)
            if feasible_time is not None:
                candidates.append(path)

    def path_sort_key(p: List[str]) -> Tuple[int, Tuple[str, ...]]:
        return (len(p), tuple(p))
    unique_candidates: List[List[str]] = []
    seen_paths = set()
    for p in sorted(candidates, key=path_sort_key):
        key = tuple(p)
        if key not in seen_paths:
            seen_paths.add(key)
            unique_candidates.append(p)

    path_to_distance: Dict[Tuple[str, ...], int] = {}
    for p in unique_candidates:
        if len(p) == 1:
            path_to_distance[tuple(p)] = 0
            continue
        total = feasible_total_travel(p)
        if total is None:
            continue
        dist_sum = 0
        for k in range(len(p) - 1):
            dist_sum += graph[p[k]][p[k + 1]]
        path_to_distance[tuple(p)] = dist_sum

    per_vehicle_candidates: Dict[int, List[Tuple[List[str], int, int]]] = {}
    for vid, cap in validated_vehicles:
        options: List[Tuple[List[str], int, int]] = []
        for p in unique_candidates:
            key = tuple(p)
            if key not in path_to_distance:
                continue
            dist = path_to_distance[key]
            cost = fuel_cost_of(dist, cap)
            value = route_value(p, dist, cap)
            options.append((p, dist, cost, value))
        options.append(([], 0, 0, 0))  # Empty route has no value
        options.sort(key=lambda x: (-x[3], x[2], x[1], len(x[0]), tuple(x[0]) if x[0] else ()))  # Sort by value (descending), then cost
        per_vehicle_candidates[vid] = options

    MAX_OPT = 30
    for vid in list(per_vehicle_candidates.keys()):
        if len(per_vehicle_candidates[vid]) > MAX_OPT:
            per_vehicle_candidates[vid] = per_vehicle_candidates[vid][:MAX_OPT]

    if (phases and len(phases) > 0) or (demands is not None):
        per_vehicle_city_best: Dict[int, Dict[str, Tuple[List[str], int, int]]] = {}
        for vid, cap in validated_vehicles:
            city_best: Dict[str, Tuple[List[str], int, int]] = {}
            options = per_vehicle_candidates.get(vid, [])
            for path, dist, trip_cost, value in options:
                if not path:
                    continue
                city = path[-1]
                prev = city_best.get(city)
                if prev is None:
                    city_best[city] = (path, dist, trip_cost)
                else:
                    p_path, p_dist, p_cost = prev
                    # For demand fulfillment, prefer routes that can actually deliver
                    # (routes with multiple cities over single-city routes)
                    if len(path) > len(p_path) or (len(path) == len(p_path) and (trip_cost, dist, tuple(path)) < (p_cost, p_dist, tuple(p_path))):
                        city_best[city] = (path, dist, trip_cost)
            per_vehicle_city_best[vid] = city_best

        def min_cost_flow_assign(dem_map: Dict[str, int], remaining_cap: Dict[int, int], locked_vids: Set[int]) -> Dict[int, Tuple[List[str], int, int]]:
            SCALE = 1000
            arcs: List[Tuple[int, int, str]] = []  # (scaled_unit_cost, vid, city)
            for vid, cap in validated_vehicles:
                if vid in locked_vids:          
                    continue
                if cap <= 0:
                    continue
                city_best = per_vehicle_city_best.get(vid, {})
                for city in sorted(city_best.keys()):
                    _, _, trip_cost = city_best[city]
                    unit_scaled = (trip_cost * SCALE) // max(1, cap)
                    arcs.append((unit_scaled, vid, city))
            arcs.sort(key=lambda x: (x[0], x[1], x[2]))

            city_cap_left: Dict[str, int] = {}
            for c in city_names:
                cap_lim = None
                if hub_capacity and isinstance(hub_capacity.get(c), int):
                    cap_lim = hub_capacity[c]
                city_cap_left[c] = cap_lim if cap_lim is not None else 10**9

            dem_left: Dict[str, int] = {c: int(dem_map.get(c, 0)) for c in city_names}

            chosen_local: Dict[int, Tuple[List[str], int, int]] = {}

            progress = True
            while progress:
                progress = False
                for _, vid, city in arcs:
                    if dem_left.get(city, 0) <= 0:
                        continue
                    if remaining_cap.get(vid, 0) <= 0:
                        continue
                    if city_cap_left.get(city, 0) <= 0:
                        continue
                    assignable = min(remaining_cap[vid], dem_left[city], city_cap_left[city])
                    if assignable <= 0:
                        continue
                    if vid not in chosen_local:
                        path, dist, trip_cost = per_vehicle_city_best[vid][city]
                        chosen_local[vid] = (path, dist, trip_cost)
                    remaining_cap[vid] -= assignable
                    dem_left[city] -= assignable
                    city_cap_left[city] -= assignable
                    progress = True

            return chosen_local

        remaining_capacities: Dict[int, int] = {vid: cap for vid, cap in validated_vehicles}

        chosen_flow: Dict[int, Tuple[List[str], int, int]] = {}
        if phases and len(phases) > 0:
            for phase_dem in phases:
                phase_dem_sanitized: Dict[str, int] = {}
                for c in city_names:
                    v = phase_dem.get(c, 0) if isinstance(phase_dem, dict) else 0
                    if isinstance(v, int) and v > 0:
                        phase_dem_sanitized[c] = v
                if not phase_dem_sanitized:
                    continue
                locked_vids = set(chosen_flow.keys())  
                phase_choice = min_cost_flow_assign(phase_dem_sanitized, remaining_capacities, locked_vids)
                for vid, trip in phase_choice.items():
                    if vid not in chosen_flow:
                        chosen_flow[vid] = trip
        elif demands is not None:
            dem_sanitized: Dict[str, int] = {}
            for c in city_names:
                v = demands.get(c, 0) if isinstance(demands, dict) else 0
                if isinstance(v, int) and v > 0:
                    dem_sanitized[c] = v
            if dem_sanitized:
                locked_vids = set(chosen_flow.keys())
                chosen_flow = min_cost_flow_assign(dem_sanitized, remaining_capacities, locked_vids)

        result: Dict[str, Dict[str, Union[List[str], int]]] = {}
        for vid, cap in validated_vehicles:
            if vid in chosen_flow:
                path, dist, trip_cost = chosen_flow[vid]
                result[f'Vehicle{vid}'] = {
                    'Route': path,
                    'TravelTime': dist,
                    'FuelCost': trip_cost,
                }
                schedule = build_schedule(path)
                if schedule:
                    # Convert schedule times from minutes back to hours for display
                    schedule_hours = [[city, round(time / 60, 2)] for city, time in schedule]
                    result[f'Vehicle{vid}']['Schedule'] = schedule_hours  # type: ignore
            else:
                result[f'Vehicle{vid}'] = {
                    'Route': [],
                    'TravelTime': 0,
                    'FuelCost': 0,
                }
        return result

    from functools import lru_cache
    vehicle_order = [vid for vid, _ in validated_vehicles]

    def cities_of(path: List[str]) -> Set[str]:
        return set(path)

    use_dp = len(city_names) <= 18 and len(vehicle_order) <= 12

    @lru_cache(maxsize=None)
    def dp(idx: int, used_cities_key: Tuple[str, ...]) -> Tuple[int, Tuple[Tuple[int, Tuple[str, ...], int], ...]]:
        """Dynamic programming to find optimal assignment with no city overlap."""
        if idx == len(vehicle_order):
            return 0, tuple()
        vid = vehicle_order[idx]
        used = set(used_cities_key)
        best_value = float('-inf')
        best_assign: Optional[Tuple[Tuple[int, Tuple[str, ...], int], ...]] = None
        for path, dist, cost, value in per_vehicle_candidates[vid]:
            if cities_of(path) & used:
                continue  # Skip if cities already used by other vehicles
            next_used = tuple(sorted(used | cities_of(path)))
            tail_cost, tail_assign = dp(idx + 1, next_used)
            total_value = value + tail_cost  # tail_cost now represents total value
            candidate_assign = tail_assign + ((vid, tuple(path), dist),)
            if total_value > best_value:
                best_value = total_value
                best_assign = candidate_assign
            elif total_value == best_value and best_assign is not None:
                if candidate_assign < best_assign:
                    best_assign = candidate_assign
        if best_assign is None:
            # Skip this vehicle (empty route)
            tail_cost, tail_assign = dp(idx + 1, tuple(sorted(used)))
            return tail_cost, tail_assign
        return int(best_value), best_assign

    # Execute assignment strategy
    chosen: Dict[int, Tuple[List[str], int, int]] = {}
    if use_dp:
        # Use dynamic programming for small instances
        _, assignment = dp(0, tuple())
        for vid, path_tuple, dist in assignment:
            cap = next(c for (v, c) in validated_vehicles if v == vid)
            chosen[vid] = (list(path_tuple), dist, fuel_cost_of(dist, cap))
    else:
        # Use greedy assignment for large instances
        used: Set[str] = set()
        for vid, cap in validated_vehicles:
            sel_path: List[str] = []
            sel_dist = 0
            sel_cost = 0
            for path, dist, cost, value in per_vehicle_candidates[vid]:
                if cities_of(path) & used:
                    continue
                sel_path, sel_dist, sel_cost = path, dist, cost
                used.update(cities_of(path))
                break
            chosen[vid] = (sel_path, sel_dist, sel_cost)

    # Build final results
    result: Dict[str, Dict[str, Union[List[str], int]]] = {}
    for vid, _ in validated_vehicles:
        path, dist, cost = chosen.get(vid, ([], 0, 0))
        result[f'Vehicle{vid}'] = {
            'Route': path,
            'TravelTime': dist,
            'FuelCost': cost,
        }
        schedule = build_schedule(path)
        if schedule:
            # Convert schedule times from minutes back to hours for display
            schedule_hours = [[city, float(f"{time/60:.2f}")] for city, time in schedule]
            result[f'Vehicle{vid}']['Schedule'] = schedule_hours  # type: ignore
    
    return result

if __name__ == "__main__":
    # Example usage
    cities = [
        ['HubA', 8, 10],    # 8:00 AM to 10:00 AM
        ['HubB', 6, 9],     # 6:00 AM to 9:00 AM
        ['CityX', 9, 12],   # 9:00 AM to 12:00 PM
        ['CityY', 11, 14]   # 11:00 AM to 2:00 PM
    ]
    vehicles = [
        [101, 120],
        [202, 80],
        [303, 150]
    ]
    traffic_data = {
        'HubA-HubB': 30,       # 30 minutes
        'HubB-CityX': 30,      # 30 minutes  
        'HubA-CityX': 60,      # 60 minutes (1 hour)
        'CityX-CityY': 30,     # 30 minutes
        'HubB-CityY': 60       # 60 minutes (1 hour)
    }

    demands = {'HubB': 50, 'CityX': 75}  # Demand quantities per city
    hub_capacity = {'HubB': 100, 'CityX': 200}  # Capacity limits per hub
    updates = [['HubA-HubB', 15], ['HubB-CityX', None]]  # Traffic updates
    phases = [{'HubB': 30}, {'CityX': 40}]  # Demand phases
    result = optimize_fleet_scheduling(cities, vehicles, traffic_data,demands,hub_capacity,updates,phases)
    print(result)