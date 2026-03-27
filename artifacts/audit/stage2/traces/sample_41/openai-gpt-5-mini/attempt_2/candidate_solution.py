def infinite_horizon_value_iteration(
    states: list,
    actions: list,
    transition_probabilities: dict,
    rewards: dict,
    gamma: float,
    epsilon: float
) -> dict:
    # Input validation
    if not isinstance(states, list) or len(states) == 0:
        return {'error': 'Empty states list'}
    if not isinstance(actions, list) or len(actions) == 0:
        return {'error': 'Empty actions list'}
    # duplicates
    if len(set(states)) != len(states):
        return {'error': 'Duplicate states found'}
    if len(set(actions)) != len(actions):
        return {'error': 'Duplicate actions found'}
    # gamma
    try:
        gamma_val = float(gamma)
    except Exception:
        return {'error': 'Invalid gamma value'}
    if not (0.0 < gamma_val < 1.0):
        return {'error': 'Invalid gamma value'}
    # epsilon
    try:
        eps = float(epsilon)
    except Exception:
        return {'error': 'Invalid epsilon value'}
    if not (eps > 0.0):
        return {'error': 'Invalid epsilon value'}
    # transition_probabilities presence
    if not isinstance(transition_probabilities, dict):
        return {'error': 'Missing transition probabilities'}
    for s in states:
        if s not in transition_probabilities or not isinstance(transition_probabilities[s], dict):
            return {'error': 'Missing transition probabilities'}
        for a in actions:
            if a not in transition_probabilities[s] or not isinstance(transition_probabilities[s][a], dict):
                return {'error': 'Missing transition probabilities'}
    # validate next states and probabilities
    for s in states:
        for a in actions:
            trans = transition_probabilities[s][a]
            total = 0.0
            if not isinstance(trans, dict):
                return {'error': 'Missing transition probabilities'}
            for s_next, prob in trans.items():
                if s_next not in states:
                    return {'error': 'Invalid next state in transitions'}
                try:
                    p = float(prob)
                except Exception:
                    return {'error': 'Invalid transition probability'}
                if p < 0.0 or p > 1.0:
                    return {'error': 'Invalid transition probability'}
                total += p
            if abs(total - 1.0) > 1e-6:
                return {'error': 'Transition probabilities do not sum to 1'}
    # rewards presence
    if not isinstance(rewards, dict):
        return {'error': 'Missing rewards'}
    for s in states:
        if s not in rewards or not isinstance(rewards[s], dict):
            return {'error': 'Missing rewards'}
        for a in actions:
            if a not in rewards[s]:
                return {'error': 'Missing rewards'}
            r = rewards[s][a]
            try:
                _ = float(r)
            except Exception:
                return {'error': 'Invalid reward value'}
    # Initialize V
    V_old = {s: 0.0 for s in states}
    # Value iteration
    while True:
        V_new = {}
        delta = 0.0
        for s in states:
            best = None
            for a in actions:
                r = float(rewards[s][a])
                trans = transition_probabilities[s][a]
                exp = r
                sum_term = 0.0
                for s_next, p in trans.items():
                    sum_term += float(p) * V_old[s_next]
                exp = r + gamma_val * sum_term
                if best is None or exp > best:
                    best = exp
            V_new[s] = best if best is not None else 0.0
            diff = abs(V_new[s] - V_old[s])
            if diff > delta:
                delta = diff
        if delta < eps:
            V_final = V_new
            break
        V_old = V_new
    # Policy extraction with tie-breaking
    policy = {}
    for s in states:
        best_val = None
        best_action = None
        for a in actions:
            r = float(rewards[s][a])
            trans = transition_probabilities[s][a]
            sum_term = 0.0
            for s_next, p in trans.items():
                sum_term += float(p) * V_final[s_next]
            val = r + gamma_val * sum_term
            if best_val is None or (val > best_val + 1e-9):
                best_val = val
                best_action = a
            elif abs(val - best_val) <= 1e-9:
                # tie: keep earlier action (actions list order), so do nothing
                pass
        policy[s] = best_action if best_action is not None else actions[0]
    # Round value function to 2 decimals
    value_function = {s: round(V_final[s], 2) for s in states}
    return {'value_function': value_function, 'policy': policy}