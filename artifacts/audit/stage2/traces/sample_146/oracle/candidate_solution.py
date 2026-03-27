# main.py
from collections import deque, Counter


def adaptive_topological_sort(graph_input: dict) -> dict:
    """
    Perform adaptive topological sorting with cycle detection and analytics.

    Parameters:
        graph_input (dict): A dictionary containing:
            - "deliveries": List[str] -> unique delivery identifiers.
            - "constraints": List[List[str]] -> each element is [predecessor, successor].
            - "new_constraints" (optional): List[List[str]] -> new constraints to insert dynamically.

    Returns:
        dict: A dictionary containing:
            - "sorted_deliveries": List[str] -> valid topological order, or empty if cycle detected.
            - "has_cycle": bool -> whether a cycle was found.
            - "cycle_nodes": List[str] -> nodes involved in a detected cycle.
            - "dependency_metrics": dict -> includes:
                - "in_degree": dict[str, int]
                - "out_degree": dict[str, int]
                - "depth_levels": dict[str, int]
                - "independent_clusters": int
            - "graph_statistics": dict -> includes:
                - "total_nodes": int
                - "total_edges": int
                - "average_in_degree": float
                - "average_out_degree": float
                - "max_depth": int
                - "density": float
                - "critical_path_count": int
                - "degree_centralization": float
                - "source_ratio": float
                - "sink_ratio": float
                - "betweenness_centrality": dict -> {"average": float, "max_node": str, "max_score": float}
                - "pagerank": dict -> {"average": float, "top_nodes": List[List]}
                - "longest_path_length": int
                - "width_metrics": dict -> {"max_width": int, "average_width": float, "level_distribution": dict[str, int]}
                - "transitive_reduction_ratio": float
                - "fan_metrics": dict -> {"max_fan_in": int, "max_fan_out": int, "median_fan_in": int, "median_fan_out": int}
                - "bottleneck_count": int
                - "bottleneck_nodes": List[str]
                - "clustering_coefficient": float
                - "degree_variance": float
                - "parallelization_factor": float
            - "update_log": List[dict] -> chronological log of inserted constraints and resulting actions.
            - "errors": List[str] -> validation errors (only when success is False).
    """
    # Extract input data
    deliveries = graph_input.get("deliveries", [])
    constraints = graph_input.get("constraints", [])
    new_constraints = graph_input.get("new_constraints", [])

    # Validate input data
    validation_results = _validate_input(deliveries, constraints, new_constraints)
    if not validation_results["is_valid"]:
        return {
            "success": False,
            "errors": validation_results["errors"]
        }

    # Build adjacency list and track all constraints
    all_constraints = list(constraints)
    update_log = []

    # Process new constraints dynamically
    for new_constraint in new_constraints:
        if len(new_constraint) == 2:
            all_constraints.append(new_constraint)

    # Build graph representation
    graph = _build_graph(deliveries, all_constraints)

    # Detect cycles first
    has_cycle, cycle_nodes = _detect_cycle(graph, deliveries)

    # Perform topological sort
    sorted_deliveries = []
    if not has_cycle:
        sorted_deliveries = _topological_sort_kahns(graph, deliveries)

    # Compute dependency metrics
    dependency_metrics = _compute_dependency_metrics(graph, deliveries)

    # Compute graph statistics
    graph_statistics = _compute_graph_statistics(graph, deliveries, dependency_metrics)

    # Build update log for new constraints
    for new_constraint in new_constraints:
        if len(new_constraint) == 2:
            log_entry = {
                "action": "insert_constraint",
                "constraint": new_constraint,
                "result": "reordered successfully" if not has_cycle else "cycle detected",
                "cycle_detected": has_cycle
            }
            update_log.append(log_entry)

    # Return comprehensive results
    return {
        "success": True,
        "sorted_deliveries": sorted_deliveries,
        "has_cycle": has_cycle,
        "cycle_nodes": cycle_nodes,
        "dependency_metrics": dependency_metrics,
        "graph_statistics": graph_statistics,
        "update_log": update_log
    }


