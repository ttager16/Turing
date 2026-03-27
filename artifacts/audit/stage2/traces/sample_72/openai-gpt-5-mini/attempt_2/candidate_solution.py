def detect_anomalies(transaction_data: List[Dict[str, Any]], 
                     historical_data: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    # Validation helpers
    def valid_cid(cid):
        return isinstance(cid, str) and cid != "" and all(c.isupper() or c.isdigit() for c in cid)
    def valid_amount(a):
        return (isinstance(a, (int, float)) and a > 0)
    def valid_timestamp(t):
        return isinstance(t, int) and t > 0
    # Basic input presence
    if not transaction_data:
        return []
    if not isinstance(transaction_data, list) or not isinstance(historical_data, dict):
        return []
    # Validate transaction_data schema
    for tx in transaction_data:
        if not isinstance(tx, dict):
            return []
        required = {'customer_id','amount','location','timestamp','linked_accounts'}
        if set(tx.keys()) != required:
            return []
        cid = tx['customer_id']
        if not valid_cid(cid):
            return []
        if not valid_amount(tx['amount']):
            return []
        if not valid_timestamp(tx['timestamp']):
            return []
        la = tx['linked_accounts']
        if not isinstance(la, list) or len(la) != 1:
            return []
        if not valid_cid(la[0]):
            return []
    # Validate historical_data schema
    for k, v in historical_data.items():
        if not valid_cid(k):
            return []
        if not isinstance(v, list):
            return []
        for tx in v:
            if not isinstance(tx, dict):
                return []
            req = {'amount','location','timestamp','linked_accounts'}
            if set(tx.keys()) != req:
                return []
            if not valid_amount(tx['amount']):
                return []
            if not valid_timestamp(tx['timestamp']):
                return []
            la = tx['linked_accounts']
            if not isinstance(la, list) or not (len(la) == 0 or len(la) == 1):
                return []
            if len(la) == 1 and not valid_cid(la[0]):
                return []

    # Build graph: nodes from all customer_ids in transactions and historical edges (if any)
    graph = defaultdict(list)  # directed edges u -> v
    nodes = set()
    # Add new batch edges
    for tx in transaction_data:
        u = tx['customer_id']
        v = tx['linked_accounts'][0]
        nodes.add(u); nodes.add(v)
        graph[u].append(v)
        if v not in graph:
            graph.setdefault(v, [])
    # Optionally include historical edges relevant: include edges where either endpoint appears in batch
    batch_nodes = set(nodes)
    for cid, hist in historical_data.items():
        # include historical entries only if cid in batch_nodes or their linked account in batch_nodes
        for tx in hist:
            la = tx['linked_accounts']
            if len(la) == 1:
                u = cid
                v = la[0]
                if u in batch_nodes or v in batch_nodes:
                    nodes.add(u); nodes.add(v)
                    graph[u].append(v)
                    if v not in graph:
                        graph.setdefault(v, [])

    # Union-Find DSU
    parent = {}
    rank = {}
    def make_set(x):
        if x not in parent:
            parent[x] = x
            rank[x] = 0
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        rx = find(x); ry = find(y)
        if rx == ry:
            return
        if rank[rx] < rank[ry]:
            parent[rx] = ry
        else:
            parent[ry] = rx
            if rank[rx] == rank[ry]:
                rank[rx] += 1

    for n in nodes:
        make_set(n)
    for u in graph:
        for v in graph[u]:
            union(u, v)

    # Historical stats: median and MAD, and 7-day historical avg rate (transactions per hour)
    hist_amounts = {}
    hist_timestamps = {}
    for cid in nodes:
        hist_amounts[cid] = []
        hist_timestamps[cid] = []
    for cid, hist in historical_data.items():
        for tx in hist:
            if cid in hist_amounts:
                hist_amounts[cid].append(float(tx['amount']))
                hist_timestamps[cid].append(int(tx['timestamp']))

    def median(lst):
        s = sorted(lst)
        n = len(s)
        if n == 0:
            return None
        mid = n // 2
        if n % 2 == 1:
            return s[mid]
        return (s[mid-1] + s[mid]) / 2.0

    def mad(lst, med):
        diffs = [abs(x - med) for x in lst]
        return median(diffs) if diffs else 0.0

    stats = {}
    for cid in nodes:
        amts = hist_amounts.get(cid, [])
        if len(amts) >= 2:
            med = median(amts)
            m = mad(amts, med)
            stats[cid] = {'median': med, 'mad': m}
        else:
            stats[cid] = None
    # Historical rate: compute average transactions per hour over last 7 days in historical timestamps if any
    rates = {}
    SEVEN_DAYS = 7 * 24 * 3600
    for cid in nodes:
        ts = sorted(hist_timestamps.get(cid, []))
        if not ts:
            rates[cid] = 0.0
            continue
        latest = ts[-1]
        window_start = latest - SEVEN_DAYS
        count = sum(1 for t in ts if t >= window_start)
        # average per hour
        rates[cid] = count / (7 * 24.0)

    # For burst detection: for each sender, count transactions in 1-hour window in the batch and compare to historical average per hour
    # Prepare batch timestamps per customer
    batch_times = defaultdict(list)
    for tx in transaction_data:
        batch_times[tx['customer_id']].append(tx['timestamp'])
    # For each transaction, evaluate rules
    results = []
    K = 3  # hops
    # Precompute adjacency for BFS (graph)
    for tx in transaction_data:
        u = tx['customer_id']
        v = tx['linked_accounts'][0]
        anomaly = False
        # Amount outlier
        if historical_data:
            stat = stats.get(u)
            if stat is not None:
                med = stat['median']; m = stat['mad']
                thresh = med + 3.5 * (1.4826 * m)
                if float(tx['amount']) > thresh:
                    anomaly = True
        # Cycle detection using DSU: only search if u and v in same DSU component
        if u in parent and v in parent and find(u) == find(v):
            # BFS from v up to depth K to see if can reach u within <=K hops
            visited = set([v])
            dq = deque()
            dq.append((v,0))
            found_cycle = False
            while dq:
                curr, depth = dq.popleft()
                if depth > K:
                    continue
                if curr == u and depth > 0:
                    found_cycle = True
                    break
                if depth == K:
                    continue
                for nei in graph.get(curr, []):
                    if nei not in visited:
                        visited.add(nei)
                        dq.append((nei, depth+1))
            if found_cycle:
                anomaly = True
        # High-frequency bursts: compare count in any 1-hour window in batch for u to 7-day historical avg per hour * factor
        times = sorted(batch_times.get(u, []))
        burst = False
        if times:
            # sliding window count within 3600 seconds
            left = 0
            maxcount = 0
            for right in range(len(times)):
                while times[right] - times[left] > 3600:
                    left += 1
                maxcount = max(maxcount, right - left + 1)
            hist_rate_per_hour = rates.get(u, 0.0)
            # if historical rate is zero, but there are multiple in hour, consider burst if more than 3 in hour
            threshold_count = max(3, math.ceil(hist_rate_per_hour * 1.0 * 3))  # heuristic: 3x historical hourly rate, at least 3
            if maxcount > threshold_count:
                burst = True
        if burst:
            anomaly = True
        results.append({'customer_id': u, 'anomaly': bool(anomaly)})
    return results