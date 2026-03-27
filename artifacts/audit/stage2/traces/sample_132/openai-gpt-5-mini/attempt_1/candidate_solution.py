def process_offline_graph_queries(road_network: List[Dict], intersection_data: List[Dict], 
                                closure_schedule: List[Dict], query_batch: List[Dict]) -> Dict[str, Any]:
    # Basic validations
    if not isinstance(query_batch, list) or len(query_batch) == 0:
        return {"error": "Empty query batch provided"}
    # Build intersection map
    inter_map = {}
    for inter in intersection_data:
        iid = inter.get("intersection_id")
        if iid is None:
            return {"error": "Input is not valid"}
        coords = inter.get("coordinates", {})
        x = coords.get("x"); y = coords.get("y")
        if x is None or y is None or not (0 <= x <= 10000) or not (0 <= y <= 10000):
            return {"error": f"Invalid coordinates for intersection {iid}"}
        cluster = inter.get("neighborhood_cluster")
        if not isinstance(cluster, int) or not (1 <= cluster <= 10):
            return {"error": f"Invalid neighborhood cluster assignment for intersection {iid}"}
        inter_map[iid] = inter.copy()
    # Validate road segments and build adjacency
    adj = defaultdict(list)  # node -> list of (neighbor, edge_id, properties)
    edge_map = {}
    for edge in road_network:
        eid = edge.get("edge_id")
        a = edge.get("intersection_a"); b = edge.get("intersection_b")
        if a not in inter_map or b not in inter_map:
            return {"error": f"Invalid intersection reference in road segment {eid}"}
        edge_map[eid] = edge.copy()
        adj[a].append((b, eid))
        adj[b].append((a, eid))
    # Validate connected_roads consistency
    for iid, inter in inter_map.items():
        con = inter.get("connected_roads", [])
        for eid in con:
            if eid not in edge_map:
                return {"error": f"Inconsistent road connections for intersection {iid}"}
            e = edge_map[eid]
            if not (e["intersection_a"] == iid or e["intersection_b"] == iid):
                return {"error": f"Inconsistent road connections for intersection {iid}"}
    # Validate closures times and overlapping high priority
    for cl in closure_schedule:
        cid = cl.get("closure_id")
        st = cl.get("start_time"); en = cl.get("end_time")
        if st is None or en is None or st >= en:
            return {"error": f"Invalid closure time window for closure {cid}"}
    # overlapping high-priority closures on same intersection
    high_priority_by_inter = defaultdict(list)
    for cl in closure_schedule:
        if cl.get("priority_level") == 1:
            high_priority_by_inter[cl["affected_intersection"]].append((cl["start_time"], cl["end_time"]))
    for iid, intervals in high_priority_by_inter.items():
        intervals.sort()
        for i in range(1, len(intervals)):
            if intervals[i][0] < intervals[i-1][1]:
                return {"error": "Overlapping high-priority closures detected"}
    # Validate query times
    for q in query_batch:
        qt = q.get("query_time")
        if qt is None or not (0 <= qt <= 168):
            return {"error": f"Query time outside valid range for query {q.get('query_id')}"}
    # Connectivity validation: check whole graph connected
    visited = set()
    nodes = list(inter_map.keys())
    if nodes:
        start = nodes[0]
        stack = [start]; visited.add(start)
        while stack:
            u = stack.pop()
            for v,_ in adj[u]:
                if v not in visited:
                    visited.add(v); stack.append(v)
    if len(visited) != len(inter_map):
        return {"error": "Disconnected network components detected"}
    # Preprocessing metrics
    total_intersections_processed = len(inter_map)
    total_road_segments_analyzed = len(road_network)
    # compute intersection degrees and critical intersections
    degrees = {iid: len(adj[iid]) for iid in inter_map}
    critical_intersections = [iid for iid, d in degrees.items() if d > 4]
    # Build edge attributes quick access
    def edge_attrs(eid):
        e = edge_map[eid]
        return e["segment_length"], e["traffic_density"], e["congestion_weight"], e["max_speed_limit"]
    # Build direct shortest paths (Dijkstra) function avoiding closed intersections set
    def dijkstra(src, forbidden):
        dist = {node: float('inf') for node in inter_map}
        prev = {}
        dist[src] = 0
        h = [(0, src)]
        while h:
            d,u = heapq.heappop(h)
            if d!=dist[u]: continue
            for v,eid in adj[u]:
                if v in forbidden: continue
                if u in forbidden: continue
                sl,_,_,_ = edge_attrs(eid)
                nd = d + sl
                if nd < dist[v]:
                    dist[v]=nd; prev[v]= (u,eid); heapq.heappush(h,(nd,v))
        return dist, prev
    # Precompute all-pairs shortest distances (cache limited: use Dijkstra from each node)
    shortest_cache = {}
    for node in inter_map:
        dist,_ = dijkstra(node, set())
        shortest_cache[node] = dist
    shortest_path_cache_size = sum(1 for _ in shortest_cache)
    # Helper to reconstruct path from prev map
    def reconstruct(prev, src, tgt):
        if tgt not in prev and src!=tgt:
            return None
        path = []
        cur = tgt
        if src==tgt:
            return [src]
        while cur!=src:
            path.append(cur)
            if cur not in prev:
                return None
            cur = prev[cur][0]
        path.append(src)
        return list(reversed(path))
    # Helper to find k alternative simple paths using BFS-like Yen's simplification
    def k_shortest_paths(src, tgt, k, forbidden):
        # Use simple variant: repeatedly find shortest, then ban one edge of found path to get alternative
        results = []
        banned_edges_sets = []
        base_forbidden = set(forbidden)
        temp_bans = []
        attempts = 0
        while len(results) < k and attempts < k*10:
            attempts += 1
            # build graph excluding base_forbidden and edges in latest banned set
            dist = {node: float('inf') for node in inter_map}
            prev = {}
            dist[src]=0
            h=[(0,src)]
            while h:
                d,u = heapq.heappop(h)
                if d!=dist[u]: continue
                for v,eid in adj[u]:
                    if v in base_forbidden or u in base_forbidden: continue
                    skip = False
                    for s in temp_bans:
                        if (u,v,eid) in s:
                            skip = True; break
                    if skip: continue
                    sl,_,_,_ = edge_attrs(eid)
                    nd = d+sl
                    if nd < dist[v]:
                        dist[v]=nd; prev[v]=(u,eid); heapq.heappush(h,(nd,v))
            path = reconstruct(prev, src, tgt)
            if not path:
                break
            # compute edge list for path
            edge_list = []
            for i in range(len(path)-1):
                a=path[i]; b=path[i+1]
                # find edge id
                eid = None
                for nb,eid_candidate in adj[a]:
                    if nb==b:
                        eid = eid_candidate; break
                if eid is None:
                    eid = -1
                edge_list.append((a,b,eid))
            results.append((path, edge_list))
            # ban one middle edge to get alternative next time
            ban_set = set()
            if len(edge_list)>0:
                # choose middle edge deterministically
                idx = max(0, (len(edge_list)-1)//2)
                ban_set.add(edge_list[idx])
            temp_bans.append(ban_set)
            if len(temp_bans)>k:
                temp_bans.pop(0)
        # return just paths
        return [p for p,e in results]
    # closure active set at time
    def active_closures_at(t):
        res = []
        for cl in closure_schedule:
            if cl["start_time"] <= t < cl["end_time"]:
                res.append(cl)
        return res
    # For quick mapping closure by intersection
    closures_by_inter = defaultdict(list)
    for cl in closure_schedule:
        closures_by_inter[cl["affected_intersection"]].append(cl)
    # Query processing
    query_results = []
    total_detour_distance = 0
    high_impact_closures = set()
    for q in sorted(query_batch, key=lambda x: x.get("query_id",0)):
        qid = q["query_id"]
        qtype = q["query_type"]
        src = q["source_intersection"]
        tgt = q["target_intersection"]
        qt = q["query_time"]
        max_alt = q.get("max_alternative_paths",1)
        dist_thresh = q.get("distance_threshold", 50000)
        # validate source/target
        if src not in inter_map or tgt not in inter_map:
            return {"error": "Input is not valid"}
        # theoretical min distance between src and tgt
        theoretical = shortest_cache[src].get(tgt, float('inf'))
        if theoretical==float('inf'):
            return {"error": "Disconnected network components detected"}
        if dist_thresh < theoretical:
            return {"error": f"Distance threshold too restrictive for query {qid}"}
        # compute active closures and forbidden intersections (if fully closed: alternative_capacity 0 means fully closed)
        active = active_closures_at(qt)
        forbidden = set()
        affected_closure_ids = set()
        for cl in active:
            aid = cl["affected_intersection"]
            if cl.get("alternative_capacity",0.0) <= 0.0:
                forbidden.add(aid)
                affected_closure_ids.add(cl["closure_id"])
            else:
                # partial closure still counts as affecting path (but not forbidden)
                affected_closure_ids.add(cl["closure_id"])
        # For path-finding, treat forbidden set
        dist_map, prev = dijkstra(src, forbidden)
        path = reconstruct(prev, src, tgt)
        result_status = "no_path_found"
        optimal_path = []
        path_distance = 0
        path_quality = 0.0
        travel_time_est = 0
        affected_closures = sorted(list(affected_closure_ids))
        alternative_paths_out = []
        if path:
            result_status = "success"
            optimal_path = path
            path_distance = int(sum(edge_attrs(next(eid for nb,eid in adj[path[i]] if nb==path[i+1]))[0]) if False else 0)  # placeholder to be replaced
            # compute path distance properly
            pd = 0
            congestion_sum = 0
            traffic_sum = 0
            affected_segments = 0
            closed_intersections_on_path = 0
            total_closure_duration = 0
            baseline_delay_sum = 0
            travel_time_minutes = 0.0
            for i in range(len(path)-1):
                a = path[i]; b = path[i+1]
                eid = None
                for nb, eid_candidate in adj[a]:
                    if nb == b:
                        eid = eid_candidate; break
                sl, td, cw, msl = edge_attrs(eid)
                pd += sl
                congestion_sum += cw
                traffic_sum += td
                # affected segment if connects to any closed intersection
                if a in affected_closure_ids or b in affected_closure_ids or a in forbidden or b in forbidden:
                    affected_segments += 1
                # travel time: segment_length/km / speed *60
                travel_time_minutes += (sl/1000.0)/msl*60.0
                # baseline delay at node a (count each node's baseline once)
                baseline_delay_sum += inter_map[a]["baseline_delay"]
            # add baseline for last node
            baseline_delay_sum += inter_map[path[-1]]["baseline_delay"]
            travel_time_minutes += baseline_delay_sum/60.0
            # closure counts and durations
            closed_on_path = set()
            total_closure_duration = 0
            for cl in active:
                if cl["affected_intersection"] in path:
                    closed_on_path.add(cl["closure_id"])
                    total_closure_duration += (cl["end_time"] - cl["start_time"])
                    # mark high impact if intersection critical
                    if degrees[cl["affected_intersection"]] > 4:
                        high_impact_closures.add(cl["closure_id"])
            closed_intersections_on_path = len(closed_on_path)
            avg_traffic = traffic_sum / max(1, len(path)-1)
            # detour complexity
            direct_shortest = shortest_cache[src].get(tgt, float('inf'))
            detour_complexity = (pd - direct_shortest) * 10 if direct_shortest!=float('inf') else 0
            # closure penalty
            closure_penalty = (closed_intersections_on_path * 100) + (total_closure_duration * 0.5)
            # adjust for critical intersections multiplier
            multiplier = 1.0
            for node in path:
                if degrees[node] > 4:
                    multiplier = 1.5
                    break
            closure_penalty *= multiplier
            affected_segments_adj = affected_segments
            traffic_impact_factor = avg_traffic * 25
            congestion_level = congestion_sum
            alternative_routes_count = 0  # fill after computing alternatives
            # Path quality score formula
            path_quality = pd + (closure_penalty * affected_segments_adj) + (traffic_impact_factor * congestion_level) + (detour_complexity * alternative_routes_count)
            path_distance = int(pd)
            travel_time_est = int(round(travel_time_minutes))
            affected_closures = sorted(list(closed_on_path))
            # alternatives
            alt_paths = k_shortest_paths(src, tgt, max_alt, forbidden)
            alt_structs = []
            for ap in alt_paths:
                if ap == path:
                    continue
                # compute distance and score
                apd = 0
                ac_sum = 0
                at_sum = 0
                a_cong = 0
                for i in range(len(ap)-1):
                    a = ap[i]; b = ap[i+1]
                    eid = None
                    for nb,eid_candidate in adj[a]:
                        if nb==b:
                            eid = eid_candidate; break
                    sl, td, cw, msl = edge_attrs(eid)
                    apd += sl
                    at_sum += td
                    a_cong += cw
                avg_t = at_sum / max(1, len(ap)-1) if len(ap)>1 else 0
                detour_factor = round(apd / max(1, path_distance), 2) if path_distance>0 else 1.0
                detour_cx = (apd - direct_shortest) * 10 if direct_shortest!=float('inf') else 0
                closure_pen = closure_penalty  # approximate same
                traffic_imp = (avg_t * 25) * a_cong
                quality = apd + (closure_pen * affected_segments_adj) + traffic_imp + detour_cx * 1
                alt_structs.append({
                    "path_intersections": ap,
                    "path_distance": int(apd),
                    "quality_score": float(quality),
                    "detour_factor": float(round(detour_factor,2))
                })
                alternative_routes_count += 1
            # update path quality with actual alternative count
            path_quality = pd + (closure_penalty * affected_segments_adj) + (traffic_impact_factor * congestion_level) + (detour_complexity * alternative_routes_count)
            alternative_paths_out = alt_structs
            total_detour_distance += sum(a["path_distance"] - path_distance for a in alt_structs if a["path_distance"]>path_distance)
        else:
            result_status = "no_path_found"
            optimal_path = []
            path_distance = 0
            path_quality = 0.0
            travel_time_est = 0
            alternative_paths_out = []
        # status adjustments
        if result_status=="success" and len(alternative_paths_out) < max(0, q.get("max_alternative_paths",0)):
            # if fewer alternatives than requested, mark insufficient if required
            if qtype=="alternative_routes" and len(alternative_paths_out) < q.get("max_alternative_paths",0):
                result_status = "insufficient_alternatives"
        query_results.append({
            "query_id": qid,
            "query_type": qtype,
            "result_status": result_status,
            "optimal_path": optimal_path,
            "path_distance": int(path_distance),
            "path_quality_score": float(path_quality),
            "travel_time_estimate": int(travel_time_est),
            "affected_closures": affected_closures,
            "alternative_paths": alternative_paths_out
        })
    # network analysis: simple metrics
    # total_connectivity_score: fraction of pairs reachable (here fully connected -> 1.0)
    n = len(inter_map)
    total_pairs = n*(n-1)/2 if n>1 else 1
    reachable_pairs = total_pairs  # since connected
    total_connectivity_score = 1.0 if total_pairs>0 else 0.0
    # cluster connectivity matrix (1-10 clusters but only include used clusters)
    clusters = sorted(set(inter["neighborhood_cluster"] for inter in inter_map.values()))
    idx = {c:i for i,c in enumerate(clusters)}
    m = len(clusters)
    matrix = [[0.0]*m for _ in range(m)]
    # simplistic: clusters connected if any inter from cluster connects to any in other cluster
    cluster_nodes = defaultdict(list)
    for iid, inter in inter_map.items():
        cluster_nodes[inter["neighborhood_cluster"]].append(iid)
    for i,c1 in enumerate(clusters):
        for j,c2 in enumerate(clusters):
            if c1==c2:
                matrix[i][j]=1.0
            else:
                connected = False
                for a in cluster_nodes[c1]:
                    for b in cluster_nodes[c2]:
                        if shortest_cache[a].get(b,float('inf'))<float('inf'):
                            connected = True; break
                    if connected: break
                matrix[i][j]=1.0 if connected else 0.0
    closure_impact_summary = {
        "high_impact_clos