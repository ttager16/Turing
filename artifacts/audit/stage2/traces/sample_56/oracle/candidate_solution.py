from typing import Dict, List
import math

def custom_sort_markets(data: Dict[str, List[float]]) -> Dict[str, List[float]]:

    if not isinstance(data, dict) or not data:
        return {}

    valid_letters = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def is_valid_key(name):
        if not isinstance(name, str) or not name:
            return False
        return all(ch in valid_letters for ch in name)

    def is_valid_float(value):
        return isinstance(value, float) and math.isfinite(value)

    market_keys = []
    for key, values in data.items():
        if not is_valid_key(key):
            return {}
        if not isinstance(values, list):
            return {}
        for number in values:
            if not is_valid_float(number):
                return {}
        market_keys.append(key)

    def merge_sections(source, target, left_start, left_len, right_start, right_len):
        left_end = left_start + left_len
        right_end = right_start + right_len
        dest_index = left_start
        i, j = left_start, right_start
        while i < left_end and j < right_end:
            if source[i] <= source[j]:
                target[dest_index] = source[i]
                i += 1
            else:
                target[dest_index] = source[j]
                j += 1
            dest_index += 1
        while i < left_end:
            target[dest_index] = source[i]
            i += 1
            dest_index += 1
        while j < right_end:
            target[dest_index] = source[j]
            j += 1
            dest_index += 1

    def iterative_merge_sort(sequence):
        n = len(sequence)
        if n <= 1:
            return sequence[:]
        source = sequence[:]
        target = [None] * n
        width = 1
        while width < n:
            index = 0
            while index < n:
                left = index
                mid = index + width
                right = index + 2 * width
                if mid > n:
                    while index < n:
                        target[index] = source[index]
                        index += 1
                    break
                left_len = width
                right_len = right - mid if right <= n else n - mid
                merge_sections(source, target, left, left_len, mid, right_len)
                index = right
            source, target = target, source
            width <<= 1
        return source

    def merge_sorted_lists(list_a, list_b):
        len_a, len_b = len(list_a), len(list_b)
        merged = [None] * (len_a + len_b)
        i = j = k = 0
        while i < len_a and j < len_b:
            if list_a[i] <= list_b[j]:
                merged[k] = list_a[i]
                i += 1
            else:
                merged[k] = list_b[j]
                j += 1
            k += 1
        while i < len_a:
            merged[k] = list_a[i]
            i += 1
            k += 1
        while j < len_b:
            merged[k] = list_b[j]
            j += 1
            k += 1
        return merged

    sorted_keys = iterative_merge_sort(market_keys)
    sorted_markets = {k: iterative_merge_sort(data[k]) for k in sorted_keys}

    market_lists = [sorted_markets[k] for k in sorted_keys]
    while len(market_lists) > 1:
        merged_round = []
        index = 0
        while index + 1 < len(market_lists):
            merged = merge_sorted_lists(market_lists[index], market_lists[index + 1])
            merged_round.append(merged)
            index += 2
        if index < len(market_lists):
            merged_round.append(market_lists[index])
        market_lists = merged_round

    combined = market_lists[0]
    result = {k: sorted_markets[k] for k in sorted_keys}
    result["combined"] = combined
    return result


if __name__ == "__main__":
    data = {
        "marketB": [1.0, 6.0, 3.0, 6.0],
        "marketA": [5.2, 2.0, 5.2, 3.0],
        "marketC": []
    }
    print(custom_sort_markets(data))