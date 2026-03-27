def process_network_operations(n: int, operations: list[list[str]]) -> list[int]:
    class NetworkState:
        def __init__(self):
            self.edges = {}  # (u, v) -> (cost, priority)
            self.valid = True
            self.adj = {}  # u -> set of edges incident to u
        
        def copy(self):
            new_state = NetworkState()
            new_state.edges = self.edges.copy()
            new_state.valid = self.valid
            new_state.adj = {u: edges.copy() for u, edges in self.adj.items()}
            return new_state
        
        def add_edge(self, edge, cost, priority):
            u, v = edge
            self.edges[edge] = (cost, priority)
            if u not in self.adj:
                self.adj[u] = set()
            if v not in self.adj:
                self.adj[v] = set()
            self.adj[u].add(edge)
            self.adj[v].add(edge)
        
        def remove_edge(self, edge):
            if edge in self.edges:
                del self.edges[edge]
                u, v = edge
                if u in self.adj:
                    self.adj[u].discard(edge)
                    if not self.adj[u]:
                        del self.adj[u]
                if v in self.adj:
                    self.adj[v].discard(edge)
                    if not self.adj[v]:
                        del self.adj[v]
    
    def normalize_edge(u, v):
        return (min(u, v), max(u, v))
    
    def find_min_edge_dominating_set(state):
        if not state.valid:
            return -1
        
        if not state.edges:
            return 0
        
        edges = list(state.edges.keys())
        priority_edges = [e for e in edges if state.edges[e][1] == 1]
        
        # All priority edges must be in the solution
        selected = set(priority_edges)
        total_cost = sum(state.edges[e][0] for e in priority_edges)
        
        # Use adjacency to efficiently find dominated edges
        dominated = set(selected)
        for e in selected:
            u, v = e
            if u in state.adj:
                dominated.update(state.adj[u])
            if v in state.adj:
                dominated.update(state.adj[v])
        
        if dominated == set(edges):
            return total_cost
        
        remaining_edges = [e for e in edges if e not in selected]
        
        if len(edges) <= 20:
            # Exact solution via brute force
            min_additional_cost = float('inf')
            
            for mask in range(1 << len(remaining_edges)):
                additional = set()
                additional_cost = 0
                
                for i in range(len(remaining_edges)):
                    if mask & (1 << i):
                        additional.add(remaining_edges[i])
                        additional_cost += state.edges[remaining_edges[i]][0]
                
                current_selected = selected | additional
                all_dominated = set(current_selected)
                
                for e in current_selected:
                    u, v = e
                    if u in state.adj:
                        all_dominated.update(state.adj[u])
                    if v in state.adj:
                        all_dominated.update(state.adj[v])
                
                if all_dominated == set(edges):
                    min_additional_cost = min(min_additional_cost, additional_cost)
            
            if min_additional_cost == float('inf'):
                return -1
            
            return total_cost + min_additional_cost
        else:
            # Greedy approach for larger graphs
            current_dominated = dominated.copy()
            current_selected = selected.copy()
            additional_cost = 0
            
            while len(current_dominated) < len(edges):
                best_edge = None
                best_ratio = float('inf')
                
                for e in edges:
                    if e in current_selected:
                        continue
                    
                    # Count newly dominated edges using set operations
                    u, v = e
                    u_neighbors = state.adj.get(u, set())
                    v_neighbors = state.adj.get(v, set())
                    
                    newly = set()
                    if e not in current_dominated:
                        newly.add(e)
                    newly |= (u_neighbors - current_dominated)
                    newly |= (v_neighbors - current_dominated)
                    
                    new_dominated_count = len(newly)
                    
                    if new_dominated_count > 0:
                        ratio = state.edges[e][0] / new_dominated_count
                        if ratio < best_ratio:
                            best_ratio = ratio
                            best_edge = e
                
                if best_edge is None:
                    return -1
                
                current_selected.add(best_edge)
                additional_cost += state.edges[best_edge][0]
                
                # Update dominated set using adjacency
                u, v = best_edge
                current_dominated.add(best_edge)
                if u in state.adj:
                    current_dominated.update(state.adj[u])
                if v in state.adj:
                    current_dominated.update(state.adj[v])
            
            return total_cost + additional_cost
    
    history = []
    current_state = NetworkState()
    results = []
    
    for op in operations:
        if op[0] == "ADD":
            u, v = int(op[1]), int(op[2])
            cost = int(op[3])
            priority = int(op[4])
            
            if u == v:
                current_state.valid = False
            else:
                edge = normalize_edge(u, v)
                # Remove old edge if exists to update adjacency
                if edge in current_state.edges:
                    current_state.remove_edge(edge)
                current_state.add_edge(edge, cost, priority)
                current_state.valid = True
            
            history.append(current_state.copy())
        
        elif op[0] == "REMOVE":
            u, v = int(op[1]), int(op[2])
            edge = normalize_edge(u, v)
            
            if edge in current_state.edges:
                current_state.remove_edge(edge)
                current_state.valid = True
            else:
                current_state.valid = False
            
            history.append(current_state.copy())
        
        elif op[0] == "QUERY":
            results.append(find_min_edge_dominating_set(current_state))
            history.append(current_state.copy())
        
        elif op[0] == "ROLLBACK":
            k = int(op[1])
            if k > len(history) or k < 1:
                current_state = NetworkState()
                current_state.valid = False
            else:
                current_state = history[k - 1].copy()
            
            history.append(current_state.copy())
    
    return results