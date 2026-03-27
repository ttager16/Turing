from typing import List, Dict, Any


def normalize_priority_devices(priority_devices):
    """Convert string keys to integer keys in priority_devices dictionary."""
    if not priority_devices:
        return {}
    normalized = {}
    for key, value in priority_devices.items():
        normalized[int(key)] = value
    return normalized


def optimize_smart_city_energy(
    zone_states: List[int],
    zone_configs: List[Dict[str, Any]],
    grid_segments: List[Dict[str, Any]],
    inter_zone_deps: List[List[int]],
    weather_conditions: Dict[str, Any],
    global_energy_limit: int,
    mutual_exclusion_groups: List[List[List[int]]],
    synchronization_groups: List[List[List[int]]],
    cascading_propagation: List[List[int]],
    transition_cost_matrices: List[List[List[int]]]
) -> List[int]:
    
    if not zone_states:
        return []
    
    num_zones = len(zone_states)
    
    # Check for internal contradictions first
    for i, config in enumerate(zone_configs):
        if check_zone_internal_contradictions(config, synchronization_groups, i):
            result = [-1 if j == i else zone_states[j] for j in range(num_zones)]
            return result
    
    # Try greedy optimization first
    current_states = list(zone_states)
    apply_mandatory_constraints(
        current_states, zone_configs, weather_conditions, 
        synchronization_groups, cascading_propagation
    )
    
    if validate_all_constraints(current_states, zone_configs, grid_segments, inter_zone_deps,
                                weather_conditions, global_energy_limit, mutual_exclusion_groups,
                                synchronization_groups, cascading_propagation):
        return current_states
    
    greedy_result = greedy_optimize(
        current_states, zone_configs, grid_segments, inter_zone_deps,
        weather_conditions, global_energy_limit, mutual_exclusion_groups,
        synchronization_groups, cascading_propagation, zone_states
    )
    
    if greedy_result and validate_all_constraints(greedy_result, zone_configs, grid_segments, inter_zone_deps,
                                                weather_conditions, global_energy_limit, mutual_exclusion_groups,
                                                synchronization_groups, cascading_propagation):
        # If greedy found a solution, use backtracking to find optimal solution
        best_solution = backtracking_optimize(
            zone_states, zone_configs, grid_segments, inter_zone_deps,
            weather_conditions, global_energy_limit, mutual_exclusion_groups,
            synchronization_groups, cascading_propagation, transition_cost_matrices
        )
        return best_solution if best_solution is not None else greedy_result
    
    # If greedy failed, try backtracking
    result = backtracking_optimize(
        zone_states, zone_configs, grid_segments, inter_zone_deps,
        weather_conditions, global_energy_limit, mutual_exclusion_groups,
        synchronization_groups, cascading_propagation, transition_cost_matrices
    )
    return result if result is not None else []


def apply_mandatory_constraints(states, zone_configs, weather_conditions, 
                                synchronization_groups, cascading_propagation):
    
    for zone_idx in range(len(states)):
        config = zone_configs[zone_idx]
        device_count = config.get('device_count', 16)
        priority_devices = normalize_priority_devices(config.get('priority_devices', {}))
        
        for device_idx, min_state in priority_devices.items():
            if device_idx < device_count:
                current_state = get_device_state(states[zone_idx], device_idx)
                if current_state < min_state:
                    states[zone_idx] = set_device_state(states[zone_idx], device_idx, min_state)
    
    if weather_conditions:
        temperature = weather_conditions.get('temperature', 0)
        threshold = weather_conditions.get('high_temp_threshold', float('inf'))
        
        if temperature > threshold:
            devices_affected = weather_conditions.get('devices_affected', [])
            for zone_idx, device_idx in devices_affected:
                if zone_idx < len(states):
                    state = get_device_state(states[zone_idx], device_idx)
                    if state < 2:
                        states[zone_idx] = set_device_state(states[zone_idx], device_idx, 2)
    
    for group in synchronization_groups:
        if not group:
            continue
        max_state = 0
        for zone_idx, device_idx in group:
            if zone_idx < len(states):
                state = get_device_state(states[zone_idx], device_idx)
                max_state = max(max_state, state)
        
        for zone_idx, device_idx in group:
            if zone_idx < len(states):
                states[zone_idx] = set_device_state(states[zone_idx], device_idx, max_state)


