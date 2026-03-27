def infinite_horizon_value_iteration(
    states: list,
    actions: list,
    transition_probabilities: dict,
    rewards: dict,
    gamma: float,
    epsilon: float
) -> dict:
    """Perform value iteration for an infinite horizon MDP.

    Args:
        states: List of unique state identifiers.
        actions: List of unique action identifiers.
        transition_probabilities: Nested dict of transition probabilities.
        rewards: Nested dict of immediate rewards.
        gamma: Discount factor (0 < gamma < 1).
        epsilon: Convergence threshold (> 0).

    Returns:
        dict: Dictionary with keys:
            - "value_function": Mapping of states to optimal values (2 decimals)
            - "policy": Mapping of states to optimal actions
            OR
            - "error": Description of validation issue
    """
    # Validate inputs
    if not isinstance(states, list):
        return {'error': 'Empty states list'}
    if not states:
        return {'error': 'Empty states list'}
    if not all(isinstance(s, str) for s in states):
        return {'error': 'Empty states list'}
    if not isinstance(actions, list):
        return {'error': 'Empty actions list'}
    if not actions:
        return {'error': 'Empty actions list'}
    if not all(isinstance(a, str) for a in actions):
        return {'error': 'Empty actions list'}
    if len(states) != len(set(states)):
        return {'error': 'Duplicate states found'}
    if len(actions) != len(set(actions)):
        return {'error': 'Duplicate actions found'}
    if not isinstance(gamma, (int, float)) or not (0 < gamma < 1):
        return {'error': 'Invalid gamma value'}
    if not isinstance(epsilon, (int, float)) or epsilon <= 0:
        return {'error': 'Invalid epsilon value'}
    if not isinstance(transition_probabilities, dict):
        return {'error': 'Missing transition probabilities'}

    for s in states:
        if s not in transition_probabilities:
            return {'error': 'Missing transition probabilities'}
        if not isinstance(transition_probabilities[s], dict):
            return {'error': 'Missing transition probabilities'}
        for a in actions:
            if a not in transition_probabilities[s]:
                return {'error': 'Missing transition probabilities'}
            if not isinstance(transition_probabilities[s][a], dict):
                return {'error': 'Missing transition probabilities'}

            for s_next in transition_probabilities[s][a]:
                if s_next not in states:
                    return {'error': 'Invalid next state in transitions'}

            prob_sum = 0.0
            for s_next, prob in transition_probabilities[s][a].items():
                if not isinstance(prob, (int, float)) or not (0 <= prob <= 1):
                    return {'error': 'Invalid transition probability'}
                prob_sum += prob
            if abs(prob_sum - 1.0) > 1e-6:
                return {'error': 'Transition probabilities do not sum to 1'}

    if not isinstance(rewards, dict):
        return {'error': 'Missing rewards'}
    for s in states:
        if s not in rewards:
            return {'error': 'Missing rewards'}
        if not isinstance(rewards[s], dict):
            return {'error': 'Missing rewards'}
        for a in actions:
            if a not in rewards[s]:
                return {'error': 'Missing rewards'}
            if not isinstance(rewards[s][a], (int, float)):
                return {'error': 'Invalid reward value'}

    def compute_q_value(state, action, value_function):
        """Compute Q(s, a) = R(s, a) + γ * Σ P(s'|s,a) * V(s')."""
        q = rewards[state][action]
        for next_state, prob in transition_probabilities[state][action].items():
            q += gamma * prob * value_function[next_state]
        return q

    V = {s: 0.0 for s in states}

    while True:
        V_old = V.copy()
        for s in states:
            V[s] = max(compute_q_value(s, a, V_old) for a in actions)
        delta = max(abs(V[s] - V_old[s]) for s in states)
        if delta < epsilon:
            break

    policy = {}
    for s in states:
        best_action = None
        best_value = float('-inf')
        for a in actions:
            q_value = compute_q_value(s, a, V)
            if best_action is None:
                best_action = a
                best_value = q_value
            elif q_value > best_value + 1e-9:
                best_action = a
                best_value = q_value
        policy[s] = best_action

    value_function = {s: round(V[s], 2) for s in states}
    return {"value_function": value_function, "policy": policy}