# main.py
from typing import List, Dict, Any, Tuple
import heapq


class UnionFind:
    """Union-Find data structure for handling network partitions and connectivity."""

    def __init__(self, nodes: List[str]):
        self.parent = {node: node for node in nodes}
        self.rank = {node: 0 for node in nodes}

    def find(self, node: str) -> str:
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])  # Path compression
        return self.parent[node]

    def union(self, node1: str, node2: str) -> bool:
        root1, root2 = self.find(node1), self.find(node2)
        if root1 == root2:
            return False

        # Union by rank
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1
        return True

    def connected(self, node1: str, node2: str) -> bool:
        return self.find(node1) == self.find(node2)


class PriorityQueue:
    """Custom priority queue implementation using heapq."""

    def __init__(self):
        self._heap = []
        self._entry_finder = {}
        self._counter = 0
        self.REMOVED = '<removed-task>'

    def add_task(self, task, priority=0):
        """Add a new task or update the priority of an existing task."""
        if task in self._entry_finder:
            self.remove_task(task)
        entry = [priority, self._counter, task]
        self._entry_finder[task] = entry
        heapq.heappush(self._heap, entry)
        self._counter += 1

    def remove_task(self, task):
        """Mark an existing task as REMOVED."""
        entry = self._entry_finder.pop(task)
        entry[-1] = self.REMOVED

    def pop_task(self):
        """Remove and return the lowest priority task."""
        while self._heap:
            priority, count, task = heapq.heappop(self._heap)
            if task is not self.REMOVED:
                del self._entry_finder[task]
                return task, priority
        raise KeyError('pop from an empty priority queue')

    def empty(self) -> bool:
        return len(self._entry_finder) == 0


class NetworkGraph:
    """Graph representation of the network with bandwidth and latency constraints."""

    def __init__(self, branches: List[Dict[str, Any]], network_status: Dict[str, Any]):
        self.branches = {b['branch_id']: b for b in branches}
        self.latency_matrix = network_status.get('latency_matrix', {})
        self.adjacency = self._build_adjacency()
        self.available_bandwidth = {b['branch_id']: b['bandwidth'] for b in branches}

    def _build_adjacency(self) -> Dict[str, List[Tuple[str, int]]]:
        """Build adjacency list representation of the network."""
        adjacency = {branch_id: [] for branch_id in self.branches}

        for edge_key, latency in self.latency_matrix.items():
            # Parse edge key in format "src->dst"
            if '->' in edge_key:
                src, dst = edge_key.split('->')
                # Only add edges if both nodes exist in the branches
                if src in self.branches and dst in self.branches:
                    adjacency[src].append((dst, latency))
                    adjacency[dst].append((src, latency))  # Bidirectional

        return adjacency

    def dijkstra(self, source: str, target: str) -> Tuple[List[str], int]:
        """Find shortest path using Dijkstra's algorithm."""
        distances = {node: float('inf') for node in self.branches}
        distances[source] = 0
        previous = {}
        pq = PriorityQueue()
        pq.add_task(source, 0)

        while not pq.empty():
            current, current_dist = pq.pop_task()

            if current == target:
                break

            for neighbor, latency in self.adjacency[current]:
                distance = current_dist + latency

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    pq.add_task(neighbor, distance)

        # Reconstruct path
        if target not in previous and source != target:
            return [], float('inf')

        path = []
        current = target
        while current in previous:
            path.append(current)
            current = previous[current]
        path.append(source)
        path.reverse()

        return path, distances[target]

    def has_bandwidth(self, path: List[str], required_bandwidth: int) -> bool:
        """Check if path has sufficient bandwidth."""
        for node in path:
            if self.available_bandwidth[node] < required_bandwidth:
                return False
        return True

    def allocate_bandwidth(self, path: List[str], bandwidth: int):
        """Allocate bandwidth along a path."""
        for node in path:
            self.available_bandwidth[node] -= bandwidth


