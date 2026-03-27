# main.py
from typing import List, Tuple, Dict, Optional, Any


class AVLNode:
    """
    Node in AVL tree, keyed by timestamp.
    Each node stores all transactions with the same timestamp,
    ordered by their appearance index.
    """

    def __init__(self, timestamp: int):
        self.timestamp = timestamp
        self.transactions: List[Tuple[str, int]] = []  # [(canonical_id, appearance_idx)]
        self.left: Optional['AVLNode'] = None
        self.right: Optional['AVLNode'] = None
        self.height: int = 1


class AVLTree:
    """
    Self-balancing AVL tree for temporal indexing.
    """

    def __init__(self):
        self.root: Optional[AVLNode] = None

    def _get_height(self, node: Optional[AVLNode]) -> int:
        """Get height of node, treating None as 0."""
        return node.height if node else 0

    def _get_balance(self, node: Optional[AVLNode]) -> int:
        """Calculate balance factor (left height - right height)."""
        if not node:
            return 0
        return self._get_height(node.left) - self._get_height(node.right)

    def _update_height(self, node: AVLNode) -> None:
        """Update node height based on children."""
        node.height = 1 + max(self._get_height(node.left), self._get_height(node.right))

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        """Perform right rotation."""
        x = y.left
        T2 = x.right

        # Rotation
        x.right = y
        y.left = T2

        # Update heights
        self._update_height(y)
        self._update_height(x)

        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        """Perform left rotation."""
        y = x.right
        T2 = y.left

        # Rotation
        y.left = x
        x.right = T2

        # Update heights
        self._update_height(x)
        self._update_height(y)

        return y

    def insert(self, timestamp: int, canonical_id: str, appearance_idx: int) -> None:
        """
        Insert transaction into AVL tree.
        If timestamp exists, append to that node's transaction list.
        """
        self.root = self._insert_recursive(self.root, timestamp, canonical_id, appearance_idx)

    def _insert_recursive(self, node: Optional[AVLNode], timestamp: int,
                          canonical_id: str, appearance_idx: int) -> AVLNode:
        """Recursive insertion with AVL balancing."""
        # Standard BST insertion
        if not node:
            new_node = AVLNode(timestamp)
            new_node.transactions.append((canonical_id, appearance_idx))
            return new_node

        if timestamp < node.timestamp:
            node.left = self._insert_recursive(node.left, timestamp, canonical_id, appearance_idx)
        elif timestamp > node.timestamp:
            node.right = self._insert_recursive(node.right, timestamp, canonical_id, appearance_idx)
        else:
            # Same timestamp - append to existing node
            node.transactions.append((canonical_id, appearance_idx))
            return node

        # Update height
        self._update_height(node)

        # Get balance factor
        balance = self._get_balance(node)

        # Left-Left case
        if balance > 1 and timestamp < node.left.timestamp:
            return self._rotate_right(node)

        # Right-Right case
        if balance < -1 and timestamp > node.right.timestamp:
            return self._rotate_left(node)

        # Left-Right case
        if balance > 1 and timestamp > node.left.timestamp:
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        # Right-Left case
        if balance < -1 and timestamp < node.right.timestamp:
            node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def range_query(self, start: int, end: int) -> List[Tuple[str, int]]:
        """
        Query all transactions in [start, end] timestamp range.
        Returns list of (canonical_id, appearance_idx) tuples.
        """
        if start > end:
            return []

        results = []
        self._range_query_recursive(self.root, start, end, results)
        return results

    def _range_query_recursive(self, node: Optional[AVLNode], start: int,
                                end: int, results: List[Tuple[str, int]]) -> None:
        """Recursive in-order traversal for range query."""
        if not node:
            return

        # If current timestamp is greater than start, explore left subtree
        if node.timestamp > start:
            self._range_query_recursive(node.left, start, end, results)

        # If current timestamp is in range, collect transactions
        if start <= node.timestamp <= end:
            results.extend(node.transactions)

        # If current timestamp is less than end, explore right subtree
        if node.timestamp < end:
            self._range_query_recursive(node.right, start, end, results)


class TransactionMetadata:
    """Metadata for each unique canonical transaction."""

    def __init__(self, timestamp: int, appearance_idx: int, amount: float):
        self.timestamp = timestamp
        self.appearance_idx = appearance_idx
        self.amount = amount


