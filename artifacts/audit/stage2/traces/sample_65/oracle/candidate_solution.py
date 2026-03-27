from typing import List, Dict

def manage_device_clusters(devices: List[List], operations: List[List]) -> List[List[int]]:
    """
    Manage IoT device clusters with dynamic state transitions and efficiency-based grouping.
    
    This function implements a distributed IoT system where devices transition between states
    (active, standby, failed) and are organized into clusters based on efficiency scores using
    Union-Find data structure with pairwise compatibility checking.
    
    Args:
        devices: List of [device_id, efficiency_score] lists
                 - device_id: unique positive integer
                 - efficiency_score: float in range [0.0, 1.0]
        
        operations: List of [operation_type, device_id] lists
                   - operation_type: 'join', 'fail', 'standby', or 'resume'
                   - device_id: target device for the operation
    
    Returns:
        List of clusters, where each cluster is a sorted list of device IDs.
        Clusters are sorted by their minimum device_id.
        Only 'active' state devices appear in output.
    
    Device States:
        - active: Device is operational and can be part of clusters
        - standby: Device is temporarily inactive (can be resumed)
        - failed: Device is permanently removed (cannot be reactivated)
    
    Clustering Rules:
        - Only 'active' devices appear in output clusters
        - Devices with efficiency ≥ 0.75 can cluster if combined avg ≥ 0.75
        - Devices with efficiency < 0.75 form individual clusters
        - Pairwise compatibility checking for optimal clustering
    
    Operations:
        - 'join': Add/activate device (creates with eff=0.80 if non-existent)
                 Cannot reactivate failed devices (failed state is permanent)
        - 'fail': Permanently remove device (irreversible)
        - 'standby': Temporarily exclude device (reversible via resume)
                    Cannot be applied to failed devices
        - 'resume': Reactivate standby device (only works on standby state)
    
    Edge Cases:
        - Only 'join' creates non-existent devices (other operations ignored)
        - Failed state is permanent - no operation can reactivate
        - Duplicate operations have no additional effect
        - Empty operations list returns clusters of all initial devices
        - All devices failed returns empty list []
    
    Algorithm:
        Uses Union-Find with path compression and union by rank for efficient
        cluster management. Implements pairwise merging based on efficiency
        compatibility to ensure optimal clustering.
    
    Time Complexity: O(n²·α(n)) where n is number of devices, α is inverse Ackermann
    Space Complexity: O(n)
    
    Example:
        >>> devices = [[1, 0.92], [2, 0.88], [3, 0.75], [4, 0.66]]
        >>> operations = [['join', 5], ['standby', 2], ['fail', 3], ['resume', 2]]
        >>> manage_device_clusters(devices, operations)
        [[1, 2, 5], [4]]
        
        Explanation:
        - Device 5 added with eff=0.80
        - Device 2 temporarily standby, then resumed
        - Device 3 permanently failed (removed)
        - High efficiency devices [1,2,5] cluster (avg=0.867 ≥ 0.75)
        - Low efficiency device 4 forms individual cluster
    """
    
    # Device state tracking
    device_efficiency: Dict[int, float] = {}
    device_state: Dict[int, str] = {}
    
    # Initialize devices from input - all start in 'active' state
    for device in devices:
        device_id, efficiency = device[0], device[1]
        device_efficiency[device_id] = efficiency
        device_state[device_id] = 'active'
    
    # Process operations sequentially
    for operation in operations:
        operation_type, device_id = operation[0], operation[1]
        
        # Device creation: ONLY 'join' creates non-existent devices
        # Other operations on non-existent devices are ignored
        if device_id not in device_efficiency:
            if operation_type == 'join':
                # Create new device with default efficiency 0.80 in active state
                device_efficiency[device_id] = 0.80
                device_state[device_id] = 'active'
            # Non-join operations on non-existent devices: no-op
            continue
        
        # Process operation based on type (device exists at this point)
        if operation_type == 'join':
            # Join activates device UNLESS it's failed
            # Failed state is permanent and cannot be overridden
            if device_state[device_id] != 'failed':
                device_state[device_id] = 'active'
        
        elif operation_type == 'fail':
            # Permanently fail the device (irreversible)
            device_state[device_id] = 'failed'
        
        elif operation_type == 'standby':
            # Put device on standby (temporary inactive state)
            # Cannot transition failed devices to standby
            if device_state[device_id] != 'failed':
                device_state[device_id] = 'standby'
        
        elif operation_type == 'resume':
            # Reactivate device from standby state
            # Only works if device is currently in standby
            if device_state[device_id] == 'standby':
                device_state[device_id] = 'active'
    
    # Collect active devices (only these appear in output)
    active_devices = []
    for device_id in device_efficiency:
        if device_state.get(device_id) == 'active':
            active_devices.append(device_id)
    
    # Return empty list if no active devices
    if not active_devices:
        return []
    
    # Union-Find implementation with path compression and union by rank
    parent: Dict[int, int] = {}
    rank: Dict[int, int] = {}
    
    def find(x: int) -> int:
        """
        Find root of device's cluster with path compression.
        Path compression flattens tree structure for O(α(n)) operations.
        """
        if x not in parent:
            parent[x] = x
            rank[x] = 0
        if parent[x] != x:
            parent[x] = find(parent[x])  # Path compression
        return parent[x]
    
    def union(x: int, y: int) -> None:
        """
        Merge two clusters using union by rank.
        Attaches shorter tree under root of taller tree for balance.
        """
        root_x = find(x)
        root_y = find(y)
        
        if root_x == root_y:
            return  # Already in same cluster
        
        # Union by rank for balanced tree structure
        if rank[root_x] < rank[root_y]:
            parent[root_x] = root_y
        elif rank[root_x] > rank[root_y]:
            parent[root_y] = root_x
        else:
            parent[root_y] = root_x
            rank[root_x] += 1
    
    def get_cluster_members(device_id: int, active_set: set) -> List[int]:
        """Get all devices currently in the same cluster as device_id."""
        root = find(device_id)
        members = []
        for d in active_set:
            if find(d) == root:
                members.append(d)
        return members
    
    def calculate_cluster_avg(members: List[int]) -> float:
        """Calculate average efficiency of a cluster."""
        if not members:
            return 0.0
        total = sum(device_efficiency[d] for d in members)
        return total / len(members)
    
    # Initialize union-find structure for all active devices
    for device_id in active_devices:
        find(device_id)
    
    active_set = set(active_devices)
    
    # Separate devices by efficiency threshold (0.75)
    high_efficiency_devices = []
    low_efficiency_devices = []
    
    for device_id in active_devices:
        if device_efficiency[device_id] >= 0.75:
            high_efficiency_devices.append(device_id)
        else:
            low_efficiency_devices.append(device_id)
    
    # Pairwise clustering for high-efficiency devices
    # Merge two devices/clusters if their combined average ≥ 0.75
    # This ensures compatibility-based clustering
    high_efficiency_devices.sort()  # Process in consistent order
    
    for i in range(len(high_efficiency_devices)):
        for j in range(i + 1, len(high_efficiency_devices)):
            device_i = high_efficiency_devices[i]
            device_j = high_efficiency_devices[j]
            
            # Skip if already in the same cluster
            if find(device_i) == find(device_j):
                continue
            
            # Get current cluster members for both devices
            cluster_i = get_cluster_members(device_i, active_set)
            cluster_j = get_cluster_members(device_j, active_set)
            
            # Calculate what the combined average efficiency would be
            combined_members = cluster_i + cluster_j
            combined_avg = calculate_cluster_avg(combined_members)
            
            # Merge clusters if combined average meets threshold
            if combined_avg >= 0.75:
                union(device_i, device_j)
    
    # Low efficiency devices automatically form individual clusters
    # (they remain separate in the union-find structure)
    
    # Build final clusters from union-find structure
    cluster_map: Dict[int, List[int]] = {}
    
    for device_id in active_devices:
        root = find(device_id)
        if root not in cluster_map:
            cluster_map[root] = []
        cluster_map[root].append(device_id)
    
    # Sort devices within each cluster (ascending order)
    result = []
    for cluster in cluster_map.values():
        cluster.sort()
        result.append(cluster)
    
    # Sort clusters by their minimum device_id
    result.sort(key=lambda c: c[0])
    
    return result


# Example usage
if __name__ == "__main__":
    # Test case from prompt
    devices = [[1, 0.92], [2, 0.88], [3, 0.75], [4, 0.66]]
    operations = [
        ['join', 5],      # Add device 5 with eff=0.80
        ['standby', 2],   # Temporarily remove device 2
        ['fail', 3],      # Permanently remove device 3
        ['resume', 2]     # Reactivate device 2
    ]
    
    output = manage_device_clusters(devices, operations)
    print("Output:", output)