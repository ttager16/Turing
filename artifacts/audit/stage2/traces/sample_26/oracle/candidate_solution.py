from typing import List, Dict, Any, Union
from datetime import datetime
from collections import defaultdict, deque

class TransactionGraph:
    """Graph representation for transaction analysis."""
    
    def __init__(self):
        self.nodes = {}
        self.edges = defaultdict(list)
        self.reverse_edges = defaultdict(list)
        self.amount_thresholds = (1, 10000000)
        self.business_hours = (9, 17)
    
    def add_transaction(self, transaction):
        """Add transaction to graph."""
        tx_id = transaction['transaction_id']
        source = transaction['source_account']
        dest = transaction['destination_account']
        amount = transaction['amount']
        timestamp = transaction['timestamp']
        
        self.nodes[tx_id] = {
            'source': source,
            'dest': dest,
            'amount': amount,
            'timestamp': timestamp,
            'type': transaction['transaction_type']
        }
        
        self.edges[source].append((dest, tx_id))
        self.reverse_edges[dest].append((source, tx_id))
    
    def validate_amount(self, amount):
        """Validate transaction amount against thresholds."""
        return self.amount_thresholds[0] <= amount <= self.amount_thresholds[1]
    
    def is_business_hours(self, timestamp_str):
        """Check if transaction occurred during business hours."""
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        hour = dt.hour
        return self.business_hours[0] <= hour < self.business_hours[1]
    
    def find_cycles(self):
        """Find circular transaction patterns."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(account, path, tx_path):
            if account in rec_stack:
                cycle_start = path.index(account)
                # Return the transaction IDs that form the cycle
                cycle_txs = tx_path[cycle_start:]
                cycles.append(cycle_txs)
                return
            if account in visited:
                return
            
            visited.add(account)
            rec_stack.add(account)
            
            for neighbor, tx_id in self.edges[account]:
                dfs(neighbor, path + [account], tx_path + [tx_id])
            
            rec_stack.remove(account)
        
        accounts = list(self.edges.keys())
        for account in accounts:
            if account not in visited:
                dfs(account, [], [])
        
        return cycles
    
    def find_high_frequency_accounts(self, min_transactions=10):
        """Find accounts with unusually high transaction frequency."""
        account_counts = defaultdict(int)
        for tx in self.nodes.values():
            account_counts[tx['source']] += 1
        return [acc for acc, count in account_counts.items() if count >= min_transactions]
    
    def find_multi_hop_flows(self, max_hops=5):
        """Find multi-hop transaction flows."""
        flows = []
        visited_flows = set()
        
        def dfs(account, path, depth):
            if depth >= max_hops:
                return
            
            for neighbor, tx_id in self.edges[account]:
                new_path = path + [tx_id]
                path_key = tuple(new_path)
                
                if path_key not in visited_flows and len(new_path) >= 5:
                    flows.append(new_path)
                    visited_flows.add(path_key)
                
                if depth + 1 < max_hops:
                    dfs(neighbor, new_path, depth + 1)
        
        accounts = list(self.edges.keys())
        for account in accounts:
            dfs(account, [], 0)
        
        return flows
    
    def find_large_amount_transactions(self, threshold=100000):
        """Find transactions exceeding amount threshold."""
        large_txs = []
        for tx_id, tx in self.nodes.items():
            if tx['amount'] > threshold:
                large_txs.append(tx_id)
        return large_txs
    
    def find_rapid_sequential_transactions(self, time_window_minutes=5):
        """Find rapid sequential transactions."""
        rapid_sequences = []
        account_timestamps = defaultdict(list)

        for tx_id, tx in self.nodes.items():
            account_timestamps[tx['source']].append((tx_id, tx['timestamp']))

        for account, txs in account_timestamps.items():
            txs.sort(key=lambda x: x[1])
            for i in range(len(txs) - 1):
                current_time = datetime.fromisoformat(txs[i][1].replace('Z', '+00:00'))
                next_time = datetime.fromisoformat(txs[i + 1][1].replace('Z', '+00:00'))
                time_diff = (next_time - current_time).total_seconds() / 60

                if next_time > current_time and time_diff <= time_window_minutes:
                    rapid_sequences.append([txs[i][0], txs[i + 1][0]])

        return rapid_sequences


class FraudDetector:
    """Main fraud detection engine."""
    
    def __init__(self):
        self.graph = TransactionGraph()
        self.fraud_scenarios = {
            'cyclic_transfers': 0,
            'multi_account_infiltration': 0,
            'nested_money_laundering': 0,
            'high_frequency_accounts': 0,
            'large_amount_transactions': 0,
            'rapid_sequential_transactions': 0,
            'after_hours_transactions': 0,
            'invalid_amount_transactions': 0
        }
    
    def detect_fraudulent_transactions(self, transactions: List[Dict[str, Any]], timeframe: List[str]) -> List[Union[List[Dict[str, Any]], Dict[str, Any]]]:
        """Detect fraudulent transaction patterns."""
        flagged_transactions = []
        key_subgraphs = []
        
        start_time = datetime.fromisoformat(timeframe[0].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(timeframe[1].replace('Z', '+00:00'))
        
        filtered_transactions = []
        for tx in transactions:
            tx_time = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00'))
            if start_time <= tx_time <= end_time:
                filtered_transactions.append(tx)
                self.graph.add_transaction(tx)
        
        flagged_transactions.extend(self._detect_cyclic_transfers())
        flagged_transactions.extend(self._detect_multi_account_infiltration())
        flagged_transactions.extend(self._detect_high_frequency_accounts())
        flagged_transactions.extend(self._detect_nested_money_laundering())
        flagged_transactions.extend(self._detect_large_amount_transactions())
        flagged_transactions.extend(self._detect_rapid_sequential_transactions())
        flagged_transactions.extend(self._detect_after_hours_transactions())
        flagged_transactions.extend(self._detect_invalid_amount_transactions())
        
        key_subgraphs = self._generate_key_subgraphs()
        
        summary_report = {
            'total_anomalies': len(flagged_transactions),
            'fraud_scenarios': self.fraud_scenarios.copy(),
            'key_subgraphs': key_subgraphs
        }
        
        return [flagged_transactions, summary_report]
    
    def _detect_cyclic_transfers(self):
        """Detect cyclic transfer patterns."""
        cycles = self.graph.find_cycles()
        flagged = []
        for cycle in cycles:
            if len(cycle) >= 2:
                flagged.append({
                    'chain': cycle,
                    'reason': 'Cyclic transfer pattern detected'
                })
                self.fraud_scenarios['cyclic_transfers'] += 1
        return flagged
    
    def _detect_multi_account_infiltration(self):
        """Detect multi-account infiltration patterns."""
        flagged = []
        multi_hop_flows = self.graph.find_multi_hop_flows()
        for flow in multi_hop_flows:
            if len(flow) >= 5:
                flagged.append({
                    'chain': flow[:5],
                    'reason': 'Multi-account infiltration pattern'
                })
                self.fraud_scenarios['multi_account_infiltration'] += 1
        return flagged
    
    def _detect_nested_money_laundering(self):
        """Detect nested money laundering patterns."""
        high_freq_accounts = self.graph.find_high_frequency_accounts()
        flagged = []
        for account in high_freq_accounts:
            account_transactions = []
            for tx_id, tx in self.graph.nodes.items():
                if tx['source'] == account or tx['dest'] == account:
                    account_transactions.append(tx_id)
            
            if len(account_transactions) >= 8:
                flagged.append({
                    'chain': account_transactions[:8],
                    'reason': 'Nested money laundering pattern'
                })
                self.fraud_scenarios['nested_money_laundering'] += 1
        return flagged
    
    def _detect_high_frequency_accounts(self):
        """Detect high frequency account activity."""
        high_freq_accounts = self.graph.find_high_frequency_accounts()
        flagged = []
        for account in high_freq_accounts:
            # Preserve insertion order by timestamps and include all of the account's outgoing tx ids
            ordered = sorted(
                (
                    (tx_id, tx['timestamp'])
                    for tx_id, tx in self.graph.nodes.items()
                    if tx['source'] == account
                ),
                key=lambda t: t[1],
            )
            account_txs = [tx_id for tx_id, _ in ordered]
            flagged.append({'chain': account_txs, 'reason': 'High frequency account activity'})
            self.fraud_scenarios['high_frequency_accounts'] += 1
        return flagged
    
    def _detect_large_amount_transactions(self):
        """Detect large amount transactions."""
        large_txs = self.graph.find_large_amount_transactions()
        flagged = []
        for tx_id in large_txs:
            tx = self.graph.nodes[tx_id]
            if not self.graph.validate_amount(tx['amount']):
                continue
            flagged.append({'chain': [tx_id], 'reason': 'Large amount transaction'})
            self.fraud_scenarios['large_amount_transactions'] += 1
        return flagged
    
    def _detect_rapid_sequential_transactions(self):
        """Detect rapid sequential transactions."""
        rapid_sequences = self.graph.find_rapid_sequential_transactions()
        flagged = []
        for sequence in rapid_sequences:
            flagged.append({
                'chain': sequence,
                'reason': 'Rapid sequential transactions'
            })
            self.fraud_scenarios['rapid_sequential_transactions'] += 1
        return flagged
    
    def _detect_after_hours_transactions(self):
        """Detect after-hours transactions."""
        flagged = []
        for tx_id, tx in self.graph.nodes.items():
            if not self.graph.is_business_hours(tx['timestamp']):
                flagged.append({
                    'chain': [tx_id],
                    'reason': 'After-hours transaction'
                })
                self.fraud_scenarios['after_hours_transactions'] += 1
        return flagged
    
    def _detect_invalid_amount_transactions(self):
        """Detect invalid amount transactions."""
        flagged = []
        for tx_id, tx in self.graph.nodes.items():
            if not self.graph.validate_amount(tx['amount']):
                flagged.append({
                    'chain': [tx_id],
                    'reason': 'Invalid amount transaction'
                })
                self.fraud_scenarios['invalid_amount_transactions'] += 1
        return flagged
    
    def _generate_key_subgraphs(self):
        """Generate key subgraph information."""
        subgraphs = []
        high_freq_accounts = self.graph.find_high_frequency_accounts()
        
        for account in high_freq_accounts[:5]:
            related_accounts = set()
            for tx_id, tx in self.graph.nodes.items():
                if tx['source'] == account or tx['dest'] == account:
                    related_accounts.add(tx['source'])
                    related_accounts.add(tx['dest'])
            
            subgraphs.append({
                'nodes_involved': sorted(list(related_accounts)),
                'description': f'High activity cluster around account {account}'
            })
        
        return subgraphs


def detect_fraudulent_transactions(transactions: List[Dict[str, Any]], timeframe: List[str]) -> List[Union[List[Dict[str, Any]], Dict[str, Any]]]:
    """Detect fraudulent transaction patterns in given timeframe."""
    detector = FraudDetector()
    return detector.detect_fraudulent_transactions(transactions, timeframe)


if __name__ == '__main__':
    sample_transactions = [
        {
            'transaction_id': 'G101',
            'timestamp': '2023-11-01T08:30:00',
            'amount': 2000,
            'source_account': 'AC987',
            'destination_account': 'AC123',
            'transaction_type': 'transfer'
        },
        {
            'transaction_id': 'G102',
            'timestamp': '2023-11-01T08:31:00',
            'amount': 1500,
            'source_account': 'AC123',
            'destination_account': 'AC456',
            'transaction_type': 'transfer'
        },
        {
            'transaction_id': 'G103',
            'timestamp': '2023-11-01T08:35:00',
            'amount': 100000,
            'source_account': 'AC999',
            'destination_account': 'AC123',
            'transaction_type': 'deposit'
        }
    ]
    
    timeframe = ['2023-11-01T00:00:00', '2023-11-02T00:00:00']
    
    result = detect_fraudulent_transactions(sample_transactions, timeframe)
    flagged_transactions, summary_report = result[0], result[1]
    
    print("Flagged transactions:")
    print(flagged_transactions)
    print("\nSummary report:")
    print(summary_report)