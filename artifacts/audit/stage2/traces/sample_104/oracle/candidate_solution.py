from typing import Any, Dict, List, Tuple

TierWeights = {"critical": 3, "essential": 2, "normal": 1}
ValidStates = {"normal", "peak", "maintenance"}


def _parse_int_nonneg(x: Any) -> int:
    try:
        if isinstance(x, bool):
            return 0
        if isinstance(x, (int,)):
            return max(0, int(x))
        if isinstance(x, float):
            return max(0, int(x))
        if isinstance(x, str):
            v = float(x.strip())
            return max(0, int(v))
    except Exception:
        pass
    return 0


def _parse_float(x: Any, default: float = 1e9) -> float:
    try:
        if isinstance(x, bool):
            return default
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            return float(x.strip())
    except Exception:
        return default
    return default


def _tier_weight(t: Any) -> int:
    if isinstance(t, str):
        t = t.lower()
    return TierWeights.get(t, TierWeights["normal"])


def _usable_capacity(state: str, cap: int, em_cap: int) -> int:
    if state == "maintenance":
        return 0
    if state == "peak":
        return cap + em_cap
    return cap


def _wrap_ops_if_needed(ops: Any) -> List[List[Any]]:
    if ops is None:
        return []
    if isinstance(ops, list) and ops and isinstance(ops[0], str):
        return [ops]  # single flattened op
    if isinstance(ops, list):
        # ensure every element is a list-like op
        wrapped = []
        for op in ops:
            if isinstance(op, list):
                wrapped.append(op)
        return wrapped
    return []


