def optimize_resource_allocation(graph: "BipartiteGraph") -> List[List[str]]:
    # Helper parsers
    def to_int(x, default=0):
        try:
            if isinstance(x, str) and x.strip()=="":
                return default
            return int(float(x))
        except Exception:
            return default
    def to_float(x, default=1e9):
        try:
            return float(x)
        except Exception:
            return default

    # Deep copy-ish handling input dicts
    providers_in = { }  # id -> dict
    consumers_in = { }  # id -> dict
    edges_in = {}  # (p,c) -> [max_edge, unit_cost]
    prev_alloc = {}
    ops = graph.get("ops", [])
    # Normalize providers list, later entries overwrite earlier
    for p in graph.get("providers", []):
        pid = str(p.get("id"))
        providers_in[pid] = dict(p)
        providers_in[pid]['id'] = pid
    for c in graph.get("consumers", []):
        cid = str(c.get("id"))
        consumers_in[cid] = dict(c)
        consumers_in[cid]['id'] = cid
    for e in graph.get("edges", []):
        if not isinstance(e, (list,tuple)) or len(e) < 4:
            continue
        pid, cid, me, uc = str(e[0]), str(e[1]), e[2], e[3]
        edges_in[(pid,cid)] = [me, uc]
    for pa in graph.get("prev_alloc", []) or []:
        if len(pa) >= 3:
            key = (str(pa[0]), str(pa[1]))
            prev_alloc[key] = prev_alloc.get(key, 0) + max(0, to_int(pa[2],0))
    # Normalize numeric fields with coercions
    def normalize_provider(p):
        p = dict(p)
        p['id'] = str(p.get('id'))
        p['cap'] = max(0, to_int(p.get('cap',0),0))
        p['em_cap'] = max(0, to_int(p.get('em_cap',0),0))
        p['priority'] = max(0, to_int(p.get('priority',0),0))
        state = p.get('state','normal')
        if state not in ('normal','peak','maintenance'):
            state = 'normal'
        p['state'] = state
        p['layer'] = to_int(p.get('layer',0),0)
        p['segment'] = str(p.get('segment',''))
        return p
    def normalize_consumer(c):
        c = dict(c)
        c['id'] = str(c.get('id'))
        c['dem'] = max(0, to_int(c.get('dem',0),0))
        tier = c.get('tier','normal')
        if tier not in ('critical','essential','normal'):
            tier = 'normal'
        c['tier'] = tier
        c['layer'] = to_int(c.get('layer',0),0)
        c['segment'] = str(c.get('segment',''))
        return c
    def normalize_edge(me_uc):
        me, uc = me_uc
        me = max(0, to_int(me,0))
        uc = to_float(uc,1e9)
        return [me, uc]

    providers = {}
    for pid,p in providers_in.items():
        providers[pid] = normalize_provider(p)
    consumers = {}
    for cid,c in consumers_in.items():
        consumers[cid] = normalize_consumer(c)
    edges = {}
    for (pid,cid),(me,uc) in edges_in.items():
        edges[(pid,cid)] = normalize_edge((me,uc))

    # Apply ops; ops can be flattened list or list-of-lists
    ops_list = []
    if isinstance(ops, list) and ops and not (isinstance(ops[0], (list,tuple))):
        # flattened? uncertain; but accept if length matches
        # try to chunk by first token types; safer: treat as given list-of-lists if elements are lists
        # If it's flat, ignore (ambiguous). But spec: accept either list-of-lists or single flattened op.
        ops_list = [ops]
    else:
        ops_list = list(ops)

    # Bound checking helpers
    def bounds_ok(providers_d, consumers_d, edges_d):
        if not (0 <= len(providers_d) <= 20): return False
        if not (0 <= len(consumers_d) <= 30): return False
        if not (0 <= len(edges_d) <= 200): return False
        s_caps = sum(max(0, to_int(p['cap'],0)) + max(0, to_int(p.get('em_cap',0),0)) for p in providers_d.values())
        s_dem = sum(max(0, to_int(c['dem'],0)) for c in consumers_d.values())
        if s_caps > 200 or s_dem > 200: return False
        return True

    tier_weight = {'critical':3,'essential':2,'normal':1}

    for op in ops_list:
        if not op or not isinstance(op, (list,tuple)): continue
        typ = op[0]
        try:
            if typ == "set_state":
                _, pid, state = op
                pid = str(pid)
                if pid in providers and state in ('normal','peak','maintenance'):
                    old = dict(providers)
                    providers[pid]['state'] = state
                    if not bounds_ok(providers, consumers, edges):
                        providers = old
            elif typ == "set_capacity":
                _, pid, cap, em_cap = op
                pid = str(pid)
                if pid in providers:
                    old = dict(providers)
                    providers[pid]['cap'] = max(0, to_int(cap,0))
                    providers[pid]['em_cap'] = max(0, to_int(em_cap,0))
                    if not bounds_ok(providers, consumers, edges):
                        providers = old
            elif typ == "merge_consumers":
                _, new_id, ids = op
                new_id = str(new_id)
                ids = [str(x) for x in ids]
                # check all exist and same layer
                if not ids: continue
                exist = all(i in consumers for i in ids)
                if not exist: continue
                layers = {consumers[i]['layer'] for i in ids}
                if len(layers)!=1: continue
                old_providers = dict(providers); old_consumers = dict(consumers); old_edges = dict(edges)
                total_dem = sum(consumers[i]['dem'] for i in ids)
                # tier highest numerical weight; tie -> first id in list
                weights = [(tier_weight[consumers[i]['tier']], i) for i in ids]
                maxw = max(w for w,i in weights)
                chosen_tier = None
                for i in ids:
                    if tier_weight[consumers[i]['tier']] == maxw:
                        chosen_tier = consumers[i]['tier']; break
                newc = {'id':new_id, 'dem': total_dem, 'tier': chosen_tier, 'layer': consumers[ids[0]]['layer'], 'segment': consumers[ids[0]]['segment']}
                # remove old ids
                for i in ids:
                    consumers.pop(i, None)
                    # remove edges to them
                    for k in list(edges.keys()):
                        if k[1] == i:
                            edges.pop(k,None)
                consumers[new_id] = normalize_consumer(newc)
                if not bounds_ok(providers, consumers, edges):
                    providers = old_providers; consumers = old_consumers; edges = old_edges
            elif typ == "split_consumer":
                _, old_id, parts = op
                old_id = str(old_id)
                if old_id not in consumers: continue
                # parts is list of dicts
                old_providers = dict(providers); old_consumers = dict(consumers); old_edges = dict(edges)
                total_dem_parts = 0
                new_parts = []
                ok = True
                for part in parts:
                    if not isinstance(part, dict) or 'id' not in part:
                        ok = False; break
                    pid = str(part['id'])
                    p = {'id':pid, 'dem': part.get('dem',0), 'tier': part.get('tier', 'normal'), 'layer': part.get('layer', consumers[old_id]['layer']), 'segment': part.get('segment', consumers[old_id]['segment'])}
                    p = normalize_consumer(p)
                    total_dem_parts += p['dem']
                    new_parts.append(p)
                if not ok: continue
                # optionally allow mismatch in demand? Spec: remove old. If op would violate bounds ignore.
                consumers.pop(old_id, None)
                # remove edges to old_id
                for k in list(edges.keys()):
                    if k[1] == old_id:
                        edges.pop(k,None)
                for p in new_parts:
                    consumers[p['id']] = p
                if not bounds_ok(providers, consumers, edges):
                    providers = old_providers; consumers = old_consumers; edges = old_edges
            elif typ == "add_edge":
                _, pid, cid, me, uc = op
                pid = str(pid); cid = str(cid)
                old_edges = dict(edges)
                edges[(pid,cid)] = normalize_edge((me,uc))
                if not bounds_ok(providers, consumers, edges):
                    edges = old_edges
            elif typ == "remove_edge":
                _, pid, cid = op
                pid = str(pid); cid = str(cid)
                if (pid,cid) in edges:
                    old_edges = dict(edges)
                    edges.pop((pid,cid),None)
                    if not bounds_ok(providers, consumers, edges):
                        edges = old_edges
        except Exception:
            continue

    # After ops, re-normalize data structures
    providers = {pid: normalize_provider(p) for pid,p in providers.items()}
    consumers = {cid: normalize_consumer(c) for cid,c in consumers.items()}
    edges = {k: normalize_edge(v) for k,v in edges.items()}

    # Usable edges only when both endpoints exist and layer equal; we'll check per use.
    # Compute usable capacity per provider by state
    def usable_cap(p):
        st = p['state']
        if st == 'maintenance':
            return 0
        if st == 'normal':
            return p['cap']
        if st == 'peak':
            return p['cap'] + p.get('em_cap',0)
        return p['cap']

    # Initialize remaining capacities and demands, and edge remaining
    prov_rem = {pid: max(0, usable_cap(p)) for pid,p in providers.items()}
    cons_rem = {cid: max(0, c['dem']) for cid,c in consumers.items()}
    edge_rem = {}
    edge_cost = {}
    for (pid,cid),(me,uc) in edges.items():
        # only usable if both endpoints exist and same layer
        if pid in providers and cid in consumers and providers[pid]['layer'] == consumers[cid]['layer']:
            edge_rem[(pid,cid)] = max(0, me)
            edge_cost[(pid,cid)] = uc
    # prev_alloc map for indicator per pair >0
    prev_present = {k: (v>0) for k,v in prev_alloc.items()}

    # Allocation result: list of [p,c] pairs each unit
    allocation = []

    # Precompute list of consumers eligible at all (with at least one provider edge and provider cap>0)
    # We'll loop unit-by-unit as per rules
    # For lexicographic weighted max-min we need allocated_i / (weight * dem_i)
    allocated = {cid:0 for cid in consumers.keys()}

    # Total possible units bounded
    total_possible = sum(cons_rem.values())
    # Loop until can't allocate more
    while True:
        # Build list of consumers with unmet demand and at least one eligible provider with positive capacity and edge rem
        candidates = []
        for cid, rem_dem in cons_rem.items():
            if rem_dem <= 0: continue
            # check if any provider eligible
            has = False
            for pid in providers.keys():
                if prov_rem.get(pid,0) <= 0: continue
                if (pid,cid) not in edge_rem: continue
                if edge_rem[(pid,cid)] <= 0: continue
                # layer check already enforced in edge_rem construction
                has = True; break
            if has:
                w = tier_weight.get(consumers[cid]['tier'],1)
                denom = w * max(1, consumers[cid]['dem'])
                val = allocated.get(cid,0) / denom
                candidates.append((val, cid))
        if not candidates:
            break
        # choose consumer minimizing value, tie-break by consumer_id lexicographic
        candidates.sort(key=lambda x: (x[0], x[1]))
        chosen_cid = candidates[0][1]
        # For chosen consumer, pick provider per effective_cost formula among eligible providers
        prov_list = []
        for pid in providers.keys():
            if prov_rem.get(pid,0) <= 0: continue
            if (pid,chosen_cid) not in edge_rem: continue
            if edge_rem[(pid,chosen_cid)] <= 0: continue
            # unit_cost
            uc = edge_cost.get((pid,chosen_cid), 1e9)
            prio = providers[pid].get('priority',0)
            indicator = 0 if prev_present.get((pid,chosen_cid), False) else 1
            eff = uc - 0.1 * prio + 0.5 * indicator
            prov_list.append((eff, pid))
        if not prov_list:
            # no eligible provider for this consumer anymore; remove consumer from consideration
            cons_rem[chosen_cid] = 0
            continue
        # tie-break by (provider_id, consumer_id) lexicographic when eff equal: include consumer id
        prov_list.sort(key=lambda x: (round(x[0],12), x[1], chosen_cid))
        chosen_pid = prov_list[0][1]
        # allocate one unit
        allocation.append([chosen_pid, chosen_cid])
        prov_rem[chosen_pid] -= 1
        cons_rem[chosen_cid] -= 1
        edge_rem[(chosen_pid,chosen_cid)] -= 1
        allocated[chosen_cid] = allocated.get(chosen_cid,0) + 1
        # loop continues
        # Stop if allocations exceed 200 units as a safety
        if len(allocation) >= 200:
            break

    return allocation