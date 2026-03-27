from typing import List, Dict, Any
import json

class RouteOptimizer:
    def __init__(self, variables: List[str], clauses: List[List[str]], 
                 real_time_data: List[List[Any]],
                 route_capacities: Dict[str, float],
                 route_emissions: Dict[str, float],
                 route_regions: Dict[str, str],
                 region_min_capacity: Dict[str, float],
                 region_max_emissions: Dict[str, float],
                 route_penalty_factors: Dict[str, float],
                 total_budget: float,
                 region_min_route_count: Dict[str, int]):
        self.variables = variables
        self.clauses = clauses
        self.real_time_data = real_time_data
        self.route_capacities = route_capacities
        self.route_emissions = route_emissions
        self.route_regions = route_regions
        self.region_min_capacity = region_min_capacity
        self.region_max_emissions = region_max_emissions
        self.route_penalty_factors = route_penalty_factors
        self.total_budget = total_budget
        self.region_min_route_count = region_min_route_count
        
        self.var_set = set()
        self.idx_of = {}
        self.n = 0
        self.g = []
        self.gr = []
        self.comp = []
        self.forced_false = set()
        self.route_costs = {}
        
        # Algorithm metrics tracking
        self.pruning_operations = 0
        self.greedy_iterations = 0
        self.feasibility_checks = 0
        self.refinement_iterations = 0
        self.routes_removed = 0
        self.converged = False
        
        # Reserved config keys (optional, config-driven)
        self.dominance_share_cap = float(route_penalty_factors.get('__dominance_share_cap__', 1.0))
        mei_val = route_penalty_factors.get('__max_emissions_intensity__', None)
        self.max_emissions_intensity = None if mei_val is None else float(mei_val)
        self.balance_penalty_lambda = float(route_penalty_factors.get('__balance_penalty_lambda__', 0.0))
        self.pair_incompatibility_threshold = route_penalty_factors.get('__pair_incompatibility_threshold__', None)
        self.pair_incompatibility_threshold = (None if self.pair_incompatibility_threshold is None 
                                               else float(self.pair_incompatibility_threshold))
        self.greedy_seed = int(route_penalty_factors.get('__greedy_seed__', 0))
        self.beam_width = int(route_penalty_factors.get('__beam_width__', 1))
        self.epsilon_cost = float(route_penalty_factors.get('__epsilon_cost__', 1e-3))
        self.epsilon_constraints = float(route_penalty_factors.get('__epsilon_constraints__', 1e-9))
        self.max_raw_cost_share = float(route_penalty_factors.get('__max_raw_cost_share__', 1.0))
        
        # JSON-encoded reserved keys
        self.regional_budgets = {}
        rb_raw = route_penalty_factors.get('__regional_budgets__', '')
        if isinstance(rb_raw, str) and rb_raw:
            try:
                parsed = json.loads(rb_raw)
                if isinstance(parsed, dict):
                    # Ensure float values
                    self.regional_budgets = {str(k): float(v) for k, v in parsed.items()}
            except Exception:
                self.regional_budgets = {}
        
        def _parse_list(key: str) -> List[str]:
            val = route_penalty_factors.get(key, '')
            if isinstance(val, str) and val:
                try:
                    lst = json.loads(val)
                    if isinstance(lst, list):
                        return [self.normalize_var_name(str(x)) for x in lst]
                except Exception:
                    return []
            return []
        
        self.mandatory_routes = set(_parse_list('__mandatory_routes__'))
        self.forbidden_routes = set(_parse_list('__forbidden_routes__'))
        # JSON-encoded min distinct per region mapping
        min_distinct_raw = route_penalty_factors.get('__min_distinct_routes_per_region__', '')
        self.min_distinct_routes_per_region = {}
        if isinstance(min_distinct_raw, str) and min_distinct_raw:
            try:
                parsed = json.loads(min_distinct_raw)
                if isinstance(parsed, dict):
                    self.min_distinct_routes_per_region = {str(k): int(v) for k, v in parsed.items()}
            except Exception:
                self.min_distinct_routes_per_region = {}
        
    def normalize_var_name(self, name: str) -> str:
        return name.strip()

    def is_negated(self, lit: str) -> bool:
        s = lit.strip()
        if not s:
            return False
        return s[0] in ('¬', '!', '~') or s.upper().startswith('NOT ')

    def literal_var(self, lit: str) -> str:
        s = lit.strip()
        if s.upper().startswith('NOT '):
            s = s[4:].strip()
        elif self.is_negated(s):
            s = s[1:].strip()
        return self.normalize_var_name(s)

    def literal_sign(self, lit: str) -> bool:
        s = lit.strip()
        if s.upper().startswith('NOT '):
            return False
        return not self.is_negated(s)

    def pos(self, i: int) -> int:
        return i << 1

    def neg(self, i: int) -> int:
        return (i << 1) | 1

    def lit_index(self, lit: str) -> int:
        vi = self.idx_of[self.literal_var(lit)]
        return self.pos(vi) if self.literal_sign(lit) else self.neg(vi)

    def build_implication_graph(self):
        self.var_set = set(self.normalize_var_name(v) for v in self.variables)
        for a, b in self.clauses:
            self.var_set.add(self.literal_var(a))
            self.var_set.add(self.literal_var(b))

        var_list = sorted(self.var_set)
        self.idx_of = {name: i for i, name in enumerate(var_list)}
        self.n = len(var_list)

        V = 2 * self.n
        self.g = [[] for _ in range(V)]
        self.gr = [[] for _ in range(V)]

        for a, b in self.clauses:
            ai = self.lit_index(a)
            bi = self.lit_index(b)
            self.g[ai ^ 1].append(bi)
            self.gr[bi].append(ai ^ 1)
            self.g[bi ^ 1].append(ai)
            self.gr[ai].append(bi ^ 1)

    def process_real_time_data(self):
        try:
            updates = self.real_time_data or []
        except Exception:
            updates = []

        for name, val in updates:
            vname = self.normalize_var_name(name)
            if vname in self.idx_of:
                if val is None or val <= 0.0:
                    self.forced_false.add(self.idx_of[vname])
                else:
                    self.route_costs[vname] = val

        for vname in self.var_set:
            if vname not in self.route_costs and vname in self.variables:
                self.route_costs[vname] = 1.0

        for vi in self.forced_false:
            p = self.pos(vi)
            nlit = self.neg(vi)
            self.g[p].append(nlit)
            self.gr[nlit].append(p)

    def tarjan_scc(self):
        V = 2 * self.n
        visited = [False] * V
        order = []

        for u in range(V):
            if not visited[u]:
                stack = [(u, 0)]
                visited[u] = True
                while stack:
                    v, it = stack[-1]
                    if it < len(self.g[v]):
                        w = self.g[v][it]
                        stack[-1] = (v, it + 1)
                        if not visited[w]:
                            visited[w] = True
                            stack.append((w, 0))
                    else:
                        order.append(stack.pop()[0])

        self.comp = [0] * V
        cid = 0
        visited = [False] * V

        for u in reversed(order):
            if not visited[u]:
                stack = [u]
                visited[u] = True
                while stack:
                    v = stack.pop()
                    self.comp[v] = cid
                    for w in self.gr[v]:
                        if not visited[w]:
                            visited[w] = True
                            stack.append(w)
                cid += 1

    def is_satisfiable_assignment(self, assignment: List[bool]) -> bool:
        for a, b in self.clauses:
            A_var = self.literal_var(a)
            B_var = self.literal_var(b)
            A_idx = self.idx_of[A_var]
            B_idx = self.idx_of[B_var]
            A_sign = self.literal_sign(a)
            B_sign = self.literal_sign(b)
            
            A_val = assignment[A_idx] if A_sign else not assignment[A_idx]
            B_val = assignment[B_idx] if B_sign else not assignment[B_idx]
            
            if not (A_val or B_val):
                return False
        return True

    def check_regional_constraints(self, assignment: List[bool]) -> bool:
        """Check all regional and business constraints with proper tolerances."""
        self.feasibility_checks += 1
        var_list = sorted(self.var_set)
        
        region_capacity = {}
        region_emissions = {}
        region_route_count = {}
        region_costs = {}
        region_selected_routes = {}
        total_raw_cost = 0.0
        
        TOLERANCE = self.epsilon_constraints  # Tolerance for constraint checks
        
        for i in range(self.n):
            if assignment[i]:
                route_name = var_list[i]
                if route_name in self.variables:
                    # Forbidden routes cannot be selected
                    if route_name in self.forbidden_routes:
                        return False

                    capacity = self.route_capacities.get(route_name, 0.0)
                    cost = self.route_costs.get(route_name, 1.0)
                    
                    # Business Constraint: Zero-capacity prohibition
                    # Routes with capacity <= 0 cannot be selected
                    if capacity <= 0.0:
                        return False
                    
                    # Business Constraint: Closed routes (cost <= 0) cannot be selected
                    if cost <= 0.0:
                        return False
                    
                    # Add to total raw cost for budget check (regardless of region)
                    total_raw_cost += cost
                    
                    region = self.route_regions.get(route_name)
                    if region:
                        emissions = self.route_emissions.get(route_name, 0.0)
                        
                        region_capacity[region] = region_capacity.get(region, 0.0) + capacity
                        region_emissions[region] = region_emissions.get(region, 0.0) + emissions
                        region_route_count[region] = region_route_count.get(region, 0) + 1
                        region_costs[region] = region_costs.get(region, 0.0) + cost
                        region_selected_routes.setdefault(region, []).append(route_name)
        
        # Check regional capacity constraints (with tolerance)
        for region, min_cap in self.region_min_capacity.items():
            if region_capacity.get(region, 0.0) < min_cap - TOLERANCE:
                return False
        
        # Check regional emission constraints (with tolerance)
        for region, max_emis in self.region_max_emissions.items():
            if region_emissions.get(region, 0.0) > max_emis + TOLERANCE:
                return False
        
        # Check regional route count constraints
        for region, min_count in self.region_min_route_count.items():
            if region_route_count.get(region, 0) < min_count:
                return False
        
        # Check total budget constraint (if specified and > 0, with tolerance)
        if self.total_budget > 0 and total_raw_cost > self.total_budget + TOLERANCE:
            return False
        
        # Per-region budgets (optional)
        for region, limit in self.regional_budgets.items():
            if limit > 0 and region_costs.get(region, 0.0) > limit + TOLERANCE:
                return False
        
        # Emissions intensity per region (optional, only if max specified)
        if self.max_emissions_intensity is not None:
            for region in self.region_max_emissions.keys():
                cap = region_capacity.get(region, 0.0)
                emis = region_emissions.get(region, 0.0)
                if cap > 0.0 and (emis / cap) > self.max_emissions_intensity + TOLERANCE:
                    return False
        
        # Dominance share cap (optional)
        if self.dominance_share_cap < 1.0:
            for region, total_cap in region_capacity.items():
                if total_cap > 0.0:
                    max_share = self.dominance_share_cap * total_cap + TOLERANCE
                    for route_name in region_selected_routes.get(region, []):
                        cap_i = self.route_capacities.get(route_name, 0.0)
                        if cap_i > max_share:
                            return False

        # Raw cost share cap (optional)
        if self.max_raw_cost_share < 1.0:
            for region, sum_raw in region_costs.items():
                if sum_raw > 0.0:
                    max_share_raw = self.max_raw_cost_share * sum_raw + TOLERANCE
                    for route_name in region_selected_routes.get(region, []):
                        raw_i = self.route_costs.get(route_name, 0.0)
                        if raw_i > max_share_raw:
                            return False
        
        # Pair incompatibility threshold (optional)
        if self.pair_incompatibility_threshold is not None and self.pair_incompatibility_threshold < float('inf'):
            pit = self.pair_incompatibility_threshold
            for region, names in region_selected_routes.items():
                for idx_a in range(len(names)):
                    a = names[idx_a]
                    cap_a = self.route_capacities.get(a, 0.0)
                    for idx_b in range(idx_a + 1, len(names)):
                        b = names[idx_b]
                        cap_b = self.route_capacities.get(b, 0.0)
                        if cap_a + cap_b > pit + TOLERANCE:
                            return False
        
        # Mandatory routes (must be selected if eligible)
        for m in self.mandatory_routes:
            if m in self.variables and m in self.idx_of:
                i = self.idx_of[m]
                cap = self.route_capacities.get(m, 0.0)
                cost = self.route_costs.get(m, 1.0)
                if cap > 0.0 and cost > 0.0:
                    if not assignment[i]:
                        return False

        # Reserved: minimum distinct routes per region
        for region, min_distinct in self.min_distinct_routes_per_region.items():
            if region_route_count.get(region, 0) < int(min_distinct):
                return False

        # Hard intra-region diversity rule
        # If a region has ≥3 open, positive-capacity candidates and region_min_route_count[r] ≥ 2, then select at least 2
        # Compute candidate counts from all variables (not just selected)
        candidates_per_region = {}
        for name in var_list:
            if name in self.variables:
                region = self.route_regions.get(name)
                if region is None:
                    continue
                cap = self.route_capacities.get(name, 0.0)
                cost = self.route_costs.get(name, 1.0)
                if cap > 0.0 and cost > 0.0:
                    candidates_per_region[region] = candidates_per_region.get(region, 0) + 1
        for region, cand_count in candidates_per_region.items():
            min_count_req = self.region_min_route_count.get(region, 0)
            if cand_count >= 3 and min_count_req >= 2:
                if region_route_count.get(region, 0) < 2:
                    return False
        
        return True

    def compute_weighted_cost(self, assignment: List[bool]) -> float:
        """Compute total adjusted weighted cost."""
        total_cost = 0.0
        var_list = sorted(self.var_set)
        for i in range(self.n):
            if assignment[i]:
                route_name = var_list[i]
                if route_name in self.variables:
                    cost = self.route_costs.get(route_name, 1.0)
                    capacity = self.route_capacities.get(route_name, 1.0)
                    penalty_factor = self.route_penalty_factors.get(route_name, 0.0)
                    base_weighted_cost = cost / max(capacity, 1.0)
                    adjusted_weighted_cost = base_weighted_cost * (1.0 + penalty_factor)
                    total_cost += adjusted_weighted_cost
        return total_cost
    
    def compute_tie_breakers(self, assignment: List[bool]) -> List:
        """
        Compute all tie-breaking metrics in order:
        TB1: Total adjusted weighted cost (lower is better)
        TB2: Total route count (fewer is better)
        TB3: Total raw cost (lower is better)
        TB4: Total regional capacity (higher is better, so negate for min comparison)
        TB5: Lexicographically sorted route names (for deterministic ordering)
        """
        var_list = sorted(self.var_set)
        total_adjusted_cost = 0.0
        total_raw_cost = 0.0
        total_capacity = 0.0
        selected_routes = []
        
        for i in range(self.n):
            if assignment[i]:
                route_name = var_list[i]
                if route_name in self.variables:
                    cost = self.route_costs.get(route_name, 1.0)
                    capacity = self.route_capacities.get(route_name, 1.0)
                    penalty_factor = self.route_penalty_factors.get(route_name, 0.0)
                    
                    base_weighted_cost = cost / max(capacity, 1.0)
                    adjusted_weighted_cost = base_weighted_cost * (1.0 + penalty_factor)
                    
                    total_adjusted_cost += adjusted_weighted_cost
                    total_raw_cost += cost
                    total_capacity += capacity
                    selected_routes.append(route_name)
        
        route_count = len(selected_routes)
        selected_routes_sorted = sorted(selected_routes)
        
        # Optional TB6: regional capacity variance
        capacity_by_region = {}
        if self.balance_penalty_lambda > 0.0:
            for i in range(self.n):
                if assignment[i]:
                    rn = var_list[i]
                    if rn in self.variables:
                        r = self.route_regions.get(rn)
                        if r is not None:
                            capacity_by_region[r] = capacity_by_region.get(r, 0.0) + self.route_capacities.get(rn, 0.0)
            caps = list(capacity_by_region.values())
            if caps:
                mean_cap = sum(caps) / len(caps)
                variance = sum((c - mean_cap) * (c - mean_cap) for c in caps) / len(caps)
            else:
                variance = 0.0
        else:
            variance = 0.0
        
        # Return list for lexicographic comparison
        # TB4 is negated because higher capacity is better
        if self.balance_penalty_lambda > 0.0:
            return [total_adjusted_cost, route_count, total_raw_cost, -total_capacity, selected_routes_sorted, variance]
        else:
            return [total_adjusted_cost, route_count, total_raw_cost, -total_capacity, selected_routes_sorted]

    def is_better(self, tb_new: List, tb_best: List) -> bool:
        """
        Compare two tie-breaker lists with epsilon tolerance on TB1 (adjusted cost).
        """
        # TB1 tolerance on adjusted cost
        cost_new = tb_new[0]
        cost_best = tb_best[0]
        if abs(cost_new - cost_best) > self.epsilon_cost:
            return cost_new < cost_best
        # Fallback lexicographic on remaining fields
        # Ensure lists have equal length
        L = min(len(tb_new), len(tb_best))
        for i in range(1, L):
            if tb_new[i] != tb_best[i]:
                return tb_new[i] < tb_best[i]
        return False
    
    def get_selected_routes(self, assignment: List[bool]) -> List[str]:
        selected = []
        in_vars = [self.normalize_var_name(v) for v in self.variables]
        for v in in_vars:
            i = self.idx_of.get(v)
            if i is not None and assignment[i]:
                selected.append(v)
        return selected

    def get_scc_based_assignment(self) -> List[bool]:
        assignment = [False] * self.n
        for i in range(self.n):
            if i in self.forced_false:
                assignment[i] = False
            else:
                assignment[i] = self.comp[self.pos(i)] > self.comp[self.neg(i)]
        return assignment

    def solve_with_costs(self) -> Dict[str, Any]:
        free_vars = [i for i in range(self.n) if i not in self.forced_false 
                     and self.comp[self.pos(i)] != self.comp[self.neg(i)]]
        
        if len(free_vars) <= 18:
            best_assignment = None
            best_tie_breakers = None
            
            search_limit = 1 << len(free_vars)
            COST_TOLERANCE = 1e-3  # Tolerance for cost equality in tie-breaking
            
            for mask in range(search_limit):
                assignment = [False] * self.n
                
                for i in self.forced_false:
                    assignment[i] = False
                
                for bit_idx, var_idx in enumerate(free_vars):
                    assignment[var_idx] = bool(mask & (1 << bit_idx))
                
                if self.is_satisfiable_assignment(assignment):
                    self.pruning_operations += 1
                    if self.check_regional_constraints(assignment):
                        tie_breakers = self.compute_tie_breakers(assignment)
                        
                        if best_tie_breakers is None or self.is_better(tie_breakers, best_tie_breakers):
                            best_tie_breakers = tie_breakers
                            best_assignment = assignment[:]

            if best_assignment is None:
                return {}
            
            selected = sorted(self.get_selected_routes(best_assignment))
            self.converged = True
            return self._build_result_dict(selected, best_assignment)
        else:
            self.greedy_iterations = 0
            assignment = [False] * self.n
            for i in self.forced_false:
                assignment[i] = False
            
            var_list = sorted(self.var_set)
            unsatisfied_clauses = set(range(len(self.clauses)))
            
            # Deterministic greedy order based on seed (rotation of var_list indices)
            if self.n > 0:
                start = self.greedy_seed % self.n
                greedy_index_order = list(range(start, self.n)) + list(range(0, start))
            else:
                greedy_index_order = []
            
            while unsatisfied_clauses:
                self.greedy_iterations += 1
                best_var = None
                best_var_value = True
                best_score = -1
                
                for i in greedy_index_order:
                    if i in self.forced_false or assignment[i]:
                        continue
                    
                    test_assign = assignment[:]
                    test_assign[i] = True
                    
                    newly_satisfied = 0
                    for clause_idx in unsatisfied_clauses:
                        a, b = self.clauses[clause_idx]
                        A_var = self.literal_var(a)
                        B_var = self.literal_var(b)
                        A_idx = self.idx_of[A_var]
                        B_idx = self.idx_of[B_var]
                        A_sign = self.literal_sign(a)
                        B_sign = self.literal_sign(b)
                        
                        A_val = test_assign[A_idx] if A_sign else not test_assign[A_idx]
                        B_val = test_assign[B_idx] if B_sign else not test_assign[B_idx]
                        
                        if A_val or B_val:
                            newly_satisfied += 1
                    
                    if newly_satisfied > 0:
                        route_name = var_list[i]
                        cost = self.route_costs.get(route_name, 1.0)
                        capacity = self.route_capacities.get(route_name, 1.0)
                        penalty_factor = self.route_penalty_factors.get(route_name, 0.0)
                        adjusted_weighted_cost = (cost / max(capacity, 1.0)) * (1.0 + penalty_factor)
                        base_score = newly_satisfied / adjusted_weighted_cost if adjusted_weighted_cost > 0 else newly_satisfied
                        
                        # Balance penalty (heuristic only)
                        if self.balance_penalty_lambda > 0.0:
                            # Compute capacity variance for test_assign
                            cap_by_region = {}
                            for j in range(self.n):
                                if test_assign[j]:
                                    rn = var_list[j]
                                    if rn in self.variables:
                                        r = self.route_regions.get(rn)
                                        if r is not None:
                                            cap_by_region[r] = cap_by_region.get(r, 0.0) + self.route_capacities.get(rn, 0.0)
                            caps = list(cap_by_region.values())
                            if caps:
                                mean_cap = sum(caps) / len(caps)
                                variance = sum((c - mean_cap) * (c - mean_cap) for c in caps) / len(caps)
                            else:
                                variance = 0.0
                            score = base_score - self.balance_penalty_lambda * variance
                        else:
                            score = base_score
                        
                        if score > best_score:
                            best_score = score
                            best_var = i
                            best_var_value = True
                
                if best_var is not None:
                    assignment[best_var] = best_var_value
                    
                    to_remove = set()
                    for clause_idx in unsatisfied_clauses:
                        a, b = self.clauses[clause_idx]
                        A_var = self.literal_var(a)
                        B_var = self.literal_var(b)
                        A_idx = self.idx_of[A_var]
                        B_idx = self.idx_of[B_var]
                        A_sign = self.literal_sign(a)
                        B_sign = self.literal_sign(b)
                        
                        A_val = assignment[A_idx] if A_sign else not assignment[A_idx]
                        B_val = assignment[B_idx] if B_sign else not assignment[B_idx]
                        
                        if A_val or B_val:
                            to_remove.add(clause_idx)
                    
                    unsatisfied_clauses -= to_remove
                else:
                    break
            
            if not self.is_satisfiable_assignment(assignment):
                self.pruning_operations += 1
                scc_assignment = self.get_scc_based_assignment()
                if self.is_satisfiable_assignment(scc_assignment):
                    assignment = scc_assignment
                else:
                    return {}
            
            if not self.check_regional_constraints(assignment):
                return {}
            
            assignment = self.optimize_assignment(assignment)
            
            if not self.check_regional_constraints(assignment):
                return {}
            
            selected = sorted(self.get_selected_routes(assignment))
            self.converged = True
            return self._build_result_dict(selected, assignment)
    
    def optimize_assignment(self, assignment: List[bool]) -> List[bool]:
        """Post-processing optimization using tie-breakers."""
        var_list = sorted(self.var_set)
        improved = True
        
        while improved:
            self.refinement_iterations += 1
            improved = False
            true_vars = [i for i in range(self.n) if assignment[i] and i not in self.forced_false]
            
            # Sort by adjusted weighted cost (descending) to try removing expensive routes first
            true_vars_by_cost = sorted(true_vars, 
                key=lambda i: (self.route_costs.get(var_list[i], 1.0) / max(self.route_capacities.get(var_list[i], 1.0), 1.0)) * 
                              (1.0 + self.route_penalty_factors.get(var_list[i], 0.0)), 
                reverse=True)
            
            for i in true_vars_by_cost:
                test_assign = assignment[:]
                test_assign[i] = False
                
                if self.is_satisfiable_assignment(test_assign) and self.check_regional_constraints(test_assign):
                    # Use tie-breakers to verify improvement
                    test_tb = self.compute_tie_breakers(test_assign)
                    current_tb = self.compute_tie_breakers(assignment)
                    if self.is_better(test_tb, current_tb):
                        assignment = test_assign
                        self.routes_removed += 1
                        improved = True
                        break
        
        self.converged = not improved  # Converged when no more improvements
        return assignment
    
    def _build_result_dict(self, selected_routes: List[str], assignment: List[bool]) -> Dict[str, Any]:
        """Build result dictionary with metrics."""
        total_adjusted = self.compute_weighted_cost(assignment)
        
        # Compute total raw cost
        var_list = sorted(self.var_set)
        total_raw = 0.0
        for i in range(self.n):
            if assignment[i]:
                route_name = var_list[i]
                if route_name in self.variables:
                    total_raw += self.route_costs.get(route_name, 1.0)
        
        return {
            'selected_routes': selected_routes,
            'total_adjusted_cost': round(total_adjusted, 6),
            'total_raw_cost': round(total_raw, 6),
            'algorithm_metrics': {
                'pruning_operations': self.pruning_operations,
                'greedy_iterations': self.greedy_iterations,
                'feasibility_checks': self.feasibility_checks,
                'refinement_iterations': self.refinement_iterations,
                'routes_removed': self.routes_removed,
                'converged': self.converged
            }
        }

    def solve_without_costs(self) -> Dict[str, Any]:
        free_vars = [i for i in range(self.n) if i not in self.forced_false 
                     and self.comp[self.pos(i)] != self.comp[self.neg(i)]]
        
        if len(free_vars) <= 20:
            best_assignment = None
            min_true_count = float('inf')
            
            search_limit = 1 << len(free_vars)
            for mask in range(search_limit):
                assignment = [False] * self.n
                
                for i in self.forced_false:
                    assignment[i] = False
                
                for bit_idx, var_idx in enumerate(free_vars):
                    assignment[var_idx] = bool(mask & (1 << bit_idx))
                
                if self.is_satisfiable_assignment(assignment) and self.check_regional_constraints(assignment):
                    self.pruning_operations += 1
                    true_count = sum(assignment)
                    if true_count < min_true_count:
                        min_true_count = true_count
                        best_assignment = assignment[:]
        else:
            assignment = self.get_scc_based_assignment()
            if self.is_satisfiable_assignment(assignment) and self.check_regional_constraints(assignment):
                best_assignment = assignment
            else:
                best_assignment = None
        
        if best_assignment is None:
            return {}
        
        selected = sorted(self.get_selected_routes(best_assignment))
        self.converged = True
        return self._build_result_dict(selected, best_assignment)

    def solve(self) -> Dict[str, Any]:
        self.build_implication_graph()
        self.process_real_time_data()
        self.tarjan_scc()
        
        for i in range(self.n):
            if self.comp[self.pos(i)] == self.comp[self.neg(i)]:
                return {}
        
        if not self.route_costs:
            return self.solve_without_costs()
        else:
            return self.solve_with_costs()


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
    if route_capacities is None:
        route_capacities = {}
    if route_emissions is None:
        route_emissions = {}
    if route_regions is None:
        route_regions = {}
    if region_min_capacity is None:
        region_min_capacity = {}
    if region_max_emissions is None:
        region_max_emissions = {}
    if route_penalty_factors is None:
        route_penalty_factors = {}
    if region_min_route_count is None:
        region_min_route_count = {}
    
    optimizer = RouteOptimizer(variables, clauses, real_time_data, 
                               route_capacities, route_emissions, route_regions,
                               region_min_capacity, region_max_emissions,
                               route_penalty_factors, total_budget, region_min_route_count)
    return optimizer.solve()