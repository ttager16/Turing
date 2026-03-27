def __init__(self):
        # adjacency: src -> list of (dst, amount, original_idx)
        self.adj = defaultdict(list)
        # pair stats: (src,dst) -> {'count':int,'total':float}
        self.pair_stats = defaultdict(lambda: {'count':0, 'total':0.0})
        # node set
        self.nodes = set()
        # lock for concurrent threshold updates / modifications
        self.lock = threading.RLock()
        # track edges list for cycles etc
        self.edges = []  # tuples (src,dst,amount)
        # per-node outgoing totals per currency layer
        self.layer_map = defaultdict(set)  # node -> set(layers)
        # quick map for reverse adjacency
        self.rev = defaultdict(list)

    def _extract_currency(self, account: str) -> str:
        # assume prefix letters denote currency (e.g., accountUSD1)
        m = _account_currency_re.search(account)
        if m:
            return m.group(1)
        # fallback: non-digit suffix
        letters = ''.join([c for c in account if c.isalpha()])
        return letters or 'UNK'

    def insert_transaction(self, src: str, dst: str, amount: float):
        with self.lock:
            self.nodes.add(src); self.nodes.add(dst)
            self.adj[src].append((dst, amount))
            self.rev[dst].append((src, amount))
            self.edges.append((src, dst, amount))
            pair = (src, dst)
            ps = self.pair_stats[pair]
            ps['count'] += 1
            ps['total'] += amount
            # update layer maps
            self.layer_map[src].add(self._extract_currency(src))
            self.layer_map[dst].add(self._extract_currency(dst))

    def remove_transaction(self, src: str, dst: str, amount: float):
        with self.lock:
            # best effort removal: remove first matching edge
            lst = self.adj.get(src, [])
            for i, (d,a) in enumerate(lst):
                if d==dst and a==amount:
                    lst.pop(i)
                    break
            # remove from rev
            lst2 = self.rev.get(dst, [])
            for i,(s,a) in enumerate(lst2):
                if s==src and a==amount:
                    lst2.pop(i)
                    break
            # remove from edges
            for i,(s,d,a) in enumerate(self.edges):
                if s==src and d==dst and a==amount:
                    self.edges.pop(i); break
            pair = (src,dst)
            if pair in self.pair_stats:
                ps = self.pair_stats[pair]
                ps['count'] = max(0, ps['count']-1)
                ps['total'] = max(0.0, ps['total']-amount)

    def neighbors(self, node: str):
        return [d for (d,a) in self.adj.get(node,[])]

    def get_edges_from(self, node: str):
        return list(self.adj.get(node,[]))

    def get_pair_stats(self, src: str, dst: str):
        return self.pair_stats.get((src,dst), {'count':0,'total':0.0})

    def is_cross_currency(self, src: str, dst: str) -> bool:
        return self._extract_currency(src) != self._extract_currency(dst)

