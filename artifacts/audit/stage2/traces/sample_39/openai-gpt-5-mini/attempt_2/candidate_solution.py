def __init__(self, capacity=1000):
        self.capacity = max(1, capacity)
        # we'll bucket amounts into fixed buckets up to some dynamic max
        self.bucket_count = 256
        self.max_val = 1000000.0
        self.buckets = [0] * self.bucket_count
        self.total = 0

    def _bucket_index(self, x):
        if x < 0:
            x = 0.0
        frac = min(1.0, x / self.max_val)
        idx = int(frac * (self.bucket_count - 1))
        return idx

    def insert(self, x):
        # expand max_val if necessary
        if x > self.max_val:
            while x > self.max_val:
                self.max_val *= 2
            # re-bucket all not tracked individually; to keep deterministic non-decreasing,
            # we do nothing to previous counts (they remain in relative lower buckets).
        idx = self._bucket_index(x)
        self.buckets[idx] += 1
        self.total += 1

    def approx_percentile_upper(self, p):  # p in [0,1], return upper-bound estimate non-decreasing
        if self.total == 0:
            return 0.0
        target = p * self.total
        cum = 0
        for i, c in enumerate(self.buckets):
            cum += c
            if cum >= target:
                # return upper bound of bucket
                frac = (i + 1) / self.bucket_count
                return frac * self.max_val
        return self.max_val

