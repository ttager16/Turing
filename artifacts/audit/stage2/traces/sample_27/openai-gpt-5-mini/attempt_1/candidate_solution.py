def simulate_optimal_strategy(units: List[Dict[str, Any]], terrain_graph: Dict[str, Any], scenarios: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    if not units or not scenarios:
        return []

    # Build unit lookup
    unit_by_type = {u['type']: u for u in units}
    unit_types = list(unit_by_type.keys())
    sectors = terrain_graph.get('nodes', [])
    edges_orig = terrain_graph.get('edges', [])
    resources = terrain_graph.get('resources', {})
    if not sectors or not edges_orig:
        return []

    # Build synergy lookup (bidirectional)
    synergy_lookup = {}
    for u in units:
        a = u['type']
        for b in u.get('synergy', []):
            if b in unit_by_type:
                key = tuple(sorted((a, b)))
                synergy_lookup[key] = 1.2

    # Helper to compute synergy score for allocations
    def compute_synergy(allocs: List[Dict[str, Any]]) -> float:
        # expand units per sector
        sector_units = defaultdict(list)  # sector -> list of unit types (repeated)
        for a in allocs:
            sector_units[a['sector']].extend([a['unit']] * a['count'])
        total = 0.0
        for sec, ul in sector_units.items():
            if len(ul) < 2:
                continue
            # unique pairs from expanded list; to avoid double counting identical positions, consider combinations by indices
            for i in range(len(ul)):
                for j in range(i + 1, len(ul)):
                    u1, u2 = ul[i], ul[j]
                    key = tuple(sorted((u1, u2)))
                    mult = synergy_lookup.get(key, 1.0)
                    if mult > 1.0:
                        p1 = unit_by_type[u1]['power']
                        p2 = unit_by_type[u2]['power']
                        total += (p1 + p2) * 0.2  # coefficient
        return total

    # Terrain change effects mapping (percentage multipliers)
    terrain_effects = {
        'forest_to_desert': 0.80,
        'desert_to_mountain': 0.60,
        'mountain_to_forest': 1.10
    }
    terrain_penalty = {
        'forest_to_desert': 20,
        'desert_to_mountain': 40,
        'mountain_to_forest': -10
    }
    tactical_penalty = {
        'aggressive': 30,
        'flanking': 10,
        'turtling': 0
    }
    tactical_effects = {
        'aggressive': 0.70,
        'flanking': 0.90,
        'turtling': 1.0
    }

    # Flow calculation per scenario
    def adjust_capacities_for_scenario(edges, terrain_change, enemy_strat):
        edges_copy = copy.deepcopy(edges)
        te = terrain_effects.get(terrain_change, 1.0)
        te_pen = terrain_penalty.get(terrain_change, 0)
        tac = tactical_effects.get(enemy_strat, 1.0)
        tac_pen = tactical_penalty.get(enemy_strat, 0)
        # apply environmental then tactical, integer truncation
        for e in edges_copy:
            cap = e.get('capacity', 0)
            cap = int(cap * te)
            cap = int(cap * tac)
            e['capacity'] = max(0, cap)
        return edges_copy, te_pen, tac_pen

    # Flow distribution algorithm
    def compute_flows(adjusted_edges, resources_map):
        if not adjusted_edges or not resources_map:
            return {}
        total_resources = sum(resources_map.get(n, 0) for n in sectors)
        total_adjusted_capacity = sum(e['capacity'] for e in adjusted_edges)
        distributable = min(total_resources, total_adjusted_capacity)
        if distributable <= 0 or total_adjusted_capacity <= 0:
            # zero-valued flow mappings when exhausted
            return {f"{e['from']}->{e['to']}": 0 for e in adjusted_edges}
        flows = {}
        # allocate proportionally to edge capacity
        for e in adjusted_edges:
            key = f"{e['from']}->{e['to']}"
            cap = e['capacity']
            if total_adjusted_capacity == 0:
                flow = 0
            else:
                flow = int(distributable * (cap / total_adjusted_capacity))
                if flow > cap:
                    flow = cap
            flows[key] = flow
        # Due to truncation we may have leftover; distribute greedily up to caps
        assigned = sum(flows.values())
        leftover = distributable - assigned
        if leftover > 0:
            # sort edges by remaining capacity
            rem_caps = [(k, e['capacity'] - flows[k]) for k, e in zip([f"{e['from']}->{e['to']}" for e in adjusted_edges], adjusted_edges)]
            for k, rem in rem_caps:
                if leftover <= 0:
                    break
                add = min(rem, leftover)
                flows[k] += add
                leftover -= add
        return flows

    # Efficiency metrics
    def compute_efficiencies(total_power, total_cost, achieved_flow, original_total_capacity):
        power_eff = (total_power / total_cost) if total_cost > 0 else 0.0
        flow_eff = (achieved_flow / original_total_capacity) if original_total_capacity > 0 else 0.0
        return power_eff, flow_eff

    # Generate configurations
    configs = []

    # Single-sector: one unit type in one sector counts 1..10
    for s in sectors:
        for ut in unit_types:
            for c in range(1, 11):
                allocs = [{'unit': ut, 'sector': s, 'count': c}]
                configs.append({'allocations': allocs, 'flows': {}})

    # Multi-sector: distinct sector pairs with different unit types, counts 1..10 each
    # choose ordered pairs of distinct sectors and ordered pairs of unit types (allow same unit? requirement says different unit types across pairs)
    for s1, s2 in combinations(sectors, 2):
        for ut1 in unit_types:
            for ut2 in unit_types:
                if ut1 == ut2:
                    continue
                for c1 in range(1, 11):
                    for c2 in range(1, 11):
                        allocs = [{'unit': ut1, 'sector': s1, 'count': c1}, {'unit': ut2, 'sector': s2, 'count': c2}]
                        configs.append({'allocations': allocs, 'flows': {}})
                        # also reversed sectors
                        allocs2 = [{'unit': ut1, 'sector': s2, 'count': c1}, {'unit': ut2, 'sector': s1, 'count': c2}]
                        configs.append({'allocations': allocs2, 'flows': {}})

    # Synergy-focused: compatible pairs co-located in same sector
    compatible_pairs = []
    for a in unit_types:
        for b in unit_types:
            if a >= b:
                continue
            if tuple(sorted((a, b))) in synergy_lookup:
                compatible_pairs.append((a, b))
    for s in sectors:
        for a, b in compatible_pairs:
            for ca in range(1, 11):
                for cb in range(1, 11):
                    allocs = [{'unit': a, 'sector': s, 'count': ca}, {'unit': b, 'sector': s, 'count': cb}]
                    configs.append({'allocations': allocs, 'flows': {}})

    # Remove duplicates (by allocations normalized)
    seen = set()
    unique_configs = []
    for c in configs:
        # sort allocations for normalization
        key = tuple(sorted([(a['unit'], a['sector'], a['count']) for a in c['allocations']]))
        if key in seen:
            continue
        seen.add(key)
        unique_configs.append(c)
    configs = unique_configs

    # Heuristic ranking: raw power + synergy potential
    def heuristic_score(cfg):
        total_power = sum(unit_by_type[a['unit']]['power'] * a['count'] for a in cfg['allocations'])
        syn = compute_synergy(cfg['allocations'])
        return total_power + syn
    configs.sort(key=heuristic_score, reverse=True)
    configs = configs[:100]

    # Precompute original total capacity
    original_total_capacity = sum(e.get('capacity', 0) for e in edges_orig)

    results = []
    # Evaluate each candidate across scenarios
    for cfg in configs:
        per_scenario_scores = []
        accumulated_flows = defaultdict(int)
        for sc in scenarios:
            enemy = sc.get('enemy_strat', '')
            terr = sc.get('terrain_change', '')
            adjusted_edges, terr_pen, tac_pen = adjust_capacities_for_scenario(edges_orig, terr, enemy)
            # compute flows
            flows = compute_flows(adjusted_edges, resources)
            # compute aggregate power and cost
            total_power = sum(unit_by_type[a['unit']]['power'] * a['count'] for a in cfg['allocations'])
            total_cost = sum(unit_by_type[a['unit']]['base_cost'] * a['count'] for a in cfg['allocations'])
            # synergy
            syn_score = compute_synergy(cfg['allocations'])
            syn_bonus = syn_score * 2  # doubled
            # efficiencies
            achieved_flow = sum(flows.values())
            power_eff, flow_eff = compute_efficiencies(total_power, total_cost, achieved_flow, original_total_capacity)
            # Score formula:
            base = total_power + (power_eff + flow_eff) * (1/100) * 100  # since scaled by 1/100, multiply back: effectively power_eff+flow_eff
            # The spec: "both efficiency metrics scaled by 1/100" ambiguous; implement as adding (power_eff + flow_eff)*(1/100)*100 => power_eff+flow_eff
            score = base + syn_bonus
            # apply penalties/bonuses
            score -= terr_pen
            score -= tac_pen
            # clamp 0..1000
            score = max(0, min(1000, score))
            per_scenario_scores.append(int(score))
            # accumulate flows
            for k, v in flows.items():
                accumulated_flows[k] += v
        # average score integer division
        avg_score = sum(per_scenario_scores) // len(per_scenario_scores)
        # average flows per edge across scenarios (integer division)
        avg_flows = {k: accumulated_flows[k] // len(scenarios) for k in accumulated_flows}
        result_cfg = {
            'configuration': {
                'allocations': [{'unit': a['unit'], 'sector': a['sector'], 'count': a['count']} for a in cfg['allocations']],
                'flows': avg_flows
            },
            'score': int(max(0, min(1000, avg_score)))
        }
        results.append(result_cfg)

    # sort by score desc and select top 10
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:10]