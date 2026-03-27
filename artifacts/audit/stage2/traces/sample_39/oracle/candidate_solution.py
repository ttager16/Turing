from typing import List, Dict, Any, Set
from collections import defaultdict


class SegmentTree:
    """Segment tree for range queries on transaction attributes with incremental updates."""
    
    def __init__(self, initial_capacity: int = 1000, operation=max):
        self.capacity = initial_capacity
        self.operation = operation
        self.tree = [0] * (4 * self.capacity)
        self.size = 0
    
    def add_value(self, value: float):
        """Add a new value incrementally."""
        if self.size >= self.capacity:
            self._expand_capacity()
        self._insert_at_position(0, 0, self.capacity - 1, self.size, value)
        self.size += 1
    
    def _expand_capacity(self):
        """Double the capacity when needed."""
        self.capacity *= 2
        new_tree = [0] * (4 * self.capacity)
        new_tree[:len(self.tree)] = self.tree
        self.tree = new_tree
    
    def _insert_at_position(self, node: int, start: int, end: int, idx: int, value: float):
        """Insert value at position idx."""
        if start == end:
            if start == idx:
                self.tree[node] = value
        else:
            mid = (start + end) // 2
            if idx <= mid:
                self._insert_at_position(2 * node + 1, start, mid, idx, value)
            else:
                self._insert_at_position(2 * node + 2, mid + 1, end, idx, value)
            
            left_val = self.tree[2 * node + 1] if 2 * node + 1 < len(self.tree) else (float('-inf') if self.operation is max else float('inf'))
            right_val = self.tree[2 * node + 2] if 2 * node + 2 < len(self.tree) else (float('-inf') if self.operation is max else float('inf'))
            self.tree[node] = self.operation(left_val, right_val)
    
    def query(self, node: int, start: int, end: int, l: int, r: int) -> float:
        """Query range [l, r] for the operation result."""
        return self._query_internal(node, start, end, l, r)
    
    def _query_internal(self, node: int, start: int, end: int, l: int, r: int) -> float:
        if r < start or end < l or r >= self.size:
            return float('-inf') if self.operation is max else float('inf')
        if l <= start and end <= r:
            return self.tree[node]
        mid = (start + end) // 2
        left = self._query_internal(2 * node + 1, start, mid, l, r)
        right = self._query_internal(2 * node + 2, mid + 1, end, l, r)
        return self.operation(left, right)
    
    def get_percentile(self, percentile: float) -> float:
        """Get approximate percentile value from the tree."""
        if self.size == 0:
            return 0.0
        # Simple approximation - query max in range
        idx = int(self.size * percentile)
        if idx >= self.size:
            idx = self.size - 1
        return self.query(0, 0, self.capacity - 1, 0, idx)
    
    def update(self, node: int, start: int, end: int, idx: int, value: float):
        if start == end:
            self.tree[node] = value
        else:
            mid = (start + end) // 2
            if idx <= mid:
                self.update(2 * node + 1, start, mid, idx, value)
            else:
                self.update(2 * node + 2, mid + 1, end, idx, value)
            self.tree[node] = self.operation(
                self.tree[2 * node + 1], 
                self.tree[2 * node + 2]
            )


class GraphNode:
    """Node in the multi-graph representing an account or entity."""
    
    def __init__(self, account_id: str, account_type: str = "unknown"):
        self.account_id = account_id
        self.account_type = account_type
        self.cumulative_amount = 0.0
        self.transaction_count = 0
        self.suspiciousness_index = 0.0
        self.last_transaction_time = 0
        self.regions = set()
        self.connected_accounts = set()
        self.incoming_edges = []
        self.outgoing_edges = []
    
    def update_metrics(self, amount: float, timestamp: int, region: str, update_time: bool = True):
        self.cumulative_amount += amount
        self.transaction_count += 1
        if update_time:
            self.last_transaction_time = max(self.last_transaction_time, timestamp)
        self.regions.add(region)
        self.suspiciousness_index = self._calculate_suspiciousness()
    
    def _calculate_suspiciousness(self) -> float:
        """Calculate suspiciousness based on multiple factors."""
        base_score = 0.0
        
        # High transaction frequency
        if self.transaction_count > 10:
            base_score += 0.3
        
        # High cumulative amount
        if self.cumulative_amount > 50000:
            base_score += 0.4
        
        # Multiple regions
        if len(self.regions) > 2:
            base_score += 0.2
        
        # High connectivity
        if len(self.connected_accounts) > 5:
            base_score += 0.1
        
        # Account type risk factors
        if self.account_type in ["business", "corporate"]:
            base_score += 0.05
        elif self.account_type == "new":
            base_score += 0.15
        
        return min(base_score, 1.0)