def _validate_input(deliveries: list, constraints: list, new_constraints: list) -> dict:
    """
    Validate input data for correctness.

    Args:
        deliveries: List of all node identifiers
        constraints: List of [predecessor, successor] pairs
        new_constraints: List of new [predecessor, successor] pairs to insert

    Returns:
        dict: Validation results including errors if any
    """
    errors = []

    # Check if deliveries is empty
    if not deliveries:
        errors.append("Deliveries list cannot be empty.")
        return {"is_valid": False, "errors": errors}

    # Check for duplicates in deliveries
    if len(deliveries) != len(set(deliveries)):
        duplicates = [d for d in set(deliveries) if deliveries.count(d) > 1]
        errors.append(f"Duplicate deliveries found: {duplicates}")

    # Check for None values in deliveries
    if None in deliveries:
        errors.append("Deliveries list contains None values.")

    delivery_set = set(deliveries)

    # Validate constraints
    all_constraints_list = list(constraints) + list(new_constraints)
    seen_constraints = set()

    for constraint in all_constraints_list:
        if len(constraint) != 2:
            errors.append(f"Constraint {constraint} does not have exactly two elements.")
            continue

        predecessor, successor = constraint

        # Check for self-loops
        if predecessor == successor:
            errors.append(f"Self-loop detected: {constraint}")

        # Check if nodes exist in deliveries
        if predecessor not in delivery_set:
            errors.append(f"Predecessor '{predecessor}' not in deliveries.")
        if successor not in delivery_set:
            errors.append(f"Successor '{successor}' not in deliveries.")

        # Check for duplicate constraints
        constraint_tuple = (predecessor, successor)
        if constraint_tuple in seen_constraints:
            errors.append(f"Duplicate constraint: {constraint}")
        seen_constraints.add(constraint_tuple)

    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }


def _build_graph(deliveries: list, constraints: list) -> dict:
    """
    Build adjacency list representation of the graph.

    Args:
        deliveries: List of all node identifiers
        constraints: List of [predecessor, successor] pairs

    Returns:
        dict: Graph representation with adjacency lists and reverse adjacency lists
    """
    adj_list = {node: [] for node in deliveries}
    reverse_adj_list = {node: [] for node in deliveries}

    for constraint in constraints:
        if len(constraint) == 2:
            predecessor, successor = constraint
            if predecessor in adj_list and successor in adj_list:
                adj_list[predecessor].append(successor)
                reverse_adj_list[successor].append(predecessor)

    return {
        "adj_list": adj_list,
        "reverse_adj_list": reverse_adj_list,
        "nodes": deliveries,
        "edges": constraints
    }


def _detect_cycle(graph: dict, deliveries: list) -> tuple:
    """
    Detect cycles using depth-first search with color-based tracking.

    Args:
        graph: Graph representation
        deliveries: List of all nodes

    Returns:
        tuple: (has_cycle: bool, cycle_nodes: list)
    """
    adj_list = graph["adj_list"]

    # Color states: 0 = white (unvisited), 1 = gray (visiting), 2 = black (visited)
    color = {node: 0 for node in deliveries}
    parent = {node: None for node in deliveries}
    cycle_nodes = []

    def dfs_visit(node, path):
        """DFS visit with cycle detection."""
        nonlocal cycle_nodes

        if cycle_nodes:  # Cycle already found
            return

        color[node] = 1  # Mark as visiting (gray)
        path.append(node)

        for neighbor in adj_list[node]:
            if color[neighbor] == 1:  # Back edge found - cycle detected
                # Extract cycle nodes from path
                if neighbor in path:
                    cycle_start_idx = path.index(neighbor)
                    cycle_nodes = sorted(list(set(path[cycle_start_idx:] + [neighbor])))
                return
            elif color[neighbor] == 0:  # Unvisited
                parent[neighbor] = node
                dfs_visit(neighbor, path)
                if cycle_nodes:  # Propagate cycle detection
                    return

        color[node] = 2  # Mark as visited (black)
        path.pop()  # Backtrack

    # Visit all nodes
    for node in deliveries:
        if color[node] == 0 and not cycle_nodes:
            dfs_visit(node, [])

    has_cycle = len(cycle_nodes) > 0
    return has_cycle, cycle_nodes


