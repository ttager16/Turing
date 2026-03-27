def __init__(self, key, value):
        self.key = key
        self.value = value
        self.child = None
        self.sibling = None

def meld(a: PairNode, b: PairNode):
    if a is None: return b
    if b is None: return a
    if a.key <= b.key:
        # attach b as first child of a
        b.sibling = a.child
        a.child = b
        return a
    else:
        a.sibling = b.child
        b.child = a
        return b

def insert_node(root: PairNode, node: PairNode):
    return meld(root, node)

def pop_min_node(root: PairNode):
    if root is None:
        return None, None
    min_node = root
    # two-pass pairing of children
    # first pass: pair siblings left to right
    pairs = []
    child = root.child
    while child:
        a = child
        b = None
        nextsib = child.sibling
        if nextsib:
            b = nextsib
            child = nextsib.sibling
        else:
            child = None
        a.sibling = None
        if b:
            b.sibling = None
            pairs.append(meld(a, b))
        else:
            pairs.append(a)
    # second pass: meld right-to-left
    newroot = None
    for node in reversed(pairs):
        newroot = meld(newroot, node)
    return min_node, newroot

def validate_order(o):
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
    # per-stream heaps
    per_buy_roots = []
    per_sell_roots = []
    arrival = 0
    any_orders = False
    for stream in order_streams:
        if not isinstance(stream, list):
            return []
        buy_root = None
        sell_root = None
        for order in stream:
            if not validate_order(order):
                return []
            any_orders = True
            pr, side, price = order
            # arrival index
            arr = arrival
            arrival += 1
            # create entries for per-stream heaps
            # buy heap: min-heap on (-price, priority, arrival)
            # sell heap: min-heap on (price, priority, arrival)
            if side == 'buy':
                key = (-float(price), pr, arr)
                node = PairNode(key, [pr, side, float(price), arr])
                buy_root = insert_node(buy_root, node)
            else:
                key = (float(price), pr, arr)
                node = PairNode(key, [pr, side, float(price), arr])
                sell_root = insert_node(sell_root, node)
        per_buy_roots.append(buy_root)
        per_sell_roots.append(sell_root)
    if not any_orders:
        return []
    # meld all per-stream heaps into global heaps
    buy_root = None
    sell_root = None
    for r in per_buy_roots:
        buy_root = meld(buy_root, r)
    for r in per_sell_roots:
        sell_root = meld(sell_root, r)
    # matching: while best_buy.price >= best_sell.price
    while buy_root is not None and sell_root is not None:
        best_buy_node, buy_root_after = pop_min_node(buy_root)
        best_sell_node, sell_root_after = pop_min_node(sell_root)
        if best_buy_node is None or best_sell_node is None:
            # restore and break
            if best_buy_node:
                buy_root = meld(best_buy_node, buy_root_after)
            else:
                buy_root = buy_root_after
            if best_sell_node:
                sell_root = meld(best_sell_node, sell_root_after)
            else:
                sell_root = sell_root_after
            break
        buy_price = -best_buy_node.key[0]
        sell_price = best_sell_node.key[0]
        if buy_price >= sell_price:
            # match executed: discard both
            buy_root = buy_root_after
            sell_root = sell_root_after
            continue
        else:
            # cannot match: put them back and stop
            buy_root = meld(best_buy_node, buy_root_after)
            sell_root = meld(best_sell_node, sell_root_after)
            break
    # collect remaining orders
    remaining = []
    # drain buy heap
    while buy_root is not None:
        node, buy_root = pop_min_node(buy_root)
        if node:
            remaining.append(node.value)
    # drain sell heap
    while sell_root is not None:
        node, sell_root = pop_min_node(sell_root)
        if node:
            remaining.append(node.value)
    if not remaining:
        return []
    # each value is [pr, side, price, arrival]
    # global key: (priority ASC, side ('buy'<'sell'), price_aggressiveness, arrival_index ASC)
    # price_aggressiveness: for buy -> -price; for sell -> +price
    def global_key(v):
        pr, side, price, arr = v
        price_aggr = -price if side=='buy' else price
        side_key = 0 if side=='buy' else 1
        return (pr, side_key, price_aggr, arr)
    remaining.sort(key=global_key)
    # convert back to required [priority, side, price]
    return [[v[0], v[1], v[2]] for v in remaining]