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

    # Reserved keys from penalty dict
    dominance_share_cap = route_penalty_factors.get("__dominance_share_cap__", 1.0)
    max_emissions_intensity = route_penalty_factors.get("__max_emissions_intensity__", float("inf"))
    balance_penalty_lambda = route_penalty_factors.get("__balance_penalty_lambda__", 0.0)
    regional_budgets = route_penalty_factors.get("__regional_budgets__", {}) or {}
    mandatory_routes = set(route_penalty_factors.get("__mandatory_routes__", []) or [])
    forbidden_routes = set(route_penalty_factors.get("__forbidden_routes__", []) or [])
    pair_incompatibility_threshold = route_penalty_factors.get("__pair_incompatibility_threshold__", float("inf"))
    min_distinct_per_region = route_penalty_factors.get("__min_distinct_routes_per_region__", {}) or {}
    max_raw_cost_share = route_penalty_factors.get("__max_raw_cost_share__", 1.0)
    greedy_seed = int(route_penalty_factors.get("__greedy_seed__", 0))
    beam_width = max(1, int(route_penalty_factors.get("__beam_width__", 1)))
    epsilon_cost = float(route_penalty_factors.get("__epsilon_cost__", 1e-3))
    epsilon_constraints = float(route_penalty_factors.get("__epsilon_constraints__", 1e-9))

    # Map variables to indices for 2-SAT
    var_index = {v: i for i, v in enumerate(variables)}
    n = len(variables)

    # Build implication graph for 2-SAT (using literal indexing: x -> 2*i, not x -> 2*i^1)
    m = 2 * n
    g = [[] for _ in range(m)]
    grev = [[] for _ in range(m)]

    def lit(vname, positive=True):
        if vname not in var_index:
            return None
        i = var_index[vname]
        return 2 * i + (0 if positive else 1)

    def add_imp(a, b):
        g[a].append(b)
        grev[b].append(a)

    # Clause (A or B) => (!A -> B) and (!B -> A)
    for clause in clauses:
        if not clause:
            continue
        if len(clause) == 1:
            A = clause[0]
            la = lit(A, True)
            if la is None: continue
            add_imp(la ^ 1, la)
        else:
            A, B = clause[0], clause[1]
            la = lit(A, True); lb = lit(B, True)
            if la is None or lb is None: continue
            add_imp(la ^ 1, lb)
            add_imp(lb ^ 1, la)

    # Forced false from closure cost <=0
    raw_cost_map = {r: v for r, v in real_time_data}
    for r, cost in raw_cost_map.items():
        if cost is not None and cost <= 0.0 and r in var_index:
            idx = lit(r, True)
            add_imp(idx, idx ^ 1)  # x -> not x

    # Kosaraju for SCCs
    visited = [False] * m
    order = []

    def dfs1(u):
        visited[u] = True
        for v in g[u]:
            if not visited[v]:
                dfs1(v)
        order.append(u)

    for i in range(m):
        if not visited[i]:
            dfs1(i)
    comp = [-1] * m
    cid = 0

    def dfs2(u, cid):
        comp[u] = cid
        for v in grev[u]:
            if comp[v] == -1:
                dfs2(v, cid)

    for u in reversed(order):
        if comp[u] == -1:
            dfs2(u, cid)
            cid += 1

    assignment_forced = {}
    for vname, i in var_index.items():
        if comp[2 * i] == comp[2 * i + 1]:
            return {}
        # if component of not x > comp of x in topological order => x = True
        assignment_forced[vname] = None

    # detect forced false from implication closure simple pass: if x -> not x then forced false
    for vname, i in var_index.items():
        if (2 * i) < len(g):
            if (2 * i ^ 1) in g[2 * i]:
                assignment_forced[vname] = False
        if (2 * i + 1) < len(g):
            if (2 * i + 1 ^ 1) in g[2 * i + 1]:
                assignment_forced[vname] = True

    # Zero-capacity prohibition: cannot select routes with capacity <=0
    for r in variables:
        if route_capacities.get(r, 0.0) <= 0.0:
            assignment_forced[r] = False

    # Prepare route metrics
    def base_weighted_cost(r):
        raw = float(raw_cost_map.get(r, 0.0))
        cap = max(1.0, float(route_capacities.get(r, 0.0)))
        return raw / cap

    def adjusted_weighted_cost(r):
        bw = base_weighted_cost(r)
        return bw * (1.0 + float(route_penalty_factors.get(r, 0.0)))

    all_routes = list(variables)
    free_vars = [r for r in all_routes if assignment_forced.get(r) is None]
    forced_selected = [r for r, v in assignment_forced.items() if v is True]
    forced_unselected = [r for r, v in assignment_forced.items() if v is False]

    pruning_operations = 0
    greedy_iterations = 0
    feasibility_checks = 0
    refinement_iterations = 0
    routes_removed = 0
    converged = True

    # Helper: evaluate feasibility given selected set
    def check_constraints(selected):
        nonlocal feasibility_checks
        feasibility_checks += 1
        sel = set(selected)
        # mandatory/forbidden
        if not mandatory_routes.issubset(sel):
            return False
        if forbidden_routes & sel:
            return False
        # capacities per region
        region_caps = defaultdict(float)
        region_emis = defaultdict(float)
        region_counts = defaultdict(int)
        region_raw = defaultdict(float)
        for r in sel:
            cap = float(route_capacities.get(r, 0.0))
            emis = float(route_emissions.get(r, 0.0))
            region = route_regions.get(r, "")
            region_caps[region] += cap
            region_emis[region] += emis
            region_counts[region] += 1
            region_raw[region] += float(raw_cost_map.get(r, 0.0))
            # per-route dominance share
            total_region_cap = sum(route_capacities.get(rr, 0.0) for rr in all_routes if route_regions.get(rr, "") == region)
            if total_region_cap > 0 and cap > dominance_share_cap * total_region_cap + epsilon_constraints:
                return False
            # emissions intensity
            if cap > 0 and (emis / cap) > max_emissions_intensity + epsilon_constraints:
                return False
            # raw cost share within region
            total_region_raw = sum(float(raw_cost_map.get(rr, 0.0)) for rr in all_routes if route_regions.get(rr, "") == region)
            if total_region_raw > 0 and float(raw_cost_map.get(r, 0.0)) > max_raw_cost_share * total_region_raw + epsilon_constraints:
                return False
        # regional budgets
        for region, lim in regional_budgets.items():
            if region_raw.get(region, 0.0) > lim + epsilon_constraints:
                return False
        # region-level mins and max emissions
        for region, mincap in region_min_capacity.items():
            if region_caps.get(region, 0.0) + epsilon_constraints < mincap:
                return False
        for region, maxe in region_max_emissions.items():
            if region_emis.get(region, 0.0) - epsilon_constraints > maxe:
                return False
        # route counts
        for region, mincount in region_min_route_count.items():
            if region_counts.get(region, 0) < mincount:
                return False
        # budget
        total_raw = sum(float(raw_cost_map.get(r, 0.0)) for r in sel)
        if total_budget > 0 and total_raw > total_budget + epsilon_constraints:
            return False
        # pair incompatibility: same-region pair capacity sum cap
        region_selected_routes = defaultdict(list)
        for r in sel:
            region_selected_routes[route_regions.get(r, "")].append(r)
        for region, lst in region_selected_routes.items():
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    cap_sum = route_capacities.get(lst[i], 0.0) + route_capacities.get(lst[j], 0.0)
                    if cap_sum > pair_incompatibility_threshold + epsilon_constraints:
                        return False
        # intra-region diversity hard rule
        for region in set(route_regions.get(r, "") for r in all_routes):
            open_positive = [r for r in all_routes if route_regions.get(r, "") == region and route_capacities.get(r, 0.0) > 0.0]
            if len(open_positive) >= 3:
                minreq = region_min_route_count.get(region, 0)
                if minreq >= 2:
                    if sum(1 for r in sel if route_regions.get(r, "") == region) < 2:
                        return False
        # min distinct per region
        for region, mn in min_distinct_per_region.items():
            if sum(1 for r in sel if route_regions.get(r, "") == region) < mn:
                return False
        return True

    def total_costs(selected):
        total_adj = sum(adjusted_weighted_cost(r) for r in selected)
        total_raw = sum(float(raw_cost_map.get(r, 0.0)) for r in selected)
        return total_adj, total_raw

    def tb_tuple(selected):
        total_adj, total_raw = total_costs(selected)
        n_routes = len(selected)
        total_capacity = sum(route_capacities.get(r, 0.0) for r in selected)
        lex = tuple(sorted(selected))
        # regional capacity variance
        regions = set(route_regions.get(r, "") for r in all_routes)
        vals = []
        for reg in regions:
            vals.append(sum(route_capacities.get(r, 0.0) for r in selected if route_regions.get(r, "") == reg))
        if vals:
            mean = sum(vals) / len(vals)
            var = sum((x - mean) ** 2 for x in vals) / len(vals)
        else:
            var = 0.0
        return (total_adj, n_routes, total_raw, -total_capacity, lex, var)

    # Check mandatory forced selections
    for r in mandatory_routes:
        if r not in variables:
            return {}

    # Prepare initial solution
    initial_selected = set(forced_selected)
    # Remove forbidden from forced_selected
    if forbidden_routes & set(initial_selected):
        return {}

    # For small free var set, exhaustive search
    best_sel = None
    best_tb = None

    if len(free_vars) <= 18:
        # enumerate
        k = len(free_vars)
        for mask in range(1 << k):
            sel = set(initial_selected)
            for i in range(k):
                if (mask >> i) & 1:
                    sel.add(free_vars[i])
            # respect forced unselected
            sel -= set(forced_unselected)
            # respect forbidden
            if forbidden_routes & sel:
                pruning_operations += 1
                continue
            # satisfiability: simple check - ensure each clause satisfied
            sat = True
            for clause in clauses:
                ok = False
                for litname in clause:
                    if litname in sel:
                        ok = True
                        break
                if not ok:
                    sat = False
                    break
            if not sat:
                pruning_operations += 1
                continue
            # constraints
            if not check_constraints(sel):
                pruning_operations += 1
                continue
            tb = tb_tuple(sel)
            if best_sel is None:
                best_sel = set(sel); best_tb = tb
            else:
                # compare with tie-breaking
                if abs(tb[0] - best_tb[0]) <= epsilon_cost:
                    # apply TB2..TB6
                    if tb[1] != best_tb[1]:
                        if tb[1] < best_tb[1]:
                            best_sel = set(sel); best_tb = tb
                    elif tb[2] != best_tb[2]:
                        if tb[2] < best_tb[2]:
                            best_sel = set(sel); best_tb = tb
                    elif tb[3] != best_tb[3]:
                        if tb[3] < best_tb[3]:
                            best_sel = set(sel); best_tb = tb
                    elif tb[4] != best_tb[4]:
                        if tb[4] < best_tb[4]:
                            best_sel = set(sel); best_tb = tb
                    elif balance_penalty_lambda > 0 and tb[5] != best_tb[5]:
                        if tb[5] < best_tb[5]:
                            best_sel = set(sel); best_tb = tb
                else:
                    if tb[0] < best_tb[0]:
                        best_sel = set(sel); best_tb = tb
    else:
        # Greedy heuristic with beam search
        random.seed(greedy_seed)
        candidates = [set(initial_selected)]
        best_sel = None
        best_tb = None
        iterations = 0
        while candidates and iterations < 1000:
            iterations += 1
            greedy_iterations += 1
            new_cands = []
            for cand in candidates:
                # compute unsatisfied clauses
                unsat_clauses = []
                for clause in clauses:
                    if not any(litname in cand for litname in clause):
                        unsat_clauses.append(clause)
                # score each available route not in cand
                scores = []
                for r in all_routes:
                    if r in cand or r in forbidden_routes:
                        continue
                    # coverage score
                    cov = 0
                    for clause in unsat_clauses:
                        if r in clause:
                            cov += 1
                    awc = adjusted_weighted_cost(r)
                    score = (cov / awc) if awc > 0 else cov * 1e6
                    # balance penalty
                    if balance_penalty_lambda > 0:
                        # compute variance if added
                        temp = set(cand); temp.add(r)
                        regions = set(route_regions.get(rr, "") for rr in all_routes)
                        vals = []
                        for reg in regions:
                            vals.append(sum(route_capacities.get(rr, 0.0) for rr in temp if route_regions.get(rr, "") == reg))
                        mean = sum(vals) / len(vals) if vals else 0.0
                        var = sum((x - mean) ** 2 for x in vals) / len(vals) if vals else 0.0
                        score = score - balance_penalty_lambda * var
                    scores.append(( -score, r))
                scores.sort()
                # pick top beam_width
                for _, r in scores[:beam_width]:
                    new = set(cand); new.add(r)
                    # quick SAT check: clauses satisfied?
                    sat = True
                    for clause in clauses:
                        if not any(litname in new for litname in clause):
                            sat = False
                            break
                    if not sat:
                        continue
                    if not check_constraints(new):
                        continue
                    tb = tb_tuple(new)
                    if best_sel is None or tb[0] + epsilon_cost < best_tb[0] or (abs(tb[0] - best_tb[0]) <= epsilon_cost and tb[1:] < best_tb[1:]):
                        best_sel = set(new); best_tb = tb
                    new_cands.append(new)
            candidates = new_cands[:beam_width]
            if iterations > 200:
                break

    if best_sel is None:
        return {}

    # Post-processing refinement: try removing redundant routes
    current = set(best_sel)
    improved = True
    iter_count = 0
    removed = 0
    while improved and iter_count < 100:
        iter_count += 1
        refinement_iterations += 1
        improved = False
        # sort candidates by descending adjusted weighted cost
        cand_list = sorted(list(current), key=lambda r: adjusted_weighted_cost(r), reverse=True)
        for r in cand_list:
            trial = set(current)
            trial.remove(r)
            # must keep mandatory
            if not mandatory_routes.issubset(trial):
                continue
            # satisfiability simple check
            sat = True
            for clause in clauses:
                if not any(litname in trial for litname in clause):
                    sat = False
                    break
            if not sat:
                continue
            if not check_constraints(trial):
                continue
            # compare tie-breakers: prefer lower adjusted cost
            tb_trial = tb_tuple(trial)
            tb_current = tb_tuple(current)
            if tb_trial[0] + epsilon_cost < tb_current[0] or (abs(tb_trial[0] - tb_current[0]) <= epsilon_cost and tb_trial[1:] <= tb_current[1:]):
                current = trial
                removed += 1
                improved = True
                break
    routes_removed = removed
    conver