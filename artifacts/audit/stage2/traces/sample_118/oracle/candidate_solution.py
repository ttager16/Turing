from typing import Dict, List
from collections import deque

def optimize_water_flow(
    graph: Dict[str, List[List]],
    source: str,
    target: str,
    capacity_changes: List[List]
) -> int:
    
    def is_valid_node(value):
        return isinstance(value, str) and len(value) > 0

    if graph is None or capacity_changes is None:
        return 0
    if not isinstance(graph, dict) or not isinstance(capacity_changes, list):
        return 0
    if not is_valid_node(source) or not is_valid_node(target):
        return 0
    if len(graph) == 0 and len(capacity_changes) == 0:
        return 0

    network = {}
    for node, neighbors in graph.items():
        if not is_valid_node(node):
            return 0
        if not isinstance(neighbors, list):
            return 0
        seen = set()
        for edge in neighbors:
            if not isinstance(edge, list) or len(edge) != 2:
                return 0
            neighbor, capacity = edge
            if not is_valid_node(neighbor):
                return 0
            if type(capacity) is not int or capacity < 0:
                return 0
            if node == neighbor:
                return 0
            if neighbor in seen:
                return 0
            seen.add(neighbor)
            if capacity == 0:
                continue
            network.setdefault(node, {})[neighbor] = capacity

    for change in capacity_changes:
        if not isinstance(change, list) or len(change) != 3:
            return 0
        u, v, delta = change
        if not is_valid_node(u) or not is_valid_node(v):
            return 0
        if type(delta) is not int:
            return 0
        if u == v:
            return 0
        network.setdefault(u, {})
        network.setdefault(v, {})
        if v not in network[u]:
            if delta < 0:
                return 0
            if delta == 0:
                continue
            network[u][v] = delta
        else:
            new_capacity = network[u][v] + delta
            if new_capacity < 0:
                return 0
            network[u][v] = new_capacity

    final_network = {}
    existing_edges = set()
    for u in sorted(network.keys()):
        for v in sorted(network[u].keys()):
            cap = network[u][v]
            if cap <= 0:
                continue
            if (u, v) in existing_edges:
                return 0
            existing_edges.add((u, v))
            final_network.setdefault(u, {})[v] = cap
    network = final_network

    nodes = set()
    for u in network:
        nodes.add(u)
        for v in network[u]:
            nodes.add(v)
    if source not in nodes:
        nodes.add(source)
    if target not in nodes:
        nodes.add(target)

    def is_path_available():
        if source == target:
            return True
        queue = deque([source])
        visited = {source}
        while queue:
            current = queue.popleft()
            for neighbor in sorted(network.get(current, {})):
                if network[current][neighbor] > 0 and neighbor not in visited:
                    if neighbor == target:
                        return True
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    if not is_path_available():
        return 0

    def build_residual_graph(caps):
        residual = {n: {} for n in nodes}
        for u in caps:
            for v, c in caps[u].items():
                residual[u][v] = c
                residual[v].setdefault(u, 0)
        return residual

    def find_best_augmenting_path(residual):
        all_paths = []
        queue = deque([[source]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbor in sorted(residual.get(current, {})):
                capacity = residual[current][neighbor]
                if capacity <= 0 or neighbor in path:
                    continue
                extended_path = path + [neighbor]
                bottleneck = min(
                    [residual[path[i]][path[i + 1]] for i in range(len(path) - 1)] + [capacity]
                )
                if neighbor == target:
                    all_paths.append((bottleneck, extended_path))
                else:
                    queue.append(extended_path)
        if not all_paths:
            return 0, []
        all_paths.sort(key=lambda x: (-x[0], x[1]))
        best_bottleneck, best_path = all_paths[0]
        return best_bottleneck, best_path

    def apply_flow(residual, path, flow):
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            residual[u][v] -= flow
            residual[v][u] = residual[v].get(u, 0) + flow

    residual_graph = build_residual_graph(network)
    max_flow = 0

    while True:
        bottleneck, path = find_best_augmenting_path(residual_graph)
        if bottleneck == 0:
            break
        max_flow += bottleneck
        apply_flow(residual_graph, path, bottleneck)

    return max_flow


if __name__ == "__main__":
    graph = {
        "0": [["1", 10], ["2", 5]],
        "1": [["2", 5], ["3", 10]],
        "2": [["4", 7]],
        "3": [["4", 8]],
        "4": []
    }
    source = "0"
    target = "4"
    capacity_changes = [
        ["0", "1", 4],
        ["1", "3", -5],
        ["2", "4", 3]
    ]
    print(optimize_water_flow(graph, source, target, capacity_changes))