def detect_anomalies(transaction_data: List[Dict[str, Any]], 
                     historical_data: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    # Validation helpers
    def valid_cid(cid):
        return isinstance(cid, str) and cid != "" and all(ch.isupper() or ch.isdigit() for ch in cid)
    def valid_amount(a):
        return (isinstance(a, (int, float)) and not isinstance(a, bool)) and a > 0
    def valid_timestamp(t):
        return isinstance(t, int) and t > 0
    def validate_tx(tx, is_hist=False):
        if not isinstance(tx, dict):
            return False
        keys = {'customer_id', 'amount', 'location', 'timestamp', 'linked_accounts'}
        if set(tx.keys()) != keys:
            return False
        if not valid_cid(tx['customer_id']): return False
        if not valid_amount(tx['amount']): return False
        if not valid_timestamp(tx['timestamp']): return False
        if not isinstance(tx['linked_accounts'], list): return False
        if is_hist:
            if len(tx['linked_accounts']) not in (0,1): return False
            if len(tx['linked_accounts'])==1 and not valid_cid(tx['linked_accounts'][0]): return False
        else:
            if len(tx['linked_accounts']) != 1: return False
            if not valid_cid(tx['linked_accounts'][0]): return False
        return True

    # Input presence
    if not transaction_data:
        return []
    if not isinstance(transaction_data, list):
        return []
    for tx in transaction_data:
        if not validate_tx(tx, is_hist=False):
            return []
    if not isinstance(historical_data, dict):
        return []
    for k,v in historical_data.items():
        if not valid_cid(k): return []
        if not isinstance(v, list):
            return []
        for tx in v:
            if not validate_tx(tx, is_hist=True):
                return []

    # Build set of all nodes
    nodes = set()
    for tx in transaction_data:
        nodes.add(tx['customer_id'])
        nodes.add(tx['linked_accounts'][0])
    for cust, txs in historical_data.items():
        nodes.add(cust)
        for tx in txs:
            if tx['linked_accounts']:
                nodes.add(tx['linked_accounts'][0])

    # Build directed graph including historical edges (optionally all)
    graph = defaultdict(list)  # adjacency list u -> [v,...]
    # Include historical edges
    for cust, txs in historical_data.items():
        for tx in txs:
            if tx['linked_accounts']:
                v = tx['linked_accounts'][0]
                graph[cust].append(v)
    # Include new batch edges
    for tx in transaction_data:
        u = tx['customer_id']; v = tx['linked_accounts'][0]
        graph[u].append(v)

    # Prepare historical statistics: amounts list and timestamps for rate
    hist_amounts = {}
    hist_timestamps = {}
    for cust, txs in historical_data.items():
        amt_list = []
        ts_list = []
        for tx in txs:
            amt_list.append(float(tx['amount']))
            ts_list.append(int(tx['timestamp']))
        if amt_list:
            hist_amounts[cust] = sorted(amt_list)
        else:
            hist_amounts[cust] = []
        hist_timestamps[cust] = sorted(ts_list)

    # Helper stats
    def median(sorted_list):
        n = len(sorted_list)
        if n==0: return None
        mid = n//2
        if n%2==1:
            return sorted_list[mid]
        return 0.5*(sorted_list[mid-1]+sorted_list[mid])
    def mad(sorted_list, med):
        # median absolute deviation
        devs = sorted([abs(x - med) for x in sorted_list])
        return median(devs) if devs else 0.0

    # Precompute medians and MADs for customers with >=2 history
    stats = {}
    for cust, arr in hist_amounts.items():
        if len(arr) >= 2:
            m = median(arr)
            md = mad(arr, m)
            stats[cust] = (m, md)
    # Precompute average hourly rate over 7-day historical window:
    # For simplicity, compute average transactions per hour over the full historical timestamps span capped at 7 days.
    avg_rate = {}
    SEVEN_DAYS = 7*24*3600
    for cust, ts_list in hist_timestamps.items():
        if not ts_list:
            avg_rate[cust] = 0.0
            continue
        # consider only last 7 days relative to max timestamp
        max_t = ts_list[-1]
        cutoff = max_t - SEVEN_DAYS
        relevant = [t for t in ts_list if t >= cutoff]
        span = max_t - (relevant[0] if relevant else max_t)
        span = max(span, 3600)  # at least 1 hour to avoid div 0
        hours = span / 3600.0
        avg_rate[cust] = len(relevant) / hours if hours>0 else float(len(relevant))

    # Union-Find over nodes for pruning
    parent = {}
    rank = {}
    def make_set(x):
        parent[x]=x; rank[x]=0
    for n in nodes:
        make_set(n)
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra==rb: return
        if rank[ra] < rank[rb]:
            parent[ra]=rb
        else:
            parent[rb]=ra
            if rank[ra]==rank[rb]:
                rank[ra]+=1

    # Union edges from historical and new to form undirected connectivity for pruning
    for u, vs in graph.items():
        for v in vs:
            if u in parent and v in parent:
                union(u,v)

    # Cycle detection BFS bounded to K=3 hops (i.e., path length <=3 from v to u)
    K = 3
    def has_short_cycle(u,v):
        # if u and v not in same component, skip
        if find(u) != find(v):
            return False
        # BFS from v up to depth K to find u
        q = deque()
        q.append((v,0))
        visited = {v}
        while q:
            node, d = q.popleft()
            if d> K: 
                continue
            if node == u and d>0:
                return True
            if d==K:
                continue
            for nb in graph.get(node,()):
                if nb not in visited:
                    visited.add(nb)
                    q.append((nb,d+1))
        return False

    # High-frequency burst: compare count in 1-hour window around the tx timestamp vs historical avg_rate
    def is_burst(cust, tx_timestamp):
        # compute number of transactions in [ts-1800, ts+1800] among new batch + historical? Requirement: "customer performs more transactions within a short window compared to 7-day historical average"
        # We'll count transactions from both historical (within last 7 days) and new batch timestamps.
        window_start = tx_timestamp - 3600//2
        window_end = tx_timestamp + 3600//2
        # collect histories within last 7 days relative to tx_timestamp
        hist_ts = hist_timestamps.get(cust, [])
        count = 0
        for t in hist_ts:
            if window_start <= t <= window_end:
                count += 1
        # include new batch transactions by same cust in that window
        for tx in transaction_data:
            if tx['customer_id']==cust and window_start <= tx['timestamp'] <= window_end:
                count += 1
        # expected count = avg_rate[cust] * 1 hour
        expected = avg_rate.get(cust,0.0) * 1.0
        # If expected very small, set threshold minimally to avoid false positives: require count >=3 when expected <1
        if expected < 1.0:
            return count >= 3
        # flag if count > 3x expected
        return count > 3.0 * expected

    results = []
    for tx in transaction_data:
        u = tx['customer_id']
        amt = float(tx['amount'])
        ts = int(tx['timestamp'])
        v = tx['linked_accounts'][0]
        anomaly = False
        # Amount outlier
        if u in stats:
            med, md = stats[u]
            threshold = med + 3.5 * (1.4826 * md)
            if amt > threshold:
                anomaly = True
        # Cycle detection using DSU pruning
        if not anomaly:
            try:
                if has_short_cycle(u,v):
                    anomaly = True
            except Exception:
                pass
        # High-frequency burst
        if not anomaly:
            if is_burst(u, ts):
                anomaly = True
        results.append({'customer_id': u, 'anomaly': bool(anomaly)})
    return results