def apply_device_dependencies(states, zone_configs):
    """Apply device dependency constraints."""
    improved = False
    for zone_idx in range(len(states)):
        config = zone_configs[zone_idx]
        device_count = config.get('device_count', 16)
        device_dependencies = config.get('device_dependencies', [])
        
        for device_idx, required_device_idx, min_state in device_dependencies:
            if device_idx >= device_count or required_device_idx >= device_count:
                continue
            required_state = get_device_state(states[zone_idx], required_device_idx)
            if required_state > 0:
                device_state = get_device_state(states[zone_idx], device_idx)
                if device_state < min_state:
                    states[zone_idx] = set_device_state(states[zone_idx], device_idx, min_state)
                    improved = True
    return improved


def apply_cascading_propagation_constraints(states, cascading_propagation):
    """Apply cascading propagation constraints."""
    improved = False
    for zone_from, device_from, zone_to, device_to in cascading_propagation:
        if zone_from >= len(states) or zone_to >= len(states):
            continue
        
        state_from = get_device_state(states[zone_from], device_from)
        state_to = get_device_state(states[zone_to], device_to)
        
        if state_from > 0:
            required_state = max(1, state_from - 1)
            if state_to < required_state:
                states[zone_to] = set_device_state(states[zone_to], device_to, required_state)
                improved = True
    return improved


def apply_energy_quota_constraints(states, zone_configs):
    """Apply zone energy quota constraints."""
    improved = False
    for zone_idx in range(len(states)):
        config = zone_configs[zone_idx]
        device_count = config.get('device_count', 16)
        quota = config.get('energy_quota', float('inf'))
        current_energy = calculate_zone_energy(states[zone_idx], device_count)
        
        if current_energy > quota:
            priority_devices = normalize_priority_devices(config.get('priority_devices', {}))
            for device_idx in range(device_count):
                if device_idx in priority_devices:
                    continue
                
                state = get_device_state(states[zone_idx], device_idx)
                if state > 0:
                    states[zone_idx] = set_device_state(states[zone_idx], device_idx, state - 1)
                    improved = True
                    break
    return improved


def apply_inter_zone_dependency_constraints(states, inter_zone_deps):
    """Apply inter-zone dependency constraints."""
    improved = False
    for zone_a, device_a, zone_b, min_state_b in inter_zone_deps:
        if zone_a >= len(states) or zone_b >= len(states):
            continue
        state_a = get_device_state(states[zone_a], device_a)
        if state_a > 0:
            state_b = get_device_state(states[zone_b], device_a)
            if state_b < min_state_b:
                states[zone_b] = set_device_state(states[zone_b], device_a, min_state_b)
                improved = True
    return improved


def apply_mutual_exclusion_constraints(states, mutual_exclusion_groups):
    """Apply mutual exclusion constraints."""
    improved = False
    for group in mutual_exclusion_groups:
        peak_devices = []
        for zone_idx, device_idx in group:
            if zone_idx < len(states):
                state = get_device_state(states[zone_idx], device_idx)
                if state == 3:
                    peak_devices.append((zone_idx, device_idx))
        
        if len(peak_devices) > 1:
            for zone_idx, device_idx in peak_devices[1:]:
                states[zone_idx] = set_device_state(states[zone_idx], device_idx, 2)
                improved = True
    return improved


