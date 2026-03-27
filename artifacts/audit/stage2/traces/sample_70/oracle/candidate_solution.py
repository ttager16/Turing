from typing import List, Dict, Any
import heapq
import math

# Named constants to replace magic numbers and clarify intent
ALPHA = 0.6  # EMA weight blending current signals vs historical
PRIORITY_DISCOUNT_FACTOR = 0.4  # Scale of priority impact on edge costs
MIN_COST_THRESHOLD = 1e-6  # Minimum edge cost clamp to avoid zero/negative costs
LAYER_SWITCH_MULTIPLIER = 1.55  # Cost multiplier when crossing layers
CONGESTION_INFLATION_RATE = 0.1  # Congestion inflation per unit served
COST_EPSILON = 1e-12  # Epsilon for deterministic tie-breaking on floats

def optimize_traffic_batch(
    city_network: List[List[Any]],
    historical_data: List[List[Any]],
    current_conditions: Dict[str, Any],
    demands: List[List[Any]]
) -> Dict[str, Any]:
    """
    Deterministic batch routing with capacity + congestion updates.

    Inputs are JSON-compatible only. Returns:
    {
      "routes": List[List[str]],
      "unserved_demands": int,
      "layer_switches": int,
      "total_cost": float
    }
    """


    def _clamp_float(x: float, lo: float, hi: float) -> float:
        if x < lo: return lo
        if x > hi: return hi
        return x

    def _edge_id(u: str, v: str) -> str:
        return f"{u}-{v}"

    def _layer_of(node: str) -> str:
        
        i = node.find(":")
        return "" if i < 0 else node[:i]

    def _finite(x: float) -> float:
        try:
            xf = float(x)
            return xf if math.isfinite(xf) else 0.0
        except Exception:
            return 0.0

 
    nodes: Dict[str, bool] = {}
    edges: List[List[Any]] = []  # [u, v, base_cost, eid]
    adj: Dict[str, List[List[Any]]] = {}

    for rec in city_network:
        if (not isinstance(rec, list)) or len(rec) != 3:
            continue
        u, v = str(rec[0]), str(rec[1])
        try:
            b = float(rec[2])
        except Exception:
            continue
        if b <= 0.0:
            continue
        eid = _edge_id(u, v)
        nodes[u] = True
        nodes[v] = True
        edges.append([u, v, b, eid])
        adj.setdefault(u, []).append([v, b, eid])


    h_map: Dict[str, float] = {}
    for rec in historical_data:
        if (not isinstance(rec, list)) or len(rec) != 2:
            continue
        eid = str(rec[0])
        try:
            h_val = float(rec[1])
        except Exception:
            h_val = 0.0
        h_map[eid] = _finite(h_val)

    # current_conditions: {"U-V": float, ..., "capacity_map": {...}?}
    capacity_map = {}
    if isinstance(current_conditions, dict):
        maybe_cap = current_conditions.get("capacity_map")
        if isinstance(maybe_cap, dict):
            # keep only ints >= 0 (we'll clamp below anyway)
            for k, v in maybe_cap.items():
                try:
                    capacity_map[str(k)] = int(v)
                except Exception:
                    pass

    curr_signals: Dict[str, float] = {}
    if isinstance(current_conditions, dict):
        for k, v in current_conditions.items():
            if k == "capacity_map":
                continue
            try:
                curr_signals[str(k)] = _finite(float(v))
            except Exception:
                curr_signals[str(k)] = 0.0


    alpha = ALPHA
    cost_base: Dict[str, float] = {}
    for _u, _v, b, eid in edges:
        h = h_map.get(eid, 0.0)
        c = curr_signals.get(eid, 0.0)
        ema = alpha * c + (1.0 - alpha) * h
        effective_ema = max(0.0, ema)
        cost_base[eid] = _finite(b * (1.0 + effective_ema / 100.0))


    residual: Dict[str, int] = {eid: 1 for _, _, _, eid in edges}
    for eid, cap in capacity_map.items():
        if eid in residual:
            try:
                residual[eid] = max(0, int(cap))
            except Exception:
                pass

    def _shortest_path(src: str, dst: str, units: int, priority: float) -> (List[str], float):
        if not nodes.get(src, False) or not nodes.get(dst, False):
            return [], float("inf")

        p = _clamp_float(_finite(priority), 0.0, 1.0)
        # Per edge for this demand: cost = (cost_base * layer_mult) * (1 - PRIORITY_DISCOUNT_FACTOR*p), clamped to >= MIN_COST_THRESHOLD
        pr_scale = max(MIN_COST_THRESHOLD, 1.0 - PRIORITY_DISCOUNT_FACTOR * p)

        start_path = [src]
        start_key = "->".join(start_path)
        heap: List[List[Any]] = [[0.0, start_key, src, start_path]]
        best: Dict[str, List[Any]] = {src: [0.0, start_key, start_path]}

        while heap:
            cost_u, key_u, u, path_u = heapq.heappop(heap)
            bc = best.get(u)
            # Skip stale entry
            if bc is not None and (cost_u > bc[0] or (abs(cost_u - bc[0]) <= COST_EPSILON and key_u > bc[1])):
                continue
            if u == dst:
                return path_u[:], cost_u

            for v, b, eid in adj.get(u, []):
                # capacity feasibility for this demand
                if residual.get(eid, 0) < units:
                    continue

                layer_mult = LAYER_SWITCH_MULTIPLIER if _layer_of(u) != _layer_of(v) else 1.0
                base_now = cost_base.get(eid, b)  # fall back to b if not found (defensive)
                edge_cost = base_now * layer_mult
                edge_cost *= pr_scale
                edge_cost = max(MIN_COST_THRESHOLD, _finite(edge_cost))

                new_cost = cost_u + edge_cost
                new_path = path_u + [v]
                new_key = "->".join(new_path)

                prev = best.get(v)
                if (prev is None or
                    new_cost < prev[0] - COST_EPSILON or
                    (abs(new_cost - prev[0]) <= COST_EPSILON and new_key < prev[1])):
                    best[v] = [new_cost, new_key, new_path]
                    heapq.heappush(heap, [new_cost, new_key, v, new_path])

        return [], float("inf")


    def _decrement_capacity(path: List[str], units: int) -> None:
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            eid = _edge_id(u, v)
            if eid in residual:
                residual[eid] = max(0, residual[eid] - units)

    def _count_layer_switches(path: List[str]) -> int:
        switches = 0
        for i in range(len(path) - 1):
            if _layer_of(path[i]) != _layer_of(path[i+1]):
                switches += 1
        return switches

    def _inflate_costs(path: List[str], units: int) -> None:
        if units <= 0:
            return
        factor = 1.0 + CONGESTION_INFLATION_RATE * float(units)
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            eid = _edge_id(u, v)
            if eid in cost_base:
                cost_base[eid] = _finite(cost_base[eid] * factor)


    routes: List[List[str]] = []
    unserved = 0
    total_switches = 0
    total_cost = 0.0

    for d in demands:
        # Validate demand record
        if (not isinstance(d, list)) or len(d) != 5:
            routes.append([])
            unserved += 1
            continue

        src, dst = str(d[0]), str(d[1])
        commodity = d[2]  # not used in cost, but kept for signature compliance
        try:
            units = int(d[3])
        except Exception:
            units = 0
        try:
            priority = float(d[4])
        except Exception:
            priority = 0.0

        units = max(0, units)
        priority = _clamp_float(priority, 0.0, 1.0)

        # Find feasible, minimum-cost path with tie-break
        path, path_cost = _shortest_path(src, dst, units, priority)

        if not path:
            routes.append([])
            unserved += 1
            continue

        # Capacity update (no change when units == 0, by formula it becomes 0)
        if units > 0:
            _decrement_capacity(path, units)

        # Congestion inflation for future demands (only if served and units > 0)
        if units > 0:
            _inflate_costs(path, units)

        # Accumulate stats *as-of routing time* (cost used by Dijkstra already includes layer & priority)
        total_cost += _finite(path_cost)
        total_switches += _count_layer_switches(path)
        routes.append(path)

    # Clean up tiny negative float noise
    if total_cost < 0.0 and total_cost > -COST_EPSILON:
        total_cost = 0.0

    return {
        "routes": routes,
        "unserved_demands": int(unserved),
        "layer_switches": int(total_switches),
        "total_cost": float(total_cost)
    }


