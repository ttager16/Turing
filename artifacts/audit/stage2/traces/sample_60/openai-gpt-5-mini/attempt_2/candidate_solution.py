def __init__(self, key: float):
        self.key = key
        self.prio = random.randrange(1 << 30)
        self.left = None
        self.right = None
        self.size = 1
        self.max_key = key
        # metadata
        self.last_update_ts = time.time()
        self.volume = 0.0
        self.risk = 0.0

def _size(n: Optional[Node]) -> int:
    return n.size if n else 0

def _max_key(n: Optional[Node]) -> Optional[float]:
    return n.max_key if n else None

def _pull(n: Node):
    n.size = 1 + _size(n.left) + _size(n.right)
    n.max_key = n.key
    if n.left and n.left.max_key > n.max_key:
        n.max_key = n.left.max_key
    if n.right and n.right.max_key > n.max_key:
        n.max_key = n.right.max_key

def _clone(n: Optional[Node]) -> Optional[Node]:
    if n is None: return None
    c = Node(n.key)
    c.prio = n.prio
    c.left = n.left
    c.right = n.right
    c.size = n.size
    c.max_key = n.max_key
    c.last_update_ts = n.last_update_ts
    c.volume = n.volume
    c.risk = n.risk
    return c

def _split(root: Optional[Node], key: float):
    if root is None:
        return (None, None)
    root = _clone(root)
    if key < root.key:
        left, right = _split(root.left, key)
        root.left = right
        _pull(root)
        return (left, root)
    else:
        left, right = _split(root.right, key)
        root.right = left
        _pull(root)
        return (root, right)

def _merge(a: Optional[Node], b: Optional[Node]) -> Optional[Node]:
    if a is None: return b
    if b is None: return a
    if a.prio > b.prio:
        a = _clone(a)
        a.right = _merge(a.right, b)
        _pull(a)
        return a
    else:
        b = _clone(b)
        b.left = _merge(a, b.left)
        _pull(b)
        return b

def _exists(root: Optional[Node], key: float) -> bool:
    cur = root
    while cur:
        if key == cur.key: return True
        if key < cur.key:
            cur = cur.left
        else:
            cur = cur.right
    return False

def _insert(root: Optional[Node], node: Node) -> Optional[Node]:
    if root is None:
        return node
    if node.prio > root.prio:
        left, right = _split(root, node.key)
        node.left = left
        node.right = right
        _pull(node)
        return node
    root = _clone(root)
    if node.key < root.key:
        root.left = _insert(root.left, node)
    elif node.key > root.key:
        root.right = _insert(root.right, node)
    else:
        # duplicate keys: replace metadata and timestamp
        root.last_update_ts = time.time()
    _pull(root)
    return root

def _erase(root: Optional[Node], key: float) -> Optional[Node]:
    if root is None: return None
    root = _clone(root)
    if key == root.key:
        res = _merge(root.left, root.right)
        return res
    elif key < root.key:
        root.left = _erase(root.left, key)
    else:
        root.right = _erase(root.right, key)
    _pull(root)
    return root

def _max_le(root: Optional[Node], value: float) -> Optional[float]:
    # find maximum key <= value
    cur = root
    res = None
    while cur:
        if cur.key <= value:
            if res is None or cur.key > res:
                res = cur.key
            # also maybe right subtree has larger <= value
            cur = cur.right
        else:
            cur = cur.left
    return res

def update_and_query_stock_tree(operations: List[Tuple[str, int]]) -> List[Optional[float]]:
    random.seed(123456)
    root: Optional[Node] = None
    out: List[Optional[float]] = []
    # history stack stores tuples describing inverse operations to allow rollback
    # We store entries only for mutating ops. Each entry is a callable snapshot via lambdas: we store the previous root.
    history: List[Optional[Node]] = []
    for op in operations:
        typ = op[0]
        if typ == 'insert':
            val = float(op[1])
            history.append(root)  # save previous state for rollback
            if not _exists(root, val):
                node = Node(val)
                node.last_update_ts = time.time()
                node.volume = 1.0
                node.risk = 0.0
                root = _insert(root, node)
            else:
                # update metadata timestamp
                # perform an update path by erasing and re-inserting to update clone path
                root = _erase(root, val)
                node = Node(val)
                node.last_update_ts = time.time()
                node.volume = 1.0
                root = _insert(root, node)
            out.append(None)
        elif typ == 'delete':
            val = float(op[1])
            history.append(root)
            if _exists(root, val):
                root = _erase(root, val)
            out.append(None)
        elif typ == 'bulk_insert':
            # interpret integer as center value; insert a small batch around it
            center = float(op[1])
            history.append(root)
            # create a deterministic set around center, including center and +/- offsets
            offsets = [-2, -1, 0, 1, 2]
            for d in offsets:
                v = center + d
                if not _exists(root, v):
                    node = Node(v)
                    node.last_update_ts = time.time()
                    node.volume = 1.0 + abs(d)
                    node.risk = max(0.0, 1.0 - abs(d)*0.1)
                    root = _insert(root, node)
                else:
                    # refresh metadata
                    root = _erase(root, v)
                    node = Node(v)
                    node.last_update_ts = time.time()
                    node.volume = 1.0 + abs(d)
                    node.risk = max(0.0, 1.0 - abs(d)*0.1)
                    root = _insert(root, node)
            out.append(None)
        elif typ == 'rollback':
            # rollback last k mutating ops. op[1] is number of operations to revert.
            k = int(op[1])
            # find last k mutating changes in history (history saves state before each mutating op)
            # If k >= len(history): revert to empty (None)
            target_index = len(history) - k
            if target_index < 0:
                root = None
                history = []
            else:
                root = history[target_index]
                history = history[:target_index]
            out.append(None)
        elif typ == 'query':
            val = float(op[1])
            res = _max_le(root, val)
            out.append(res)
        else:
            # unknown op: ignore
            out.append(None)
    return out