def detect_fraudulent_activity(transaction_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not transaction_data:
        return []

    # preserve original order mapping
    id_to_idx = {t.get("transaction_id", str(i)): i for i, t in enumerate(transaction_data)}

    # Node stats
    node_tx_count = defaultdict(int)
    node_cum_amount = defaultdict(float)
    node_regions = defaultdict(set)
    node_connected = defaultdict(set)
    node_account_type = dict()  # last known account type
    # For temporal checks: maintain last outgoing and last incoming timestamps per node with amounts
    last_outgoing = defaultdict(lambda: None)
    last_incoming = defaultdict(lambda: None)
    incoming_history = defaultdict(list)  # list of (timestamp, amount)

    # Graph edges: adjacency list with edge objects in order
    edges = []  # list of dicts representing edges
    adj = defaultdict(list)
    rev_adj = defaultdict(list)

    # Segment tree for amounts
    st = SegmentTree(capacity=1000)

    # First pass: ingest transactions, build nodes and simple stats, insert amounts into segment tree
    for t in transaction_data:
        txid = t.get("transaction_id")
        sender = t.get("sender")
        receiver = t.get("receiver")
        amount = float(t.get("amount", 0.0))
        ts = int(t.get("timestamp", 0))
        region = t.get("region")
        acct_type = (t.get("account_type") or "unknown").lower()

        # assign account types if not present
        if sender not in node_account_type:
            node_account_type[sender] = acct_type
        else:
            # prefer explicit known types earlier; keep existing if not unknown
            if node_account_type[sender] == "unknown" and acct_type != "unknown":
                node_account_type[sender] = acct_type

        if receiver not in node_account_type:
            node_account_type[receiver] = acct_type
        else:
            if node_account_type[receiver] == "unknown" and acct_type != "unknown":
                node_account_type[receiver] = acct_type

        node_tx_count[sender] += 1
        node_tx_count[receiver] += 0  # receiving not counted toward 'transaction_count' per sender? But include both sides: specification counts per account; we'll count both roles
        node_tx_count[receiver] += 1

        node_cum_amount[sender] += amount
        node_cum_amount[receiver] += amount

        if region is not None:
            node_regions[sender].add(region)
            node_regions[receiver].add(region)

        node_connected[sender].add(receiver)
        node_connected[receiver].add(sender)

        # temporal histories
        incoming_history[receiver].append((ts, amount))
        last_incoming[receiver] = ts
        last_outgoing[sender] = ts

        # graph edge
        edge = {
            "txid": txid,
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "timestamp": ts,
            "region": region,
            "account_type": acct_type,
            "index": len(edges),
            "original": t
        }
        edges.append(edge)
        adj[sender].append(edge)
        rev_adj[receiver].append(edge)

        # insert into segment tree
        st.insert(amount)

    # compute approximate percentiles
    P90_est = st.approx_percentile_upper(0.90)
    P85_est = st.approx_percentile_upper(0.85)
    # Account-type risk thresholds
    acct_type_risk_threshold = 0.8 * P90_est

    # Compute node SI
    node_SI = {}
    for node in set(list(node_tx_count.keys()) + list(node_cum_amount.keys())):
        SI = 0.0
        if node_tx_count.get(node, 0) > 10:
            SI += 0.30
        if node_cum_amount.get(node, 0.0) > 50000.0:
            SI += 0.40
        if len(node_regions.get(node, set())) > 2:
            SI += 0.20
        if len(node_connected.get(node, set())) > 5:
            SI += 0.10
        atype = (node_account_type.get(node) or "unknown").lower()
        if atype in ("business", "corporate"):
            SI += 0.05
        if atype == "new":
            SI += 0.15
        node_SI[node] = min(1.0, SI)

    # Edge suspiciousness S per formula
    edge_S = [0.0] * len(edges)
    flagged_by_detector = [False] * len(edges)  # additional detectors may flag independently
    for i, e in enumerate(edges):
        S = 0.0
        amt = e["amount"]
        sender = e["sender"]
        receiver = e["receiver"]
        ts = e["timestamp"]
        region = e["region"]
        acct_type = e["account_type"]

        if amt > 15000:
            S += 0.40
        if amt > max(P90_est, 5000.0):
            S += 0.30
        # cross-region: region not in sender's regions (sender's regions collected)
        sender_regions = node_regions.get(sender, set())
        if region is not None and region not in sender_regions and amt > 2000.0:
            S += 0.20
        # time gap since sender's last: find previous outgoing timestamp before this tx for sender
        # We'll approximate by looking at last outgoing earlier than this tx:
        prev_out_ts = None
        for oe in adj[sender]:
            if oe["timestamp"] < ts and oe["txid"] != e["txid"]:
                if prev_out_ts is None or oe["timestamp"] > prev_out_ts:
                    prev_out_ts = oe["timestamp"]
        if prev_out_ts is not None and (ts - prev_out_ts) < 180 and amt > 1000.0:
            S += 0.30
        # sender.SI >0.5 and receiver.SI >0.5 and amount >2000
        if node_SI.get(sender, 0.0) > 0.5 and node_SI.get(receiver, 0.0) > 0.5 and amt > 2000.0:
            S += 0.40
        if acct_type in ("new", "business") and amt > 5000.0:
            S += 0.20

        edge_S[i] = min(1.0, S)

        # Independent detectors:
        # High-value general flag
        if amt > 10000.0:
            flagged_by_detector[i] = True
        # Outliers approx (85th) and minimum 5000
        if amt > max(5000.0, P85_est):
            flagged_by_detector[i] = True
        # Temporal anomalies: gap <60s for amounts >2000
        # check if sender had incoming to sender recently (i.e., this is outgoing after incoming)
        # If this tx occurs within 60s after an incoming to sender and amt>2000 => temporal anomaly
        incoming_list = incoming_history.get(sender, [])
        # find latest incoming before this tx
        latest_in_before = None
        for it, ia in incoming_list:
            if it < ts:
                if latest_in_before is None or it > latest_in_before[0]:
                    latest_in_before = (it, ia)
        if latest_in_before and (ts - latest_in_before[0]) < 60 and amt > 2000.0:
            flagged_by_detector[i] = True
        # Rapid succession: gap <180s for amounts >1000 (check between this tx and previous outgoing)
        prev_out = prev_out_ts
        if prev_out is not None and (ts - prev_out) < 180 and amt > 1000.0:
            flagged_by_detector[i] = True
        # Cross-region two-tier: signal >2000, direct flag >5000
        if region is not None and region not in sender_regions:
            if amt > 5000.0:
                flagged_by_detector[i] = True
            elif amt > 2000.0:
                # signal (we mark but not necessarily full flag)
                S = min(1.0, S + 0.05)
                edge_S[i] = S

        # chain transactions: after receiving funds, account sends outgoing where amount >5000 and exceeds at least one prior incoming
        # Check when sender had prior incoming >0 and this outgoing amt >5000 and greater than at least one prior incoming
        prior_incomings = incoming_history.get(sender, [])
        if prior_incomings:
            # find if any incoming amount less than current amount
            if amt > 5000.0 and any(ia < amt for it, ia in prior_incomings):
                flagged_by_detector[i] = True

        # extra high-amount bump
        if amt > 15000.0:
            # already added to S; flagged
            flagged_by_detector[i] = True

    # Build directed graph for SCC detection using Tarjan's algorithm
    index = {}
    lowlink = {}
    onstack = set()
    stack = []
    idx_counter = [0]
    sccs = []
    nodes = set(node_SI.keys())

    def strongconnect(v):
        index[v] = idx_counter[0]
        lowlink[v] = idx_counter[0]
        idx_counter[0] += 1
        stack.append(v)
        onstack.add(v)
        for e in adj.get(v, []):
            w = e["receiver"]
            if w not in index:
                if len(index) < 1000000:  # safe guard
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in onstack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            # start a new SCC
            comp = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in list(nodes):
        if v not in index:
            strongconnect(v)

    # Only analyze SCCs with size >1
    suspicious_edge_indices = set()
    for comp in sccs:
        if len(comp) <= 1:
            continue
        # collect edges internal to SCC
        internal_edges = []
        for u in comp:
            for e in adj.get(u, []):
                if e["receiver"] in comp:
                    internal_edges.append(e)
        # for performance, filter edges with S > 0.6
        candidate_edges = [e for e in internal_edges if edge_S[e["index"]] > 0.6]
        # DP on simple paths length <=3 within SCC
        # we'll do bounded DFS from each node up to depth 3, aggregating edge S
        visited_paths = set()
        for start in comp:
            stack2 = [ (start, [start], 0.0, []) ]  # node, path_nodes, aggregated_score, edge_indices
            while stack2:
                node, path_nodes, agg, edge_idxs = stack2.pop()
                if len(path_nodes)-1 >= 1:
                    # if path length <=3 and aggregated edge suspiciousness average > threshold, mark edges
                    if len(path_nodes)-1 <= 3:
                        # compute aggregated edge score as average of edges in path
                        if edge_idxs:
                            avgS = sum(edge_S[idx] for idx in edge_idxs) / len(edge_idxs)
                            if avgS > 0.6:
                                for idx in edge_idxs:
                                    suspicious_edge_indices.add(idx)
                if len(path_nodes)-1 >= 3:
                    continue
                for e in adj.get(node, []):
                    w = e["receiver"]
                    eid = e["index"]
                    # only traverse edges internal to comp
                    if w not in comp:
                        continue
                    if eid in edge_idxs:
                        continue
                    # avoid cycles beyond simple path
                    if w in path_nodes:
                        continue
                    new_edge_idxs = edge_idxs + [eid]
                    stack2.append((w, path_nodes + [w], agg + edge_S[eid], new_edge_idxs))

    # Final decision: gather flagged transactions preserving input order
    output = []
    seen_txids = set()
    for i, e in enumerate(edges):
        txid = e["txid"]
        original = e["original"].copy()
        # Determine if fraudulent based on combination:
        is_fraud = False
        amt = e["amount"]
        sender = e["sender"]
        receiver = e["receiver"]
        # Edge suspiciousness
        if edge_S[i] > 0.6:
            is_fraud = True
        # flagged by other detectors
        if flagged_by_detector[i]:
            is_fraud = True
        # suspicious edge in SCC DP
        if i in suspicious_edge_indices:
            is_fraud = True
        # Apply extra rules: temporal anomaly supersedes general rapid; check again with precedence
        # Check if temporal anomaly (incoming->outgoing gap<60 for amt>2000)
        incoming_list = incoming_history.get(sender, [])
        latest_in_before = None
        for it, ia in incoming_list:
            if it < e["timestamp"]:
                if latest_in_before is None or it > latest_in_before[0]:
                    latest_in_before = (it, ia)
        if latest_in_before and (e["timestamp"] - latest_in_before[0]) < 60 and amt > 2000.0:
            is_fraud = True
        else:
            # general rapid succession
            prev_out_ts = None
            for oe in adj[sender]:
                if oe["timestamp"] < e["timestamp"] and oe["txid"] != txid:
                    if prev_out_ts is None or oe["timestamp"] > prev_out_ts:
                        prev_out_ts = oe["timestamp"]
            if prev_out_ts is not None and (e["timestamp"] - prev_out_ts) < 180 and amt > 1000.0:
                is_fraud = True

        # Enforce minimum amounts to reduce false positives
        if amt < 100.0:
            is_fraud = False

        if is_fraud:
            if txid not in seen_txids:
                seen_txids.add(txid)
                original["fraudulent"] = True
                output.append(original)

    # Preserve input order: sort by original input index
    output.sort(key=lambda x: id_to_idx.get(x.get("transaction_id"), 0))
    return output