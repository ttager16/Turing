# main.py
from typing import Any, Dict, List, Tuple
import math
import hashlib
import heapq
import itertools

# Constants for deterministic jitter calculation
# Jitter must be ≤ 1e-6 as per spec. Mathematical derivation:
# 1. SHA-256 hash produces 256 bits (32 bytes), we use first 8 bytes (64 bits)
# 2. Max value from 8 bytes: 2^64 - 1 ≈ 1.84 × 10^19
# 3. We need jitter ≤ 1e-6, so: (hash_value mod M) / D ≤ 1e-6
# 4. To ensure this bound, choose M = 10000 (10^4) and D = 10^10 (10_000_000_000)
#    - Max jitter = (M-1) / D = 9999 / 10^10 = 9.999 × 10^-7 < 1e-6 ✓
# 5. This provides ~10^4 distinct jitter values with microsecond-level precision
# 6. Values chosen to balance: (a) sufficient granularity for tie-breaking,
#    (b) strict ≤ 1e-6 bound, (c) computational efficiency (small modulo, clean division)
MAX_JITTER_MODULO = 10000  # Modulo constrains hash output to [0, 9999]
JITTER_PRECISION_DIVISOR = 10_000_000_000  # Scales to ≤ 9.999e-7, ensuring < 1e-6 bound

############################################
# Graph construction (no tuples)
############################################

class Graph:
    def __init__(self):
        # adjacency[u] = list of [v, capacity, base_cost, base_time]
        self.adjacency: Dict[int, List[List[Any]]] = {}
        # key "u-v" is used for variance lookup
        self.variance: Dict[str, float] = {}

    def add_edge(self, u: int, v: int, capacity: float, base_cost: float, base_time: float, var: float):
        self.adjacency.setdefault(u, []).append([v, float(capacity), float(base_cost), float(base_time)])
        # ensure v exists in adjacency map for completeness
        self.adjacency.setdefault(v, self.adjacency.get(v, []))
        self.variance[f"{u}-{v}"] = float(var)

    def neighbors(self, u: int) -> List[List[Any]]:
        return self.adjacency.get(u, [])


############################################
# Path search with specified tie-breaking
############################################

