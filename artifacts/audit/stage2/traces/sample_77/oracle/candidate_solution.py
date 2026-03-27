from typing import List, Any

def schedule_tasks(tasks: List[List[Any]], operations: List[List[Any]]) -> List[str]:
    def is_string(x):
        return isinstance(x, str)

    def is_integer(x):
        return isinstance(x, int) and not isinstance(x, bool)

    def is_list_pair(x):
        return isinstance(x, list) and len(x) == 2

    allowed_operations = {"link", "split", "merge", "adjust", "balance"}
    MERGE_CAP_LIMIT = 100
    capacities = {}
    links = {}
    seen_names = set()

    for item in tasks:
        if not (isinstance(item, list) and len(item) == 2):
            return []
        capacity_value, cluster_name = item
        if not (is_integer(capacity_value) and capacity_value >= 0 and is_string(cluster_name)):
            return []
        if cluster_name in seen_names:
            return []
        seen_names.add(cluster_name)
        capacities[cluster_name] = capacity_value
        links[cluster_name] = set()

    def cluster_exists(name: str) -> bool:
        return name in capacities

    for op in operations:
        if not (isinstance(op, list) and len(op) == 2 and is_string(op[0])):
            return []
        operation_type, payload = op
        if operation_type not in allowed_operations:
            return []

        if operation_type == "link":
            if not is_list_pair(payload):
                return []
            cluster_a, cluster_b = payload
            if not (is_string(cluster_a) and is_string(cluster_b) and cluster_a != cluster_b):
                return []
            if not (cluster_exists(cluster_a) and cluster_exists(cluster_b)):
                return []
            links[cluster_a].add(cluster_b)
            links[cluster_b].add(cluster_a)

        elif operation_type == "split":
            if not is_string(payload):
                return []
            cluster_a = payload
            if not cluster_exists(cluster_a):
                return []
            capacities[cluster_a] = capacities[cluster_a] // 2

        elif operation_type == "merge":
            if not is_list_pair(payload):
                return []
            target_cluster, source_cluster = payload
            if not (is_string(target_cluster) and is_string(source_cluster) and target_cluster != source_cluster):
                return []
            if not (cluster_exists(target_cluster) and cluster_exists(source_cluster)):
                return []
            combined = capacities[target_cluster] + capacities[source_cluster]
            if combined > MERGE_CAP_LIMIT:
                return []
            capacities[target_cluster] = combined
            for neighbor in links.get(source_cluster, ()):
                if neighbor != target_cluster:
                    links[target_cluster].add(neighbor)
                    if neighbor in links:
                        links[neighbor].discard(source_cluster)
                        links[neighbor].add(target_cluster)
            del capacities[source_cluster]
            links.pop(source_cluster, None)

        elif operation_type == "adjust":
            if not is_list_pair(payload):
                return []
            delta, cluster_a = payload
            if not (is_integer(delta) and is_string(cluster_a)):
                return []
            if not cluster_exists(cluster_a):
                return []
            new_cap = capacities[cluster_a] + delta
            if new_cap < 0:
                new_cap = 0
            capacities[cluster_a] = new_cap

        elif operation_type == "balance":
            if not is_list_pair(payload):
                return []
            cluster_a, cluster_b = payload
            if not (is_string(cluster_a) and is_string(cluster_b) and cluster_a != cluster_b):
                return []
            if not (cluster_exists(cluster_a) and cluster_exists(cluster_b)):
                return []
            capacity_a, capacity_b = capacities[cluster_a], capacities[cluster_b]
            if capacity_a == capacity_b:
                continue
            if capacity_a > capacity_b:
                larger, smaller = cluster_a, cluster_b
                larger_cap, smaller_cap = capacity_a, capacity_b
            else:
                larger, smaller = cluster_b, cluster_a
                larger_cap, smaller_cap = capacity_b, capacity_a
            if 2 * larger_cap > 3 * smaller_cap:
                difference = larger_cap - smaller_cap
                transfer = difference // 2
                capacities[larger] = larger_cap - transfer
                capacities[smaller] = smaller_cap + transfer

        for v in capacities.values():
            if not (is_integer(v) and v >= 0):
                return []

    return [name for name, _ in sorted(capacities.items(), key=lambda item: (-item[1], item[0]))]


if __name__ == "__main__":
    tasks = [
        [10, 'cluster_A'],
        [7,  'cluster_B'],
        [15, 'cluster_C']
    ]
    operations = [
        ['link',   ['cluster_A', 'cluster_B']],
        ['split',  'cluster_C'],
        ['merge',  ['cluster_C', 'cluster_B']],
        ['adjust', [5, 'cluster_A']],
        ['balance', ['cluster_A', 'cluster_C']],
    ]
    result = schedule_tasks(tasks, operations)
    print(result)