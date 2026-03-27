from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List
import heapq


# Graph structure constraints
MAX_NODES = 1000
MAX_EDGES_PER_NODE = 50
MAX_BASE_WEIGHT = 1000

# Validation ranges for parameters
MIN_RELIABILITY = 0.1
MAX_RELIABILITY = 1.0
MIN_ROBUSTNESS_WEIGHT = 0.1
MAX_ROBUSTNESS_WEIGHT = 2.0

# Edge parameter validation ranges
MIN_CONGESTION = 1.0
MAX_CONGESTION = 5.0
MIN_RELIABILITY_SCORE = 0.1
MAX_RELIABILITY_SCORE = 1.0
MIN_PEAK_HOUR_ADJUSTMENT = 1.0
MAX_PEAK_HOUR_ADJUSTMENT = 3.0


class _RobustPathUtils:
    # Utility helpers for robust shortest path computation.
    @staticmethod
    def is_number(x):
        """Return True if x is an int/float/Decimal value."""
        return isinstance(x, (int, float, Decimal))

    @staticmethod
    def quantize2(val):
        """Round a value to 2 decimal places using bankers' rounding."""
        if isinstance(val, Decimal):
            d = val
        else:
            d = Decimal(str(val))
        return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def appears_in_chain(label, node_id):
        """Detect cycles by checking if node_id already appears in the label chain."""
        cur = label
        while cur is not None:
            if cur["node"] == node_id:
                return True
            cur = cur["prev"]
        return False

    @staticmethod
    def effective_cost(edge, is_peak_hour):
        """Compute effective traversal cost for an edge under peak/non-peak conditions."""
        bw = Decimal(str(edge[1]))
        cm = Decimal(str(edge[2]))
        if is_peak_hour:
            pha = Decimal(str(edge[4]))
            return bw * cm * pha
        else:
            return bw * cm

    @staticmethod
    def robustness_gain(edge, robustness_weight_decimal):
        """Compute robustness gain contributed by an edge."""
        rs = Decimal(str(edge[3]))
        return rs * robustness_weight_decimal

    @staticmethod
    def is_dominated(candidate, existing_list):
        """Check if candidate label is dominated by any existing label (cost>= and rob<=)."""
        j = 0
        while j < len(existing_list):
            e = existing_list[j]
            if (e["cost"] <= candidate["cost"] and e["rob"] >= candidate["rob"]) and (
                    e["cost"] < candidate["cost"] or e["rob"] > candidate["rob"]):
                return True
            j += 1
        return False

    @staticmethod
    def prune_with(candidate, existing_list):
        """Prune labels strictly dominated by candidate; keep the rest."""
        k = 0
        kept = []
        while k < len(existing_list):
            e = existing_list[k]
            if (candidate["cost"] <= e["cost"] and candidate["rob"] >= e["rob"]) and (
                    candidate["cost"] < e["cost"] or candidate["rob"] > e["rob"]):
                pass
            else:
                kept.append(e)
            k += 1
        return kept


