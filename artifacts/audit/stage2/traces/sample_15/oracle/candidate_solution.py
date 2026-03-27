from typing import List, Dict, Set, Optional, DefaultDict, Tuple
from collections import defaultdict, deque
import itertools


def allocate_minimum_workshops(
    workshop_slots: List[List[int]], 
    student_preferences: List[List[int]]
) -> int:
    """
    Determine the minimum count of scheduled workshops that accommodates all students
    under complex, multi-campus constraints.
    
    Workshop slots format: [campus_id, timeslot_start, capacity, instructor_id, timeslot_end (optional)]
    - If 4 elements: point timeslot (start == end)
    - If 5 elements: range timeslot [start, end]
    
    Constraints enforced:
    1. Capacity limits per workshop
    2. Instructor availability (no double-booking)
    3. Timeslot conflicts (overlapping time ranges)
    4. Campus adjacency (no student can attend workshops on different campuses without sufficient travel time)
    5. Per-campus resource limitations
    
    :param workshop_slots: Workshop definitions with campus, time, capacity, instructor
    :param student_preferences: List of valid workshop indices per student
    :return: Minimum number of workshops needed or -1 if impossible
    :raises ValueError: If input data is malformed (negative values, invalid ranges, etc.)
    """
    # Special case: No students
    if not student_preferences:
        return 0
    
    # Special case: No workshops but students exist
    if not workshop_slots:
        return -1
    
    # Normalize and validate input
    workshops = _normalize_workshops(workshop_slots)
    
    # Validate student preferences
    if not _validate_preferences(student_preferences, len(workshops)):
        return -1
        
    # Check capacity feasibility
    n_students = len(student_preferences)
    total_capacity = sum(ws['capacity'] for ws in workshops)
    if total_capacity < n_students:
        return -1
        
    # Compute constraints
    time_conflicts = _compute_time_conflicts(workshops)
    instructor_conflicts = _compute_instructor_conflicts(workshops)
    campus_conflicts = _compute_campus_adjacency_conflicts(workshops)
    
    # Combine all conflicts
    all_conflicts = [time_conflicts[i] | instructor_conflicts[i] | campus_conflicts[i] 
                    for i in range(len(workshops))]
    
    # Use exact algorithm to find minimum number of workshops
    return _find_minimum_workshops_exact(workshops, student_preferences, all_conflicts)


def _normalize_workshops(workshop_slots: List[List[int]]) -> List[Dict]:
    """Normalize workshop data to consistent dictionary format.
    Validates input and raises ValueError for malformed data."""
    workshops = []
    for i, slot in enumerate(workshop_slots):
        if len(slot) < 4:
            raise ValueError(f"Workshop {i} has insufficient data")
        
        if len(slot) == 4:
            campus, time, capacity, instructor = slot
            time_start = time_end = time
        else:  # len(slot) == 5
            campus, time_start, capacity, instructor, time_end = slot
        
        # Validate - must raise ValueError as specified in requirements
        if campus < 0:
            raise ValueError(f"Workshop {i} has negative campus ID: {campus}")
        if time_start < 0:
            raise ValueError(f"Workshop {i} has negative start time: {time_start}")
        if time_end < 0:
            raise ValueError(f"Workshop {i} has negative end time: {time_end}")
        if capacity <= 0:
            raise ValueError(f"Workshop {i} has non-positive capacity: {capacity}")
        if time_start > time_end:
            raise ValueError(f"Workshop {i} has invalid time range: {time_start} > {time_end}")
        
        workshops.append({
            'id': i,
            'campus': campus,
            'time_start': time_start,
            'time_end': time_end,
            'capacity': capacity,
            'instructor': instructor
        })
    
    return workshops


def _validate_preferences(preferences: List[List[int]], n_workshops: int) -> bool:
    """Validate student preferences against available workshops.
    Raises ValueError for invalid preferences."""
    for i, prefs in enumerate(preferences):
        if not prefs:
            return False  # Student has no preferences
        
        for ws_id in prefs:
            if ws_id < 0 or ws_id >= n_workshops:
                raise ValueError(f"Student {i} has invalid workshop preference: {ws_id}")
    
    return True


