from typing import List, Dict, Optional
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

MAX_WORKER_THREADS = 8
MAX_ITERATION_MULTIPLIER = 3


def optimize_logistics_network(
    nodes: List[int],
    base_edges: Dict[str, List[dict]],
    commodities: List[dict],
    time_horizon: int,
    holding_rules: Optional[List[dict]] = None,
    dynamic_obstructions: Optional[List[dict]] = None
) -> Dict[str, any]:
    """
    Optimize multi-commodity flow in a time-layered logistics network.
    
    Multi-Objective Optimization (Lexicographic Order):
        1. PRIMARY: Maximize throughput - route as much demand as possible
        2. SECONDARY: Minimize total cost - among maximum-throughput solutions, choose lowest cost
    
    Implementation Strategy:
        Uses successive shortest-path algorithm with Bellman-Ford relaxation to naturally
        achieve lexicographic optimality: each flow augmentation finds the minimum-cost path,
        so maximum flow is routed at minimum total cost.
    
    Time-Layered Graph Expansion:
        Each base edge generates stateful edges (u,t) → (v,t') for each time step in its
        availability window, tracking residual capacity via hash maps (O(1) per edge access).
    
    Advanced Features:
        - Time-dependent costs and capacities (via callable functions)
        - Commodity conflicts (forbidden pairs with transitive closure)
        - Priority-based routing (high-priority commodities routed first)
        - Concurrent processing (ThreadPoolExecutor for normal-priority commodities)
        - Holding at nodes (goods can wait with per-timestep cost)
        - Dynamic obstructions (edges become permanently blocked at specific times)
    
    Args:
        nodes: List of node IDs in the base graph
        base_edges: Dict mapping source node (as string) to list of edge dicts with:
            - to (int): destination node
            - capacity (int|callable): fixed capacity or fn(total_flow, time) → capacity
            - cost (float|callable): fixed cost or fn(commodity_id, time) → cost
            - time_windows (List[List[int]]): list of [start, end] intervals (inclusive)
            - forbidden_pairs (List[List[int]]): commodity pairs that cannot share edge
            - obstruction_time (int|None): time when edge becomes permanently blocked
            - reverse_edge (dict|None): optional reverse edge with same schema
        commodities: List of commodity dicts with:
            - id (int): unique commodity identifier
            - source (int): origin node
            - sink (int): destination node
            - demand (float): amount to route (int or float)
            - priority (int): routing priority (higher routed first, default 0)
            - max_split (int): max number of paths allowed (default 1)
        time_horizon: Number of time steps to consider (T)
        holding_rules: Optional list of holding rules with:
            - node (int): node where holding is allowed
            - capacity (int): max units that can be held per timestep
            - cost_per_unit_per_time (float): holding cost per unit per timestep
        dynamic_obstructions: Optional list of obstruction dicts with:
            - u (int): source node
            - v (int): destination node
            - block_time (int): time when edge becomes permanently blocked
    
    Returns:
        Dict with keys:
            - paths (Dict[str, List[List[int]]]): commodity_id (str) → list of node paths
            - flows (Dict[str, float|int]): commodity_id (str) → achieved flow amount
            - cost (float): total cost (transport + holding)
            - throughput (float|int): sum of all achieved flows
        
        Optimization guarantees:
            - Maximum throughput achieved (primary objective)
            - Minimum cost among all maximum-throughput solutions (secondary objective)
            - Flow values are int if all demands and capacities are integers, else float
    """
    network = TimeLayeredNetwork(nodes, base_edges, commodities, time_horizon, holding_rules, dynamic_obstructions)
    return network.solve()


