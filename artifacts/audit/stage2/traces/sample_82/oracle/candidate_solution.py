from typing import Any, Dict, List
import threading


class Node:
    """Represents a node in the adaptive sensor list."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.children = {}  # zone/type name -> Node
        self.readings = []  # List of float values
        self.lock = threading.Lock()
        
    def add_reading(self, value: float):
        """Add a reading to this node."""
        with self.lock:
            self.readings.append(value)
    
    def remove_reading_at_index(self, idx: int):
        """Remove a reading at a specific index."""
        with self.lock:
            if 0 <= idx < len(self.readings):
                self.readings.pop(idx)
    
    def get_child(self, name: str):
        """Get or create a child node."""
        with self.lock:
            if name not in self.children:
                # Construct child ID based on parent
                if self.node_id == "root":
                    child_id = f"zone:{name}"
                else:
                    child_id = f"{self.node_id}/type:{name}"
                self.children[name] = Node(child_id)
            return self.children[name]
    
    def get_sorted_children(self):
        """Return children sorted by name."""
        with self.lock:
            return sorted(self.children.items())


def build_adaptive_sensor_list(
    data_stream: List[Dict[str, Any]],
    invalidations: List[int] = []
) -> Dict[str, Any]:
    """
    Build a hierarchical, adaptive, branchable linked list with a deterministic single
    next-pointer traversal, hot-segment promotion, partial rollback, and per-segment aggregates.
    
    Returns a deterministic snapshot containing:
      - 'linked_order': List[str] of node IDs in traversal order.
      - 'next_pointer_of': Dict[str, str or None] mapping node ID -> next node ID (or None).
      - 'segment_stats': Dict[str, Dict[str, Any]] per node:
            For base type nodes: {count, sum, min, max, avg}
            For hot nodes: {latest_value}
      - 'path_index': Dict[str, str] mapping each sensor key to its base type node ID.
      - 'leaf_values': Dict[str, List[float]] final per (zone/type) values after invalidations.
    """
    
    root = Node("root")
    
    # Track which events belong to which type node for invalidation
    event_to_node = {}  # event_index -> (type_node, local_index, zone, sensor_type)
    
    # Track readings per (zone, type) for hot segment management
    zone_type_tracker = {}  # (zone, type) -> [(event_idx, value), ...]
    
    # Step 1: Process all events
    for event_idx, event in enumerate(data_stream):
        # Parse event dictionary
        sensor_key = event.get("sensor", "")
        value = event.get("value", 0.0)
        
        # Parse sensor key
        parts = sensor_key.split('_', 1)
        if len(parts) != 2:
            continue
        
        sensor_type, zone = parts
        
        # Navigate to zone node
        zone_node = root.get_child(zone)
        
        # Navigate to type node
        type_node = zone_node.get_child(sensor_type)
        
        # Track local index within this type node
        local_idx = len(type_node.readings)
        event_to_node[event_idx] = (type_node, local_idx, zone, sensor_type)
        
        # Add reading
        type_node.add_reading(value)
        
        # Track for hot segment
        key = (zone, sensor_type)
        if key not in zone_type_tracker:
            zone_type_tracker[key] = []
        zone_type_tracker[key].append((event_idx, value))
    
    # Step 2: Apply invalidations
    invalidation_set = set(invalidations)
    
    for event_idx in sorted(invalidations, reverse=True):
        if event_idx in event_to_node:
            type_node, local_idx, zone, sensor_type = event_to_node[event_idx]
            
            # Remove from type node
            if 0 <= local_idx < len(type_node.readings):
                type_node.readings.pop(local_idx)
            
            # Update all subsequent events' local indices for this type node
            for other_idx in range(event_idx + 1, len(data_stream)):
                if other_idx in event_to_node:
                    other_node, other_local, other_zone, other_type = event_to_node[other_idx]
                    if other_node == type_node and other_local > local_idx:
                        event_to_node[other_idx] = (other_node, other_local - 1, other_zone, other_type)
            
            # Remove from tracker
            key = (zone, sensor_type)
            if key in zone_type_tracker:
                zone_type_tracker[key] = [
                    (idx, val) for idx, val in zone_type_tracker[key] 
                    if idx != event_idx
                ]
    
    # Step 3: Create hot segments
    hot_segments = {}  # (zone, type) -> Node (hot segment)
    
    for (zone, sensor_type), events in zone_type_tracker.items():
        valid_events = [(idx, val) for idx, val in events if idx not in invalidation_set]
        
        if len(valid_events) >= 2:
            # Get the latest value
            latest_value = valid_events[-1][1]
            
            # Create hot segment node
            type_node_id = f"zone:{zone}/type:{sensor_type}"
            hot_node_id = f"{type_node_id}*"
            hot_node = Node(hot_node_id)
            hot_node.readings = [latest_value]
            
            hot_segments[(zone, sensor_type)] = hot_node
    
    # Step 4: Build traversal order
    def traverse(node: Node, order: List[str]):
        """Recursively traverse and build order."""
        order.append(node.node_id)
        
        # Get sorted children
        for child_name, child_node in node.get_sorted_children():
            traverse(child_node, order)
            
            # If this is a type node, check for hot segment
            if "/" in child_node.node_id and "/type:" in child_node.node_id:
                # Extract zone and type from node_id
                parts = child_node.node_id.split("/")
                zone = parts[0].replace("zone:", "")
                sensor_type = parts[1].replace("type:", "")
                
                if (zone, sensor_type) in hot_segments:
                    hot_node = hot_segments[(zone, sensor_type)]
                    order.append(hot_node.node_id)
    
    linked_order = []
    traverse(root, linked_order)
    
    # Step 5: Build next pointers
    next_pointer_of = {}
    for i in range(len(linked_order)):
        if i < len(linked_order) - 1:
            next_pointer_of[linked_order[i]] = linked_order[i + 1]
        else:
            next_pointer_of[linked_order[i]] = None
    
    # Step 6: Compute segment stats
    segment_stats = {}
    
    def compute_stats(node: Node):
        """Recursively compute stats."""
        # Only compute stats for type nodes (leaf nodes with readings)
        if "/" in node.node_id and "/type:" in node.node_id and not node.node_id.endswith("*"):
            if node.readings:
                count = len(node.readings)
                total = sum(node.readings)
                min_val = min(node.readings)
                max_val = max(node.readings)
                avg = round(total / count, 3)
                
                segment_stats[node.node_id] = {
                    "count": count,
                    "sum": total,
                    "min": min_val,
                    "max": max_val,
                    "avg": avg
                }
        
        for child_name, child_node in node.get_sorted_children():
            compute_stats(child_node)
    
    compute_stats(root)
    
    # Add hot segment stats
    for (zone, sensor_type), hot_node in hot_segments.items():
        if hot_node.readings:
            segment_stats[hot_node.node_id] = {
                "latest_value": hot_node.readings[0]
            }
    
    # Step 7: Build path index
    path_index = {}
    
    def build_path_index(node: Node):
        """Build path index for type nodes."""
        if "/" in node.node_id and "/type:" in node.node_id and not node.node_id.endswith("*"):
            # Extract zone and type
            parts = node.node_id.split("/")
            zone = parts[0].replace("zone:", "")
            sensor_type = parts[1].replace("type:", "")
            sensor_key = f"{sensor_type}_{zone}"
            path_index[sensor_key] = node.node_id
        
        for child_name, child_node in node.get_sorted_children():
            build_path_index(child_node)
    
    build_path_index(root)
    
    # Step 8: Build leaf values
    leaf_values = {}
    
    def build_leaf_values(node: Node):
        """Build leaf values for type nodes."""
        if "/" in node.node_id and "/type:" in node.node_id and not node.node_id.endswith("*"):
            if node.readings:
                leaf_values[node.node_id] = node.readings.copy()
        
        for child_name, child_node in node.get_sorted_children():
            build_leaf_values(child_node)
    
    build_leaf_values(root)
    
    return {
        "linked_order": linked_order,
        "next_pointer_of": next_pointer_of,
        "segment_stats": segment_stats,
        "path_index": path_index,
        "leaf_values": leaf_values
    }