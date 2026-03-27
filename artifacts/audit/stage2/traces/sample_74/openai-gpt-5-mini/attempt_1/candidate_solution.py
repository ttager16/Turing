def __init__(self, timestamp: int, appearance: int, amount: float):
        self.timestamp = timestamp
        self.appearance = appearance
        self.amount = amount

class AVLNode:
    def __init__(self, timestamp: int):
        self.timestamp: int = timestamp
        self.transactions: List[Tuple[str, int]] = []  # list of (canonical_id, appearance_index)
        self.left: Optional['AVLNode'] = None
        self.right: Optional['AVLNode'] = None
        self.height: int = 1

def node_height(n: Optional[AVLNode]) -> int:
    return n.height if n else 0

def update_height(n: AVLNode):
    n.height = 1 + max(node_height(n.left), node_height(n.right))

def balance_factor(n: Optional[AVLNode]) -> int:
    if not n:
        return 0
    return node_height(n.left) - node_height(n.right)

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

def insert_avl(root: Optional[AVLNode], timestamp: int, canonical_id: str, appearance: int) -> AVLNode:
    if root is None:
        node = AVLNode(timestamp)
        node.transactions.append((canonical_id, appearance))
        return node
    if timestamp < root.timestamp:
        root.left = insert_avl(root.left, timestamp, canonical_id, appearance)
    elif timestamp > root.timestamp:
        root.right = insert_avl(root.right, timestamp, canonical_id, appearance)
    else:
        # same timestamp, append transaction tuple
        root.transactions.append((canonical_id, appearance))
        return root
    update_height(root)
    bf = balance_factor(root)
    # Left Left
    if bf > 1 and timestamp < root.left.timestamp:
        return right_rotate(root)
    # Right Right
    if bf < -1 and timestamp > root.right.timestamp:
        return left_rotate(root)
    # Left Right
    if bf > 1 and timestamp > root.left.timestamp:
        root.left = left_rotate(root.left)
        return right_rotate(root)
    # Right Left
    if bf < -1 and timestamp < root.right.timestamp:
        root.right = right_rotate(root.right)
        return left_rotate(root)
    return root

def range_query(root: Optional[AVLNode], start: int, end: int, out: List[Tuple[str,int]]):
    if not root:
        return
    if start <= root.timestamp <= end:
        # traverse left, then this node, then right to maintain timestamp order; appearance ordering handled later
        range_query(root.left, start, end, out)
        out.extend(root.transactions)
        range_query(root.right, start, end, out)
    elif root.timestamp < start:
        range_query(root.right, start, end, out)
    else:
        range_query(root.left, start, end, out)

def traverse_stats(root: Optional[AVLNode], stats: Dict[str,int]):
    if not root:
        return
    stats['node_count'] += 1
    if root.left is None and root.right is None:
        stats['leaf_count'] += 1
    lh = node_height(root.left)
    rh = node_height(root.right)
    stats['balance_max'] = max(stats['balance_max'], abs(lh - rh))
    traverse_stats(root.left, stats)
    traverse_stats(root.right, stats)

def collect_all_transactions(root: Optional[AVLNode], out: List[Tuple[str,int,int]]):
    if not root:
        return
    collect_all_transactions(root.left, out)
    for cid, app in root.transactions:
        out.append((cid, app, root.timestamp))
    collect_all_transactions(root.right, out)

