def optimize_routes(
    variables: List[str],
    clauses: List[List[str]],
    real_time_data: List[List[Any]],
    route_capacities: Dict[str, float] = None,
    route_emissions: Dict[str, float] = None,
    route_regions: Dict[str, str] = None,
    region_min_capacity: Dict[str, float] = None,
    region_max_emissions: Dict[str, float] = None,
    route_penalty_factors: Dict[str, float] = None,
    total_budget: float = 0.0,
    region_min_route_count: Dict[str, int] = None
) -> Dict[str, Any]:
    # Defaults
    route_capacities = route_capacities or {}
    route_emissions = route_emissions or {}
    route_regions = route_regions or {}
    region_min_capacity = region_min_capacity or {}
    region_max_emissions = region_max_emissions or {}
    route_penalty_factors = route_penalty_factors or {}
    region_min_route_count = region_min_route_count or {}

    # reserved keys from route_penalty_factors might include JSON strings or real values
    def extract_reserved(key, default):
        v = route_penalty_factors.get(key, default)
        return v

    dominance_share_cap = float(extract_reserved("__dominance_share_cap__", 1.0))
    max_emissions_intensity = float(extract_reserved("__max_emissions_intensity__", float("inf")))
    balance_penalty_lambda = float(extract_reserved("__balance_penalty_lambda__", 0.0))
    regional_budgets = extract_reserved("__regional_budgets__", {})
    mandatory_routes = set(extract_reserved("__mandatory_routes__", []))
    forbidden_routes = set(extract_reserved("__forbidden_routes__", []))
    pair_incompatibility_threshold = float(extract_reserved("__pair_incompatibility_threshold__", float("inf")))
    min_distinct_routes_per_region = extract_reserved("__min_distinct_routes_per_region__", {})
    max_raw_cost_share = float(extract_reserved("__max_raw_cost_share__", 1.0))
    greedy_seed = int(extract_reserved("__greedy_seed__", 0))
    beam_width = int(extract_reserved("__beam_width__", 1))
    epsilon_cost = float(extract_reserved("__epsilon_cost__", 1e-3))
    epsilon_constraints = float(extract_reserved("__epsilon_constraints__", 1e-9))

    # Build raw cost map from real_time_data: expects [route, cost]
    raw_costs = {r: float(c) for r, c in real_time_data}
    # Helper safe getters
    def cap(r): return float(route_capacities.get(r, 0.0))
    def emis(r): return float(route_emissions.get(r, 0.0))
    def region_of(r): return route_regions.get(r, None)
    def penalty(r): return float(route_penalty_factors.get(r, 0.0))
    routes = list(variables)

    # 2-SAT handling: variables are positive literals only; clauses are (A or B) where A,B are variable names possibly negated? Prompt implies names only positive.
    # We'll treat clause entries as possibly prefixed with '!' for negation. Normalize.
    def parse_lit(s):
        s = str(s)
        if s.startswith("!"):
            return (s[1:], False)
        return (s, True)

    parsed_clauses = []
    for cl in clauses:
        if len(cl) == 0:
            continue
        a = parse_lit(cl[0])
        b = parse_lit(cl[1]) if len(cl) > 1 else a
        parsed_clauses.append((a, b))

    # Build implication graph for 2-SAT: map literal to index
    vars_set = set(routes)
    idx = {}
    for v in vars_set:
        idx[(v, True)] = len(idx)
        idx[(v, False)] = len(idx)
    nvars2 = len(idx)

    g = [[] for _ in range(nvars2)]
    gr = [[] for _ in range(nvars2)]
    def add_imp(a, b):
        g[a].append(b)
        gr[b].append(a)

    def lit_index(l):
        (v, val) = l
        return idx[(v, val)]

    for (a, b) in parsed_clauses:
        # (a ∨ b) -> (!a => b) and (!b => a)
        na = (a[0], not a[1])
        nb = (b[0], not b[1])
        add_imp(lit_index(na), lit_index(b))
        add_imp(lit_index(nb), lit_index(a))

    # Tarjan SCC implementation
    N = nvars2
    index = 0
    indices = [-1]*N
    lowlink = [0]*N
    onstack = [False]*N
    S = []
    comp = [-1]*N
    compcount = 0

    def strongconnect(v):
        nonlocal index, compcount
        indices[v] = index
        lowlink[v] = index
        index += 1
        S.append(v); onstack[v] = True
        for w in g[v]:
            if indices[w] == -1:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif onstack[w]:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            while True:
                w = S.pop()
                onstack[w] = False
                comp[w] = compcount
                if w == v:
                    break
            compcount += 1

    for v in range(N):
        if indices[v] == -1:
            strongconnect(v)

    # Check unsatisfiable: variable and negation in same comp
    for v in vars_set:
        if comp[idx[(v, True)]] == comp[idx[(v, False)]]:
            return {}

    # Forced assignments: if raw_cost <=0 => forced FALSE (cannot select). Also zero-capacity prohibition.
    forced_assign = {}  # route -> False/True
    for r in routes:
        if raw_costs.get(r, 0.0) <= 0.0:
            forced_assign[r] = False
        if cap(r) <= 0.0:
            forced_assign[r] = False
        if r in forbidden_routes:
            forced_assign[r] = False
        if r in mandatory_routes:
            forced_assign[r] = True

    # free variables
    free_vars = [r for r in routes if r not in forced_assign]
    k = len(free_vars)

    pruning_operations = 0
    greedy_iterations = 0
    feasibility_checks = 0
    refinement_iterations = 0
    routes_removed = 0

    # helper compute metrics and feasibility
    regions = set(route_regions.get(r, None) for r in routes if route_regions.get(r, None) is not None)
    regions = set(r for r in regions if r is not None)

    def compute_stats(selected_set):
        # returns feasibility boolean and metrics
        nonlocal feasibility_checks
        feasibility_checks += 1
        sel = set(selected_set)
        # respect forced_assign
        for r,v in forced_assign.items():
            if v and r not in sel:
                return False, {}
            if (not v) and r in sel:
                return False, {}
        # zero-capacity prohibition already enforced
        # budget
        total_raw = sum(raw_costs.get(r,0.0) for r in sel)
        if total_budget > 0 and total_raw > total_budget + epsilon_constraints:
            return False, {}
        # per-region budgets
        regional_raw = defaultdict(float)
        regional_cap = defaultdict(float)
        regional_emis = defaultdict(float)
        regional_count = defaultdict(int)
        for r in sel:
            reg = region_of(r)
            regional_raw[reg] += raw_costs.get(r,0.0)
            regional_cap[reg] += cap(r)
            regional_emis[reg] += emis(r)
            regional_count[reg] += 1
        # region constraints
        for reg in regions:
            if regional_cap[reg] + epsilon_constraints < region_min_capacity.get(reg, 0.0) - epsilon_constraints:
                return False, {}
            if regional_emis[reg] > region_max_emissions.get(reg, float("inf")) + epsilon_constraints:
                return False, {}
            if regional_count[reg] < region_min_route_count.get(reg, 0):
                return False, {}
            # emissions intensity
            if regional_cap[reg] > 0:
                intensity = regional_emis[reg] / max(1e-12, regional_cap[reg])
                if intensity > max_emissions_intensity + epsilon_constraints:
                    return False, {}
            # per-region budgets
            if str(reg) in regional_budgets:
                if regional_raw[reg] > float(regional_budgets[str(reg)]) + epsilon_constraints:
                    return False, {}
            # min distinct routes per region
            min_dist = int(min_distinct_routes_per_region.get(str(reg), 0))
            if regional_count[reg] < min_dist:
                return False, {}
            # intra-region diversity: if region has >=3 open pos-cap candidates and min_route_count >=2 select at least 2 distinct
            open_candidates = [r for r in routes if region_of(r)==reg and cap(r)>0.0 and r not in forced_assign or (r in forced_assign and forced_assign[r])]
            if len(open_candidates) >=3 and region_min_route_count.get(reg,0) >=2:
                if regional_count[reg] < 2:
                    return False, {}
        # dominance caps and pair incompat
        total_capacity = sum(cap(r) for r in routes)
        for r in sel:
            if dominance_share_cap < 1.0 and total_capacity>0:
                if cap(r) > dominance_share_cap * total_capacity + epsilon_constraints:
                    return False, {}
            if raw_costs.get(r,0.0) > max_raw_cost_share * regional_raw.get(region_of(r), (total_raw if total_raw>0 else 1.0)) + epsilon_constraints:
                return False, {}
        # pair incompatibility: for same-region pairs sum capacity <= threshold
        by_region = defaultdict(list)
        for r in sel:
            by_region[region_of(r)].append(r)
        for reg, lst in by_region.items():
            for i in range(len(lst)):
                for j in range(i+1, len(lst)):
                    if cap(lst[i]) + cap(lst[j]) > pair_incompatibility_threshold + epsilon_constraints:
                        return False, {}
        # raw_cost share per route and regional
        # Compute adjusted costs
        adjusted = {}
        base = {}
        for r in sel:
            b = raw_costs.get(r,0.0)/max(cap(r),1.0)
            base[r]=b
            adjusted[r]= b * (1.0 + penalty(r))
        total_adjusted = sum(adjusted.values())
        # regional capacity variance
        caps = [regional_cap[r] for r in regions] if regions else [0.0]
        if regions:
            vals = [regional_cap[r] for r in regions]
            mean = sum(vals)/len(vals)
            var = sum((x-mean)**2 for x in vals)/len(vals)
        else:
            var = 0.0
        return True, {
            "total_raw": total_raw,
            "total_adjusted": total_adjusted,
            "adjusted_map": adjusted,
            "base_map": base,
            "regional_cap": regional_cap,
            "regional_raw": regional_raw,
            "regional_emis": regional_emis,
            "regional_count": regional_count,
            "variance": var,
            "num_routes": len(sel),
            "selected": sorted(list(sel))
        }

    # tie-breaker compare: a better than b -> True
    def better(a, b):
        if a is None: return False
        if b is None: return True
        ta = a["total_adjusted"]; tb = b["total_adjusted"]
        if abs(ta - tb) > epsilon_cost:
            return ta < tb
        if a["num_routes"] != b["num_routes"]:
            return a["num_routes"] < b["num_routes"]
        if a["total_raw"] != b["total_raw"]:
            return a["total_raw"] < b["total_raw"]
        # higher total capacity preferred
        tcap_a = sum(cap(r) for r in a["selected"])
        tcap_b = sum(cap(r) for r in b["selected"])
        if tcap_a != tcap_b:
            return tcap_a > tcap_b
        # lexicographically smaller
        if a["selected"] != b["selected"]:
            return a["selected"] < b["selected"]
        # variance lower if balance_penalty_lambda >0
        if balance_penalty_lambda > 0:
            if a["variance"] != b["variance"]:
                return a["variance"] < b["variance"]
        return False

    best_solution = None

    # Exhaustive for small k
    if k <= 18:
        # Map free_vars index
        fv_idx = {free_vars[i]: i for i in range(len(free_vars))}
        total = 1<<k
        for mask in range(total):
            sel = set()
            # add forced trues
            for r,v in forced_assign.items():
                if v:
                    sel.add(r)
            for i, r in enumerate(free_vars):
                if (mask>>i)&1:
                    sel.add(r)
            # skip forced falses present
            invalid=False
            for r,v in forced_assign.items():
                if (not v) and r in sel:
                    invalid=True; break
            if invalid:
                pruning_operations +=1
                continue
            # check mandatory
            if not mandatory_routes.issubset(sel):
                pruning_operations +=1
                continue
            ok, stats = compute_stats(sel)
            if not ok:
                pruning_operations +=1
                continue
            if better(stats, best_solution):
                best_solution = stats
    else:
        # Greedy deterministic with beam
        random.seed(greedy_seed)
        greedy_iterations = 0
        # maintain beam of candidate sets and their stats
        # start from mandatory routes
        start = set(r for r,v in forced_assign.items() if v) | set(mandatory_routes)
        # exclude forced false
        start = set(x for x in start if not (x in forced_assign and forced_assign[x]==False))
        # candidate pool: routes not forbidden and capacity>0
        pool = [r for r in routes if r not in forbidden_routes and not (r in forced_assign and forced_assign[r]==False)]
        # determine clause coverage: unsatisfied clauses that become satisfied by selecting route
        def clause_coverage(selected_set, route):
            # clause satisfied if any literal true
            cov = 0
            for (a,b) in parsed_clauses:
                # check currently satisfied
                def lit_true(lit, sel):
                    name, val = lit
                    present = name in sel
                    return present if val else (not present)
                if not (lit_true(a, selected_set) or lit_true(b, selected_set)):
                    # if adding route satisfies
                    if lit_true(a, selected_set|{route}) or lit_true(b, selected_set|{route}):
                        cov +=1
            return cov

        beam = [(start, None)]
        for it in range(10000):
            newbeam = []
            greedy_iterations +=1
            for (sel, _) in beam:
                # compute scores for candidates not yet selected
                candidates = [r for r in pool if r not in sel]
                scored = []
                for r in candidates:
                    b = raw_costs.get(r,0.0)/max(cap(r),1.0)
                    adj = b*(1.0+penalty(r))
                    cov = clause_coverage(sel, r)
                    score = cov / (adj if adj>0 else 1e-12)
                    # apply balance penalty
                    score = score - balance_penalty_lambda * (adj)
                    scored.append((score, r, adj))
                scored.sort(key=lambda x:(-x[0], x[2], x[1]))
                # expand top beam_width
                for sc in scored[:beam_width]:
                    new_sel = set(sel)
                    new_sel.add(sc[1])
                    ok, stats = compute_stats(new_sel)
                    if ok:
                        newbeam.append((new_sel, stats))
                    else:
                        # allow infeasible as well up to beam but count feasibility check already in compute_stats
                        pass
            if not newbeam:
                break
            # keep best beam_width by stats
            # rank by total_adjusted then tie-breakers
            newbeam_stats = []
            for s, st in newbeam:
                newbeam_stats.append((st, s))
            newbeam_stats.sort(key=lambda x: (x[0]["total_adjusted"], x[0]["num_routes"], x[0]["total_raw"], -sum(cap(r) for r in x[0]["selected"]), x[0]["selected"]))
            beam = [(s, st) for (st,s) in newbeam_stats[:beam_width]]
            # track best
            for s, st in beam:
                if better(st, best_solution):
                    best_solution = st
            # termination heuristic: if beam does not improve for some iterations, break
            # we break if we've done many iterations or no improvement last iter
            if greedy_iterations > 2000:
                break

    if best_solution is None:
        return {}

    # Post-processing refinement: attempt to remove redundant routes iteratively
    converged = False
    prev_selected = set(best_solution["selected"])
    for it in range(1000):
        refinement_iterations +=1
        removed_this_iter = 0
        # candidates sorted by descending adjusted weighted cost
        adjusted_map = best_solution["adjusted_map"]
        cand_sorted = sorted(best_solution["selected"], key=lambda r: (-adjusted_map.get(r, raw_costs.get(r,0.0)/max(cap(r),1.0)*(1+penalty(r))), r))
        changed = False
        for r in cand_sorted:
            if r in mandatory_routes or (r in forced_assign and forced_assign[r]):
                continue
            trial = set(best_solution["selected"])
            trial.remove(r)
            ok, stats = compute_stats(trial)
            if ok:
                # tie-breaker: accept if better or equal within epsilon_cost but passes TBs
                if better(stats, best_solution) or abs(stats["total_adjusted"] - best_solution["total_adjusted"]) <= epsilon_cost:
                    # ensure TB ordering: use better comparator; if equal, check tie order
                    if better(stats,