class TemporalHashTable:
    """
    Integrated data structure combining:
    - Hash map for canonical ID lookup
    - AVL tree for temporal indexing
    - Deterministic merge and query capabilities
    """

    def __init__(self):
        self.hash_index: Dict[str, TransactionMetadata] = {}
        self.time_index: AVLTree = AVLTree()
        self.next_appearance_idx: int = 0

    def _extract_canonical_id(self, transaction_id: str) -> str:
        """
        Extract canonical ID from transaction ID.
        If prefixed with 'B{branch}|{id}', return {id}.
        Otherwise, return full transaction_id.
        """
        if '|' in transaction_id and transaction_id.startswith('B'):
            # Extract canonical ID after the '|'
            parts = transaction_id.split('|', 1)
            if len(parts) == 2:
                return parts[1]
        return transaction_id

    def insert_transaction(self, timestamp: int, transaction_id: str, amount: float) -> bool:
        """
        Insert transaction if canonical ID not seen before.
        Returns True if inserted, False if duplicate.
        """
        canonical_id = self._extract_canonical_id(transaction_id)

        # Check for duplicate
        if canonical_id in self.hash_index:
            return False

        # Record metadata in hash index
        appearance_idx = self.next_appearance_idx
        self.next_appearance_idx += 1

        metadata = TransactionMetadata(timestamp, appearance_idx, amount)
        self.hash_index[canonical_id] = metadata

        # Insert into time index
        self.time_index.insert(timestamp, canonical_id, appearance_idx)

        return True

    def query_range(self, start: int, end: int) -> List[str]:
        """
        Query transactions in [start, end] range.
        Returns canonical IDs ordered by appearance index.
        """
        # Get all matching transactions
        matches = self.time_index.range_query(start, end)

        # Sort by appearance index
        matches.sort(key=lambda x: x[1])

        # Extract canonical IDs
        return [canonical_id for canonical_id, _ in matches]


def process_transactions(transactions: List[List],
                         queries: List[List]) -> Dict[str, Any]:
    """
    Main entry point for temporal transaction processing.

    Args:
        transactions: List of [timestamp, transaction_id, amount] lists
        queries: List of [start_timestamp, end_timestamp] lists

    Returns:
        Dictionary with comprehensive metrics:
        - 'results': List of query results (lists of canonical IDs)
        - 'unique_count': Number of unique transactions processed
        - 'duplicate_count': Number of duplicate transactions ignored
        - 'branch_statistics': Stats about branch origins and merging
        - 'timestamp_statistics': Min/max/range of timestamps
        - 'amount_statistics': Financial amount analytics
        - 'query_statistics': Per-query metrics and coverage
        - 'tree_statistics': AVL tree balance and structure metrics
        - 'performance_metrics': Processing efficiency metrics
    """
    # Initialize temporal hash table
    table = TemporalHashTable()

    # Tracking variables for metrics
    duplicate_count = 0
    branch_map = {}  # Track transactions per branch
    timestamps = []
    amounts = []
    duplicate_branches = []

    # Process all transactions
    for txn in transactions:
        timestamp, transaction_id, amount = txn[0], txn[1], txn[2]

        # Track branch origin
        if '|' in transaction_id and transaction_id.startswith('B'):
            branch_id = transaction_id.split('|')[0]
            branch_map[branch_id] = branch_map.get(branch_id, 0) + 1

        inserted = table.insert_transaction(timestamp, transaction_id, amount)
        if not inserted:
            duplicate_count += 1
            duplicate_branches.append(transaction_id)
        else:
            timestamps.append(timestamp)
            amounts.append(amount)

    # Process all queries and collect statistics
    query_results = []
    query_stats = []

    for query in queries:
        start, end = query[0], query[1]
        result = table.query_range(start, end)
        query_results.append(result)

        # Calculate query-specific metrics
        if result:
            matching_amounts = [table.hash_index[tx_id].amount for tx_id in result]
            query_stat = {
                'range': [start, end],
                'result_count': len(result),
                'total_amount': sum(matching_amounts),
                'avg_amount': sum(matching_amounts) / len(matching_amounts),
                'min_amount': min(matching_amounts),
                'max_amount': max(matching_amounts)
            }
        else:
            query_stat = {
                'range': [start, end],
                'result_count': 0,
                'total_amount': 0.0,
                'avg_amount': 0.0,
                'min_amount': 0.0,
                'max_amount': 0.0
            }
        query_stats.append(query_stat)

    # Calculate tree statistics
    tree_stats = _calculate_tree_stats(table.time_index.root)

    # Build comprehensive response
    return {
        'results': query_results,
        'unique_count': len(table.hash_index),
        'duplicate_count': duplicate_count,
        'branch_statistics': {
            'branches_detected': len(branch_map),
            'transactions_per_branch': branch_map,
            'duplicate_sources': len(duplicate_branches),
            'merge_efficiency': round(len(table.hash_index) / len(transactions) * 100, 2) if transactions else 0.0
        },
        'timestamp_statistics': {
            'min_timestamp': min(timestamps) if timestamps else None,
            'max_timestamp': max(timestamps) if timestamps else None,
            'timestamp_range': max(timestamps) - min(timestamps) if timestamps else 0,
            'unique_timestamps': len(set(timestamps)) if timestamps else 0,
            'out_of_order_ratio': _calculate_out_of_order_ratio(transactions)
        },
        'amount_statistics': {
            'total_amount': sum(amounts),
            'average_amount': sum(amounts) / len(amounts) if amounts else 0.0,
            'min_amount': min(amounts) if amounts else 0.0,
            'max_amount': max(amounts) if amounts else 0.0,
            'amount_std_dev': _calculate_std_dev(amounts)
        },
        'query_statistics': {
            'total_queries': len(queries),
            'per_query_metrics': query_stats,
            'total_results_returned': sum(len(r) for r in query_results),
            'avg_results_per_query': sum(len(r) for r in query_results) / len(queries) if queries else 0.0,
            'empty_query_count': sum(1 for r in query_results if not r)
        },
        'tree_statistics': tree_stats,
        'performance_metrics': {
            'total_transactions_processed': len(transactions),
            'insertion_success_rate': round((len(table.hash_index) / len(transactions) * 100), 2) if transactions else 0.0,
            'deduplication_rate': round((duplicate_count / len(transactions) * 100), 2) if transactions else 0.0,
        }
    }


