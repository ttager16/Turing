def multi_stage_adaptive_filter(  
    channels: List[float],  
    edges: List[List[int]],  
    threshold_updates: List[List[float]],  
    max_latency_ms: float  
) -> List[float]:
    start_time = time.time()
    n = len(channels)
    # Defensive copy
    ch = [float(x) if x is not None else float('nan') for x in channels]
    # Normalize invalid readings
    for i in range(n):
        v = ch[i]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            ch[i] = 0.0
        elif v == float('inf') or v == float('-inf'):
            # saturate to a large finite value
            ch[i] = 1e6 if v > 0 else 0.0
        elif v < 0:
            ch[i] = 0.0

    # Build initial thresholds default to 1.0 if not set
    thresholds = [1.0] * n

    # Segment tree for range updates (stores latest timestamped threshold)
    size = 1
    while size < n:
        size <<= 1
    seg_val = [None] * (2 * size)  # store threshold
    seg_time = [ -1.0 ] * (2 * size)  # store timestamp order

    def seg_apply(pos: int, val: float, t: float):
        if seg_time[pos] <= t:
            seg_time[pos] = t
            seg_val[pos] = val

    def seg_push(pos: int):
        for h in range((size).bit_length(), 0, -1):
            i = pos >> h
            if i <= 0:
                continue
            if seg_val[i] is not None:
                seg_apply(i*2, seg_val[i], seg_time[i])
                seg_apply(i*2+1, seg_val[i], seg_time[i])
                seg_val[i] = None

    def seg_range_update(l: int, r: int, val: float, t: float):
        if l > r:
            l, r = r, l
        l = max(0, l)
        r = min(n-1, r)
        if l > r:
            return
        l += size
        r += size
        l0, r0 = l, r
        while l <= r:
            if (l & 1) == 1:
                seg_apply(l, val, t)
                l += 1
            if (r & 1) == 0:
                seg_apply(r, val, t)
                r -= 1
            l >>= 1; r >>= 1
        # no immediate push for lazy propagation

    def seg_point_update(idx: int, val: float, t: float):
        if idx < 0 or idx >= n:
            return
        i = idx + size
        seg_apply(i, val, t)
        # propagate up: update parents' time if newer
        i >>= 1
        while i:
            # parent holds no aggregated value; keep as None
            i >>= 1

    # Apply threshold updates in sequence; most recent wins -> timestamp order
    t_counter = 0.0
    for upd in threshold_updates:
        t_counter += 1.0
        if not isinstance(upd, list) or len(upd) < 2:
            logging.warning("Malformed update ignored: %s", upd)
            continue
        try:
            if len(upd) == 2:
                idx = int(upd[0])
                thr = float(upd[1])
                if 0 <= idx < n:
                    seg_point_update(idx, thr, t_counter)
                else:
                    # out-of-bounds ignored
                    continue
            elif len(upd) >= 3:
                a = int(upd[0]); b = int(upd[1]); thr = float(upd[2])
                seg_range_update(a, b, thr, t_counter)
            else:
                logging.warning("Malformed update ignored: %s", upd)
        except Exception:
            logging.warning("Malformed update ignored: %s", upd)
            continue

    # Materialize thresholds from segment tree
    for i in range(n):
        pos = i + size
        # push all from root to leaf
        seg_push(pos)
        if seg_val[pos] is not None:
            thresholds[i] = float(seg_val[pos])

    # Build directed graph
    adj_out: List[List[int]] = [[] for _ in range(n)]
    adj_in: List[List[int]] = [[] for _ in range(n)]
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) < 2:
            continue
        try:
            u = int(e[0]); v = int(e[1])
        except Exception:
            continue
        if 0 <= u < n and 0 <= v < n:
            adj_out[u].append(v)
            adj_in[v].append(u)
        else:
            # silently ignore out-of-bounds
            continue

    # Active mask initial: those meeting or exceeding threshold are kept
    active = [False] * n
    ratio = [0.0] * n
    for i in range(n):
        thr = thresholds[i]
        mq = ch[i]
        if thr == 0.0:
            # avoid divide by zero: if measured > 0 keep large ratio
            r = float('inf') if mq > 0 else 0.0
        else:
            r = mq / thr
        ratio[i] = r
        if r >= 1.0:
            active[i] = True

    # Helper: compute SCCs using Kosaraju
    visited = [False]*n
    order = []
    def dfs1(u):
        visited[u]=True
        for v in adj_out[u]:
            if 0<=v<n and not visited[v]:
                dfs1(v)
        order.append(u)
    for i in range(n):
        if not visited[i]:
            dfs1(i)
    comp = [-1]*n
    visited2 = [False]*n
    radj = adj_in
    def dfs2(u, cid):
        comp[u]=cid
        visited2[u]=True
        for v in radj[u]:
            if 0<=v<n and not visited2[v]:
                dfs2(v, cid)
    cid=0
    for u in reversed(order):
        if not visited2[u]:
            dfs2(u, cid)
            cid+=1

    # Bridge detection on undirected representation for node-bridge effect:
    # We'll treat removal of a node and see if component count increases.
    # For efficiency, compute articulation points using undirected graph
    und = [[] for _ in range(n)]
    for u in range(n):
        for v in adj_out[u]:
            if 0<=v<n:
                und[u].append(v)
                und[v].append(u)
    disc = [-1]*n
    low = [0]*n
    time_dfs = 0
    ap = [False]*n

    def ap_dfs(u, parent):
        nonlocal time_dfs
        children = 0
        disc[u] = time_dfs
        low[u] = time_dfs
        time_dfs += 1
        for v in und[u]:
            if disc[v] == -1:
                children += 1
                ap_dfs(v, u)
                low[u] = min(low[u], low[v])
                if parent != -1 and low[v] >= disc[u]:
                    ap[u] = True
            elif v != parent:
                low[u] = min(low[u], disc[v])
        if parent == -1 and children > 1:
            ap[u] = True

    for i in range(n):
        if disc[i] == -1:
            ap_dfs(i, -1)

    # Detect cycles (ring topologies) using simple DFS to flag nodes in any cycle
    in_cycle = [False]*n
    color = [0]*n
    def cycle_dfs(u):
        color[u]=1
        for v in adj_out[u]:
            if not (0<=v<n): continue
            if color[v]==0:
                cycle_dfs(v)
            elif color[v]==1:
                # back edge found -> mark cycle nodes by traversal (simple marking)
                in_cycle[v]=True
                # propagate mark up current path
        color[u]=2
    for i in range(n):
        if color[i]==0:
            cycle_dfs(i)
    # Also mark nodes with indegree>0 and outdegree>0 in strongly connected comps size>1 as ring-like
    comp_size = [0]*cid
    for i in range(n):
        if comp[i]>=0:
            comp_size[comp[i]]+=1
    for i in range(n):
        if comp_size[comp[i]]>1 and len(adj_in[i])>0 and len(adj_out[i])>0:
            in_cycle[i]=True

    # Now evaluate rules in priority order for each node not already active
    result = [0.0]*n
    # Precompute neighbor active counts (use active initial set of >=1.0)
    for i in range(n):
        if active[i]:
            result[i] = ch[i]
    def count_active_out(u):
        return sum(1 for v in adj_out[u] if 0<=v<n and active[v])
    def count_active_in(u):
        return sum(1 for v in adj_in[u] if 0<=v<n and active[v])

    for i in range(n):
        if active[i]:
            continue
        r = ratio[i]
        thr = thresholds[i]
        # Bridge channels preserved if ratio between 0.81 and 0.82 and is articulation point
        if 0.81 <= r <= 0.82 and ap[i]:
            active[i]=True
            result[i]=ch[i]
            continue
        # Critical junction channels: in_cycle and ratio between 0.79 and 0.81 AND connecting to >=2 active neighbors
        if 0.79 <= r <= 0.81 and in_cycle[i]:
            neigh = 0
            neigh += count_active_in(i)
            neigh += count_active_out(i)
            if neigh >= 2:
                active[i]=True
                result[i]=ch[i]
                continue
        # Source channels: no incoming connections with ratio >0.85 and feeding at least 1 active downstream
        if len(adj_in[i])==0 and r > 0.85:
            if count_active_out(i) >= 1:
                active[i]=True
                result[i]=ch[i]
                continue
        # Sink channels: no outgoing connections, ratio between 0.75 and 0.78 and receiving from at least 3 active sources
        if len(adj_out[i])==0 and 0.75 <= r <= 0.78:
            if count_active_in(i) >= 3:
                active[i]=True
                result[i]=ch[i]
                continue
        # Otherwise suppressed
        result[i]=0.0

    # Final pass: ensure channels meeting/exceeding threshold are preserved (already handled), but ensure bridge rules may rely on status
    for i in range(n):
        if ratio[i] >= 1.0:
            result[i]=ch[i]

    # Performance logging
    elapsed_ms = (time.time() - start_time)*1000.0
    if elapsed_ms > max_latency_ms:
        logging.warning("Processing time %.2fms exceeded budget %.2fms", elapsed_ms, max_latency_ms)
    return result