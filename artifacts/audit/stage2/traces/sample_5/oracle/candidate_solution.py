import copy
from collections import defaultdict, deque
import threading
import time
from decimal import Decimal, getcontext

def optimize_order_flow_graph(nodes: int, edges: list, trades: list) -> dict:
    
    getcontext().prec = 28
    
    if nodes <= 0:
        return {
            "total_flow": 0,
            "total_cost": 0,
            "flow_distribution": {},
            "partial_fills": []
        }
    
    if not edges or not trades:
        return {
            "total_flow": 0,
            "total_cost": 0,
            "flow_distribution": {},
            "partial_fills": []
        }
    
    class GraphState:
        def __init__(self):
            self.adjacency = defaultdict(list)
            self.capacities = {}
            self.costs = {}
            self.lock = threading.RLock()
            self.version = 0
            self.pending_updates = deque()
            self.update_log = []
        
        def add_edge(self, u, v, capacity, cost):
            with self.lock:
                if v not in self.adjacency[u]:
                    self.adjacency[u].append(v)
                
                edge_key = (u, v)
                self.capacities[edge_key] = Decimal(str(capacity))
                self.costs[edge_key] = Decimal(str(cost))
                
                reverse_key = (v, u)
                if reverse_key not in self.capacities:
                    self.capacities[reverse_key] = Decimal('0')
                    self.costs[reverse_key] = -Decimal(str(cost))
                    if u not in self.adjacency[v]:
                        self.adjacency[v].append(u)
                
                self.version += 1
        
        def remove_edge(self, u, v):
            with self.lock:
                edge_key = (u, v)
                if edge_key in self.capacities:
                    self.capacities[edge_key] = Decimal('0')
                    self.version += 1
        
        def update_cost(self, u, v, new_cost):
            with self.lock:
                edge_key = (u, v)
                if edge_key in self.costs:
                    self.costs[edge_key] = Decimal(str(new_cost))
                    reverse_key = (v, u)
                    if reverse_key in self.costs:
                        self.costs[reverse_key] = -Decimal(str(new_cost))
                    self.version += 1
        
        def apply_pending_updates(self):
            with self.lock:
                while self.pending_updates:
                    update = self.pending_updates.popleft()
                    update_type = update.get('type')
                    
                    if update_type == 'add_edge':
                        self.add_edge(update['u'], update['v'], update['capacity'], update['cost'])
                    elif update_type == 'remove_edge':
                        self.remove_edge(update['u'], update['v'])
                    elif update_type == 'update_cost':
                        self.update_cost(update['u'], update['v'], update['cost'])
                    
                    self.update_log.append(update)
        
        def snapshot(self):
            with self.lock:
                snapshot_state = GraphState()
                snapshot_state.adjacency = copy.deepcopy(self.adjacency)
                snapshot_state.capacities = copy.deepcopy(self.capacities)
                snapshot_state.costs = copy.deepcopy(self.costs)
                snapshot_state.version = self.version
                return snapshot_state
    
    baseline_graph = GraphState()
    
    for edge_data in edges:
        if not isinstance(edge_data, (list, tuple)) or len(edge_data) != 4:
            continue
        
        try:
            u, v, capacity, cost = edge_data
            u, v = int(u), int(v)
            capacity = float(capacity)
            cost = float(cost)
        except (ValueError, TypeError):
            continue
        
        if u == v or capacity <= 0:
            continue
        if u < 0 or v < 0 or u >= nodes or v >= nodes:
            continue
        
        baseline_graph.add_edge(u, v, capacity, cost)
    
    original_snapshot = baseline_graph.snapshot()
    
    working_graph = baseline_graph.snapshot()
    
    accumulated_flow = Decimal('0')
    accumulated_cost = Decimal('0')
    global_flow_distribution = defaultdict(lambda: Decimal('0'))
    partial_fill_records = []
    
    epsilon = Decimal('1e-9')
    
    class FlowComputation:
        def __init__(self, graph_state, source, target, demand):
            self.graph = graph_state
            self.source = source
            self.target = target
            self.demand = Decimal(str(demand))
            self.flow_achieved = Decimal('0')
            self.cost_incurred = Decimal('0')
            self.flow_map = defaultdict(lambda: Decimal('0'))
            self.computation_snapshot = None
        
        def find_shortest_path_spfa(self):
            distances = [Decimal('inf')] * nodes
            predecessors = [-1] * nodes
            in_queue = [False] * nodes
            relaxation_count = [0] * nodes
            
            distances[self.source] = Decimal('0')
            queue = deque([self.source])
            in_queue[self.source] = True
            
            max_relaxations = nodes
            iterations = 0
            max_iterations = nodes * 20
            
            while queue and iterations < max_iterations:
                iterations += 1
                current = queue.popleft()
                in_queue[current] = False
                
                if current not in self.graph.adjacency:
                    continue
                
                for neighbor in self.graph.adjacency[current]:
                    edge_key = (current, neighbor)
                    
                    with self.graph.lock:
                        capacity = self.graph.capacities.get(edge_key, Decimal('0'))
                        cost = self.graph.costs.get(edge_key, Decimal('0'))
                    
                    if capacity > epsilon:
                        new_distance = distances[current] + cost
                        
                        if new_distance < distances[neighbor]:
                            distances[neighbor] = new_distance
                            predecessors[neighbor] = current
                            
                            relaxation_count[neighbor] += 1
                            if relaxation_count[neighbor] > max_relaxations:
                                return None
                            
                            if not in_queue[neighbor]:
                                if queue and distances[neighbor] < distances[queue[0]]:
                                    queue.appendleft(neighbor)
                                else:
                                    queue.append(neighbor)
                                in_queue[neighbor] = True
            
            if distances[self.target] == Decimal('inf'):
                return None
            
            path = []
            current = self.target
            visited = set()
            
            while current != -1:
                if current in visited:
                    return None
                visited.add(current)
                path.append(current)
                current = predecessors[current]
            
            path.reverse()
            
            if len(path) < 2 or path[0] != self.source or path[-1] != self.target:
                return None
            
            return path
        
        def compute_flow(self):
            self.computation_snapshot = self.graph.snapshot()
            
            max_iterations = min(nodes * nodes, 5000)
            iteration = 0
            
            while self.flow_achieved < self.demand - epsilon and iteration < max_iterations:
                iteration += 1
                
                if iteration % 100 == 0:
                    self.graph.apply_pending_updates()
                
                path = self.find_shortest_path_spfa()
                
                if path is None:
                    break
                
                bottleneck = Decimal('inf')
                for i in range(len(path) - 1):
                    u_node, v_node = path[i], path[i + 1]
                    edge_key = (u_node, v_node)
                    
                    with self.graph.lock:
                        capacity = self.graph.capacities.get(edge_key, Decimal('0'))
                    
                    bottleneck = min(bottleneck, capacity)
                
                flow_push = min(bottleneck, self.demand - self.flow_achieved)
                
                if flow_push <= epsilon:
                    break
                
                with self.graph.lock:
                    for i in range(len(path) - 1):
                        u_node, v_node = path[i], path[i + 1]
                        
                        forward_key = (u_node, v_node)
                        reverse_key = (v_node, u_node)
                        
                        self.graph.capacities[forward_key] -= flow_push
                        self.graph.capacities[reverse_key] = self.graph.capacities.get(reverse_key, Decimal('0')) + flow_push
                        
                        self.flow_map[forward_key] += flow_push
                        
                        edge_cost = self.graph.costs.get(forward_key, Decimal('0'))
                        self.cost_incurred += flow_push * edge_cost
                
                self.flow_achieved += flow_push
            
            return self.flow_achieved, self.cost_incurred, self.flow_map
    
    trade_snapshots = []
    
    for trade_idx, trade_request in enumerate(trades):
        if not isinstance(trade_request, dict):
            continue
        
        try:
            volume = float(trade_request.get("volume", 0))
            source = int(trade_request.get("source", -1))
            target = int(trade_request.get("target", -1))
        except (ValueError, TypeError):
            continue
        
        if volume <= 0:
            continue
        if source < 0 or target < 0 or source >= nodes or target >= nodes:
            continue
        if source == target:
            continue
        
        pre_trade_snapshot = working_graph.snapshot()
        trade_snapshots.append({
            'trade_index': trade_idx,
            'snapshot': pre_trade_snapshot,
            'timestamp': time.time()
        })
        
        flow_computer = FlowComputation(working_graph, source, target, volume)
        
        trade_flow, trade_cost, trade_flow_map = flow_computer.compute_flow()
        
        with working_graph.lock:
            accumulated_flow += trade_flow
            accumulated_cost += trade_cost
            
            for edge_key, flow_value in trade_flow_map.items():
                if flow_value > epsilon:
                    global_flow_distribution[edge_key] += flow_value
        
        if trade_flow < Decimal(str(volume)) - epsilon:
            partial_fill_records.append({
                "volume_unfilled": float(Decimal(str(volume)) - trade_flow),
                "source": source,
                "target": target
            })
        
        if trade_idx < len(trades) - 1:
            working_graph.apply_pending_updates()
    
    final_snapshot = working_graph.snapshot()
    
    final_flow_distribution = {}
    for edge_key, flow_value in global_flow_distribution.items():
        if flow_value > epsilon:
            with original_snapshot.lock:
                if edge_key in original_snapshot.capacities and original_snapshot.capacities[edge_key] > Decimal('0'):
                    edge_str = f"[{edge_key[0]},{edge_key[1]}]"
                    final_flow_distribution[edge_str] = float(flow_value)
    
    
    return {
        "total_flow": float(accumulated_flow),
        "total_cost": float(accumulated_cost),
        "flow_distribution": final_flow_distribution,
        "partial_fills": partial_fill_records
    }
    

if __name__ == "__main__":
    
    nodes = 6  
    edges = [  
      [0, 1, 10, 2],  
      [1, 2, 5, 1],  
      [2, 3, 10, 3],  
      [0, 4, 4, 2],  
      [4, 5, 6, 4],  
      [1, 5, 3, 6],  
      [2, 4, 2, 10]  
    ]  
    trades = [  
      {"volume": 8, "source": 0, "target": 3},  
      {"volume": 5, "source": 0, "target": 5}  
    ]
    
    result = optimize_order_flow_graph(nodes, edges, trades)
    print(result)