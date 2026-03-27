def __init__(self, key:int, prio:int=None, last_update:float=None, volume:float=0.0):
        self.key = key
        self.prio = prio if prio is not None else random.randrange(1<<30)
        self.left = None
        self.right = None
        self.last_update = last_update if last_update is not None else time.time()
        self.volume = volume
        self.size = 1
        self.max_key = key

def _size(node:Optional[TreapNode]) -> int:
    return node.size if node else 0

def _recalc(node:TreapNode):
    node.size = 1 + _size(node.left) + _size(node.right)
    node.max_key = node.key
    if node.left and node.left.max_key > node.max_key:
        node.max_key = node.left.max_key
    if node.right and node.right.max_key > node.max_key:
        node.max_key = node.right.max_key

def _clone_node(node:Optional[TreapNode]) -> Optional[TreapNode]:
    if node is None: return None
    n = TreapNode(node.key, node.prio, node.last_update, node.volume)
    n.left = node.left
    n.right = node.right
    n.size = node.size
    n.max_key = node.max_key
    return n

def _split(root:Optional[TreapNode], key:int) -> Tuple[Optional[TreapNode], Optional[TreapNode]]:
    # split into <=key and >key
    if root is None:
        return None, None
    root = _clone_node(root)
    if root.key <= key:
        l, r = _split(root.right, key)
        root.right = l
        _recalc(root)
        return root, r
    else:
        l, r = _split(root.left, key)
        root.left = r
        _recalc(root)
        return l, root

def _merge(a:Optional[TreapNode], b:Optional[TreapNode]) -> Optional[TreapNode]:
    if a is None: return b
    if b is None: return a
    if a.prio > b.prio:
        a = _clone_node(a)
        a.right = _merge(a.right, b)
        _recalc(a)
        return a
    else:
        b = _clone_node(b)
        b.left = _merge(a, b.left)
        _recalc(b)
        return b

def _contains(root:Optional[TreapNode], key:int) -> bool:
    cur = root
    while cur:
        if key == cur.key: return True
        cur = cur.left if key < cur.key else cur.right
    return False

def _insert(root:Optional[TreapNode], node:TreapNode) -> Optional[TreapNode]:
    if root is None:
        return node
    if node.prio > root.prio:
        left, right = _split(root, node.key)
        node.left = left
        node.right = right
        _recalc(node)
        return node
    root = _clone_node(root)
    if node.key < root.key:
        root.left = _insert(root.left, node)
    elif node.key > root.key:
        root.right = _insert(root.right, node)
    else:
        # replace metadata for equal key
        root.last_update = node.last_update
        root.volume = node.volume
    _recalc(root)
    return root

def _erase(root:Optional[TreapNode], key:int) -> Optional[TreapNode]:
    if root is None: return None
    root = _clone_node(root)
    if key < root.key:
        root.left = _erase(root.left, key)
        _recalc(root)
        return root
    elif key > root.key:
        root.right = _erase(root.right, key)
        _recalc(root)
        return root
    else:
        return _merge(root.left, root.right)

def _max_le(root:Optional[TreapNode], key:int) -> Optional[int]:
    # find maximum key <= key
    cur = root
    ans = None
    while cur:
        if cur.key <= key:
            if ans is None or cur.key > ans:
                ans = cur.key
            cur = cur.right
        else:
            cur = cur.left
    return ans

def update_and_query_stock_tree(operations: List[Tuple[str, int]]) -> List[Optional[float]]:
    results: List[Optional[float]] = []
    root: Optional[TreapNode] = None
    # history stack stores previous roots for rollback (partial by count)
    history: List[Optional[TreapNode]] = []
    # For simulated concurrency, we also keep an op log with timestamps and metadata for possible partial rollbacks
    op_log: List[Tuple[str, Any]] = []
    for op in operations:
        cmd = op[0]
        if cmd == 'insert':
            val = op[1]
            # save state
            history.append(root)
            op_log.append(('insert', val))
            if not _contains(root, val):
                node = TreapNode(val)
                root = _insert(root, node)
            else:
                # update metadata
                # replace by erase+insert to update timestamp
                root = _erase(root, val)
                node = TreapNode(val)
                root = _insert(root, node)
            results.append(None)
        elif cmd == 'delete':
            val = op[1]
            history.append(root)
            op_log.append(('delete', val))
            if _contains(root, val):
                root = _erase(root, val)
            results.append(None)
        elif cmd == 'bulk_insert':
            center = op[1]
            history.append(root)
            op_log.append(('bulk_insert', center))
            # insert a small interval around center for simulation: center-2..center+2
            for d in range(-2,3):
                v = center + d
                if not _contains(root, v):
                    root = _insert(root, TreapNode(v))
                else:
                    root = _erase(root, v)
                    root = _insert(root, TreapNode(v))
            results.append(None)
        elif cmd == 'rollback':
            # rollback last k operations if provided as int; op[1] is count
            k = op[1]
            # clamp
            k = max(0, min(k, len(history)))
            if k == 0:
                results.append(None)
                continue
            # Rollback k steps: restore root to state before the last k operations.
            # history stores root before each mutating op; last entry is before last op.
            # So restoring history[-k] would revert k most recent mutating ops.
            target_index = len(history) - k
            root = history[target_index] if target_index >= 0 else None
            # truncate history and op_log
            history = history[:target_index]
            op_log = op_log[:target_index]
            results.append(None)
        elif cmd == 'query':
            val = op[1]
            ans = _max_le(root, val)
            results.append(float(ans) if ans is not None else None)
        else:
            # unknown op - ignore
            results.append(None)
    return results