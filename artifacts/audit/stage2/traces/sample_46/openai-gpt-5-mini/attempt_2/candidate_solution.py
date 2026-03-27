def maximize_ad_impressions(payload: Dict[str, Any]) -> Dict[str, float | List[str]]:
    budget: float = float(payload.get("budget", 0.0))
    raw_bids = payload.get("bids", [])
    synergy_list = payload.get("synergy", [])
    seg_caps_raw = payload.get("segment_roi_cap", {}) or {}

    # Normalize segment caps keys to ints
    segment_caps: Dict[int, float] = {}
    for k, v in seg_caps_raw.items():
        try:
            ik = int(k)
        except Exception:
            continue
        segment_caps[ik] = float(v)

    # Build synergy map: unordered pair -> penalty
    synergy: Dict[Tuple[int, int], float] = {}
    for entry in synergy_list:
        pair = entry.get("pair", [])
        if not pair or len(pair) != 2:
            continue
        a, b = int(pair[0]), int(pair[1])
        if a == b:
            continue
        key = (a, b) if a < b else (b, a)
        synergy[key] = float(entry.get("penalty", 0.0))

    # Parse bids into dicts; ensure deterministic order by original list order
    bids: List[Dict[str, Any]] = []
    for item in raw_bids:
        if not item or len(item) < 4:
            continue
        bid_id = str(item[0])
        cost = float(item[1])
        roi = float(item[2])
        segments = [int(s) for s in item[3]]
        bids.append({
            "id": bid_id,
            "cost": cost,
            "roi": roi,
            "segments": segments
        })

    # Helper to compute utility components for a set of accepted bid ids
    def evaluate(accepted_set: List[str]) -> Dict[str, Any]:
        # accepted_set is list for deterministic ordering; use set for membership
        accepted = set(accepted_set)
        total_cost = 0.0
        # accumulate per-segment allocated ROI (before caps)
        seg_alloc: Dict[int, float] = {}
        for b in bids:
            if b["id"] in accepted:
                total_cost += b["cost"]
                segs = b["segments"]
                if not segs:
                    continue
                per_seg = b["roi"] / len(segs)
                for s in segs:
                    seg_alloc[s] = seg_alloc.get(s, 0.0) + per_seg
        # apply per-segment caps
        total_roi = 0.0
        for s, alloc in seg_alloc.items():
            cap = segment_caps.get(s)
            if cap is None:
                total_roi += alloc
            else:
                # cap is for total across accepted bids; if alloc > cap, clipped
                total_roi += min(alloc, cap)
        # compute penalties: presence-based unordered pairs across segments present
        present_segments = set(seg_alloc.keys())
        total_penalty = 0.0
        for (a, b), p in synergy.items():
            if a in present_segments and b in present_segments:
                total_penalty += p
        utility = total_roi - total_penalty
        return {
            "total_cost": total_cost,
            "total_roi": total_roi,
            "total_penalty": total_penalty,
            "utility": utility
        }

    # Precompute metrics per bid for greedy ordering: marginal ROI ignoring caps and synergy
    # Deterministic tie-breaker: index order
    bid_index = {b["id"]: i for i, b in enumerate(bids)}
    # Use a greedy score: (roi / cost) higher is better; if cost==0 handle
    def bid_score(b):
        return (b["roi"] / b["cost"]) if b["cost"] > 0 else float('inf')

    # Initial greedy selection: iterate bids sorted by score desc, deterministic tie by index
    sorted_bids = sorted(bids, key=lambda x: (-bid_score(x), bid_index[x["id"]]))
    accepted: List[str] = []
    remaining_budget = budget
    # Track per-seg allocated pre-cap for quick incremental checks
    seg_alloc: Dict[int, float] = {}
    def current_penalty_for_segments(segments_present: set) -> float:
        tot = 0.0
        for (a, b), p in synergy.items():
            if a in segments_present and b in segments_present:
                tot += p
        return tot

    # Greedy add if cost fits and marginal utility positive (considering caps and penalties)
    for b in sorted_bids:
        if b["cost"] > remaining_budget:
            continue
        # simulate adding bid
        new_seg_alloc = dict(seg_alloc)
        per_seg = b["roi"] / (len(b["segments"]) if b["segments"] else 1)
        for s in b["segments"]:
            new_seg_alloc[s] = new_seg_alloc.get(s, 0.0) + per_seg
        # compute total_roi with caps
        total_roi = 0.0
        for s, alloc in new_seg_alloc.items():
            cap = segment_caps.get(s)
            if cap is None:
                total_roi += alloc
            else:
                total_roi += min(alloc, cap)
        # compute penalty
        present_segments = set(new_seg_alloc.keys())
        total_penalty = current_penalty_for_segments(present_segments)
        # compute previous total_roi and penalty to get marginal
        prev_total_roi = 0.0
        for s, alloc in seg_alloc.items():
            cap = segment_caps.get(s)
            prev_total_roi += alloc if cap is None else min(alloc, cap)
        prev_penalty = current_penalty_for_segments(set(seg_alloc.keys()))
        marginal = (total_roi - prev_total_roi) - (total_penalty - prev_penalty)
        if marginal >= 0:
            # accept
            accepted.append(b["id"])
            remaining_budget -= b["cost"]
            seg_alloc = new_seg_alloc

    # Local improvement phase: try to add single bids or swap one in for one out (deterministic)
    improved = True
    # To ensure determinism, always iterate bids in the same base order (sorted_bids)
    while improved:
        improved = False
        # Try additions first
        for b in sorted_bids:
            if b["id"] in accepted:
                continue
            if b["cost"] > remaining_budget:
                continue
            # simulate add
            new_accepted = accepted + [b["id"]]
            eval_new = evaluate(new_accepted)
            eval_curr = evaluate(accepted)
            if eval_new["utility"] > eval_curr["utility"] + 1e-9:
                # accept
                accepted = new_accepted
                remaining_budget -= b["cost"]
                improved = True
                break
        if improved:
            continue
        # Try swaps: replace one accepted bid with one non-accepted bid if cost constraint and utility improves
        # Deterministic nested loops over accepted then candidate
        for out_id in list(accepted):
            out_bid = next((x for x in bids if x["id"] == out_id), None)
            if out_bid is None:
                continue
            for in_bid in sorted_bids:
                if in_bid["id"] in accepted:
                    continue
                # new cost = current_cost - out_cost + in_cost must fit budget
                curr_eval = evaluate(accepted)
                new_cost = curr_eval["total_cost"] - out_bid["cost"] + in_bid["cost"]
                if new_cost > budget + 1e-9:
                    continue
                new_accepted = [x for x in accepted if x != out_id] + [in_bid["id"]]
                # ensure deterministic order of accepted: keep order as in original bids list
                new_accepted_sorted = [b["id"] for b in bids if b["id"] in set(new_accepted)]
                eval_new = evaluate(new_accepted_sorted)
                if eval_new["utility"] > curr_eval["utility"] + 1e-9:
                    accepted = new_accepted_sorted
                    remaining_budget = budget - eval_new["total_cost"]
                    improved = True
                    break
            if improved:
                break
        # If still not improved, try multi-adds of lowest-cost single additions (attempt 2-add combos limited)
        if not improved:
            # attempt single addition of smallest cost that fits even if marginal zero? we already tried
            # try pairwise addition of two unused bids if combined fits and improves
            unused = [b for b in sorted_bids if b["id"] not in accepted]
            n_unused = len(unused)
            # limit combinations to reasonable amount: since bids per input can be large, only consider first 50 unused to remain efficient
            limit = 50
            consider = unused[:limit]
            found = False
            for i in range(len(consider)):
                bi = consider[i]
                if bi["cost"] > remaining_budget:
                    continue
                for j in range(i+1, len(consider)):
                    bj = consider[j]
                    if bi["cost"] + bj["cost"] > remaining_budget:
                        continue
                    new_accepted = accepted + [bi["id"], bj["id"]]
                    eval_new = evaluate(new_accepted)
                    eval_curr = evaluate(accepted)
                    if eval_new["utility"] > eval_curr["utility"] + 1e-9:
                        # accept and break
                        # deterministic ordering
                        accepted = [b["id"] for b in bids if b["id"] in set(new_accepted)]
                        remaining_budget = budget - evaluate(accepted)["total_cost"]
                        improved = True
                        found = True
                        break
                if found:
                    break

    # Final evaluation and deterministic accepted ordering: order by original bids list
    accepted_final = [b["id"] for b in bids if b["id"] in set(accepted)]
    final_eval = evaluate(accepted_final)
    # Round floats to reasonable precision for determinism
    def clean(x: float) -> float:
        return float(round(x + 0.0, 10))
    result = {
        "accepted": accepted_final,
        "total_cost": clean(final_eval["total_cost"]),
        "total_roi": clean(final_eval["total_roi"]),
        "total_penalty": clean(final_eval["total_penalty"]),
        "utility": clean(final_eval["utility"])
    }
    return result