def _topological_sort_kahns(graph: dict, deliveries: list) -> list:
    """
    Perform topological sort using Kahn's algorithm (BFS-based).

    Args:
        graph: Graph representation
        deliveries: List of all nodes

    Returns:
        list: Topologically sorted list of nodes
    """
    adj_list = graph["adj_list"]
    reverse_adj_list = graph["reverse_adj_list"]

    # Calculate in-degrees
    in_degree = {node: len(reverse_adj_list[node]) for node in deliveries}

    # Initialize queue with nodes having zero in-degree
    queue = deque([node for node in deliveries if in_degree[node] == 0])

    # Sort queue for determinism
    queue = deque(sorted(queue))

    sorted_list = []

    while queue:
        # Process nodes in deterministic order
        current = queue.popleft()
        sorted_list.append(current)

        # Reduce in-degree of neighbors
        neighbors_to_add = []
        for neighbor in adj_list[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                neighbors_to_add.append(neighbor)

        # Add new zero in-degree nodes in sorted order for determinism
        for neighbor in sorted(neighbors_to_add):
            queue.append(neighbor)

    return sorted_list


def _compute_dependency_metrics(graph: dict, deliveries: list) -> dict:
    """
    Compute comprehensive dependency metrics.

    Args:
        graph: Graph representation
        deliveries: List of all nodes

    Returns:
        dict: Dependency metrics including degrees, depth levels, and clusters
    """
    adj_list = graph["adj_list"]
    reverse_adj_list = graph["reverse_adj_list"]

    # Compute in-degree and out-degree
    in_degree = {node: len(reverse_adj_list[node]) for node in deliveries}
    out_degree = {node: len(adj_list[node]) for node in deliveries}

    # Compute depth levels using BFS from nodes with zero in-degree
    depth_levels = _compute_depth_levels(graph, deliveries)

    # Compute independent clusters using union-find
    independent_clusters = _compute_independent_clusters(graph, deliveries)

    return {
        "in_degree": in_degree,
        "out_degree": out_degree,
        "depth_levels": depth_levels,
        "independent_clusters": independent_clusters
    }


def _compute_depth_levels(graph: dict, deliveries: list) -> dict:
    """
    Compute depth level for each node using BFS layering.

    Args:
        graph: Graph representation
        deliveries: List of all nodes

    Returns:
        dict: Mapping of node to depth level
    """
    adj_list = graph["adj_list"]
    reverse_adj_list = graph["reverse_adj_list"]

    depth = {node: -1 for node in deliveries}

    # Find all source nodes (zero in-degree)
    sources = [node for node in deliveries if len(reverse_adj_list[node]) == 0]

    # BFS from all sources simultaneously
    queue = deque([(node, 0) for node in sorted(sources)])

    while queue:
        current, level = queue.popleft()

        # Update depth if this is a longer path
        if depth[current] < level:
            depth[current] = level

            # Add neighbors with updated depth
            for neighbor in sorted(adj_list[current]):
                queue.append((neighbor, level + 1))

    # Nodes with no path from any source get depth 0
    for node in deliveries:
        if depth[node] == -1:
            depth[node] = 0

    return depth


def _compute_independent_clusters(graph: dict, deliveries: list) -> int:
    """
    Compute number of independent clusters using union-find on undirected version.

    Args:
        graph: Graph representation
        deliveries: List of all nodes

    Returns:
        int: Number of independent connected components
    """
    adj_list = graph["adj_list"]

    # Build undirected adjacency list
    undirected_adj = {node: set() for node in deliveries}
    for node in deliveries:
        for neighbor in adj_list[node]:
            undirected_adj[node].add(neighbor)
            undirected_adj[neighbor].add(node)

    # Find connected components using BFS
    visited = set()
    clusters = 0

    for node in deliveries:
        if node not in visited:
            clusters += 1
            # BFS to mark all nodes in this component
            queue = deque([node])
            visited.add(node)

            while queue:
                current = queue.popleft()
                for neighbor in undirected_adj[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

    return clusters


def _compute_graph_statistics(graph: dict, deliveries: list, dependency_metrics: dict) -> dict:
    """
    Compute overall graph statistics.

    Args:
        graph: Graph representation
        deliveries: List of all nodes
        dependency_metrics: Previously computed metrics

    Returns:
        dict: Graph statistics
    """
    total_nodes = len(deliveries)

    # Count total edges (avoid duplicates)
    edges_set = set()
    for constraint in graph["edges"]:
        if len(constraint) == 2:
            edges_set.add(tuple(constraint))
    total_edges = len(edges_set)

    # Calculate averages
    in_degrees = list(dependency_metrics["in_degree"].values())
    out_degrees = list(dependency_metrics["out_degree"].values())

    average_in_degree = sum(in_degrees) / total_nodes if total_nodes > 0 else 0.0
    average_out_degree = sum(out_degrees) / total_nodes if total_nodes > 0 else 0.0

    # Calculate max depth
    depth_levels = dependency_metrics["depth_levels"]
    max_depth = max(depth_levels.values()) if depth_levels else 0

    # Graph Density
    # Density = actual_edges / possible_edges (for directed graph)
    # Ranges from 0 (no edges) to 1 (complete graph)
    max_possible_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 0
    density = total_edges / max_possible_edges if max_possible_edges > 0 else 0.0

    # Critical Path Nodes
    # Nodes that lie on the longest path (have max_depth)
    critical_path_nodes = [node for node, depth in depth_levels.items() if depth == max_depth]
    critical_path_count = len(critical_path_nodes)

    # Degree Centralization
    # Measures how much the graph depends on central hub nodes
    total_degrees = [in_deg + out_deg for in_deg, out_deg in zip(in_degrees, out_degrees)]
    if total_degrees and total_nodes > 1:
        max_degree = max(total_degrees)
        sum_differences = sum(max_degree - deg for deg in total_degrees)
        max_possible_sum = (total_nodes - 1) * (2 * (total_nodes - 1))
        degree_centralization = sum_differences / max_possible_sum if max_possible_sum > 0 else 0.0
    else:
        degree_centralization = 0.0

    # Proportion of nodes that are sources (in-degree=0) or sinks (out-degree=0)
    source_nodes = sum(1 for deg in in_degrees if deg == 0)
    sink_nodes = sum(1 for deg in out_degrees if deg == 0)
    source_ratio = source_nodes / total_nodes if total_nodes > 0 else 0.0
    sink_ratio = sink_nodes / total_nodes if total_nodes > 0 else 0.0

    # --- ADVANCED METRICS ---

    # Betweenness Centrality (simplified version for DAGs)
    # Measures how often a node appears on shortest paths between other nodes
    betweenness_scores = _compute_betweenness_centrality(graph, deliveries)
    avg_betweenness = sum(betweenness_scores.values()) / total_nodes if total_nodes > 0 else 0.0
    max_betweenness_node = max(betweenness_scores, key=betweenness_scores.get) if betweenness_scores else None

    # PageRank-style importance score
    # Identifies critical nodes based on incoming dependencies
    pagerank_scores = _compute_pagerank(graph, deliveries, iterations=10)
    avg_pagerank = sum(pagerank_scores.values()) / total_nodes if total_nodes > 0 else 0.0

    # Round PageRank scores
    pagerank_scores = {node: round(score, 6) for node, score in pagerank_scores.items()}

    # Longest Path Length (Critical Path Length)
    longest_path_length = _compute_longest_path_length(graph, deliveries)

    # Width metrics (max number of parallel tasks at any depth level)
    width_metrics = _compute_width_metrics(depth_levels)

    # Transitive Reduction Ratio
    # Measures redundancy: ratio of edges that could be removed without changing reachability
    transitive_reduction_ratio = _compute_transitive_reduction_ratio(graph, deliveries)

    # Fan-out/Fan-in analysis
    fan_metrics = _compute_fan_metrics(in_degrees, out_degrees)

    # Bottleneck nodes (high in-degree AND high out-degree)
    bottleneck_nodes = _identify_bottlenecks(dependency_metrics["in_degree"],
                                              dependency_metrics["out_degree"])

    # Clustering coefficient (for underlying undirected graph)
    clustering_coefficient = _compute_clustering_coefficient(graph, deliveries)

    # Degree variance (indicates heterogeneity in node connectivity)
    degree_variance = _compute_degree_variance(total_degrees)

    # Parallel efficiency potential
    parallelization_factor = _compute_parallelization_factor(depth_levels, total_nodes)

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "average_in_degree": round(average_in_degree, 4),
        "average_out_degree": round(average_out_degree, 4),
        "max_depth": max_depth,
        "density": round(density, 3),
        "critical_path_count": critical_path_count,
        "degree_centralization": round(degree_centralization, 2),
        "source_ratio": round(source_ratio, 5),
        "sink_ratio": round(sink_ratio, 5),
        # Advanced metrics
        "betweenness_centrality": {
            "average": round(avg_betweenness, 4),
            "max_node": max_betweenness_node,
            "max_score": round(betweenness_scores.get(max_betweenness_node, 0.0), 4) if max_betweenness_node else 0.0
        },
        "pagerank": {
            "average": round(avg_pagerank, 6),
            "top_nodes": [[node, score] for node, score in sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)[:3]]
        },
        "longest_path_length": longest_path_length,
        "width_metrics": width_metrics,
        "transitive_reduction_ratio": round(transitive_reduction_ratio, 4),
        "fan_metrics": fan_metrics,
        "bottleneck_count": len(bottleneck_nodes),
        "bottleneck_nodes": bottleneck_nodes[:5],  # Top 5
        "clustering_coefficient": round(clustering_coefficient, 4),
        "degree_variance": round(degree_variance, 4),
        "parallelization_factor": round(parallelization_factor, 4)
    }


