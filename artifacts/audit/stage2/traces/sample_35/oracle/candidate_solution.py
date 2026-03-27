import heapq
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set

class SegmentTree:
    def __init__(self, arr: List[int]):
        # Find next power of 2
        n = 1
        while n < len(arr):
            n <<= 1
        self.n = n
        self.seg = [float('inf')] * (2 * n)
        
        # Initialize leaves
        for i, v in enumerate(arr):
            self.seg[self.n + i] = v
            
        # Build tree bottom-up
        for i in range(self.n - 1, 0, -1):
            self.seg[i] = min(self.seg[2 * i], self.seg[2 * i + 1])

    def point_update(self, idx: int, val: float) -> None:
        i = self.n + idx
        self.seg[i] = val
        i //= 2
        while i:
            self.seg[i] = min(self.seg[2 * i], self.seg[2 * i + 1])
            i //= 2

    def point_query(self, idx: int) -> float:
        return self.seg[self.n + idx]

# Constants
DEPOT_NODE = 0
DEPOT_HANDLING_COST = 1  # one-time cost when a vehicle first leaves depot

def compute_throughput_cost(capacity: int) -> int:
    if capacity >= 3:
        return 1
    return 2


class VehicleState:
    def __init__(
        self,
        vehicle_id: int,
        max_capacity: int = 100,
        max_fuel: int = 1000,
        max_operating_time: int = 480,
        speed: float = 1.0,
        fuel_efficiency: float = 1.0,
    ) -> None:
        self.vehicle_id = vehicle_id
        self.max_capacity = max_capacity
        self.current_capacity = 0
        self.max_fuel = max_fuel
        self.current_fuel = max_fuel
        self.fuel_efficiency = fuel_efficiency
        self.max_operating_time = max_operating_time
        self.current_time = 0
        self.speed = speed
        self.location = 0
        self.route = [0]  # Start at depot
        self.cargo = defaultdict(int)  # item_type -> quantity
        self.left_depot = False
        
    def can_add_load(self, load: int) -> bool:
        return self.current_capacity + load <= self.max_capacity
    
    def can_travel(self, distance: float) -> bool:
        fuel_needed = distance * self.fuel_efficiency
        return self.current_fuel >= fuel_needed

    def apply_travel(self, distance: float) -> None:
        # Update fuel and time
        self.current_fuel -= distance * self.fuel_efficiency
        # Avoid division by zero
        if self.speed > 0:
            self.current_time += distance / self.speed
        else:
            self.current_time += distance  # fallback - probably not realistic

    def apply_wait(self, minutes: float) -> None:
        if minutes > 0:
            self.current_time += minutes


class CrossDockState:
    def __init__(self, node_id: int, capacity: int) -> None:
        self.node_id = node_id
        self.capacity = capacity
        self.usage = 0
        self.inventory = defaultdict(int)
        
    def can_accept(self) -> bool:
        return self.usage < self.capacity


def dijkstra(
    graph: Dict[int, List[Tuple[int, float]]],
    start: int,
    end: int,
    blocked_edges: Optional[Set[Tuple[int, int]]] = None,
) -> Tuple[List[int], float]:
    """
    Standard Dijkstra implementation for shortest path
    Returns (path, distance) or ([], inf) if no path exists
    """
    if blocked_edges is None:
        blocked_edges = set()
    
    distances = defaultdict(lambda: float('inf'))
    distances[start] = 0
    previous = {}
    pq = [(0, start)]
    visited = set()
    
    while pq:
        current_dist, current = heapq.heappop(pq)
        
        if current in visited:
            continue
        visited.add(current)
        
        if current == end:
            break
        
        if current not in graph:
            continue
            
        for neighbor, cost in graph[current]:
            if (current, neighbor) in blocked_edges:
                continue
            
            distance = current_dist + cost
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = current
                heapq.heappush(pq, (distance, neighbor))
    
    # Reconstruct path
    if end not in previous and end != start:
        return [], float('inf')
    
    path = []
    current = end
    while current in previous:
        path.append(current)
        current = previous[current]
    path.append(start)
    path.reverse()
    
    return path, distances[end]


