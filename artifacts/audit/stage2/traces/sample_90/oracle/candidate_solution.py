from typing import List, Optional, Any
import heapq


def real_time_stock_stack(operations: List[List[Any]]) -> List[Optional[int]]:
    if not isinstance(operations, list) or len(operations) == 0:
        return []

    valid_ops = {"push", "pop", "get_min", "get_max", "merge_clusters", "range_sum"}

    def is_valid_int(x):
        return isinstance(x, int) and -10**9 <= x <= 10**9

    def is_valid_symbol_arg(x):
        return (x is None) or (isinstance(x, int) and x >= 0)

    symbols = [Symbol()]
    active_symbol_id = 0
    last_pushed_symbol = None
    redirect_symbol = None

    global_min_heap = []
    global_max_heap = []

    def update_global_heaps(symbol_id):
        symbol = symbols[symbol_id]
        min_val = symbol.get_min()
        max_val = symbol.get_max()
        if min_val is not None:
            heapq.heappush(global_min_heap, (min_val, symbol_id, symbol.version))
        if max_val is not None:
            heapq.heappush(global_max_heap, (-max_val, symbol_id, symbol.version))

    def get_global_min():
        while global_min_heap:
            min_val, symbol_id, ver = global_min_heap[0]
            symbol = symbols[symbol_id]
            current = symbol.get_min()
            if current is None or symbol.version != ver or current != min_val:
                heapq.heappop(global_min_heap)
                continue
            return min_val
        return None

    def get_global_max():
        while global_max_heap:
            neg_val, symbol_id, ver = global_max_heap[0]
            symbol = symbols[symbol_id]
            current = symbol.get_max()
            if current is None or symbol.version != ver or current != -neg_val:
                heapq.heappop(global_max_heap)
                continue
            return -neg_val
        return None

    results = []

    for operation in operations:
        if not isinstance(operation, list) or len(operation) != 2:
            return []
        name, arg = operation[0], operation[1]
        if not isinstance(name, str) or name not in valid_ops:
            return []

        if name == "push":
            if not isinstance(arg, int) or not is_valid_int(arg):
                return []
        elif name == "pop":
            if arg is not None:
                return []
        elif name in ("get_min", "get_max", "range_sum"):
            if not is_valid_symbol_arg(arg):
                return []
        elif name == "merge_clusters":
            if arg is not None:
                return []
        else:
            return []

        if name == "push":
            target = redirect_symbol if redirect_symbol is not None else active_symbol_id
            redirect_symbol = None
            symbols[target].push_value(arg)
            update_global_heaps(target)
            last_pushed_symbol = target
            results.append(None)

        elif name == "pop":
            target = last_pushed_symbol if last_pushed_symbol is not None else active_symbol_id
            symbols[target].pop_value()
            update_global_heaps(target)
            results.append(None)

        elif name == "get_min":
            if arg is None:
                results.append(get_global_min())
            else:
                if arg >= len(symbols):
                    return []
                results.append(symbols[arg].get_min())

        elif name == "get_max":
            if arg is None:
                results.append(get_global_max())
            else:
                if arg >= len(symbols):
                    return []
                results.append(symbols[arg].get_max())

        elif name == "merge_clusters":
            source = symbols[active_symbol_id]
            new_symbol = source.clone()
            source.baseline_sum = source.stack_sum
            new_symbol.baseline_sum = new_symbol.stack_sum
            symbols.append(new_symbol)
            new_id = len(symbols) - 1
            redirect_symbol = new_id
            update_global_heaps(new_id)
            results.append(None)

        elif name == "range_sum":
            if arg is None or arg >= len(symbols):
                return []
            symbol = symbols[arg]
            results.append(symbol.baseline_sum if symbol.baseline_sum is not None else symbol.total_pushed_sum)

    return results


class Symbol:
    def __init__(self):
        self.values = []
        self.min_values = []
        self.max_values = []
        self.stack_sum = 0
        self.total_pushed_sum = 0
        self.baseline_sum = None
        self.version = 0

    def clone(self):
        _symbol = Symbol()
        _symbol.values = self.values.copy()
        _symbol.min_values = self.min_values.copy()
        _symbol.max_values = self.max_values.copy()
        _symbol.stack_sum = self.stack_sum
        _symbol.total_pushed_sum = self.total_pushed_sum
        return _symbol

    def push_value(self, value):
        self.values.append(value)
        self.stack_sum += value
        self.total_pushed_sum += value
        if self.min_values:
            self.min_values.append(min(self.min_values[-1], value))
            self.max_values.append(max(self.max_values[-1], value))
        else:
            self.min_values.append(value)
            self.max_values.append(value)
        self.version += 1

    def pop_value(self):
        if not self.values:
            return None
        value = self.values.pop()
        self.stack_sum -= value
        self.min_values.pop()
        self.max_values.pop()
        self.version += 1
        return value

    def get_min(self):
        return self.min_values[-1] if self.min_values else None

    def get_max(self):
        return self.max_values[-1] if self.max_values else None

if __name__ == "__main__":
    operations = [
        ['push', 100],
        ['push', 250],
        ['get_max', None],
        ['push', 80],
        ['merge_clusters', None],
        ['get_min', None],
        ['pop', None],
        ['push', 300],
        ['get_min', 1],
        ['get_max', 0],
        ['range_sum', 0],
        ['pop', None],
        ['get_max', None]
    ]
    print(real_time_stock_stack(operations))