def _compute_betweenness_centrality(graph: dict, deliveries: list) -> dict:
    """Calculate betweenness centrality for each node."""
    from collections import defaultdict

    betweenness = {node: 0.0 for node in deliveries}
    adj_list = graph["adj_list"]

    for source in deliveries:
        # BFS to find shortest paths
        stack = []
        paths = defaultdict(list)
        path_count = {node: 0 for node in deliveries}
        path_count[source] = 1
        distance = {node: -1 for node in deliveries}
        distance[source] = 0
        queue = deque([source])

        while queue:
            current = queue.popleft()
            stack.append(current)
            for neighbor in adj_list[current]:
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[current] + 1
                if distance[neighbor] == distance[current] + 1:
                    path_count[neighbor] += path_count[current]
                    paths[neighbor].append(current)

        dependency = {node: 0.0 for node in deliveries}
        while stack:
            node = stack.pop()
            for predecessor in paths[node]:
                dependency[predecessor] += (path_count[predecessor] / path_count[node]) * (1 + dependency[node])
            if node != source:
                betweenness[node] += dependency[node]

    return betweenness


def _compute_pagerank(graph: dict, deliveries: list, iterations: int = 10, damping: float = 0.85) -> dict:
    """Calculate PageRank scores for nodes."""
    reverse_adj = graph["reverse_adj_list"]
    n = len(deliveries)
    pagerank = {node: 1.0 / n for node in deliveries}

    for _ in range(iterations):
        new_pagerank = {}
        for node in deliveries:
            rank_sum = sum(pagerank[pred] / len(graph["adj_list"][pred])
                           for pred in reverse_adj[node] if len(graph["adj_list"][pred]) > 0)
            new_pagerank[node] = (1 - damping) / n + damping * rank_sum
        pagerank = new_pagerank

    return pagerank


