import heapq
from typing import List, Dict, Any, Optional


def prioritized_topological_sort(n: int, edges: List[List[int]], importance: List[int]) -> Optional[Dict[str, Any]]:
    """
    Compute a priority-aware topological order of tasks in a DAG using Kahn's algorithm.
    """
    # Input validation
    if not isinstance(n, int):
        return {'error': 'n must be an integer'}

    if n < 1 or n > 100000:
        return {'error': 'n out of range'}

    if not isinstance(edges, list):
        return {'error': 'edges must be a list of lists'}

    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2:
            return {'error': 'edge must be a list of two integers'}
        if not isinstance(edge[0], int) or not isinstance(edge[1], int):
            return {'error': 'edge must be a list of two integers'}
        if edge[0] < 0 or edge[0] >= n or edge[1] < 0 or edge[1] >= n:
            return {'error': 'node id out of range'}

    if not isinstance(importance, list):
        return {'error': 'importance must be a list of integers'}

    if len(importance) != n:
        return {'error': 'importance length mismatch'}

    for imp in importance:
        if not isinstance(imp, int):
            return {'error': 'importance must be a list of integers'}

    # Build adjacency list and degree arrays, handling duplicate edges
    adj = [[] for _ in range(n)]
    in_degree = [0] * n
    out_degree = [0] * n
    edge_set = set()

    for u, v in edges:
        if u == v:
            return None

        # Treat duplicate edges as single dependency
        if (u, v) not in edge_set:
            edge_set.add((u, v))
            adj[u].append(v)
            in_degree[v] += 1
            out_degree[u] += 1

    original_in_degrees = in_degree[:]
    original_out_degrees = out_degree[:]

    num_sources = sum(1 for d in in_degree if d == 0)
    num_sinks = sum(1 for d in out_degree if d == 0)

    # Initialize priority queue with all source nodes
    heap = []
    for i in range(n):
        if in_degree[i] == 0:
            heapq.heappush(heap, [-importance[i], i])

    order = []
    levels = [-1] * n
    topo_positions = [-1] * n
    max_parallel_frontier = len(heap)
    frontier_max_importance_sum = sum(importance[i] for i in range(n) if in_degree[i] == 0)
    tie_breaks_count = 0

    for i in range(n):
        if in_degree[i] == 0:
            levels[i] = 0

    current_in_degree = in_degree[:]
    pending_level = [-1] * n 

    # Kahn's algorithm with priority-based selection
    while heap:
        frontier_size = len(heap)
        max_parallel_frontier = max(max_parallel_frontier, frontier_size)

        frontier_importance = sum(importance[item[1]] for item in heap)
        frontier_max_importance_sum = max(frontier_max_importance_sum, frontier_importance)

        tie_for_step = False
        if len(heap) > 1:
            highest_imp = -heap[0][0]
            tied_candidates = 0
            for item in heap:
                if -item[0] == highest_imp:
                    tied_candidates += 1
                else:
                    continue
            if tied_candidates > 1:
                tie_for_step = True

        neg_imp, u = heapq.heappop(heap)
        if tie_for_step:
            tie_breaks_count += 1
        order.append(u)
        topo_positions[u] = len(order) - 1

        for v in adj[u]:
            pending_level[v] = max(pending_level[v], levels[u] + 1)
            current_in_degree[v] -= 1
            if current_in_degree[v] == 0:
                levels[v] = max(levels[v], pending_level[v])
                heapq.heappush(heap, [-importance[v], v])

    processed_count = len(order)
    if processed_count < n:
        return None

    priority_score = sum(importance[order[i]] * (n - i) for i in range(n))

    longest_path_length = max(levels)

    level_widths = [0] * (longest_path_length + 1)
    for level in levels:
        level_widths[level] += 1

    # Compute longest distance from each node to any sink
    longest_dist_to_sink = [0] * n

    for i in range(n - 1, -1, -1):
        u = order[i]
        if out_degree[u] == 0:
            longest_dist_to_sink[u] = 0
        else:
            max_dist = 0
            for v in adj[u]:
                max_dist = max(max_dist, longest_dist_to_sink[v] + 1)
            longest_dist_to_sink[u] = max_dist

    # Calculate latest permissible levels without delaying makespan
    makespan = longest_path_length
    latest_levels = [makespan - longest_dist_to_sink[i] for i in range(n)]

    slack = [latest_levels[i] - levels[i] for i in range(n)]

    cumulative_importance_prefix = []
    cumsum = 0
    for task_id in order:
        cumsum += importance[task_id]
        cumulative_importance_prefix.append(cumsum)

    result = {
        'order': order,
        'statistics': {
            'is_dag': True,
            'processed_count': processed_count,
            'max_parallel_frontier': max_parallel_frontier,
            'priority_score': priority_score,
            'levels': levels,
            'longest_path_length': longest_path_length,
            'num_sources': num_sources,
            'num_sinks': num_sinks,
            'in_degrees': original_in_degrees,
            'out_degrees': original_out_degrees,
            'level_widths': level_widths,
            'latest_levels': latest_levels,
            'slack': slack,
            'topo_positions': topo_positions,
            'cumulative_importance_prefix': cumulative_importance_prefix,
            'frontier_max_importance_sum': frontier_max_importance_sum,
            'tie_breaks_count': tie_breaks_count
        }
    }

    return result


if __name__ == "__main__":
    n = 6
    edges = [
        [0, 2],
        [1, 2],
        [1, 3],
        [2, 4],
        [3, 4],
        [4, 5]
    ]
    importance = [5, 10, 7, 7, 3, 1]
    print(prioritized_topological_sort(n, edges, importance))