class GraphEdge:
    """Edge in the multi-graph representing a transaction."""
    
    def __init__(self, transaction_id: str, sender: str, receiver: str, 
                 amount: float, timestamp: int, region: str, account_type: str = "unknown"):
        self.transaction_id = transaction_id
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.timestamp = timestamp
        self.region = region
        self.account_type = account_type
        self.suspiciousness = 0.0
        self.prev_sender_time = 0
        self.sender_regions_snapshot = set()
        self.original_data = {
            "transaction_id": transaction_id,
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "timestamp": timestamp,
            "region": region,
            "account_type": account_type
        }
    
    def calculate_suspiciousness(self, sender_node: GraphNode, receiver_node: GraphNode, 
                                amount_threshold: float = 0.0) -> float:
        """Calculate edge suspiciousness based on node states and transaction properties."""
        score = 0.0
        
        # High amount transactions - only for truly high amounts
        if self.amount > 15000:
            score += 0.4
        
        # Outlier detection using threshold - only for significant amounts
        if amount_threshold > 0 and self.amount > max(amount_threshold, 5000):
            score += 0.3
        
        # Cross-region transactions - only for significant amounts
        if self.region not in sender_node.regions and self.amount > 2000:
            score += 0.2
        
        # Rapid successive transactions - only for high amounts
        if sender_node.last_transaction_time > 0 and self.amount > 1000:
            time_diff = self.timestamp - sender_node.last_transaction_time
            if time_diff < 180:  # Less than 3 minutes
                score += 0.3
        
        # Both nodes are suspicious - require high amounts
        if (sender_node.suspiciousness_index > 0.5 and receiver_node.suspiciousness_index > 0.5 
            and self.amount > 2000):
            score += 0.4
        
        # Account type mismatch or high-risk types - require significant amounts
        if self.account_type in ["new", "business"] and self.amount > 5000:
            score += 0.2
        
        return min(score, 1.0)


