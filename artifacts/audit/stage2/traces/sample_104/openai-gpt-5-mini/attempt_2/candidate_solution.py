def optimize_resource_allocation(graph: "BipartiteGraph") -> List[List[str]]:
    # Helpers
    def to_int(v, default=0):
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            try:
                return int(float(v))
            except:
                return default
        return default

    def to_float(v, default=1e9):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except:
                return default
        return default

    tier_weight = {"critical":3, "essential":2, "normal":1}

    # Deep copy-like rebuild
    providers_raw = graph.get("providers", []) or []
    consumers_raw = graph.get("consumers", []) or []
    edges_raw = graph.get("edges", []) or []
    prev_alloc_raw = graph.get("prev_alloc", []) or []
    ops_raw = graph.get("ops", []) or []

    # Normalize providers and consumers into dicts with overwrite semantics
    providers = {}
    for p in providers_raw:
        pid = str(p.get("id"))
        cap = to_int(p.get("cap",0),0)
        em_cap = to_int(p.get("em_cap",0),0)
        if cap < 0: cap = 0
        if em_cap < 0: em_cap = 0
        priority = to_int(p.get("priority",0),0)
        state = p.get("state","normal")
        if state not in ("normal","peak","maintenance"):
            state = "normal"
        layer = to_int(p.get("layer",0),0)
        segment = str(p.get("segment",""))
        providers[pid] = {"id":pid,"cap":cap,"em_cap":em_cap,"priority":priority,"state":state,"layer":layer,"segment":segment}

    consumers = {}
    for c in consumers_raw:
        cid = str(c.get("id"))
        dem = to_int(c.get("dem",0),0)
        if dem < 0: dem = 0
        tier = c.get("tier","normal")
        if tier not in ("critical","essential","normal"):
            tier = "normal"
        layer = to_int(c.get("layer",0),0)
        segment = str(c.get("segment",""))
        consumers[cid] = {"id":cid,"dem":dem,"tier":tier,"layer":layer,"segment":segment}

    # Edges map (provider,consumer) -> dict
    edges = {}
    for e in edges_raw:
        if not isinstance(e, (list,tuple)) or len(e) < 4: continue
        pid = str(e[0]); cid = str(e[1])
        max_edge = to_int(e[2],0)
        if max_edge < 0: max_edge = 0
        unit_cost = to_float(e[3],1e9)
        edges[(pid,cid)] = {"max_edge":max_edge,"unit_cost":unit_cost}

    # prev_alloc map for indicator: count>0 means existed
    prev_alloc_map = {}
    for pa in prev_alloc_raw:
        if not isinstance(pa, (list,tuple)) or len(pa) < 3: continue
        pid = str(pa[0]); cid = str(pa[1]); amt = to_int(pa[2],0)
        if amt < 0: amt = 0
        if amt > 0:
            prev_alloc_map[(pid,cid)] = prev_alloc_map.get((pid,cid),0) + amt

    # Normalize ops format: allow flattened single op?
    ops = []
    if isinstance(ops_raw, list) and ops_raw and all(not isinstance(x, list) for x in ops_raw):
        # single flattened op? But spec allows list-of-lists or single flattened op.
        ops = [ops_raw]
    else:
        ops = list(ops_raw)

    # Apply ops in order, ignoring those that would violate bounds.
    def current_bounds_ok(pdict, cdict, edict):
        if not (0 <= len(pdict) <= 20 and 0 <= len(cdict) <= 30 and 0 <= len(edict) <= 200):
            return False
        s_cap = sum(max(0,to_int(x.get("cap",0),0))+max(0,to_int(x.get("em_cap",0),0)) for x in pdict.values())
        s_dem = sum(max(0,to_int(x.get("dem",0),0)) for x in cdict.values())
        if s_cap > 200 or s_dem > 200:
            return False
        return True

    for op in ops:
        if not isinstance(op, (list,tuple)) or not op:
            continue
        typ = op[0]
        # make copies to test effect
        p2 = {k:v.copy() for k,v in providers.items()}
        c2 = {k:v.copy() for k,v in consumers.items()}
        e2 = {k:v.copy() for k,v in edges.items()}
        ignore = False
        if typ == "set_state" and len(op) >= 3:
            pid = str(op[1]); state = op[2]
            if pid in p2 and state in ("normal","peak","maintenance"):
                p2[pid]["state"] = state
        elif typ == "set_capacity" and len(op) >= 4:
            pid = str(op[1]); cap = to_int(op[2],0); em_cap = to_int(op[3],0)
            if cap < 0 or em_cap < 0:
                # ignore
                pass
            else:
                if pid in p2:
                    p2[pid]["cap"] = cap
                    p2[pid]["em_cap"] = em_cap
        elif typ == "merge_consumers" and len(op) >= 3:
            new_id = str(op[1]); ids = list(op[2]) if op[2] else []
            # validate existences: all ids must exist
            if not ids:
                ignore = True
            else:
                # compute merged demand and tier weight
                total_dem = 0
                # pick tier with highest numerical weight; tie -> first in list
                best_tier = None
                best_weight = -1
                layers = set()
                segment = None
                for idx,iid in enumerate(ids):
                    iid = str(iid)
                    if iid not in c2:
                        ignore = True; break
                    ci = c2[iid]
                    total_dem += max(0,to_int(ci.get("dem",0),0))
                    tw = tier_weight.get(ci.get("tier","normal"),1)
                    if tw > best_weight:
                        best_weight = tw; best_tier = ci.get("tier","normal")
                    if idx == 0:
                        segment = ci.get("segment","")
                    layers.add(ci.get("layer",0))
                if not ignore:
                    if len(layers) != 1:
                        ignore = True
                    else:
                        layer = layers.pop()
                        # remove old ids
                        for iid in ids:
                            iid = str(iid)
                            if iid in c2: del c2[iid]
                        c2[new_id] = {"id":new_id,"dem":total_dem,"tier":best_tier,"layer":layer,"segment":segment}
        elif typ == "split_consumer" and len(op) >= 3:
            old_id = str(op[1]); parts = op[2]
            if old_id not in c2:
                ignore = True
            else:
                # parts is list of dicts
                total_new_dem = 0
                for part in parts:
                    if not isinstance(part, dict) or "id" not in part or "dem" not in part:
                        ignore = True; break
                    pid = str(part.get("id"))
                    demv = to_int(part.get("dem",0),0)
                    if demv < 0:
                        ignore = True; break
                    total_new_dem += demv
                if not ignore:
                    # demand must sum equal? spec doesn't state, assume allowed any; but bounds will check totals.
                    del c2[old_id]
                    for part in parts:
                        pid = str(part.get("id"))
                        demv = to_int(part.get("dem",0),0)
                        tier = part.get("tier","normal")
                        if tier not in ("critical","essential","normal"): tier="normal"
                        layer = to_int(part.get("layer",0),0)
                        segment = str(part.get("segment",""))
                        c2[pid] = {"id":pid,"dem":demv,"tier":tier,"layer":layer,"segment":segment}
        elif typ == "add_edge" and len(op) >= 5:
            pid = str(op[1]); cid = str(op[2]); max_edge = to_int(op[3],0); unit_cost = to_float(op[4],1e9)
            if max_edge < 0:
                ignore = True
            else:
                e2[(pid,cid)] = {"max_edge":max_edge,"unit_cost":unit_cost}
        elif typ == "remove_edge" and len(op) >= 3:
            pid = str(op[1]); cid = str(op[2])
            if (pid,cid) in e2: del e2[(pid,cid)]
        else:
            # unknown op -> ignore
            continue

        if ignore:
            continue
        if current_bounds_ok(p2,c2,e2):
            providers = p2; consumers = c2; edges = e2
        else:
            # ignore op
            continue

    # After ops, coerce numeric strings etc were handled; enforce normalization again
    for pid,p in list(providers.items()):
        p["cap"] = max(0,to_int(p.get("cap",0),0))
        p["em_cap"] = max(0,to_int(p.get("em_cap",0),0))
        p["priority"] = max(0,to_int(p.get("priority",0),0))
        if p.get("state") not in ("normal","peak","maintenance"):
            p["state"]="normal"
        p["layer"] = to_int(p.get("layer",0),0)
    for cid,c in list(consumers.items()):
        c["dem"] = max(0,to_int(c.get("dem",0),0))
        if c.get("tier") not in ("critical","essential","normal"):
            c["tier"]="normal"
        c["layer"] = to_int(c.get("layer",0),0)

    # Usable providers capacity depending on state
    prov_remaining = {}
    for pid,p in providers.items():
        state = p.get("state","normal")
        if state == "maintenance":
            usable = 0
        elif state == "normal":
            usable = p.get("cap",0)
        elif state == "peak":
            usable = p.get("cap",0) + p.get("em_cap",0)
        else:
            usable = p.get("cap",0)
        usable = max(0, to_int(usable,0))
        prov_remaining[pid] = usable

    # Edge remaining per-edge
    edge_remaining = {}
    edge_cost = {}
    for (pid,cid),ed in edges.items():
        max_e = max(0,to_int(ed.get("max_edge",0),0))
        edge_remaining[(pid,cid)] = max_e
        edge_cost[(pid,cid)] = to_float(ed.get("unit_cost",1e9),1e9)

    # Consumers unmet demand
    cons_unmet = {}
    for cid,c in consumers.items():
        cons_unmet[cid] = max(0,to_int(c.get("dem",0),0))

    # Only edges usable if both endpoints exist and layer matches
    def eligible_providers_for_consumer(cid):
        res = []
        if cid not in consumers: return res
        cl = consumers[cid]["layer"]
        for pid,p in providers.items():
            if p["layer"] != cl: continue
            if prov_remaining.get(pid,0) <= 0: continue
            if (pid,cid) not in edge_remaining: continue
            if edge_remaining.get((pid,cid),0) <= 0: continue
            res.append(pid)
        return res

    # Prev alloc indicator: need to know if pair had amount>0
    prev_has = set(k for k,v in prev_alloc_map.items() if v>0)

    allocation = []  # list of [pid,cid] per unit

    # Main loop: allocate unit-by-unit
    while True:
        # Build list of consumers with unmet demand >0 and at least one eligible provider
        candidates = []
        for cid,unmet in cons_unmet.items():
            if unmet <= 0: continue
            elig = eligible_providers_for_consumer(cid)
            if not elig: continue
            weight = tier_weight.get(consumers[cid]["tier"],1)
            dem = max(1,to_int(consumers[cid].get("dem",0),0))
            allocated = consumers[cid].get("_allocated",0)
            metric = allocated / (weight * dem) if (weight*dem)>0 else float('inf')
            candidates.append((metric,cid))
        if not candidates:
            break
        # choose consumer with minimal metric; tie by consumer_id lexicographic
        candidates.sort(key=lambda x: (x[0], x[1]))
        _, chosen_cid = candidates[0]

        # For chosen consumer, pick provider minimizing effective_cost
        elig_providers = eligible_providers_for_consumer(chosen_cid)
        prov_choices = []
        for pid in elig_providers:
            if prov_remaining.get(pid,0) <= 0: continue
            if edge_remaining.get((pid,chosen_cid),0) <= 0: continue
            uc = edge_cost.get((pid,chosen_cid),1e9)
            priority = providers[pid].get("priority",0)
            indicator = 0 if (pid,chosen_cid) in prev_has else 1
            effective_cost = uc - 0.1 * priority + 0.5 * indicator
            prov_choices.append((effective_cost, pid))
        if not prov_choices:
            # no provider actually available
            # mark consumer as impossible by setting no elig; continue loop
            # but to avoid infinite loop, remove from consideration by setting unmet to 0?
            # Instead, break as no further units feasible for any consumer? No, others may be feasible.
            # So mark consumer unmet to 0 to skip it.
            cons_unmet[chosen_cid] = 0
            continue
        prov_choices.sort(key=lambda x: (x[0], x[1]))
        chosen_pid = prov_choices[0][1]

        # Allocate one unit
        allocation.append([chosen_pid, chosen_cid])
        prov_remaining[chosen_pid] = prov_remaining.get(chosen_pid,0) - 1
        edge_remaining[(chosen_pid,chosen_cid)] = edge_remaining.get((chosen_pid,chosen_cid),0) - 1
        cons_unmet[chosen_cid] = cons_unmet.get(chosen_cid,0) - 1
        consumers[chosen_cid]["_allocated"] = consumers[chosen_cid].get("_allocated",0) + 1

    return allocation