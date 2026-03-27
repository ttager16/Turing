from typing import List
from decimal import Decimal, InvalidOperation

def meldable_priority_queue(order_streams: List[List]) -> List:
    if not isinstance(order_streams, list):
        return []
    if len(order_streams) == 0:
        return []
    for stream in order_streams:
        if not isinstance(stream, list):
            return []

    class LeftistHeapNode:
        def __init__(self, item):
            self.item = item
            self.left = None
            self.right = None
            self.npl = 1

    class LeftistHeap:
        def __init__(self, comparator):
            self.root = None
            self.comparator = comparator

        def merge_nodes(self, a, b):
            if a is None:
                return b
            if b is None:
                return a
            if not self.comparator(a.item, b.item):
                a, b = b, a
            a.right = self.merge_nodes(a.right, b)
            left_npl  = a.left.npl  if a.left  else 0
            right_npl = a.right.npl if a.right else 0
            if left_npl < right_npl:
                a.left, a.right = a.right, a.left
                right_npl = a.right.npl if a.right else 0
            a.npl = right_npl + 1
            return a


        def meld(self, other):
            self.root = self.merge_nodes(self.root, other.root)
            other.root = None
            other.size = 0

        def insert(self, item):
            node = LeftistHeapNode(item)
            self.root = self.merge_nodes(self.root, node)

        def peek_min(self):
            return self.root.item if self.root else None

        def pop_min(self):
            item = self.root.item
            self.root = self.merge_nodes(self.root.left, self.root.right)
            return item

        def is_empty(self):
            return self.root is None

    comparator = lambda a, b: a[0] < b[0]

    per_stream_buy_heaps = []
    per_stream_sell_heaps = []
    arrival_index = 0

    for stream in order_streams:
        buy_heap = LeftistHeap(comparator)
        sell_heap = LeftistHeap(comparator)

        for entry in stream:
            if not isinstance(entry, list) or len(entry) != 3:
                return []
            priority, side, price_value = entry[0], entry[1], entry[2]
            if type(priority) is not int:
                return []
            if side not in ("buy", "sell"):
                return []
            if not isinstance(price_value, (int, float)) or isinstance(price_value, bool):
                return []
            original_price = price_value
            try:
                price_dec = Decimal(str(price_value))
            except (InvalidOperation, ValueError):
                return []
            if not price_dec.is_finite() or price_dec < 0:
                return []

            if side == "buy":
                heap_key = (-price_dec, priority, arrival_index)
                buy_heap.insert((heap_key, priority, side, price_dec, original_price, arrival_index))
            else:
                heap_key = (price_dec, priority, arrival_index)
                sell_heap.insert((heap_key, priority, side, price_dec, original_price, arrival_index))

            arrival_index += 1

        per_stream_buy_heaps.append(buy_heap)
        per_stream_sell_heaps.append(sell_heap)

    global_buy = LeftistHeap(comparator)
    for heap in per_stream_buy_heaps:
        global_buy.meld(heap)

    global_sell = LeftistHeap(comparator)
    for heap in per_stream_sell_heaps:
        global_sell.meld(heap)

    def best_buy_price():
        item = global_buy.peek_min()
        if item is None:
            return None
        return -item[0][0]

    def best_sell_price():
        item = global_sell.peek_min()
        if item is None:
            return None
        return item[0][0]

    while (not global_buy.is_empty()) and (not global_sell.is_empty()):
        top_buy = best_buy_price()
        top_sell = best_sell_price()
        if top_buy is None or top_sell is None:
            break
        if top_buy >= top_sell:
            global_buy.pop_min()
            global_sell.pop_min()
        else:
            break

    remaining = []
    while not global_buy.is_empty():
        _, priority, side, price_dec, orig_price, arrival = global_buy.pop_min()
        remaining.append([priority, side, orig_price, arrival, price_dec])
    while not global_sell.is_empty():
        _, priority, side, price_dec, orig_price, arrival = global_sell.pop_min()
        remaining.append([priority, side, orig_price, arrival, price_dec])

    if not remaining:
        return []

    def global_key(record):
        priority, side, _, arrival, price_dec = record
        side_rank = 0 if side == "buy" else 1
        price_aggressiveness = -price_dec if side == "buy" else price_dec
        return (priority, side_rank, price_aggressiveness, arrival)

    remaining.sort(key=global_key)
    return [[priority, side, price] for priority, side, price, _, _ in remaining]


if __name__ == "__main__":
    order_streams = [
        [[10, 'buy', 105.2], [25, 'sell', 106.0], [5, 'buy', 103.5]],
        [[8,  'buy', 101.0], [2,  'sell', 109.5]],
        [[15, 'sell', 104.3], [1,  'buy', 108.0]],
        [[20, 'buy', 102.0], [18, 'sell', 110.0]]
    ]
    print(meldable_priority_queue(order_streams))