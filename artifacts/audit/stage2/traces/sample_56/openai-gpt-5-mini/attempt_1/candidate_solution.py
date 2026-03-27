def custom_sort_markets(data: Dict[str, List[float]]) -> Dict[str, List[float]]:
    # Validation
    if not isinstance(data, dict) or len(data) == 0:
        return {}
    for k, v in data.items():
        if not isinstance(k, str) or k == "" or not all(('a' <= ch <= 'z') or ('A' <= ch <= 'Z') for ch in k):
            return {}
        if not isinstance(v, list):
            return {}
        for x in v:
            if not isinstance(x, float):
                return {}
            if math.isinf(x) or math.isnan(x):
                return {}
    # Helper: stable iterative bottom-up merge sort for list of floats
    def merge_two(left: List[float], right: List[float]) -> List[float]:
        i = j = 0
        n, m = len(left), len(right)
        out = [0.0] * (n + m)
        p = 0
        while i < n and j < m:
            if left[i] <= right[j]:
                out[p] = left[i]
                i += 1
            else:
                out[p] = right[j]
                j += 1
            p += 1
        while i < n:
            out[p] = left[i]; i += 1; p += 1
        while j < m:
            out[p] = right[j]; j += 1; p += 1
        return out

    def bottom_up_merge_sort(arr: List[float]) -> List[float]:
        n = len(arr)
        if n <= 1:
            return arr[:]  # copy to avoid mutating input
        # copy original with stability preserved by positions (values only; stability for equal floats preserved by left<=right tie)
        src = arr[:]  # shallow copy of floats
        dest = [0.0] * n
        width = 1
        while width < n:
            i = 0
            dest_index = 0
            while i < n:
                left = i
                mid = i + width
                right = min(i + 2 * width, n)
                l = left
                r = mid
                while l < mid and r < right:
                    if src[l] <= src[r]:
                        dest[dest_index] = src[l]; l += 1
                    else:
                        dest[dest_index] = src[r]; r += 1
                    dest_index += 1
                while l < mid:
                    dest[dest_index] = src[l]; l += 1; dest_index += 1
                while r < right:
                    dest[dest_index] = src[r]; r += 1; dest_index += 1
                i += 2 * width
            # copy any remaining tail if dest_index < n (shouldn't happen but ensure)
            while dest_index < n:
                dest[dest_index] = src[dest_index]; dest_index += 1
            # swap src and dest buffers
            src, dest = dest, src
            width *= 2
        return src

    # Process markets in lexicographic order
    keys = sorted(data.keys())
    sorted_lists = {}
    for k in keys:
        sorted_lists[k] = bottom_up_merge_sort(data[k])

    # Multi-round deterministic pairwise merge based on lexicographic order
    # Start with list of lists in keys order
    lists = [sorted_lists[k] for k in keys]
    if len(lists) == 0:
        return {}
    # If only empty lists possible, proceed
    while len(lists) > 1:
        next_round = []
        i = 0
        while i < len(lists):
            if i + 1 < len(lists):
                merged = merge_two(lists[i], lists[i+1])
                next_round.append(merged)
                i += 2
            else:
                # carry forward odd one
                next_round.append(lists[i])
                i += 1
        lists = next_round
    combined = lists[0]
    # Build result dict with markets in lexicographic order and combined last
    result: Dict[str, List[float]] = {}
    for k in keys:
        # ensure copies so input not mutated
        result[k] = sorted_lists[k][:]
    result["combined"] = combined[:]
    return result