if __name__ == "__main__":
   
    city_network = [
        ["L1:A", "L1:B", 2.5],
        ["L1:B", "L1:C", 3.0],
        ["L2:A", "L2:B", 1.0],
        ["L2:B", "L2:C", 1.5],
        ["L1:C", "L1:D", 2.0],
        ["L2:C", "L2:D", 2.5],
        ["L1:C", "L2:C", 0.8],  # cross-layer edge (L1 -> L2)
    ]
    historical_data = [
        ["L1:A-L1:B", 90],
        ["L1:B-L1:C", 110],
        ["L2:A-L2:B", 70],
        ["L1:C-L1:D", 60],
        ["L2:C-L2:D", 100],
        ["L1:C-L2:C", 50],
    ]
    current_conditions = {
        "L1:A-L1:B": 95,
        "L1:B-L1:C": 120,
        "L2:A-L2:B": 75,
        "L1:C-L1:D": 80,
        "L2:C-L2:D": 105,
        "L1:C-L2:C": 40,
        "capacity_map": {
            "L1:A-L1:B": 2,
            "L1:B-L1:C": 1,
            "L1:C-L1:D": 1,
            "L1:C-L2:C": 1,
            "L2:A-L2:B": 1,
            "L2:B-L2:C": 1,
            "L2:C-L2:D": 1,
        },
    }
    demands = [
        ["L1:A", "L1:D", "passenger", 1, 0.5],
        ["L2:A", "L2:D", "freight", 1, 0.3],
        ["L1:A", "L2:D", "emergency", 1, 1.0],
    ]

    summary = optimize_traffic_batch(city_network, historical_data, current_conditions, demands)
    import json
    print(json.dumps(summary, indent=2))