def apply_global_energy_constraints(states, zone_configs, global_energy_limit):
    """Apply global energy limit constraints."""
    improved = False
    total_energy = calculate_total_energy(states, zone_configs)
    if total_energy > global_energy_limit:
        for zone_idx in range(len(states)):
            config = zone_configs[zone_idx]
            device_count = config.get('device_count', 16)
            priority_devices = normalize_priority_devices(config.get('priority_devices', {}))
            for device_idx in range(device_count):
                if device_idx in priority_devices:
                    continue
                state = get_device_state(states[zone_idx], device_idx)
                if state > 0:
                    states[zone_idx] = set_device_state(states[zone_idx], device_idx, state - 1)
                    improved = True
                    total_energy = calculate_total_energy(states, zone_configs)
                    if total_energy <= global_energy_limit:
                        break
            if total_energy <= global_energy_limit:
                break
    return improved


def apply_grid_segment_constraints(states, zone_configs, grid_segments):
    """Apply grid segment capacity constraints."""
    improved = False
    for segment in grid_segments:
        zones = segment.get('zones_in_segment', [])
        capacity = segment.get('segment_capacity', float('inf'))
        
        segment_energy = 0
        for zone_idx in zones:
            if zone_idx < len(states):
                device_count = zone_configs[zone_idx].get('device_count', 16)
                segment_energy += calculate_zone_energy(states[zone_idx], device_count)
        
        if segment_energy > capacity:
            for zone_idx in zones:
                if zone_idx >= len(states):
                    continue
                config = zone_configs[zone_idx]
                device_count = config.get('device_count', 16)
                priority_devices = normalize_priority_devices(config.get('priority_devices', {}))
                for device_idx in range(device_count):
                    if device_idx in priority_devices:
                        continue
                    state = get_device_state(states[zone_idx], device_idx)
                    if state > 0:
                        states[zone_idx] = set_device_state(states[zone_idx], device_idx, state - 1)
                        improved = True
                        segment_energy = sum(
                            calculate_zone_energy(states[z], zone_configs[z].get('device_count', 16))
                            for z in zones if z < len(states)
                        )
                        if segment_energy <= capacity:
                            break
                if segment_energy <= capacity:
                    break
    return improved


def greedy_optimize(states, zone_configs, grid_segments, inter_zone_deps,
                   weather_conditions, global_energy_limit, mutual_exclusion_groups,
                   synchronization_groups, cascading_propagation, original_states):
    """Greedy optimization using centralized constraint application functions."""
    
    max_iterations = 50
    for iteration in range(max_iterations):
        if validate_all_constraints(states, zone_configs, grid_segments, inter_zone_deps,
                                    weather_conditions, global_energy_limit, mutual_exclusion_groups,
                                    synchronization_groups, cascading_propagation):
            return states
        
        improved = False
        
        # Apply all constraints using centralized functions
        improved |= apply_device_dependencies(states, zone_configs)
        improved |= apply_cascading_propagation_constraints(states, cascading_propagation)
        improved |= apply_energy_quota_constraints(states, zone_configs)
        improved |= apply_inter_zone_dependency_constraints(states, inter_zone_deps)
        improved |= apply_mutual_exclusion_constraints(states, mutual_exclusion_groups)
        improved |= apply_global_energy_constraints(states, zone_configs, global_energy_limit)
        improved |= apply_grid_segment_constraints(states, zone_configs, grid_segments)
        
        if not improved:
            break
    
    if validate_all_constraints(states, zone_configs, grid_segments, inter_zone_deps,
                                weather_conditions, global_energy_limit, mutual_exclusion_groups,
                                synchronization_groups, cascading_propagation):
        return states
    
    return None


