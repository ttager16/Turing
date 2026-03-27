from typing import Dict, List, Tuple, Any

def maximize_ad_impressions(payload: Dict[str, Any]) -> Dict[str, float | List[str]]:
    """
    Synergy-aware optimizer with greedy + local improvements (add, remove, 1-for-1 swap).
    Deterministic and pure-Python.

    Input payload:
      - "budget": float
      - "bids": List[[bid_id: str, cost: float, roi: float, segments: List[int]]]
      - "synergy": List[{"pair": [int, int], "penalty": float}]
      - "segment_roi_cap": Dict[str|int, float]

    Returns:
      {
        "accepted": List[str],         # deterministic (sorted by id)
        "total_cost": float,
        "total_roi": float,            # after caps (presence-based equal split)
        "total_penalty": float,        # presence-based pair penalties
        "utility": float               # total_roi - total_penalty
      }
    """
    # ---------- Normalize input ----------
    budget = float(payload.get("budget", 0.0))

    raw_bids = payload.get("bids", []) or []
    items: List[Tuple[str, float, float, Tuple[int, ...]]] = []
    for bid_id, cost, roi, segs in raw_bids:
        bid_id = str(bid_id)
        cost = float(cost)
        roi = float(roi)
        segs = tuple(sorted(set(int(s) for s in (segs or []))))
        items.append((bid_id, cost, roi, segs))

    # synergy: accumulate (sum) duplicate penalties for identical unordered pairs
    norm_synergy: Dict[Tuple[int, int], float] = {}
    for obj in (payload.get("synergy", []) or []):
        a, b = int(obj["pair"][0]), int(obj["pair"][1])
        if a == b:
            continue
        if a > b:
            a, b = b, a
        pen = float(obj["penalty"])
        norm_synergy[(a, b)] = norm_synergy.get((a, b), 0.0) + pen

    # caps: allow str/int keys; keep deterministic
    segment_roi_cap: Dict[int, float] = {int(k): float(v) for k, v in (payload.get("segment_roi_cap", {}) or {}).items()}

    # Quick lookups
    by_id: Dict[str, Tuple[str, float, float, Tuple[int, ...]]] = {bid[0]: bid for bid in items}
    all_ids_sorted: List[str] = sorted(by_id.keys())
    cost_by_id: Dict[str, float] = {bid[0]: bid[1] for bid in items}

    # ---------- Helpers ----------
    def compute_result(accepted_ids: List[str]) -> Dict[str, float | List[str]]:
        """Deterministic full recomputation (authoritative)."""
        acc_sorted = sorted(accepted_ids)
        spent = 0.0
        total_roi = 0.0
        seg_used: Dict[int, float] = {k: 0.0 for k in segment_roi_cap}
        active_segments: set[int] = set()

        for bid_id in acc_sorted:
            _, cost, roi, segs = by_id[bid_id]
            spent += cost
            if roi > 0.0 and segs:
                share = roi / len(segs)
                add = 0.0
                for s in segs:
                    if s in segment_roi_cap:
                        rem = segment_roi_cap[s] - seg_used.get(s, 0.0)
                        if rem > 0.0:
                            inc = share if share <= rem else rem
                            seg_used[s] = seg_used.get(s, 0.0) + inc
                            add += inc
                    else:
                        add += share
                total_roi += add
            # presence-based activation, even if capped to zero
            for s in segs:
                active_segments.add(s)

        # presence-based penalties (each unordered active pair once)
        act = sorted(active_segments)
        total_penalty = 0.0
        for i in range(len(act)):
            ai = act[i]
            for j in range(i + 1, len(act)):
                p = (ai, act[j])
                total_penalty += norm_synergy.get(p, 0.0)

        utility = total_roi - total_penalty
        return {
            "accepted": acc_sorted,
            "total_cost": spent,
            "total_roi": total_roi,
            "total_penalty": total_penalty,
            "utility": utility,
        }

    def utility_of(ids: List[str]) -> float:
        return float(compute_result(ids)["utility"])  # type: ignore[index]

    # Cheap optimistic bound for pruning (no caps, only internal presence penalties)
    # Used to skip candidates that cannot possibly help.
    def optimistic_gain_upper_bound(bid_id: str) -> float:
        _, cost, roi, segs = by_id[bid_id]
        if roi <= 0.0 or not segs or cost > budget:
            return 0.0
        # ROI upper bound = roi (no caps considered)
        # Penalty lower bound (best case) = only internal pairs in the bid itself
        internal = 0.0
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                a, b = segs[i], segs[j]
                if a > b:
                    a, b = b, a
                internal += norm_synergy.get((a, b), 0.0)
        return roi - internal

    prunable = {bid_id for bid_id in all_ids_sorted if optimistic_gain_upper_bound(bid_id) <= 0.0}

    # ---------- Greedy seeds (two modes) ----------
    def greedy_pass(mode: str) -> List[str]:
        accepted: List[str] = []
        spent = 0.0
        seg_used: Dict[int, float] = {k: 0.0 for k in segment_roi_cap}
        active_segments: set[int] = set()
        active_pairs: set[Tuple[int, int]] = set()

        def capped_roi_contrib(roi: float, segs: Tuple[int, ...]) -> float:
            if roi <= 0.0 or not segs:
                return 0.0
            share = roi / len(segs)
            contrib = 0.0
            for s in segs:
                if s in segment_roi_cap:
                    rem = segment_roi_cap[s] - seg_used.get(s, 0.0)
                    if rem > 0.0:
                        contrib += share if share <= rem else rem
                else:
                    contrib += share
            return contrib

        def incremental_penalty(segs: Tuple[int, ...]) -> float:
            if not segs:
                return 0.0
            inc = 0.0
            # internal
            for i in range(len(segs)):
                for j in range(i + 1, len(segs)):
                    a, b = segs[i], segs[j]
                    if a > b:
                        a, b = b, a
                    p = (a, b)
                    if p not in active_pairs:
                        inc += norm_synergy.get(p, 0.0)
            # cross
            for s in segs:
                for t in active_segments:
                    if s == t:
                        continue
                    a, b = (s, t) if s < t else (t, s)
                    if (a, b) not in active_pairs:
                        inc += norm_synergy.get((a, b), 0.0)
            return inc

        def activate(segs: Tuple[int, ...]) -> None:
            # internal
            for i in range(len(segs)):
                for j in range(i + 1, len(segs)):
                    a, b = segs[i], segs[j]
                    if a > b:
                        a, b = b, a
                    active_pairs.add((a, b))
            # cross
            for s in segs:
                for t in active_segments:
                    if s == t:
                        continue
                    a, b = (s, t) if s < t else (t, s)
                    active_pairs.add((a, b))
            active_segments.update(segs)

        remaining = [bid_id for bid_id in all_ids_sorted if bid_id not in prunable]
        while True:
            best = None  # (key, bid_id, inc_roi, inc_pen, cost)
            for bid_id in remaining:
                _, cost, roi, segs = by_id[bid_id]
                if spent + cost > budget:
                    continue
                inc_pen = incremental_penalty(segs)
                inc_roi = capped_roi_contrib(roi, segs)
                gain = inc_roi - inc_pen
                if gain <= 0.0:
                    continue
                if mode == "ratio":
                    primary = (gain / cost) if cost > 0 else float("inf")
                    key = (primary, gain, -cost, segs, bid_id)
                else:
                    ratio = (gain / cost) if cost > 0 else float("inf")
                    key = (gain, ratio, -cost, segs, bid_id)
                if best is None or key > best[0]:
                    best = (key, bid_id, inc_roi, inc_pen, cost)
            if best is None:
                break
            _, bid_id, _, _, cost = best
            _, _, roi, segs = by_id[bid_id]
            # advance caps
            if roi > 0.0 and segs:
                share = roi / len(segs)
                for s in segs:
                    if s in segment_roi_cap:
                        rem = segment_roi_cap[s] - seg_used.get(s, 0.0)
                        if rem > 0.0:
                            seg_used[s] = seg_used.get(s, 0.0) + (share if share <= rem else rem)
            activate(segs)
            accepted.append(bid_id)
            spent += cost
            remaining.remove(bid_id)

        return sorted(accepted)

    seed_ratio = greedy_pass("ratio")
    seed_abs = greedy_pass("abs")
    best_ids = seed_abs if utility_of(seed_abs) > utility_of(seed_ratio) else seed_ratio

    # ---------- Local improvements ----------
    # We avoid arbitrary hard iteration caps; loop ends when a full pass yields no change.
    changed = True
    while changed:
        changed = False
        cur = compute_result(best_ids)
        cur_util = float(cur["utility"])  # type: ignore[index]
        cur_cost = float(cur["total_cost"])  # type: ignore[index]

        # (A) Profitable single additions (repeat until no positive add fits)
        added = True
        while added:
            added = False
            for cand in all_ids_sorted:
                if cand in best_ids or cand in prunable:
                    continue
                c = cost_by_id[cand]
                if cur_cost + c > budget:
                    continue
                trial = best_ids + [cand]
                u = utility_of(trial)
                if u > cur_util:
                    best_ids = sorted(trial)
                    cur_util = u
                    cur_cost += c
                    changed = True
                    added = True
                    # restart scanning from smallest id to keep determinism
                    break

        # (B) Profitable single removals (can reduce penalties and free budget)
        removed = True
        while removed:
            removed = False
            for out_id in list(best_ids):
                trial = [x for x in best_ids if x != out_id]
                u = utility_of(trial)
                if u > cur_util:
                    best_ids = trial  # already sorted minus one
                    cur_util = u
                    cur_cost -= cost_by_id[out_id]
                    changed = True
                    removed = True
                    # after removing, try to greedily add again (packed usage of budget)
                    break
            if removed:
                # re-pack
                repacked = True
                while repacked:
                    repacked = False
                    for cand in all_ids_sorted:
                        if cand in best_ids or cand in prunable:
                            continue
                        c = cost_by_id[cand]
                        if cur_cost + c > budget:
                            continue
                        trial = best_ids + [cand]
                        u = utility_of(trial)
                        if u > cur_util:
                            best_ids = sorted(trial)
                            cur_util = u
                            cur_cost += c
                            changed = True
                            repacked = True
                            break

        # (C) Profitable 1-for-1 swaps
        swapped = True
        while swapped:
            swapped = False
            acc_list = list(best_ids)
            for out_id in acc_list:
                base_cost = cur_cost - cost_by_id[out_id]
                for in_id in all_ids_sorted:
                    if in_id == out_id or in_id in best_ids or in_id in prunable:
                        continue
                    new_cost = base_cost + cost_by_id[in_id]
                    if new_cost > budget:
                        continue
                    trial = [x for x in best_ids if x != out_id] + [in_id]
                    u = utility_of(trial)
                    if u > cur_util:
                        best_ids = sorted(trial)
                        cur_util = u
                        cur_cost = new_cost
                        changed = True
                        swapped = True
                        # after a successful swap, try to greedily add again to fill slack
                        added_more = True
                        while added_more:
                            added_more = False
                            for cand in all_ids_sorted:
                                if cand in best_ids or cand in prunable:
                                    continue
                                c = cost_by_id[cand]
                                if cur_cost + c > budget:
                                    continue
                                trial2 = best_ids + [cand]
                                u2 = utility_of(trial2)
                                if u2 > cur_util:
                                    best_ids = sorted(trial2)
                                    cur_util = u2
                                    cur_cost += c
                                    changed = True
                                    added_more = True
                                    break
                        break
                if swapped:
                    break

    # ---------- Final (single) rounding for output ----------
    final = compute_result(best_ids)
    return {
        "accepted": final["accepted"],  # type: ignore[index]
        "total_cost": round(float(final["total_cost"]), 10),       # type: ignore[index]
        "total_roi": round(float(final["total_roi"]), 10),         # type: ignore[index]
        "total_penalty": round(float(final["total_penalty"]), 10), # type: ignore[index]
        "utility": round(float(final["utility"]), 10),             # type: ignore[index]
    }