from collections import defaultdict

def get_shortest_paths(graph: dict, source: str, updates: list[list[str]]) -> dict:
    def is_valid_id(node_id):
        return isinstance(node_id, str) and node_id.isdigit()
    
    if not isinstance(graph, dict):
        return {}
    if not isinstance(updates, list):
        return {}
    if not is_valid_id(source):
        return {}
    if graph == {} and not updates:
        return {}

    all_nodes = set()
    for node, neighbors in graph.items():
        if not is_valid_id(node) or not isinstance(neighbors, list):
            return {}
        for neighbor in neighbors:
            if not is_valid_id(neighbor):
                return {}
        all_nodes.add(node)
        all_nodes.update(neighbors)

    for update in updates:
        if not (isinstance(update, list) and len(update) == 3):
            return {}
        action, node_a, node_b = update
        if action not in ("activate", "deactivate"):
            return {}
        if not (is_valid_id(node_a) and is_valid_id(node_b)):
            return {}
        all_nodes.update([node_a, node_b])

    all_nodes.add(source)

    def ensure_symmetric(adjacency):
        for node in all_nodes:
            adjacency.setdefault(node, [])
        for node in list(adjacency.keys()):
            adjacency[node] = sorted({nbr for nbr in adjacency[node] if nbr != node})
        for node in list(adjacency.keys()):
            for neighbor in adjacency[node]:
                if node not in adjacency.get(neighbor, []):
                    adjacency.setdefault(neighbor, []).append(node)
        for node in adjacency:
            adjacency[node] = sorted(set(adjacency[node]))

    adjacency = {node: list(neighbors) for node, neighbors in graph.items()}
    ensure_symmetric(adjacency)

    def run_bfs(adjacency, start):
        distance = {n: -1 for n in adjacency}
        parent = {n: None for n in adjacency}
        if start not in adjacency:
            distance[start] = 0
            return distance, parent
        distance[start] = 0
        frontier = [start]
        while frontier:
            frontier.sort()
            next_frontier = []
            for current in frontier:
                for neighbor in adjacency[current]:
                    if distance[neighbor] == -1:
                        distance[neighbor] = distance[current] + 1
                        parent[neighbor] = current
                        next_frontier.append(neighbor)
                    else:
                        candidate = distance[current] + 1
                        if candidate == distance[neighbor] and current < parent.get(neighbor, current):
                            parent[neighbor] = current
            frontier = next_frontier
        return distance, parent

    distance, parent = run_bfs(adjacency, source)

    def apply_updates(adjacency, updates):
        for action, node_a, node_b in updates:
            adjacency.setdefault(node_a, [])
            adjacency.setdefault(node_b, [])
            if node_a == node_b:
                continue
            if action == "activate":
                if node_b not in adjacency[node_a]:
                    adjacency[node_a].append(node_b)
                if node_a not in adjacency[node_b]:
                    adjacency[node_b].append(node_a)
            elif action == "deactivate":
                if node_b in adjacency[node_a]:
                    adjacency[node_a].remove(node_b)
                if node_a in adjacency[node_b]:
                    adjacency[node_b].remove(node_a)
        ensure_symmetric(adjacency)

    apply_updates(adjacency, updates)

    children = defaultdict(list)
    for child, par in parent.items():
        if par is not None:
            children[par].append(child)
    for node in children:
        children[node].sort()

    invalid_nodes = set()
    for child, par in parent.items():
        if child == source or par is None:
            continue
        if child not in adjacency.get(par, []) or par not in adjacency.get(child, []):
            stack = [child]
            while stack:
                node = stack.pop()
                if node in invalid_nodes:
                    continue
                invalid_nodes.add(node)
                for descendant in children.get(node, []):
                    stack.append(descendant)

    for node in invalid_nodes:
        distance[node] = -1
        parent[node] = None

    proposed_distance = {}
    proposed_parent = {}

    def propose(node, via):
        candidate = distance[via] + 1
        if (
            node not in proposed_distance
            or candidate < proposed_distance[node]
            or (candidate == proposed_distance[node] and via < proposed_parent[node])
        ):
            proposed_distance[node] = candidate
            proposed_parent[node] = via

    for node in invalid_nodes:
        for neighbor in adjacency[node]:
            if distance.get(neighbor, -1) >= 0:
                propose(node, neighbor)

    for action, node_a, node_b in updates:
        if action != "activate" or node_a == node_b:
            continue
        if distance.get(node_a, -1) >= 0:
            propose(node_b, node_a)
        if distance.get(node_b, -1) >= 0:
            propose(node_a, node_b)

    frontier = []
    for node in sorted(proposed_distance):
        proposed_dist = proposed_distance[node]
        proposed_par = proposed_parent[node]
        current_dist = distance.get(node, -1)
        if (
            current_dist == -1 or proposed_dist < current_dist
            or (proposed_dist == current_dist and (parent[node] is None or proposed_par < parent[node]))
        ):
            distance[node] = proposed_dist
            parent[node] = proposed_par
            frontier.append(node)

    while frontier:
        frontier.sort()
        next_frontier = []
        for current in frontier:
            for neighbor in adjacency[current]:
                candidate = distance[current] + 1
                neighbor_dist = distance.get(neighbor, -1)
                if neighbor_dist == -1 or candidate < neighbor_dist:
                    distance[neighbor] = candidate
                    parent[neighbor] = current
                    next_frontier.append(neighbor)
                elif candidate == neighbor_dist and current < parent.get(neighbor, current):
                    parent[neighbor] = current
        frontier = next_frontier

    for node in all_nodes.union(adjacency.keys()):
        distance.setdefault(node, -1)
    distance[source] = 0

    return {node: distance[node] for node in sorted(distance)}


if __name__ == "__main__":
    graph = {
        "0": ["1", "2"],
        "1": ["0", "3"],
        "2": ["0", "4"],
        "3": ["1", "5"],
        "4": ["2", "5"],
        "5": ["3", "4", "6"],
        "6": ["5"]
    }
    source = "0"
    updates = [
        ["deactivate", "5", "6"],
        ["activate", "1", "6"],
        ["deactivate", "2", "4"],
        ["activate", "2", "6"],
        ["deactivate", "1", "3"],
        ["activate", "0", "3"],
    ]
    print(get_shortest_paths(graph, source, updates))