class PathFinder:
    def __init__(self, graph: Graph, congestion_factor: float, hash_seed: int, jitter_fn):
        self.g = graph
        self.cf = float(congestion_factor)
        self.seed = int(hash_seed)
        # Counters for diagnostics (not impacting required fixed metrics)
        self.paths_considered = 0
        self.ties_broken = 0
        self.jitter_fn = jitter_fn
        # Track paths by full signature (cost, edges, path_tuple) to detect jitter tie-breaking
        # When cost, edges, and path_tuple are all equal, jitter breaks the tie
        self._heap_entries_by_full_sig: Dict[Tuple[float, int, Tuple[int, ...]], List[Tuple[float, int]]] = {}
        # Track which full signatures have already been counted for ties_broken
        self._ties_counted: set = set()

    def _edge_weight(self, edge: List[Any]) -> float:
        # edge = [v, capacity, base_cost, base_time]
        base_cost = edge[2]
        return base_cost * self.cf

    def best_path(self, src: int, dst: int, required_amount: float,
                  remaining_capacities: Dict[str, float], is_priority: bool = False) -> Dict[str, Any]:
        """
        Dijkstra-like search minimizing cost; apply tie-breaking:
        1) lower total cost
        2) fewer edges
        3) lexicographic path
        4) deterministic jitter (very small)
        Returns dict with: {"path": List[int], "cost": float, "edges": int, "jitter_used": bool}
        If no path, returns {"path": [], "cost": inf, "edges": 0, "jitter_used": False}
        
        Args:
            is_priority: If True, this path-finding will count toward paths_considered metric.
        """
        # Reset per-call tracking for tie-breaking (heap entries are per-search)
        # Track by (cost, edges) to detect when multiple paths with same cost/edges exist
        # (indicating jitter may break ties even if path_tuples differ lexicographically)
        heap_entries_by_cost_edges: Dict[Tuple[float, int], set] = {}
        ties_counted_this_call: set = set()
        
        # Priority queue items use deterministic tie-breaking per spec:
        # (cost, edges, tuple(path), jitter, node, counter)
        counter = itertools.count()
        pq: List[Tuple[float, int, Tuple[int, ...], float, int, int]] = []

        # dist map: node -> (best_cost, edges, path_tuple)
        visited_best: Dict[int, Tuple[float, int, Tuple[int, ...]]] = {}

        start_path = (src,)
        start_jitter = self.jitter_fn(list(start_path), self.seed)
        start_item = (0.0, 0, start_path, start_jitter, src, next(counter))
        heapq.heappush(pq, start_item)
        # Initialize tracking for start state
        cost_edges_sig = (0.0, 0)
        heap_entries_by_cost_edges[cost_edges_sig] = {start_path}

        while pq:
            cost_so_far, edges_so_far, path_tuple, jitter_key, u, _ = heapq.heappop(pq)
            
            # Canonical state signature for tie-breaking tracking
            best = visited_best.get(u)
            improved = False
            if best is None:
                improved = True
            else:
                prev_cost, prev_edges, prev_path_tuple = best
                if cost_so_far < prev_cost:
                    improved = True
                elif math.isclose(cost_so_far, prev_cost, rel_tol=1e-12, abs_tol=1e-12):
                    if edges_so_far < prev_edges:
                        improved = True
                    elif edges_so_far == prev_edges:
                        if path_tuple < prev_path_tuple:
                            improved = True
                            # lexicographic tie-break applied (no jitter needed)
                        elif path_tuple == prev_path_tuple:
                            # Absolute tie on cost, edges, and path - jitter decides
                            improved = False  # keep current improved=False to avoid redundant visitation
                        else:
                            # path_tuple > prev_path_tuple: this state loses due to lex order
                            improved = False  # keep current improved=False to avoid redundant visitation

            if not improved:
                continue

            visited_best[u] = (cost_so_far, edges_so_far, path_tuple)
            # Count paths considered: increment for each priority delivery's successful path-finding
            # This counts every time we successfully find a path for a priority delivery
            if u == dst:
                if is_priority:
                    self.paths_considered += 1
                    # Check if this destination path has ties - count ties only when reaching destination
                    # with a (cost, edges) signature that has multiple path_tuples
                    cost_edges_sig = (cost_so_far, edges_so_far)
                    if cost_edges_sig in heap_entries_by_cost_edges:
                        existing_paths = heap_entries_by_cost_edges[cost_edges_sig]
                        if len(existing_paths) > 1 and cost_edges_sig not in ties_counted_this_call:
                            # Multiple paths reached destination with same (cost, edges) - jitter broke the tie
                            self.ties_broken += 1
                            ties_counted_this_call.add(cost_edges_sig)
                final_cost = cost_so_far
                jitter_used = False  # jitter is encoded in heap ordering as a key
                return {
                    "path": list(path_tuple),
                    "cost": final_cost,
                    "edges": edges_so_far,
                    "jitter_used": jitter_used
                }

            for edge in self.g.neighbors(u):
                v, capacity, base_cost, base_time = edge
                # respect remaining capacities for the required amount
                cap_key = f"{u}-{v}"
                rem_cap = remaining_capacities.get(cap_key, capacity)
                if rem_cap <= 0.0:
                    continue
                # Edge weight
                w = self._edge_weight(edge)
                new_cost = cost_so_far + w
                new_edges = edges_so_far + 1
                new_path_tuple = path_tuple + (v,)
                # Jitter used as 4th tiebreaker key (≤ 1e-6), does not alter primary cost
                jitter = self.jitter_fn(list(new_path_tuple), self.seed)
                # Track by (cost, edges) to detect when multiple paths with same cost/edges exist
                # We'll only count ties when paths actually reach the destination
                cost_edges_sig = (new_cost, new_edges)
                if cost_edges_sig in heap_entries_by_cost_edges:
                    existing_paths = heap_entries_by_cost_edges[cost_edges_sig]
                    if path_tuple not in existing_paths:
                        existing_paths.add(path_tuple)
                else:
                    # First occurrence of this (cost, edges) combination
                    heap_entries_by_cost_edges[cost_edges_sig] = {path_tuple}
                # Push with tie-aware tuple per required order
                heapq.heappush(pq, (new_cost, new_edges, new_path_tuple, jitter, v, next(counter)))

        return {"path": [], "cost": float("inf"), "edges": 0, "jitter_used": False}