class DynamicMultiGraph:
    """Dynamic multi-graph for fraud detection."""
    
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self.adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.amount_segment_tree = SegmentTree(operation=max)
        self.timestamp_segment_tree = SegmentTree(operation=max)
        self.transaction_list = []
    
    def add_transaction(self, tx_data: Dict[str, Any]) -> GraphEdge:
        """Add a new transaction to the graph."""
        account_type = tx_data.get("account_type", "unknown")
        
        edge = GraphEdge(
            tx_data["transaction_id"],
            tx_data["sender"],
            tx_data["receiver"],
            tx_data["amount"],
            tx_data["timestamp"],
            tx_data["region"],
            account_type
        )
        
        # Update or create nodes
        sender_id = tx_data["sender"]
        receiver_id = tx_data["receiver"]
        
        if sender_id not in self.nodes:
            self.nodes[sender_id] = GraphNode(sender_id, account_type)
        if receiver_id not in self.nodes:
            self.nodes[receiver_id] = GraphNode(receiver_id, account_type)
        
        # Get amount threshold for outlier detection BEFORE updating metrics
        amount_threshold = self.amount_segment_tree.get_percentile(0.9)
        
        # Snapshot sender's previous timestamp before updating node metrics
        edge.prev_sender_time = self.nodes[sender_id].last_transaction_time
        # Snapshot sender's known regions before this transaction
        edge.sender_regions_snapshot = set(self.nodes[sender_id].regions)
        # Calculate edge suspiciousness BEFORE updating node metrics
        # This ensures cross-region and temporal checks work correctly
        edge.suspiciousness = edge.calculate_suspiciousness(
            self.nodes[sender_id], 
            self.nodes[receiver_id],
            amount_threshold
        )
        
        # Update segment trees incrementally
        self._update_segment_trees(tx_data)
        
        # update node metrics AFTER suspiciousness calculation
        self.nodes[sender_id].update_metrics(
            tx_data["amount"], 
            tx_data["timestamp"], 
            tx_data["region"]
        )
        self.nodes[receiver_id].update_metrics(
            tx_data["amount"], 
            tx_data["timestamp"], 
            tx_data["region"]
        )
        
        # Add edge to graph
        self.edges[edge.transaction_id] = edge
        self.adjacency_list[sender_id].add(receiver_id)
        self.reverse_adjacency_list[receiver_id].add(sender_id)
        
        # Update connected accounts and edge lists
        self.nodes[sender_id].connected_accounts.add(receiver_id)
        self.nodes[receiver_id].connected_accounts.add(sender_id)
        self.nodes[sender_id].outgoing_edges.append(edge)
        self.nodes[receiver_id].incoming_edges.append(edge)
        
        return edge

    def _update_segment_trees(self, tx_data: Dict[str, Any]):
        """Update segment trees incrementally with new transaction data."""
        self.transaction_list.append(tx_data)
        
        # Incrementally add to segment trees
        self.amount_segment_tree.add_value(tx_data["amount"])
        self.timestamp_segment_tree.add_value(tx_data["timestamp"])
    
    def find_suspicious_patterns(self) -> List[GraphEdge]:
        """Find suspicious patterns using SCC detection, DP, and segment tree analysis."""
        suspicious_edges = []
        
        # Get outlier thresholds from segment trees
        amount_threshold = self.amount_segment_tree.get_percentile(0.85)
        
        # Find strongly connected components
        sccs = self._tarjan_scc()
        
        # Analyze each SCC for suspicious patterns
        for scc in sccs:
            if len(scc) > 1:  # Only analyze non-trivial SCCs
                scc_suspicious = self._analyze_scc_patterns(scc)
                suspicious_edges.extend(scc_suspicious)
        
        # Find high-value individual transactions using segment tree thresholds
        high_value_edges = self._find_high_value_transactions(amount_threshold)
        suspicious_edges.extend(high_value_edges)
        
        # Find outliers using segment tree analysis
        outlier_edges = self._find_outlier_transactions(amount_threshold)
        suspicious_edges.extend(outlier_edges)
        
        # Remove duplicates
        seen = set()
        unique_suspicious = []
        for edge in suspicious_edges:
            if edge.transaction_id not in seen:
                seen.add(edge.transaction_id)
                unique_suspicious.append(edge)
        
        return unique_suspicious
    
    def _tarjan_scc(self) -> List[List[str]]:
        """Tarjan's algorithm for finding strongly connected components."""
        index = 0
        stack = []
        indices = {}
        lowlinks = {}
        on_stack = set()
        sccs = []
        
        def strongconnect(node):
            nonlocal index
            indices[node] = index
            lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            
            for neighbor in self.adjacency_list[node]:
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[neighbor])
            
            if lowlinks[node] == indices[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(scc)
        
        for node in self.nodes:
            if node not in indices:
                strongconnect(node)
        
        return sccs
    
    def _analyze_scc_patterns(self, scc: List[str]) -> List[GraphEdge]:
        """Analyze patterns within a strongly connected component using DP."""
        suspicious_edges = []
        
        # Use DP to find suspicious paths within the SCC
        dp_cache = {}
        
        def find_suspicious_paths(node: str, visited: Set[str], depth: int) -> List[GraphEdge]:
            if depth > 3:  # Limit recursion depth
                return []
            
            if (node, tuple(sorted(visited))) in dp_cache:
                return dp_cache[(node, tuple(sorted(visited)))]
            
            suspicious = []
            visited.add(node)
            
            for neighbor in self.adjacency_list[node]:
                if neighbor in scc and neighbor not in visited:
                    # Check if this edge is suspicious
                    for edge in self.edges.values():
                        if (edge.sender == node and edge.receiver == neighbor and 
                            edge.suspiciousness > 0.6):
                            suspicious.append(edge)
                    
                    # Recursively find paths from neighbor
                    sub_suspicious = find_suspicious_paths(neighbor, visited.copy(), depth + 1)
                    suspicious.extend(sub_suspicious)
            
            dp_cache[(node, tuple(sorted(visited)))] = suspicious
            return suspicious
        
        # Analyze each node in the SCC
        for node in scc:
            paths = find_suspicious_paths(node, set(), 0)
            suspicious_edges.extend(paths)
        
        return suspicious_edges
    
    def _find_high_value_transactions(self, amount_threshold: float) -> List[GraphEdge]:
        """Find high-value transactions that might be fraudulent using dynamic thresholds."""
        suspicious_edges = []
        
        for edge in self.edges.values():
            sender_node = self.nodes[edge.sender]
            
            # High amount threshold (dynamic based on segment tree) - only for truly high amounts
            if edge.amount > max(10000, amount_threshold):
                suspicious_edges.append(edge)
            
            # Cross-region transactions with significant amounts - require higher threshold
            if (len(edge.sender_regions_snapshot) > 0 and edge.region not in edge.sender_regions_snapshot and edge.amount > 5000):
                suspicious_edges.append(edge)
            
            # Rapid successive high amounts - require both high amount and rapid succession
            if (sender_node.transaction_count > 1 and 
                sender_node.cumulative_amount > 50000 and
                edge.amount > 5000):
                suspicious_edges.append(edge)
            
            # Chain transactions: receiving and immediately sending larger amounts - require significant amounts
            if (len(sender_node.incoming_edges) > 0 and 
                edge.amount > 5000 and
                any(incoming.amount < edge.amount for incoming in sender_node.incoming_edges)):
                suspicious_edges.append(edge)
            
            # High-value transactions in general - only flag truly high amounts
            if edge.amount > 10000:
                suspicious_edges.append(edge)
            
            # Account type specific checks - absolute threshold (> $5,000)
            if edge.account_type in ["new", "business"] and edge.amount > 5000:
                suspicious_edges.append(edge)
        
        return suspicious_edges
    
    def _find_outlier_transactions(self, amount_threshold: float) -> List[GraphEdge]:
        """Find outlier transactions using segment tree analysis."""
        suspicious_edges = []
        
        for edge in self.edges.values():
            # Check if amount is an outlier - only for significant amounts
            if edge.amount > max(amount_threshold, 5000):
                suspicious_edges.append(edge)
            
            # Check for temporal anomalies using the sender's immediate prior timestamp snapshot
            if edge.prev_sender_time > 0 and edge.amount > 2000:
                time_diff = edge.timestamp - edge.prev_sender_time
                if 0 <= time_diff < 60:  # Very rapid transactions (less than 1 minute)
                    suspicious_edges.append(edge)
            # General rapid succession rule (< 180s for amounts > $1,000)
            if edge.prev_sender_time > 0 and edge.amount > 1000:
                time_diff = edge.timestamp - edge.prev_sender_time
                if 0 <= time_diff < 180:
                    suspicious_edges.append(edge)
        
        return suspicious_edges



class FraudDetector:
    """Main fraud detection system."""
    
    def __init__(self):
        self.graph = DynamicMultiGraph()
    
    def detect_fraudulent_activity(self, tx_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Main fraud detection function."""
        fraudulent_transactions = []
        
        # Process each transaction
        for tx in tx_data:
            self.graph.add_transaction(tx)
        
        # Find suspicious patterns
        suspicious_edges = self.graph.find_suspicious_patterns()
        
        # Convert to required output format in input order
        suspicious_ids = {e.transaction_id for e in suspicious_edges}
        for tx in tx_data:
            if tx["transaction_id"] in suspicious_ids:
                fraud_result = tx.copy()
                if "account_type" not in fraud_result:
                    fraud_result["account_type"] = "unknown"
                fraud_result["fraudulent"] = True
                fraudulent_transactions.append(fraud_result)
        
        return fraudulent_transactions
    


def detect_fraudulent_activity(transaction_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect fraudulent activity using advanced multi-graph analysis and segment trees.
    
    Args:
        transaction_data: List of transaction dictionaries with keys:
            - transaction_id: str
            - sender: str  
            - receiver: str
            - amount: float
            - timestamp: int
            - region: str
    
    Returns:
        List of transaction dictionaries with 'fraudulent' key set to True
    """
    detector = FraudDetector()
    return detector.detect_fraudulent_activity(transaction_data)


if __name__ == "__main__":
    # Sample Usage
    tx_data = [
    {"transaction_id": "t1", "sender": "A", "receiver": "B", "amount": 100, "timestamp": 1630245600, "region": "US", "account_type": "personal"},
    {"transaction_id": "t2", "sender": "C", "receiver": "D", "amount": 15000, "timestamp": 1630249200, "region": "APAC", "account_type": "new"},
    {"transaction_id": "t3", "sender": "E", "receiver": "F", "amount": 12000, "timestamp": 1630252800, "region": "EU", "account_type": "business"},
    {"transaction_id": "t4", "sender": "G", "receiver": "H", "amount": 250, "timestamp": 1630256400, "region": "US", "account_type": "personal"}
    ]
    
    fraud_result = detect_fraudulent_activity(tx_data)
    print("Detected fraudulent transactions:")
    for tx in fraud_result:
        print(tx)