def _compute_longest_path_length(graph: dict, deliveries: list) -> int:
    """Calculate the length of the longest path in the DAG."""
    adj_list = graph["adj_list"]
    reverse_adj = graph["reverse_adj_list"]

    longest_path = {node: 0 for node in deliveries}
    in_degree = {node: len(reverse_adj[node]) for node in deliveries}
    queue = deque([node for node in deliveries if in_degree[node] == 0])

    while queue:
        current = queue.popleft()
        for neighbor in adj_list[current]:
            longest_path[neighbor] = max(longest_path[neighbor], longest_path[current] + 1)
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return max(longest_path.values()) if longest_path else 0


def _compute_width_metrics(depth_levels: dict) -> dict:
    """Calculate width statistics (parallelization potential)."""
    level_counts = Counter(depth_levels.values())
    max_width = max(level_counts.values()) if level_counts else 0
    avg_width = sum(level_counts.values()) / len(level_counts) if level_counts else 0.0

    return {
        "max_width": max_width,
        "average_width": round(avg_width, 2),
        "level_distribution": {str(k): v for k, v in sorted(level_counts.items())}
    }


def _compute_transitive_reduction_ratio(graph: dict, deliveries: list) -> float:
    """Calculate ratio of redundant edges (transitive edges)."""
    adj_list = graph["adj_list"]

    # Compute transitive closure using Floyd-Warshall style
    reachable = {node: set(adj_list[node]) for node in deliveries}

    for k in deliveries:
        for i in deliveries:
            if k in reachable[i]:
                reachable[i].update(reachable[k])

    # Count direct edges that are also reachable via other paths
    redundant = 0
    total = 0
    for node in deliveries:
        for neighbor in adj_list[node]:
            total += 1
            # Check if neighbor is reachable via another path
            for intermediate in adj_list[node]:
                if intermediate != neighbor and neighbor in reachable[intermediate]:
                    redundant += 1
                    break

    return redundant / total if total > 0 else 0.0


