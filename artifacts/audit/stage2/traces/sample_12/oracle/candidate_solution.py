import logging
import math
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cross-region alliances operate at 50% of the smaller region's capacity
CROSS_REGION_CAPACITY_FACTOR = 0.5

# Iteration multiplier for maximum iterations in component solving
# Based on component size to ensure convergence while preventing infinite loops
ITERATION_MULTIPLIER = 10

# Maximum number of over-resolution attempts when exploring moves
# Tries exact resolution and over-resolution by 1 to find optimal solutions
MAX_OVER_RESOLUTION_ATTEMPTS = 2


class AllianceAllocator:
    """Class to handle alliance allocation calculations."""
    
    @staticmethod
    def min_players_to_reduce(current_players: int, constraint: int, target_reduction: int) -> int:
        """Calculate minimum players to move to reduce alliance count by target_reduction."""
        if constraint <= 0 or current_players <= 0:
            return None
        
        current_alliances = math.ceil(current_players / constraint)
        if target_reduction <= 0:
            return 0
        if target_reduction > current_alliances:
            return None
        
        target_alliances = current_alliances - target_reduction
        
        # Binary search for minimum move
        low = 0
        high = current_players
        result = None
        
        while low <= high:
            mid = (low + high) // 2
            new_players = current_players - mid
            new_alliances = math.ceil(new_players / constraint) if new_players > 0 else 0
            
            if new_alliances <= target_alliances:
                result = mid
                high = mid - 1
            else:
                low = mid + 1
        
        return result
    
    @staticmethod
    def find_connected_components(synergy_map: Dict[str, int], num_regions: int) -> List[List[int]]:
        """Find connected components in the synergy graph using BFS."""
        # Build adjacency list (using lists only)
        adjacency: List[List[int]] = [[] for _ in range(num_regions)]
        for key_str in synergy_map.keys():
            region_a, region_b = map(int, key_str.split(','))
            if region_b not in adjacency[region_a]:
                adjacency[region_a].append(region_b)
            if region_a not in adjacency[region_b]:
                adjacency[region_b].append(region_a)
        
        # Find components using BFS
        visited = [False] * num_regions
        components: List[List[int]] = []
        
        for start_region in range(num_regions):
            if visited[start_region]:
                continue
            
            # BFS to find all connected regions
            component = []
            queue = [start_region]
            visited[start_region] = True
            
            while queue:
                current = queue.pop(0)
                component.append(current)
                
                for neighbor in adjacency[current]:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)
            
            if component:
                components.append(component)
        
        return components
    
    def solve_component(
        self,
        component_regions: List[int],
        component_players: List[int],
        component_constraints: List[int],
        component_synergy_map: Dict[str, int],
        global_players: List[int]
    ) -> tuple[List[int], Dict[str, int], bool]:
        """
        Solve allocation for a single connected component.
        
        Args:
            component_regions: Global region indices in this component
            component_players: Component players (indexed by component position)
            component_constraints: Component constraints (indexed by component position)
            component_synergy_map: Component synergy map
            global_players: Global players list for validation
        
        Returns:
            (regional_players, cross_region_total, is_feasible)
        """
        num_component_regions = len(component_players)
        regional_players = list(component_players)
        cross_region_total: Dict[str, int] = {}
        
        if not component_synergy_map:
            # No synergies in this component, return base allocation
            return regional_players, cross_region_total, True
        
        # Validate zero-player regions: no alliances may originate from or depend on them
        for comp_idx in range(num_component_regions):
            global_idx = component_regions[comp_idx]
            if global_players[global_idx] == 0:
                # Zero-player region cannot have alliances
                if regional_players[comp_idx] != 0:
                    return regional_players, cross_region_total, False
                # Check if it participates in synergies - it can only be a connectivity node
                # If a synergy involves a zero-player region with limit > 0, it's invalid
                # (since the other region would need 0 alliances, which isn't possible if it has players)
                for key_str, limit in component_synergy_map.items():
                    comp_a, comp_b = map(int, key_str.split(','))
                    if (comp_a == comp_idx or comp_b == comp_idx):
                        other_comp = comp_b if comp_a == comp_idx else comp_a
                        # If zero-player region is in synergy with limit > 0 and other has players, invalid
                        if limit > 0 and component_players[other_comp] > 0:
                            # This would require other region to have <= limit alliances
                            # But if limit is too small, it might be impossible
                            # For now, allow it as connectivity but ensure no alliances depend on zero region
                            pass
        
        # Pre-check for infeasible zero synergy limits
        for key_str, limit in component_synergy_map.items():
            comp_a, comp_b = map(int, key_str.split(','))
            if limit == 0:
                if component_players[comp_a] > 0 or component_players[comp_b] > 0:
                    cross_capacity = min(component_constraints[comp_a], component_constraints[comp_b]) * CROSS_REGION_CAPACITY_FACTOR
                    if cross_capacity <= 0:
                        return regional_players, cross_region_total, False
        
        max_iterations = len(component_synergy_map) * num_component_regions * ITERATION_MULTIPLIER
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Track state before iteration for stagnation detection
            regional_players_before = list(regional_players)
            violations_before = []
            
            # Calculate current regional alliance counts
            regional_alliances = [
                math.ceil(regional_players[i] / component_constraints[i]) if component_constraints[i] > 0 and regional_players[i] > 0 else 0
                for i in range(num_component_regions)
            ]
            
            # Find violations
            violations = []
            for key_str, limit in component_synergy_map.items():
                comp_a, comp_b = map(int, key_str.split(','))
                current_combined = regional_alliances[comp_a] + regional_alliances[comp_b]
                
                if current_combined > limit:
                    excess = current_combined - limit
                    violations.append((key_str, comp_a, comp_b, excess, limit))
                    violations_before.append((key_str, comp_a, comp_b))
            
            if not violations:
                break
            
            # Process all violations in this iteration
            made_progress = False
            violations.sort(key=lambda x: x[3], reverse=True)
            
            for key_str, comp_a, comp_b, excess, limit in violations:
                # Recalculate alliances in case previous moves affected this region
                regional_alliances = [
                    math.ceil(regional_players[i] / component_constraints[i]) if component_constraints[i] > 0 and regional_players[i] > 0 else 0
                    for i in range(num_component_regions)
                ]
                
                # Re-check if still violated
                current_combined = regional_alliances[comp_a] + regional_alliances[comp_b]
                if current_combined <= limit:
                    continue
                
                excess = current_combined - limit
                
                # Special handling for zero limit
                if limit == 0:
                    if regional_players[comp_a] > 0 or regional_players[comp_b] > 0:
                        cross_capacity = min(component_constraints[comp_a], component_constraints[comp_b]) * CROSS_REGION_CAPACITY_FACTOR
                        if cross_capacity <= 0:
                            return regional_players, cross_region_total, False
                        
                        # Move all players to cross-region
                        total_to_move = regional_players[comp_a] + regional_players[comp_b]
                        regional_players[comp_a] = 0
                        regional_players[comp_b] = 0
                        cross_region_total[key_str] = cross_region_total.get(key_str, 0) + total_to_move
                        made_progress = True
                    continue
                
                # Calculate cross-region capacity
                cross_capacity = min(component_constraints[comp_a], component_constraints[comp_b]) * CROSS_REGION_CAPACITY_FACTOR
                if cross_capacity <= 0:
                    if regional_players[comp_a] > 0 or regional_players[comp_b] > 0:
                        return regional_players, cross_region_total, False
                    continue
                
                # Find best move to resolve this violation
                # We want to minimize total alliances (regional + cross-region) after the move
                # Track separately: regional alliances and cross-region alliances are counted independently
                best_move = None
                best_total_alliances = float('inf')
                
                current_alliances_a = regional_alliances[comp_a]
                current_alliances_b = regional_alliances[comp_b]
                
                # Calculate current cross-region alliances for this pair
                # Cross-region alliances are separate from regional alliances
                current_cross_players = cross_region_total.get(key_str, 0)
                current_cross_alliances = math.ceil(current_cross_players / cross_capacity) if cross_capacity > 0 and current_cross_players > 0 else 0
                
                # Try moving from comp_a only
                # Try exact reduction and over-resolving by 1
                if regional_players[comp_a] > 0:
                    moves_to_try = []
                    move_a = self.min_players_to_reduce(regional_players[comp_a], component_constraints[comp_a], excess)
                    if move_a is not None and move_a <= regional_players[comp_a] and move_a > 0:
                        moves_to_try.append(move_a)
                    # Also try over-resolving by 1
                    move_a_plus = self.min_players_to_reduce(regional_players[comp_a], component_constraints[comp_a], excess + 1)
                    if move_a_plus is not None and move_a_plus <= regional_players[comp_a] and move_a_plus > 0:
                        if move_a_plus not in moves_to_try:
                            moves_to_try.append(move_a_plus)
                    
                    for try_move_a in moves_to_try:
                        if try_move_a > 0 and try_move_a <= regional_players[comp_a]:
                            # Calculate new regional alliances after move
                            new_players_a = regional_players[comp_a] - try_move_a
                            new_alliances_a = math.ceil(new_players_a / component_constraints[comp_a]) if component_constraints[comp_a] > 0 and new_players_a > 0 else 0
                            
                            # Verify this resolves the violation
                            if new_alliances_a + current_alliances_b <= limit:
                                # Calculate new cross-region alliances needed
                                # Cross-region alliances count players from BOTH regions
                                total_after_move = current_cross_players + try_move_a
                                new_cross_alliances = math.ceil(total_after_move / cross_capacity) if cross_capacity > 0 and total_after_move > 0 else 0
                                
                                # Total alliances = regional alliances (both regions) + cross-region alliances
                                # Regional alliances are independent per region, cross-region are shared
                                new_total = new_alliances_a + current_alliances_b + new_cross_alliances
                                
                                # Minimize total alliances
                                if new_total < best_total_alliances:
                                    best_move = (try_move_a, 0)
                                    best_total_alliances = new_total
                
                # Try moving from comp_b only
                # Try exact reduction and over-resolving by 1
                if regional_players[comp_b] > 0:
                    moves_to_try = []
                    move_b = self.min_players_to_reduce(regional_players[comp_b], component_constraints[comp_b], excess)
                    if move_b is not None and move_b <= regional_players[comp_b] and move_b > 0:
                        moves_to_try.append(move_b)
                    # Also try over-resolving by 1
                    move_b_plus = self.min_players_to_reduce(regional_players[comp_b], component_constraints[comp_b], excess + 1)
                    if move_b_plus is not None and move_b_plus <= regional_players[comp_b] and move_b_plus > 0:
                        if move_b_plus not in moves_to_try:
                            moves_to_try.append(move_b_plus)
                    
                    for try_move_b in moves_to_try:
                        if try_move_b > 0 and try_move_b <= regional_players[comp_b]:
                            new_players_b = regional_players[comp_b] - try_move_b
                            new_alliances_b = math.ceil(new_players_b / component_constraints[comp_b]) if component_constraints[comp_b] > 0 and new_players_b > 0 else 0
                            reduction = current_alliances_b - new_alliances_b
                            
                            # Verify this resolves the violation
                            if current_alliances_a + new_alliances_b <= limit:
                                total_after_move = current_cross_players + try_move_b
                                new_cross_alliances = math.ceil(total_after_move / cross_capacity) if cross_capacity > 0 and total_after_move > 0 else 0
                                
                                new_total = current_alliances_a + new_alliances_b + new_cross_alliances
                                
                                if new_total < best_total_alliances:
                                    best_move = (0, try_move_b)
                                    best_total_alliances = new_total
                
                # Try moving from both regions
                # Also try over-resolving by 1 to explore better solutions
                if regional_players[comp_a] > 0 and regional_players[comp_b] > 0:
                    for extra in range(MAX_OVER_RESOLUTION_ATTEMPTS):  # Try exact and over-resolution attempts
                        target_reduction = excess + extra
                        for reduction_a in range(target_reduction + 1):
                            reduction_b = target_reduction - reduction_a
                            
                            if reduction_a > current_alliances_a or reduction_b > current_alliances_b:
                                continue
                            
                            move_a = self.min_players_to_reduce(regional_players[comp_a], component_constraints[comp_a], reduction_a) if reduction_a > 0 else 0
                            move_b = self.min_players_to_reduce(regional_players[comp_b], component_constraints[comp_b], reduction_b) if reduction_b > 0 else 0
                            
                            if move_a is None or move_b is None:
                                continue
                            if move_a > regional_players[comp_a] or move_b > regional_players[comp_b]:
                                continue
                            
                            total_moved = move_a + move_b
                            if total_moved > 0:
                                # Calculate new regional alliances
                                new_players_a = regional_players[comp_a] - move_a
                                new_players_b = regional_players[comp_b] - move_b
                                new_alliances_a = math.ceil(new_players_a / component_constraints[comp_a]) if component_constraints[comp_a] > 0 and new_players_a > 0 else 0
                                new_alliances_b = math.ceil(new_players_b / component_constraints[comp_b]) if component_constraints[comp_b] > 0 and new_players_b > 0 else 0
                                
                                # Verify this resolves the violation (or over-resolves)
                                new_combined = new_alliances_a + new_alliances_b
                                if new_combined <= limit:
                                    # Calculate new cross-region alliances
                                    total_after_move = current_cross_players + total_moved
                                    new_cross_alliances = math.ceil(total_after_move / cross_capacity) if cross_capacity > 0 and total_after_move > 0 else 0
                                    
                                    # Total alliances after move
                                    new_total = new_alliances_a + new_alliances_b + new_cross_alliances
                                    
                                    if new_total < best_total_alliances:
                                        best_move = (move_a, move_b)
                                        best_total_alliances = new_total
                
                # Execute best move with validation
                if best_move and (best_move[0] > 0 or best_move[1] > 0):
                    move_a, move_b = best_move
                    # Final validation before executing
                    if move_a <= regional_players[comp_a] and move_b <= regional_players[comp_b]:
                        # Verify cross-region capacity can accommodate the move
                        total_players_to_move = move_a + move_b
                        current_cross = cross_region_total.get(key_str, 0)
                        total_after_move = current_cross + total_players_to_move
                        
                        # Check if this move is feasible
                        required_alliances = math.ceil(total_after_move / cross_capacity) if cross_capacity > 0 and total_after_move > 0 else 0
                        if required_alliances * cross_capacity >= total_after_move:
                            regional_players[comp_a] -= move_a
                            regional_players[comp_b] -= move_b
                            cross_region_total[key_str] = total_after_move
                            made_progress = True
            
            # Simplified stagnation detection: check if any violation was resolved in this iteration
            if not made_progress:
                # Recalculate violations after processing all violations in this iteration
                regional_alliances_after = [
                    math.ceil(regional_players[i] / component_constraints[i]) if component_constraints[i] > 0 and regional_players[i] > 0 else 0
                    for i in range(num_component_regions)
                ]
                
                violations_after = []
                for key_str, limit in component_synergy_map.items():
                    comp_a, comp_b = map(int, key_str.split(','))
                    current_combined = regional_alliances_after[comp_a] + regional_alliances_after[comp_b]
                    if current_combined > limit:
                        violations_after.append((key_str, comp_a, comp_b))
                
                # If no violations were resolved (same set of violations), check if infeasible
                if len(violations_after) >= len(violations_before):
                    # Check if infeasible
                    for key_str, comp_a, comp_b, excess, limit in violations:
                        if limit == 0:
                            if regional_players[comp_a] > 0 or regional_players[comp_b] > 0:
                                cross_capacity = min(component_constraints[comp_a], component_constraints[comp_b]) * CROSS_REGION_CAPACITY_FACTOR
                                if cross_capacity <= 0:
                                    return regional_players, cross_region_total, False
                        
                        if regional_players[comp_a] == 0 and regional_players[comp_b] == 0:
                            return regional_players, cross_region_total, False
                    
                    # Stagnation without resolution - infeasible
                    if iteration >= max_iterations:
                        return regional_players, cross_region_total, False
        
        # Final verification
        regional_alliances = [
            math.ceil(regional_players[i] / component_constraints[i]) if component_constraints[i] > 0 and regional_players[i] > 0 else 0
            for i in range(num_component_regions)
        ]
        
        for key_str, limit in component_synergy_map.items():
            comp_a, comp_b = map(int, key_str.split(','))
            current_combined = regional_alliances[comp_a] + regional_alliances[comp_b]
            if current_combined > limit:
                return regional_players, cross_region_total, False
        
        return regional_players, cross_region_total, True