def dijkstra_avoid_nodes(
    graph: Dict[int, List[Tuple[int, float]]],
    start: int,
    end: int,
    blocked_edges: Optional[Set[Tuple[int, int]]] = None,
    forbidden_nodes: Optional[Set[int]] = None,
) -> Tuple[List[int], float]:
    """
    Dijkstra that avoids entering any node in forbidden_nodes on the path forward,
    except it allows reaching the end even if end is in forbidden_nodes.
    """
    if blocked_edges is None:
        blocked_edges = set()
    if forbidden_nodes is None:
        forbidden_nodes = set()

    distances = defaultdict(lambda: float('inf'))
    distances[start] = 0
    previous = {}
    pq = [(0, start)]
    visited = set()

    while pq:
        current_dist, current = heapq.heappop(pq)
        if current in visited:
            continue
        visited.add(current)
        if current == end:
            break
        if current not in graph:
            continue

        for neighbor, cost in graph[current]:
            if (current, neighbor) in blocked_edges:
                continue
            # Skip forbidden forward nodes, but allow the end node
            if neighbor != end and neighbor in forbidden_nodes:
                continue
            distance = current_dist + cost
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = current
                heapq.heappush(pq, (distance, neighbor))

    if end not in previous and end != start:
        return [], float('inf')

    path = []
    current = end
    while current in previous:
        path.append(current)
        current = previous[current]
    path.append(start)
    path.reverse()
    return path, distances[end]


def build_graph_with_segment_tree(
    edges: List[Tuple[int, int, int]],
    traffic_updates: List[Tuple[int, int, int]],
) -> Tuple[Dict[int, List[Tuple[int, float]]], Dict[Tuple[int, int], float]]:
    """
    Build graph with dynamic edge costs using segment tree
    """
    # Map edges to indices for segment tree
    idx_map = {}
    base_costs = []
    for i, (u, v, c) in enumerate(edges):
        idx_map[(u, v)] = i
        base_costs.append(c)
    
    st = SegmentTree(base_costs)
    
    # Apply traffic updates
    for u, v, new_c in traffic_updates:
        if (u, v) in idx_map:
            st.point_update(idx_map[(u, v)], new_c)

    # Get final edge costs
    edge_costs = {}
    for (u, v), i in idx_map.items():
        edge_costs[(u, v)] = st.point_query(i)

    # Build adjacency list
    graph = defaultdict(list)
    for (u, v), c in edge_costs.items():
        graph[u].append((v, c))
    
    return graph, edge_costs


def compute_augmented_path_cost(
    v_state: VehicleState,
    path: List[int],
    edge_costs: Dict[Tuple[int, int], float],
    cross_dock_states: Dict[int, CrossDockState],
) -> Tuple[float, float]:
    """
    Calculate total cost including distance, depot handling, and cross-dock fees
    """
    if not path or len(path) == 1:
        return 0.0, 0.0
    
    total_distance = 0.0
    augmented_cost = 0.0
    
    # One-time depot handling cost
    if not v_state.left_depot and v_state.location == DEPOT_NODE and path[0] == DEPOT_NODE:
        augmented_cost += DEPOT_HANDLING_COST
    
    for i in range(len(path) - 1):
        u, w = path[i], path[i + 1]
        dist = edge_costs.get((u, w), 0)
        total_distance += dist
        
        # Add cross-dock throughput cost
        if w in cross_dock_states:
            augmented_cost += compute_throughput_cost(cross_dock_states[w].capacity)
    
    augmented_cost += total_distance
    return augmented_cost, total_distance


def calculate_item_priority(item_demands: Dict[str, List[int]], node: str) -> int:
    """priority based on total demand"""
    if node not in item_demands:
        return 0
    # Higher demand = higher priority
    return sum(item_demands[node])


