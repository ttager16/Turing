def optimize_rehearsal_schedule(
    actor_availability: List[List],
    scene_requirements: List[Dict[str, Any]],
    historical_data: Dict[str, List[int]],
    role_mapping: Dict[str, Dict[str, float]],
    transport_times: Dict[str, int],
    buffer_intervals: int,
    rehearsal_capacity: Dict[str, int]
) -> Dict[str, Dict[str, List[str]]]:
    # Prepare actor sets and availability map
    actors = [entry[0] for entry in actor_availability]
    avail_map = {entry[0]: set(entry[1]) for entry in actor_availability}
    # Compute P_available from historical data (average)
    p_avail = {}
    for a in actors:
        hist = historical_data.get(a, [])
        if hist:
            p_avail[a] = sum(hist) / len(hist)
        else:
            p_avail[a] = 0.5
    # role fit default
    def role_fit(a, r):
        return role_mapping.get(a, {}).get(r, 1.0)
    # transport time lookup symmetric
    def transport(a, b):
        if a == b:
            return 0
        k1 = f"{a}-{b}"
        k2 = f"{b}-{a}"
        return transport_times.get(k1, transport_times.get(k2, 5))  # default medium travel 5
    # Sort actors by name for tie-breaker index
    sorted_actors = sorted(actors)
    idx_map = {a: i for i, a in enumerate(sorted_actors)}
    # Build scene list sorted by time
    scenes = sorted(scene_requirements, key=lambda x: x['time_slot'])
    # Initialize assignments
    assignments = {s['scene_id']: {role: [] for role in s['roles'].keys()} for s in scenes}
    # Track per actor assigned scenes (list of time_slots)
    actor_assigned_times = {a: [] for a in actors}
    actor_assigned_count = {a: 0 for a in actors}
    # Helper to check buffer feasibility
    def can_assign_actor(a, scene_time):
        if actor_assigned_count[a] >= rehearsal_capacity.get(a, math.inf):
            return False
        for t in actor_assigned_times[a]:
            if abs(t - scene_time) <= buffer_intervals:
                return False
        return True
    # For each scene, for each role slot, pick best actor greedily
    for scene in scenes:
        sid = scene['scene_id']
        tslot = scene['time_slot']
        # Precompute candidate actors available at that time and feasible by buffer/capacity
        candidates = [a for a in actors if tslot in avail_map.get(a, set()) and can_assign_actor(a, tslot)]
        # For computing C_travel for a candidate we consider already assigned actors to this scene
        for role, count_needed in scene['roles'].items():
            for _ in range(count_needed):
                best_score = None
                best_actor = None
                for a in candidates:
                    if a in sum([assignments[sid][r] for r in assignments[sid]], []):
                        # already assigned to a role in this scene (one role per scene)
                        continue
                    # compute components
                    P_available = p_avail.get(a, 0.0)
                    W_role_fit = role_fit(a, role)
                    U_workload = actor_assigned_count[a] / max(1, rehearsal_capacity.get(a, 1))
                    # compute average travel cost among actors already assigned to this scene plus this actor
                    current_assigned = sum([assignments[sid][r] for r in assignments[sid]], [])
                    travel_costs = []
                    for other in current_assigned + [a]:
                        for other2 in current_assigned + [a]:
                            if other < other2:
                                travel_costs.append(transport(other, other2))
                    C_travel = (sum(travel_costs) / len(travel_costs)) if travel_costs else 0.0
                    P_name = 0.001 * idx_map.get(a, 0)
                    score = 2.0 * P_available + 1.5 * W_role_fit - 0.3 * U_workload - 0.1 * C_travel - P_name
                    # Only consider if actor still feasible (capacity/buffer) — already checked candidates initial, but capacity may change within loop
                    if actor_assigned_count[a] >= rehearsal_capacity.get(a, math.inf):
                        continue
                    if not can_assign_actor(a, tslot):
                        continue
                    if best_score is None or score > best_score:
                        best_score = score
                        best_actor = a
                if best_actor:
                    assignments[sid][role].append(best_actor)
                    actor_assigned_times[best_actor].append(tslot)
                    actor_assigned_count[best_actor] += 1
                    # remove from candidates if reached capacity or cannot take more at same scene
                    if actor_assigned_count[best_actor] >= rehearsal_capacity.get(best_actor, math.inf):
                        if best_actor in candidates:
                            candidates.remove(best_actor)
                else:
                    # cannot fill this slot; leave empty
                    pass
    return assignments