def backtracking_optimize(zone_states, zone_configs, grid_segments, inter_zone_deps,
                         weather_conditions, global_energy_limit, mutual_exclusion_groups,
                         synchronization_groups, cascading_propagation, transition_cost_matrices):
    """Backtracking search to find optimal solution with weighted objective function."""
    
    num_zones = len(zone_states)
    best_solution = None
    best_cost = float('inf')
    
    def backtrack(current_states, zone_idx, device_idx, depth):
        nonlocal best_solution, best_cost
        
        # Limit backtracking depth to prevent infinite recursion
        if depth > 8:
            return
        
        # If we've explored all devices in all zones
        if zone_idx >= num_zones:
            if validate_all_constraints(current_states, zone_configs, grid_segments, inter_zone_deps,
                                      weather_conditions, global_energy_limit, mutual_exclusion_groups,
                                      synchronization_groups, cascading_propagation):
                
                # Calculate weighted cost
                total_energy = calculate_total_energy(current_states, zone_configs)
                total_transition_cost = calculate_transition_cost(zone_states, current_states, 
                                                                transition_cost_matrices, zone_configs)
                weighted_cost = 0.7 * total_energy + 0.3 * total_transition_cost
                
                # Calculate load balance score for tie-breaking
                load_balance_score = calculate_load_balance_score(current_states, grid_segments, zone_configs)
                
                # Update best solution if this is better
                if (weighted_cost < best_cost - 0.01 or 
                    (abs(weighted_cost - best_cost) <= 0.01 and 
                     (best_solution is None or load_balance_score < best_solution[1]))):
                    best_solution = (current_states[:], load_balance_score)
                    best_cost = weighted_cost
            
            return
        
        # Get current device count for this zone
        device_count = zone_configs[zone_idx].get('device_count', 16)
        
        # If we've explored all devices in current zone, move to next zone
        if device_idx >= device_count:
            backtrack(current_states, zone_idx + 1, 0, depth)
            return
        
        # Try all possible states for current device
        for new_state in [0, 1, 2, 3]:
            # Skip if no change
            if get_device_state(current_states[zone_idx], device_idx) == new_state:
                continue
            
            # Make the change
            old_state = current_states[zone_idx]
            current_states[zone_idx] = set_device_state(current_states[zone_idx], device_idx, new_state)
            
            # Check if this change maintains basic constraints
            if validate_zone_constraints(current_states[zone_idx], zone_configs[zone_idx], zone_idx):
                # Apply cascading propagation
                temp_states = apply_cascading_propagation(current_states, cascading_propagation)
                
                # Continue backtracking
                backtrack(temp_states, zone_idx, device_idx + 1, depth + 1)
            
            # Restore state
            current_states[zone_idx] = old_state
    
    # Start backtracking
    initial_states = list(zone_states)
    apply_mandatory_constraints(
        initial_states, zone_configs, weather_conditions, 
        synchronization_groups, cascading_propagation
    )
    
    backtrack(initial_states, 0, 0, 0)
    
    return best_solution[0] if best_solution else []


def apply_cascading_propagation(states, cascading_propagation):
    """Apply cascading propagation rules iteratively until fixed point."""
    states = states[:]
    max_iterations = 10
    
    for _ in range(max_iterations):
        # Use centralized constraint application function
        changed = apply_cascading_propagation_constraints(states, cascading_propagation)
        if not changed:
            break
    
    return states


def get_device_state(bitmask, device_idx):
    return (bitmask >> (device_idx * 2)) & 0b11


def set_device_state(bitmask, device_idx, state):
    mask = ~(0b11 << (device_idx * 2))
    bitmask = bitmask & mask
    bitmask = bitmask | (state << (device_idx * 2))
    return bitmask


def calculate_zone_energy(bitmask, device_count):
    energy_map = {0: 0, 1: 1, 2: 3, 3: 5}
    total = 0
    for i in range(device_count):
        state = get_device_state(bitmask, i)
        total += energy_map[state]
    return total


def calculate_total_energy(states, zone_configs):
    total = 0
    for i, bitmask in enumerate(states):
        device_count = zone_configs[i].get('device_count', 16)
        total += calculate_zone_energy(bitmask, device_count)
    return total


