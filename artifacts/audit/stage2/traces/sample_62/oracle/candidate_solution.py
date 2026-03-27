from typing import Any, Dict, List, Optional, Set
from collections import deque, defaultdict

def design_fraud_detection_tree(commands: List[str]) -> Dict[str, Any]:
    """
    Execute AVL-based operations with risk rules.

    Parameters:
        commands: list[str]

    Returns:
        dict: {"alerts": list[int], "size": int}
    """
    tree = FraudDetectionTree()
    for line in commands:
        line = line.strip()
        if not line:
            continue
        if line.startswith("INSERT "):
            parts = line.split()
            tx_id = int(parts[1])
            amount = float(parts[2])
            category = parts[3]
            merchant_id = int(parts[4])
            desc = " ".join(parts[5:]) if len(parts) > 5 else ""
            if category not in CATEGORIES:
                continue
            if tx_id in tree.nodes:
                tree.update_existing(tx_id, amount, category, merchant_id, desc)
            else:
                tree.insert_new(tx_id, amount, category, merchant_id, desc)
        elif line.startswith("DELETE "):
            parts = line.split()
            tx_id = int(parts[1])
            tree.delete_key(tx_id)
        elif line.startswith("REALLOCATE "):
            parts = line.split()
            old_id = int(parts[1])
            new_id = int(parts[2])
            tree.reallocate(old_id, new_id)
        elif line.startswith("BATCH_REALLOCATE "):
            payload = line[len("BATCH_REALLOCATE "):].strip()
            pairs = payload.split(",") if payload else []
            mappings: List[tuple[int, int]] = []
            for p in pairs:
                old_s, new_s = p.split("->", 1)
                mappings.append((int(old_s), int(new_s)))
            tree.batch_reallocate(mappings)
    return {"alerts": tree.alerts, "size": tree.size}


CATEGORIES = {"TRANSFER", "PURCHASE", "REFUND", "WITHDRAWAL", "DEPOSIT"}

RECENT_WINDOW_SIZE = 5
H3_VELOCITY_WINDOW = 8
H2_TOKEN_FREQ_THRESHOLD = 4
C3_SAME_MERCHANT_COUNT = 3

DECAY_RATE_PER_SEQ = 0.01
MIN_DECAY_FACTOR = 0.5

C_BASE = 100.0
H_BASE = 50.0
M_BASE = 25.0

C1_EXTREME_AMOUNT = 50000.0
C2_REFUND_AMOUNT = 5000.0
H1_HIGH_AMOUNT_LOW = 10000.0
H1_HIGH_AMOUNT_HIGH = 50000.0
M1_CATEGORY_DOMINANCE = 0.6
M2_AMOUNT_PROXIMITY = 0.05
M3_JACCARD_THRESHOLD = 0.6


class AVLNode:
    __slots__ = (
        "key",
        "amount",
        "desc",
        "category",
        "merchant_id",
        "sequence",
        "height",
        "left",
        "right",
        "tokens",
    )

    def __init__(
        self,
        key: int,
        amount: float,
        desc: str,
        category: str,
        merchant_id: int,
        sequence: int,
    ) -> None:
        self.key = key
        self.amount = amount
        self.desc = desc
        self.category = category
        self.merchant_id = merchant_id
        self.sequence = sequence
        self.height = 1
        self.left: Optional["AVLNode"] = None
        self.right: Optional["AVLNode"] = None
        self.tokens: Set[str] = set(desc.lower().split()) if desc else set()


