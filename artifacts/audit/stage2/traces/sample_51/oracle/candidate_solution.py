import math
import json

def greedy_portfolio_allocate(
    prices: list[float],
    expected_returns: list[float],
    max_weights: list[float],
    budget: float,
    risk_penalty: float,
    round_decimals: int = 6
) -> dict:
    """
    Deterministic single-pass greedy allocator.
    Ranks by (expected_return - risk_penalty) desc, then price asc, then index asc.
    Sanitizes inputs, clips caps to [0,1], accumulates per-index errors, and returns a
    JSON-compatible result: {"weights","spent","score","errors"}
    """

    def to_float(x):
        try:
            f = float(x)
            return f if math.isfinite(f) else None
        except Exception:
            return None

    def fail(msg):
        return {"weights": [], "spent": 0.0, "score": 0.0, "errors": [msg]}

    if not (isinstance(prices, list) and isinstance(expected_returns, list) and isinstance(max_weights, list) and
            len(prices) == len(expected_returns) == len(max_weights)):
        return fail("length mismatch")

    n = len(prices)
    if n == 0:
        return {"weights": [], "spent": 0.0, "score": 0.0, "errors": ["no assets"]}

    b = to_float(budget)
    if b is None or b <= 0.0:
        return fail("invalid budget")

    errors = []
    global_errors = []

    if not isinstance(round_decimals, int) or not (0 <= round_decimals <= 12):
        round_decimals = 6
        global_errors.append("round_decimals coerced to 6")
    d = round_decimals

    rp = to_float(risk_penalty)
    if rp is None:
        rp = 0.0
        global_errors.append("risk_penalty coerced to 0")

    caps = [0.0] * n
    sp = [0.0] * n
    sr = [0.0] * n
    valid = [False] * n
    keys = [0.0] * n
    all_caps_zero = True

    for i in range(n):
        mw = to_float(max_weights[i])
        if mw is None:
            caps[i] = 0.0
            errors.append(f"max_weights[{i}] clipped to 0.0")
        else:
            if mw < 0.0:
                caps[i] = 0.0
                errors.append(f"max_weights[{i}] clipped to 0.0")
            elif mw > 1.0:
                caps[i] = 1.0
                errors.append(f"max_weights[{i}] clipped to 1.0")
            else:
                caps[i] = float(mw)
        if caps[i] != 0.0:
            all_caps_zero = False

        p = to_float(prices[i])
        r = to_float(expected_returns[i])
        if not (p is not None and p > 0.0):
            errors.append(f"prices[{i}] invalid")
        if r is None:
            errors.append(f"expected_returns[{i}] invalid")

        if (p is not None and p > 0.0) and (r is not None):
            sp[i] = p
            sr[i] = r
            valid[i] = True
            k = sr[i] - rp
            if not math.isfinite(k):
                return fail("numerical failure")
            keys[i] = k

    if not any(valid):
        final_errors = errors + (["all caps zero"] if all_caps_zero else []) + global_errors
        return {"weights": [0.0] * n, "spent": 0.0, "score": 0.0, "errors": final_errors}

    candidates = []
    for i in range(n):
        if valid[i]:
            candidates.append([i, keys[i], sp[i], caps[i]])
    candidates.sort(key=lambda t: [-t[1], t[2], t[0]])

    weights = [0.0] * n
    remaining = b
    last_changed = None
    if not math.isfinite(remaining):
        return fail("numerical failure")

    for idx, _, _, cap_i in candidates:
        if remaining <= 0.0 or round(remaining, d) == 0.0:
            break
        if cap_i <= 0.0:
            continue
        avail_frac = remaining / b
        if not math.isfinite(avail_frac):
            return fail("numerical failure")
        if avail_frac < 0.0:
            avail_frac = 0.0
        alloc_frac = cap_i if cap_i < avail_frac else avail_frac
        if alloc_frac <= 0.0:
            continue
        spend_amt = alloc_frac * b
        if not (math.isfinite(spend_amt) and spend_amt >= 0.0):
            return fail("numerical failure")
        weights[idx] = alloc_frac
        remaining -= spend_amt
        if remaining < -1e-12:
            return fail("numerical failure")
        if remaining < 0.0:
            remaining = 0.0
        last_changed = idx

    unit = 1.0 if d == 0 else 10.0 ** (-d)
    rounded = [round(w, d) for w in weights]
    fixed = [0.0] * n
    for i in range(n):
        wr = rounded[i]
        cap = caps[i]
        if d == 0:
            max_allowed = float(math.floor(cap))
        else:
            cells = math.floor(cap / unit + 1e-15)
            max_allowed = round(cells * unit, d)
        if wr > max_allowed:
            wr = max_allowed
        if wr < 0.0:
            wr = 0.0
        fixed[i] = wr + 0.0
    weights = fixed

    spent_raw = sum(weights) * b
    if not math.isfinite(spent_raw):
        return fail("numerical failure")

    if spent_raw > b + 1e-12 and last_changed is not None and unit > 0.0:
        over = spent_raw - b
        steps_needed = int(math.ceil((over / (b * unit)) - 1e-12))
        if steps_needed < 1:
            steps_needed = 1
        new_w = weights[last_changed] - steps_needed * unit
        if new_w < 0.0:
            new_w = 0.0
        weights[last_changed] = round(new_w, d) + 0.0
        spent_raw = sum(weights) * b
        guard = 0
        while spent_raw > b + 1e-12 and weights[last_changed] > 0.0 and guard < 10000:
            weights[last_changed] = round(max(0.0, weights[last_changed] - unit), d) + 0.0
            spent_raw = sum(weights) * b
            guard += 1
        if guard >= 10000:
            return fail("numerical failure")

    spent = round(spent_raw, d)
    if spent > round(b, d) + (10 ** (-d)) * 0.5:
        return fail("numerical failure")

    score = 0.0
    for i in range(n):
        if weights[i] == 0.0 or not valid[i]:
            continue
        shares = (weights[i] * b) / sp[i]
        if not math.isfinite(shares):
            return fail("numerical failure")
        contrib = shares * (sr[i] - rp)
        if not math.isfinite(contrib):
            return fail("numerical failure")
        score += contrib
        if not math.isfinite(score):
            return fail("numerical failure")
    score = round(score, d)

    final_errors = errors + (["all caps zero"] if all_caps_zero else []) + global_errors
    weights = [w + 0.0 for w in weights]
    spent = spent + 0.0
    score = score + 0.0

    return {"weights": weights, "spent": spent, "score": score, "errors": final_errors}


if __name__ == "__main__":
    prices = [10.0]
    expected_returns = [0.2]
    max_weights = [0.7]
    budget = 100.0
    risk_penalty = 0.0
    round_decimals = 0
    result = greedy_portfolio_allocate(
        prices, expected_returns, max_weights, budget, risk_penalty, round_decimals
    )
    print(json.dumps(result, indent=2))