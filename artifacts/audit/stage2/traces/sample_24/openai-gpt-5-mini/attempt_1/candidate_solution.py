def get_device_state(mask: int, i: int) -> int:
    return (mask >> (i * 2)) & 0b11

def set_device_state(mask: int, i: int, s: int) -> int:
    clear = ~(0b11 << (i * 2)) & 0xFFFFFFFF
    return (mask & clear) | ((s & 0b11) << (i * 2))

def zone_energy(mask: int, device_count: int) -> int:
    e = 0
    for i in range(device_count):
        e += STATE_ENERGY[get_device_state(mask, i)]
    return e

def transition_cost(zone_idx: int, device_idx: int, from_s: int, to_s: int, transition_cost_matrices):
    mat = transition_cost_matrices[zone_idx][device_idx]
    return mat[from_s][to_s]

def compute_total_transition_cost(orig_states: List[int], new_states: List[int], zone_configs, transition_cost_matrices):
    total = 0
    for z_idx, (o_mask, n_mask) in enumerate(zip(orig_states, new_states)):
        dcount = zone_configs[z_idx].get('device_count', 16)
        for i in range(dcount):
            total += transition_cost(z_idx, i, get_device_state(o_mask, i), get_device_state(n_mask, i), transition_cost_matrices)
    return total

def apply_cascading_requirements(states_masks, cascading_list, zone_configs):
    # propagate until fixed point: if a device increased compared to baseline, enforce min on target
    changed = True
    while changed:
        changed = False
        for (zf, df, zt, dt) in cascading_list:
            dcount_f = zone_configs[zf].get('device_count', 16)
            dcount_t = zone_configs[zt].get('device_count', 16)
            if df >= dcount_f or dt >= dcount_t:
                continue
            sf = get_device_state(states_masks[zf], df)
            st = get_device_state(states_masks[zt], dt)
            # if source > 0 then target must be at least source-1 (min 1)
            if sf > 0:
                req = max(1, sf - 1)
                if st < req:
                    states_masks[zt] = set_device_state(states_masks[zt], dt, req)
                    changed = True
    return states_masks

def enforce_sync_groups(states_masks, sync_groups, zone_configs):
    # ensure devices in sync groups end up same state. If conflicting priorities exist, detect -1
    for group in sync_groups:
        # find required minimum from priorities
        min_req = None
        for (z, d) in group:
            if z >= len(zone_configs): continue
            pc = zone_configs[z].get('priority_devices', {})
            if str(d) in pc:
                r = pc[str(d)]
                if min_req is None or r > min_req:
                    min_req = r
        # find current max state among group
        cur_max = 0
        for (z, d) in group:
            if z >= len(states_masks): continue
            cur_max = max(cur_max, get_device_state(states_masks[z], d))
        target = cur_max
        if min_req is not None and target < min_req:
            target = min_req
        # apply target to all
        for (z, d) in group:
            states_masks[z] = set_device_state(states_masks[z], d, target)
    return states_masks

def enforce_mutual_exclusion(states_masks, me_groups, zone_configs):
    # ensure at most one peak per group: if multiple, pick one with minimal energy impact by downgrading others
    for group in me_groups:
        peaks = []
        for (z, d) in group:
            if z >= len(states_masks): continue
            if get_device_state(states_masks[z], d) == 3:
                peaks.append((z, d))
        if len(peaks) <= 1:
            continue
        # compute impact for downgrading each to active(2)
        impacts = []
        for (z, d) in peaks:
            before = STATE_ENERGY[3]
            after = STATE_ENERGY[2]
            impacts.append(((z, d), after - before))
        # keep the one whose removal causes largest negative impact? we want minimize total energy+transition: prefer keep that minimizes total cost when others downgraded
        # choose keeper as one minimizing total incremental energy if others downgraded
        best_keeper = None
        best_score = None
        for keeper in peaks:
            score = 0
            for p in peaks:
                if p == keeper:
                    continue
                z, d = p
                score += (STATE_ENERGY[2] - STATE_ENERGY[3])
            if best_score is None or score < best_score:
                best_score = score
                best_keeper = keeper
        # downgrade others
        for p in peaks:
            if p == best_keeper:
                continue
            z, d = p
            states_masks[z] = set_device_state(states_masks[z], d, 2)
    return states_masks