def get_blocked_edges(
    edge_costs: Dict[Tuple[int, int], float],
    threshold: int = 500,
) -> Set[Tuple[int, int]]:
    """Mark expensive edges as blocked"""
    blocked = set()
    for edge, cost in edge_costs.items():
        if cost >= threshold:
            blocked.add(edge)
    return blocked


def _path_all_cross_docks_feasible(
    path: List[int],
    cross_dock_states: Dict[int, CrossDockState],
) -> bool:
    """Check if all cross-docks in path can accept vehicles"""
    if not path:
        return False
    for node in path[1:]:  # skip starting node
        if node in cross_dock_states and not cross_dock_states[node].can_accept():
            return False
    return True


def _compute_candidate_path_and_cost(
    v_state: VehicleState,
    dest: int,
    graph: Dict[int, List[Tuple[int, float]]],
    blocked_edges: Set[Tuple[int, int]],
    cross_dock_states: Dict[int, CrossDockState],
    edge_costs: Dict[Tuple[int, int], float],
    upper_bound: float = float('inf'),
) -> Tuple[List[int], float]:
    def count_cross_dock_entries(path: List[int]) -> float:
        if not path:
            return float('inf')
        count = 0
        for node in path[1:]:
            if node in cross_dock_states:
                count += 1
        return float(count)

    best_path = []
    best_cost = float('inf')
    best_cd_entries = float('inf')

    # Try direct path first (no forward cross-dock entries)
    direct_path, direct_dist = dijkstra_avoid_nodes(
        graph,
        v_state.location,
        dest,
        blocked_edges,
        set(cross_dock_states.keys())
    )
    if direct_path and direct_dist < upper_bound:
        if _path_all_cross_docks_feasible(direct_path, cross_dock_states):
            aug_cost, distance = compute_augmented_path_cost(
                v_state, direct_path, edge_costs, cross_dock_states
            )
            if distance < float('inf') and v_state.can_travel(distance):
                cand_cd = count_cross_dock_entries(direct_path)
                if aug_cost < best_cost or (aug_cost == best_cost and cand_cd < best_cd_entries):
                    best_path, best_cost, best_cd_entries = direct_path, aug_cost, cand_cd

    # Use the best known cost as an upper bound for pruning further searches
    pruning_upper = min(best_cost, upper_bound)

    # Try paths through single cross-dock
    for cd_id, cd_state in cross_dock_states.items():
        if not cd_state.can_accept():
            continue
        
        p1, d1 = dijkstra(graph, v_state.location, cd_id, blocked_edges)
        if not p1 or d1 >= pruning_upper:
            continue
        
        p2, d2 = dijkstra(graph, cd_id, dest, blocked_edges)
        if not p2 or d1 + d2 >= pruning_upper:
            continue
        
        combined = p1[:-1] + p2
        if not _path_all_cross_docks_feasible(combined, cross_dock_states):
            continue
        
        aug_cost, distance = compute_augmented_path_cost(
            v_state, combined, edge_costs, cross_dock_states
        )
        if v_state.can_travel(distance):
            cand_cd = count_cross_dock_entries(combined)
            if aug_cost < best_cost or (aug_cost == best_cost and cand_cd < best_cd_entries):
                best_path, best_cost, best_cd_entries = combined, aug_cost, cand_cd
                pruning_upper = min(pruning_upper, best_cost)

    # Try paths through two cross-docks as last resort
    if len(cross_dock_states) >= 2:
        cds_sorted = sorted(cross_dock_states.keys())
        for cd1 in cds_sorted:
            if not cross_dock_states[cd1].can_accept():
                continue
                
            p1, d1 = dijkstra(graph, v_state.location, cd1, blocked_edges)
            if not p1 or d1 >= pruning_upper:
                continue
                
            for cd2 in cds_sorted:
                if cd2 == cd1 or not cross_dock_states[cd2].can_accept():
                    continue
                    
                p2, d2 = dijkstra(graph, cd1, cd2, blocked_edges)
                if not p2 or d1 + d2 >= pruning_upper:
                    continue
                    
                p3, d3 = dijkstra(graph, cd2, dest, blocked_edges)
                if not p3 or d1 + d2 + d3 >= pruning_upper:
                    continue
                    
                combined = p1[:-1] + p2[:-1] + p3
                if not _path_all_cross_docks_feasible(combined, cross_dock_states):
                    continue
                    
                aug_cost, distance = compute_augmented_path_cost(
                    v_state, combined, edge_costs, cross_dock_states
                )
                if v_state.can_travel(distance):
                    cand_cd = count_cross_dock_entries(combined)
                    if aug_cost < best_cost or (aug_cost == best_cost and cand_cd < best_cd_entries):
                        best_path, best_cost, best_cd_entries = combined, aug_cost, cand_cd
                        pruning_upper = min(pruning_upper, best_cost)

    return best_path, best_cost