############################################
# Core optimization - Class-based structure
############################################

class DeliveryRouteOptimizer:
    """
    Deterministic probabilistic routing solver.
    
    Encapsulates all optimization logic, helper functions, and state management
    in a class structure for improved organization and readability.
    """
    
    def __init__(self, network: List[List[Any]], deliveries: List[Dict[str, Any]],
                 priority_deliveries: List[Dict[str, Any]], traffic_variance: Dict[str, float],
                 vehicle_capacity: Dict[str, float], driver_constraints: Dict[str, float],
                 congestion_factor: float, hash_seed: int, probabilistic_threshold: float):
        """Initialize optimizer with network configuration and constraints."""
        self.network = network
        self.deliveries = deliveries
        self.priority_deliveries = priority_deliveries
        self.traffic_variance = traffic_variance
        self.vehicle_capacity = vehicle_capacity
        self.driver_constraints = driver_constraints
        self.congestion_factor = congestion_factor
        self.hash_seed = hash_seed
        self.probabilistic_threshold = probabilistic_threshold
        
        # Build graph and initialize state
        self.graph = self._build_graph()
        self.edge_time_cf = self._compute_edge_times()
        self.remaining_cap: Dict[str, float] = {}
        self.driver_used: Dict[str, float] = {vt: 0.0 for vt in sorted(vehicle_capacity.keys())}
        self.pathfinder = PathFinder(self.graph, congestion_factor, hash_seed, self.stable_jitter_for_path)
        self.available_vehicles = sorted(vehicle_capacity.keys())
        
        # Output accumulators
        self.out_routes: List[Dict[str, Any]] = []
        self.delivery_status: List[Dict[str, Any]] = []
        self.expected_cost_sum = 0.0
    
    # ========== Helper Methods (previously nested functions) ==========
    
    def stable_jitter_for_path(self, path: List[int], seed: int) -> float:
        """
        Compute deterministic jitter for path-based tie-breaking.
        
        Uses SHA-256 hash to generate a small deterministic value (≤ 1e-6)
        that breaks ties in path selection while maintaining reproducibility.
        """
        path_string = ",".join(map(str, path))
        data = f"{seed}|{path_string}".encode()
        h = hashlib.sha256(data).digest()
        H = int.from_bytes(h[:8], 'big')
        return (H % MAX_JITTER_MODULO) / JITTER_PRECISION_DIVISOR
    
    def std_normal_cdf(self, x: float) -> float:
        """Compute standard normal cumulative distribution function."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    
    def on_time_probability(self, mu: float, sigma2: float, deadline: float) -> float:
        """
        Compute probability that delivery arrives on time.
        
        Uses normal distribution: P(arrival_time ≤ deadline) = Φ((deadline - μ) / σ)
        where μ = mean travel time, σ² = variance.
        """
        if sigma2 <= 0.0:
            return 1.0 if mu <= deadline else 0.0
        sigma = math.sqrt(sigma2)
        z = (deadline - mu) / sigma
        return self.std_normal_cdf(z)
    
    def get_vehicle_for_type(self, delivery_type: str) -> str:
        """
        Select vehicle with highest remaining budget ratio.
        
        Policy: Choose vehicle maximizing (remaining_budget / total_budget),
        breaking ties lexicographically by vehicle name.
        """
        if not self.available_vehicles:
            return ""
        
        best_vehicle = ""
        max_ratio = -1.0
        
        for veh in sorted(self.available_vehicles):
            total_budget = self.driver_constraints.get(veh, 0.0)
            if total_budget <= 0:
                continue
            used_budget = self.driver_used.get(veh, 0.0)
            remaining_budget = total_budget - used_budget
            ratio = remaining_budget / total_budget
            
            if ratio > max_ratio:
                max_ratio = ratio
                best_vehicle = veh
        
        return best_vehicle
    
    def _accumulate_time_and_variance(self, path: List[int]) -> Tuple[float, float]:
        """Compute total mean travel time and variance along a path."""
        mu = 0.0
        var = 0.0
        for u, v in zip(path[:-1], path[1:]):
            for edge in self.graph.neighbors(u):
                if edge[0] == v:
                    base_time = edge[3]
                    mu += base_time * self.congestion_factor
                    var += self.graph.variance[f"{u}-{v}"] * (self.congestion_factor * self.congestion_factor)
                    break
        return mu, var
    
    def _path_min_capacity(self, path: List[int]) -> float:
        """Find minimum remaining capacity along a path (bottleneck)."""
        cmin = float("inf")
        for u, v in zip(path[:-1], path[1:]):
            cap_key = f"{u}-{v}"
            rem = self.remaining_cap.get(cap_key, None)
            if rem is None:
                cap_val = None
                for e in self.graph.neighbors(u):
                    if e[0] == v:
                        cap_val = e[1]
                        break
                if cap_val is None:
                    return 0.0
                rem = cap_val
            cmin = min(cmin, rem)
        if cmin == float("inf"):
            return 0.0
        return max(0.0, cmin)
    
    def _deduct_capacity(self, path: List[int], amount: float) -> None:
        """Reduce remaining capacity along path by specified amount."""
        for u, v in zip(path[:-1], path[1:]):
            cap_key = f"{u}-{v}"
            if cap_key not in self.remaining_cap:
                cap_val = None
                for e in self.graph.neighbors(u):
                    if e[0] == v:
                        cap_val = e[1]
                        break
                if cap_val is None:
                    continue
                self.remaining_cap[cap_key] = cap_val
            self.remaining_cap[cap_key] -= amount
            if self.remaining_cap[cap_key] < 0.0:
                self.remaining_cap[cap_key] = 0.0
    
    def _driver_hours_for_path(self, path: List[int], amount: float, vehicle_cap: float) -> float:
        """Compute driver-hours needed to transport amount along path."""
        if vehicle_cap <= 0:
            return float("inf")
        total_time = 0.0
        for u, v in zip(path[:-1], path[1:]):
            t = self.edge_time_cf.get((u, v))
            if t is not None:
                total_time += t
            else:
                for e in self.graph.neighbors(u):
                    if e[0] == v:
                        total_time += e[3] * self.congestion_factor
                        break
        return (total_time * amount) / vehicle_cap
    
    # ========== Setup Methods ==========
    
    def _build_graph(self) -> Graph:
        """Construct graph from network edges."""
        g = Graph()
        for row in self.network:
            u, v, cap, cost, time_ = int(row[0]), int(row[1]), float(row[2]), float(row[3]), float(row[4])
            var = float(self.traffic_variance.get(f"{u}-{v}", 0.0))
            g.add_edge(u, v, cap, cost, time_, var)
        return g
    
    def _compute_edge_times(self) -> Dict[Tuple[int, int], float]:
        """Precompute edge travel times with congestion factor."""
        edge_time_cf: Dict[Tuple[int, int], float] = {}
        for row in self.network:
            u, v = int(row[0]), int(row[1])
            time_ = float(row[4])
            edge_time_cf[(u, v)] = time_ * self.congestion_factor
        return edge_time_cf
    
    def _sort_deliveries(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Sort deliveries deterministically per Prompt specification."""
        deliveries_sorted = sorted(
            enumerate(self.deliveries),
            key=lambda idx_d: (idx_d[1]["src"], idx_d[1]["dst"], idx_d[1]["type"], idx_d[1]["amount"], idx_d[0])
        )
        priority_sorted = sorted(
            enumerate(self.priority_deliveries),
            key=lambda idx_pd: (idx_pd[1]["src"], idx_pd[1]["dst"], idx_pd[1]["type"], idx_pd[1]["required"], idx_pd[0])
        )
        return [d for _, d in deliveries_sorted], [pd for _, pd in priority_sorted]
    
    # ========== Core Logic Methods ==========
    
    def _assign_amount_along_path(self, dsrc: int, ddst: int, dtyp: str, amt: float, veh_type: str) -> float:
        """
        Assign delivery amount along path while respecting capacity and driver-hour constraints.
        
        Returns actual amount assigned (may be less than requested due to constraints).
        """
        if amt <= 0.0:
            return 0.0
        
        res = self.pathfinder.best_path(dsrc, ddst, amt, self.remaining_cap)
        path = res["path"]
        if not path:
            return 0.0
        
        # Find path bottleneck capacity
        cmin = self._path_min_capacity(path)
        if cmin <= 0.0:
            return 0.0
        assignable = min(amt, cmin)
        
        veh_cap = self.vehicle_capacity[veh_type]
        
        # Enforce driver-hour constraint
        need_hours = self._driver_hours_for_path(path, assignable, veh_cap)
        budget_available = max(0.0, self.driver_constraints.get(veh_type, 0.0) - self.driver_used.get(veh_type, 0.0))
        
        if need_hours > budget_available:
            if need_hours > 0:
                scale = budget_available / need_hours
                assignable = assignable * scale
                need_hours = self._driver_hours_for_path(path, assignable, veh_cap)
            else:
                assignable = 0.0
                need_hours = 0.0
        
        if assignable <= 0.0:
            return 0.0
        
        # Update state: deduct capacity and driver hours
        self._deduct_capacity(path, assignable)
        self.driver_used[veh_type] = self.driver_used.get(veh_type, 0.0) + need_hours
        
        # Record routes and accumulate cost
        for u, v in zip(path[:-1], path[1:]):
            self.out_routes.append({"u": u, "v": v, "delivery_type": dtyp, "amount": assignable, "vehicle": veh_type})
            for e in self.graph.neighbors(u):
                if e[0] == v:
                    self.expected_cost_sum += e[2] * assignable * self.congestion_factor
                    break
        
        return assignable
    
    def _process_priority_delivery(self, pd: Dict[str, Any]) -> None:
        """Process a single priority delivery."""
        ptype = pd["type"]
        psrc = pd["src"]
        pdst = pd["dst"]
        deadline = float(pd["deadline"])
        required = float(pd["required"])
        
        res = self.pathfinder.best_path(psrc, pdst, required, self.remaining_cap, is_priority=True)
        path = res["path"]
        
        delivered_amt = 0.0
        on_time_p = 0.0
        if path:
            mu, var = self._accumulate_time_and_variance(path)
            on_time_p = self.on_time_probability(mu, var, deadline)
            
            if on_time_p >= float(self.probabilistic_threshold):
                veh = self.get_vehicle_for_type(ptype)
                delivered_amt = self._assign_amount_along_path(psrc, pdst, ptype, required, veh)
            else:
                delivered_amt = 0.0
                on_time_p = 0.0
                path = []
        
        self.delivery_status.append({
            "delivery_type": ptype,
            "src": psrc,
            "dst": pdst,
            "requested": required,
            "delivered": delivered_amt,
            "is_priority": True,
            "deadline": deadline,
            "on_time_probability": on_time_p,
            "route": path if delivered_amt > 0 else []
        })
    
    def _process_regular_delivery(self, d: Dict[str, Any]) -> None:
        """Process a single non-priority delivery."""
        src, dst, dtyp, amt = d["src"], d["dst"], d["type"], float(d["amount"])
        
        res = self.pathfinder.best_path(src, dst, amt, self.remaining_cap, is_priority=False)
        if not res["path"]:
            self.delivery_status.append({
                "delivery_type": dtyp,
                "src": src,
                "dst": dst,
                "requested": amt,
                "delivered": 0.0,
                "is_priority": False,
                "deadline": 0.0,
                "on_time_probability": 1.0,
                "route": []
            })
            return
        
        veh = self.get_vehicle_for_type(dtyp)
        assigned = self._assign_amount_along_path(src, dst, dtyp, amt, veh)
        
        self.delivery_status.append({
            "delivery_type": dtyp,
            "src": src,
            "dst": dst,
            "requested": amt,
            "delivered": assigned,
            "is_priority": False,
            "deadline": 0.0,
            "on_time_probability": 1.0,
            "route": res["path"] if assigned > 0 else []
        })
    
    def _compute_resource_usage(self) -> Dict[str, float]:
        """Compute resource usage ratios for all vehicles."""
        resource_usage = {}
        for vt in sorted(self.driver_constraints.keys()):
            budget = self.driver_constraints[vt]
            used = self.driver_used.get(vt, 0.0)
            ratio = used / budget if budget > 0 else 0.0
            resource_usage[vt] = ratio
        return resource_usage
    
    def optimize(self) -> Dict[str, Any]:
        """
        Main optimization method.
        
        Processes priority deliveries first, then regular deliveries,
        and returns the complete solution.
        """
        deliveries_sorted, priority_sorted = self._sort_deliveries()
        
        # Process priority deliveries first
        for pd in priority_sorted:
            self._process_priority_delivery(pd)
        
        # Process regular deliveries
        for d in deliveries_sorted:
            self._process_regular_delivery(d)
        
        # Compute final outputs
        resource_usage = self._compute_resource_usage()
        metrics = {"paths_considered": self.pathfinder.paths_considered, 
                   "ties_broken": self.pathfinder.ties_broken}
        
        return {
            "routes": self.out_routes,
            "expected_cost": self.expected_cost_sum,
            "delivery_status": self.delivery_status,
            "resource_usage": resource_usage,
            "metrics": metrics
        }


