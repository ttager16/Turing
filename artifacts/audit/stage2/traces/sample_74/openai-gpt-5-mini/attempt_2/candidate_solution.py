def __init__(self, timestamp: int, appearance: int, amount: float):
        self.timestamp = timestamp
        self.appearance = appearance
        self.amount = amount

class AVLNode:
    def __init__(self, timestamp: int):
        self.timestamp: int = timestamp
        self.transactions: List[Tuple[str, int]] = []  # list of (canonical_id, appearance)
        self.left: Optional['AVLNode'] = None
        self.right: Optional['AVLNode'] = None
        self.height: int = 1

def height(node: Optional[AVLNode]) -> int:
    return node.height if node else 0

def update_height(node: AVLNode):
    node.height = 1 + max(height(node.left), height(node.right))

def balance_factor(node: Optional[AVLNode]) -> int:
    if not node:
        return 0
    return height(node.left) - height(node.right)

def right_rotate(y: AVLNode) -> AVLNode:
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def left_rotate(x: AVLNode) -> AVLNode:
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

def rebalance(node: AVLNode, inserted_timestamp: int) -> AVLNode:
    update_height(node)
    bf = balance_factor(node)
    if bf > 1:
        if inserted_timestamp < node.left.timestamp:
            # left-left
            return right_rotate(node)
        else:
            # left-right
            node.left = left_rotate(node.left)
            return right_rotate(node)
    if bf < -1:
        if inserted_timestamp > node.right.timestamp:
            # right-right
            return left_rotate(node)
        else:
            # right-left
            node.right = right_rotate(node.right)
            return left_rotate(node)
    return node

def avl_insert(node: Optional[AVLNode], timestamp: int, canonical_id: str, appearance: int) -> AVLNode:
    if node is None:
        newnode = AVLNode(timestamp)
        newnode.transactions.append((canonical_id, appearance))
        return newnode
    if timestamp < node.timestamp:
        node.left = avl_insert(node.left, timestamp, canonical_id, appearance)
    elif timestamp > node.timestamp:
        node.right = avl_insert(node.right, timestamp, canonical_id, appearance)
    else:
        # same timestamp: append
        node.transactions.append((canonical_id, appearance))
        return node
    return rebalance(node, timestamp)

def range_query_node(node: Optional[AVLNode], start: int, end: int, out: List[Tuple[int, int, str]]):
    if node is None:
        return
    if start <= node.timestamp <= end:
        # left subtree
        range_query_node(node.left, start, end, out)
        # collect transactions
        for cid, app in node.transactions:
            out.append((app, node.timestamp, cid))
        range_query_node(node.right, start, end, out)
    elif node.timestamp < start:
        range_query_node(node.right, start, end, out)
    else:
        range_query_node(node.left, start, end, out)

def collect_tree_stats(node: Optional[AVLNode], stats: Dict[str, Any]):
    if node is None:
        return
    stats['node_count'] += 1
    if node.left is None and node.right is None:
        stats['leaf_count'] += 1
    lh = height(node.left)
    rh = height(node.right)
    stats['balance_factor_max'] = max(stats['balance_factor_max'], abs(lh - rh))
    stats['height'] = max(stats['height'], node.height)
    collect_tree_stats(node.left, stats)
    collect_tree_stats(node.right, stats)

