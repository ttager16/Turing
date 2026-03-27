def manage_device_logs(device_logs: List[List[Any]]) -> List[List[Any]]:
    # Δ_stale
    DELTA = 1

    # First pass: find latest timestamp per device
    latest = defaultdict(lambda: -10**18)
    for log in device_logs:
        try:
            dev, ts, _ = log
            if isinstance(ts, int):
                if ts > latest[dev]:
                    latest[dev] = ts
        except Exception:
            continue

    # Apply stale and duplicate_entry filters, preserve original order
    filtered = []
    for log in device_logs:
        if len(log) < 3:
            continue
        dev, ts, payload = log
        # duplicate_entry rule
        if payload == "duplicate_entry":
            continue
        # stale rule: if there exists newer_timestamp such that newer - ts > DELTA => stale
        if latest.get(dev, -10**18) - ts > DELTA:
            continue
        filtered.append(log)

    # Build a set of existing (device, timestamp) for reference validation
    existing = set()
    for log in filtered:
        dev, ts, _ = log
        existing.add((dev, ts))

    # Validate references: if payload matches REF_dev_ts must exist in existing, else discard
    result = []
    for log in filtered:
        dev, ts, payload = log
        m = REF_RE.match(str(payload))
        if m:
            ref_dev = m.group(1)
            try:
                ref_ts = int(m.group(2))
            except Exception:
                continue
            if (ref_dev, ref_ts) not in existing:
                # invalid reference -> discard
                continue
        result.append(log)

    # Final integrity pass: ensure no cycles of references (simple detection via graph on indices)
    # Build directed graph of indices where edge i->j if log i references log j
    index_map = {}
    for idx, log in enumerate(result):
        index_map[(log[0], log[1])] = idx

    edges = [[] for _ in result]
    for i, log in enumerate(result):
        payload = str(log[2])
        m = REF_RE.match(payload)
        if m:
            ref = (m.group(1), int(m.group(2)))
            j = index_map.get(ref)
            if j is not None:
                edges[i].append(j)

    # Detect cycles using DFS and remove any logs participating in cycles (rollback)
    visited = [0]*len(result)  # 0=unvisited,1=visiting,2=done
    in_cycle = [False]*len(result)

    def dfs(u):
        if visited[u] == 1:
            return [u]
        if visited[u] == 2:
            return []
        visited[u] = 1
        for v in edges[u]:
            cycle = dfs(v)
            if cycle:
                # mark nodes in cycle
                in_cycle[u] = True
                # propagate marking
                for node in cycle:
                    in_cycle[node] = True
                # return cycle to propagate up until full cycle closed
                if u in cycle:
                    return []
                else:
                    cycle.append(u)
                    return cycle
        visited[u] = 2
        return []

    for i in range(len(result)):
        if visited[i] == 0:
            dfs(i)

    if any(in_cycle):
        final = []
        removed_set = set()
        for i, flag in enumerate(in_cycle):
            if flag:
                removed_set.add((result[i][0], result[i][1], result[i][2]))
        # remove any logs that are part of cycles; preserve order
        for log in result:
            if (log[0], log[1], log[2]) in removed_set:
                continue
            final.append(log)
        return final

    return result