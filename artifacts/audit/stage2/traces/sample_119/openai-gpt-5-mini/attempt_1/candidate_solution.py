def optimize_water_distribution(source_nodes: List[Dict], pipe_segments: List[Dict], 
                               demand_zones: List[Dict], reservoir_nodes: List[Dict]) -> Dict[str, Any]:
    # Validation
    if not demand_zones:
        return {"error": "No demand zones provided"}
    # build node set from sources, pipes, reservoirs, demand zones
    node_ids = set()
    for s in source_nodes:
        node_ids.add(s.get("source_id"))
    for p in pipe_segments:
        if "start_node_id" in p:
            node_ids.add(p["start_node_id"])
        if "end_node_id" in p:
            node_ids.add(p["end_node_id"])
    for r in reservoir_nodes:
        node_ids.add(r.get("node_id"))
    for z in demand_zones:
        node_ids.add(z.get("node_id"))
    # Validate sources
    for s in source_nodes:
        sid = s.get("source_id")
        coords = s.get("location_coordinates")
        if not isinstance(coords, list) or len(coords) != 2 or any(not isinstance(c, (int, float)) or c<0 or c>2000 for c in coords):
            return {"error": f"Invalid coordinates for source {sid}"}
        if s.get("current_production_rate",0) > s.get("max_output_capacity",0):
            return {"error": f"Source production exceeds maximum capacity for source {sid}"}
    # Validate pipes
    valid_status = {"active","maintenance","degraded","critical"}
    for p in pipe_segments:
        pid = p.get("pipe_id")
        if p.get("start_node_id") not in node_ids or p.get("end_node_id") not in node_ids:
            return {"error": f"Invalid node reference in pipe {pid}"}
        if p.get("current_flow_rate",0) > p.get("max_flow_capacity",0):
            return {"error": f"Current flow exceeds pipe capacity for pipe {pid}"}
        if p.get("maintenance_status") not in valid_status:
            return {"error": f"Invalid maintenance status for pipe {pid}"}
    # Validate demand zones
    for z in demand_zones:
        zid = z.get("zone_id")
        if z.get("minimum_flow_requirement",0) > z.get("target_flow_requirement",0):
            return {"error": f"Invalid flow requirements for zone {zid}"}
        pl = z.get("priority_level")
        if pl is None or not (1 <= pl <=5):
            return {"error": f"Invalid priority level for zone {zid}"}
    # Validate reservoirs
    for r in reservoir_nodes:
        rid = r.get("reservoir_id")
        if r.get("current_water_level",0) > r.get("overflow_threshold",0):
            return {"error": f"Reservoir {rid} exceeds overflow threshold"}
    # Build graph adjacency for active pipes only
    pipes_by_id = {p["pipe_id"]: copy.deepcopy(p) for p in pipe_segments}
    adj = defaultdict(list)
    rev_adj = defaultdict(list)
    for p in pipe_segments:
        adj[p["start_node_id"]].append(p["end_node_id"])
        rev_adj[p["end_node_id"]].append(p["start_node_id"])
    # Connectivity: each demand zone must be reachable from some source through active pipes (maintenance/degraded/critical still considered as edges but only "active" preferred in redistribution)
    active_edges = set()
    for p in pipe_segments:
        if p["maintenance_status"] == "active":
            active_edges.add((p["start_node_id"], p["end_node_id"]))
    # For connectivity, allow any maintenance status as path existence
    graph_any = defaultdict(list)
    for p in pipe_segments:
        graph_any[p["start_node_id"]].append(p["end_node_id"])
    source_node_ids = set(s["source_id"] for s in source_nodes)
    def reachable(node):
        visited = set()
        dq = deque()
        for sn in source_node_ids:
            dq.append(sn)
            visited.add(sn)
        while dq:
            u = dq.popleft()
            if u == node:
                return True
            for v in graph_any.get(u,[]):
                if v not in visited:
                    visited.add(v)
                    dq.append(v)
        return False
    for z in demand_zones:
        if not reachable(z["node_id"]):
            return {"error": "Network contains unreachable demand zones"}
    # Prepare capacities for max-flow: edges as pipe_id keyed
    # We'll create network with super-source connected to each source node with capacity = available production (max_output_capacity - current usage limited by current_production_rate)
    # and sinks as demand zone nodes with required target_flow_requirement.
    # Compute total available capacity from sources (sum of outgoing capacities from sources)
    total_available_capacity = 0
    source_out_caps = {}
    for s in source_nodes:
        cap = s.get("max_output_capacity",0)
        total_available_capacity += cap
        source_out_caps[s["source_id"]] = cap
    # Build edge capacities mapping (start,end) -> capacity initial equal to max_flow_capacity - current_flow_rate (remaining)
    # But algorithm will allocate anew ignoring current_flow_rate as flows replaced by allocated_flow_rate; still consider current as baseline for validations and utilization.
    edge_caps = {}
    for p in pipe_segments:
        start = p["start_node_id"]; end = p["end_node_id"]
        cap = p["max_flow_capacity"]
        # effective capacity adjusted for maintenance/degraded per guidelines (reduce by 30% or 50%)
        status = p["maintenance_status"]
        if status == "maintenance":
            cap = int(cap * 0.7)
        elif status == "degraded":
            cap = int(cap * 0.5)
        edge_caps[(start,end,p["pipe_id"])] = cap
    # Detect cycles using DFS on directed graph considering edges with current_flow_rate >0
    graph_flow = defaultdict(list)
    for p in pipe_segments:
        if p.get("current_flow_rate",0) > 0:
            graph_flow[p["start_node_id"]].append((p["end_node_id"], p["pipe_id"]))
    visited = {}
    cycles = []
    path_stack = []
    def dfs(u):
        visited[u] = 1
        for v,pid in graph_flow.get(u,[]):
            if visited.get(v,0) == 0:
                path_stack.append((u,v,pid))
                dfs(v)
                path_stack.pop()
            elif visited.get(v,0) == 1:
                # found cycle: collect node sequence
                seq = []
                # include nodes from first occurrence of v in path_stack
                for a,b,pp in path_stack:
                    seq.append(a)
                    if b == v:
                        seq.append(b)
                        break
                # ensure unique
                if seq and seq not in cycles:
                    cycles.append(seq)
        visited[u] = 2
    for n in list(node_ids):
        if visited.get(n,0) == 0:
            dfs(n)
    cycles_detected = len(cycles)
    redistributed_total = 0
    # If cycles, apply redistribution rule: reduce minimum flow in cycle by 20% and redistribute to alternative pipes
    if cycles_detected > 0:
        for cycle in cycles:
            # find pipe ids in cycle
            cycle_pids = []
            # collect consecutive edges
            for i in range(len(cycle)-1):
                a = cycle[i]; b = cycle[i+1]
                for p in pipe_segments:
                    if p["start_node_id"]==a and p["end_node_id"]==b and p.get("current_flow_rate",0)>0:
                        cycle_pids.append(p["pipe_id"])
                        break
            if not cycle_pids:
                continue
            # find minimum current_flow_rate among those pipes
            min_flow = min(pipes_by_id[pid]["current_flow_rate"] for pid in cycle_pids)
            reduce_amount = int(min_flow * 0.2)
            if reduce_amount <=0:
                continue
            redistributed_total += reduce_amount * len(cycle_pids)
            # reduce from each pipe proportionally (20% of its flow)
            for pid in cycle_pids:
                p = pipes_by_id[pid]
                dec = int(p["current_flow_rate"] * 0.2)
                p["current_flow_rate"] = max(0, p["current_flow_rate"] - dec)
            # find alternative pipes: not in cycle, maintenance_status active, utilization <80%
            alt_pipes = []
            for p in pipe_segments:
                if p["pipe_id"] in cycle_pids:
                    continue
                if p["maintenance_status"] != "active":
                    continue
                util = p["current_flow_rate"] / p["max_flow_capacity"] if p["max_flow_capacity"]>0 else 0
                if util < 0.8:
                    alt_pipes.append(p)
            if alt_pipes:
                # distribute total reduced flow evenly among qualifying alternative pipes respecting remaining capacity
                total_to_distribute = sum(int(pipes_by_id[pid]["current_flow_rate"] * 0.2) for pid in cycle_pids)
                per = total_to_distribute // len(alt_pipes)
                for p in alt_pipes:
                    rem = p["max_flow_capacity"] - p["current_flow_rate"]
                    add = min(per, rem)
                    p["current_flow_rate"] += add
    # Now perform flow allocation using simplified Ford-Fulkerson from super-source to super-sink.
    # Build nodes mapping: use integers; super-source = -1, super-sink = -2
    # Edges with capacities: from super-source to each source node capacity = source current_production_rate (we use current_production_rate as available)
    # from pipes: start->end capacity = edge_caps[(start,end,pid)]
    # from demand zone node to super-sink capacity = target_flow_requirement
    capacities = defaultdict(int)
    neighbors = defaultdict(list)
    def add_edge(u,v,c):
        capacities[(u,v)] = capacities.get((u,v),0) + c
        capacities.setdefault((v,u),0)
        if v not in neighbors[u]:
            neighbors[u].append(v)
        if u not in neighbors[v]:
            neighbors[v].append(u)
    super_source = -1
    super_sink = -2
    for s in source_nodes:
        add_edge(super_source, s["source_id"], s.get("current_production_rate",0))
    for (start,end,pid), cap in edge_caps.items():
        add_edge(start, end, cap)
    zone_targets = {}
    for z in demand_zones:
        zid = z["zone_id"]; node = z["node_id"]; target = z["target_flow_requirement"]
        zone_targets[zid] = (node,target,z["minimum_flow_requirement"], z["priority_level"])
        add_edge(node, super_sink, target)
    # Edmonds-Karp BFS
    def bfs_find_path():
        parent = {}
        q = deque([super_source])
        parent[super_source] = None
        while q:
            u = q.popleft()
            for v in neighbors.get(u,[]):
                if v not in parent and capacities.get((u,v),0) > 0:
                    parent[v] = u
                    if v == super_sink:
                        # build path
                        path = []
                        cur = v
                        while cur != super_source:
                            prev = parent[cur]
                            path.append((prev,cur))
                            cur = prev
                        path.reverse()
                        return path
                    q.append(v)
        return None
    # Run to maximize fulfillment but we need to prioritize priority zones: we will iteratively open sink edges for zones by priority
    # So remove all node->super_sink edges initially, then add by ascending priority
    # Remove by setting capacity to 0
    saved_zone_edges = {}
    for z in demand_zones:
        node = z["node_id"]; target = z["target_flow_requirement"]
        saved_zone_edges[node] = capacities.get((node,super_sink),0)
        capacities[(node,super_sink)] = 0
    # Also maintain allocated flows on pipes
    allocated_on_edge = defaultdict(int)
    # process zones by priority
    zones_sorted = sorted(demand_zones, key=lambda x: x["priority_level"])
    zone_delivered = {}
    for z in zones_sorted:
        node = z["node_id"]; target = z["target_flow_requirement"]; minreq = z["minimum_flow_requirement"]
        # open this zone's sink capacity
        capacities[(node,super_sink)] = target
        if super_sink not in neighbors[node]:
            neighbors[node].append(super_sink)
        if node not in neighbors[super_sink]:
            neighbors[super_sink].append(node)
        # run max-flow until no augmenting path or until this zone full
        while True:
            path = bfs_find_path()
            if not path:
                break
            # find bottleneck
            bottleneck = min(capacities[(u,v)] for u,v in path)
            # send flow
            for u,v in path:
                capacities[(u,v)] -= bottleneck
                capacities[(v,u)] += bottleneck
                # if edge corresponds to an actual pipe (start->end with pipe id)
                # we find matching pipe_id(s) in original edge_caps keys
                # update allocated_on_edge by matching start,end and available capacity difference
                for p in pipe_segments:
                    if p["start_node_id"]==u and p["end_node_id"]==v:
                        allocated_on_edge[p["pipe_id"]] += bottleneck
                        break
            # stop early if sink edge is saturated
            if capacities[(node,super_sink)] == 0:
                break
        # compute delivered to this zone as flow accumulated into super_sink from node
        delivered = 0
        # delivered equals flow on reverse edge super_sink->node (which stores flow)
        delivered = capacities.get((super_sink,node),0)
        # But there may be flows from other nodes into sink; we compute specific by original target - remaining capacity
        delivered = target - capacities.get((node,super_sink),0)
        zone_delivered[z["zone_id"]] = delivered
        # if not meeting minimum and cannot augment further, still record delivered
    # Build optimal_flow_allocation for each pipe: allocated_flow_rate should replace current_flow_rate
    optimal_allocation = []
    total_flow_delivered = sum(zone_delivered.values())
    # For pipes without any allocated flow, we may set allocated to min(current_flow_rate, max_flow_capacity) or 0.
    for p in pipe_segments:
        pid = p["pipe_id"]
        alloc = allocated_on_edge.get(pid, 0)
        # Ensure integer and not exceeding max
        alloc = int(min(alloc, p["max_flow_capacity"]))
        utilization = (alloc / p["max_flow_capacity"])*100 if p["max_flow_capacity"]>0 else 0.0
        # apply pressure drop formula to compute effective_capacity
        if p["max_flow_capacity"]>0:
            ratio = alloc / p["max_flow_capacity"]
            eff = p["max_flow_capacity"]
            if ratio > 0.9:
                eff = int(p["max_flow_capacity"] * 0.8)
            elif ratio > 0.8:
                eff = int(p["max_flow_capacity"] * 0.9)
            else:
                eff = p["max_flow_capacity"]
        else:
            eff = 0
        # maintenance integration: effective capacity reductions already applied earlier to edge_caps; but output requires effective_capacity as integer
        if p["maintenance_status"] == "maintenance":
            eff = int(eff * 0.7)
        elif p["maintenance_status"] == "degraded":
            eff = int(eff * 0.5)
        # pressure status
        if utilization <= 80.0:
            ps = "normal"
        elif utilization <= 90.0:
            ps = "reduced"
        else:
            ps = "critical"
        optimal_allocation.append({
            "pipe_id": pid,
            "allocated_flow_rate": int(alloc),
            "utilization_percentage": round(utilization,2),
            "effective_capacity": int(eff),
            "pressure_status": ps
        })
    # zone satisfaction list
    zone_satisfaction = []
    for z in demand_zones:
        zid = z["zone_id"]
        delivered = int(zone_delivered.get(zid,0))
        target = z["target_flow_requirement"]
        minreq = z["minimum_flow_requirement"]
        satisfaction_percentage = (delivered / target *100) if target>0 else 0.0
        priority_met = delivered >= minreq
        zone_satisfaction.append({
            "zone_id": zid,
            "flow_delivered": delivered,
            "satisfaction_percentage": round(satisfaction_percentage,2),
            "priority_met": priority_met
        })
    # cycle_analysis
    cycle_paths = cycles
    # reservoir status: compute net flows approximate: inflow sum of allocated on pipes ending at reservoir node, outflow sum of allocated on pipes starting at reservoir node
    reservoir_status = []
    for r in reservoir_nodes:
        rid = r["reservoir_id"]; node = r["node_id"]
        inflow = 0; outflow = 0
        for p in pipe_segments:
            pid = p["pipe_id"]
            alloc = allocated_on_edge.get(pid,0)
            if p["end_node_id"] == node:
                inflow += alloc
            if p["start_node_id"] == node:
                outflow += alloc
        net_flow_rate = inflow - outflow
        # convert to cubic meters per minute net_flow_rate/1000; cumulative_volume_change assumed single minute for simplicity
        volume_change = net_flow_rate / 1000.0
        final_level = r["current_water_level"] + volume_change
        overflow_risk = final_level > r["overflow_threshold"]
        utilization_rate = r["current_water_level"] / r["max_storage_capacity"] if r["max_storage_capacity"]>0 else 0.0
        reservoir_status.append({
            "reservoir_id": rid,
            "final_water_level": int(final_level),
            "overflow_risk": bool(overflow_risk),
            "utilization_rate": round(utilization_rate,4)
        })
    # system metrics
    total_production_cost = 0.0
    for s in source_nodes:
        total_production_cost += s.get("current_production_rate",0) * s.get("operational_cost",0.0)
    # bottleneck pipes: utilization >95%
    bottleneck_pipes = []
    underutilized_capacity = 0
    for p in pipe_segments:
        pid = p["pipe_id"]
        alloc = allocated_on_edge.get(pid,0)
        util_pct = (alloc / p["max_flow_capacity"])*100 if p["max_flow_capacity"]>0 else 0
        if util_pct >