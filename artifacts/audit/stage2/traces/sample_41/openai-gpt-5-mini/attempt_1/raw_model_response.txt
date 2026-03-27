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
        if not (0.0 < float(gamma) < 1.0):
            return {'error': 'Invalid gamma value'}
    except Exception:
        return {'error': 'Invalid gamma value'}
    # epsilon
    try:
        if not (float(epsilon) > 0.0):
            return {'error': 'Invalid epsilon value'}
    except Exception:
        return {'error': 'Invalid epsilon value'}
    # transitions presence
    if not isinstance(transition_probabilities, dict):
        return {'error': 'Missing transition probabilities'}
    for s in states:
        if s not in transition_probabilities or not isinstance(transition_probabilities[s], dict):
            return {'error': 'Missing transition probabilities'}
        for a in actions:
            if a not in transition_probabilities[s] or not isinstance(transition_probabilities[s][a], dict):
                return {'error': 'Missing transition probabilities'}
    # transitions validity
    for s in states:
        for a in actions:
            trans_dict = transition_probabilities[s][a]
            total = 0.0
            for s_next, p in trans_dict.items():
                if s_next not in states:
                    return {'error': 'Invalid next state in transitions'}
                try:
                    pval = float(p)
                except Exception:
                    return {'error': 'Invalid transition probability'}
                if not (0.0 <= pval <= 1.0):
                    return {'error': 'Invalid transition probability'}
                total += pval
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
    # Initialization
    V_old = {s: 0.0 for s in states}
    gamma = float(gamma)
    epsilon = float(epsilon)
    # Value iteration
    while True:
        V_new = {}
        for s in states:
            best = None
            for a in actions:
                r = float(rewards[s][a])
                exp = 0.0
                trans = transition_probabilities[s][a]
                for s_next, p in trans.items():
                    exp += float(p) * V_old[s_next]
                val = r + gamma * exp
                if best is None or val > best:
                    best = val
            V_new[s] = best if best is not None else 0.0
        delta = max(abs(V_new[s] - V_old[s]) for s in states)
        if delta < epsilon:
            V_final = V_new
            break
        V_old = V_new
    # Policy extraction
    policy = {}
    for s in states:
        best_val = None
        best_action = None
        for a in actions:
            r = float(rewards[s][a])
            exp = 0.0
            trans = transition_probabilities[s][a]
            for s_next, p in trans.items():
                exp += float(p) * V_final[s_next]
            val = r + gamma * exp
            if best_val is None or val > best_val + 1e-9:
                best_val = val
                best_action = a
            elif abs(val - best_val) <= 1e-9:
                # tie: keep earlier action (actions are iterated in order)
                pass
        policy[s] = best_action if best_action is not None else actions[0]
    # Round value function to 2 decimals
    value_function = {s: round(V_final[s], 2) for s in states}
    return {'value_function': value_function, 'policy': policy}