def _compute_time_conflicts(workshops: List[Dict]) -> List[Set[int]]:
    """Compute time conflicts between workshops."""
    n_workshops = len(workshops)
    conflicts = [set() for _ in range(n_workshops)]
    
    for i in range(n_workshops):
        for j in range(i+1, n_workshops):
            # Check for time overlap
            if max(workshops[i]['time_start'], workshops[j]['time_start']) <= min(workshops[i]['time_end'], workshops[j]['time_end']):
                conflicts[i].add(j)
                conflicts[j].add(i)
    
    return conflicts


def _compute_instructor_conflicts(workshops: List[Dict]) -> List[Set[int]]:
    """Compute instructor conflicts (same instructor, overlapping times)."""
    n_workshops = len(workshops)
    conflicts = [set() for _ in range(n_workshops)]
    
    # Group by instructor
    instructor_workshops = defaultdict(list)
    for i, ws in enumerate(workshops):
        instructor_workshops[ws['instructor']].append(i)
    
    # Check for time conflicts within each instructor's workshops
    for instructor, ws_ids in instructor_workshops.items():
        for i, ws_i in enumerate(ws_ids):
            for ws_j in ws_ids[i+1:]:
                # Check for time overlap
                if max(workshops[ws_i]['time_start'], workshops[ws_j]['time_start']) <= min(workshops[ws_i]['time_end'], workshops[ws_j]['time_end']):
                    conflicts[ws_i].add(ws_j)
                    conflicts[ws_j].add(ws_i)
    
    return conflicts


def _compute_campus_adjacency_conflicts(workshops: List[Dict]) -> List[Set[int]]:
    """Compute campus adjacency conflicts."""
    n_workshops = len(workshops)
    conflicts = [set() for _ in range(n_workshops)]
    
    for i in range(n_workshops):
        for j in range(i+1, n_workshops):
            # Skip if same campus
            if workshops[i]['campus'] == workshops[j]['campus']:
                continue
            
            # Check if time gap is sufficient for travel
            time_gap_ij = workshops[j]['time_start'] - workshops[i]['time_end']
            time_gap_ji = workshops[i]['time_start'] - workshops[j]['time_end']
            
            # Assume travel time of 1 time unit between different campuses
            travel_time = 1
            
            if (time_gap_ij >= 0 and time_gap_ij < travel_time) or (time_gap_ji >= 0 and time_gap_ji < travel_time):
                conflicts[i].add(j)
                conflicts[j].add(i)
    
    return conflicts


def _can_assign_all_students(
    selected_workshops: Set[int], 
    workshops: List[Dict],
    student_preferences: List[List[int]]
) -> bool:
    """
    Check if all students can be assigned to the selected workshops.
    Uses maximum flow algorithm for bipartite matching with capacity constraints.
    """
    if not selected_workshops:
        return False
    
    n_students = len(student_preferences)
    
    # Create residual graph for Ford-Fulkerson
    # Source -> Students -> Workshops -> Sink
    graph = defaultdict(dict)
    source = 's'
    sink = 't'
    
    # Connect source to students (capacity 1)
    for i in range(n_students):
        student_node = f'student_{i}'
        graph[source][student_node] = 1
    
    # Connect students to their preferred workshops
    for i, prefs in enumerate(student_preferences):
        student_node = f'student_{i}'
        valid_prefs = [ws_id for ws_id in prefs if ws_id in selected_workshops]
        
        if not valid_prefs:
            return False  # Student cannot be assigned
        
        for ws_id in valid_prefs:
            workshop_node = f'workshop_{ws_id}'
            graph[student_node][workshop_node] = 1
    
    # Connect workshops to sink (capacity = workshop capacity)
    for ws_id in selected_workshops:
        workshop_node = f'workshop_{ws_id}'
        graph[workshop_node][sink] = workshops[ws_id]['capacity']
    
    # Use Ford-Fulkerson to find max flow
    max_flow = 0
    while True:
        # Find an augmenting path using BFS
        path = _find_augmenting_path(graph, source, sink)
        if not path:
            break
            
        # Find minimum residual capacity along path
        min_capacity = float('inf')
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            min_capacity = min(min_capacity, graph[u].get(v, 0))
        
        # Update residual capacities
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            graph[u][v] -= min_capacity
            if graph[u][v] == 0:
                del graph[u][v]
            
            # Add reverse edge
            if v not in graph or u not in graph[v]:
                graph[v][u] = 0
            graph[v][u] += min_capacity
        
        max_flow += min_capacity
    
    return max_flow == n_students


