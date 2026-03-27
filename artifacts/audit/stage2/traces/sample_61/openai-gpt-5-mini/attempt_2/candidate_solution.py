def __init__(self, key: int):
        self.key = key
        self.height = 1
        self.left: Optional['AVLNode'] = None
        self.right: Optional['AVLNode'] = None

def _height(node: Optional[AVLNode]) -> int:
    return node.height if node else 0

def _update_height(node: AVLNode) -> None:
    node.height = 1 + max(_height(node.left), _height(node.right))

def _balance_factor(node: AVLNode) -> int:
    return _height(node.left) - _height(node.right)

def _rotate_right(y: AVLNode) -> AVLNode:
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    _update_height(y)
    _update_height(x)
    return x

def _rotate_left(x: AVLNode) -> AVLNode:
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    _update_height(x)
    _update_height(y)
    return y

def _rebalance(node: AVLNode) -> AVLNode:
    _update_height(node)
    bf = _balance_factor(node)
    if bf > 1:
        if _balance_factor(node.left) < 0:
            node.left = _rotate_left(node.left)
        return _rotate_right(node)
    if bf < -1:
        if _balance_factor(node.right) > 0:
            node.right = _rotate_right(node.right)
        return _rotate_left(node)
    return node

def _avl_insert(node: Optional[AVLNode], key: int) -> AVLNode:
    if node is None:
        return AVLNode(key)
    if key < node.key:
        node.left = _avl_insert(node.left, key)
    elif key > node.key:
        node.right = _avl_insert(node.right, key)
    else:
        return node
    return _rebalance(node)

def _find_min(node: AVLNode) -> AVLNode:
    current = node
    while current.left:
        current = current.left
    return current

def _avl_delete(node: Optional[AVLNode], key: int) -> Optional[AVLNode]:
    if node is None:
        return None
    if key < node.key:
        node.left = _avl_delete(node.left, key)
    elif key > node.key:
        node.right = _avl_delete(node.right, key)
    else:
        if node.left is None:
            return node.right
        elif node.right is None:
            return node.left
        else:
            succ = _find_min(node.right)
            node.key = succ.key
            node.right = _avl_delete(node.right, succ.key)
    if node is None:
        return None
    return _rebalance(node)

def _avl_search(node: Optional[AVLNode], key: int) -> Optional[int]:
    current = node
    while current:
        if key == current.key:
            return current.key
        elif key < current.key:
            current = current.left
        else:
            current = current.right
    return None

def handle_orders(operations: List[List]) -> List:
    if not isinstance(operations, list):
        return []
    root: Optional[AVLNode] = None
    results: List = []
    for op in operations:
        if not isinstance(op, list) or len(op) != 2:
            return []
        typ, val = op[0], op[1]
        if not isinstance(typ, str):
            return []
        cmd = typ.strip().lower()
        if not isinstance(val, int) or isinstance(val, bool):
            return []
        if cmd == 'insert':
            root = _avl_insert(root, val)
            results.append(None)
        elif cmd == 'delete':
            root = _avl_delete(root, val)
            results.append(None)
        elif cmd == 'search':
            res = _avl_search(root, val)
            results.append(res)
        else:
            return []
    return results