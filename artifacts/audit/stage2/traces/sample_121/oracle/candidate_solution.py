# main.py
from typing import List, Dict, Tuple, Set, Any


class UnionFind:
    """
    Efficient Union-Find data structure with path compression and union by rank.
    Used for cycle detection in MST construction.
    """

    def __init__(self, n: int) -> None:
        """Initialize Union-Find for n nodes."""
        self.parent = list(range(n))
        self.rank = [0] * n
        self.components = n

    def find(self, x: int) -> int:
        """Find the root of x with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """Union two sets by rank. Returns True if successful, False if already connected."""
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x == root_y:
            return False

        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1

        self.components -= 1
        return True


class CapacityValidator:
    """
    Validates capacity constraints across multiple phases for MST edges.
    Tracks cumulative loads and ensures no edge exceeds its capacity in any phase.
    """

    def __init__(self, graph: List[Tuple], data_loads: Dict[Tuple[Tuple[int, int], str], int]) -> None:
        """
        Initialize capacity validator.

        Args:
            graph: List of edges with capacity maps
            data_loads: Dictionary of loads per edge per phase
        """
        self.graph = graph
        self.data_loads = data_loads

        # Build edge index for fast lookup
        self.edge_index = {}
        for idx, edge in enumerate(graph):
            start, end, cost, capacity_map = edge
            # Store bidirectional mapping
            key1 = (min(start, end), max(start, end))
            self.edge_index[key1] = (idx, capacity_map)

        # Extract all phases from capacity maps
        self.phases = set()
        for edge in graph:
            _, _, _, capacity_map = edge
            self.phases.update(capacity_map.keys())

    def validate_edge(self, start: int, end: int) -> bool:
        """
        Check if an edge can handle all its loads across all phases.

        Args:
            start: Starting node
            end: Ending node

        Returns:
            True if edge satisfies all capacity constraints, False otherwise
        """
        edge_key = (min(start, end), max(start, end))

        if edge_key not in self.edge_index:
            return False

        idx, capacity_map = self.edge_index[edge_key]

        # Check each phase
        for phase in self.phases:
            if phase not in capacity_map:
                # Edge doesn't support this phase
                return False

            capacity = capacity_map[phase]
            total_load = 0

            # Sum all loads for this edge in this phase
            # Check both directions
            for (u, v) in [(start, end), (end, start)]:
                load_key = ((u, v), phase)
                if load_key in self.data_loads:
                    total_load += self.data_loads[load_key]

            # Validate capacity
            if total_load > capacity:
                return False

        return True

    def filter_valid_edges(self, edges: List[Tuple]) -> List[Tuple]:
        """
        Filter a list of edges to only include those satisfying capacity constraints.

        Args:
            edges: List of (start, end, cost, capacity_map) tuples

        Returns:
            List of valid edges that meet all capacity requirements
        """
        valid_edges = []
        for edge in edges:
            start, end, _, _ = edge
            if self.validate_edge(start, end):
                valid_edges.append(edge)
        return valid_edges


def compute_mst_with_capacity_internal(graph: List[Tuple], data_loads: Dict[Tuple[Tuple[int, int], str], int]) -> List[Tuple[int, int, float]]:
    """
    Internal computation function using native Python types.

    Args:
        graph: List of (start, end, cost, capacity_map) tuples
        data_loads: Dict mapping ((u, v), phase) to load value

    Returns:
        List of (start, end, cost) tuples representing the MST
    """
    if not graph:
        return []

    # Find number of nodes
    nodes = set()
    for start, end, _, _ in graph:
        nodes.add(start)
        nodes.add(end)

    if not nodes:
        return []

    n = max(nodes) + 1

    # Initialize capacity validator
    validator = CapacityValidator(graph, data_loads)

    # Filter edges that satisfy capacity constraints
    valid_edges = validator.filter_valid_edges(graph)

    if not valid_edges:
        return []

    # Sort edges by cost (Kruskal's algorithm)
    valid_edges.sort(key=lambda x: x[2])

    # Initialize Union-Find
    uf = UnionFind(n)

    # Build MST
    mst = []
    for start, end, cost, _ in valid_edges:
        if uf.union(start, end):
            mst.append((start, end, cost))

            # Early termination if we have enough edges
            if len(mst) == len(nodes) - 1:
                break

    return mst


def _compute_capacity_analysis(mst: List[Tuple[int, int, float]], graph: List[Tuple],
                               data_loads: Dict[Tuple[Tuple[int, int], str], int]) -> Dict[str, Any]:
    """
    Analyze capacity utilization across all MST edges and phases.

    Returns metrics about how efficiently capacity is being used.
    """
    if not mst:
        return {
            "average_utilization": 0.0,
            "max_utilization": 0.0,
            "min_utilization": 0.0,
            "bottleneck_edges": [],
            "underutilized_edges": []
        }

    # Build edge lookup
    edge_map = {}
    for start, end, cost, capacity_map in graph:
        key = (min(start, end), max(start, end))
        edge_map[key] = (cost, capacity_map)

    utilizations = []
    bottleneck_edges = []  # Utilization > 80%
    underutilized_edges = []  # Utilization < 30%

    for start, end, cost in mst:
        edge_key = (min(start, end), max(start, end))
        if edge_key not in edge_map:
            continue

        _, capacity_map = edge_map[edge_key]

        # Calculate utilization for each phase
        phase_utilizations = []
        for phase, capacity in capacity_map.items():
            total_load = 0
            for (u, v) in [(start, end), (end, start)]:
                load_key = ((u, v), phase)
                if load_key in data_loads:
                    total_load += data_loads[load_key]

            if capacity > 0:
                utilization = (total_load / capacity) * 100
                phase_utilizations.append(utilization)

        if phase_utilizations:
            avg_util = sum(phase_utilizations) / len(phase_utilizations)
            max_util = max(phase_utilizations)
            utilizations.append(avg_util)

            if max_util > 80:
                bottleneck_edges.append([start, end, round(max_util, 2)])
            if avg_util < 30:
                underutilized_edges.append([start, end, round(avg_util, 2)])

    avg_utilization = sum(utilizations) / len(utilizations) if utilizations else 0

    return {
        "average_utilization": round(avg_utilization, 2),
        "max_utilization": round(max(utilizations), 2) if utilizations else 0.0,
        "min_utilization": round(min(utilizations), 2) if utilizations else 0.0,
        "bottleneck_edges": bottleneck_edges,
        "underutilized_edges": underutilized_edges
    }


def _compute_graph_metrics(mst: List[Tuple[int, int, float]], graph: List[Tuple],
                           nodes: Set[int]) -> Dict[str, Any]:
    """
    Compute topological and efficiency metrics for the MST.
    """
    if not mst or not nodes:
        return {
            "node_count": 0,
            "density": 0.0,
            "cost_savings": 0.0,
            "pruned_edges": 0,
            "average_degree": 0.0
        }

    n = len(nodes)

    # Calculate degree distribution
    degree = {node: 0 for node in nodes}
    for start, end, _ in mst:
        degree[start] = degree.get(start, 0) + 1
        degree[end] = degree.get(end, 0) + 1

    avg_degree = sum(degree.values()) / len(degree) if degree else 0

    # Calculate cost savings (vs using all edges)
    total_graph_cost = sum(cost for _, _, cost, _ in graph)
    mst_cost = sum(cost for _, _, cost in mst)
    cost_savings = ((total_graph_cost - mst_cost) / total_graph_cost * 100) if total_graph_cost > 0 else 0

    # Calculate graph density (actual edges / possible edges)
    max_edges = n * (n - 1) // 2 if n > 1 else 0
    density = (len(mst) / max_edges * 100) if max_edges > 0 else 0

    pruned_edges = len(graph) - len(mst)

    return {
        "node_count": n,
        "density": round(density, 2),
        "cost_savings_percent": round(cost_savings, 2),
        "pruned_edges": pruned_edges,
        "average_degree": round(avg_degree, 2),
        "max_degree": max(degree.values()) if degree else 0,
        "min_degree": min(degree.values()) if degree else 0
    }


def _compute_phase_analysis(mst: List[Tuple[int, int, float]], graph: List[Tuple],
                            data_loads: Dict[Tuple[Tuple[int, int], str], int]) -> Dict[str, Any]:
    """
    Analyze load distribution and constraints across different phases.
    """
    # Extract all phases
    phases = set()
    for _, _, _, capacity_map in graph:
        phases.update(capacity_map.keys())

    if not phases or not mst:
        return {
            "phases": [],
            "total_phases": 0,
            "critical_phase": None
        }

    # Build edge lookup
    edge_map = {}
    for start, end, cost, capacity_map in graph:
        key = (min(start, end), max(start, end))
        edge_map[key] = capacity_map

    phase_stats = {}
    for phase in phases:
        total_load = 0
        total_capacity = 0
        edge_count = 0

        for start, end, _ in mst:
            edge_key = (min(start, end), max(start, end))
            if edge_key not in edge_map:
                continue

            capacity_map = edge_map[edge_key]
            if phase not in capacity_map:
                continue

            capacity = capacity_map[phase]
            total_capacity += capacity
            edge_count += 1

            # Sum loads for this edge in this phase
            for (u, v) in [(start, end), (end, start)]:
                load_key = ((u, v), phase)
                if load_key in data_loads:
                    total_load += data_loads[load_key]

        utilization = (total_load / total_capacity * 100) if total_capacity > 0 else 0
        phase_stats[phase] = {
            "total_load": total_load,
            "total_capacity": total_capacity,
            "utilization": round(utilization, 2),
            "edge_count": edge_count
        }

    # Find critical phase (highest utilization)
    critical_phase = None
    max_util = 0
    for phase, stats in phase_stats.items():
        if stats["utilization"] > max_util:
            max_util = stats["utilization"]
            critical_phase = phase

    return {
        "phases": sorted(list(phases)),
        "total_phases": len(phases),
        "critical_phase": critical_phase,
        "phase_details": phase_stats
    }


def _compute_edge_efficiency(mst: List[Tuple[int, int, float]], graph: List[Tuple],
                             data_loads: Dict[Tuple[Tuple[int, int], str], int]) -> Dict[str, Any]:
    """
    Calculate efficiency metrics for each edge in the MST.

    Efficiency is measured as: (total_load / cost) across all phases
    Higher values indicate better cost-effectiveness.
    """
    if not mst:
        return {
            "most_efficient_edge": None,
            "least_efficient_edge": None,
            "average_efficiency": 0.0
        }

    # Build edge lookup
    edge_map = {}
    for start, end, cost, capacity_map in graph:
        key = (min(start, end), max(start, end))
        edge_map[key] = capacity_map

    efficiencies = []

    for start, end, cost in mst:
        edge_key = (min(start, end), max(start, end))
        if edge_key not in edge_map:
            continue

        capacity_map = edge_map[edge_key]

        # Calculate total load across all phases
        total_load = 0
        for phase in capacity_map.keys():
            for (u, v) in [(start, end), (end, start)]:
                load_key = ((u, v), phase)
                if load_key in data_loads:
                    total_load += data_loads[load_key]

        # Efficiency: load per unit cost
        efficiency = total_load / cost if cost > 0 else 0
        efficiencies.append({
            "edge": [start, end],
            "cost": cost,
            "total_load": total_load,
            "efficiency": round(efficiency, 2)
        })

    if not efficiencies:
        return {
            "most_efficient_edge": None,
            "least_efficient_edge": None,
            "average_efficiency": 0.0
        }

    # Sort by efficiency
    sorted_eff = sorted(efficiencies, key=lambda x: x["efficiency"], reverse=True)
    avg_eff = sum(e["efficiency"] for e in efficiencies) / len(efficiencies)

    return {
        "most_efficient_edge": sorted_eff[0],
        "least_efficient_edge": sorted_eff[-1],
        "average_efficiency": round(avg_eff, 2),
        "all_edges": sorted_eff
    }


def compute_mst_with_capacity(graph: List[List], data_loads: Dict[str, int]) -> Dict[str, Any]:
    """
    Main entry point: Compute a spanning structure that minimizes cost while
    adhering to multi-phase capacity constraints.

    Args:
        graph: List of lists [start_node, end_node, base_cost, capacity_map]
               where capacity_map is a dict with string keys
        data_loads: Dict mapping "u,v,phase" strings to load values

    Returns:
        Dictionary containing:
            - "mst": List of edges [start, end, cost]
            - "total_cost": Total cost of the MST
            - "edge_count": Number of edges in the MST
            - "valid": Whether the solution is valid
            - "capacity_analysis": Detailed capacity utilization metrics
            - "graph_metrics": Graph topology and efficiency metrics
            - "phase_analysis": Per-phase load distribution
    """
    # Validate input
    if not isinstance(graph, list):
        return {"error": "Graph must be a list of edges."}
    if not isinstance(data_loads, dict):
        return {"error": "Data loads must be a dictionary."}

    # Validate edge structure
    for edge in graph:
        if not isinstance(edge, list) or len(edge) != 4:
            return {"error": "Each edge must be a list of [start, end, cost, capacity_map]."}
        if not isinstance(edge[2], (int, float)):
            return {"error": "Edge cost must be a number."}
        if not isinstance(edge[3], dict):
            return {"error": "Edge capacity_map must be a dictionary."}

    # Convert input to internal format
    internal_graph = []
    for edge in graph:
        start, end, cost, capacity_map = edge
        internal_graph.append((start, end, cost, capacity_map))

    # Convert data_loads to internal format
    internal_loads = {}
    for key, value in data_loads.items():
        # Parse key format: "u,v,phase"
        parts = key.split(',')
        if len(parts) >= 3:
            u = int(parts[0])
            v = int(parts[1])
            phase = ','.join(parts[2:])  # Handle phases with commas
            internal_loads[((u, v), phase)] = value

    # Compute MST
    mst = compute_mst_with_capacity_internal(internal_graph, internal_loads)

    # Convert output
    mst_output = [[start, end, cost] for start, end, cost in mst]
    total_cost = sum(cost for _, _, cost in mst)

    # Determine validity
    nodes = set()
    for edge in graph:
        nodes.add(edge[0])
        nodes.add(edge[1])

    expected_edges = len(nodes) - 1 if nodes else 0
    is_valid = len(mst) == expected_edges and expected_edges > 0

    # Advanced Analysis: Compute additional metrics
    capacity_analysis = _compute_capacity_analysis(mst, internal_graph, internal_loads)
    graph_metrics = _compute_graph_metrics(mst, internal_graph, nodes)
    phase_analysis = _compute_phase_analysis(mst, internal_graph, internal_loads)
    edge_efficiency = _compute_edge_efficiency(mst, internal_graph, internal_loads)

    return {
        "mst": mst_output,
        "total_cost": total_cost,
        "edge_count": len(mst),
        "valid": is_valid,
        "capacity_analysis": capacity_analysis,
        "graph_metrics": graph_metrics,
        "phase_analysis": phase_analysis,
        "edge_efficiency": edge_efficiency
    }


# Example usage
if __name__ == "__main__":
    graph = [
        [0, 1, 5,  {'day': 100, 'night': 80}],
        [1, 2, 8,  {'day': 60,  'night': 120}],
        [2, 3, 14, {'day': 200, 'night': 150}],
        [3, 0, 20, {'day': 50,  'night': 50}],
        [1, 3, 18, {'day': 70,  'night': 110}]
    ]

    data_loads = {
        "0,1,day": 60,
        "0,1,night": 80,
        "1,2,day": 50,
        "1,2,night": 120,
        "2,3,day": 100,
        "2,3,night": 140,
        "0,3,day": 10,
        "0,3,night": 30,
        "1,3,day": 60,
        "1,3,night": 70
    }

    result = compute_mst_with_capacity(graph, data_loads)
    print(result)