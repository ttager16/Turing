def detect_fraudulent_transactions(transactions: List[Dict[str, Any]], timeframe: List[str]) -> List[Union[List[Dict[str, Any]], Dict[str, Any]]]:
    """Detect fraudulent transaction patterns in given timeframe."""
    # Edge case: empty input
    if not transactions:
        summary = {
            'total_anomalies': 0,
            'fraud_scenarios': {
                'cyclic_transfers': 0,
                'multi_account_infiltration': 0,
                'nested_money_laundering': 0,
                'high_frequency_accounts': 0,
                'large_amount_transactions': 0,
                'rapid_sequential_transactions': 0,
                'after_hours_transactions': 0,
                'invalid_amount_transactions': 0
            },
            'key_subgraphs': []
        }
        return [[], summary]

    # Parse timeframe
    start_tf = datetime.fromisoformat(timeframe[0])
    end_tf = datetime.fromisoformat(timeframe[1])

    # Preprocess transactions: filter by timeframe inclusive start, exclusive end
    txs = []
    tx_by_id = {}
    for t in transactions:
        try:
            ts = datetime.fromisoformat(t['timestamp'])
        except Exception:
            continue
        if not (start_tf <= ts < end_tf):
            continue
        tx = dict(t)
        tx['_ts'] = ts
        txs.append(tx)
        tx_by_id[tx['transaction_id']] = tx

    # If none in timeframe
    if not txs:
        summary = {
            'total_anomalies': 0,
            'fraud_scenarios': {
                'cyclic_transfers': 0,
                'multi_account_infiltration': 0,
                'nested_money_laundering': 0,
                'high_frequency_accounts': 0,
                'large_amount_transactions': 0,
                'rapid_sequential_transactions': 0,
                'after_hours_transactions': 0,
                'invalid_amount_transactions': 0
            },
            'key_subgraphs': []
        }
        return [[], summary]

    # Build adjacency lists for directed graph: source -> list of (dest, tx_id)
    adj = defaultdict(list)
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for tx in sorted(txs, key=lambda x: x['_ts']):
        sid = tx['source_account']
        did = tx['destination_account']
        tid = tx['transaction_id']
        adj[sid].append((did, tid))
        outgoing[sid].append(tx)
        incoming[did].append(tx)

    flagged = []
    counts = {
        'cyclic_transfers': 0,
        'multi_account_infiltration': 0,
        'nested_money_laundering': 0,
        'high_frequency_accounts': 0,
        'large_amount_transactions': 0,
        'rapid_sequential_transactions': 0,
        'after_hours_transactions': 0,
        'invalid_amount_transactions': 0
    }

    # Rule 1 & 2 & 3: per-transaction checks
    for tx in txs:
        tid = tx['transaction_id']
        amount = tx.get('amount', 0)
        ts = tx['_ts']
        # Invalid amount
        if amount < 1 or amount > 10_000_000:
            flagged.append({'chain': [tid], 'reason': 'Invalid amount transaction'})
            counts['invalid_amount_transactions'] += 1
            # continue checking other flags may be redundant but keep deterministic
            continue
        # After-hours: business hours 9:00 <= t <17:00 (exclusive of 17:00)
        hour_min = ts.time()
        if not (hour_min >= datetime(ts.year, ts.month, ts.day, 9, 0).time() and hour_min < datetime(ts.year, ts.month, ts.day, 17, 0).time()):
            flagged.append({'chain': [tid], 'reason': 'After-hours transaction'})
            counts['after_hours_transactions'] += 1
        # Large amount >100k (and valid)
        if amount > 100_000:
            flagged.append({'chain': [tid], 'reason': 'Large amount transaction'})
            counts['large_amount_transactions'] += 1

    # Rule 6: High frequency account activity (10+ outgoing)
    high_freq_accounts = []
    for acc, outs in outgoing.items():
        if len(outs) >= 10:
            # order by timestamp ascending
            outs_sorted = sorted(outs, key=lambda x: x['_ts'])
            chain = [tx['transaction_id'] for tx in outs_sorted]
            flagged.append({'chain': chain, 'reason': 'High frequency account activity'})
            counts['high_frequency_accounts'] += 1
            high_freq_accounts.append(acc)

    # Rule 7: Nested money laundering for high-frequency accounts
    nested_flagged_accounts = []
    for acc in high_freq_accounts:
        txs_related = incoming[acc] + outgoing[acc]
        # sort by timestamp
        txs_related_sorted = sorted(txs_related, key=lambda x: x['_ts'])
        if len(txs_related_sorted) >= 8:
            chain = [tx['transaction_id'] for tx in txs_related_sorted[:8]]
            flagged.append({'chain': chain, 'reason': 'Nested money laundering pattern'})
            counts['nested_money_laundering'] += 1
            nested_flagged_accounts.append(acc)

    # Rule 8: Rapid sequential transactions: 2+ from same source within 5 minutes -> flag consecutive pairs
    for acc, outs in outgoing.items():
        outs_sorted = sorted(outs, key=lambda x: x['_ts'])
        for i in range(len(outs_sorted) - 1):
            t1 = outs_sorted[i]['_ts']
            t2 = outs_sorted[i+1]['_ts']
            if (t2 - t1) <= timedelta(minutes=5):
                chain = [outs_sorted[i]['transaction_id'], outs_sorted[i+1]['transaction_id']]
                flagged.append({'chain': chain, 'reason': 'Rapid sequential transactions'})
                counts['rapid_sequential_transactions'] += 1

    # Rule 5: Multi-account infiltration: detect chains with 5+ hops from same source using DFS, flag first 5 transactions
    # We'll perform DFS up to depth >=5
    def dfs_chains(start_acc):
        results = []
        stack = [(start_acc, [], set())]  # node, path of tx ids, visited accounts to avoid immediate repeats
        while stack:
            node, path, visited = stack.pop()
            for (nbr, tid) in adj.get(node, []):
                if tid in path:
                    continue
                new_path = path + [tid]
                if len(new_path) >= 5:
                    results.append(new_path[:5])
                # prevent infinite loops by limiting length to, say, 20
                if len(new_path) < 20:
                    new_visited = set(visited)
                    new_visited.add(node)
                    stack.append((nbr, new_path, new_visited))
        return results

    multi_infil_count = 0
    for acc in list(adj.keys()):
        chains = dfs_chains(acc)
        for c in chains:
            flagged.append({'chain': c, 'reason': 'Multi-account infiltration pattern'})
            counts['multi_account_infiltration'] += 1
            multi_infil_count += 1

    # Rule 4: Cyclic transfer patterns: detect directed cycles len>=2 using DFS
    visited_global = set()
    cycles_found = set()  # store tuple of tx ids sorted to avoid dup
    def dfs_cycle(node, stack_nodes, stack_txids, index_map):
        visited_global.add(node)
        for (nbr, tid) in adj.get(node, []):
            if nbr in index_map:
                # found cycle from index_map[nbr] to end
                start_idx = index_map[nbr]
                cycle_txids = stack_txids[start_idx:] + [tid]
                if len(cycle_txids) >= 2:
                    key = tuple(cycle_txids)
                    if key not in cycles_found:
                        cycles_found.add(key)
            elif nbr not in visited_global and len(stack_txids) < 100:
                index_map[nbr] = len(stack_txids)
                stack_txids.append(tid)
                dfs_cycle(nbr, stack_nodes + [nbr], stack_txids, index_map)
                # backtrack
                stack_txids.pop()
                index_map.pop(nbr, None)

    for node in list(adj.keys()):
        if node not in visited_global:
            dfs_cycle(node, [node], [], {node: 0})

    for cycle in cycles_found:
        flagged.append({'chain': list(cycle), 'reason': 'Cyclic transfer pattern detected'})
        counts['cyclic_transfers'] += 1

    # Edge case: detect self-loops and circular references explicitly
    for acc, edges in adj.items():
        for (nbr, tid) in edges:
            if acc == nbr:
                # self-loop
                flagged.append({'chain': [tid], 'reason': 'Cyclic transfer pattern detected'})
                counts['cyclic_transfers'] += 1

    # Build key_subgraphs for up to 5 clusters from high-frequency accounts
    key_subgraphs = []
    clusters_added = 0
    for acc in high_freq_accounts:
        if clusters_added >= 5:
            break
        related_accounts = set()
        for tx in incoming[acc] + outgoing[acc]:
            related_accounts.add(tx['source_account'])
            related_accounts.add(tx['destination_account'])
        nodes_involved = sorted(list(related_accounts))
        desc = f"High activity cluster around account {acc}"
        key_subgraphs.append({'nodes_involved': nodes_involved, 'description': desc})
        clusters_added += 1

    # Consolidated summary
    total_anomalies = len(flagged)
    summary = {
        'total_anomalies': total_anomalies,
        'fraud_scenarios': {
            'cyclic_transfers': counts['cyclic_transfers'],
            'multi_account_infiltration': counts['multi_account_infiltration'],
            'nested_money_laundering': counts['nested_money_laundering'],
            'high_frequency_accounts': counts['high_frequency_accounts'],
            'large_amount_transactions': counts['large_amount_transactions'],
            'rapid_sequential_transactions': counts['rapid_sequential_transactions'],
            'after_hours_transactions': counts['after_hours_transactions'],
            'invalid_amount_transactions': counts['invalid_amount_transactions']
        },
        'key_subgraphs': key_subgraphs
    }

    return [flagged, summary]