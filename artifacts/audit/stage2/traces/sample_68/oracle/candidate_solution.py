from typing import List, Dict, Optional, Union


class ComponentMetadata:
    """Minimal metadata for each connected component."""
    
    def __init__(self, shard_id: int):
        # Use dict to track members instead of set (no sets allowed)
        self.members: Dict[int, bool] = {shard_id: True}
        self.total_load = self._calculate_load(shard_id)
    
    def _calculate_load(self, shard_id: int) -> int:
        """Calculate load for a shard using formula: (shard_id % 100) + 1"""
        return (shard_id % 100) + 1


class VersionSnapshot:
    """Snapshot of the disjoint-set state at a specific version."""
    
    def __init__(self):
        self.parent: Dict[int, int] = {}
        self.rank: Dict[int, int] = {}


class VersionedDisjointSet:
    """
    Disjoint-Set with versioning, load balancing, and split operations.
    Optimized for O(log n) split and O(1) load updates.
    """
    
    def __init__(self, max_shards: int, max_component_load: int = 500):
        self.max_shards = max_shards
        self.max_component_load = max_component_load
        
        # Current state - use dictionary for sparse representation
        self.parent: Dict[int, int] = {}
        self.rank: Dict[int, int] = {}
        self.metadata: Dict[int, ComponentMetadata] = {}
        
        # Versioning - store complete state snapshots
        self.version_snapshots: List[VersionSnapshot] = []
        self._save_version()  # Version 0 (initial empty state)
    
    def _calculate_load(self, shard_id: int) -> int:
        """Calculate load for a shard using formula: (shard_id % 100) + 1"""
        return (shard_id % 100) + 1
    
    def _ensure_initialized(self, x: int):
        """Lazy initialization of shard."""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            self.metadata[x] = ComponentMetadata(x)
    
    def _save_version(self):
        """Create a complete snapshot of current state."""
        snapshot = VersionSnapshot()
        # Copy dictionaries
        for k, v in self.parent.items():
            snapshot.parent[k] = v
        for k, v in self.rank.items():
            snapshot.rank[k] = v
        self.version_snapshots.append(snapshot)
    
    def _find_with_compression(self, x: int) -> int:
        """Find root of element x with path compression."""
        self._ensure_initialized(x)
        
        if self.parent[x] != x:
            self.parent[x] = self._find_with_compression(self.parent[x])
        return self.parent[x]
    
    def _find_in_version(self, x: int, version: int) -> int:
        """Find root in a historical version without modification."""
        if version < 0 or version >= len(self.version_snapshots):
            return -1
        
        snapshot = self.version_snapshots[version]
        if x not in snapshot.parent:
            return x
        
        # Simple find without path compression for historical queries
        root = x
        visited: Dict[int, bool] = {}
        while snapshot.parent.get(root, root) != root:
            if root in visited:
                return root
            visited[root] = True
            root = snapshot.parent[root]
        return root
    
    def find(self, x: int, version: Optional[int] = None) -> int:
        """Find root of element x."""
        if version is not None:
            return self._find_in_version(x, version)
        else:
            return self._find_with_compression(x)
    
    def is_connected(self, x: int, y: int, version: Optional[int] = None) -> bool:
        """Check if two shards are in the same component."""
        root_x = self.find(x, version)
        root_y = self.find(y, version)
        if root_x == -1 or root_y == -1:
            return False
        return root_x == root_y
    
    def union(self, x: int, y: int) -> bool:
        """
        Union two shards with load-aware merging.
        Returns True if merge was successful, False if rejected due to constraints.
        Time complexity: O(α(n)) amortized
        """
        self._ensure_initialized(x)
        self._ensure_initialized(y)
        
        root_x = self._find_with_compression(x)
        root_y = self._find_with_compression(y)
        
        if root_x == root_y:
            # Already connected - save version anyway
            self._save_version()
            return True
        
        # Use stored total_load instead of recalculating - O(1) operation
        load_x = self.metadata[root_x].total_load
        load_y = self.metadata[root_y].total_load
        total_load = load_x + load_y
        
        # Enforce strict capacity constraint
        if total_load > self.max_component_load:
            # Save version without making changes
            self._save_version()
            return False
        
        # Perform union by rank
        if self.rank[root_x] < self.rank[root_y]:
            root_x, root_y = root_y, root_x
            load_x, load_y = load_y, load_x
        
        self.parent[root_y] = root_x
        
        if self.rank[root_x] == self.rank[root_y]:
            self.rank[root_x] += 1
        
        # Merge metadata - O(n) for member merge but unavoidable for maintaining member list
        for member in self.metadata[root_y].members:
            self.metadata[root_x].members[member] = True
        
        # Update total load - O(1) operation
        self.metadata[root_x].total_load = total_load
        
        # Save version after successful union
        self._save_version()
        
        return True
    
    def split(self, x: int, y: int) -> bool:
        """
        Split shard y from shard x by isolating y into its own component.
        Returns True if split was performed, False otherwise.
        Time complexity: O(log n) with path compression
        """
        self._ensure_initialized(x)
        self._ensure_initialized(y)
        
        root_x = self._find_with_compression(x)
        root_y = self._find_with_compression(y)
        
        if root_x != root_y:
            # Already in different components
            self._save_version()
            return False
        
        if x == y:
            # Cannot split a shard from itself
            self._save_version()
            return False
        
        # Get the component root
        component_root = root_x
        
        # Make y its own root
        self.parent[y] = y
        self.rank[y] = 0
        
        # Remove y from the original component's members - O(1) dict operation
        if y in self.metadata[component_root].members:
            del self.metadata[component_root].members[y]
        
        # Update load - O(1) operation (subtract instead of recalculating)
        y_load = self._calculate_load(y)
        self.metadata[component_root].total_load -= y_load
        
        # Ensure non-negative load
        if self.metadata[component_root].total_load < 0:
            self.metadata[component_root].total_load = 0
        
        # Create new metadata for y's component
        new_meta = ComponentMetadata(y)
        self.metadata[y] = new_meta
        
        # Save version after successful split
        self._save_version()
        
        return True