def optimize_resource_allocation(graph: "BipartiteGraph") -> List[List[str]]:
    providers_in: List[Dict[str, Any]] = list(graph.get("providers", []))
    consumers_in: List[Dict[str, Any]] = list(graph.get("consumers", []))
    edges_in: List[List[Any]] = list(graph.get("edges", []))
    prev_alloc_in: List[List[Any]] = list(graph.get("prev_alloc", []))
    ops_in: List[List[Any]] = _wrap_ops_if_needed(graph.get("ops", []))

    # Normalize providers
    providers: Dict[str, Dict[str, Any]] = {}
    for p in providers_in:
        pid = str(p.get("id", "") or "")
        if not pid:
            continue
        prov = {
            "id": pid,
            "cap": _parse_int_nonneg(p.get("cap", 0)),
            "em_cap": _parse_int_nonneg(p.get("em_cap", 0)),
            "priority": _parse_int_nonneg(p.get("priority", 0)),
            "state": str(p.get("state", "normal")),
            "layer": _parse_int_nonneg(p.get("layer", 0)),
            "segment": str(p.get("segment", "")),
        }
        if prov["state"] not in ValidStates:
            prov["state"] = "normal"
        providers[pid] = prov

    # Normalize consumers
    consumers: Dict[str, Dict[str, Any]] = {}
    for c in consumers_in:
        cid = str(c.get("id", "") or "")
        if not cid:
            continue
        cons = {
            "id": cid,
            "dem": _parse_int_nonneg(c.get("dem", 0)),
            "tier": str(c.get("tier", "normal")).lower(),
            "layer": _parse_int_nonneg(c.get("layer", 0)),
            "segment": str(c.get("segment", "")),
        }
        if cons["tier"] not in TierWeights:
            cons["tier"] = "normal"
        consumers[cid] = cons

    edges: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for e in edges_in:
        if not isinstance(e, list) or len(e) < 4:
            continue
        pid, cid, me, cost = e[0], e[1], e[2], e[3]
        pid, cid = str(pid), str(cid)
        max_edge = _parse_int_nonneg(me)
        unit_cost = _parse_float(cost, default=1e9)
        edges[(pid, cid)] = {"max_edge": max_edge, "cost": unit_cost}

    # Previous allocation exemptions (no churn penalty iff amount > 0)
    prev_exempt = set()
    for a in prev_alloc_in:
        if not isinstance(a, list) or len(a) < 3:
            continue
        pid, cid, amount = str(a[0]), str(a[1]), _parse_int_nonneg(a[2])
        if amount > 0:
            prev_exempt.add((pid, cid))

    # Helper bounds checks (applied only to ops; never enforce minima)
    def total_cap_plus_em(provs: Dict[str, Dict[str, Any]]) -> int:
        s = 0
        for pv in provs.values():
            s += _parse_int_nonneg(pv.get("cap", 0))
            s += _parse_int_nonneg(pv.get("em_cap", 0))
        return s

    def total_dem(cons: Dict[str, Dict[str, Any]]) -> int:
        s = 0
        for cv in cons.values():
            s += _parse_int_nonneg(cv.get("dem", 0))
        return s

    def bounds_okay_after(
        provs: Dict[str, Dict[str, Any]],
        cons: Dict[str, Dict[str, Any]],
        edg_map: Dict[Tuple[str, str], Dict[str, Any]],
    ) -> bool:
        if len(provs) > 20:
            return False
        if len(cons) > 30:
            return False
        if len(edg_map) > 200:
            return False
        if total_cap_plus_em(provs) > 200:
            return False
        if total_dem(cons) > 200:
            return False
        return True

    # Apply ops in order; ignore any op that would violate bounds.
    for op in ops_in:
        if not op:
            continue
        kind = op[0] if op else None

        # Make working copies for tentative application
        t_prov = {k: dict(v) for k, v in providers.items()}
        t_cons = {k: dict(v) for k, v in consumers.items()}
        t_edges = {k: dict(v) for k, v in edges.items()}

        applied = False

        if kind == "set_state" and len(op) >= 3:
            pid, new_state = str(op[1]), str(op[2])
            if pid in t_prov and new_state in ValidStates:
                t_prov[pid]["state"] = new_state
                applied = True

        elif kind == "set_capacity" and len(op) >= 4:
            pid = str(op[1])
            if pid in t_prov:
                nc = _parse_int_nonneg(op[2])
                ne = _parse_int_nonneg(op[3])
                t_prov[pid]["cap"] = nc
                t_prov[pid]["em_cap"] = ne
                applied = True

        elif kind == "merge_consumers" and len(op) >= 3:
            new_id = str(op[1])
            merge_ids = list(op[2]) if isinstance(op[2], list) else []
            if new_id and merge_ids:
                # Validate existence and single-layer
                if new_id in t_cons:
                    applied = False
                else:
                    all_exist = all(mid in t_cons for mid in merge_ids)
                    if all_exist:
                        layers = {t_cons[mid]["layer"] for mid in merge_ids}
                        if len(layers) == 1:
                            # Build merged
                            dem_sum = sum(
                                _parse_int_nonneg(t_cons[mid]["dem"])
                                for mid in merge_ids
                            )
                            # tier = max by weight
                            max_tier = "normal"
                            max_w = -1
                            for mid in merge_ids:
                                tr = t_cons[mid]["tier"]
                                w = _tier_weight(tr)
                                if w > max_w:
                                    max_w = w
                                    max_tier = tr
                            new_cons = {
                                "id": new_id,
                                "dem": dem_sum,
                                "tier": max_tier,
                                "layer": t_cons[merge_ids[0]]["layer"],
                                "segment": t_cons[merge_ids[0]]["segment"],
                            }
                            # Apply: remove olds, add new
                            for mid in merge_ids:
                                t_cons.pop(mid, None)
                            t_cons[new_id] = new_cons
                            applied = True
                        else:
                            applied = False

        elif kind == "split_consumer" and len(op) >= 3:
            old_id = str(op[1])
            parts = op[2] if isinstance(op[2], list) else []
            if old_id in t_cons and parts:
                # Prepare new set
                t_cons.pop(old_id, None)
                for part in parts:
                    cid = str(part.get("id", "") or "")
                    if not cid:
                        continue
                    ncons = {
                        "id": cid,
                        "dem": _parse_int_nonneg(part.get("dem", 0)),
                        "tier": str(part.get("tier", "normal")).lower(),
                        "layer": _parse_int_nonneg(part.get("layer", 0)),
                        "segment": str(part.get("segment", "")),
                    }
                    if ncons["tier"] not in TierWeights:
                        ncons["tier"] = "normal"
                    t_cons[cid] = ncons
                applied = True

        elif kind == "add_edge" and len(op) >= 5:
            pid, cid = str(op[1]), str(op[2])
            me = _parse_int_nonneg(op[3])
            cost = _parse_float(op[4], default=1e9)
            t_edges[(pid, cid)] = {"max_edge": me, "cost": cost}
            applied = True

        elif kind == "remove_edge" and len(op) >= 3:
            pid, cid = str(op[1]), str(op[2])
            t_edges.pop((pid, cid), None)
            applied = True

        # Only commit if bounds hold and we actually changed something meaningful
        if applied and bounds_okay_after(t_prov, t_cons, t_edges):
            providers, consumers, edges = t_prov, t_cons, t_edges

    # Build remaining capacities and edge caps
    prov_remaining: Dict[str, int] = {}
    for pid, p in providers.items():
        cap = _parse_int_nonneg(p.get("cap", 0))
        em = _parse_int_nonneg(p.get("em_cap", 0))
        state = str(p.get("state", "normal"))
        prov_remaining[pid] = _usable_capacity(state, cap, em)

    cons_dem: Dict[str, int] = {
        cid: _parse_int_nonneg(c.get("dem", 0)) for cid, c in consumers.items()
    }
    cons_alloc: Dict[str, int] = {cid: 0 for cid in consumers.keys()}
    cons_weight: Dict[str, int] = {
        cid: _tier_weight(consumers[cid].get("tier", "normal"))
        for cid in consumers.keys()
    }

    edge_remaining: Dict[Tuple[str, str], int] = {}
    edge_cost: Dict[Tuple[str, str], float] = {}
    for key, val in edges.items():
        edge_remaining[key] = _parse_int_nonneg(val.get("max_edge", 0))
        edge_cost[key] = _parse_float(val.get("cost", 1e9), default=1e9)

    # Helper: find consumers that can still receive at least one unit
    def _eligible_consumers() -> List[str]:
        elig = []
        for cid, c in consumers.items():
            dem = cons_dem.get(cid, 0)
            alloc = cons_alloc.get(cid, 0)
            if dem <= alloc or dem <= 0:
                continue
            # Check if there exists a feasible (provider, cid)
            clayer = c.get("layer", 0)
            feasible = False
            for pid, p in providers.items():
                if prov_remaining.get(pid, 0) <= 0:
                    continue
                if p.get("layer", 0) != clayer:
                    continue
                if edge_remaining.get((pid, cid), 0) <= 0:
                    continue
                # endpoints must exist; already ensured by dicts
                feasible = True
                break
            if feasible:
                elig.append(cid)
        return elig

    result: List[List[str]] = []

    # Allocation loop: unit-by-unit weighted max-min water-filling
    while True:
        candidates = _eligible_consumers()
        if not candidates:
            break

        # Compute fairness ratio allocated_i / (w_i * dem_i); choose min, ties by consumer_id
        def fair_key(cid: str):
            alloc = cons_alloc.get(cid, 0)
            w = max(1, cons_weight.get(cid, 1))
            d = max(1, cons_dem.get(cid, 1))
            ratio = alloc / (w * d)
            return (ratio, cid)

        candidates.sort(key=fair_key)
        chosen_cid = candidates[0]
        chosen_c = consumers[chosen_cid]
        chosen_layer = chosen_c.get("layer", 0)

        # Among eligible providers for chosen consumer, pick min effective cost
        provider_choices: List[List[Any]] = []
        for pid, p in providers.items():
            if prov_remaining.get(pid, 0) <= 0:
                continue
            if p.get("layer", 0) != chosen_layer:
                continue
            if edge_remaining.get((pid, chosen_cid), 0) <= 0:
                continue
            base_cost = edge_cost.get((pid, chosen_cid), 1e9)
            priority = _parse_int_nonneg(p.get("priority", 0))
            churn_pen = 0.0 if (pid, chosen_cid) in prev_exempt else 0.5
            eff = base_cost - 0.1 * priority + churn_pen
            provider_choices.append([eff, pid])

        if not provider_choices:
            # No provider can serve this consumer anymore; remove it from consideration this round
            # and continue to next best consumer. To guarantee progress/determinism, mark it ineligible
            # for this iteration by temporarily setting demand to current allocation.
            cons_dem[chosen_cid] = cons_alloc.get(chosen_cid, 0)
            continue

        provider_choices.sort(key=lambda x: (x[0], x[1], chosen_cid))
        chosen_pid = provider_choices[0][1]

        # Allocate one unit
        prov_remaining[chosen_pid] -= 1
        edge_remaining[(chosen_pid, chosen_cid)] -= 1
        cons_alloc[chosen_cid] += 1
        result.append([chosen_pid, chosen_cid])

    return result
`