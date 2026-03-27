from typing import List, Dict, Set
from collections import defaultdict

def allocate_minimum_sessions(
    departments: List[List[int]],     # <- changed from List[Tuple[int, int, int]]
    conflicts: List[List[int]],       # <- changed from List[Tuple[int, int]]
    session_capacity: int
) -> int:
    if not departments:
        return 0
    
    n = len(departments)
    
    if any(dept[0] > session_capacity for dept in departments):
        return -1
    
    synergy_groups = defaultdict(list)
    for idx, (cap, synergy, res) in enumerate(departments):
        if synergy > 0:
            synergy_groups[synergy].append(idx)
    
    for group_id, members in synergy_groups.items():
        total_cap = sum(departments[idx][0] for idx in members)
        if total_cap > session_capacity:
            return -1
    
    conflict_set = set()
    for i, j in conflicts:
        conflict_set.add((min(i, j), max(i, j)))
    
    for group_id, members in synergy_groups.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pair = (min(members[i], members[j]), max(members[i], members[j]))
                if pair in conflict_set:
                    return -1
    
    merged_units = []
    dept_to_unit = {}
    unit_id = 0
    
    for group_id, members in synergy_groups.items():
        total_cap = sum(departments[idx][0] for idx in members)
        resources = set(departments[idx][2] for idx in members if departments[idx][2] > 0)
        merged_units.append({
            'id': unit_id,
            'capacity': total_cap,
            'departments': members,
            'resources': resources
        })
        for member in members:
            dept_to_unit[member] = unit_id
        unit_id += 1
    
    for idx in range(n):
        if idx not in dept_to_unit:
            cap, _, res = departments[idx]
            resources = {res} if res > 0 else set()
            merged_units.append({
                'id': unit_id,
                'capacity': cap,
                'departments': [idx],
                'resources': resources
            })
            dept_to_unit[idx] = unit_id
            unit_id += 1
    
    final_units = merged_units
    merged_unit_map = {unit['id']: idx for idx, unit in enumerate(final_units)}
    
    unit_conflicts = defaultdict(set)
    
    for i, j in conflicts:
        if i < n and j < n:
            unit_i = merged_unit_map.get(dept_to_unit[i])
            unit_j = merged_unit_map.get(dept_to_unit[j])
            if unit_i is not None and unit_j is not None and unit_i != unit_j:
                unit_conflicts[unit_i].add(unit_j)
                unit_conflicts[unit_j].add(unit_i)
    
    for i in range(len(final_units)):
        for j in range(i + 1, len(final_units)):
            unit_i = final_units[i]
            unit_j = final_units[j]
            shared_resources = unit_i['resources'] & unit_j['resources']
            if shared_resources:
                unit_conflicts[i].add(j)
                unit_conflicts[j].add(i)
    
    num_units = len(final_units)
    
    def is_valid_session(mask: int) -> bool:
        total_capacity = 0
        for i in range(num_units):
            if mask & (1 << i):
                total_capacity += final_units[i]['capacity']
                if total_capacity > session_capacity:
                    return False
                
                for j in range(i + 1, num_units):
                    if mask & (1 << j):
                        if j in unit_conflicts[i]:
                            return False
        return True
    
    dp = {}
    dp[0] = 0
    
    for mask in range(1, 1 << num_units):
        dp[mask] = float('inf')
        
        subset = mask
        while subset > 0:
            if is_valid_session(subset):
                remaining = mask ^ subset
                dp[mask] = min(dp[mask], 1 + dp[remaining])
            subset = (subset - 1) & mask
    
    result = dp[(1 << num_units) - 1]
    return result if result != float('inf') else -1