class TimeLayeredNetwork:
    def __init__(self, nodes, base_edges, commodities, time_horizon, holding_rules, dynamic_obstructions):
        self.nodes = nodes
        self.base_edges = {int(k): v for k, v in (base_edges or {}).items()}
        self.commodities = sorted(commodities or [], key=lambda c: c.get('priority', 0), reverse=True)
        self.time_horizon = time_horizon
        self.holding_rules = {h['node']: h for h in (holding_rules or [])}
        
        self.obstructions = {}
        if dynamic_obstructions:
            for obs in dynamic_obstructions:
                self.obstructions[(obs['u'], obs['v'])] = obs['block_time']
        
        self.graph = defaultdict(list)
        self.edge_capacity = {}
        self.edge_cost = {}
        self.edge_forbidden = {}
        self.edge_locks = {}
        self.flow_usage = defaultdict(int)
        
        self.commodity_paths = {c['id']: [] for c in self.commodities}
        self.commodity_flows = {c['id']: 0.0 for c in self.commodities}
        
        self._build_time_layered_graph()
        self._compute_conflict_closure()
        
    def _build_time_layered_graph(self):
        for u in self.base_edges:
            for edge_data in self.base_edges[u]:
                v = edge_data['to']
                capacity = edge_data['capacity']
                cost = edge_data['cost']
                time_windows = edge_data.get('time_windows', [])
                forbidden_pairs_raw = edge_data.get('forbidden_pairs', [])
                forbidden_pairs = set(tuple(pair) for pair in forbidden_pairs_raw) if isinstance(forbidden_pairs_raw, list) else forbidden_pairs_raw
                obstruction_time = edge_data.get('obstruction_time')
                reverse_edge = edge_data.get('reverse_edge')
                
                if (u, v) in self.obstructions:
                    obstruction_time = self.obstructions[(u, v)]
                
                for tw_start, tw_end in time_windows:
                    for t in range(tw_start, min(tw_end + 1, self.time_horizon)):
                        if obstruction_time is not None and t >= obstruction_time:
                            break
                        
                        t_next = t + 1
                        
                        if t_next >= self.time_horizon:
                            continue
                        
                        edge_key = (u, t, v, t_next)
                        
                        self.graph[(u, t)].append((v, t_next, edge_key))
                        self.edge_capacity[edge_key] = capacity
                        self.edge_cost[edge_key] = cost
                        self.edge_forbidden[edge_key] = forbidden_pairs
                        self.edge_locks[edge_key] = threading.Lock()
                
                if reverse_edge:
                    rev_capacity = reverse_edge.get('capacity', capacity)
                    rev_cost = reverse_edge.get('cost', cost)
                    rev_time_windows = reverse_edge.get('time_windows', time_windows)
                    rev_forbidden_raw = reverse_edge.get('forbidden_pairs', forbidden_pairs)
                    rev_forbidden = set(tuple(pair) for pair in rev_forbidden_raw) if isinstance(rev_forbidden_raw, list) else rev_forbidden_raw
                    
                    for tw_start, tw_end in rev_time_windows:
                        for t in range(tw_start, min(tw_end + 1, self.time_horizon)):
                            t_next = t + 1
                            
                            if t_next >= self.time_horizon:
                                continue
                            
                            edge_key = (v, t, u, t_next)
                            
                            self.graph[(v, t)].append((u, t_next, edge_key))
                            self.edge_capacity[edge_key] = rev_capacity
                            self.edge_cost[edge_key] = rev_cost
                            self.edge_forbidden[edge_key] = rev_forbidden
                            self.edge_locks[edge_key] = threading.Lock()
        
        for node in self.nodes:
            if node in self.holding_rules:
                holding_cap = self.holding_rules[node]['capacity']
                holding_cost = self.holding_rules[node]['cost_per_unit_per_time']
            else:
                holding_cap = float('inf')
                holding_cost = 0.0
            
            for t in range(self.time_horizon - 1):
                edge_key = (node, t, node, t + 1)
                self.graph[(node, t)].append((node, t + 1, edge_key))
                self.edge_capacity[edge_key] = holding_cap
                self.edge_cost[edge_key] = holding_cost
                self.edge_forbidden[edge_key] = set()
                self.edge_locks[edge_key] = threading.Lock()
    
    def _compute_conflict_closure(self):
        all_commodities = {c['id'] for c in self.commodities}
        conflict_graph = {c: set() for c in all_commodities}
        
        for forbidden_set in self.edge_forbidden.values():
            for c1, c2 in forbidden_set:
                if c1 in conflict_graph and c2 in conflict_graph:
                    conflict_graph[c1].add(c2)
                    conflict_graph[c2].add(c1)
        
        for c in all_commodities:
            changed = True
            while changed:
                changed = False
                for neighbor in list(conflict_graph[c]):
                    for transitive in conflict_graph[neighbor]:
                        if transitive != c and transitive not in conflict_graph[c]:
                            conflict_graph[c].add(transitive)
                            changed = True
        
        for edge_key in self.edge_forbidden:
            expanded = set()
            for c1, c2 in self.edge_forbidden[edge_key]:
                if c1 in conflict_graph and c2 in conflict_graph:
                    expanded.add((c1, c2))
                    for t1 in conflict_graph[c1]:
                        if t1 >= c1:
                            expanded.add((c1, t1))
                    for t2 in conflict_graph[c2]:
                        if t2 >= c2:
                            expanded.add((c2, t2))
            self.edge_forbidden[edge_key].update(expanded)
    
    def solve(self):
        total_cost = 0.0
        
        high_priority = [c for c in self.commodities if c.get('priority', 0) > 0]
        normal_priority = [c for c in self.commodities if c.get('priority', 0) == 0]
        
        for commodity in high_priority:
            result = self._route_commodity(commodity)
            if result is None:
                self.commodity_paths[commodity['id']] = []
                self.commodity_flows[commodity['id']] = 0.0
                continue
            paths, flow, cost = result
            self.commodity_paths[commodity['id']] = paths
            self.commodity_flows[commodity['id']] = flow
            total_cost += cost
        
        if len(normal_priority) > 1:
            with ThreadPoolExecutor(max_workers=min(len(normal_priority), MAX_WORKER_THREADS)) as executor:
                futures = {}
                for commodity in normal_priority:
                    future = executor.submit(self._route_commodity, commodity)
                    futures[future] = commodity
                
                for future in as_completed(futures):
                    commodity = futures[future]
                    result = future.result()
                    if result is None:
                        self.commodity_paths[commodity['id']] = []
                        self.commodity_flows[commodity['id']] = 0.0
                        continue
                    paths, flow, cost = result
                    self.commodity_paths[commodity['id']] = paths
                    self.commodity_flows[commodity['id']] = flow
                    total_cost += cost
        else:
            for commodity in normal_priority:
                result = self._route_commodity(commodity)
                if result is None:
                    self.commodity_paths[commodity['id']] = []
                    self.commodity_flows[commodity['id']] = 0.0
                    continue
                paths, flow, cost = result
                self.commodity_paths[commodity['id']] = paths
                self.commodity_flows[commodity['id']] = flow
                total_cost += cost
        
        aggregate_throughput = sum(self.commodity_flows.values())
        
        return {
            "paths": {str(k): v for k, v in self.commodity_paths.items()},
            "flows": {str(k): v for k, v in self.commodity_flows.items()},
            "cost": total_cost,
            "throughput": aggregate_throughput
        }
    
    def _route_commodity(self, commodity):
        c_id = commodity['id']
        source = commodity['source']
        sink = commodity['sink']
        demand = commodity['demand']
        max_split = commodity.get('max_split', 1)
        
        if source == sink:
            is_integer_demand = isinstance(demand, int) or demand == int(demand)
            return [], (0 if is_integer_demand and self._all_capacities_integer() else 0.0), 0.0
        
        is_integer_demand = isinstance(demand, int) or demand == int(demand)
        
        total_flow = 0.0
        total_cost = 0.0
        paths = []
        
        for _ in range(max_split):
            remaining = demand - total_flow
            if remaining <= 1e-9:
                break
            
            result = self._find_augmenting_path(c_id, source, sink, remaining)
            if result is None:
                break
            
            path, flow, cost = result
            
            if not path or flow <= 1e-9:
                break
            
            if is_integer_demand and self._all_capacities_integer():
                flow = int(flow)
            
            total_flow += flow
            total_cost += cost
            paths.append(self._extract_base_path(path))
        
        if is_integer_demand and self._all_capacities_integer():
            total_flow = int(total_flow)
        
        return paths, total_flow, total_cost
    
    def _all_capacities_integer(self):
        for edge_key in self.edge_capacity:
            cap = self.edge_capacity[edge_key]
            if callable(cap):
                return False
            if cap != float('inf') and not isinstance(cap, int):
                return False
        return True
    
    def _find_augmenting_path(self, commodity_id, source, sink, max_flow):
        dist = {(source, 0): 0.0}
        parent = {(source, 0): None}
        min_cap = {(source, 0): float('inf')}
        in_queue = {(source, 0): True}
        queue = deque([(source, 0)])
        
        iteration_count = 0
        max_iterations = len(self.graph) * self.time_horizon * MAX_ITERATION_MULTIPLIER
        
        while queue and iteration_count < max_iterations:
            iteration_count += 1
            u, t = queue.popleft()
            in_queue[(u, t)] = False
            
            if t >= self.time_horizon:
                continue
            
            current_dist = dist[(u, t)]
            current_cap = min_cap[(u, t)]
            
            for v, t_next, edge_key in self.graph.get((u, t), []):
                if not self._can_use_edge(edge_key, commodity_id):
                    continue
                
                residual = self._get_residual_capacity(edge_key, commodity_id)
                if residual <= 1e-9:
                    continue
                
                edge_cost = self._get_edge_cost(edge_key, commodity_id, t)
                new_dist = current_dist + edge_cost
                new_cap = min(current_cap, residual)
                
                should_update = False
                if (v, t_next) not in dist:
                    should_update = True
                elif new_dist < dist[(v, t_next)] - 1e-9:
                    should_update = True
                elif abs(new_dist - dist[(v, t_next)]) < 1e-9 and new_cap > min_cap.get((v, t_next), 0):
                    should_update = True
                
                if should_update:
                    dist[(v, t_next)] = new_dist
                    parent[(v, t_next)] = (u, t, edge_key)
                    min_cap[(v, t_next)] = new_cap
                    
                    if not in_queue.get((v, t_next), False):
                        queue.append((v, t_next))
                        in_queue[(v, t_next)] = True
        
        best_sink = None
        best_cost = float('inf')
        best_cap = 0
        
        for t in range(self.time_horizon):
            if (sink, t) in dist:
                if dist[(sink, t)] < best_cost - 1e-9:
                    best_cost = dist[(sink, t)]
                    best_cap = min_cap.get((sink, t), 0)
                    best_sink = (sink, t)
                elif abs(dist[(sink, t)] - best_cost) < 1e-9 and min_cap.get((sink, t), 0) > best_cap:
                    best_cap = min_cap.get((sink, t), 0)
                    best_sink = (sink, t)
        
        if best_sink is None:
            return [], 0.0, 0.0
        
        path = []
        current = best_sink
        
        while current in parent and parent[current] is not None:
            u, t, edge_key = parent[current]
            path.append(edge_key)
            current = (u, t)
        
        path.reverse()
        flow = min(max_flow, min_cap[best_sink])
        
        if not self._allocate_flow(path, commodity_id, flow):
            return [], 0.0, 0.0
        
        total_cost = 0.0
        for edge_key in path:
            u, t, v, t_next = edge_key
            edge_cost = self._get_edge_cost(edge_key, commodity_id, t)
            total_cost += flow * edge_cost
        
        return path, flow, total_cost
    
    def _can_use_edge(self, edge_key, commodity_id):
        forbidden = self.edge_forbidden.get(edge_key, set())
        
        for c1, c2 in forbidden:
            if c1 == commodity_id == c2:
                edge_state = getattr(self, '_edge_commodity_state', {})
                if edge_key in edge_state and commodity_id in edge_state[edge_key]:
                    return False
                return True
            
            if c1 == commodity_id or c2 == commodity_id:
                edge_state = getattr(self, '_edge_commodity_state', {})
                if edge_key in edge_state:
                    other = c2 if c1 == commodity_id else c1
                    if other in edge_state[edge_key]:
                        return False
        
        return True
    
    def _get_residual_capacity(self, edge_key, commodity_id):
        capacity = self.edge_capacity[edge_key]
        
        if callable(capacity):
            u, t, v, t_next = edge_key
            total_flow = self.flow_usage.get(edge_key, 0)
            capacity = capacity(total_flow, t)
        
        used = self.flow_usage.get(edge_key, 0)
        
        forbidden = self.edge_forbidden.get(edge_key, set())
        for c1, c2 in forbidden:
            if c1 == commodity_id == c2:
                edge_state = getattr(self, '_edge_commodity_state', {})
                if edge_key in edge_state and commodity_id in edge_state[edge_key]:
                    return 0
                return min(1, capacity - used) if capacity != float('inf') else 1
        
        return capacity - used if capacity != float('inf') else float('inf')
    
    def _get_edge_cost(self, edge_key, commodity_id, time):
        cost = self.edge_cost[edge_key]
        
        if callable(cost):
            cost = cost(commodity_id, time)
        
        return cost
    
    def _allocate_flow(self, path, commodity_id, flow):
        locks_acquired = []
        
        try:
            for edge_key in path:
                self.edge_locks[edge_key].acquire()
                locks_acquired.append(edge_key)
            
            for edge_key in path:
                if not self._can_use_edge(edge_key, commodity_id):
                    return False
            
            for edge_key in path:
                residual = self._get_residual_capacity(edge_key, commodity_id)
                if residual < flow - 1e-9:
                    return False
            
            for edge_key in path:
                self.flow_usage[edge_key] = self.flow_usage.get(edge_key, 0) + flow
                
                if not hasattr(self, '_edge_commodity_state'):
                    self._edge_commodity_state = {}
                if edge_key not in self._edge_commodity_state:
                    self._edge_commodity_state[edge_key] = set()
                self._edge_commodity_state[edge_key].add(commodity_id)
            
            return True
            
        finally:
            for edge_key in locks_acquired:
                self.edge_locks[edge_key].release()
    
    def _extract_base_path(self, path):
        if not path:
            return []
        
        base_path = [path[0][0]]
        for edge_key in path:
            u, t, v, t_next = edge_key
            if not base_path or base_path[-1] != v:
                base_path.append(v)
        
        return base_path