def process_transactions(transactions: List[List],
                         queries: List[List]) -> Dict[str, Any]:
    hash_index: Dict[str, TransactionMetadata] = {}
    root: Optional[AVLNode] = None
    appearance_counter = 0
    total_processed = 0
    duplicate_count = 0
    branch_counts: Dict[str,int] = {}
    duplicate_sources = 0  # count of duplicate transaction IDs encountered (per constraint 13)
    out_of_order_count = 0
    prev_timestamp: Optional[int] = None

    # For amount stats accumulation for unique inserted transactions
    amounts_by_cid: Dict[str, float] = {}

    # Process transactions
    for tx in transactions:
        total_processed += 1
        timestamp, txid, amount = tx
        # Branch detection and canonical parsing
        branch_id = None
        canonical = txid
        if isinstance(txid, str) and txid.startswith('B') and '|' in txid:
            parts = txid.split('|', 1)
            branch_id = parts[0]
            canonical = parts[1]
            branch_counts.setdefault(branch_id, 0)
            branch_counts[branch_id] += 1
        else:
            # If not branch-prefixed, still count nothing for branches
            pass
        if branch_id is None and isinstance(txid, str) and txid.startswith('B') and '|' not in txid:
            # starts with B but no '|', per rules branch only when contains '|'
            pass
        # Also, if branch prefix exists, counts should include duplicates per constraint 12: count all transactions with each branch prefix including duplicates
        # Done above.
        # Deduplication
        if canonical in hash_index:
            duplicate_count += 1
            duplicate_sources += 1
            # still count branch occurrence if branch present even for duplicates
            continue
        # Out-of-order detection
        if prev_timestamp is not None and timestamp < prev_timestamp:
            out_of_order_count += 1
        prev_timestamp = timestamp
        # Insert
        appearance = appearance_counter
        appearance_counter += 1
        metadata = TransactionMetadata(timestamp, appearance, amount)
        hash_index[canonical] = metadata
        amounts_by_cid[canonical] = amount
        root = insert_avl(root, timestamp, canonical, appearance)

    unique_count = len(hash_index)

    # Timestamp statistics
    if unique_count == 0:
        min_timestamp = None
        max_timestamp = None
        timestamp_range = 0
        unique_timestamps = 0
        out_of_order_ratio = 0.0
    else:
        ts_list = [m.timestamp for m in hash_index.values()]
        min_timestamp = min(ts_list)
        max_timestamp = max(ts_list)
        timestamp_range = max_timestamp - min_timestamp
        unique_timestamps = len(set(ts_list))
        out_of_order_ratio = round((out_of_order_count / total_processed) * 100, 2) if total_processed>0 else 0.0

    # Amount statistics (population std dev)
    if unique_count == 0:
        total_amount = 0.0
        avg_amount = 0.0
        min_amount = 0.0
        max_amount = 0.0
        amount_std_dev = 0.0
    else:
        amounts = list(amounts_by_cid.values())
        total_amount = sum(amounts)
        avg_amount = total_amount / len(amounts)
        min_amount = min(amounts)
        max_amount = max(amounts)
        # population variance
        mean = avg_amount
        var = sum((a - mean) ** 2 for a in amounts) / len(amounts)
        amount_std_dev = round(math.sqrt(var), 2)

    # Queries
    results: List[List[str]] = []
    per_query_metrics: List[Dict[str, Any]] = []
    total_results_returned = 0
    empty_query_count = 0
    for q in queries:
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
        collected: List[Tuple[str,int]] = []
        range_query(root, start, end, collected)
        # Remove duplicates? Transactions are unique by canonical in tree; collected may contain multiple entries but unique canonical across tree exists.
        # Sort by appearance index
        collected_sorted = sorted(collected, key=lambda x: x[1])
        canonical_list = [cid for cid,_ in collected_sorted]
        results.append(canonical_list)
        total_results_returned += len(canonical_list)
        if len(canonical_list) == 0:
            empty_query_count += 1
            per_query_metrics.append({
                "range": [start, end],
                "result_count": 0,
                "total_amount": 0.0,
                "avg_amount": 0.0,
                "min_amount": 0.0,
                "max_amount": 0.0
            })
        else:
            # compute amount stats for these canonical IDs (unique)
            vals = [hash_index[c].amount for c in canonical_list]
            t_amt = sum(vals)
            avg_a = t_amt / len(vals)
            min_a = min(vals)
            max_a = max(vals)
            per_query_metrics.append({
                "range": [start, end],
                "result_count": len(vals),
                "total_amount": t_amt,
                "avg_amount": avg_a,
                "min_amount": min_a,
                "max_amount": max_a
            })

    total_queries = len(queries)
    avg_results_per_query = (total_results_returned / total_queries) if total_queries>0 else 0.0

    # Tree statistics
    if root is None:
        tree_height = 0
        node_count = 0
        balance_max = 0
        is_balanced = True
        leaf_count = 0
        theoretical_min_height = 0
        balance_efficiency = 100.0
    else:
        tree_height = node_height(root)
        stats = {'node_count':0, 'leaf_count':0, 'balance_max':0}
        traverse_stats(root, stats)
        node_count = stats['node_count']
        leaf_count = stats['leaf_count']
        balance_max = stats['balance_max']
        is_balanced = (balance_max <= 1)
        theoretical_min_height = int(math.isqrt(node_count))
        balance_efficiency = round((1 - balance_max/10) * 100, 2)
    # Performance metrics
    insertion_success_rate = round(((total_processed - duplicate_count) / total_processed) * 100, 2) if total_processed>0 else 0.0
    deduplication_rate = round((duplicate_count / total_processed) * 100, 2) if total_processed>0 else 0.0

    # Branch statistics summary
    branches_detected = len(branch_counts)
    merge_efficiency = round((unique_count / total_processed) * 100, 2) if total_processed>0 else 0.0

    output = {
        "results": results,
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "branch_statistics": {
            "branches_detected": branches_detected,
            "transactions_per_branch": branch_counts,
            "duplicate_sources": duplicate_sources,
            "merge_efficiency": merge_efficiency
        },
        "timestamp_statistics": {
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
            "timestamp_range": timestamp_range,
            "unique_timestamps": unique_timestamps,
            "out_of_order_ratio": out_of_order_ratio
        },
        "amount_statistics": {
            "total_amount": round(total_amount, 2),
            "average_amount": round(avg_amount, 2),
            "min_amount": round(min_amount, 2),
            "max_amount": round(max_amount, 2),
            "amount_std_dev": amount_std_dev
        },
        "query_statistics": {
            "total_queries": total_queries,
            "per_query_metrics": per_query_metrics,
            "total_results_returned": total_results_returned,
            "avg_results_per_query": avg_results_per_query,
            "empty_query_count": empty_query_count
        },
        "tree_statistics": {
            "height": tree_height,
            "node_count": node_count,
            "balance_factor_max": balance_max,
            "is_balanced": is_balanced,
            "leaf_count": leaf_count,
            "theoretical_min_height": theoretical_min_height,
            "balance_efficiency": balance_efficiency
        },
        "performance_metrics": {
            "total_transactions_processed": total_processed,
            "insertion_success_rate": insertion_success_rate,
            "deduplication_rate": deduplication_rate
        }
    }
    return output