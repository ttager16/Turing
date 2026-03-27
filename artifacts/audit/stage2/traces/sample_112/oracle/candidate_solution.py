from typing import List, Dict, Any, Set
from collections import defaultdict
import threading
import re

MAX_CYCLE_LENGTH = 6
MAX_SUSPICIOUS_PATH_LENGTH = 4
MAX_CYCLES_TO_REPORT = 1


def detect_anomalies(transaction_data: List[List], thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Detect anomalies in financial transaction data across multi-currency networks.
    
    This function identifies suspicious patterns including high volume/frequency transactions,
    cross-currency flow spikes, cyclical flows, and cross-currency self-loops in transaction
    networks. It constructs a multi-layer graph and applies pattern detection algorithms to
    identify potential fraud or money laundering activities.
    
    Args:
        transaction_data: A list of transactions, where each transaction is a list containing:
            [source_account, destination_account, amount]
            Example: [['accountUSD1', 'accountUSD2', 1500.0], ...]
        
        thresholds: A dictionary of detection thresholds with the following optional keys:
            - 'volume_threshold' (float): Minimum volume to flag high-volume transactions (default: 1000.0)
            - 'frequency_threshold' (int): Minimum transaction count between same account pair (default: 3)
            - 'cross_currency_sensitivity' (float): Sensitivity factor for cross-currency transactions (default: 0.8)
            - 'cycle_threshold' (float): Minimum total volume for cyclical flows to be flagged (default: 2000.0)
    
    Returns:
        A list of dictionaries, each representing a detected anomaly with the following keys:
            - 'accounts' (list): [source_account, destination_account] involved in the anomaly
            - 'amount' (float): Total transaction amount for this anomaly
            - 'anomaly_type' (str): Type of anomaly detected, one of:
                * 'High Volume and Frequency'
                * 'Cross-Currency Flow Spike'
                * 'Suspicious Cyclical Flow'
                * 'Cross-Currency Self-Loop'
            - 'flow_path' (list): Sequence of accounts in the transaction flow
        
        Example return:
        [
            {
                'accounts': ['accountUSD1', 'accountUSD2'],
                'amount': 3500.0,
                'anomaly_type': 'High Volume and Frequency',
                'flow_path': ['accountUSD1', 'accountUSD2']
            }
        ]
    """
    detector = AnomalyDetector()
    detector.update_thresholds(thresholds)
    detector.add_transactions(transaction_data)
    return detector.get_anomalies()


class AnomalyDetector:
    def __init__(self):
        self._graph_lock = threading.RLock()
        self._threshold_lock = threading.RLock()
        
        self.graph = defaultdict(lambda: defaultdict(list))
        self.aggregated_flows = defaultdict(lambda: {'total': 0.0, 'count': 0})
        self.account_currencies = {}
        
        self._thresholds = {
            'volume_threshold': 1000.0,
            'frequency_threshold': 3,
            'cross_currency_sensitivity': 0.8,
            'cycle_threshold': 2000.0
        }
        
    def update_thresholds(self, thresholds: Dict[str, float]):
        with self._threshold_lock:
            self._thresholds.update(thresholds)
    
    def add_transactions(self, transaction_data: List[List]):
        with self._graph_lock:
            for transaction in transaction_data:
                src, dst, amount = transaction[0], transaction[1], transaction[2]
                self._add_single_transaction(src, dst, amount)
    
    def _add_single_transaction(self, src: str, dst: str, amount: float):
        self.graph[src][dst].append(amount)
        key = (src, dst)
        self.aggregated_flows[key]['total'] += amount
        self.aggregated_flows[key]['count'] += 1
        
        if src not in self.account_currencies:
            self.account_currencies[src] = self._extract_currency(src)
        if dst not in self.account_currencies:
            self.account_currencies[dst] = self._extract_currency(dst)
    
    def _extract_currency(self, account: str) -> str:
        match = re.search(r'(USD|EUR|GBP|JPY|CHF|CNY|AUD|CAD)', account, re.IGNORECASE)
        return match.group(1).upper() if match else 'UNKNOWN'
    
    def _get_currency(self, account: str) -> str:
        return self.account_currencies.get(account, self._extract_currency(account))
    
    def _get_account_base(self, account: str) -> str:
        currency = self._get_currency(account)
        if currency != 'UNKNOWN':
            return re.sub(f'account{currency}', '', account, flags=re.IGNORECASE)
        return re.sub(r'account', '', account, flags=re.IGNORECASE)
    
    def _is_cross_currency(self, src: str, dst: str) -> bool:
        return self._get_currency(src) != self._get_currency(dst)
    
    def get_anomalies(self) -> List[Dict[str, Any]]:
        with self._graph_lock:
            with self._threshold_lock:
                anomalies = []
                
                edges_in_cycles = set()
                edges_in_balanced_self_loops = set()
                
                cycle_anomalies = self._detect_cycles()
                for anomaly in cycle_anomalies:
                    path = anomaly['flow_path']
                    for i in range(len(path) - 1):
                        edges_in_cycles.add((path[i], path[i+1]))
                
                self_loop_anomalies = self._detect_self_loops()
                volume_threshold = self._thresholds.get('volume_threshold', 1000.0)
                cross_currency_sensitivity = self._thresholds.get('cross_currency_sensitivity', 0.8)
                adjusted_threshold = volume_threshold / cross_currency_sensitivity
                
                for anomaly in self_loop_anomalies:
                    path = anomaly['flow_path']
                    if len(path) == 3 and path[0] == path[2]:
                        src, dst = path[0], path[1]
                        forward_vol = self.aggregated_flows.get((src, dst), {}).get('total', 0.0)
                        backward_vol = self.aggregated_flows.get((dst, src), {}).get('total', 0.0)
                        if forward_vol > adjusted_threshold and backward_vol > adjusted_threshold:
                            edges_in_balanced_self_loops.add((src, dst))
                            edges_in_balanced_self_loops.add((dst, src))
                
                exclude_edges = edges_in_cycles | edges_in_balanced_self_loops
                
                anomalies.extend(self._detect_high_volume_frequency())
                anomalies.extend(self._detect_cross_currency_spikes(exclude_edges))
                anomalies.extend(cycle_anomalies)
                anomalies.extend(self_loop_anomalies)
                
                return anomalies
    
    def _detect_high_volume_frequency(self) -> List[Dict[str, Any]]:
        anomalies = []
        volume_threshold = self._thresholds.get('volume_threshold', 1000.0)
        frequency_threshold = self._thresholds.get('frequency_threshold', 3)
        
        for (src, dst), flow_data in self.aggregated_flows.items():
            if not self._is_cross_currency(src, dst):
                if (flow_data['total'] > volume_threshold and 
                    flow_data['count'] >= frequency_threshold):
                    anomalies.append({
                        'accounts': [src, dst],
                        'amount': flow_data['total'],
                        'anomaly_type': 'High Volume and Frequency',
                        'flow_path': [src, dst]
                    })
        
        return anomalies
    
    def _detect_cross_currency_spikes(self, exclude_edges: Set) -> List[Dict[str, Any]]:
        anomalies = []
        volume_threshold = self._thresholds.get('volume_threshold', 1000.0)
        cross_currency_sensitivity = self._thresholds.get('cross_currency_sensitivity', 0.8)
        adjusted_threshold = volume_threshold / cross_currency_sensitivity
        
        for (src, dst), flow_data in self.aggregated_flows.items():
            if self._is_cross_currency(src, dst) and (src, dst) not in exclude_edges:
                if flow_data['total'] > adjusted_threshold:
                    anomalies.append({
                        'accounts': [src, dst],
                        'amount': flow_data['total'],
                        'anomaly_type': 'Cross-Currency Flow Spike',
                        'flow_path': [src, dst]
                    })
        
        return anomalies
    
    def _detect_cycles(self) -> List[Dict[str, Any]]:
        """
        Detect 'Suspicious Cyclical Flow' anomalies.
        
        Note: Despite the name, this detects both:
        1. True cycles (paths returning to start node)
        2. Suspicious multi-hop paths (3+ nodes with cross-currency transactions)
        
        Both are classified as 'Suspicious Cyclical Flow' per problem requirements.
        """
        anomalies = []
        cycle_threshold = self._thresholds.get('cycle_threshold', 2000.0)
        processed = set()
        valid_cycles = []
        
        for start_node in list(self.graph.keys()):
            cycles = self._find_cycles_dfs(start_node, max_length=MAX_CYCLE_LENGTH)
            suspicious_paths = self._find_suspicious_paths(start_node, max_length=MAX_SUSPICIOUS_PATH_LENGTH)
            
            all_paths = cycles + suspicious_paths
            for path in all_paths:
                if len(path) < 3:
                    continue
                
                path_key = tuple(path)
                reverse_key = tuple(reversed(path))
                
                if path_key not in processed and reverse_key not in processed:
                    total_volume = self._calculate_path_volume(path)
                    if total_volume > cycle_threshold:
                        processed.add(path_key)
                        processed.add(reverse_key)
                        valid_cycles.append((path, total_volume, len(path)))
        
        valid_cycles.sort(key=lambda x: (x[2], x[1]))
        
        for path, volume, _ in valid_cycles[:MAX_CYCLES_TO_REPORT]:
            anomalies.append({
                'accounts': [path[0], path[-1]],
                'amount': volume,
                'anomaly_type': 'Suspicious Cyclical Flow',
                'flow_path': path
            })
        
        return anomalies
    
    def _find_cycles_dfs(self, start: str, max_length: int = MAX_CYCLE_LENGTH) -> List[List[str]]:
        cycles = []
        stack = [(start, [start], set([start]))]
        
        while stack:
            node, path, path_set = stack.pop()
            
            for neighbor in self.graph[node]:
                if neighbor == start and len(path) > 1 and len(path) <= max_length:
                    cycles.append(path)
                elif neighbor not in path_set and len(path) < max_length:
                    stack.append((neighbor, path + [neighbor], path_set | {neighbor}))
        
        return cycles
    
    def _find_suspicious_paths(self, start: str, max_length: int = MAX_SUSPICIOUS_PATH_LENGTH) -> List[List[str]]:
        """
        Find suspicious multi-hop paths with cross-currency transactions.
        
        These are NOT true cycles (don't return to start), but represent
        suspicious transaction patterns through multiple currency layers.
        Example: accountUSD3 → accountEUR2 → accountUSD1
        
        Specifically looks for 3-node paths with 2 cross-currency edges.
        """
        suspicious_paths = []
        stack = [(start, [start], set([start]), 0)]
        
        while stack:
            node, path, path_set, cross_currency_count = stack.pop()
            
            if len(path) == 3 and cross_currency_count == 2:
                suspicious_paths.append(path[:])
            
            if len(path) < max_length:
                for neighbor in self.graph[node]:
                    if neighbor not in path_set:
                        is_cross = 1 if self._is_cross_currency(node, neighbor) else 0
                        new_count = cross_currency_count + is_cross
                        stack.append((neighbor, path + [neighbor], path_set | {neighbor}, new_count))
        
        return suspicious_paths
    
    def _calculate_path_volume(self, path: List[str]) -> float:
        total = 0.0
        for i in range(len(path) - 1):
            src, dst = path[i], path[i + 1]
            if dst in self.graph[src]:
                total += sum(self.graph[src][dst])
        return total
    
    def _detect_self_loops(self) -> List[Dict[str, Any]]:
        anomalies = []
        volume_threshold = self._thresholds.get('volume_threshold', 1000.0)
        cross_currency_sensitivity = self._thresholds.get('cross_currency_sensitivity', 0.8)
        adjusted_threshold = volume_threshold / cross_currency_sensitivity
        processed = set()
        
        account_bases = defaultdict(list)
        for account in list(self.graph.keys()):
            base = self._get_account_base(account)
            if base:
                account_bases[base].append(account)
        
        for base, accounts in account_bases.items():
            if len(accounts) >= 2:
                for i, acc1 in enumerate(accounts):
                    for acc2 in accounts[i+1:]:
                        if self._is_cross_currency(acc1, acc2):
                            forward_volume = self.aggregated_flows.get((acc1, acc2), {}).get('total', 0.0)
                            backward_volume = self.aggregated_flows.get((acc2, acc1), {}).get('total', 0.0)
                            total_volume = forward_volume + backward_volume
                            
                            if forward_volume > 0 and backward_volume > 0 and total_volume > adjusted_threshold:
                                loop_key = tuple(sorted([acc1, acc2]))
                                if loop_key not in processed:
                                    processed.add(loop_key)
                                    path = [acc1, acc2, acc1] if forward_volume >= backward_volume else [acc2, acc1, acc2]
                                    anomalies.append({
                                        'accounts': [path[0], path[1]],
                                        'amount': total_volume,
                                        'anomaly_type': 'Cross-Currency Self-Loop',
                                        'flow_path': path
                                    })
        
        return anomalies


if __name__ == '__main__':
    transaction_data = [
        ['accountUSD1', 'accountUSD2', 1500.0],
        ['accountEUR1', 'accountUSD3', 2500.0],
        ['accountUSD2', 'accountEUR1', 5000.0],
        ['accountEUR2', 'accountEUR3', 200.0],
        ['accountUSD1', 'accountUSD2', 1200.0],
        ['accountUSD1', 'accountUSD2', 800.0],
        ['accountUSD3', 'accountEUR2', 1800.0],
        ['accountEUR2', 'accountUSD1', 900.0],
        ['accountEUR3', 'accountUSD4', 1100.0],
        ['accountUSD5', 'accountEUR5', 2000.0],
        ['accountEUR5', 'accountUSD5', 1900.0],
    ]
    
    thresholds = {
        'volume_threshold': 1000.0,
        'frequency_threshold': 3,
        'cross_currency_sensitivity': 0.8,
        'cycle_threshold': 2000.0,
    }
    
    anomalies = detect_anomalies(transaction_data, thresholds)
    print(anomalies)