def calculate_transition_cost(old_states, new_states, transition_cost_matrices, zone_configs):
    if not transition_cost_matrices:
        total = 0
        for old, new in zip(old_states, new_states):
            if old != new:
                total += 1
        return total
    
    total = 0
    for zone_idx, (old_bitmask, new_bitmask) in enumerate(zip(old_states, new_states)):
        device_count = zone_configs[zone_idx].get('device_count', 16)
        if zone_idx >= len(transition_cost_matrices):
            continue
        
        zone_matrix = transition_cost_matrices[zone_idx]
        for device_idx in range(device_count):
            old_state = get_device_state(old_bitmask, device_idx)
            new_state = get_device_state(new_bitmask, device_idx)
            
            if device_idx < len(zone_matrix):
                device_matrix = zone_matrix[device_idx]
                if old_state < len(device_matrix) and new_state < len(device_matrix[old_state]):
                    total += device_matrix[old_state][new_state]
    
    return total


def validate_all_constraints(states, zone_configs, grid_segments, inter_zone_deps,
                             weather_conditions, global_energy_limit, mutual_exclusion_groups,
                             synchronization_groups, cascading_propagation):
    
    for i, (bitmask, config) in enumerate(zip(states, zone_configs)):
        if not validate_zone_constraints(bitmask, config, i):
            return False
    
    if not validate_weather_constraints(states, weather_conditions):
        return False
    
    if not validate_inter_zone_deps(states, inter_zone_deps):
        return False
    
    if not validate_grid_segments(states, grid_segments, zone_configs):
        return False
    
    total_energy = calculate_total_energy(states, zone_configs)
    if total_energy > global_energy_limit:
        return False
    
    if not validate_mutual_exclusion(states, mutual_exclusion_groups):
        return False
    
    if not validate_synchronization_groups(states, synchronization_groups):
        return False
    
    if not validate_cascading_propagation(states, cascading_propagation):
        return False
    
    return True


def validate_zone_constraints(bitmask, config, zone_idx):
    device_count = config.get('device_count', 16)
    
    priority_devices = normalize_priority_devices(config.get('priority_devices', {}))
    for device_idx, min_state in priority_devices.items():
        if device_idx >= device_count:
            continue
        state = get_device_state(bitmask, device_idx)
        if state < min_state:
            return False
    
    device_dependencies = config.get('device_dependencies', [])
    for device_idx, required_device_idx, min_state in device_dependencies:
        if device_idx >= device_count or required_device_idx >= device_count:
            continue
        required_state = get_device_state(bitmask, required_device_idx)
        if required_state > 0:
            device_state = get_device_state(bitmask, device_idx)
            if device_state < min_state:
                return False
    
    energy = calculate_zone_energy(bitmask, device_count)
    quota = config.get('energy_quota', float('inf'))
    if energy > quota:
        return False
    
    return True


def validate_weather_constraints(states, weather_conditions):
    if not weather_conditions:
        return True
    
    temperature = weather_conditions.get('temperature', 0)
    threshold = weather_conditions.get('high_temp_threshold', float('inf'))
    
    if temperature <= threshold:
        return True
    
    devices_affected = weather_conditions.get('devices_affected', [])
    for zone_idx, device_idx in devices_affected:
        if zone_idx >= len(states):
            continue
        state = get_device_state(states[zone_idx], device_idx)
        if state < 2:
            return False
    
    return True


def validate_inter_zone_deps(states, inter_zone_deps):
    for zone_a, device_a, zone_b, min_state_b in inter_zone_deps:
        if zone_a >= len(states) or zone_b >= len(states):
            continue
        
        state_a = get_device_state(states[zone_a], device_a)
        if state_a > 0:
            state_b = get_device_state(states[zone_b], device_a)
            if state_b < min_state_b:
                return False
    
    return True