def min_cost_flow_assign(
    vehicle_states: List[VehicleState],
    sorted_destinations: List[int],
    graph: Dict[int, List[Tuple[int, float]]],
    blocked_edges: Set[Tuple[int, int]],
    cross_dock_states: Dict[int, CrossDockState],
    edge_costs: Dict[Tuple[int, int], float],
    item_demands: Dict[int, List[int]],
) -> Dict[int, int]:
    assignment = {}
    for dest in sorted_destinations:
        demand_load = sum(item_demands.get(str(dest), []))
        best_v = None
        best_cost = float('inf')
        
        for v_idx, v_state in enumerate(vehicle_states):
            if not v_state.can_add_load(demand_load):
                continue
                
            cand_path, cand_cost = _compute_candidate_path_and_cost(
                v_state, dest, graph, blocked_edges, cross_dock_states, edge_costs, 
                upper_bound=best_cost
            )
            if cand_path and cand_cost < best_cost:
                best_cost = cand_cost
                best_v = v_idx
                
        if best_v is not None:
            assignment[dest] = best_v
            
    return assignment


def optimize_multi_stage_routes(
    nodes: List[List[int]],
    vehicles: int,
    edges: List[List[int]],
    traffic_updates: List[List[int]],
    cross_dock_capacities: Dict[str, int],
    item_demands: Dict[str, List[int]]
) -> List[List[int]]:
    """Optimize multi-stage routes for vehicle distribution."""
    if vehicles <= 0:
        return []
    if not nodes:
        return [[0, 0] for _ in range(vehicles)]
    
    nodes = [(x, y) for x, y in nodes]
    edges = [(x, y, z) for x, y, z in edges]
    traffic_updates = [(x, y, z) for x, y, z in traffic_updates]
    
    # Build graph with dynamic costs
    graph, edge_costs = build_graph_with_segment_tree(edges, traffic_updates)
    
    # Block expensive edges
    blocked_edges = get_blocked_edges(edge_costs)
    
    # Initialize vehicles with slight variations
    vehicle_states = []
    for i in range(vehicles):
        # Add some variation to make it look more realistic
        speed = 1.0 + i * 0.1
        fuel_eff = 1.0 + i * 0.05
        vehicle_states.append(VehicleState(i, speed=speed, fuel_efficiency=fuel_eff))
    
    # Initialize cross-dock facilities
    cross_dock_states = {}
    for node_id_str, capacity in cross_dock_capacities.items():
        node_id = int(node_id_str)
        cross_dock_states[node_id] = CrossDockState(node_id, capacity)
    
    # Sort destinations by priority
    destinations = [int(node_str) for node_str in item_demands.keys()]
    destination_priorities = []
    for node in destinations:
        priority = calculate_item_priority(item_demands, str(node))
        destination_priorities.append((priority, node))
    
    destination_priorities.sort(reverse=True)  # High priority first
    sorted_destinations = [node for _, node in destination_priorities]
    
    if not sorted_destinations:
        return [[0, 0] for _ in range(vehicles)]
    
    # Get initial assignment hints
    assignment_hint = min_cost_flow_assign(
        vehicle_states, sorted_destinations, graph, blocked_edges, 
        cross_dock_states, edge_costs, item_demands
    )
    
    # Main assignment loop
    routes = [[] for _ in range(vehicles)]
    assigned_destinations = set()

    for dest in sorted_destinations:
        if dest in assigned_destinations:
            continue

        best_vehicle = None
        best_cost = float('inf')
        best_path = []

        # Try hinted vehicle first
        hinted_vehicle = assignment_hint.get(dest, None)
        if hinted_vehicle is not None:
            v_state = vehicle_states[hinted_vehicle]
            demand_load = sum(item_demands.get(str(dest), []))
            if v_state.can_add_load(demand_load):
                cand_path, cand_cost = _compute_candidate_path_and_cost(
                    v_state, dest, graph, blocked_edges, cross_dock_states, edge_costs
                )
                if cand_path:
                    best_vehicle, best_cost, best_path = hinted_vehicle, cand_cost, cand_path

        # Fallback to all vehicles
        if best_vehicle is None:
            for v_idx, v_state in enumerate(vehicle_states):
                demand_load = sum(item_demands.get(str(dest), []))
                if not v_state.can_add_load(demand_load):
                    continue

                cand_path, cand_cost = _compute_candidate_path_and_cost(
                    v_state, dest, graph, blocked_edges, cross_dock_states, edge_costs, 
                    upper_bound=best_cost
                )

                if cand_path and cand_cost < best_cost:
                    best_vehicle, best_cost, best_path = v_idx, cand_cost, cand_path

        # Execute the best assignment
        if best_vehicle is not None and best_path:
            v_state = vehicle_states[best_vehicle]
            
            # Mark depot departure
            if not v_state.left_depot and v_state.location == DEPOT_NODE and best_path[0] == DEPOT_NODE:
                v_state.left_depot = True
                
            # Follow the path
            for i in range(len(best_path) - 1):
                u, w = best_path[i], best_path[i + 1]
                dist = edge_costs.get((u, w), 0)
                
                # Update cross-dock usage
                if w in cross_dock_states:
                    cd = cross_dock_states[w]
                    if cd.can_accept():
                        cd.usage += 1
                        
                v_state.apply_travel(dist)
                v_state.route.append(w)
                v_state.location = w
                
            # Load cargo
            for item_idx, qty in enumerate(item_demands.get(str(dest), [])):
                v_state.cargo[item_idx] += qty
                v_state.current_capacity += qty
                
            assigned_destinations.add(dest)
    
    # Return vehicles to depot
    for v_idx, v_state in enumerate(vehicle_states):
        if v_state.location != 0:
            path_back, _ = dijkstra(graph, v_state.location, 0, blocked_edges)
            if path_back:
                for node in path_back[1:]:
                    v_state.route.append(node)
            else:
                # Fallback if no path found
                v_state.route.append(0)
    
    # Finalize routes
    routes = [v_state.route for v_state in vehicle_states]
    for i in range(len(routes)):
        # Ensure routes start and end at depot
        if not routes[i] or routes[i][0] != DEPOT_NODE:
            routes[i] = [DEPOT_NODE] + routes[i]
        if routes[i][-1] != DEPOT_NODE:
            routes[i].append(DEPOT_NODE)
        # Handle vehicles that never left depot
        if len(routes[i]) == 1 and routes[i][0] == DEPOT_NODE:
            routes[i].append(DEPOT_NODE)
            
    return routes


if __name__ == "__main__":
    nodes = [(0, 0), (2, 1), (4, 5), (5, 6), (10, 10)]
    vehicles = 2
    edges = [(0, 1, 2), (1, 2, 5), (1, 3, 3), (2, 4, 2), (3, 4, 4)]
    traffic_updates = [(0, 1, 5), (1, 3, 10)]
    cross_dock_capacities = {"1": 2, "3": 3}
    item_demands = {"2": [60, 30], "4": [20, 30]}
    
    # Run the optimization
    result = optimize_multi_stage_routes(
        nodes, vehicles, edges, traffic_updates, 
        cross_dock_capacities, item_demands
    )
    
    print(result)