def optimize_delivery_routes(
    network: List[List[Any]],                 # [u, v, capacity, base_cost, base_time]
    deliveries: List[Dict[str, Any]],         # {"src": int, "dst": int, "type": str, "amount": float}
    priority_deliveries: List[Dict[str, Any]],# {"type": str, "src": int, "dst": int, "deadline": float, "required": float}
    traffic_variance: Dict[str, float],       # "u-v" -> variance
    vehicle_capacity: Dict[str, float],       # vehicle type -> capacity
    driver_constraints: Dict[str, float],     # vehicle type -> driver-hour budget
    congestion_factor: float,                 # scales cost & time
    hash_seed: int,                           # deterministic tie-breaking seed
    probabilistic_threshold: float            # on-time probability threshold
) -> Dict[str, Any]:
    """
    Deterministic probabilistic routing solver (public API).

    Purpose:
        Compute cost-minimizing delivery routes on a directed network with capacity,
        per-edge variance, and per-vehicle driver-hour budgets. Priority deliveries
        must satisfy the on-time probability threshold. Non-priority deliveries are
        routed subject to remaining constraints. Deterministic tie-breaking ensures
        reproducible outputs.

    Args:
        network: List of edges [u, v, capacity, base_cost, base_time].
        deliveries: Non-priority deliveries, each {"src","dst","type","amount"}.
        priority_deliveries: Priority deliveries, each {"type","src","dst","deadline","required"}.
        traffic_variance: Map "u-v" -> variance (time^2) for each directed edge.
        vehicle_capacity: Map vehicle -> capacity (amount per driver-hour).
        driver_constraints: Map vehicle -> total driver-hours budget available.
        congestion_factor: Multiplier for costs and travel times.
        hash_seed: Integer seed used for deterministic tie-breaking jitter.
        probabilistic_threshold: Minimum on-time probability for priority deliveries.

    Returns:
        Dict with keys:
            - routes: List of per-edge assignments with fields {u,v,delivery_type,amount,vehicle}.
            - expected_cost: Total expected cost (sum base_cost * amount * congestion_factor).
            - delivery_status: List of per-delivery status entries describing requested vs delivered,
              priority flags, deadline, on_time_probability, and chosen route.
            - resource_usage: Map vehicle -> used_driver_hours / driver_constraints.
            - metrics: Deterministic metrics per Prompt (paths_considered, ties_broken).
    """
    optimizer = DeliveryRouteOptimizer(
        network, deliveries, priority_deliveries, traffic_variance,
        vehicle_capacity, driver_constraints, congestion_factor,
        hash_seed, probabilistic_threshold
    )
    return optimizer.optimize()


if __name__ == "__main__":
    import json
    
    # Simple demo aligned with the example
    network = [
        [0, 1, 10.0, 5.0, 2.0],
        [1, 2, 8.0, 3.0, 1.5],
        [0, 2, 15.0, 7.0, 3.0]
    ]

    deliveries = [
        {"src": 0, "dst": 2, "type": "STANDARD", "amount": 6.0},
        {"src": 1, "dst": 2, "type": "EXPRESS", "amount": 4.0}
    ]

    priority_deliveries = [
        {"type": "URGENT", "src": 0, "dst": 2, "deadline": 4.0, "required": 3.0}
    ]

    traffic_variance = {"0-1": 0.1, "1-2": 0.2, "0-2": 0.15}

    vehicle_capacity = {"VAN": 10.0, "TRUCK": 20.0}
    driver_constraints = {"VAN": 8.0, "TRUCK": 12.0}

    result = optimize_delivery_routes(
        network,
        deliveries,
        priority_deliveries,
        traffic_variance,
        vehicle_capacity,
        driver_constraints,
        1.0,
        42,
        0.8
    )
    print(json.dumps(result, indent=2, sort_keys=True))