def enforce_inter_zone_deps(states_masks, inter_zone_deps, zone_configs):
    for (za, da, zb, minb) in inter_zone_deps:
        if za >= len(states_masks) or zb >= len(states_masks): continue
        if da >= zone_configs[za].get('device_count',16): continue
        if da >= zone_configs[zb].get('device_count',16): continue
        if get_device_state(states_masks[za], da) > 0:
            if get_device_state(states_masks[zb], da) < minb:
                states_masks[zb] = set_device_state(states_masks[zb], da, minb)
    return states_masks

def enforce_device_dependencies(states_masks, zone_configs):
    for z_idx, zconf in enumerate(zone_configs):
        deps = zconf.get('device_dependencies', [])
        dcount = zconf.get('device_count', 16)
        for dep in deps:
            # dep format [device_idx, required_device_idx, min_state]
            if len(dep) < 3: continue
            d, reqd, minstate = dep
            if d >= dcount or reqd >= dcount: continue
            if get_device_state(states_masks[z_idx], reqd) > 0:
                if get_device_state(states_masks[z_idx], d) < minstate:
                    states_masks[z_idx] = set_device_state(states_masks[z_idx], d, minstate)
    return states_masks

def enforce_priorities(states_masks, zone_configs):
    for z_idx, zconf in enumerate(zone_configs):
        pd = zconf.get('priority_devices', {})
        dcount = zconf.get('device_count', 16)
        for k, v in pd.items():
            try:
                di = int(k)
            except:
                continue
            if di >= dcount: continue
            if get_device_state(states_masks[z_idx], di) < v:
                states_masks[z_idx] = set_device_state(states_masks[z_idx], di, v)
    return states_masks

def enforce_weather(states_masks, weather_conditions):
    if weather_conditions.get('temperature', 0) > weather_conditions.get('high_temp_threshold', 1e9):
        for (z, d) in weather_conditions.get('devices_affected', []):
            if z >= len(states_masks): continue
            states_masks[z] = set_device_state(states_masks[z], d, max(2, get_device_state(states_masks[z], d)))
    return states_masks

def check_zone_internal_contradictions(z_idx, zone_configs):
    zconf = zone_configs[z_idx]
    dcount = zconf.get('device_count', 16)
    # priority sum > quota
    quota = zconf.get('energy_quota', 10**9)
    minsum = 0
    for k, v in zconf.get('priority_devices', {}).items():
        di = int(k)
        if di >= dcount: return True
        minsum += STATE_ENERGY[v]
    if minsum > quota:
        return True
    # sync group conflicts: handled externally; return False here
    return False

def segment_utilizations(states_masks, grid_segments, zone_configs):
    utils = []
    for seg in grid_segments:
        zones = seg.get('zones_in_segment', [])
        cap = seg.get('segment_capacity', 1)
        total = 0
        for z in zones:
            if z >= len(states_masks): continue
            total += zone_energy(states_masks[z], zone_configs[z].get('device_count',16))
        pct = (total / cap) * 100 if cap>0 else 100.0
        utils.append((total, pct, cap))
    return utils

def load_balance_ok(utils, grid_segments):
    if not utils:
        return True
    pcts = [u[1] for u in utils]
    mx = max(pcts)
    mn = min(pcts)
    # constraint: max-min <=40% unless unavoidable
    return (mx - mn) <= 40.0

