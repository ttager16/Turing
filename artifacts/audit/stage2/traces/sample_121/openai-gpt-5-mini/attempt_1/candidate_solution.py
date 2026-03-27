def compute_mst_with_capacity(graph: List[List], data_loads: Dict[str, int]) -> dict:
    # Input validation
    if not isinstance(graph, list):
        return {'error': "Graph must be a list of edges."}
    if not isinstance(data_loads, dict):
        return {'error': "Data loads must be a dictionary."}

    # Normalize and validate edges, collect phases
    edges_raw = []
    phases_set = set()
    max_node = -1
    for e in graph:
        if not (isinstance(e, list) and len(e) == 4):
            return {'error': "Each edge must be a list of [start, end, cost, capacity_map]."}
        u, v, cost, capmap = e
        if not (isinstance(cost, (int, float))):
            return {'error': "Edge cost must be a number."}
        if not isinstance(capmap, dict):
            return {'error': "Edge capacity_map must be a dictionary."}
        try:
            u_int = int(u)
            v_int = int(v)
        except Exception:
            u_int = u
            v_int = v
        a, b = (u_int, v_int) if u_int <= v_int else (v_int, u_int)
        for k in capmap.keys():
            phases_set.add(k)
        max_node = max(max_node, u_int, v_int)
        edges_raw.append([a, b, float(cost), dict(capmap)])

    node_count = max_node + 1 if max_node >= 0 else 0
    phases = sorted(phases_set)

    # Helper to sum bidirectional loads for an edge and phase
    def load_for(edge_u, edge_v, phase):
        k1 = f"{edge_u},{edge_v},{phase}"
        k2 = f"{edge_v},{edge_u},{phase}"
        return int(data_loads.get(k1, 0)) + int(data_loads.get(k2, 0))

    # Exclude edges that lack capacity definitions for any phase present
    filtered_edges = []
    pruned_edges = 0
    for u, v, cost, cmap in edges_raw:
        if any(p not in cmap for p in phases):
            pruned_edges += 1
            continue
        # Check capacity validation: if any phase total load > capacity -> exclude
        violates = False
        for p in phases:
            ld = load_for(u, v, p)
            cap = cmap.get(p, 0)
            if ld > cap:
                violates = True
                break
        if violates:
            pruned_edges += 1
            continue
        filtered_edges.append([u, v, cost, cmap])

    # If no nodes or no valid edges
    if node_count == 0 or not filtered_edges:
        return {
            'mst': [],
            'total_cost': 0,
            'edge_count': 0,
            'valid': False,
            'capacity_analysis': {
                'average_utilization': 0.0,
                'max_utilization': 0.0,
                'min_utilization': 0.0,
                'bottleneck_edges': [],
                'underutilized_edges': []
            },
            'graph_metrics': {
                'node_count': node_count,
                'density': 0.0,
                'cost_savings_percent': 0.0,
                'pruned_edges': pruned_edges,
                'average_degree': 0.0,
                'max_degree': 0,
                'min_degree': 0
            },
            'phase_analysis': {
                'phases': phases,
                'total_phases': len(phases),
                'critical_phase': None,
                'phase_details': {}
            },
            'edge_efficiency': {
                'most_efficient_edge': None,
                'least_efficient_edge': None,
                'average_efficiency': 0.0,
                'all_edges': []
            }
        }

    # Kruskal's algorithm with Union-Find
    parent = {i: i for i in range(node_count)}
    rank = {i: 0 for i in range(node_count)}
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        rx, ry = find(x), find(y)
        if rx == ry:
            return False
        if rank[rx] < rank[ry]:
            parent[rx] = ry
        elif rank[ry] < rank[rx]:
            parent[ry] = rx
        else:
            parent[ry] = rx
            rank[rx] += 1
        return True

    # Sort edges by cost stable
    filtered_edges.sort(key=lambda z: z[2])

    mst_edges = []
    total_cost = 0.0
    for u, v, cost, cmap in filtered_edges:
        if len(mst_edges) == max(0, node_count - 1):
            break
        if union(u, v):
            mst_edges.append([u, v, cost, cmap])
            total_cost += cost

    valid = (len(mst_edges) == node_count - 1 and node_count > 0)

    if not valid:
        return {
            'mst': [],
            'total_cost': 0,
            'edge_count': 0,
            'valid': False,
            'capacity_analysis': {
                'average_utilization': 0.0,
                'max_utilization': 0.0,
                'min_utilization': 0.0,
                'bottleneck_edges': [],
                'underutilized_edges': []
            },
            'graph_metrics': {
                'node_count': node_count,
                'density': 0.0,
                'cost_savings_percent': 0.0,
                'pruned_edges': pruned_edges,
                'average_degree': 0.0,
                'max_degree': 0,
                'min_degree': 0
            },
            'phase_analysis': {
                'phases': phases,
                'total_phases': len(phases),
                'critical_phase': None,
                'phase_details': {}
            },
            'edge_efficiency': {
                'most_efficient_edge': None,
                'least_efficient_edge': None,
                'average_efficiency': 0.0,
                'all_edges': []
            }
        }

    # Build MST output list sorted by cost
    mst_edges.sort(key=lambda x: x[2])
    mst_output = [[int(e[0]), int(e[1]), int(e[2]) if float(e[2]).is_integer() else e[2]] for e in mst_edges]
    edge_count = len(mst_edges)
    total_cost_val = int(total_cost) if float(total_cost).is_integer() else total_cost

    # Capacity analysis per edge
    per_edge_utils = []
    bottlenecks = []
    underutilized = []
    all_phase_utils = []
    phase_totals_load = {p: 0 for p in phases}
    phase_totals_cap = {p: 0 for p in phases}
    edge_eff_list = []
    degrees = defaultdict(int)

    for u, v, cost, cmap in mst_edges:
        degrees[u] += 1
        degrees[v] += 1
        phase_utils = []
        total_load_edge = 0
        total_capacity_edge = 0
        for p in phases:
            ld = load_for(u, v, p)
            cap = cmap.get(p, 0)
            phase_totals_load[p] += ld
            phase_totals_cap[p] += cap
            total_load_edge += ld
            total_capacity_edge += cap
            util = (ld / cap * 100) if cap > 0 else 0.0
            phase_utils.append(util)
            all_phase_utils.append(util)
        avg_util = round(sum(phase_utils) / len(phase_utils), 2) if phase_utils else 0.0
        max_util = round(max(phase_utils), 2) if phase_utils else 0.0
        min_util = round(min(phase_utils), 2) if phase_utils else 0.0
        per_edge_utils.append({'edge': [int(u), int(v)], 'avg': avg_util, 'max': max_util, 'min': min_util})
        if max_util > 80:
            bottlenecks.append([int(u), int(v), round(max_util, 2)])
        if avg_util < 30:
            underutilized.append([int(u), int(v), round(avg_util, 2)])
        efficiency = round((total_load_edge / cost) , 2) if cost != 0 else float('inf')
        edge_eff_list.append({'edge': [int(u), int(v)], 'cost': int(cost) if float(cost).is_integer() else cost,
                              'total_load': int(total_load_edge), 'efficiency': efficiency})

    avg_utilization = round((sum(e['avg'] for e in per_edge_utils) / len(per_edge_utils)), 2) if per_edge_utils else 0.0
    max_utilization = round(max(all_phase_utils), 2) if all_phase_utils else 0.0
    min_utilization = round(min(all_phase_utils), 2) if all_phase_utils else 0.0

    # Graph metrics
    max_possible_edges = node_count * (node_count - 1) / 2 if node_count > 0 else 1
    density = round((edge_count / max_possible_edges) * 100, 2) if max_possible_edges > 0 else 0.0
    total_available_costs = sum(e[2] for e in edges_raw)
    cost_savings_percent = round(((total_available_costs - total_cost) / total_available_costs) * 100, 2) if total_available_costs > 0 else 0.0
    avg_degree = round(sum(degrees.values()) / node_count, 2) if node_count > 0 else 0.0
    max_degree = max(degrees.values()) if degrees else 0
    min_degree = min(degrees.values()) if degrees else 0

    # Phase analysis
    phase_details = {}
    critical_phase = None
    critical_util_val = -1
    for p in phases:
        tot_load = phase_totals_load.get(p, 0)
        tot_cap = phase_totals_cap.get(p, 0)
        util = round((tot_load / tot_cap) * 100, 2) if tot_cap > 0 else 0.0
        phase_details[p] = {'total_load': int(tot_load), 'total_capacity': int(tot_cap), 'utilization': util, 'edge_count': edge_count}
        if util > critical_util_val:
            critical_util_val = util
            critical_phase = p

    # Edge efficiency ranking
    sorted_eff = sorted(edge_eff_list, key=lambda x: x['efficiency'], reverse=True)
    average_efficiency = round((sum(e['efficiency'] for e in sorted_eff) / len(sorted_eff)), 2) if sorted_eff else 0.0
    most_eff = sorted_eff[0] if sorted_eff else None
    least_eff = sorted_eff[-1] if sorted_eff else None

    result = {
        'mst': mst_output,
        'total_cost': int(total_cost_val) if isinstance(total_cost_val, float) and float(total_cost_val).is_integer() else total_cost_val,
        'edge_count': edge_count,
        'valid': True,
        'capacity_analysis': {
            'average_utilization': avg_utilization,
            'max_utilization': max_utilization,
            'min_utilization': min_utilization,
            'bottleneck_edges': [[e[0], e[1], round(e[2], 2)] for e in bottlenecks],
            'underutilized_edges': [[e[0], e[1], round(e[2], 2)] for e in underutilized]
        },
        'graph_metrics': {
            'node_count': node_count,
            'density': density,
            'cost_savings_percent': cost_savings_percent,
            'pruned_edges': pruned_edges,
            'average_degree': avg_degree,
            'max_degree': int(max_degree),
            'min_degree': int(min_degree)
        },
        'phase_analysis': {
            'phases': phases,
            'total_phases': len(phases),
            'critical_phase': critical_phase if mst_edges else None,
            'phase_details': phase_details
        },
        'edge_efficiency': {
            'most_efficient_edge': most_eff if most_eff else None,
            'least_efficient_edge': least_eff if least_eff else None,
            'average_efficiency': average_efficiency,
            'all_edges': sorted_eff
        }
    }
    return result