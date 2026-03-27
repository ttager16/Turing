from typing import Dict, List
import heapq

def find_graph_center(graph: Dict[str, List[List[int]]]) -> int:
    if not isinstance(graph, dict) or not graph:
        return -1

    def is_int_string(node):
        return isinstance(node, str) and node.isdigit()

    try:
        for node, edges in graph.items():
            if not is_int_string(node) or not isinstance(edges, list):
                return -1
            for edge in edges:
                if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                    return -1
                neighbor, weight = edge
                if not isinstance(neighbor, int) or not isinstance(weight, int):
                    return -1
                if weight < 0 or weight > 10**9:
                    return -1
    except Exception:
        return -1

    adjacency = {}

    def add_edge(u, v, w):
        if u == v:
            return
        if u not in adjacency:
            adjacency[u] = {}
        if v not in adjacency[u] or w < adjacency[u][v]:
            adjacency[u][v] = w

    for node_str in graph.keys():
        u = int(node_str)
        if u not in adjacency:
            adjacency[u] = {}

    for u_str, edges in graph.items():
        u = int(u_str)
        for v, w in edges:
            if not isinstance(v, int) or not isinstance(w, int) or w < 0 or w > 10**9:
                return -1
            add_edge(u, v, w)
            add_edge(v, u, w)

    if not adjacency:
        return -1

    visited = set()
    components = []

    for start in list(adjacency.keys()):
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacency.get(current, {}):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))

    def find_farthest_node(start, allowed):
        seen = {start}
        stack = [(start, 0)]
        farthest, depth = start, 0
        while stack:
            node, dist = stack.pop()
            if dist > depth or (dist == depth and node < farthest):
                depth, farthest = dist, node
            for neighbor in adjacency.get(node, {}):
                if neighbor in allowed and neighbor not in seen:
                    seen.add(neighbor)
                    stack.append((neighbor, dist + 1))
        return farthest

    INF = 10**30

    def run_dijkstra(source, allowed, cutoff):
        dist = {n: INF for n in allowed}
        dist[source] = 0
        queue = [(0, source)]
        while queue:
            d, node = heapq.heappop(queue)
            if d != dist[node]:
                continue
            if d > cutoff:
                return dist, cutoff + 1, True
            for neighbor, weight in adjacency.get(node, {}).items():
                if neighbor not in allowed:
                    continue
                new_dist = d + weight
                if new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    heapq.heappush(queue, (new_dist, neighbor))
        eccentricity = max(dist.values())
        return dist, eccentricity, False

    def compute_component_center(nodes):
        allowed = set(nodes)
        if len(nodes) == 1:
            return nodes[0], 0
        degrees = {n: len(adjacency.get(n, {})) for n in nodes}
        smallest_id = nodes[0]
        highest_degree_node = min(nodes, key=lambda n: (-degrees[n], n))
        node_a = find_farthest_node(smallest_id, allowed)
        node_b = find_farthest_node(node_a, allowed)
        candidates = {smallest_id, highest_degree_node, node_a, node_b}
        lower_bound = {n: 0 for n in nodes}
        evaluated = set()
        best_node = None
        best_eccentricity = INF
        priority_queue = []

        def update_bounds(distances, ecc):
            for n in nodes:
                d_old = lower_bound[n]
                d = distances[n]
                lb = max(d, ecc - d)
                if lb > d_old:
                    lower_bound[n] = lb
                    heapq.heappush(priority_queue, (lower_bound[n], n))

        for src in sorted(candidates):
            if src in evaluated:
                continue
            cutoff = best_eccentricity - 1 if best_eccentricity < INF else INF
            dist, ecc, aborted = run_dijkstra(src, allowed, cutoff)
            evaluated.add(src)
            if not aborted:
                update_bounds(dist, ecc)
            if ecc < best_eccentricity or (ecc == best_eccentricity and (best_node is None or src < best_node)):
                best_eccentricity, best_node = ecc, src

        for _node in nodes:
            heapq.heappush(priority_queue, (lower_bound[_node], _node))

        while priority_queue:
            lb, node = heapq.heappop(priority_queue)
            if node in evaluated or lb != lower_bound[node]:
                continue
            if lower_bound[node] >= best_eccentricity:
                break
            cutoff = best_eccentricity - 1 if best_eccentricity < INF else INF
            dist, ecc, aborted = run_dijkstra(node, allowed, cutoff)
            evaluated.add(node)
            if not aborted:
                update_bounds(dist, ecc)
            if ecc < best_eccentricity or (ecc == best_eccentricity and node < best_node):
                best_eccentricity, best_node = ecc, node
        return best_node, best_eccentricity

    global_best_node = None
    global_best_eccentricity = INF
    singletons = []
    has_non_singleton = False

    for comp in components:
        if len(comp) == 1:
            singletons.append(comp[0])
        else:
            has_non_singleton = True
            node, ecc = compute_component_center(comp)
            if ecc < global_best_eccentricity or (ecc == global_best_eccentricity and (global_best_node is None or node < global_best_node)):
                global_best_eccentricity, global_best_node = ecc, node

    if has_non_singleton:
        return global_best_node if global_best_node is not None else -1
    return min(singletons) if singletons else -1


if __name__ == "__main__":
    graph = {
        "0": [[1, 7], [1, 2], [0, 9]],
        "1": [[0, 7], [0, 2], [2, 3]],
        "2": [[1, 3], [3, 1]],
        "3": [[2, 1]],
        "4": [],
        "5": [[6, 1]],
        "6": [[5, 1]]
    }
    print(find_graph_center(graph))