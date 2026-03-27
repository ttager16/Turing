from typing import List


class AVLNode:
    """
    Node class for AVL tree implementation.
    Maintains price data, height, and balance information.
    """
    def __init__(self, price: float):
        self.price = price
        self.left = None
        self.right = None
        self.height = 1
        self.size = 1  # Number of nodes in the subtree (including this node)


class AVLTree:
    """
    AVL Tree implementation for efficiently storing and querying market prices.
    Provides O(log n) operations for find, insert, and update operations.
    """
    def __init__(self):
        self.root = None
    
    def _height(self, node: AVLNode) -> int:
        """Get the height of a node (0 for None nodes)."""
        return node.height if node else 0
    
    def _size(self, node: AVLNode) -> int:
        """Get the size of a subtree (0 for None nodes)."""
        return node.size if node else 0
    
    def _update_node(self, node: AVLNode) -> None:
        """Update the height and size of a node based on its children."""
        if node:
            node.height = max(self._height(node.left), self._height(node.right)) + 1
            node.size = self._size(node.left) + self._size(node.right) + 1
    
    def _balance_factor(self, node: AVLNode) -> int:
        """Calculate the balance factor of a node."""
        return self._height(node.left) - self._height(node.right) if node else 0
    
    def _right_rotate(self, y: AVLNode) -> AVLNode:
        """Perform a right rotation on node y."""
        x = y.left
        T2 = x.right
        
        # Perform rotation
        x.right = y
        y.left = T2
        
        # Update heights and sizes
        self._update_node(y)
        self._update_node(x)
        
        return x
    
    def _left_rotate(self, x: AVLNode) -> AVLNode:
        """Perform a left rotation on node x."""
        y = x.right
        T2 = y.left
        
        # Perform rotation
        y.left = x
        x.right = T2
        
        # Update heights and sizes
        self._update_node(x)
        self._update_node(y)
        
        return y
    
    def _rebalance(self, node: AVLNode) -> AVLNode:
        """Rebalance the tree if needed after an insertion or deletion."""
        if not node:
            return None
        
        # Update height and size
        self._update_node(node)
        
        # Get balance factor
        balance = self._balance_factor(node)
        
        # Left heavy
        if balance > 1:
            # Left-Right case
            if self._balance_factor(node.left) < 0:
                node.left = self._left_rotate(node.left)
            # Left-Left case
            return self._right_rotate(node)
        
        # Right heavy
        if balance < -1:
            # Right-Left case
            if self._balance_factor(node.right) > 0:
                node.right = self._right_rotate(node.right)
            # Right-Right case
            return self._left_rotate(node)
        
        return node
    
    def insert(self, price: float) -> None:
        """Insert a new price into the AVL tree."""
        self.root = self._insert(self.root, price)
    
    def _insert(self, node: AVLNode, price: float) -> AVLNode:
        """Helper method to insert a price into the AVL tree recursively."""
        # Perform standard BST insertion
        if not node:
            return AVLNode(price)
        
        if price < node.price:
            node.left = self._insert(node.left, price)
        elif price > node.price:
            node.right = self._insert(node.right, price)
        else:
            # Price already exists, no need to insert
            return node
        
        # Rebalance the tree
        return self._rebalance(node)
    
    def delete(self, price: float) -> None:
        """Delete a price from the AVL tree."""
        self.root = self._delete(self.root, price)
    
    def _delete(self, node: AVLNode, price: float) -> AVLNode:
        """Helper method to delete a node with a specific price."""
        if not node:
            return None
        
        # Standard BST deletion
        if price < node.price:
            node.left = self._delete(node.left, price)
        elif price > node.price:
            node.right = self._delete(node.right, price)
        else:
            # Node with the price found
            
            # Case 1: Node with only one child or no child
            if not node.left:
                return node.right
            elif not node.right:
                return node.left
            
            # Case 2: Node with two children
            # Find inorder successor (smallest in the right subtree)
            successor = self._find_min_node(node.right)
            # Copy the successor's price to this node
            node.price = successor.price
            # Delete the successor
            node.right = self._delete(node.right, successor.price)
        
        # Rebalance if needed
        return self._rebalance(node)
    
    def _find_min_node(self, node: AVLNode) -> AVLNode:
        """Find the node with the minimum price in the subtree."""
        current = node
        while current.left:
            current = current.left
        return current
    
    def find_index(self, price: float) -> int:
        """
        Find the index of a price in the sorted order using O(log n) traversal.
        Returns -1 if the price is not found.
        """
        return self._find_index(self.root, price, 0)
    
    def _find_index(self, node: AVLNode, price: float, left_count: int) -> int:
        """
        Helper method to find the index of a price.
        left_count tracks the number of nodes to the left of the current path.
        """
        if not node:
            return -1
        
        if price < node.price:
            # Search in left subtree
            return self._find_index(node.left, price, left_count)
        elif price > node.price:
            # Search in right subtree
            # Add all nodes in left subtree + current node to left_count
            new_left_count = left_count + self._size(node.left) + 1
            return self._find_index(node.right, price, new_left_count)
        else:
            # Found the price
            # Index is the number of nodes in left subtree + accumulated left_count
            return left_count + self._size(node.left)
    
    def contains(self, price: float) -> bool:
        """Check if a price exists in the tree."""
        return self._contains(self.root, price)
    
    def _contains(self, node: AVLNode, price: float) -> bool:
        """Helper method to check if a price exists."""
        if not node:
            return False
        
        if price < node.price:
            return self._contains(node.left, price)
        elif price > node.price:
            return self._contains(node.right, price)
        else:
            return True


