from typing import List

def handle_orders(operations: List[List]) -> List:
    class AVLNode:
        def __init__(self, key):
            self.key = key
            self.left = None
            self.right = None
            self.height = 1

    def get_height(node):
        return node.height if node else 0

    def update_height(node):
        node.height = max(get_height(node.left), get_height(node.right)) + 1

    def balance_factor(node):
        return get_height(node.left) - get_height(node.right)

    def rotate_right(node):
        new_root = node.left
        temp = new_root.right if new_root else None
        new_root.right = node
        node.left = temp
        update_height(node)
        update_height(new_root)
        return new_root

    def rotate_left(node):
        new_root = node.right
        temp = new_root.left if new_root else None
        new_root.left = node
        node.right = temp
        update_height(node)
        update_height(new_root)
        return new_root

    def rebalance(node):
        update_height(node)
        bf = balance_factor(node)
        if bf > 1 and balance_factor(node.left) >= 0:
            return rotate_right(node)
        if bf > 1 and balance_factor(node.left) < 0:
            node.left = rotate_left(node.left)
            return rotate_right(node)
        if bf < -1 and balance_factor(node.right) <= 0:
            return rotate_left(node)
        if bf < -1 and balance_factor(node.right) > 0:
            node.right = rotate_right(node.right)
            return rotate_left(node)
        return node

    def insert_node(root, key):
        if root is None:
            return AVLNode(key)
        if key < root.key:
            root.left = insert_node(root.left, key)
        elif key > root.key:
            root.right = insert_node(root.right, key)
        else:
            return root
        return rebalance(root)

    def find_min_node(node):
        while node.left:
            node = node.left
        return node

    def delete_node(root, key):
        if root is None:
            return None
        if key < root.key:
            root.left = delete_node(root.left, key)
        elif key > root.key:
            root.right = delete_node(root.right, key)
        else:
            if root.left is None or root.right is None:
                root = root.left or root.right
            else:
                successor = find_min_node(root.right)
                root.key = successor.key
                root.right = delete_node(root.right, successor.key)
        if root is None:
            return None
        return rebalance(root)

    def search_node(root, key):
        current = root
        while current:
            if key < current.key:
                current = current.left
            elif key > current.key:
                current = current.right
            else:
                return current.key
        return None

    if not isinstance(operations, list):
        return []

    valid_ops = {"insert", "delete", "search"}
    root = None
    results = []

    for entry in operations:
        if not isinstance(entry, list) or len(entry) != 2:
            return []
        action, value = entry[0], entry[1]
        if not isinstance(action, str):
            return []
        action_lower = action.lower()
        if action_lower not in valid_ops:
            return []
        if not isinstance(value, int) or isinstance(value, bool):
            return []
        if action_lower == "insert":
            root = insert_node(root, value)
            results.append(None)
        elif action_lower == "delete":
            root = delete_node(root, value)
            results.append(None)
        else:
            results.append(search_node(root, value))

    return results


if __name__ == "__main__":
    operations = [
        ["insert", 300],
        ["insert", 450],
        ["delete", 300],
        ["search", 450]
    ]
    print(handle_orders(operations))