def _calculate_tree_stats(root: Optional[AVLNode]) -> Dict[str, Any]:
    """Calculate AVL tree statistics for performance monitoring."""
    if not root:
        return {
            'height': 0,
            'node_count': 0,
            'balance_factor_max': 0,
            'is_balanced': True,
            'leaf_count': 0
        }

    def traverse(node: Optional[AVLNode]) -> Tuple[int, int, int, int]:
        """Returns (height, node_count, max_balance, leaf_count)."""
        if not node:
            return (0, 0, 0, 0)

        left_stats = traverse(node.left)
        right_stats = traverse(node.right)

        height = 1 + max(left_stats[0], right_stats[0])
        node_count = 1 + left_stats[1] + right_stats[1]
        balance = abs(left_stats[0] - right_stats[0])
        max_balance = max(balance, left_stats[2], right_stats[2])

        is_leaf = (node.left is None and node.right is None)
        leaf_count = (1 if is_leaf else 0) + left_stats[3] + right_stats[3]

        return (height, node_count, max_balance, leaf_count)

    height, node_count, max_balance, leaf_count = traverse(root)

    return {
        'height': height,
        'node_count': node_count,
        'balance_factor_max': max_balance,
        'is_balanced': max_balance <= 1,
        'leaf_count': leaf_count,
        'theoretical_min_height': 0 if node_count == 0 else int(node_count ** 0.5),
        'balance_efficiency': round((1 - max_balance / 10) * 100, 2) if node_count > 0 else 100.0
    }


def _calculate_out_of_order_ratio(transactions: List[List]) -> float:
    """Calculate percentage of transactions arriving out of timestamp order."""
    if len(transactions) <= 1:
        return 0.0

    out_of_order = 0
    for i in range(1, len(transactions)):
        if transactions[i][0] < transactions[i-1][0]:
            out_of_order += 1

    return round((out_of_order / (len(transactions) - 1)) * 100, 2)


def _calculate_std_dev(values: List[float]) -> float:
    """Calculate standard deviation of values."""
    if not values:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return round(variance ** 0.5, 2)


# Example usage
if __name__ == "__main__":
    sample_transactions = [
        [1609459200, 'txA', 500.0],
        [1609459200, 'txB', 250.0],
        [1609462800, 'txC', 300.0],
        [1609480000, 'txD', 100.0]
    ]

    sample_queries = [
        [1609459000, 1609462800],
        [1609459200, 1609480000]
    ]

    result = process_transactions(sample_transactions, sample_queries)
    print(result)