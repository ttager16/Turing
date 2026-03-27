from typing import List, Dict, Any, Union
import math


def build_minimum_spanning_tree(n: int, edges: List[List[int]]) -> Union[Dict[str, Any], None]:
    if n == 1:
        return {
            'mst_edges': [],
            'statistics': {
                'total_cost': 0,
                'num_edges': 0,
                'max_edge_weight': 0,
                'min_edge_weight': 0,
                'positive_cost_sum': 0,
                'negative_cost_sum': 0,
                'num_positive_edges': 0,
                'num_negative_edges': 0,
                'avg_edge_weight': 0,
                'edge_weight_range': 0,
                'second_best_total_cost': None,
                'min_swap_delta': None,
                'max_swap_delta': None,
                'bridges_count': 0,
                'edge_weight_median': 0,
                'cost_stddev': 0.00
            }
        }

    edge_dict: Dict[tuple, int] = {}
    for u, v, w in edges:
        if u == v:
            continue
        if u < 0 or u >= n or v < 0 or v >= n:
            continue
        a, b = (u, v) if u < v else (v, u)
        key = (a, b)
        if key not in edge_dict or w < edge_dict[key]:
            edge_dict[key] = w

    if len(edge_dict) < n - 1:
        return None

    normalized_edges: List[List[int]] = [[u, v, w] for (u, v), w in edge_dict.items()]
    normalized_edges.sort(key=lambda e: (e[2], e[0], e[1]))

    parent = list(range(n))
    rank = [0] * n

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> bool:
        rx, ry = find(x), find(y)
        if rx == ry:
            return False
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1
        return True

    mst_edges_pairs: List[List[int]] = []
    mst_edge_weights: List[int] = []
    mst_adj: List[List[tuple]] = [[] for _ in range(n)]

    for u, v, w in normalized_edges:
        if union(u, v):
            a, b = (u, v) if u < v else (v, u)
            mst_edges_pairs.append([a, b])
            mst_edge_weights.append(w)
            mst_adj[u].append((v, w))
            mst_adj[v].append((u, w))
            if len(mst_edges_pairs) == n - 1:
                break

    if len(mst_edges_pairs) != n - 1:
        return None

    mst_edges_pairs.sort()

    total_cost = sum(mst_edge_weights)
    num_edges = len(mst_edge_weights)
    max_edge_weight = max(mst_edge_weights)
    min_edge_weight = min(mst_edge_weights)

    positive_cost_sum = sum(w for w in mst_edge_weights if w > 0)
    negative_cost_sum = sum(w for w in mst_edge_weights if w < 0)
    num_positive_edges = sum(1 for w in mst_edge_weights if w > 0)
    num_negative_edges = sum(1 for w in mst_edge_weights if w < 0)

    avg_edge_weight = round(total_cost / num_edges) if num_edges > 0 else 0
    edge_weight_range = max_edge_weight - min_edge_weight if num_edges > 0 else 0

    sorted_weights = sorted(mst_edge_weights)
    if num_edges % 2 == 1:
        edge_weight_median = sorted_weights[num_edges // 2]
    else:
        mid = num_edges // 2
        edge_weight_median = round((sorted_weights[mid - 1] + sorted_weights[mid]) / 2)

    mean = total_cost / num_edges if num_edges > 0 else 0.0
    variance = (sum((w - mean) ** 2 for w in mst_edge_weights) / num_edges) if num_edges > 0 else 0.0
    cost_stddev = round(math.sqrt(variance), 2)

    tarjan_adj: List[List[tuple]] = [[] for _ in range(n)]
    undirected_pairs = set()
    for u, v, _w in edges:
        if u == v or u < 0 or u >= n or v < 0 or v >= n:
            continue
        a, b = (u, v) if u < v else (v, u)
        undirected_pairs.add((a, b))

    edge_id = 0
    for a, b in undirected_pairs:
        tarjan_adj[a].append((b, edge_id))
        tarjan_adj[b].append((a, edge_id))
        edge_id += 1

    visited = [False] * n

    def dfs_conn(node: int) -> None:
        visited[node] = True
        for neighbor, _ in tarjan_adj[node]:
            if not visited[neighbor]:
                dfs_conn(neighbor)

    if n > 0:
        dfs_conn(0)
    is_connected = all(visited)

    if not is_connected:
        bridges_count = None
    else:
        timer = 0
        tin = [-1] * n
        low = [-1] * n
        bridges_count = 0

        def dfs_bridges(u: int, parent_edge_id: int) -> None:
            nonlocal timer, bridges_count
            tin[u] = low[u] = timer
            timer += 1
            for v, eid in tarjan_adj[u]:
                if eid == parent_edge_id:
                    continue
                if tin[v] == -1:
                    dfs_bridges(v, eid)
                    low[u] = min(low[u], low[v])
                    if low[v] > tin[u]:
                        bridges_count += 1
                else:
                    low[u] = min(low[u], tin[v])

        for i in range(n):
            if tin[i] == -1 and tarjan_adj[i]:
                dfs_bridges(i, -1)

    LOG = n.bit_length()
    up = [[-1] * n for _ in range(LOG)]
    NEG_INF = -10**9 - 5
    POS_INF = 10**9 + 5
    mx = [[NEG_INF] * n for _ in range(LOG)]
    mn = [[POS_INF] * n for _ in range(LOG)]
    depth = [0] * n

    def dfs_mst(u: int, p: int, w_par: int) -> None:
        up[0][u] = p
        if p == -1:
            mx[0][u] = NEG_INF
            mn[0][u] = POS_INF
        else:
            mx[0][u] = w_par
            mn[0][u] = w_par
        for v, w in mst_adj[u]:
            if v == p:
                continue
            depth[v] = depth[u] + 1
            dfs_mst(v, u, w)

    dfs_mst(0, -1, NEG_INF)

    for k in range(1, LOG):
        for v in range(n):
            if up[k - 1][v] != -1:
                up[k][v] = up[k - 1][up[k - 1][v]]
                mx[k][v] = max(mx[k - 1][v], mx[k - 1][up[k - 1][v]])
                mn[k][v] = min(mn[k - 1][v], mn[k - 1][up[k - 1][v]])
            else:
                up[k][v] = -1
                mx[k][v] = NEG_INF
                mn[k][v] = POS_INF

    def extremes_on_path(a: int, b: int) -> tuple:
        if a == b:
            return (POS_INF, NEG_INF)
        res_max = NEG_INF
        res_min = POS_INF
        if depth[a] < depth[b]:
            a, b = b, a
        diff = depth[a] - depth[b]
        for k in range(LOG):
            if (diff >> k) & 1:
                res_max = max(res_max, mx[k][a])
                res_min = min(res_min, mn[k][a])
                a = up[k][a]
        if a == b:
            return (res_min, res_max)
        for k in range(LOG - 1, -1, -1):
            if up[k][a] != up[k][b]:
                res_max = max(res_max, mx[k][a], mx[k][b])
                res_min = min(res_min, mn[k][a], mn[k][b])
                a = up[k][a]
                b = up[k][b]
        res_max = max(res_max, mx[0][a], mx[0][b])
        res_min = min(res_min, mn[0][a], mn[0][b])
        return (res_min, res_max)

    second_best_total_cost = None
    min_swap_delta = None
    max_swap_delta = None
    mst_pairs_set = set((u, v) for u, v in mst_edges_pairs)

    for u, v, w in normalized_edges:
        a, b = (u, v) if u < v else (v, u)
        if (a, b) in mst_pairs_set:
            continue
        min_on_path, max_on_path_val = extremes_on_path(u, v)
        delta = w - max_on_path_val
        if delta > 0:
            if min_swap_delta is None or delta < min_swap_delta:
                min_swap_delta = delta
            if max_swap_delta is None or delta > max_swap_delta:
                max_swap_delta = delta
            candidate = total_cost + delta
            if second_best_total_cost is None or candidate < second_best_total_cost:
                second_best_total_cost = candidate

    return {
        'mst_edges': mst_edges_pairs,
        'statistics': {
            'total_cost': total_cost,
            'num_edges': num_edges,
            'max_edge_weight': max_edge_weight,
            'min_edge_weight': min_edge_weight,
            'positive_cost_sum': positive_cost_sum,
            'negative_cost_sum': negative_cost_sum,
            'num_positive_edges': num_positive_edges,
            'num_negative_edges': num_negative_edges,
            'avg_edge_weight': avg_edge_weight,
            'edge_weight_range': edge_weight_range,
            'second_best_total_cost': second_best_total_cost,
            'min_swap_delta': min_swap_delta,
            'max_swap_delta': max_swap_delta,
            'bridges_count': bridges_count,
            'edge_weight_median': edge_weight_median,
            'cost_stddev': cost_stddev
        }
    }


if __name__ == "__main__":
    n = 5
    edges = [
        [0, 1, 3],
        [0, 2, 2],
        [1, 2, 1],
        [1, 3, 4],
        [2, 3, 5],
        [2, 4, -2],
        [3, 4, 3]
    ]
    print(build_minimum_spanning_tree(n, edges))