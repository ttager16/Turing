import copy
from decimal import Decimal, getcontext
from typing import List, Tuple, Optional, Dict, Any

# Set high precision for Decimal operations
getcontext().prec = 50

def process_operations(n: int, operations: list) -> list:
    """
    Initializes a segment tree for n elements (initially all metrics set to 0.0).
    Processes a sequence of operations and returns results for queries.
    """

    class Node:
        def __init__(self):
            self.wap = Decimal('0.0')
            self.mpd = Decimal('0.0')
            self.cv = Decimal('0.0')
            self.ls = Decimal('0.0')
            self.price_sum = Decimal('0.0')
            self.volume_sum = Decimal('0.0')
            self.max_price = Decimal('0.0')
            self.min_price = Decimal('0.0')
            self.has_data = False
            # Lazy propagation
            self.lazy_price_delta = Decimal('0.0')
            self.lazy_volume_delta = Decimal('0.0')
            self.has_lazy = False

        def copy(self):
            node = Node()
            node.wap = self.wap
            node.mpd = self.mpd
            node.cv = self.cv
            node.ls = self.ls
            node.price_sum = self.price_sum
            node.volume_sum = self.volume_sum
            node.max_price = self.max_price
            node.min_price = self.min_price
            node.has_data = self.has_data
            node.lazy_price_delta = self.lazy_price_delta
            node.lazy_volume_delta = self.lazy_volume_delta
            node.has_lazy = self.has_lazy
            return node

    class SegmentTree:
        def __init__(self, size):
            self.size = size
            self.tree = [Node() for _ in range(4 * size)]
            self.elements = [(Decimal('0.0'), Decimal('0.0')) for _ in range(size)]  # (price, volume)
            self.update_history = []  # List of (operation, params, timestamp)
            self.snapshots = {}  # snapshot_id -> (elements_copy, tree_copy, update_history_copy)

        def calculate_metrics(self, node: Node):
            if node.volume_sum > 0:
                node.wap = node.price_sum / node.volume_sum
            else:
                node.wap = Decimal('0.0')

            if node.has_data:
                node.mpd = node.max_price - node.min_price
            else:
                node.mpd = Decimal('0.0')

            node.cv = node.volume_sum

            if node.mpd > 0:
                node.ls = node.cv / (Decimal('1.0') + node.mpd)
            else:
                node.ls = node.cv

        def push_down(self, idx, left, right):
            """Push lazy values down to children"""
            if not self.tree[idx].has_lazy:
                return

            price_delta = self.tree[idx].lazy_price_delta
            volume_delta = self.tree[idx].lazy_volume_delta

            if left != right:
                # Has children
                left_child = 2 * idx + 1
                right_child = 2 * idx + 2

                # Propagate to left child
                self.tree[left_child].lazy_price_delta += price_delta
                self.tree[left_child].lazy_volume_delta += volume_delta
                self.tree[left_child].has_lazy = True

                # Propagate to right child
                self.tree[right_child].lazy_price_delta += price_delta
                self.tree[right_child].lazy_volume_delta += volume_delta
                self.tree[right_child].has_lazy = True

            # Apply to current node
            if left == right:
                # Leaf node - apply to element
                old_price, old_volume = self.elements[left]
                new_price = old_price + price_delta
                new_volume = old_volume + volume_delta
                self.elements[left] = (new_price, new_volume)

                if new_volume > 0:
                    self.tree[idx].price_sum = new_price * new_volume
                    self.tree[idx].volume_sum = new_volume
                    self.tree[idx].max_price = new_price
                    self.tree[idx].min_price = new_price
                    self.tree[idx].has_data = True
                else:
                    self.tree[idx].price_sum = Decimal('0.0')
                    self.tree[idx].volume_sum = Decimal('0.0')
                    self.tree[idx].max_price = Decimal('0.0')
                    self.tree[idx].min_price = Decimal('0.0')
                    self.tree[idx].has_data = False
                self.calculate_metrics(self.tree[idx])
            else:
                # Internal node - recalculate after children are updated
                # We'll need to push down to children first, then merge
                mid = (left + right) // 2
                self.push_down(2 * idx + 1, left, mid)
                self.push_down(2 * idx + 2, mid + 1, right)
                self.merge(self.tree[idx], self.tree[2 * idx + 1], self.tree[2 * idx + 2])

            # Clear lazy values
            self.tree[idx].lazy_price_delta = Decimal('0.0')
            self.tree[idx].lazy_volume_delta = Decimal('0.0')
            self.tree[idx].has_lazy = False

        def merge(self, node: Node, left: Node, right: Node):
            # price_sum and volume_sum always aggregate
            node.price_sum = left.price_sum + right.price_sum
            node.volume_sum = left.volume_sum + right.volume_sum

            # Determine parent max/min considering only children with CV > 0
            left_has_cv = left.volume_sum > Decimal('0.0')
            right_has_cv = right.volume_sum > Decimal('0.0')

            if left_has_cv and right_has_cv:
                node.max_price = max(left.max_price, right.max_price)
                node.min_price = min(left.min_price, right.min_price)
                node.has_data = True
            elif left_has_cv:
                node.max_price = left.max_price
                node.min_price = left.min_price
                node.has_data = True
            elif right_has_cv:
                node.max_price = right.max_price
                node.min_price = right.min_price
                node.has_data = True
            else:
                # No child has non-zero CV -> no price data to compute MPD
                node.max_price = Decimal('0.0')
                node.min_price = Decimal('0.0')
                node.has_data = False

            # Recompute derived metrics (WAP, MPD, CV, LS)
            self.calculate_metrics(node)

        def build(self, idx, left, right):
            self.tree[idx] = Node()  # Reset node

            if left == right:
                price, volume = self.elements[left]
                if volume > 0:
                    self.tree[idx].price_sum = price * volume
                    self.tree[idx].volume_sum = volume
                    self.tree[idx].max_price = price
                    self.tree[idx].min_price = price
                    self.tree[idx].has_data = True
                    self.calculate_metrics(self.tree[idx])
                return

            mid = (left + right) // 2
            self.build(2 * idx + 1, left, mid)
            self.build(2 * idx + 2, mid + 1, right)
            self.merge(self.tree[idx], self.tree[2 * idx + 1], self.tree[2 * idx + 2])

        def update_point(self, idx, pos, left, right, price, volume):
            self.push_down(idx, left, right)

            if left == right:
                self.elements[pos] = (price, volume)
                if volume > 0:
                    self.tree[idx].price_sum = price * volume
                    self.tree[idx].volume_sum = volume
                    self.tree[idx].max_price = price
                    self.tree[idx].min_price = price
                    self.tree[idx].has_data = True
                else:
                    self.tree[idx].price_sum = Decimal('0.0')
                    self.tree[idx].volume_sum = Decimal('0.0')
                    self.tree[idx].max_price = Decimal('0.0')
                    self.tree[idx].min_price = Decimal('0.0')
                    self.tree[idx].has_data = False
                self.calculate_metrics(self.tree[idx])
                return

            mid = (left + right) // 2
            if pos <= mid:
                self.update_point(2 * idx + 1, pos, left, mid, price, volume)
            else:
                self.update_point(2 * idx + 2, pos, mid + 1, right, price, volume)

            self.merge(self.tree[idx], self.tree[2 * idx + 1], self.tree[2 * idx + 2])

        def update_range(self, idx, left, right, qleft, qright, price_delta, volume_delta):
            if qleft > right or qright < left:
                return

            self.push_down(idx, left, right)

            if qleft <= left and right <= qright:
                # Fully covered
                self.tree[idx].lazy_price_delta += price_delta
                self.tree[idx].lazy_volume_delta += volume_delta
                self.tree[idx].has_lazy = True
                self.push_down(idx, left, right)
                return

            mid = (left + right) // 2
            self.update_range(2 * idx + 1, left, mid, qleft, qright, price_delta, volume_delta)
            self.update_range(2 * idx + 2, mid + 1, right, qleft, qright, price_delta, volume_delta)
            self.merge(self.tree[idx], self.tree[2 * idx + 1], self.tree[2 * idx + 2])

        def query(self, idx, left, right, qleft, qright) -> Node:
            if qleft > right or qright < left:
                return Node()

            self.push_down(idx, left, right)

            if qleft <= left and right <= qright:
                return self.tree[idx].copy()

            mid = (left + right) // 2
            left_node = self.query(2 * idx + 1, left, mid, qleft, qright)
            right_node = self.query(2 * idx + 2, mid + 1, right, qleft, qright)

            result = Node()
            self.merge(result, left_node, right_node)
            return result

        def apply_update(self, pos, price, volume, timestamp):
            price = Decimal(str(price))
            volume = Decimal(str(volume))
            old_price, old_volume = self.elements[pos]
            self.update_point(0, pos, 0, self.size - 1, price, volume)
            self.update_history.append(("update", pos, old_price, old_volume, price, volume, timestamp))

        def apply_range_update(self, start, end, price_delta, volume_delta, timestamp):
            price_delta = Decimal(str(price_delta))
            volume_delta = Decimal(str(volume_delta))

            # Record state before update for partial rollback
            affected = []
            for i in range(start, end + 1):
                old_price, old_volume = self.elements[i]
                affected.append((i, old_price, old_volume))

            self.update_range(0, 0, self.size - 1, start, end, price_delta, volume_delta)
            self.update_history.append(("range_update", start, end, price_delta, volume_delta, affected, timestamp))

        def rollback_updates(self, t_start, t_end, metrics_to_rollback=None):
            """
            Rollback updates within timestamp range.
            If metrics_to_rollback is None, rollback all metrics.
            Otherwise, rollback only specified metrics: ['price', 'volume', 'wap', 'mpd', 'cv', 'ls']
            """
            if metrics_to_rollback is None:
                metrics_to_rollback = ['price', 'volume']  # Rollback base metrics by default

            rollback_price = 'price' in metrics_to_rollback
            rollback_volume = 'volume' in metrics_to_rollback

            updates_to_undo = []
            new_history = []

            for entry in self.update_history:
                timestamp = entry[-1]
                if t_start <= timestamp <= t_end:
                    updates_to_undo.append(entry)
                else:
                    new_history.append(entry)

            # Undo in reverse order
            for entry in reversed(updates_to_undo):
                op_type = entry[0]
                if op_type == "update":
                    _, pos, old_price, old_volume, _, _, _ = entry
                    current_price, current_volume = self.elements[pos]

                    final_price = old_price if rollback_price else current_price
                    final_volume = old_volume if rollback_volume else current_volume

                    self.elements[pos] = (final_price, final_volume)

                elif op_type == "range_update":
                    _, start, end, price_delta, volume_delta, affected, _ = entry

                    for i, old_price, old_volume in affected:
                        current_price, current_volume = self.elements[i]

                        if rollback_price and rollback_volume:
                            self.elements[i] = (old_price, old_volume)
                        elif rollback_price:
                            self.elements[i] = (old_price, current_volume)
                        elif rollback_volume:
                            self.elements[i] = (current_price, old_volume)

            self.update_history = new_history
            self.build(0, 0, self.size - 1)

        def create_snapshot(self, snapshot_id, timestamp):
            elements_copy = copy.deepcopy(self.elements)
            tree_copy = [node.copy() for node in self.tree]
            history_copy = copy.deepcopy(self.update_history)
            self.snapshots[snapshot_id] = (elements_copy, tree_copy, history_copy)

        def restore_snapshot(self, snapshot_id):
            if snapshot_id in self.snapshots:
                elements_copy, tree_copy, history_copy = self.snapshots[snapshot_id]
                self.elements = copy.deepcopy(elements_copy)
                self.tree = [node.copy() for node in tree_copy]
                self.update_history = copy.deepcopy(history_copy)

        def conditional_check(self, src_start, src_end, mpd_threshold, dst_start, dst_end, cv_threshold, price_boost):
            mpd_threshold = Decimal(str(mpd_threshold))
            cv_threshold = Decimal(str(cv_threshold))
            price_boost = Decimal(str(price_boost))

            src_node = self.query(0, 0, self.size - 1, src_start, src_end)
            dst_node = self.query(0, 0, self.size - 1, dst_start, dst_end)

            if src_node.mpd > mpd_threshold and dst_node.cv < cv_threshold:
                for i in range(dst_start, dst_end + 1):
                    price, volume = self.elements[i]
                    self.update_point(0, i, 0, self.size - 1, price + price_boost, volume)

    tree = SegmentTree(n)
    results = []

    for op in operations:
        op_type = op[0]

        if op_type == "update":
            _, idx, price, volume, timestamp = op
            tree.apply_update(idx, price, volume, timestamp)

        elif op_type == "range_update":
            _, start, end, price_delta, volume_delta, timestamp = op
            tree.apply_range_update(start, end, price_delta, volume_delta, timestamp)

        elif op_type == "query":
            _, start, end = op
            node = tree.query(0, 0, tree.size - 1, start, end)
            wap = float(round(node.wap, 2))
            mpd = float(round(node.mpd, 2))
            cv = float(round(node.cv, 2))
            ls = float(round(node.ls, 2))
            results.append([wap, mpd, cv, ls])

        elif op_type == "rollback":
            if len(op) == 3:
                _, t_start, t_end = op
                tree.rollback_updates(t_start, t_end)
            else:
                _, t_start, t_end, metrics = op
                tree.rollback_updates(t_start, t_end, metrics)

        elif op_type == "snapshot":
            _, snapshot_id, timestamp = op
            tree.create_snapshot(snapshot_id, timestamp)

        elif op_type == "restore":
            _, snapshot_id = op
            tree.restore_snapshot(snapshot_id)

        elif op_type == "conditional_check":
            _, src_start, src_end, mpd_threshold, dst_start, dst_end, cv_threshold, price_boost = op
            tree.conditional_check(src_start, src_end, mpd_threshold, dst_start, dst_end, cv_threshold, price_boost)

    return results