def process_transactions(transactions: List[List],
                         queries: List[List]) -> Dict[str, Any]:
    # Hash table mapping canonical_id -> TransactionMetadata
    hash_index: Dict[str, TransactionMetadata] = {}
    root: Optional[AVLNode] = None
    appearance_counter = 0
    total_processed = 0
    duplicate_count = 0
    branch_counts: Dict[str, int] = {}
    duplicate_sources = 0
    out_of_order_count = 0
    prev_timestamp: Optional[int] = None
    timestamps_set = set()
    amounts_for_unique: List[float] = []

    for txn in transactions:
        total_processed += 1
        if len(txn) != 3:
            continue
        ts, txid, amount = txn
        # branch parsing
        branch_id = None
        canonical_id = txid
        if isinstance(txid, str) and txid.startswith('B') and '|' in txid:
            parts = txid.split('|', 1)
            branch_id = parts[0]
            canonical_id = parts[1]
            branch_counts[branch_id] = branch_counts.get(branch_id, 0) + 1
        else:
            # count only branch-prefixed ones per requirement 12 (count transactions with each branch prefix including duplicates)
            pass
        # For branch-prefixed detection count only when prefix exists, duplicates counted also
        if branch_id is None:
            # nothing to increment
            pass
        # deduplication
        if canonical_id in hash_index:
            duplicate_count += 1
            duplicate_sources += 1
            # still count branch occurrence if had branch prefix
            if branch_id is not None:
                # already counted above
                pass
            continue
        # out of order detection
        if prev_timestamp is not None and ts < prev_timestamp:
            out_of_order_count += 1
        prev_timestamp = ts
        # insert
        metadata = TransactionMetadata(ts, appearance_counter, float(amount))
        hash_index[canonical_id] = metadata
        root = avl_insert(root, ts, canonical_id, appearance_counter)
        appearance_counter += 1
        timestamps_set.add(ts)
        amounts_for_unique.append(float(amount))

    unique_count = len(hash_index)
    # Merge efficiency
    merge_efficiency = round((unique_count / total_processed * 100) if total_processed else 0.0, 2)
    # Timestamp statistics
    if unique_count:
        min_ts = min(md.timestamp for md in hash_index.values())
        max_ts = max(md.timestamp for md in hash_index.values())
        ts_range = max_ts - min_ts
        unique_timestamps = len(set(md.timestamp for md in hash_index.values()))
    else:
        min_ts = None
        max_ts = None
        ts_range = 0
        unique_timestamps = 0
    out_of_order_ratio = round((out_of_order_count / total_processed * 100) if total_processed else 0.0, 2)
    # Amount statistics
    if amounts_for_unique:
        total_amount = sum(amounts_for_unique)
        avg_amount = total_amount / len(amounts_for_unique)
        min_amount = min(amounts_for_unique)
        max_amount = max(amounts_for_unique)
        mean = avg_amount
        var = sum((x - mean) ** 2 for x in amounts_for_unique) / len(amounts_for_unique)
        stddev = round(math.sqrt(var), 2)
        total_amount = float(total_amount)
        avg_amount = float(avg_amount)
    else:
        total_amount = 0.0
        avg_amount = 0.0
        min_amount = 0.0
        max_amount = 0.0
        stddev = 0.0

    # Queries processing
    results: List[List[str]] = []
    per_query_metrics: List[Dict[str, Any]] = []
    total_results_returned = 0
    empty_query_count = 0
    for q in queries:
        if len(q) != 2:
            results.append([])
            per_query_metrics.append({
                "range": q,
                "result_count": 0,
                "total_amount": 0.0,
                "avg_amount": 0.0,
                "min_amount": 0.0,
                "max_amount": 0.0
            })
            empty_query_count += 1
            continue
        start, end = q
        if start > end:
            results.append([])
            per_query_metrics.append({
                "range": [start, end],
                "result_count": 0,
                "total_amount": 0.0,
                "avg_amount": 0.0,
                "min_amount": 0.0,
                "max_amount": 0.0
            })
            empty_query_count += 1
            continue
        collected: List[Tuple[int, int, str]] = []  # (appearance, timestamp, cid)
        range_query_node(root, start, end, collected)
        # sort by appearance index
        collected.sort(key=lambda x: x[0])
        ids_in_order = [cid for _, _, cid in collected]
        results.append(ids_in_order)
        cnt = len(collected)
        total_results_returned += cnt
        if cnt == 0:
            per_query_metrics.append({
                "range": [start, end],
                "result_count": 0,
                "total_amount": 0.0,
                "avg_amount": 0.0,
                "min_amount": 0.0,
                "max_amount": 0.0
            })
            empty_query_count += 1
        else:
            # compute amount stats for canonical ids in result
            amounts = [hash_index[cid].amount for cid in ids_in_order]
            tot = sum(amounts)
            avg = tot / len(amounts)
            mn = min(amounts)
            mx = max(amounts)
            per_query_metrics.append({
                "range": [start, end],
                "result_count": cnt,
                "total_amount": float(tot),
                "avg_amount": float(avg),
                "min_amount": float(mn),
                "max_amount": float(mx)
            })

    total_queries = len(queries)
    avg_results_per_query = (total_results_returned / total_queries) if total_queries else 0.0

    # Tree statistics
    tree_stats = {
        "height": 0,
        "node_count": 0,
        "balance_factor_max": 0,
        "is_balanced": True,
        "leaf_count": 0,
        "theoretical_min_height": 0,
        "balance_efficiency": 100.0
    }
    if root is None:
        tree_stats["height"] = 0
        tree_stats["node_count"] = 0
        tree_stats["balance_factor_max"] = 0
        tree_stats["is_balanced"] = True
        tree_stats["leaf_count"] = 0
        tree_stats["theoretical_min_height"] = 0
        tree_stats["balance_efficiency"] = 100.0
    else:
        stats = {"height": 0, "node_count": 0, "balance_factor_max": 0, "leaf_count": 0}
        collect_tree_stats(root, stats)
        node_count = stats["node_count"]
        height_val = root.height
        bf_max = stats["balance_factor_max"]
        is_balanced = bf_max <= 1
        leaf_count = stats["leaf_count"]
        theoretical_min = int(math.isqrt(node_count)) if node_count > 0 else 0
        balance_eff = round((1 - bf_max / 10) * 100, 2) if node_count > 0 else 100.0
        tree_stats = {
            "height": height_val,
            "node_count": node_count,
            "balance_factor_max": bf_max,
            "is_balanced": is_balanced,
            "leaf_count": leaf_count,
            "theoretical_min_height": theoretical_min,
            "balance_efficiency": balance_eff
        }

    performance_metrics = {
        "total_transactions_processed": total_processed,
        "insertion_success_rate": round((unique_count / total_processed * 100) if total_processed else 0.0, 2),
        "deduplication_rate": round((duplicate_count / total_processed * 100) if total_processed else 0.0, 2)
    }

    branch_statistics = {
        "branches_detected": len(branch_counts),
        "transactions_per_branch": dict(branch_counts),
        "duplicate_sources": duplicate_sources,
        "merge_efficiency": merge_efficiency
    }

    timestamp_statistics = {
        "min_timestamp": min_ts,
        "max_timestamp": max_ts,
        "timestamp_range": ts_range,
        "unique_timestamps": unique_timestamps,
        "out_of_order_ratio": out_of_order_ratio
    }

    amount_statistics = {
        "total_amount": float(round(total_amount, 2) if isinstance(total_amount, float) else float(total_amount)),
        "average_amount": float(round(avg_amount, 2) if isinstance(avg_amount, float) else float(avg_amount)),
        "min_amount": float(min_amount),
        "max_amount": float(max_amount),
        "amount_std_dev": stddev
    }

    query_statistics = {
        "total_queries": total_queries,
        "per_query_metrics": per_query_metrics,
        "total_results_returned": total_results_returned,
        "avg_results_per_query": avg_results_per_query,
        "empty_query_count": empty_query_count
    }

    result = {
        "results": results,
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "branch_statistics": branch_statistics,
        "timestamp_statistics": timestamp_statistics,
        "amount_statistics": amount_statistics,
        "query_statistics": query_statistics,
        "tree_statistics": tree_stats,
        "performance_metrics": performance_metrics
    }
    return result