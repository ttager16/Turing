from typing import Any, Dict, List
import heapq

def compute_dynamic_shortest_paths(
    graph: Dict[str, List[List[Any]]],
    updates: List[List[Any]],
    time_of_day: int
) -> Dict[str, List[str]]:
    def is_non_empty_string(x):
        return isinstance(x, str) and len(x) > 0

    def is_valid_time_of_day(_time):
        return isinstance(_time, int) and 0 <= _time < 24

    allowed_keys = {"traffic", "maintenance", "capacity_tier", "time_window_start", "time_window_end"}

    def validate_constraints(constraints):
        if not isinstance(constraints, dict):
            return False
        for k, v in constraints.items():
            if k not in allowed_keys:
                continue
            if k in ("traffic", "maintenance"):
                if not (isinstance(v, (int, float)) and v > 0):
                    return False
            elif k == "capacity_tier":
                if not (isinstance(v, int) and v >= 1):
                    return False
            elif k in ("time_window_start", "time_window_end"):
                if not isinstance(v, int):
                    return False
                if not (0 <= v <= 24):
                    return False
                if k == "time_window_start" and v == 24:
                    return False
        return True

    def filter_allowed_constraints(constraints):
        return {k: constraints[k] for k in allowed_keys if k in constraints}

    if not is_valid_time_of_day(time_of_day):
        return {}
    if not isinstance(graph, dict):
        return {}
    if graph == {} and (updates is None or len(updates) == 0):
        return {}

    nodes_set = set()
    normalized_graph = {}

    for src, edges in graph.items():
        if not is_non_empty_string(src):
            return {}
        if not isinstance(edges, list):
            return {}
        nodes_set.add(src)
        new_edges = []
        for edge in edges:
            if not (isinstance(edge, list) and len(edge) == 3):
                return {}
            dst, base_cost, constraints = edge[0], edge[1], edge[2]
            if not is_non_empty_string(dst):
                return {}
            if not (isinstance(base_cost, int) and base_cost >= 0):
                return {}
            if not isinstance(constraints, dict):
                return {}
            if not validate_constraints(constraints):
                return {}
            new_edges.append([dst, base_cost, filter_allowed_constraints(constraints)])
            nodes_set.add(dst)
        normalized_graph[src] = new_edges

    for _node in nodes_set:
        normalized_graph.setdefault(_node, [])

    if updates is None:
        updates = []
    if not isinstance(updates, list):
        return {}

    edge_index = {}
    for s, edges in normalized_graph.items():
        edge_index[s] = {}
        for i, (d, _, _) in enumerate(edges):
            edge_index[s].setdefault(d, []).append(i)

    for _update in updates:
        if not (isinstance(_update, list) and len(_update) == 3):
            return {}
        u_src, u_dst, u_constraints = _update[0], _update[1], _update[2]
        if not (is_non_empty_string(u_src) and is_non_empty_string(u_dst) and isinstance(u_constraints, dict)):
            return {}
        if not validate_constraints(u_constraints):
            return {}
        u_constraints = filter_allowed_constraints(u_constraints)
        if u_src in edge_index and u_dst in edge_index[u_src]:
            for edge_i in edge_index[u_src][u_dst]:
                existing = normalized_graph[u_src][edge_i][2]
                merged = dict(existing)
                for k, v in u_constraints.items():
                    merged[k] = v
                normalized_graph[u_src][edge_i][2] = merged

    def is_edge_available(constraints):
        start = constraints.get("time_window_start", None)
        end = constraints.get("time_window_end", None)
        if start is None or end is None:
            return True
        return start <= time_of_day <= end

    def compute_effective_cost(base_cost, constraints):
        traffic = float(constraints.get("traffic", 1))
        maintenance = float(constraints.get("maintenance", 1))
        cap = constraints.get("capacity_tier", 1)
        if not isinstance(cap, int) or cap < 1:
            return float("inf")
        cap_factor = 1.0 + 0.25 * max(cap - 1, 0)
        return float(base_cost) * traffic * maintenance * cap_factor

    def is_terminal_city(city):
        return len([e for e in normalized_graph[city] if e[0] != city]) == 0

    terminals = [n for n in nodes_set if is_terminal_city(n)]

    reversed_adjacency = {n: [] for n in nodes_set}
    for src, edges in normalized_graph.items():
        for dst, base_cost, cdict in edges:
            if src == dst:
                continue
            if not is_edge_available(cdict):
                continue
            cost = compute_effective_cost(base_cost, cdict)
            if cost < 0:
                return {}
            reversed_adjacency[dst].append((src, cost))

    def is_better_state(a, b):
        if b is None:
            return True
        cost_a, path_a, hops_a, next_a = a
        cost_b, path_b, hops_b, next_b = b
        if abs(cost_a - cost_b) > 0.000000001:
            return cost_a < cost_b
        if path_a != path_b:
            return path_a < path_b
        if hops_a != hops_b:
            return hops_a < hops_b
        return next_a < next_b

    def priority_key(cost, path, hops, next_hop):
        return (round(cost, 12), path, hops, next_hop)

    best_state = {n: None for n in nodes_set}
    priority_queue = []

    for terminal in terminals:
        state = (0.0, (terminal,), 0, "")
        best_state[terminal] = state
        heapq.heappush(priority_queue, (priority_key(*state), terminal))

    while priority_queue:
        _, current = heapq.heappop(priority_queue)
        current_state = best_state[current]
        for neighbor, edge_cost in reversed_adjacency[current]:
            new_cost = current_state[0] + edge_cost
            new_path = (neighbor,) + current_state[1]
            new_hops = current_state[2] + 1
            new_next = current_state[1][0] if len(current_state[1]) >= 1 else ""
            candidate = (new_cost, new_path, new_hops, new_next)
            if is_better_state(candidate, best_state[neighbor]):
                best_state[neighbor] = candidate
                heapq.heappush(priority_queue, (priority_key(*candidate), neighbor))

    result = {}
    for city in sorted(nodes_set):
        state = best_state[city]
        result[city] = [city] if state is None else list(state[1])
    return result


if __name__ == "__main__":
    graph = {
        "A": [
            ["B", 10, {"traffic": 1.0, "capacity_tier": 1}],
            ["C", 15, {"traffic": 1.5, "time_window_start": 8, "time_window_end": 20}]
        ],
        "B": [
            ["C", 5, {"traffic": 1.0, "maintenance": 0.9}],
            ["D", 20, {"traffic": 1.2, "capacity_tier": 2}]
        ],
        "C": [
            ["D", 10, {"traffic": 1.1, "maintenance": 0.95}]
        ],
        "D": []
    }
    time_of_day = 12
    updates = [
        ["A", "B", {"capacity_tier": 3}],
        ["B", "D", {"maintenance": 0.7, "time_window_start": 10, "time_window_end": 18}]
    ]
    print(compute_dynamic_shortest_paths(graph, updates, time_of_day))