class Market:
    """
    Represents a single market with an efficient AVL tree for storing prices.
    Provides O(log n) operations for finding and updating prices.
    """
    def __init__(self, prices: List[float]):
        """Initialize a market with the given list of prices."""
        self.tree = AVLTree()
        for price in prices:
            self.tree.insert(price)
    
    def find(self, price: float) -> int:
        """
        Find the index of a price in the market.
        Returns -1 if the price is not found.
        """
        return self.tree.find_index(price)
    
    def update(self, price: float) -> None:
        """
        Update the market with a new price using REPLACE PREDECESSOR logic.
        Replaces the value immediately before where price would be inserted.
        If no predecessor exists (empty or price is smallest), just insert.
        If price already exists, operation is idempotent.
        """
        # If tree is empty, just insert
        if not self.tree.root:
            self.tree.insert(price)
            return
        
        # Check if price already exists
        if self.tree.contains(price):
            return  # Idempotent
        
        # Find the predecessor (largest value < price)
        predecessor = self._find_predecessor(price)
        
        if predecessor is not None:
            # Replace predecessor with new price
            self.tree.delete(predecessor)
            self.tree.insert(price)
        else:
            # No predecessor, just insert
            self.tree.insert(price)
    
    def _find_predecessor(self, price: float) -> float:
        """Find the largest value strictly less than the given price."""
        if not self.tree.root:
            return None
        
        predecessor = None
        node = self.tree.root
        
        while node:
            if node.price < price:
                # This could be the predecessor
                predecessor = node.price
                # Try to find a larger predecessor in right subtree
                node = node.right
            else:
                # node.price >= price, go left
                node = node.left
        
        return predecessor


def manage_high_freq_trades(
    markets: List[List[float]],
    operations: List[str],
    prices: List[float],
    market_indices: List[int]
) -> List[int]:
    """
    Processes a list of markets (each a sorted list of stock prices) and
    executes a sequence of high-frequency trading operations.

    Each query is represented by aligned entries across:
    - operations[i]: a string, either 'FIND' or 'UPDATE'
    - prices[i]: the float value relevant to the operation
    - market_indices[i]: the index of the target market

    Behavior:
    - 'FIND' returns the zero-based index of the price in the specified market, or -1 if not found.
    - 'UPDATE' modifies the market by inserting or replacing the given price (no direct output).

    Returns:
    A list of integers corresponding only to 'FIND' queries, preserving their order of execution.
    """
    # Initialize markets with AVL trees
    market_managers = [Market(market) for market in markets]
    results = []
    
    # Process each operation
    for i in range(len(operations)):
        operation = operations[i]
        price = prices[i]
        market_idx = market_indices[i]
        
        # Handle invalid market indices
        if market_idx < 0 or market_idx >= len(market_managers):
            if operation == "FIND":
                results.append(-1)
            continue
        
        if operation == "FIND":
            results.append(market_managers[market_idx].find(price))
        elif operation == "UPDATE":
            market_managers[market_idx].update(price)
    
    return results