def detect_anomalies(transaction_data: List[List], thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
    graph = MultiLayerGraph()
    # local copy of thresholds with lock for real-time updates
    thr_lock = threading.RLock()
    thresholds_local = dict(thresholds)

    def update_thresholds(new_thr: Dict[str, float]):
        with thr_lock:
            thresholds_local.update(new_thr)

    # Build graph incrementally
    for tx in transaction_data:
        if not tx or len(tx) < 3:
            continue
        src, dst, amount = tx[0], tx[1], float(tx[2])
        graph.insert_transaction(src, dst, amount)

    anomalies = []
    seen_pairs = set()

    # Helper: detect high volume and frequency
    with graph.lock, thr_lock:
        vol_th = float(thresholds_local.get('volume_threshold', 1000.0))
        freq_th = float(thresholds_local.get('frequency_threshold', 3))
        cross_sens = float(thresholds_local.get('cross_currency_sensitivity', 1.0))
        # effective cross threshold: volume_threshold / sensitivity (as in prompt)
        if cross_sens != 0:
            cross_th = vol_th / cross_sens
        else:
            cross_th = vol_th

        # detect pair-based anomalies
        for (src,dst), stats in list(graph.pair_stats.items()):
            if stats['count'] <= 0:
                continue
            pair_key = (src,dst)
            if pair_key in seen_pairs:
                continue
            # high frequency and high total volume
            if stats['count'] >= freq_th and stats['total'] >= vol_th:
                anomalies.append({
                    'accounts': [src, dst],
                    'amount': stats['total'],
                    'anomaly_type': 'High Volume and Frequency',
                    'flow_path': [src, dst]
                })
                seen_pairs.add(pair_key)
                continue
            # single big transaction could be detected via edges
            # check if any single edge exceeds thresholds
            for (d, amt) in graph.get_edges_from(src):
                if d != dst:
                    continue
                if graph.is_cross_currency(src, dst):
                    if amt >= cross_th:
                        anomalies.append({
                            'accounts': [src, dst],
                            'amount': amt,
                            'anomaly_type': 'Cross-Currency Flow Spike',
                            'flow_path': [src, dst]
                        })
                        seen_pairs.add(pair_key)
                        break
                else:
                    if amt >= vol_th:
                        anomalies.append({
                            'accounts': [src, dst],
                            'amount': amt,
                            'anomaly_type': 'High Volume Transaction',
                            'flow_path': [src, dst]
                        })
                        seen_pairs.add(pair_key)
                        break

    # Detect cycles using DFS; capture cycles up to reasonable length to avoid explosion
    def detect_cycles(limit_length=10):
        with graph.lock, thr_lock:
            visited = set()
            stack = []
            onstack = set()
            cycles_found = set()

            def dfs(u):
                visited.add(u)
                stack.append(u)
                onstack.add(u)
                for (v, amt) in graph.get_edges_from(u):
                    if v not in visited:
                        dfs(v)
                    elif v in onstack:
                        # cycle from v to u
                        try:
                            idx = stack.index(v)
                        except ValueError:
                            continue
                        cycle = stack[idx:] + [v]
                        if len(cycle)-1 > limit_length:
                            continue
                        # build unique representation
                        key = tuple(cycle)
                        if key in cycles_found:
                            continue
                        cycles_found.add(key)
                stack.pop()
                onstack.discard(u)

            for node in list(graph.nodes):
                if node not in visited:
                    dfs(node)
            results = []
            cycle_threshold = float(thresholds_local.get('cycle_threshold', 2000.0))
            for cyc in cycles_found:
                # cyc is like (a,b,c,a)
                path = list(cyc)
                # compute total amount along edges in cycle
                total = 0.0
                # iterate edges along path
                for i in range(len(path)-1):
                    s = path[i]; d = path[i+1]
                    # sum all amounts for that directed edge
                    stats = graph.get_pair_stats(s,d)
                    # approximate by total pair amount
                    total += stats['total']
                if total >= cycle_threshold:
                    # classify cross-currency if any edge crosses
                    is_cross = False
                    for i in range(len(path)-1):
                        if graph.is_cross_currency(path[i], path[i+1]):
                            is_cross = True; break
                    results.append((path, total, is_cross))
            return results

    cycles = detect_cycles()
    for path, total, is_cross in cycles:
        # build accounts list as start..end-1 maybe
        accounts = list(dict.fromkeys(path[:-1]))  # unique seq
        anomalies.append({
            'accounts': accounts,
            'amount': total,
            'anomaly_type': 'Suspicious Cyclical Flow',
            'flow_path': path[:-1]
        })

    # Detect self-loops and rapid back-and-forth cross-currency pairs
    with graph.lock, thr_lock:
        for (src,dst), stats in list(graph.pair_stats.items()):
            if stats['count'] <= 0:
                continue
            # self-loop where same logical account across currencies e.g., accountUSD5 and accountEUR5
            # detect by root id numeric match or identical alphanumeric except currency prefix
            def base_id(acc):
                # strip leading letters and return numeric suffix or full string
                m = _account_currency_re.search(acc)
                if m:
                    return m.group(2)
                digits = ''.join([c for c in acc if c.isdigit()])
                return digits or acc
            if base_id(src) and base_id(src) == base_id(dst) and src != dst:
                # likely same account across currencies
                # check bidirectional partner total
                rev_stats = graph.get_pair_stats(dst, src)
                total = stats['total'] + rev_stats['total']
                if total >= (thresholds_local.get('volume_threshold',1000.0) / max(0.0001, thresholds_local.get('cross_currency_sensitivity',1.0))):
                    anomalies.append({
                        'accounts': [src, dst],
                        'amount': total,
                        'anomaly_type': 'Cross-Currency Self-Loop',
                        'flow_path': [src, dst, src]
                    })

    # Deduplicate anomalies by unique tuple (accounts tuple, type)
    uniq = {}
    final = []
    for a in anomalies:
        key = (tuple(a.get('accounts',[])), a.get('anomaly_type'), tuple(a.get('flow_path',[])))
        if key in uniq:
            # keep larger amount
            if a['amount'] > uniq[key]['amount']:
                uniq[key] = a
        else:
            uniq[key] = a
    for v in uniq.values():
        final.append(v)
    # sort for deterministic output
    final.sort(key=lambda x: (-x['amount'], x['anomaly_type'], x['accounts']))
    return final