def enforce_grid_balance_by_reduction(states_masks, grid_segments, zone_configs, mutual_exclusion_groups, synchronization_groups):
    # naive approach: if any segment >80% try reduce non-priority non-sync devices
    utils = segment_utilizations(states_masks, grid_segments, zone_configs)
    for idx, seg in enumerate(grid_segments):
        total, pct, cap = utils[idx]
        if pct > 80.0 or total > seg.get('segment_capacity', 0):
            # attempt to reduce devices in zones in this segment (skip priorities)
            zones = seg.get('zones_in_segment', [])
            # gather candidate devices (non-priority, not in sync groups) with state >0
            candidates = []
            for z in zones:
                if z >= len(states_masks): continue
                dcount = zone_configs[z].get('device_count',16)
                pri = zone_configs[z].get('priority_devices', {})
                for i in range(dcount):
                    if str(i) in pri: continue
                    s = get_device_state(states_masks[z], i)
                    if s > 0:
                        # cost of reducing by one state
                        if s > 0:
                            candidates.append((z, i, s))
            # sort candidates by energy impact descending to reduce more impactful first
            candidates.sort(key=lambda x: STATE_ENERGY[x[2]] - STATE_ENERGY[max(0, x[2]-1)], reverse=True)
            changed = True
            while (pct > 80.0 or total > cap) and candidates:
                z,i,s = candidates.pop(0)
                new_s = max(0, s-1)
                states_masks[z] = set_device_state(states_masks[z], i, new_s)
                total = sum(zone_energy(states_masks[z2], zone_configs[z2].get('device_count',16)) for z2 in zones)
                pct = (total / cap) * 100 if cap>0 else 100.0
            utils = segment_utilizations(states_masks, grid_segments, zone_configs)
    return states_masks

def validate_all_constraints(states_masks, zone_configs, grid_segments, inter_zone_deps, weather_conditions, global_energy_limit, mutual_exclusion_groups, synchronization_groups, cascading_propagation):
    # check zone contradictions
    for z in range(len(zone_configs)):
        if check_zone_internal_contradictions(z, zone_configs):
            return False, z
    # priorities
    for z_idx, zconf in enumerate(zone_configs):
        for k,v in zconf.get('priority_devices', {}).items():
            di = int(k)
            if get_device_state(states_masks[z_idx], di) < v:
                return False, None
    # device dependencies
    for z_idx, zconf in enumerate(zone_configs):
        for dep in zconf.get('device_dependencies', []):
            if len(dep)<3: continue
            d, reqd, minstate = dep
            if get_device_state(states_masks[z_idx], reqd) > 0 and get_device_state(states_masks[z_idx], d) < minstate:
                return False, None
    # inter-zone deps
    for za, da, zb, minb in inter_zone_deps:
        if za >= len(states_masks) or zb >= len(states_masks): continue
        if get_device_state(states_masks[za], da) > 0 and get_device_state(states_masks[zb], da) < minb:
            return False, None
    # cascading propagation already applied earlier
    # mutual exclusion
    for group in mutual_exclusion_groups:
        peaks = 0
        for (z,d) in group:
            if z >= len(states_masks): continue
            if get_device_state(states_masks[z], d) == 3:
                peaks += 1
        if peaks > 1:
            return False, None
    # sync groups: all same state
    for group in synchronization_groups:
        vals = None
        for (z,d) in group:
            if z >= len(states_masks): continue
            v = get_device_state(states_masks[z], d)
            if vals is None:
                vals = v
            else:
                if v != vals:
                    return False, None
    # weather
    if weather_conditions.get('temperature', 0) > weather_conditions.get('high_temp_threshold', 1e9):
        for (z,d) in weather_conditions.get('devices_affected', []):
            if get_device_state(states_masks[z], d) < 2:
                return False, None
    # zone quotas
    for z_idx, zconf in enumerate(zone_configs):
        quota = zconf.get('energy_quota', 10**9)
        if zone_energy(states_masks[z_idx], zconf.get('device_count',16)) > quota:
            return False, None
    # global energy
    total = sum(zone_energy(m, zone_configs[i].get('device_count',16)) for i,m in enumerate(states_masks))
    if total > global_energy_limit:
        return False, None
    # grid segments capacity and balance
    utils = segment_utilizations(states_masks, grid_segments, zone_configs)
    for idx, seg in enumerate(grid_segments):
        total, pct, cap = utils[idx]
        if total > seg.get('segment_capacity', 0):
            return False, None
    if not load_balance_ok(utils, grid_segments):
        # allow but mark invalid here (we desire unless unavoidable). treat as invalid so search will try other configs.
        return False, None
    return True, None

