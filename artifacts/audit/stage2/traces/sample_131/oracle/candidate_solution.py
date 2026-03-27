from typing import List, Union
import math
import heapq
from collections import deque, defaultdict

def optimize_route_planning(
    graph_data: List[List[Union[int, float]]],
    queries: List[List[Union[str, int, float, None]]]
) -> List[Union[float, bool]]:
    def is_valid_node(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1

    def is_valid_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

    def is_list_of_lists(value):
        return isinstance(value, list) and all(isinstance(item, list) for item in value)

    if graph_data == [] and queries == []:
        return []
    if not (is_list_of_lists(graph_data) and is_list_of_lists(queries)):
        return []

    edges = {}
    adjacency = defaultdict(dict)

    def make_edge_key(a, b):
        return (a, b) if a < b else (b, a)

    def rebuild_adjacency():
        adjacency.clear()
        for (a, b), info in edges.items():
            w, c = info["w"], info["cap"]
            adjacency[a][b] = (w, c)
            adjacency[b][a] = (w, c)

    for edge in graph_data:
        if len(edge) != 3:
            return []
        u, v, weight = edge
        if not (is_valid_node(u) and is_valid_node(v)):
            return []
        if u == v:
            return []
        if not is_valid_number(weight):
            return []
        key = make_edge_key(u, v)
        if key in edges:
            edges[key]["w"] = min(edges[key]["w"], float(weight))
        else:
            edges[key] = {"w": float(weight), "cap": 0.0}

    rebuild_adjacency()

    valid_queries = {
        "shortest_path", "connectivity_check",
        "add_edge", "remove_edge",
        "update_weight", "update_capacity"
    }

    results = []

    def shortest_path(start, end, demand):
        if start == end:
            return 0.0
        if start not in adjacency or end not in adjacency:
            return -1.0
        dist = {start: 0.0}
        queue = [(0.0, start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != dist.get(node, float("inf")):
                continue
            if node == end:
                return cost
            for neighbor in sorted(adjacency.get(node, {})):
                weight, capacity = adjacency[node][neighbor]
                if capacity < demand:
                    continue
                new_cost = cost + weight
                if new_cost < dist.get(neighbor, float("inf")):
                    dist[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, neighbor))
        return -1.0

    def check_connectivity(start, end):
        if start == end:
            return True
        if start not in adjacency or end not in adjacency:
            return False
        visited = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in sorted(adjacency.get(node, {})):
                if neighbor not in visited:
                    visited.add(neighbor)
                    if neighbor == end:
                        return True
                    queue.append(neighbor)
        return False

    for query in queries:
        if len(query) != 4:
            return []
        query_type, u, v, arg = query
        if query_type not in valid_queries:
            return []
        if not (is_valid_node(u) and is_valid_node(v)):
            return []
        if query_type in {"add_edge", "update_weight", "update_capacity"} and u == v:
            return []

        if query_type == "shortest_path":
            demand = 0.0 if arg is None else arg
            if not is_valid_number(demand):
                return []
            result = shortest_path(u, v, float(demand))
            results.append(float(result))

        elif query_type == "connectivity_check":
            if arg is not None:
                if not (isinstance(arg, (int, float)) and not isinstance(arg, bool) and arg == 0):
                    return []
            results.append(check_connectivity(u, v))

        elif query_type == "add_edge":
            if not is_valid_number(arg):
                return []
            weight = float(arg)
            key = make_edge_key(u, v)
            if key in edges:
                if weight < edges[key]["w"]:
                    edges[key]["w"] = weight
            else:
                edges[key] = {"w": weight, "cap": 0.0}
            a, b = key
            adjacency[a][b] = (edges[key]["w"], edges[key]["cap"])
            adjacency[b][a] = (edges[key]["w"], edges[key]["cap"])

        elif query_type == "remove_edge":
            if arg is not None:
                if not (isinstance(arg, (int, float)) and not isinstance(arg, bool) and arg == 0):
                    return []
            key = make_edge_key(u, v)
            if key in edges:
                del edges[key]
                a, b = key
                if b in adjacency.get(a, {}):
                    del adjacency[a][b]
                    if not adjacency[a]:
                        del adjacency[a]
                if a in adjacency.get(b, {}):
                    del adjacency[b][a]
                    if not adjacency[b]:
                        del adjacency[b]

        elif query_type == "update_weight":
            if not is_valid_number(arg):
                return []
            key = make_edge_key(u, v)
            if key not in edges:
                return []
            edges[key]["w"] = float(arg)
            a, b = key
            adjacency[a][b] = (edges[key]["w"], edges[key]["cap"])
            adjacency[b][a] = (edges[key]["w"], edges[key]["cap"])

        elif query_type == "update_capacity":
            if not is_valid_number(arg):
                return []
            key = make_edge_key(u, v)
            if key not in edges:
                return []
            edges[key]["cap"] = float(arg)
            a, b = key
            adjacency[a][b] = (edges[key]["w"], edges[key]["cap"])
            adjacency[b][a] = (edges[key]["w"], edges[key]["cap"])
        else:
            return []

    return results


if __name__ == "__main__":
    graph_data = [[1, 2, 5.0], [2, 3, 10.0], [1, 3, 15.0]]
    queries = [
        ["shortest_path", 1, 3, 0],
        ["connectivity_check", 1, 3, 0]
    ]
    print(optimize_route_planning(graph_data, queries))