def robust_shortest_path(
        graph: Dict[str, List[List]],
        start_node: str,
        end_node: str,
        is_peak_hour: bool,
        min_reliability: float,
        robustness_weight: float
) -> List[str]:
    """Find a path minimizing travel time subject to a minimum robustness.

    Uses Dijkstra-style label setting with Pareto pruning over (cost, robustness).
    Returns node IDs list or [] if no path satisfies the robustness threshold; on
    invalid input returns {"error": "..."}.
    """

    if not isinstance(graph, dict):
        return {"error": "Graph must be a dictionary"}

    if len(graph) > MAX_NODES:
        return {"error": "Graph cannot have more than 1000 nodes"}

    if not isinstance(is_peak_hour, bool):
        return {"error": "is_peak_hour must be a boolean"}

    if start_node not in graph:
        return {"error": "Start node not found in graph"}
    if end_node not in graph:
        return {"error": "End node not found in graph"}

    if not _RobustPathUtils.is_number(min_reliability) or float(min_reliability) < MIN_RELIABILITY or float(min_reliability) > MAX_RELIABILITY:
        return {"error": "Minimum reliability must be between 0.1 and 1.0"}
    if not _RobustPathUtils.is_number(robustness_weight) or float(robustness_weight) < MIN_ROBUSTNESS_WEIGHT or float(robustness_weight) > MAX_ROBUSTNESS_WEIGHT:
        return {"error": "Robustness weight must be between 0.1 and 2.0"}

    for node in list(graph.keys()):
        adj = graph[node]
        if len(adj) > MAX_EDGES_PER_NODE:
            return {"error": "Node cannot have more than 50 edges"}

        i = 0
        while i < len(adj):
            edge = adj[i]
            if not isinstance(edge, list) or len(edge) != 5:
                return {"error": "Edge list contains invalid types"}

            neighbor = edge[0]
            base_weight = edge[1]
            congestion_multiplier = edge[2]
            reliability_score = edge[3]
            peak_hour_adjustment = edge[4]

            # Check edge list invalid types (neighbor must be string; weights must be numeric)
            if not isinstance(neighbor, str) or not (_RobustPathUtils.is_number(base_weight) and _RobustPathUtils.is_number(congestion_multiplier) and _RobustPathUtils.is_number(reliability_score) and _RobustPathUtils.is_number(
                    peak_hour_adjustment)):
                return {"error": "Edge list contains invalid types"}

            if neighbor not in graph:
                return {"error": "Neighbor node not found in graph"}

            if not _RobustPathUtils.is_number(base_weight) or base_weight <= 0:
                return {"error": "Base weight must be positive"}
            if base_weight > MAX_BASE_WEIGHT:
                return {"error": "Base weight must not exceed 1000"}

            if float(congestion_multiplier) < MIN_CONGESTION or float(congestion_multiplier) > MAX_CONGESTION:
                return {"error": "Congestion multiplier must be between 1.0 and 5.0"}
            if float(reliability_score) < MIN_RELIABILITY_SCORE or float(reliability_score) > MAX_RELIABILITY_SCORE:
                return {"error": "Reliability score must be between 0.1 and 1.0"}
            if float(peak_hour_adjustment) < MIN_PEAK_HOUR_ADJUSTMENT or float(peak_hour_adjustment) > MAX_PEAK_HOUR_ADJUSTMENT:
                return {"error": "Peak hour adjustment must be between 1.0 and 3.0"}

            i += 1

    if start_node == end_node:
        return [start_node]

    MIN_REL = Decimal(str(min_reliability)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ROB_WT = Decimal(str(robustness_weight)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    labels = {}
    keys = list(graph.keys())
    idx = 0
    while idx < len(keys):
        labels[keys[idx]] = []
        idx += 1

    start_label = {"node": start_node, "cost": _RobustPathUtils.quantize2(0), "rob": _RobustPathUtils.quantize2(0), "prev": None, "prev_node": None}
    labels[start_node].append(start_label)

    counter = 0
    pq = []
    heapq.heappush(pq, [_RobustPathUtils.quantize2(0), counter, start_label])
    counter += 1

    # Track visited nodes to avoid reprocessing dominated labels
    visited = {}
    for k in graph.keys():
        visited[k] = set()

    while len(pq) > 0:
        item = heapq.heappop(pq)
        current_label = item[2]
        current_node = current_label["node"]
        current_cost = current_label["cost"]
        current_rob = current_label["rob"]

        # Create a signature for this label to track if we've processed similar state
        label_sig = (current_cost, current_rob)
        if label_sig in visited[current_node]:
            continue
        visited[current_node].add(label_sig)

        # Don't expand from end_node - we've reached destination
        if current_node == end_node:
            continue

        neighbors = graph[current_node]
        t = 0
        while t < len(neighbors):
            edge = neighbors[t]
            v = edge[0]

            if _RobustPathUtils.appears_in_chain(current_label, v):
                t += 1
                continue

            new_cost = _RobustPathUtils.quantize2(current_cost + _RobustPathUtils.effective_cost(edge, is_peak_hour))
            new_rob = _RobustPathUtils.quantize2(current_rob + _RobustPathUtils.robustness_gain(edge, ROB_WT))
            new_label = {"node": v, "cost": new_cost, "rob": new_rob, "prev": current_label, "prev_node": current_node}

            existing = labels[v]
            if _RobustPathUtils.is_dominated(new_label, existing):
                t += 1
                continue
            labels[v] = _RobustPathUtils.prune_with(new_label, existing)
            labels[v].append(new_label)

            heapq.heappush(pq, [new_cost, counter, new_label])
            counter += 1
            t += 1

    # After exploring all paths, find the best solution at end_node
    # Filter paths by robustness >= min_reliability, then select minimum cost
    end_labels = labels[end_node]
    u = 0
    best_solution_label = None
    while u < len(end_labels):
        lab = end_labels[u]
        if lab["rob"] >= MIN_REL:
            if best_solution_label is None or lab["cost"] < best_solution_label["cost"]:
                best_solution_label = lab
        u += 1

    if best_solution_label is None:
        return []

    path_rev = []
    cur = best_solution_label
    while cur is not None:
        path_rev.append(cur["node"])
        cur = cur["prev"]
    path = []
    i = len(path_rev) - 1
    while i >= 0:
        path.append(path_rev[i])
        i -= 1

    return path


if __name__ == "__main__":
    graph = {
        "0": [["1", 10, 1.2, 0.8, 1.5], ["2", 15, 1.0, 0.9, 1.2]],
        "1": [["0", 10, 1.2, 0.8, 1.5], ["2", 8, 1.5, 0.7, 1.8], ["3", 12, 1.1, 0.85, 1.3]],
        "2": [["0", 15, 1.0, 0.9, 1.2], ["1", 8, 1.5, 0.7, 1.8], ["3", 6, 1.3, 0.75, 1.6]],
        "3": [["1", 12, 1.1, 0.85, 1.3], ["2", 6, 1.3, 0.75, 1.6]]
    }
    start_node = "0"
    end_node = "3"
    is_peak_hour = True
    min_reliability = 0.75
    robustness_weight = 1.2
    print(robust_shortest_path(graph, start_node, end_node, is_peak_hour, min_reliability, robustness_weight))