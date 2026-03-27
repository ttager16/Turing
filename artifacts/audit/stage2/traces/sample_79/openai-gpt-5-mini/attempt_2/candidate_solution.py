def __init__(self, key, value):
        self.key = key
        self.value = value
        self.child = None
        self.sibling = None

class PairingHeap:
    def __init__(self):
        self.root: Optional[PairingHeapNode] = None
        self.size = 0

    def meld_nodes(self, a: Optional[PairingHeapNode], b: Optional[PairingHeapNode]) -> Optional[PairingHeapNode]:
        if a is None: return b
        if b is None: return a
        if a.key <= b.key:
            b.sibling = a.child
            a.child = b
            return a
        else:
            a.sibling = b.child
            b.child = a
            return b

    def meld(self, other: 'PairingHeap'):
        if other is None or other.root is None:
            return
        if self.root is None:
            self.root = other.root
            self.size = other.size
            return
        self.root = self.meld_nodes(self.root, other.root)
        self.size += other.size

    def insert(self, key, value):
        node = PairingHeapNode(key, value)
        self.root = self.meld_nodes(self.root, node)
        self.size += 1

    def peek_min(self):
        if self.root is None: return None
        return self.root.key, self.root.value

    def pop_min(self):
        if self.root is None: return None
        min_key, min_value = self.root.key, self.root.value
        if self.root.child is None:
            self.root = None
            self.size = 0
            return (min_key, min_value)
        # two-pass melding
        children = []
        cur = self.root.child
        while cur:
            nxt = cur.sibling
            cur.sibling = None
            children.append(cur)
            cur = nxt
        # first pass: meld pairs left to right
        paired = []
        i = 0
        n = len(children)
        while i+1 < n:
            paired.append(self.meld_nodes(children[i], children[i+1]))
            i += 2
        if i < n:
            paired.append(children[i])
        # second pass: meld from right to left
        res = None
        for node in reversed(paired):
            res = self.meld_nodes(res, node)
        self.root = res
        self.size -= 1
        return (min_key, min_value)

def _validate_order(o):
    if not isinstance(o, list) or len(o) != 3:
        return False
    pr, side, price = o
    if not isinstance(pr, int):
        return False
    if side not in ('buy','sell'):
        return False
    if not (isinstance(price, int) or isinstance(price, float)):
        return False
    if price < 0:
        return False
    return True

def meldable_priority_queue(order_streams: List[List]) -> List:
    if not isinstance(order_streams, list):
        return []
    # ingest per-stream heaps
    arrival = 0
    per_stream_buy_heaps: List[PairingHeap] = []
    per_stream_sell_heaps: List[PairingHeap] = []
    any_orders = False
    for stream in order_streams:
        if not isinstance(stream, list):
            return []
        buy_heap = PairingHeap()
        sell_heap = PairingHeap()
        for order in stream:
            if not _validate_order(order):
                return []
            any_orders = True
            pr, side, price = order
            # arrival_index assigned in stream-major order
            # For buy heap we store key as ( -price, priority, arrival )
            # For sell heap key as ( price, priority, arrival )
            if side == 'buy':
                key = (-price, pr, arrival)
                buy_heap.insert(key, (pr, side, price, arrival))
            else:
                key = (price, pr, arrival)
                sell_heap.insert(key, (pr, side, price, arrival))
            arrival += 1
        per_stream_buy_heaps.append(buy_heap)
        per_stream_sell_heaps.append(sell_heap)
    if not any_orders:
        return []
    # meld all per-stream heaps into global heaps
    global_buy = PairingHeap()
    global_sell = PairingHeap()
    for h in per_stream_buy_heaps:
        global_buy.meld(h)
    for h in per_stream_sell_heaps:
        global_sell.meld(h)
    # matching loop
    while global_buy.size > 0 and global_sell.size > 0:
        bpeek = global_buy.peek_min()
        speek = global_sell.peek_min()
        if bpeek is None or speek is None:
            break
        bkey, bval = bpeek
        skey, sval = speek
        # extract original prices: buy stored -price
        bprice = -bkey[0]
        sprice = skey[0]
        if bprice >= sprice:
            global_buy.pop_min()
            global_sell.pop_min()
        else:
            break
    # collect remaining orders
    remaining = []
    while global_buy.size > 0:
        _, v = global_buy.pop_min()
        remaining.append(v)
    while global_sell.size > 0:
        _, v = global_sell.pop_min()
        remaining.append(v)
    # build final sort key: (priority ASC, side ('buy'<'sell'), price_aggressiveness, arrival_index)
    def final_key(entry: Tuple[int,str,float,int]):
        pr, side, price, arr = entry
        side_rank = 0 if side == 'buy' else 1
        # price aggressiveness: buys more aggressive at higher prices -> -price
        # sells more aggressive at lower prices -> +price
        price_aggr = -price if side == 'buy' else price
        return (pr, side_rank, price_aggr, arr)
    remaining.sort(key=final_key)
    # return in required format [priority, side, price]
    return [[pr, side, price] for (pr, side, price, arr) in remaining]