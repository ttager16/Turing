from typing import List, Union

def manage_inventory(operations: List[List[Union[str, int]]]) -> List[int]:
    """
    Manage inventory using a dynamic Fenwick Tree approach.

    Parameters:
    operations: List of operations where each operation is a list:
      - ["add", value] -> append a new product with stock `value`
      - ["remove", index] -> remove product at logical index `index` (1-based)
      - ["update", index, delta] -> add `delta` to product at logical index `index` (1-based)
      - ["query", index] -> return prefix sum of stocks from logical index 1 to `index` (inclusive)
    Returns:
    List[int]: results of each "query" operation in order.
    """
    class FenwickTree:
        def __init__(self):
            self.tree = [0]
            self.size = 0

        def _resize(self, new_size):
            if new_size > self.size:
                self.tree += [0] * (new_size - self.size)
                self.size = new_size

        def update(self, i, delta):
            while i <= self.size:
                self.tree[i] += delta
                i += i & -i

        def query(self, i):
            res = 0
            while i > 0:
                res += self.tree[i]
                i -= i & -i
            return res

    tree = FenwickTree()
    stocks = []
    result = []

    for op in operations:
        if not op:
            continue
        t = op[0]

        if t == "add" and len(op) == 2:
            v = op[1]
            stocks.append(v)
            new_size = len(stocks)
            new_tree = FenwickTree()
            new_tree._resize(new_size)
            for idx, val in enumerate(stocks, 1):
                new_tree.update(idx, val)
            tree = new_tree

        elif t == "remove" and len(op) == 2:
            i = op[1]
            if 1 <= i <= len(stocks):
                stocks.pop(i - 1)
                new_tree = FenwickTree()
                new_tree._resize(len(stocks))
                for idx, val in enumerate(stocks, 1):
                    new_tree.update(idx, val)
                tree = new_tree

        elif t == "update" and len(op) == 3:
            i, d = op[1], op[2]
            if 1 <= i <= len(stocks):
                stocks[i - 1] += d
                tree.update(i, d)

        elif t == "query" and len(op) == 2:
            i = op[1]
            result.append(tree.query(i) if 1 <= i <= len(stocks) else 0)

    return result

if __name__ == "__main__":
    operations = [
        ["add", 10],
        ["add", 20],
        ["add", 15],
        ["query", 2],
        ["update", 3, 5],
        ["remove", 1],
        ["query", 2]
    ]
    output = manage_inventory(operations)
    print(output)