class FraudDetectionTree:
    def __init__(self) -> None:
        self.root: Optional[AVLNode] = None
        self.nodes: Dict[int, AVLNode] = {}
        self.size: int = 0
        self.sequence_counter: int = 0
        self.alerts: List[int] = []
        self.token_index: Dict[str, Set[int]] = defaultdict(set)
        self.category_counts: Dict[str, int] = {c: 0 for c in CATEGORIES}
        self.merchant_history: Dict[int, List[int]] = defaultdict(list)
        self.recent: deque[int] = deque(maxlen=RECENT_WINDOW_SIZE)

    def _height(self, n: Optional[AVLNode]) -> int:
        return n.height if n else 0

    def _update_height(self, n: AVLNode) -> None:
        n.height = 1 + max(self._height(n.left), self._height(n.right))

    def _balance_factor(self, n: AVLNode) -> int:
        return self._height(n.left) - self._height(n.right)

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        x = y.left
        t2 = x.right if x else None
        x.right = y
        y.left = t2
        self._update_height(y)
        self._update_height(x)
        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        y = x.right
        t2 = y.left if y else None
        y.left = x
        x.right = t2
        self._update_height(x)
        self._update_height(y)
        return y

    def _rebalance(self, node: AVLNode) -> AVLNode:
        self._update_height(node)
        bf = self._balance_factor(node)
        if bf > 1:
            if self._balance_factor(node.left) < 0:
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)
        if bf < -1:
            if self._balance_factor(node.right) > 0:
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)
        return node

    def _insert_avl(self, root: Optional[AVLNode], node: AVLNode) -> AVLNode:
        if root is None:
            return node
        if node.key < root.key:
            root.left = self._insert_avl(root.left, node)
        else:
            root.right = self._insert_avl(root.right, node)
        return self._rebalance(root)

    def _get_min(self, node: AVLNode) -> AVLNode:
        cur = node
        while cur.left:
            cur = cur.left
        return cur

    def _delete_avl(self, root: Optional[AVLNode], key: int) -> Optional[AVLNode]:
        if root is None:
            return None
        if key < root.key:
            root.left = self._delete_avl(root.left, key)
        elif key > root.key:
            root.right = self._delete_avl(root.right, key)
        else:
            if root.left is None:
                return root.right
            if root.right is None:
                return root.left
            succ = self._get_min(root.right)
            self.nodes[succ.key] = root
            root.key = succ.key
            root.amount = succ.amount
            root.desc = succ.desc
            root.category = succ.category
            root.merchant_id = succ.merchant_id
            root.sequence = succ.sequence
            root.tokens = succ.tokens
            root.right = self._delete_avl(root.right, succ.key)
        return self._rebalance(root)

    def _decay(self, current_seq: int, other_seq: int) -> float:
        diff = current_seq - other_seq
        if diff <= 0:
            return 1.0
        factor = 1.0 - DECAY_RATE_PER_SEQ * diff
        return factor if factor >= MIN_DECAY_FACTOR else MIN_DECAY_FACTOR

    def _remove_from_recent(self, key: int) -> None:
        if key in self.recent:
            tmp = deque(self.recent, maxlen=RECENT_WINDOW_SIZE)
            tmp.remove(key)
            self.recent = tmp

    def _remove_from_merchant_history(self, merchant_id: int, seq: int) -> None:
        lst = self.merchant_history.get(merchant_id)
        if not lst:
            return
        for i, v in enumerate(lst):
            if v == seq:
                lst.pop(i)
                break

    def _update_token_index_on_insert(self, key: int, tokens: Set[str]) -> None:
        for t in tokens:
            self.token_index[t].add(key)

    def _update_token_index_on_delete(self, key: int, tokens: Set[str]) -> None:
        for t in tokens:
            s = self.token_index.get(t)
            if s is not None:
                s.discard(key)
                if not s:
                    del self.token_index[t]

    def _collect_nodes(self, node: Optional[AVLNode], acc: List[AVLNode]) -> None:
        if node is None:
            return
        self._collect_nodes(node.left, acc)
        acc.append(node)
        self._collect_nodes(node.right, acc)

    def _rule_c1(self, node: AVLNode) -> float:
        return C_BASE if node.amount >= C1_EXTREME_AMOUNT else 0.0

    def _rule_c2(self, node: AVLNode) -> float:
        return C_BASE if (node.category == "REFUND" and node.amount >= C2_REFUND_AMOUNT) else 0.0

    def _rule_c3(self, node: AVLNode) -> float:
        prior_keys: List[int] = list(self.recent)
        if not prior_keys:
            return 0.0
        same_merchant_nodes: List[AVLNode] = []
        for k in reversed(prior_keys):
            other = self.nodes.get(k)
            if other is not None and other.merchant_id == node.merchant_id:
                same_merchant_nodes.append(other)
        if len(same_merchant_nodes) >= C3_SAME_MERCHANT_COUNT:
            s = 0.0
            for other in same_merchant_nodes:
                s += self._decay(node.sequence, other.sequence)
            return C_BASE * s
        return 0.0

    def _rule_h1(self, node: AVLNode) -> float:
        return H_BASE if (H1_HIGH_AMOUNT_LOW <= node.amount < H1_HIGH_AMOUNT_HIGH) else 0.0

    def _rule_h2(self, node: AVLNode) -> float:
        if not node.tokens:
            return 0.0
        for t in node.tokens:
            keys = self.token_index.get(t)
            if keys and len(keys) >= H2_TOKEN_FREQ_THRESHOLD:
                s = 0.0
                for k in keys:
                    if k == node.key:
                        continue
                    other = self.nodes.get(k)
                    if other is not None:
                        s += self._decay(node.sequence, other.sequence)
                if s >= 3.0:
                    return H_BASE
        return 0.0

    def _rule_h3(self, node: AVLNode) -> float:
        mlist = self.merchant_history.get(node.merchant_id, [])
        if not mlist:
            return 0.0
        window_start = node.sequence - H3_VELOCITY_WINDOW
        candidates = [seq for seq in mlist if window_start <= seq < node.sequence]
        if len(candidates) >= 2:
            s = 0.0
            for seq in candidates:
                s += self._decay(node.sequence, seq)
            return H_BASE * s
        return 0.0

    def _rule_m1(self, node: AVLNode) -> float:
        count = self.category_counts.get(node.category, 0)
        if self.size > 0 and count > M1_CATEGORY_DOMINANCE * self.size:
            return M_BASE
        return 0.0

    def _rule_m2(self, node: AVLNode) -> float:
        all_nodes: List[AVLNode] = []
        self._collect_nodes(self.root, all_nodes)
        limit = M2_AMOUNT_PROXIMITY * node.amount
        matches: List[AVLNode] = []
        for other in all_nodes:
            if other.key == node.key:
                continue
            if abs(other.amount - node.amount) <= limit:
                matches.append(other)
        if len(matches) >= 3:
            s = 0.0
            for other in matches:
                s += self._decay(node.sequence, other.sequence)
            return M_BASE * s
        return 0.0

    def _rule_m3(self, node: AVLNode) -> float:
        if not node.tokens:
            return 0.0
        all_nodes: List[AVLNode] = []
        self._collect_nodes(self.root, all_nodes)
        similar: List[AVLNode] = []
        for other in all_nodes:
            if other.key == node.key:
                continue
            union = node.tokens | other.tokens
            if not union:
                continue
            inter = node.tokens & other.tokens
            jac = len(inter) / float(len(union))
            if jac >= M3_JACCARD_THRESHOLD:
                similar.append(other)
        if len(similar) >= 2:
            s = 0.0
            for other in similar:
                s += self._decay(node.sequence, other.sequence)
            return M_BASE * s
        return 0.0

    def _evaluate_rules(self, node: AVLNode) -> float:
        total = 0.0
        total += self._rule_c1(node)
        total += self._rule_c2(node)
        total += self._rule_c3(node)
        total += self._rule_h1(node)
        total += self._rule_h2(node)
        total += self._rule_h3(node)
        total += self._rule_m1(node)
        total += self._rule_m2(node)
        total += self._rule_m3(node)
        return total

    def insert_new(
        self,
        key: int,
        amount: float,
        category: str,
        merchant_id: int,
        desc: str,
        evaluate_rules: bool = True,
    ) -> None:
        self.sequence_counter += 1
        seq = self.sequence_counter
        node = AVLNode(key, amount, desc, category, merchant_id, seq)
        self.root = self._insert_avl(self.root, node)
        self.nodes[key] = node
        self.size += 1
        self.category_counts[category] = self.category_counts.get(category, 0) + 1
        self._update_token_index_on_insert(key, node.tokens)
        self.merchant_history[merchant_id].append(seq)
        if evaluate_rules:
            score = self._evaluate_rules(node)
            if score >= 100.0:
                self.alerts.append(key)
        self.recent.append(key)

    def update_existing(
        self,
        key: int,
        amount: float,
        category: str,
        merchant_id: int,
        desc: str,
    ) -> None:
        node = self.nodes[key]
        old_category = node.category
        old_tokens = node.tokens
        old_merchant = node.merchant_id

        node.amount = amount
        node.desc = desc
        node.category = category
        node.merchant_id = merchant_id
        node.tokens = set(desc.lower().split()) if desc else set()

        if old_category != category:
            self.category_counts[old_category] -= 1
            self.category_counts[category] = self.category_counts.get(category, 0) + 1

        if old_tokens != node.tokens:
            self._update_token_index_on_delete(key, old_tokens)
            self._update_token_index_on_insert(key, node.tokens)

        if old_merchant != merchant_id:
            self._remove_from_merchant_history(old_merchant, node.sequence)
            self.merchant_history[merchant_id].append(node.sequence)

        score = self._evaluate_rules(node)
        if score >= 100.0:
            self.alerts.append(key)

    def delete_key(self, key: int) -> Optional[AVLNode]:
        node = self.nodes.pop(key, None)
        if node is None:
            return None
        self.category_counts[node.category] -= 1
        self._update_token_index_on_delete(key, node.tokens)
        self._remove_from_recent(key)
        self._remove_from_merchant_history(node.merchant_id, node.sequence)
        self.root = self._delete_avl(self.root, key)
        self.size -= 1
        return node

    def reallocate(self, old_key: int, new_key: int) -> None:
        node = self.delete_key(old_key)
        if node is None:
            return
        self.insert_new(
            new_key,
            node.amount,
            node.category,
            node.merchant_id,
            node.desc,
            evaluate_rules=True,
        )

    def batch_reallocate(self, mappings: List[tuple[int, int]]) -> None:
        to_insert: List[tuple[int, float, str, int, str]] = []
        for old, new in mappings:
            node = self.delete_key(old)
            if node is not None:
                to_insert.append((new, node.amount, node.category, node.merchant_id, node.desc))
        to_insert.sort(key=lambda x: x[0])
        for (new_id, amount, category, merchant_id, desc) in to_insert:
            self.insert_new(new_id, amount, category, merchant_id, desc, evaluate_rules=True)

if __name__ == "__main__":
    sample_commands = [
        "INSERT 1001 450.75 PURCHASE 501 Payment to vendor A",
        "INSERT 1002 55000.00 TRANSFER 502 Wire vendor A urgent",
        "INSERT 1003 15.00 REFUND 501 refund vendor a",
        "INSERT 1004 460.00 PURCHASE 501 fee vendor a payment",
        "INSERT 1005 455.00 PURCHASE 503 payment processing",
        "INSERT 1006 12.00 PURCHASE 501 small vendor a transaction",
        "REALLOCATE 1004 1007",
        "INSERT 1008 6000.00 REFUND 504 large refund case",
        "INSERT 1009 0.01 PURCHASE 501 vendor a",
        "DELETE 1003",
        "INSERT 1010 462.00 PURCHASE 505 payment task",
        "BATCH_REALLOCATE 1001->2001,1005->2005",
        "INSERT 1011 458.00 PURCHASE 506 payment order",
    ]
    print(design_fraud_detection_tree(sample_commands))