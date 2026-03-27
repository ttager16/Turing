from typing import List, Dict, Optional

def optimize_portfolio(
    asset_data: List[Dict[str, float]],
    market_update: Dict[str, float],
    mode: str = "risk_adjusted",
    prev_weights: Optional[List[float]] = None,
    max_per_asset: float = 0.35,
    turnover_budget: float = 0.40,
    step_size: float = 0.01,
    alpha: float = 0.2,
    beta: float = 0.2,
    use_diversification_penalty: bool = True
) -> List[float]:
    n = len(asset_data)
    prev_is_none = prev_weights is None
    if prev_weights is None:
        prev_weights = [0.0] * n

    smoothed_data = []
    for i, asset in enumerate(asset_data):
        asset_id = asset["id"]
        new_return = market_update.get(asset_id, asset["expected_return"])
        new_volatility = asset["volatility"]
        prior_return = asset["expected_return"]
        prior_volatility = asset["volatility"]
        expected_return_smooth = alpha * new_return + (1 - alpha) * prior_return
        volatility_smooth = beta * new_volatility + (1 - beta) * prior_volatility
        smoothed_data.append({
            "index": i,
            "id": asset_id,
            "expected_return_smooth": expected_return_smooth,
            "volatility_smooth": volatility_smooth
        })

    def calculate_scores(weights):
        scores = []
        for i in range(n):
            er = smoothed_data[i]["expected_return_smooth"]
            vol = smoothed_data[i]["volatility_smooth"]
            base = er if mode == "absolute" else er / (vol + 1e-6)
            adj = base * (1 - weights[i]) if use_diversification_penalty else base
            scores.append({"index": i, "score": adj, "volatility": vol, "id": smoothed_data[i]["id"]})
        return scores

    def incremental_turnover_change(weights, idx_delta):
        if prev_is_none:
            return 0.0
        delta = 0.0
        for idx, d in idx_delta.items():
            old_diff = abs(weights[idx] - prev_weights[idx])
            new_diff = abs((weights[idx] + d) - prev_weights[idx])
            delta += (new_diff - old_diff)
        return delta

    weights = list(prev_weights)
    target_total = 1.0
    max_iterations = 10000
    eps = step_size * 0.5

    need_to_build = sum(weights) < target_total - eps
    cumulative_turnover = 0.0 if prev_is_none else sum(abs(weights[i] - prev_weights[i]) for i in range(n))

    for _ in range(max_iterations):
        current_total = sum(weights)
        if need_to_build and current_total >= target_total - eps:
            need_to_build = False

        scores = calculate_scores(weights)

        if need_to_build:
            candidates = [s for s in scores if weights[s["index"]] + step_size <= max_per_asset]
            if not candidates:
                break
            candidates.sort(key=lambda x: (-x["score"], x["volatility"], x["id"]))
            best = candidates[0]
            inc = incremental_turnover_change(weights, {best["index"]: step_size})
            if not prev_is_none and cumulative_turnover + inc > turnover_budget:
                return [round(w, 2) for w in prev_weights]
            weights[best["index"]] += step_size
            cumulative_turnover += inc
        else:
            add_candidates = [s for s in scores if weights[s["index"]] + step_size <= max_per_asset]
            remove_candidates = [s for s in scores if weights[s["index"]] >= step_size]
            if not add_candidates or not remove_candidates:
                break
            add_candidates.sort(key=lambda x: (-x["score"], x["volatility"], x["id"]))
            remove_candidates.sort(key=lambda x: (x["score"], x["volatility"], x["id"]))
            best_add = add_candidates[0]
            best_remove = remove_candidates[0]
            if best_add["score"] <= best_remove["score"]:
                break
            if best_add["index"] == best_remove["index"]:
                break
            idx_delta = {best_add["index"]: step_size, best_remove["index"]: -step_size}
            inc = incremental_turnover_change(weights, idx_delta)
            if not prev_is_none and cumulative_turnover + inc > turnover_budget:
                break
            weights[best_add["index"]] += step_size
            weights[best_remove["index"]] -= step_size
            cumulative_turnover += inc

    return [round(w, 2) for w in weights]