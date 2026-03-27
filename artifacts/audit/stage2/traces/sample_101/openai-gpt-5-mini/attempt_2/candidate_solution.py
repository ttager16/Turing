def __init__(self, city_graph: Dict, capacity_map: Dict, demand_map: Dict):
        # Normalize city_graph keys and neighbor lists to integers
        self.city_graph = {}
        if not city_graph:
            self.city_graph = {}
        else:
            # detect key type by inspecting first key
            first_key = next(iter(city_graph))
            for k, nbrs in city_graph.items():
                ki = int(k) if not isinstance(k, int) else k
                self.city_graph[ki] = [int(n) for n in nbrs]
        # Sorted nodes
        self.nodes = sorted(self.city_graph.keys())
        # Normalize capacity_map: parse "u,v" strings; each undirected edge appears once
        self.capacity_map = {}
        for k, v in (capacity_map or {}).items():
            # k might be like "u,v" or already tuple
            if isinstance(k, str):
                parts = k.split(",")
                if len(parts) == 2:
                    u = int(parts[0].strip())
                    v = int(parts[1].strip())
                else:
                    continue
            elif isinstance(k, tuple) and len(k) == 2:
                u, v = int(k[0]), int(k[1])
            else:
                continue
            cap = int(v) if isinstance(v, str) and v.isdigit() else int(v)
            # store canonical key as tuple (min,max) for undirected reference but keep original directional entries for quick lookup
            key = (u, v)
            self.capacity_map[key] = cap
        # Normalize demand_map: keys may be strings
        self.demand_map = {}
        for k, v in (demand_map or {}).items():
            ki = int(k) if not isinstance(k, int) else k
            self.demand_map[ki] = int(v)
        # Ensure default zeros for missing nodes when accessed via get
    def num_nodes(self) -> int:
        return len(self.nodes)
    def num_edges(self) -> int:
        # number of unique undirected edges is size of input capacity_map
        return len(self.capacity_map)

class CapacityAwarePathfinder:
    def __init__(self, graph: CapacityConstrainedGraph):
        self.graph = graph
        # Build normalized residual capacity map that supports bidirectional access
    def shortest_distances_ignoring_capacity(self, source: int) -> Dict[int, int]:
        dist = {}
        q = deque()
        q.append(source)
        dist[source] = 0
        while q:
            u = q.popleft()
            for v in self.graph.city_graph.get(u, []):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
        return dist
    def capacity_aware_path(self, source: int, target: int, demand: int, residual: Dict[Tuple[int,int], int]) -> Optional[List[int]]:
        if source == target:
            return [source]
        q = deque()
        q.append((source, [source]))
        visited = set([source])
        while q:
            node, path = q.popleft()
            for nbr in self.graph.city_graph.get(node, []):
                if nbr in visited:
                    continue
                cap = residual.get((node, nbr), 0)
                if cap >= demand:
                    if nbr == target:
                        return path + [nbr]
                    visited.add(nbr)
                    q.append((nbr, path + [nbr]))
        return None
    def compute_weighted_distance(self, hub: int) -> Optional[int]:
        # BFS ignoring capacity for distances
        dist = self.shortest_distances_ignoring_capacity(hub)
        total = 0
        for n in self.graph.nodes:
            if n == hub:
                continue
            d = dist.get(n)
            if d is None:
                return None
            demand = self.graph.demand_map.get(n, 0)
            total += d * demand
        return total
    def is_capacity_feasible(self, hub: int) -> bool:
        # Make mutable residual capacities with bidirectional entries.
        residual = {}
        # Initialize residual capacities: for any edge in input capacity_map which is stored as (u,v) with direction as input,
        # we need to populate both (u,v) and (v,u) with same capacity.
        for (u, v), cap in self.graph.capacity_map.items():
            residual[(u, v)] = cap
            residual[(v, u)] = cap
        # Process nodes in sorted order, excluding hub
        for n in self.graph.nodes:
            if n == hub:
                continue
            demand = self.graph.demand_map.get(n, 0)
            if demand == 0:
                continue
            # find a single path from hub to n that has residual >= demand on every edge
            path = self.capacity_aware_path(hub, n, demand, residual)
            if path is None:
                return False
            # decrement capacities along path in both directions
            for i in range(len(path)-1):
                a = path[i]; b = path[i+1]
                # decrement forward and reverse
                residual[(a,b)] = residual.get((a,b), 0) - demand
                residual[(b,a)] = residual.get((b,a), 0) - demand
                # allow negatives? specification says reject if exceed, but we check before using path that each edge >= demand,
                # so after decrement they won't go below zero beyond this step.
        return True

