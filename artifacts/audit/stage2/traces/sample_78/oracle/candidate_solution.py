from typing import List

def adaptive_heap_update(data_streams: List[List[List]]) -> List[str]:
    def is_valid_symbol(symbol):
        if type(symbol) is not str or not symbol:
            return False
        for char in symbol:
            if not ('A' <= char <= 'Z'):
                return False
        return True

    def validate_data(streams):
        if type(streams) is not list or len(streams) < 3:
            return False
        for exchange in streams:
            if type(exchange) is not list:
                return False
            for record in exchange:
                if type(record) is not list or len(record) != 3:
                    return False
                symbol, volatility, volume = record
                if type(symbol) is not str:
                    return False
                if type(volatility) is not float:
                    return False
                if type(volume) is not int:
                    return False
                if not is_valid_symbol(symbol):
                    return False
                if not (0.0 <= volatility <= 1.0):
                    return False
                if volume <= 0:
                    return False
        return True

    if not validate_data(data_streams):
        return []

    def has_higher_rank(a, b):
        if a[0] > b[0]:
            return True
        if a[0] < b[0]:
            return False
        if a[1] > b[1]:
            return True
        if a[1] < b[1]:
            return False
        return a[2] < b[2]

    class MaxHeap:
        def __init__(self):
            self.items = []

        def size(self):
            return len(self.items)

        def sift_up(self, index):
            heap = self.items
            while index > 0:
                parent_index = (index - 1) // 2
                if has_higher_rank(heap[index], heap[parent_index]):
                    heap[index], heap[parent_index] = heap[parent_index], heap[index]
                    index = parent_index
                else:
                    break

        def sift_down(self, index):
            heap = self.items
            length = len(heap)
            while True:
                left = 2 * index + 1
                right = 2 * index + 2
                best = index
                if left < length and has_higher_rank(heap[left], heap[best]):
                    best = left
                if right < length and has_higher_rank(heap[right], heap[best]):
                    best = right
                if best == index:
                    break
                heap[index], heap[best] = heap[best], heap[index]
                index = best

        def push(self, item):
            self.items.append(item)
            self.sift_up(len(self.items) - 1)

        def pop(self):
            if not self.items:
                return None
            heap = self.items
            heap[0], heap[-1] = heap[-1], heap[0]
            item = heap.pop()
            if heap:
                self.sift_down(0)
            return item
        
    latest_version = {}
    best_entry = {}

    exchange_heaps = []
    for exchange_index, exchange in enumerate(data_streams):
        heap = MaxHeap()
        for symbol, volatility, volume in exchange:
            priority = volatility * (volume ** 0.25)
            current_entry = (priority, volatility, symbol)
            if symbol not in latest_version:
                latest_version[symbol] = 1
                best_entry[symbol] = current_entry
                heap.push((priority, volatility, symbol, 1, exchange_index, volume))
            else:
                previous_entry = best_entry[symbol]
                if (current_entry[0] > previous_entry[0]) or \
                   (current_entry[0] == previous_entry[0] and current_entry[1] > previous_entry[1]) or \
                   (current_entry[0] == previous_entry[0] and current_entry[1] == previous_entry[1] and current_entry[2] < previous_entry[2]):
                    latest_version[symbol] += 1
                    version = latest_version[symbol]
                    best_entry[symbol] = current_entry
                    heap.push((priority, volatility, symbol, version, exchange_index, volume))
        exchange_heaps.append(heap)

    coordinator_heap = MaxHeap()
    for heap in exchange_heaps:
        top_item = heap.pop()
        if top_item is not None:
            coordinator_heap.push(top_item)

    final_result = []
    processed_symbols = set()

    while coordinator_heap.size() > 0:
        current_item = coordinator_heap.pop()
        if current_item is None:
            break
        _, _, symbol, version, exchange_id, _ = current_item
        if latest_version.get(symbol, -1) != version or symbol in processed_symbols:
            next_item = exchange_heaps[exchange_id].pop()
            if next_item is not None:
                coordinator_heap.push(next_item)
            continue
        final_result.append(symbol)
        processed_symbols.add(symbol)
        next_item = exchange_heaps[exchange_id].pop()
        if next_item is not None:
            coordinator_heap.push(next_item)

    return final_result


if __name__ == "__main__":
    data_streams = [
        [['AAPL', 0.05, 1000], ['GOOGL', 0.03, 1500]],
        [['MSFT', 0.06, 2000], ['TSLA', 0.07, 1800]],
        [['AMZN', 0.04, 1200], ['NFLX', 0.08, 1600]]
    ]
    print(adaptive_heap_update(data_streams))