from typing import List
import math
from collections import defaultdict, deque


def maximize_station_spacing(locations: List[List[int]],
                             tiers: List[int],
                             bridges: List[List[int]],
                             R: int,
                             k: int) -> float:
    """
    Find the maximum minimum distance between k feeding stations
    that can be placed in a single connected component.
    Uses spatial indexing for efficient neighbor finding and
    backtracking for correct feasibility checking.
    """
    n = len(locations)
    
    if n < k:
        return -1.0
    
    # Build tier connectivity graph using Union-Find
    tier_parent = {}
    
    def find_tier(x):
        if x not in tier_parent:
            tier_parent[x] = x
        if tier_parent[x] != x:
            tier_parent[x] = find_tier(tier_parent[x])
        return tier_parent[x]
    
    def union_tier(a, b):
        root_a = find_tier(a)
        root_b = find_tier(b)
        if root_a != root_b:
            tier_parent[root_a] = root_b
    
    # Initialize all tiers
    for t in tiers:
        find_tier(t)
    
    # Connect tiers via bridges
    for bridge in bridges:
        union_tier(bridge[0], bridge[1])
    
    def euclidean_dist(i, j):
        dx = locations[i][0] - locations[j][0]
        dy = locations[i][1] - locations[j][1]
        return math.sqrt(dx * dx + dy * dy)
    
    # Build adjacency list using spatial grid for efficiency
    # Grid cell size = R to limit neighbor checks
    cell_size = max(1, R)
    grid = defaultdict(list)
    
    for i in range(n):
        cell_x = locations[i][0] // cell_size
        cell_y = locations[i][1] // cell_size
        grid[(cell_x, cell_y)].append(i)
    
    # Build adjacency list efficiently using spatial grid
    adj = [[] for _ in range(n)]
    
    for i in range(n):
        cell_x = locations[i][0] // cell_size
        cell_y = locations[i][1] // cell_size
        
        # Check neighboring cells (3x3 grid around current cell)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                neighbor_cell = (cell_x + dx, cell_y + dy)
                if neighbor_cell in grid:
                    for j in grid[neighbor_cell]:
                        if i < j:  # Avoid duplicate checks
                            dist = euclidean_dist(i, j)
                            
                            # Check if they can be connected in movement graph
                            if dist <= R and find_tier(tiers[i]) == find_tier(tiers[j]):
                                adj[i].append(j)
                                adj[j].append(i)
    
    # Find connected components
    visited = [False] * n
    components = []
    
    def bfs(start):
        component = []
        queue = deque([start])
        visited[start] = True
        
        while queue:
            node = queue.popleft()
            component.append(node)
            
            for neighbor in adj[node]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    queue.append(neighbor)
        
        return component
    
    for i in range(n):
        if not visited[i]:
            comp = bfs(i)
            if len(comp) >= k:
                components.append(comp)
    
    if not components:
        return -1.0
    
    # Collect all pairwise distances within components for binary search
    all_distances = set([0.0])
    for component in components:
        comp_size = len(component)
        if comp_size <= 1000:  # For reasonable component sizes, compute all pairs
            for i in range(comp_size):
                for j in range(i + 1, comp_size):
                    dist = euclidean_dist(component[i], component[j])
                    all_distances.add(dist)
        else:
            # For large components, sample distances
            step = max(1, comp_size // 1000)
            for i in range(0, comp_size, step):
                for j in range(i + 1, min(comp_size, i + 1000), step):
                    dist = euclidean_dist(component[i], component[j])
                    all_distances.add(dist)
    
    unique_distances = sorted(all_distances)
    
    def can_select_k_stations(component, min_dist):
        """
        Check if k stations can be selected with minimum distance min_dist.
        Uses backtracking with pruning for correctness.
        """
        if len(component) < k:
            return False
        
        # Precompute distance matrix for this component
        comp_size = len(component)
        dist_matrix = {}
        for i in range(comp_size):
            for j in range(i + 1, comp_size):
                dist = euclidean_dist(component[i], component[j])
                dist_matrix[(i, j)] = dist
                dist_matrix[(j, i)] = dist
        
        # Build conflict graph: edge if distance < min_dist
        conflicts = [set() for _ in range(comp_size)]
        for i in range(comp_size):
            for j in range(i + 1, comp_size):
                if dist_matrix[(i, j)] < min_dist - 1e-9:
                    conflicts[i].add(j)
                    conflicts[j].add(i)
        
        # Use backtracking to find independent set of size k
        def backtrack(idx, selected, excluded):
            if len(selected) == k:
                return True
            
            # Pruning: not enough remaining nodes
            remaining = comp_size - idx
            if len(selected) + remaining < k:
                return False
            
            if idx >= comp_size:
                return False
            
            # Skip if already excluded
            if idx in excluded:
                return backtrack(idx + 1, selected, excluded)
            
            # Try including current node
            can_include = all(idx not in conflicts[s] for s in selected)
            
            if can_include:
                selected.append(idx)
                # Exclude all conflicting nodes
                new_excluded = excluded | conflicts[idx]
                if backtrack(idx + 1, selected, new_excluded):
                    return True
                selected.pop()
            
            # Try not including current node
            return backtrack(idx + 1, selected, excluded)
        
        return backtrack(0, [], set())
    
    max_min_dist = -1.0
    
    # Try each component
    for component in components:
        # Binary search on distance
        left, right = 0, len(unique_distances) - 1
        best_for_component = -1.0
        
        while left <= right:
            mid = (left + right) // 2
            test_dist = unique_distances[mid]
            
            if can_select_k_stations(component, test_dist):
                best_for_component = test_dist
                left = mid + 1
            else:
                right = mid - 1
        
        max_min_dist = max(max_min_dist, best_for_component)
    
    return max_min_dist if max_min_dist >= 0 else -1.0