def validate_grid_segments(states, grid_segments, zone_configs):
    for segment in grid_segments:
        zones = segment.get('zones_in_segment', [])
        capacity = segment.get('segment_capacity', float('inf'))
        load_balance_required = segment.get('load_balance_required', False)
        
        total_energy = 0
        zone_energies = []
        
        for zone_idx in zones:
            if zone_idx >= len(states):
                continue
            device_count = zone_configs[zone_idx].get('device_count', 16)
            energy = calculate_zone_energy(states[zone_idx], device_count)
            total_energy += energy
            zone_energies.append(energy)
        
        if total_energy > capacity:
            return False
        
        if load_balance_required and capacity > 0 and len(zones) > 0 and len(zone_energies) > 1:
            utilizations = [e / (capacity / len(zones)) for e in zone_energies]
            if utilizations:
                max_util = max(utilizations)
                min_util = min(utilizations)
                if max_util - min_util > 0.4:
                    return False
    
    return True


def validate_mutual_exclusion(states, mutual_exclusion_groups):
    for group in mutual_exclusion_groups:
        peak_count = 0
        for zone_idx, device_idx in group:
            if zone_idx >= len(states):
                continue
            state = get_device_state(states[zone_idx], device_idx)
            if state == 3:
                peak_count += 1
        
        if peak_count > 1:
            return False
    
    return True


def validate_synchronization_groups(states, synchronization_groups):
    for group in synchronization_groups:
        if not group:
            continue
        
        zone_idx_0, device_idx_0 = group[0]
        if zone_idx_0 >= len(states):
            continue
        reference_state = get_device_state(states[zone_idx_0], device_idx_0)
        
        for zone_idx, device_idx in group[1:]:
            if zone_idx >= len(states):
                continue
            state = get_device_state(states[zone_idx], device_idx)
            if state != reference_state:
                return False
    
    return True


def validate_cascading_propagation(states, cascading_propagation):
    max_iterations = 10
    for _ in range(max_iterations):
        changed = False
        for zone_from, device_from, zone_to, device_to in cascading_propagation:
            if zone_from >= len(states) or zone_to >= len(states):
                continue
            
            state_from = get_device_state(states[zone_from], device_from)
            state_to = get_device_state(states[zone_to], device_to)
            
            required_state = max(1, state_from - 1) if state_from > 0 else 0
            
            if state_from > 0 and state_to < required_state:
                return False
        
        if not changed:
            break
    
    return True




def calculate_load_balance_score(states, grid_segments, zone_configs):
    total_variance = 0
    
    for segment in grid_segments:
        zones = segment.get('zones_in_segment', [])
        capacity = segment.get('segment_capacity', 1)
        
        utilizations = []
        for zone_idx in zones:
            if zone_idx >= len(states):
                continue
            device_count = zone_configs[zone_idx].get('device_count', 16)
            energy = calculate_zone_energy(states[zone_idx], device_count)
            util = energy / (capacity / len(zones)) if capacity > 0 and len(zones) > 0 else 0
            utilizations.append(util)
        
        if len(utilizations) > 1:
            mean = sum(utilizations) / len(utilizations)
            variance = sum((u - mean) ** 2 for u in utilizations) / len(utilizations)
            total_variance += variance
    
    return total_variance


def check_zone_internal_contradictions(config, synchronization_groups, zone_idx):
    priority_devices = normalize_priority_devices(config.get('priority_devices', {}))
    device_count = config.get('device_count', 16)
    quota = config.get('energy_quota', float('inf'))
    
    energy_map = {0: 0, 1: 1, 2: 3, 3: 5}
    min_energy = sum(energy_map[priority_devices.get(i, 0)] for i in range(device_count))
    
    if min_energy > quota:
        return True
    
    for group in synchronization_groups:
        devices_in_zone = [(z, d) for z, d in group if z == zone_idx]
        if len(devices_in_zone) > 1:
            required_states = [priority_devices.get(d, -1) for z, d in devices_in_zone]
            required_states = [s for s in required_states if s >= 0]
            if len(set(required_states)) > 1:
                return True
    
    return False