class GraphMedianFinder:
    def __init__(self, graph: CapacityConstrainedGraph):
        self.graph = graph
        self.pathfinder = CapacityAwarePathfinder(graph)
    def evaluate_hub(self, hub: int) -> Tuple[Optional[int], bool]:
        # compute distances ignoring capacity
        dist = self.pathfinder.shortest_distances_ignoring_capacity(hub)
        # connectivity
        connected = len(dist) == len(self.graph.nodes)
        # compute weighted distance; if any unreachable, returns None
        total = self.pathfinder.compute_weighted_distance(hub)
        return total, connected
    def find_optimal_hub(self) -> Dict:
        nodes = self.graph.nodes
        result = {
            "optimal_hub": 0 if not nodes else nodes[0],
            "total_weighted_distance": None,
            "feasible_hubs": [],
            "graph_connected": False,
            "num_nodes": self.graph.num_nodes(),
            "num_edges": self.graph.num_edges()
        }
        if not nodes:
            return result
        feasible_list = []
        best_cost = math.inf
        best_hub = None
        best_connected = False
        # First, test every node for capacity feasibility and compute cost/connectivity
        for n in nodes:
            feasible = self.pathfinder.is_capacity_feasible(n)
            if feasible:
                feasible_list.append(n)
            # even if not feasible, we need to know reachability/cost for selection? constraints say skip candidates that fail capacity feasibility
        # Evaluate feasible candidates for cost and connectivity
        for n in feasible_list:
            cost, connected = self.evaluate_hub(n)
            if cost is None:
                continue
            if cost < best_cost:
                best_cost = cost
                best_hub = n
                best_connected = connected
        # Fallback behavior
        if best_hub is None:
            fallback = nodes[0] if nodes else 0
            total, connected = self.evaluate_hub(fallback)
            result["optimal_hub"] = fallback
            result["total_weighted_distance"] = int(total) if total is not None else None
            result["feasible_hubs"] = feasible_list
            result["graph_connected"] = connected
            result["num_nodes"] = self.graph.num_nodes()
            result["num_edges"] = self.graph.num_edges()
            return result
        else:
            result["optimal_hub"] = best_hub
            result["total_weighted_distance"] = int(best_cost)
            result["feasible_hubs"] = feasible_list
            result["graph_connected"] = best_connected
            result["num_nodes"] = self.graph.num_nodes()
            result["num_edges"] = self.graph.num_edges()
            return result

def solve_transportation_hub_problem(input_data: Dict) -> Dict:
    # Input validation
    if not isinstance(input_data, dict):
        return {"error": "Invalid input format"}
    city_graph = input_data.get("city_graph")
    capacity_map = input_data.get("capacity_map")
    demand_map = input_data.get("demand_map")
    if not isinstance(city_graph, dict):
        return {"error": "Invalid city_graph"}
    if not isinstance(capacity_map, dict):
        return {"error": "Invalid capacity_map"}
    if not isinstance(demand_map, dict):
        return {"error": "Invalid demand_map"}
    graph = CapacityConstrainedGraph(city_graph, capacity_map, demand_map)
    finder = GraphMedianFinder(graph)
    return finder.find_optimal_hub()