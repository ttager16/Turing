def _extract_currency(account: str) -> str:
    m = _account_currency_re.match(account)
    if m:
        return m.group(1)
    # fallback: non-matched -> use whole prefix
    parts = re.split(r'(\d+)', account)
    return parts[0] if parts else account

class MultiLayerGraph:
    def __init__(self):
        # adjacency: src -> list of (dst, amount, tx_id)
        self.adj = defaultdict(list)
        # reverse adjacency for easy traversal
        self.rev = defaultdict(list)
        # aggregated edge stats: (src,dst) -> { 'count':int, 'volume':float, 'txs':[amounts] }
        self.edge_stats = defaultdict(lambda: {'count':0, 'volume':0.0, 'txs':[]})
        # node set
        self.nodes = set()
        # lock for thread-safety when thresholds or updates happen
        self.lock = threading.RLock()

    def add_transaction(self, src: str, dst: str, amount: float, tx_id: int = None):
        with self.lock:
            self.nodes.add(src); self.nodes.add(dst)
            self.adj[src].append((dst, amount, tx_id))
            self.rev[dst].append((src, amount, tx_id))
            key = (src, dst)
            s = self.edge_stats[key]
            s['count'] += 1
            s['volume'] += amount
            s['txs'].append(amount)

    def remove_transaction(self, src: str, dst: str, amount: float):
        # best-effort removal (not required by sample, included for completeness)
        with self.lock:
            lst = self.adj.get(src, [])
            for i, (d, a, tid) in enumerate(lst):
                if d == dst and a == amount:
                    lst.pop(i)
                    break
            lstr = self.rev.get(dst, [])
            for i, (s, a, tid) in enumerate(lstr):
                if s == src and a == amount:
                    lstr.pop(i)
                    break
            key = (src, dst)
            s = self.edge_stats.get(key)
            if s:
                try:
                    s['txs'].remove(amount)
                    s['count'] = max(0, s['count'] - 1)
                    s['volume'] = max(0.0, s['volume'] - amount)
                except ValueError:
                    pass