class RiskAssessment:
    """Handle risk assessment and dynamic adjustments."""

    def __init__(self, network_status: Dict[str, Any]):
        self.dynamic_risk_adjustments = network_status.get('dynamic_risk_adjustments', {})
        self.global_security_alert = network_status.get('global_security_alert', False)
        self.historical_incidents = {}
        self.anomaly_flags = {}

    def calculate_adjusted_risk(self, transaction: Dict[str, Any]) -> float:
        """Calculate adjusted risk score for a transaction."""
        base_risk = transaction['risk_score']
        branch_id = transaction['branch_id']

        # Apply dynamic risk adjustments
        dynamic_adjustment = self.dynamic_risk_adjustments.get(branch_id, 0)

        # Global security alert multiplier
        global_multiplier = 1.1 if self.global_security_alert else 1.0

        # Historical incident factor
        historical_factor = self.historical_incidents.get(branch_id, 0)

        # Anomaly detection factor
        anomaly_factor = self.anomaly_flags.get(branch_id, 0)

        adjusted_risk = (base_risk + dynamic_adjustment + historical_factor + anomaly_factor) * global_multiplier

        return min(adjusted_risk, 100.0)  # Cap at 100


class KeyDistributionOptimizer:
    """Main optimizer for key distribution."""

    def __init__(self, branches: List[Dict[str, Any]], network_status: Dict[str, Any]):
        self.network = NetworkGraph(branches, network_status)
        self.risk_assessor = RiskAssessment(network_status)
        self.union_find = UnionFind([b['branch_id'] for b in branches])
        self.allocated_transactions = []

    def _calculate_transaction_priority(self, transaction: Dict[str, Any]) -> float:
        """Calculate priority for transaction (lower value = higher priority)."""
        adjusted_risk = self.risk_assessor.calculate_adjusted_risk(transaction)

        # Higher risk = higher priority (lower priority value)
        priority = 100.0 - adjusted_risk

        return priority

    def _find_optimal_path(self, source: str, target: str, bandwidth_req: int) -> Tuple[List[str], bool]:
        """Find optimal path considering bandwidth and latency constraints."""
        if source == target:
            if self.network.available_bandwidth[source] >= bandwidth_req:
                return [source], True
            return [], False

        # Check if nodes are connected
        if not self.union_find.connected(source, target):
            return [], False

        path, latency = self.network.dijkstra(source, target)

        if not path or latency == float('inf'):
            return [], False

        # Check bandwidth availability
        if self.network.has_bandwidth(path, bandwidth_req):
            return path, True

        return [], False

    def _calculate_bandwidth_requirement(self, transaction: Dict[str, Any]) -> int:
        """Calculate bandwidth requirement based on transaction risk."""
        base_bandwidth = 10  # Base bandwidth requirement
        risk_multiplier = transaction['risk_score'] / 100.0

        # Higher risk transactions require more bandwidth for security
        return int(base_bandwidth * (1 + risk_multiplier))

    def _evaluate_path_security(self, path: List[str], transaction: Dict[str, Any]) -> float:
        """Evaluate security score of a path."""
        if not path:
            return 0.0

        security_score = 0.0

        for node in path:
            branch_info = self.network.branches[node]

            # Lower failure probability = higher security
            node_security = 1.0 - branch_info['failure_probability']

            # Apply dynamic risk adjustments
            dynamic_risk = self.risk_assessor.dynamic_risk_adjustments.get(node, 0)
            node_security -= dynamic_risk / 100.0

            security_score += max(node_security, 0.0)

        return security_score / len(path)  # Average security across path

    def optimize_distribution(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Main optimization function."""

        # Initialize network connectivity using Union-Find
        for edge_key in self.network.latency_matrix.keys():
            # Parse edge key in format "src->dst"
            if '->' in edge_key:
                src, dst = edge_key.split('->')
                # Only connect nodes that exist in the branches
                if src in self.network.branches and dst in self.network.branches:
                    self.union_find.union(src, dst)

        # Create priority queue for transactions
        transaction_queue = PriorityQueue()

        # Calculate priorities and add to queue
        for i, transaction in enumerate(transactions):
            priority = self._calculate_transaction_priority(transaction)
            transaction_queue.add_task(i, priority)

        results = []
        allocated_count = 0

        # Process transactions in priority order
        while not transaction_queue.empty():
            transaction_idx, priority = transaction_queue.pop_task()
            transaction = transactions[transaction_idx]

            branch_id = transaction['branch_id']
            bandwidth_req = self._calculate_bandwidth_requirement(transaction)

            # For transactions at the source branch
            if branch_id in self.network.branches:
                path, can_allocate = self._find_optimal_path('HQ', branch_id, bandwidth_req)

                if can_allocate and path:
                    # Evaluate path security
                    security_score = self._evaluate_path_security(path, transaction)

                    # Only allocate if security meets threshold
                    min_security_threshold = 0.7
                    if security_score >= min_security_threshold:
                        # Allocate bandwidth
                        self.network.allocate_bandwidth(path, bandwidth_req)
                        allocated_count += 1

                        results.append({
                            'transaction_id': transaction['transaction_id'],
                            'allocated': True,
                            'path_taken': path
                        })
                    else:
                        results.append({
                            'transaction_id': transaction['transaction_id'],
                            'allocated': False,
                            'path_taken': []
                        })
                else:
                    results.append({
                        'transaction_id': transaction['transaction_id'],
                        'allocated': False,
                        'path_taken': []
                    })
            else:
                # Unknown branch
                results.append({
                    'transaction_id': transaction['transaction_id'],
                    'allocated': False,
                    'path_taken': []
                })

        return results


def optimize_key_distribution(transactions: List[Dict[str, Any]],
                              branches: List[Dict[str, Any]],
                              network_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Optimize key distribution across network branches using advanced algorithms.

    This function implements a multi-stage optimization approach that:
    1. Uses priority queues to handle transaction prioritization based on risk scores
    2. Employs Union-Find for network connectivity management
    3. Implements Dijkstra's algorithm for shortest path routing
    4. Includes dynamic risk assessment with real-time adjustments
    5. Manages bandwidth allocation and constraint satisfaction
    6. Evaluates path security for optimal routing decisions

    Args:
        transactions: List of transaction dictionaries with id, branch_id, and risk_score
        branches: List of branch dictionaries with id, bandwidth, and failure_probability
        network_status: Dictionary containing latency_matrix, dynamic_risk_adjustments,
                       and global_security_alert status

    Returns:
        List of allocation results with transaction_id, allocated status, and path_taken
    """

    # Input validation
    if not transactions or not branches:
        return []

    # Validate transaction format
    for transaction in transactions:
        if not all(key in transaction for key in ['transaction_id', 'branch_id', 'risk_score']):
            raise ValueError(f"Transaction missing required fields: {transaction}")
        if not isinstance(transaction['risk_score'], (int, float)):
            raise TypeError(f"risk_score must be numeric: {transaction['risk_score']}")

    # Validate branch format
    for branch in branches:
        if not all(key in branch for key in ['branch_id', 'bandwidth', 'failure_probability']):
            raise ValueError(f"Branch missing required fields: {branch}")

    # Initialize optimizer
    optimizer = KeyDistributionOptimizer(branches, network_status)

    # Run optimization
    results = optimizer.optimize_distribution(transactions)

    # Sort results by transaction_id for consistent output
    results.sort(key=lambda x: x['transaction_id'])

    return results


# Example usage and testing
if __name__ == "__main__":
    transactions = [
        {'transaction_id': 101, 'branch_id': 'HQ', 'risk_score': 95},
        {'transaction_id': 102, 'branch_id': 'R1', 'risk_score': 78},
        {'transaction_id': 103, 'branch_id': 'R2', 'risk_score': 88},
        {'transaction_id': 104, 'branch_id': 'R1', 'risk_score': 65},
        {'transaction_id': 105, 'branch_id': 'R3', 'risk_score': 93}
    ]

    branches = [
        {'branch_id': 'HQ', 'bandwidth': 200, 'failure_probability': 0.005},
        {'branch_id': 'R1', 'bandwidth': 100, 'failure_probability': 0.013},
        {'branch_id': 'R2', 'bandwidth': 150, 'failure_probability': 0.009},
        {'branch_id': 'R3', 'bandwidth': 120, 'failure_probability': 0.011}
    ]

    network_status = {
        'latency_matrix': {
            'HQ->R1': 10,
            'HQ->R2': 15,
            'HQ->R3': 20,
            'R1->R2': 12,
            'R2->R3': 18,
            'R1->R3': 16
        },
        'dynamic_risk_adjustments': {
            'HQ': 2,
            'R1': 5,
            'R2': 0,
            'R3': 3
        },
        'global_security_alert': True
    }

    result = optimize_key_distribution(transactions, branches, network_status)
    print(result)