def weighted_objective(states_masks, orig_masks, zone_configs, transition_cost_matrices):
    energy = sum(zone_energy(states_masks[z], zone_configs[z].get('device_count',16)) for z in range(len(states_masks)))
    trans = compute_total_transition_cost(orig_masks, states_masks, zone_configs, transition_cost_matrices)
    return 0.7 * energy + 0.3 * trans, energy, trans

def optimize_smart_city_energy(
    zone_states: List[int],
    zone_configs: List[Dict[str, Any]],
    grid_segments: List[Dict[str, Any]],
    inter_zone_deps: List[List[int]],
    weather_conditions: Dict[str, Any],
    global_energy_limit: int,
    mutual_exclusion_groups: List[List[List[int]]],
    synchronization_groups: List[List[List[int]]],
    cascading_propagation: List[List[int]],
    transition_cost_matrices: List[List[List[int]]]
) -> List[int]:
    # Basic preparation and checks
    zones = len(zone_states)
    # normalize transition matrices dimensions: ensure each zone has 16 device matrices
    for z in range(len(transition_cost_matrices)):
        if len(transition_cost_matrices[z]) < 16:
            base = transition_cost_matrices[z][0] if transition_cost_matrices[z] else [[[0]*4 for _ in range(4)]]*16
            transition_cost_matrices[z] = (transition_cost_matrices[z] + [base]*16)[:16]
    # early per-zone contradiction detection
    for z in range(len(zone_configs)):
        if check_zone_internal_contradictions(z, zone_configs):
            # return -1 at that zone index
            out = [m for m in zone_states]
            out = [-1 if i==z else out[i] for i in range(len(out))]
            return out
    # initial candidate is start state; we'll attempt to adjust to satisfy constraints and optimize
    best_solution = None
    best_obj = float('inf')
    best_balance_std = float('inf')
    orig_masks = list(zone_states)
    # We'll perform a bounded-depth systematic search: try changing up to k devices across zones where k <=8
    # Build list of mutable device positions (zone, device)
    mutable_positions = []
    for z_idx, zconf in enumerate(zone_configs):
        dcount = zconf.get('device_count', 16)
        for d in range(dcount):
            mutable_positions.append((z_idx, d))
    # To limit branching, consider only devices that are not strict priority requiring peak or fixed by weather
    candidates = []
    for (z,d) in mutable_positions:
        pd = zone_configs[z].get('priority_devices', {})
        if str(d) in pd:
            continue
        if weather_conditions.get('temperature', 0) > weather_conditions.get('high_temp_threshold', 1e9):
            if [z,d] in weather_conditions.get('devices_affected', []):
                continue
        candidates.append((z,d))
    # if none candidates fallback to all
    if not candidates:
        candidates = mutable_positions
    # limit candidates to reasonable number based on requirement
    MAX_CAND = min(len(candidates), 12)
    candidates = candidates[:MAX_CAND]
    K = min(8, len(candidates))
    # brute force over combinations of up to K devices states (each device 4 states) but with pruning
    # We'll generate combinations of up to depth K devices to change from original; also include the original no-change option
    tried = 0
    # include empty change (baseline)
    all_indices = list(range(len(candidates)))
    # generate subsets of indices up to size K
    subsets = []
    for r in range(0, K+1):
        for comb in itertools.combinations(all_indices, r):
            subsets.append(comb)
    # For each subset, try all state assignments (4^r). Prune quickly by quotas/capacities heuristics
    for subset in subsets:
        r = len(subset)
        if r == 0:
            candidate_masks = list(orig_masks)
            # apply cascade, sync, deps, mutual exclusion, weather, priorities
            candidate_masks = apply_cascading_requirements(candidate_masks, cascading_propagation, zone