from typing import List, Dict, Any


def _get_effective_pmax(usine: Dict[str, Any], consecutive_on: int) -> float:
    """
    Helper function to determine the effective P-max of a usine based on
    how many consecutive time steps it has been on.
    """
    # Iterate through the ramping curve to find the current P-max.
    # The curve is assumed to be sorted by the number of steps.
    for steps, p_max_val in sorted(usine['ramping_curve']):
        if consecutive_on <= steps:
            return p_max_val

    # If consecutive_on exceeds all defined steps, use the last p_max value in the curve.
    # If the curve is empty, default to the usine's absolute p_max.
    if usine['ramping_curve']:
        return usine['ramping_curve'][-1][1]
    return usine['p_max']


def calculate_total_cost(
        demand_schedule: List[float],
        usines: List[Dict[str, Any]],
        on_off_schedule: List[List[bool]]
) -> float:
    """
    Calculates the total cost of a given on/off schedule for a set of usines
    against a demand schedule, considering all operational constraints.

    Args:
        demand_schedule: A list of power demands for each time step.
        usines: A list of dictionaries, where each dict contains the properties
                of a usine (e.g., 'name', 'cost_per_kwh', 'p_min', 'p_max',
                't_on', 't_off', 'ramping_curve').
        on_off_schedule: A 2D list where schedule[t][i] is True if usine i
                         is on at time t, and False otherwise.

    Returns:
        The total cost if the schedule is valid, or float('inf') if any
        constraint is violated.
    """
    num_usines = len(usines)
    num_timesteps = len(demand_schedule)

    # --- 1. Validate T_on and T_off Constraints ---
    # This is done first as a fast check for invalid schedules.
    for i in range(num_usines):
        usine = usines[i]
        for t in range(num_timesteps):
            # Check for an ON-trigger event (was OFF, now ON)
            if on_off_schedule[t][i] and (t == 0 or not on_off_schedule[t - 1][i]):
                # Check if it stays on for the required T_on duration
                for k in range(t, t + usine['t_on']):
                    if k >= num_timesteps or not on_off_schedule[k][i]:
                        return float('inf')  # T_on violation

            # Check for an OFF-trigger event (was ON, now OFF)
            if t > 0 and on_off_schedule[t - 1][i] and not on_off_schedule[t][i]:
                # Check if it stays off for the required T_off duration
                for k in range(t, t + usine['t_off']):
                    if k >= num_timesteps or on_off_schedule[k][i]:
                        return float('inf')  # T_off violation

    # --- 2. Calculate Total Cost via Economic Dispatch per Time Step ---
    total_cost = 0.0
    consecutive_on_counts = [0] * num_usines

    for t in range(num_timesteps):
        demand_t = demand_schedule[t]

        # Update consecutive on-time counts for each usine
        for i in range(num_usines):
            if on_off_schedule[t][i]:
                consecutive_on_counts[i] += 1
            else:
                consecutive_on_counts[i] = 0

        # Collect data for usines that are ON at the current time step
        on_plants_data = []
        for i in range(num_usines):
            if on_off_schedule[t][i]:
                usine = usines[i]
                effective_p_max = _get_effective_pmax(usine, consecutive_on_counts[i])
                on_plants_data.append({
                    'cost': usine['cost_per_kwh'],
                    'p_min': usine['p_min'],
                    'p_max': effective_p_max
                })

        # Check if the collective production range of ON plants can meet the demand
        total_p_min = sum(p['p_min'] for p in on_plants_data)
        total_p_max = sum(p['p_max'] for p in on_plants_data)

        if not (total_p_min <= demand_t <= total_p_max):
            return float('inf')

        # Sort ON plants by cost (cheapest first) for economic dispatch
        on_plants_data.sort(key=lambda p: p['cost'])

        # Dispatch production
        step_cost = 0.0
        # First, all plants must run at their minimum production level
        for plant in on_plants_data:
            step_cost += plant['p_min'] * plant['cost']

        remaining_demand_to_dispatch = demand_t - total_p_min

        # Distribute the remaining demand among the cheapest plants
        for plant in on_plants_data:
            if remaining_demand_to_dispatch <= 1e-9:  # Use tolerance for float comparison
                break

            # Additional power this plant can provide
            headroom = plant['p_max'] - plant['p_min']
            dispatch_amount = min(remaining_demand_to_dispatch, headroom)

            step_cost += dispatch_amount * plant['cost']
            remaining_demand_to_dispatch -= dispatch_amount

        total_cost += step_cost

    return total_cost