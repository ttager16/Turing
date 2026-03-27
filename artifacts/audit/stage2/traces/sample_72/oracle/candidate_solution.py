from typing import List, Dict, Any

def detect_anomalies(transaction_data: List[Dict[str, Any]], 
                     historical_data: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    
    if not isinstance(transaction_data, list) or len(transaction_data) == 0:
        return []
    if not isinstance(historical_data, dict):
        return []

    def is_valid_customer_id(customer_id):
        if not isinstance(customer_id, str) or not customer_id:
            return False
        return all(_chr.isdigit() or ('A' <= _chr <= 'Z') for _chr in customer_id)

    REQUIRED_TRANSACTION_KEYS = {"customer_id", "amount", "location", "timestamp", "linked_accounts"}
    REQUIRED_HISTORY_KEYS = {"amount", "location", "timestamp", "linked_accounts"}

    for transaction in transaction_data:
        if not isinstance(transaction, dict) or set(transaction.keys()) != REQUIRED_TRANSACTION_KEYS:
            return []
        customer = transaction["customer_id"]
        amount = transaction["amount"]
        timestamp = transaction["timestamp"]
        linked_accounts = transaction["linked_accounts"]
        if not is_valid_customer_id(customer):
            return []
        if not (isinstance(amount, (int, float)) and amount > 0):
            return []
        if not (isinstance(timestamp, int) and timestamp > 0):
            return []
        if not isinstance(linked_accounts, list):
            return []
        if len(linked_accounts) != 1 or not is_valid_customer_id(linked_accounts[0]):
            return []

    for customer_id, records in historical_data.items():
        if not is_valid_customer_id(customer_id):
            return []
        if not isinstance(records, list):
            return []
        for record in records:
            if not isinstance(record, dict) or set(record.keys()) != REQUIRED_HISTORY_KEYS:
                return []
            amount = record["amount"]
            timestamp = record["timestamp"]
            linked_accounts = record["linked_accounts"]
            if not (isinstance(amount, (int, float)) and amount > 0):
                return []
            if not (isinstance(timestamp, int) and timestamp > 0):
                return []
            if not isinstance(linked_accounts, list):
                return []
            if len(linked_accounts) not in (0, 1):
                return []
            if len(linked_accounts) == 1 and not is_valid_customer_id(linked_accounts[0]):
                return []

    no_history = len(historical_data) == 0

    adjacency = {}
    all_customers = set()

    def add_transaction_edge(sender, receiver):
        adjacency.setdefault(sender, []).append(receiver)
        all_customers.add(sender)
        all_customers.add(receiver)

    class UnionFind:
        def __init__(self):
            self.parent = {}
            self.rank = {}

        def add(self, item):
            if item not in self.parent:
                self.parent[item] = item
                self.rank[item] = 0

        def find(self, item):
            if self.parent[item] != item:
                self.parent[item] = self.find(self.parent[item])
            return self.parent[item]

        def union(self, a, b):
            root_a, root_b = self.find(a), self.find(b)
            if root_a == root_b:
                return
            if self.rank[root_a] < self.rank[root_b]:
                self.parent[root_a] = root_b
            elif self.rank[root_a] > self.rank[root_b]:
                self.parent[root_b] = root_a
            else:
                self.parent[root_b] = root_a
                self.rank[root_a] += 1

    union_find = UnionFind()

    for sender, records in historical_data.items():
        all_customers.add(sender)
        union_find.add(sender)
        for record in records:
            if len(record["linked_accounts"]) == 1:
                receiver = record["linked_accounts"][0]
                add_transaction_edge(sender, receiver)
                union_find.add(receiver)
                union_find.union(sender, receiver)

    def median(values):
        n = len(values)
        if n == 0:
            return 0.0
        sorted_values = sorted(values)
        mid = n // 2
        if n % 2:
            return float(sorted_values[mid])
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0

    median_mad_map = {}
    if not no_history:
        for customer, records in historical_data.items():
            amounts = [float(r["amount"]) for r in records]
            if len(amounts) >= 2:
                med = median(amounts)
                mad = median([abs(x - med) for x in amounts])
                median_mad_map[customer] = (med, mad)

    historical_timestamps = {}
    if not no_history:
        for customer, records in historical_data.items():
            historical_timestamps[customer] = sorted(int(r["timestamp"]) for r in records)

    batch_timestamps = {}
    transaction_indices_by_customer = {}
    for index, transaction in enumerate(transaction_data):
        customer = transaction["customer_id"]
        timestamp = int(transaction["timestamp"])
        batch_timestamps.setdefault(customer, []).append(timestamp)
        transaction_indices_by_customer.setdefault(customer, []).append(index)

    for customer in batch_timestamps:
        paired = sorted(zip(batch_timestamps[customer], transaction_indices_by_customer[customer]))
        batch_timestamps[customer] = [p[0] for p in paired]
        transaction_indices_by_customer[customer] = [p[1] for p in paired]

    def count_in_window(sorted_list, left, right):
        lo, hi = 0, len(sorted_list)
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_list[mid] < left:
                lo = mid + 1
            else:
                hi = mid
        left_index = lo
        lo, hi = 0, len(sorted_list)
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_list[mid] <= right:
                lo = mid + 1
            else:
                hi = mid
        return max(0, lo - left_index)

    ONE_HOUR = 3600
    SEVEN_DAYS = 7 * 24 * 3600

    burst_flags = [False] * len(transaction_data)
    for customer, times in batch_timestamps.items():
        if not times:
            continue
        left = 0
        right = 0
        count = len(times)
        for i in range(count):
            t = times[i]
            while left < count and times[left] < t - ONE_HOUR:
                left += 1
            if right < i:
                right = i
            while right + 1 < count and times[right + 1] <= t + ONE_HOUR:
                right += 1
            window_count = right - left + 1
            if no_history:
                flag = window_count > 3
            else:
                hist_list = historical_timestamps.get(customer, [])
                hist_count_7d = count_in_window(hist_list, t - SEVEN_DAYS, t - 1)
                avg_per_hour = hist_count_7d / 168.0 if hist_count_7d else 0.0
                threshold = max(3.0, 5.0 * avg_per_hour)
                flag = window_count > threshold
            real_index = transaction_indices_by_customer[customer][i]
            burst_flags[real_index] = flag

    MAX_HOPS = 3

    def forms_short_cycle(sender, receiver):
        if sender not in all_customers:
            union_find.add(sender)
            all_customers.add(sender)
        if receiver not in all_customers:
            union_find.add(receiver)
            all_customers.add(receiver)
        if union_find.find(sender) != union_find.find(receiver):
            return False
        visited = {receiver}
        queue = [(receiver, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth > MAX_HOPS:
                continue
            if current == sender:
                return True
            if depth == MAX_HOPS:
                continue
            for nxt in adjacency.get(current, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, depth + 1))
        return False

    def is_amount_outlier(customer, amount):
        if no_history:
            return False
        stats = median_mad_map.get(customer)
        if not stats:
            return False
        median_value, mad_value = stats
        threshold = median_value + 3.5 * (1.4826 * mad_value)
        return float(amount) > threshold

    results = []

    for index, transaction in enumerate(transaction_data):
        sender = transaction["customer_id"]
        receiver = transaction["linked_accounts"][0]
        amount = float(transaction["amount"])
        outlier = is_amount_outlier(sender, amount)
        cycle = forms_short_cycle(sender, receiver)
        burst = burst_flags[index]
        results.append({"customer_id": sender, "anomaly": bool(outlier or cycle or burst)})
        add_transaction_edge(sender, receiver)
        union_find.add(sender)
        union_find.add(receiver)
        union_find.union(sender, receiver)

    return results


if __name__ == "__main__":
    transaction_data = [
        {'customer_id': 'A001', 'amount': 300, 'location': 'DE', 'timestamp': 1638072800, 'linked_accounts': ['Z999']},
        {'customer_id': 'Z999', 'amount': 50, 'location': 'UK', 'timestamp': 1638072900, 'linked_accounts': ['A001']},
        {'customer_id': 'B123', 'amount': 200, 'location': 'US', 'timestamp': 1638073000, 'linked_accounts': ['Z999']}
    ]
    historical_data = {
        'A001': [
            {'amount': 100, 'location': 'DE', 'timestamp': 1637062800, 'linked_accounts': []},
            {'amount': 500, 'location': 'NL', 'timestamp': 1637062900, 'linked_accounts': []}
        ],
        'Z999': [
            {'amount': 60,  'location': 'UK', 'timestamp': 1637063000, 'linked_accounts': []}
        ],
        'B123': [
            {'amount': 50,  'location': 'US', 'timestamp': 1637063100, 'linked_accounts': []}
        ]
    }
    print(detect_anomalies(transaction_data, historical_data))