def detect_anomalies(transaction_data: List[List], thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
    graph = MultiLayerGraph()
    # thresholds with defaults
    volume_threshold = float(thresholds.get('volume_threshold', 1000.0))
    frequency_threshold = int(thresholds.get('frequency_threshold', 3))
    cross_currency_sensitivity = float(thresholds.get('cross_currency_sensitivity', 1.0))
    cycle_threshold = float(thresholds.get('cycle_threshold', 2000.0))

    # Effective cross-currency threshold: scale by sensitivity (lower sensitivity -> higher effective threshold)
    # The prompt implies effective threshold = volume_threshold / sensitivity
    cross_effective_threshold = volume_threshold / max(1e-9, cross_currency_sensitivity)

    # Build graph
    for idx, tx in enumerate(transaction_data):
        if len(tx) < 3:
            continue
        src, dst, amount = tx[0], tx[1], float(tx[2])
        graph.add_transaction(src, dst, amount, tx_id=idx)

    anomalies: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str,str]] = set()

    # Detect High Volume and Frequency per account pair
    with graph.lock:
        for (src, dst), stats in graph.edge_stats.items():
            if stats['count'] >= frequency_threshold and stats['volume'] > volume_threshold:
                if (src,dst) not in seen_pairs:
                    anomalies.append({
                        'accounts': [src, dst],
                        'amount': round(stats['volume'], 6),
                        'anomaly_type': 'High Volume and Frequency',
                        'flow_path': [src, dst]
                    })
                    seen_pairs.add((src,dst))

    # Detect Cross-Currency Flow Spikes (single edges exceeding cross_effective_threshold or large single tx)
    with graph.lock:
        for (src, dst), stats in graph.edge_stats.items():
            src_cur = _extract_currency(src)
            dst_cur = _extract_currency(dst)
            is_cross = src_cur != dst_cur
            # check aggregated or any single tx exceeding threshold
            if is_cross:
                if stats['volume'] > cross_effective_threshold and (src,dst) not in seen_pairs:
                    anomalies.append({
                        'accounts': [src, dst],
                        'amount': round(stats['volume'], 6),
                        'anomaly_type': 'Cross-Currency Flow Spike',
                        'flow_path': [src, dst]
                    })
                    seen_pairs.add((src,dst))
                else:
                    # check any single tx large
                    for amt in stats['txs']:
                        if amt > cross_effective_threshold and (src,dst) not in seen_pairs:
                            anomalies.append({
                                'accounts': [src, dst],
                                'amount': round(stats['volume'], 6),
                                'anomaly_type': 'Cross-Currency Flow Spike',
                                'flow_path': [src, dst]
                            })
                            seen_pairs.add((src,dst))
                            break

    # Detect cycles using DFS up to reasonable depth to avoid explosion
    # We'll detect simple cycles (no repeated nodes except start=end) and aggregate cycle volume as sum of involved directed edge volumes (use edge_stats)
    def find_cycles(limit_nodes=1000):
        cycles = []  # list of lists of nodes representing cycle path
        visited_global = set()
        nodes = list(graph.nodes)
        for start in nodes:
            if start in visited_global:
                continue
            stack = [(start, [start], set([start]))]
            while stack:
                node, path, seen = stack.pop()
                for (nbr, amt, tid) in graph.adj.get(node, []):
                    if nbr == start and len(path) >= 2:
                        cycle = path + [start]
                        # normalize cycle representation to avoid duplicates (rotate to smallest node)
                        min_idx = min(range(len(cycle)-1), key=lambda i: cycle[i])
                        normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                        if tuple(normalized) not in visited_global:
                            cycles.append(normalized)
                            # mark all nodes in cycle visited global to limit duplication
                            for n in normalized[:-1]:
                                visited_global.add(n)
                    elif nbr not in seen and len(path) < 8:  # limit depth to keep efficient
                        stack.append((nbr, path + [nbr], seen | {nbr}))
        return cycles

    cycles = find_cycles()

    # For each cycle, compute total directed volume along path edges (sum of edge_stats for adjacent pairs)
    with graph.lock:
        for cyc in cycles:
            # cyc example: [A, B, C, A]
            nodes_in_cycle = cyc[:-1]
            total = 0.0
            parts = []
            for i in range(len(nodes_in_cycle)):
                a = nodes_in_cycle[i]
                b = nodes_in_cycle[(i+1) % len(nodes_in_cycle)]
                key = (a, b)
                stats = graph.edge_stats.get(key)
                if stats:
                    total += stats['volume']
                parts.append(a)
            if total >= cycle_threshold:
                # determine anomaly type wording: Suspicious Cyclical Flow
                # Avoid duplicating with existing reported pairs
                involved = parts.copy()
                primary_pair = (involved[0], involved[-1])
                anomalies.append({
                    'accounts': [involved[0], involved[-1]],
                    'amount': round(total, 6),
                    'anomaly_type': 'Suspicious Cyclical Flow',
                    'flow_path': involved + [involved[0]]
                })

    # Detect Cross-Currency Self-Loops and rapid reciprocal flows between same logical account across currencies
    # Identify pairs where src and dst share numeric id but different currency prefix (e.g., accountUSD5, accountEUR5)
    with graph.lock:
        # map logical id -> accounts per currency
        logical_map = defaultdict(set)
        for n in graph.nodes:
            # we attempt to extract trailing number as logical id
            m = re.search(r'(\d+)$', n)
            if m:
                lid = m.group(1)
            else:
                lid = n
            logical_map[lid].add(n)
        for lid, accounts in logical_map.items():
            if len(accounts) < 2:
                continue
            # check edges among these accounts for rapid back-and-forth
            accs = list(accounts)
            for i in range(len(accs)):
                for j in range(i+1, len(accs)):
                    a = accs[i]; b = accs[j]
                    key_ab = (a,b); key_ba = (b,a)
                    stats_ab = graph.edge_stats.get(key_ab, {'count':0,'volume':0.0})
                    stats_ba = graph.edge_stats.get(key_ba, {'count':0,'volume':0.0})
                    total_volume = stats_ab['volume'] + stats_ba['volume']
                    if total_volume > cross_effective_threshold:
                        # ensure cross-currency
                        if _extract_currency(a) != _extract_currency(b):
                            anomalies.append({
                                'accounts': [a, b],
                                'amount': round(total_volume, 6),
                                'anomaly_type': 'Cross-Currency Self-Loop',
                                'flow_path': [a, b, a] if stats_ba['count']>0 else [a, b]
                            })

    # Deduplicate anomalies by (type, tuple(accounts), amount) coarse key
    uniq = []
    seen_keys = set()
    for an in anomalies:
        key = (an.get('anomaly_type'), tuple(an.get('accounts',[])), round(float(an.get('amount',0.0)),6))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        uniq.append(an)

    return uniq