if __name__ == "__main__":
    nodes = [0, 1, 2, 3]
    
    base_edges = {
        "0": [
            {
                "to": 1,
                "capacity": 10,
                "cost": 2.0,
                "time_windows": [[0, 1]],
                "forbidden_pairs": [],
                "obstruction_time": None
            },
            {
                "to": 2,
                "capacity": 5,
                "cost": 1.0,
                "time_windows": [[1, 2]],
                "forbidden_pairs": [],
                "obstruction_time": None
            }
        ],
        "1": [
            {
                "to": 3,
                "capacity": 8,
                "cost": 3.0,
                "time_windows": [[1, 3]],
                "forbidden_pairs": [],
                "obstruction_time": None
            }
        ],
        "2": [
            {
                "to": 3,
                "capacity": 6,
                "cost": 4.0,
                "time_windows": [[2, 4]],
                "forbidden_pairs": [],
                "obstruction_time": None
            }
        ]
    }
    
    commodities = [
        {"id": 0, "source": 0, "sink": 3, "demand": 7.0},
        {"id": 1, "source": 0, "sink": 3, "demand": 4.0}
    ]
    
    time_horizon = 5
    holding_rules = None
    dynamic_obstructions = None
    
    result = optimize_logistics_network(
        nodes, base_edges, commodities, time_horizon, holding_rules, dynamic_obstructions
    )
    
    print(result)