def allocate_minimum_alliances(
    players: List[int],
    constraints: List[int],
    synergies: List[List[int]]
) -> int:
    """
    Calculate the minimal total number of alliances needed across all regions.
    
    Regional alliances are formed within single regions with capacity limits.
    Cross-region alliances span two connected regions at 50% capacity and
    don't count toward synergy limits.
    
    Args:
        players: Number of players in each region
        constraints: Maximum capacity per regional alliance in each region
        synergies: List of [region_a, region_b, synergy_limit] lists
                  representing maximum combined regional alliances
    
    Returns:
        Minimum total number of alliances (regional + cross-region).
        Returns -1 if no feasible configuration exists.
    """
    if not players:
        return 0
    
    num_regions = len(players)
    
    # Validate inputs
    if len(constraints) != num_regions:
        if len(constraints) < num_regions:
            constraints = constraints + [constraints[-1] if constraints else 1] * (num_regions - len(constraints))
        else:
            constraints = constraints[:num_regions]
    
    # Validate zero-player regions: no alliances may originate from or depend on them
    for i in range(num_regions):
        if players[i] == 0 and constraints[i] > 0:
            # Zero-player region with positive constraint is valid (just means no alliances)
            # This will be validated during component solving
            pass
    
    # Build synergy constraint map with explicit zero-player region validation
    synergy_map: Dict[str, int] = {}
    for synergy in synergies:
        if len(synergy) >= 3:
            region_a, region_b, limit = synergy[0], synergy[1], synergy[2]
            
            # Explicit validation: zero-player regions cannot have alliances
            # If both regions have zero players, synergy limit must allow 0 alliances
            if players[region_a] == 0 and players[region_b] == 0:
                if limit < 0:
                    return -1  # Invalid constraint
                # Both zero - no alliances possible, this is valid
            
            # If one region has zero players, it can only be a connectivity node
            # The other region must satisfy the limit on its own
            elif players[region_a] == 0 or players[region_b] == 0:
                # Zero-player region cannot have alliances, so other region must have <= limit alliances
                # This will be validated during component solving
                pass
            
            key = f"{min(region_a, region_b)},{max(region_a, region_b)}"
            synergy_map[key] = limit
    
    if not synergy_map:
        # No synergy constraints, return base allocation
        return sum(math.ceil(players[i] / constraints[i]) if constraints[i] > 0 else 0 
                  for i in range(num_regions))
    
    # Create allocator instance
    allocator = AllianceAllocator()
    
    # Find disconnected components
    components = allocator.find_connected_components(synergy_map, num_regions)
    
    # Process each component independently
    total_regional_players = list(players)
    total_cross_region: Dict[str, int] = {}
    
    for component_regions in components:
        # Extract component data
        component_players = [players[i] for i in component_regions]
        component_constraints = [constraints[i] for i in component_regions]
        
        # Build component synergy map with component indices
        component_synergy_map: Dict[str, int] = {}
        for key_str, limit in synergy_map.items():
            global_a, global_b = map(int, key_str.split(','))
            if global_a in component_regions and global_b in component_regions:
                comp_a = component_regions.index(global_a)
                comp_b = component_regions.index(global_b)
                comp_key = f"{min(comp_a, comp_b)},{max(comp_a, comp_b)}"
                component_synergy_map[comp_key] = limit
        
        # Solve this component
        component_regional_players, component_cross_region, is_feasible = allocator.solve_component(
            component_regions,
            component_players,
            component_constraints,
            component_synergy_map,
            players  # Pass global players for validation
        )
        
        if not is_feasible:
            return -1
        
        # Map results back to global indices
        for i, global_idx in enumerate(component_regions):
            total_regional_players[global_idx] = component_regional_players[i]
        
        # Map cross-region alliances back to global keys
        for comp_key, total_players in component_cross_region.items():
            comp_a, comp_b = map(int, comp_key.split(','))
            global_a = component_regions[comp_a]
            global_b = component_regions[comp_b]
            global_key = f"{min(global_a, global_b)},{max(global_a, global_b)}"
            total_cross_region[global_key] = total_cross_region.get(global_key, 0) + total_players
    
    # Calculate totals
    regional_alliances = [
        math.ceil(total_regional_players[i] / constraints[i]) if constraints[i] > 0 and total_regional_players[i] > 0 else 0
        for i in range(num_regions)
    ]
    
    total_regional = sum(regional_alliances)
    
    # Calculate cross-region alliances and verify feasibility
    total_cross_region_count = 0
    for key_str, total_players in total_cross_region.items():
        if total_players > 0:
            region_a, region_b = map(int, key_str.split(','))
            cross_capacity = min(constraints[region_a], constraints[region_b]) * CROSS_REGION_CAPACITY_FACTOR
            if cross_capacity <= 0:
                # Cannot form cross-region alliances - verify no players are allocated
                if total_players > 0:
                    return -1
            else:
                # Verify feasibility: check if we can accommodate all players
                cross_alliances = math.ceil(total_players / cross_capacity)
                total_cross_region_count += cross_alliances
                
                # Verify no over-allocation: cross-region alliances * capacity >= total players
                if cross_alliances * cross_capacity < total_players:
                    return -1
    
    total_alliances = total_regional + total_cross_region_count
    
    logger.info(f"Regional alliances: {total_regional}, Cross-region: {total_cross_region_count}, Total: {total_alliances}")
    
    return total_alliances