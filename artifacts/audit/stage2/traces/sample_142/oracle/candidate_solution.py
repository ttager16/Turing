import logging
from typing import Dict, List
from collections import defaultdict
import heapq

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def compute_secure_shortest_path(
    graph: Dict[str, List[int]], 
    start: int, 
    end: int, 
    min_security_level: int
) -> List[int]:
    """
    Compute the shortest path from start to end that satisfies minimum security constraints.
    
    Args:
        graph: Dictionary mapping edge strings "u,v" to [travel_cost, security_rating] lists
        start: Starting node ID
        end: Destination node ID
        min_security_level: Minimum security level required for edges (1-10)
    
    Returns:
        List of node IDs representing the shortest secure path, or empty list if no path exists
    """
    # Handle case where start equals end
    if start == end:
        logger.info(f"Start and end are the same: {start}")
        return [start]
    
    # Build adjacency list with only edges meeting security requirement
    adjacency_list = defaultdict(list)
    for edge_key, edge_value in graph.items():
        # Parse edge key: must be "u,v" string format for JSON compatibility
        if not isinstance(edge_key, str):
            logger.warning(f"Edge key must be a string, got {type(edge_key)}, skipping")
            continue
        
        parts = edge_key.split(',')
        if len(parts) != 2:
            logger.warning(f"Invalid edge key format: {edge_key}, expected 'u,v' format, skipping")
            continue
        
        try:
            u = int(parts[0])
            v = int(parts[1])
        except ValueError:
            logger.warning(f"Invalid node IDs in edge key: {edge_key}, skipping")
            continue
        
        # Parse edge value: must be [cost, security] list format for JSON compatibility
        if not isinstance(edge_value, list) or len(edge_value) < 2:
            logger.warning(f"Edge value must be a list [cost, security], got {edge_value}, skipping")
            continue
        
        try:
            cost = int(edge_value[0])
            security = int(edge_value[1])
        except (ValueError, TypeError):
            logger.warning(f"Invalid edge value format: {edge_value}, skipping")
            continue
        
        if security >= min_security_level:
            adjacency_list[u].append((v, cost))
            logger.debug(f"Edge ({u}, {v}) has security {security} >= {min_security_level}, added")
        else:
            logger.debug(f"Edge ({u}, {v}) has security {security} < {min_security_level}, skipped")
    
    # Check if start node has any outgoing edges
    if start not in adjacency_list:
        logger.warning(f"Start node {start} has no valid outgoing edges")
        return []
    
    # Use Dijkstra's algorithm to find shortest path
    # Priority queue: (total_cost, current_node, path)
    priority_queue = [(0, start, [start])]
    visited = set()
    
    while priority_queue:
        current_cost, current_node, path = heapq.heappop(priority_queue)
        
        # Skip if already visited with a shorter path
        if current_node in visited:
            continue
        
        visited.add(current_node)
        
        # If reached destination, return the path
        if current_node == end:
            logger.info(f"Found path from {start} to {end}: {path} with cost {current_cost}")
            return path
        
        # Explore neighbors
        if current_node in adjacency_list:
            for neighbor, edge_cost in adjacency_list[current_node]:
                if neighbor not in visited:
                    new_cost = current_cost + edge_cost
                    new_path = path + [neighbor]
                    heapq.heappush(priority_queue, (new_cost, neighbor, new_path))
                    logger.debug(f"Exploring edge ({current_node}, {neighbor}) with cost {edge_cost}, total cost {new_cost}")
    
    # No path found
    logger.warning(f"No path found from {start} to {end} with security >= {min_security_level}")
    return []