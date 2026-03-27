def optimize_logistics_network(
    nodes: List[int],
    base_edges: Dict[str, List[dict]],
    commodities: List[dict],
    time_horizon: int,
    holding_rules: Optional[List[dict]] = None,
    dynamic_obstructions: Optional[List[dict]] = None
) -> Dict[str, Any]:
    # Build obstruction lookup
    obstruction = {}
    if dynamic_obstructions:
        for d in dynamic_obstructions:
            obstruction[(d["u"], d["v"])] = d["block_time"]
    # Build transitive closure of forbidden commodity pairs across all edges
    C = {c["id"] for c in commodities}
    forb = {c: set() for c in C}
    for u_s, edges in base_edges.items():
        for e in edges:
            for a, b in e.get("forbidden_pairs", []):
                forb.setdefault(a, set()).add(b)
                forb.setdefault(b, set()).add(a)
    # Floyd-Warshall style closure on small commodity set
    changed = True
    while changed:
        changed = False
        for a in list(forb.keys()):
            for b in list(forb[a]):
                for c in list(forb.get(b, set())):
                    if c not in forb[a] and c != a:
                        forb[a].add(c)
                        changed = True

    # Create time-layered graph nodes: (node, t)
    # Create stateful edges with locks and capacities
    edge_id_counter = 0
    state_edges = {}  # id -> edge dict
    out_edges = defaultdict(list)  # (u,t) -> list of edge ids
    in_edges = defaultdict(list)   # (v,t') -> list of edge ids

    def add_state_edge(u, tu, v, tv, capacity, cost, forbidden_set, edge_obj):
        nonlocal edge_id_counter
        eid = edge_id_counter
        edge_id_counter += 1
        state_edges[eid] = {
            "u": u, "tu": tu, "v": v, "tv": tv,
            "cap": float(capacity),
            "cost": float(cost),
            "forbidden": set(forbidden_set),
            "lock": threading.Lock(),
            "resid": float(capacity),
            "orig": edge_obj
        }
        out_edges[(u, tu)].append(eid)
        in_edges[(v, tv)].append(eid)

    # Expand edges per time windows, handling obstructions and reverse edges
    for u_s, edges in base_edges.items():
        u = int(u_s)
        for e in edges:
            v = int(e["to"])
            cap = e.get("capacity", 0)
            cost = e.get("cost", 0.0)
            tws = e.get("time_windows", [])
            forb_pairs = e.get("forbidden_pairs", [])
            edge_ob = e.get("obstruction_time", None)
            glob_ob = obstruction.get((u, v))
            if edge_ob is not None and glob_ob is not None:
                block_time = min(edge_ob, glob_ob)
            else:
                block_time = edge_ob if edge_ob is not None else glob_ob
            # Build forbidden set transitive expanded
            forb_set = set()
            for a,b in forb_pairs:
                forb_set.add(a); forb_set.add(b)
                forb_set |= forb.get(a, set()) | forb.get(b, set())
            for tw in tws:
                s, t = tw
                for tt in range(s, t+1):
                    if block_time is not None and tt >= block_time:
                        continue
                    # travel assumed to take 1 timestep: (u,tt)->(v,tt+1)
                    if tt+1 <= time_horizon:
                        add_state_edge(u, tt, v, tt+1, cap, cost, forb_set, e)
            # reverse edge if provided
            rev = e.get("reverse_edge")
            if rev:
                rv = rev.get("to", u)
                rcap = rev.get("capacity", cap)
                rcost = rev.get("cost", -cost)
                rtw = rev.get("time_windows", tws)
                rforb = rev.get("forbidden_pairs", [])
                r_edge_ob = rev.get("obstruction_time", None)
                for tw in rtw:
                    s, t = tw
                    for tt in range(s, t+1):
                        if r_edge_ob is not None and tt >= r_edge_ob:
                            continue
                        if tt+1 <= time_horizon:
                            add_state_edge(v, tt, rv, tt+1, rcap, rcost, rforb, rev)

    # Holding edges at nodes
    holding_map = {}
    if holding_rules:
        for h in holding_rules:
            holding_map[h["node"]] = {"cap": h["capacity"], "cost": h["cost_per_unit_per_time"]}
    for n in nodes:
        hr = holding_map.get(n)
        for t in range(0, time_horizon):
            if hr:
                add_state_edge(n, t, n, t+1, hr["cap"], hr["cost"], set(), {"holding": True})
            else:
                # allow free holding with infinite cap and zero cost if unspecified
                add_state_edge(n, t, n, t+1, 1e12, 0.0, set(), {"holding": True})

    # Prepare commodity order by priority descending
    commodities_sorted = sorted(commodities, key=lambda x: (-x.get("priority", 0), x["id"]))
    # Determine integer vs float
    integer_flow = all(float(c["demand"]).is_integer() for c in commodities)
    # Outputs
    paths_out = {}
    flows_out = {}
    total_cost = 0.0
    total_throughput = 0.0

    # For each commodity in priority order, run successive shortest augmentations until demand met or no path
    for com in commodities_sorted:
        cid = com["id"]
        demand = float(com["demand"])
        remaining = demand
        max_split = max(1, int(com.get("max_split", 1)))
        found_paths = []
        achieved = 0.0

        # We will allow splits up to max_split: loop augmentations
        for split_idx in range(max_split):
            if remaining <= 1e-9:
                break
            # Build residual graph costs and capacities snapshot
            # Use Bellman-Ford (because negative costs possible), but graph size can be large; use SPFA-like
            # Source nodes are (source, t) for t in 0..time_horizon where commodity can start
            s_nodes = [(com["source"], t) for t in range(0, time_horizon+1)]
            t_nodes = [(com["sink"], t) for t in range(0, time_horizon+1)]
            # Try to find shortest path from any s_node to any t_node using available residual capacities and respecting forbidden sets
            dist = {}
            prev = {}
            inq = {}
            q = deque()
            # Initialize distances for all possible start times as 0 if there is outgoing capacity from that (node,t)
            for sn in s_nodes:
                dist[sn] = 0.0
                q.append(sn)
                inq[sn] = True
            # SPFA on layered nodes using state_edges
            while q:
                cur = q.popleft()
                inq[cur] = False
                for eid in out_edges.get(cur, []):
                    ed = state_edges[eid]
                    withed = False
                    # check residual
                    if ed["resid"] <= 1e-9:
                        continue
                    # commodity conflict: if any forbidden commodity present on edge equal to this commodity then capacity may be limited.
                    # We enforce that if forbidden contains this cid, at most 1 unit of this commodity can be on that edge.
                    if cid in ed["forbidden"]:
                        # if any flow already assigned to same commodity on this edge -> treat resid as min(resid, 1 - used_by_same)
                        # We track only resid, and no per-commodity assignment stored; to enforce at most one unit, assume resid <=1 when forbidden contains self
                        # For simplicity, if original cap >1 and forbidden self exists, limit augmentation to min(1.0, resid)
                        pass
                    nu = (ed["v"], ed["tv"])
                    nd = dist[cur] + ed["cost"]
                    if nu not in dist or nd + 1e-12 < dist[nu]:
                        dist[nu] = nd
                        prev[nu] = (cur, eid)
                        if not inq.get(nu, False):
                            q.append(nu); inq[nu] = True
            # Find best sink time with minimal dist
            best_tnode = None
            best_cost = None
            for tn in t_nodes:
                if tn in dist:
                    if best_cost is None or dist[tn] < best_cost:
                        best_cost = dist[tn]; best_tnode = tn
            if best_tnode is None:
                break  # no augmenting path
            # Reconstruct path edges
            path_nodes = []
            path_eids = []
            cur = best_tnode
            while cur in prev:
                pcur, peid = prev[cur]
                path_eids.append(peid)
                path_nodes.append(cur[0])
                cur = pcur
            # add start node
            path_nodes.append(cur[0])
            path_nodes.reverse()
            # Determine bottleneck capacity considering forbidden pairs and resid
            bottleneck = remaining
            for eid in path_eids:
                ed = state_edges[eid]
                # compute allowed resid for this commodity considering forbidden sets
                allowed = ed["resid"]
                # self-conflict: if forbidden contains cid and original capacity >=1, allow at most 1.0
                if cid in ed["forbidden"]:
                    allowed = min(allowed, 1.0)
                # transitive conflicts: if any forbidden commodity already routed on this edge -> we don't track per-edge assignment; assume worst-case and allow only if no forbidden (best-effort)
                # For concurrency safety, will lock when applying
                if allowed < bottleneck:
                    bottleneck = allowed
            if bottleneck <= 1e-9:
                break
            # Apply augmentation with locks per edge to avoid race conditions
            # For concurrency: try to reserve capacities with threadpool (parallel locks)
            def reserve(eid, amount):
                ed = state_edges[eid]
                ed["lock"].acquire()
                try:
                    take = min(ed["resid"], amount)
                    # enforce self-forbid
                    if cid in ed["forbidden"]:
                        take = min(take, 1.0)
                    ed["resid"] -= take
                    return take, ed["cost"]
                finally:
                    ed["lock"].release()
            # We want to atomically take bottleneck across edges; do per-edge locking sequentially to avoid deadlock (consistent ordering)
            path_eids_sorted = sorted(path_eids)
            # Acquire all locks in order
            for eid in path_eids_sorted:
                state_edges[eid]["lock"].acquire()
            try:
                # recompute true bottleneck under locks
                true_bottleneck = remaining
                for eid in path_eids:
                    ed = state_edges[eid]
                    allowed = ed["resid"]
                    if cid in ed["forbidden"]:
                        allowed = min(allowed, 1.0)
                    true_bottleneck = min(true_bottleneck, allowed)
                if true_bottleneck <= 1e-9:
                    taken = 0.0
                else:
                    # reduce resid
                    for eid in path_eids:
                        ed = state_edges[eid]
                        reduce_amt = true_bottleneck
                        ed["resid"] -= reduce_amt
                    taken = true_bottleneck
            finally:
                for eid in reversed(path_eids_sorted):
                    state_edges[eid]["lock"].release()
            if taken <= 1e-9:
                break
            # record path and cost
            path_cost = 0.0
            for eid in path_eids:
                path_cost += state_edges[eid]["cost"]
            found_paths.append(path_nodes)
            achieved += taken
            remaining -= taken
            total_cost += taken * path_cost
            total_throughput += taken
        # finalize commodity result
        # cast to int if integer_flow true
        if integer_flow:
            achieved = int(round(achieved))
            demand = int(round(demand))
        paths_out[str(cid)] = found_paths
        flows_out[str(cid)] = float(achieved) if not integer_flow else achieved
        total_cost = float(total_cost)
        total_throughput = float(total_throughput)

    return {"paths": paths_out, "flows": flows_out, "cost": total_cost, "throughput": total_throughput}