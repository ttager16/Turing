def manage_device_clusters(devices: List[List], operations: List[List]) -> List[List[int]]:
    # device info
    eff: Dict[int, float] = {}
    state: Dict[int, str] = {}  # 'active', 'standby', 'failed'
    # initialize
    for d, e in devices:
        eff[d] = float(e)
        state[d] = 'active'
    # helper to ensure device exists
    def ensure(did: int):
        if did not in eff:
            eff[did] = 0.80
            state[did] = 'active'
    # process operations sequentially
    for op in operations:
        if not op: continue
        typ = op[0]
        did = op[1] if len(op) > 1 else None
        if did is None:
            continue
        if typ == 'join':
            if did in eff:
                # if previously failed, join should add as active per edge-case? treat join as create/reactivate
                if state.get(did) == 'failed':
                    eff.setdefault(did, 0.80)
                    state[did] = 'active'
                else:
                    state[did] = 'active'
            else:
                eff[did] = 0.80
                state[did] = 'active'
        elif typ == 'fail':
            if did not in eff:
                eff[did] = 0.80
            state[did] = 'failed'
        elif typ == 'standby':
            if did not in eff:
                eff[did] = 0.80
            # only change if not failed
            if state.get(did) != 'failed':
                state[did] = 'standby'
        elif typ == 'resume':
            if did not in eff:
                eff[did] = 0.80
            if state.get(did) == 'standby':
                state[did] = 'active'
        else:
            # unknown op - ignore
            continue
    # collect active devices
    active_ids = [d for d, s in state.items() if s == 'active']
    if not active_ids:
        return []
    # separate high and low efficiency
    high: List[int] = []
    low: List[int] = []
    for d in active_ids:
        if eff.get(d, 0.80) >= 0.75:
            high.append(d)
        else:
            low.append(d)
    # Devices with efficiency <0.75 form singletons
    clusters: List[List[int]] = []
    for d in sorted(low):
        clusters.append([d])
    # For high-efficiency devices, we need to form clusters where combined average >=0.75.
    # Strategy: greedily try to merge by sorting descending efficiency and adding while average >=0.75.
    # Then any remaining singles that cannot merge stay as singletons.
    high_sorted = sorted(high, key=lambda x: (-eff.get(x,0), x))
    used: Set[int] = set()
    i = 0
    n = len(high_sorted)
    while i < n:
        if high_sorted[i] in used:
            i += 1
            continue
        # start new candidate cluster with this device
        cluster = [high_sorted[i]]
        s = eff.get(high_sorted[i], 0.8)
        cnt = 1
        used.add(high_sorted[i])
        # try to add other unused high devices in descending efficiency order
        for j in range(i+1, n):
            did = high_sorted[j]
            if did in used:
                continue
            new_s = s + eff.get(did, 0.8)
            new_cnt = cnt + 1
            if (new_s / new_cnt) >= 0.75:
                cluster.append(did)
                s = new_s
                cnt = new_cnt
                used.add(did)
        # finalize cluster sorted ascending
        clusters.append(sorted(cluster))
        i += 1
        # advance i to next unused
        while i < n and high_sorted[i] in used:
            i += 1
    # sort clusters by their minimum device_id
    clusters.sort(key=lambda c: (c[0] if c else float('inf')))
    return clusters