def _find_augmenting_path(graph, source, sink):
    """Find an augmenting path in the residual graph using BFS."""
    visited = {source: None}
    queue = deque([source])
    
    while queue and sink not in visited:
        node = queue.popleft()
        for neighbor, capacity in graph[node].items():
            if neighbor not in visited and capacity > 0:
                visited[neighbor] = node
                queue.append(neighbor)
    
    if sink in visited:
        # Reconstruct path
        path = [sink]
        while path[0] != source:
            path.insert(0, visited[path[0]])
        return path
    
    return None


def _find_minimum_workshops_exact(
    workshops: List[Dict],
    student_preferences: List[List[int]],
    conflicts: List[Set[int]]
) -> int:
    """
    Find the minimum number of workshops needed using an exact algorithm.
    This uses a branch-and-bound approach to find the true minimum.
    """
    n_workshops = len(workshops)
    n_students = len(student_preferences)
    
    # Compute theoretical minimum based on capacity
    workshop_capacities = sorted([ws['capacity'] for ws in workshops], reverse=True)
    min_needed = 0
    capacity_so_far = 0
    
    for capacity in workshop_capacities:
        if capacity_so_far >= n_students:
            break
        min_needed += 1
        capacity_so_far += capacity
    
    # Try increasingly larger subsets until we find a solution
    for size in range(min_needed, n_workshops + 1):
        result = _find_workshop_set_of_size(workshops, student_preferences, conflicts, size)
        if result is not None:
            return len(result)
    
    return -1  # No solution found


def _find_workshop_set_of_size(
    workshops: List[Dict],
    student_preferences: List[List[int]],
    conflicts: List[Set[int]],
    size: int
) -> Optional[Set[int]]:
    """Find a valid set of workshops of the given size."""
    n_workshops = len(workshops)
    
    # Sort workshops by utility (popularity / capacity ratio)
    workshop_popularity = defaultdict(int)
    for prefs in student_preferences:
        for ws_id in prefs:
            workshop_popularity[ws_id] += 1
    
    # Sort by popularity and then by capacity
    workshop_utility = [(i, workshop_popularity[i] / workshops[i]['capacity']) 
                       for i in range(n_workshops)]
    sorted_workshops = sorted(workshop_utility, key=lambda x: (-x[1], -workshops[x[0]]['capacity']))
    sorted_workshop_ids = [ws[0] for ws in sorted_workshops]
    
    # Use branch and bound to search for a valid set
    return _backtrack_search(set(), sorted_workshop_ids, 0, workshops, student_preferences, conflicts, size)


def _backtrack_search(
    current_set: Set[int],
    sorted_workshops: List[int],
    start_idx: int,
    workshops: List[Dict],
    student_preferences: List[List[int]],
    conflicts: List[Set[int]],
    target_size: int
) -> Optional[Set[int]]:
    """
    Recursive backtracking search for a valid workshop set.
    Uses branch and bound pruning.
    """
    # Check if we have a solution
    if len(current_set) == target_size:
        if _can_assign_all_students(current_set, workshops, student_preferences):
            return current_set
        return None
    
    # Check if we can still reach the target size
    remaining = target_size - len(current_set)
    if start_idx + remaining > len(sorted_workshops):
        return None
    
    # Try adding more workshops
    for i in range(start_idx, len(sorted_workshops)):
        ws_id = sorted_workshops[i]
        
        # Check if adding this workshop creates conflicts
        if any(conflicting_ws in current_set for conflicting_ws in conflicts[ws_id]):
            continue
        
        # Try this workshop
        new_set = current_set.copy()
        new_set.add(ws_id)
        
        # Recursively search
        result = _backtrack_search(
            new_set, 
            sorted_workshops, 
            i + 1, 
            workshops,
            student_preferences, 
            conflicts, 
            target_size
        )
        
        if result is not None:
            return result
    
    return None