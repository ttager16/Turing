from typing import List, Dict, Any, Set, Tuple


def allocate_minimum_teams(projects: List[Dict[str, Any]], teams: List[Dict[str, Any]]) -> int:
    """
    Find the minimum number of teams required to complete all projects within deadlines.
    Uses binary search to optimize the allocation.
    
    CLEAR RULES:
    1. Each phase takes exactly 1 day to complete
    2. A team can only work on ONE phase at a time (no parallel work)
    3. Team availability is the total number of days they can work
    4. Phases can be scheduled on any day from 0 to (deadline - 1)
    5. A team needs ALL required skills collectively to work on a phase
    6. Phases from different projects are independent and can be done in any order
    
    Args:
        projects: List of project dictionaries with phases and deadlines
        teams: List of team dictionaries with members and availability
    
    Returns:
        Minimum number of teams needed, or -1 if impossible
    """
    if not projects:
        return 0
    
    if not teams:
        return -1
    
    # Binary search on number of teams
    left, right = 1, len(teams)
    result = -1
    
    while left <= right:
        mid = (left + right) // 2
        
        if can_complete_with_k_teams(projects, teams[:mid]):
            result = mid
            right = mid - 1
        else:
            left = mid + 1
    
    return result


def can_complete_with_k_teams(projects: List[Dict[str, Any]], 
                                selected_teams: List[Dict[str, Any]]) -> bool:
    """
    Check if k teams can complete all project phases within their deadlines.
    Uses a greedy approach: assign each phase to the earliest available capable team.
    
    Args:
        projects: List of projects with phases
        selected_teams: List of k teams to check
    
    Returns:
        True if all phases can be completed, False otherwise
    """
    # Collect all phases from all projects with their deadlines
    all_phases = []
    
    for project in projects:
        project_deadline = project.get('project_deadline', float('inf'))
        phases = project.get('phases', [])
        
        for phase in phases:
            # Effective deadline is minimum of phase deadline and project deadline
            phase_deadline = min(phase.get('deadline', float('inf')), project_deadline)
            required_skills = set(phase.get('required_skills', []))
            
            all_phases.append({
                'required_skills': required_skills,
                'deadline': phase_deadline
            })
    
    # Sort phases by deadline (earliest first) - greedy strategy
    all_phases.sort(key=lambda x: x['deadline'])
    
    # Track each team's schedule: list of (start_day, end_day) tuples
    team_schedules = [[] for _ in range(len(selected_teams))]
    
    # Try to assign each phase to a team
    for phase in all_phases:
        required_skills = phase['required_skills']
        deadline = phase['deadline']
        
        # Find a team that can do this phase
        assigned = False
        
        for team_idx, team in enumerate(selected_teams):
            # Check if team has the required skills
            if not team_has_skills(team, required_skills):
                continue
            
            base_availability = team.get('base_availability', 0)
            schedule = team_schedules[team_idx]
            
            # Find earliest slot where this team can work (phase takes 1 day)
            earliest_start = find_earliest_slot(schedule, base_availability, 1, deadline)
            
            if earliest_start is not None:
                # Assign this phase to this team
                schedule.append((earliest_start, earliest_start + 1))
                schedule.sort()
                assigned = True
                break
        
        if not assigned:
            return False
    
    return True


def team_has_skills(team: Dict[str, Any], required_skills: Set[str]) -> bool:
    """
    Check if a team collectively has all required skills.
    
    Args:
        team: Team dictionary with members
        required_skills: Set of required skills
    
    Returns:
        True if team has all skills, False otherwise
    """
    if not required_skills:
        return True
    
    team_skills = set()
    for member in team.get('members', []):
        team_skills.update(member.get('skills', []))
    
    return required_skills.issubset(team_skills)


def find_earliest_slot(schedule: List[Tuple[int, int]], 
                       max_availability: int, 
                       duration: int,
                       deadline: int) -> int:
    """
    Find the earliest available time slot in a schedule.
    
    LOGIC:
    - Schedule contains busy periods: [(start, end), ...]
    - Need to find a gap of 'duration' days
    - Must complete before 'deadline' (so start + duration <= deadline)
    - Total work cannot exceed max_availability
    
    Args:
        schedule: Sorted list of (start, end) tuples representing busy times
        max_availability: Maximum days the team can work (total)
        duration: Duration needed for the task (always 1 day for our problem)
        deadline: Latest time the task must complete
    
    Returns:
        Earliest start time (day number), or None if no slot available
    """
    # Cannot schedule if invalid constraints
    if duration > max_availability or duration > deadline or deadline <= 0:
        return None
    
    # Calculate total days already used
    total_used = sum(end - start for start, end in schedule)
    
    # Check if adding this phase would exceed availability
    if total_used + duration > max_availability:
        return None
    
    # If no schedule yet, start at day 0
    if not schedule:
        return 0 if duration <= deadline else None
    
    # Try to fit before first scheduled item
    if schedule[0][0] >= duration and duration <= deadline:
        return 0
    
    # Try to fit in gaps between scheduled items
    for i in range(len(schedule) - 1):
        gap_start = schedule[i][1]
        gap_end = schedule[i + 1][0]
        gap_size = gap_end - gap_start
        
        if gap_size >= duration and gap_start + duration <= deadline:
            return gap_start
    
    # Try to fit after last scheduled item
    last_end = schedule[-1][1]
    if last_end + duration <= deadline:
        return last_end
    
    return None