def manage_shard_connections(operations: List[List[Union[str, int, None]]]) -> List[str]:
    """
    Main function to manage shard connections with versioning and load balancing.
    
    Args:
        operations: List of operations, each as [op_type, shard_a, shard_b, maybe_version]
    
    Returns:
        List of strings ("True" or "False") results, one per operation
    """
    max_shards = 2_000
    max_component_load = 500
    
    # Find max shard ID in operations to optimize memory
    max_shard_id = 0
    for op in operations:
        if len(op) >= 3 and isinstance(op[1], int) and isinstance(op[2], int):
            max_shard_id = max(max_shard_id, op[1], op[2])
    
    actual_max = min(max_shard_id + 100, max_shards)
    
    # CRITICAL FIX: Build mapping from operation count to snapshot index
    # Version k = state after operation k-1 completes
    # operation_to_snapshot[k] = snapshot index for version k
    operation_to_snapshot: Dict[int, int] = {0: 0}  # Version 0 = initial state (snapshot 0)
    snapshot_count = 1  # Start with 1 (initial snapshot)
    
    for i, op in enumerate(operations):
        op_type = op[0]
        # Union and split create new snapshots
        if op_type in ['union', 'split']:
            snapshot_count += 1
        # After operation i completes, we're at version i+1
        operation_to_snapshot[i + 1] = snapshot_count - 1
    
    ds = VersionedDisjointSet(actual_max, max_component_load)
    results: List[str] = []
    
    for op_idx, op in enumerate(operations):
        op_type = op[0]
        shard_a = op[1] if len(op) > 1 else 0
        shard_b = op[2] if len(op) > 2 else 0
        maybe_version = op[3] if len(op) > 3 else None
        
        if op_type == 'union':
            result = ds.union(shard_a, shard_b)
            results.append("True" if result else "False")
        elif op_type == 'split':
            result = ds.split(shard_a, shard_b)
            results.append("True" if result else "False")
        elif op_type == 'find':
            result = ds.is_connected(shard_a, shard_b)
            results.append("True" if result else "False")
        elif op_type == 'find_versioned':
            # When processing operation at index op_idx:
            # - Operations 0 through op_idx-1 have completed
            # - We are currently at version op_idx (state after op_idx-1)
            # - If querying version > op_idx, it's in the future
            current_version = op_idx
            
            if maybe_version is not None and maybe_version <= current_version and maybe_version in operation_to_snapshot:
                snapshot_idx = operation_to_snapshot[maybe_version]
                result = ds.is_connected(shard_a, shard_b, version=snapshot_idx)
            else:
                # Version doesn't exist (future or invalid)
                result = False
            results.append("True" if result else "False")
    
    return results