def _compute_fan_metrics(in_degrees: list, out_degrees: list) -> dict:
    """Analyze fan-in and fan-out distribution."""
    return {
        "max_fan_in": max(in_degrees) if in_degrees else 0,
        "max_fan_out": max(out_degrees) if out_degrees else 0,
        "median_fan_in": sorted(in_degrees)[len(in_degrees)//2] if in_degrees else 0,
        "median_fan_out": sorted(out_degrees)[len(out_degrees)//2] if out_degrees else 0
    }


def _identify_bottlenecks(in_degree: dict, out_degree: dict, threshold_percentile: float = 0.75) -> list:
    """Identify bottleneck nodes with high in and out degrees."""
    total_degrees = [(node, in_degree[node] + out_degree[node]) for node in in_degree]
    total_degrees.sort(key=lambda x: x[1], reverse=True)

    if not total_degrees:
        return []

    threshold = total_degrees[int(len(total_degrees) * (1 - threshold_percentile))][1]
    bottlenecks = [node for node, deg in total_degrees if deg >= threshold and
                   in_degree[node] > 0 and out_degree[node] > 0]

    return sorted(bottlenecks)


def _compute_clustering_coefficient(graph: dict, deliveries: list) -> float:
    """Calculate average clustering coefficient."""
    adj_list = graph["adj_list"]

    clustering_coeffs = []
    for node in deliveries:
        neighbors = set(adj_list[node])
        if len(neighbors) < 2:
            continue

        # Count edges between neighbors (treat as undirected)
        edges_between = 0
        for n1 in neighbors:
            for n2 in neighbors:
                if n1 != n2 and (n2 in adj_list[n1] or n1 in adj_list[n2]):
                    edges_between += 1

        max_edges = len(neighbors) * (len(neighbors) - 1)
        clustering_coeffs.append(edges_between / max_edges if max_edges > 0 else 0.0)

    return sum(clustering_coeffs) / len(clustering_coeffs) if clustering_coeffs else 0.0


def _compute_degree_variance(total_degrees: list) -> float:
    """Calculate variance in node degrees."""
    if not total_degrees:
        return 0.0

    mean = sum(total_degrees) / len(total_degrees)
    variance = sum((d - mean) ** 2 for d in total_degrees) / len(total_degrees)
    return variance


def _compute_parallelization_factor(depth_levels: dict, total_nodes: int) -> float:
    """Calculate theoretical speedup from parallelization."""
    if not depth_levels or total_nodes == 0:
        return 1.0

    max_depth = max(depth_levels.values())
    # Theoretical speedup = total_work / critical_path_length
    return total_nodes / (max_depth + 1) if max_depth >= 0 else 1.0


# Example usage
if __name__ == "__main__":
    graph_input = {
        "deliveries": ["A", "B", "C", "D", "E"],
        "constraints": [["A", "B"], ["B", "C"], ["A", "C"], ["D", "E"]],
        "new_constraints": [["C", "A"]]
    }
    result = adaptive_topological_sort(graph_input)
    print(result)