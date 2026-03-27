from typing import List


# Segment tree constants
# 4x size ensures sufficient space for complete binary tree representation
SEGMENT_TREE_SIZE_MULTIPLIER = 4

# Binary tree navigation constants
# Binary tree array indexing: left child at 2i, right child at 2i+1
LEFT_CHILD_MULTIPLIER = 2  # Left child is at index parent * 2
RIGHT_CHILD_OFFSET = 1     # Right child is at index parent * 2 + 1


class FinancialSegmentTree:
    """Segment tree for financial metrics with lazy propagation."""

    def __init__(self, prices: List[int], weights: List[float], multipliers: List[float]):
        self.n = len(prices)

        # Precompute weighted multiplier prefix sums
        wm = [weights[i] * multipliers[i] for i in range(self.n)]
        self.wm_prefix = [0.0] * (self.n + 1)
        for i in range(self.n):
            self.wm_prefix[i + 1] = self.wm_prefix[i] + wm[i]

        # Initialize segment tree arrays
        size = SEGMENT_TREE_SIZE_MULTIPLIER * self.n
        self.sumP = [0.0] * size
        self.sumW = [0.0] * size
        self.sumPW = [0.0] * size
        self.sumPP = [0.0] * size
        self.sumPWM = [0.0] * size
        self.cnt = [0] * size
        self.lazy_add = [0.0] * size

        # Build the segment tree
        self._build(1, 0, self.n - 1, prices, weights, multipliers)

    def _sum_wm(self, l: int, r: int) -> float:
        """Calculate sum of weights * multipliers over range [l, r]."""
        return self.wm_prefix[r + 1] - self.wm_prefix[l]

    def _build(self, idx: int, l: int, r: int, prices: List[int], weights: List[float], multipliers: List[float]):
        """Build segment tree from leaf to root."""
        if l == r:
            p = float(prices[l])
            w = float(weights[l])
            m = float(multipliers[l])
            self.sumP[idx] = p
            self.sumW[idx] = w
            self.sumPW[idx] = p * w
            self.sumPP[idx] = p * p
            self.sumPWM[idx] = p * w * m
            self.cnt[idx] = 1
            return
        mid = (l + r) // 2
        left = idx * LEFT_CHILD_MULTIPLIER
        right = idx * LEFT_CHILD_MULTIPLIER + RIGHT_CHILD_OFFSET
        self._build(left, l, mid, prices, weights, multipliers)
        self._build(right, mid + 1, r, prices, weights, multipliers)
        self._pull(idx, l, r)

    def _pull(self, idx: int, l: int, r: int):
        """Update parent node from children nodes."""
        if l == r:
            return
        left = idx * LEFT_CHILD_MULTIPLIER
        right = idx * LEFT_CHILD_MULTIPLIER + RIGHT_CHILD_OFFSET
        self.sumP[idx] = self.sumP[left] + self.sumP[right]
        self.sumW[idx] = self.sumW[left] + self.sumW[right]
        self.sumPW[idx] = self.sumPW[left] + self.sumPW[right]
        self.sumPP[idx] = self.sumPP[left] + self.sumPP[right]
        self.sumPWM[idx] = self.sumPWM[left] + self.sumPWM[right]
        self.cnt[idx] = self.cnt[left] + self.cnt[right]

    def _apply_add(self, idx: int, l: int, r: int, delta: float):
        """Apply lazy update delta to segment at idx."""
        if delta == 0.0:
            return
        seg_len = float(r - l + 1)
        pre_sumP = self.sumP[idx]

        self.sumP[idx] = pre_sumP + delta * seg_len
        self.sumPP[idx] = self.sumPP[idx] + 2.0 * delta * pre_sumP + (delta * delta) * seg_len
        self.sumPW[idx] = self.sumPW[idx] + delta * self.sumW[idx]
        self.sumPWM[idx] = self.sumPWM[idx] + delta * self._sum_wm(l, r)
        self.lazy_add[idx] += delta

    def _push(self, idx: int, l: int, r: int):
        """Propagate lazy updates to children."""
        if self.lazy_add[idx] != 0.0 and l != r:
            mid = (l + r) // 2
            left = idx * LEFT_CHILD_MULTIPLIER
            right = idx * LEFT_CHILD_MULTIPLIER + RIGHT_CHILD_OFFSET
            d = self.lazy_add[idx]
            self._apply_add(left, l, mid, d)
            self._apply_add(right, mid + 1, r, d)
            self.lazy_add[idx] = 0.0

    def range_add(self, idx: int, l: int, r: int, ql: int, qr: int, delta: float):
        """Add delta to all prices in range [ql, qr]."""
        if ql > r or qr < l or l > r:
            return
        if ql <= l and r <= qr:
            self._apply_add(idx, l, r, delta)
            return
        self._push(idx, l, r)
        mid = (l + r) // 2
        left = idx * LEFT_CHILD_MULTIPLIER
        right = idx * LEFT_CHILD_MULTIPLIER + RIGHT_CHILD_OFFSET
        self.range_add(left, l, mid, ql, qr, delta)
        self.range_add(right, mid + 1, r, ql, qr, delta)
        self._pull(idx, l, r)

    def point_set(self, idx: int, l: int, r: int, pos: int, new_price: float):
        """Set price at position pos to new_price."""
        if l == r:
            delta = new_price - self.sumP[idx]
            self._apply_add(idx, l, r, delta)
            return
        self._push(idx, l, r)
        mid = (l + r) // 2
        left = idx * LEFT_CHILD_MULTIPLIER
        right = idx * LEFT_CHILD_MULTIPLIER + RIGHT_CHILD_OFFSET
        if pos <= mid:
            self.point_set(left, l, mid, pos, new_price)
        else:
            self.point_set(right, mid + 1, r, pos, new_price)
        self._pull(idx, l, r)

    def range_query(self, idx: int, l: int, r: int, ql: int, qr: int):
        """Query range [ql, qr] and return aggregated values as list."""
        if ql > r or qr < l or l > r:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0]
        if ql <= l and r <= qr:
            return [self.sumP[idx], self.sumW[idx], self.sumPW[idx], self.sumPP[idx], self.sumPWM[idx], self.cnt[idx]]
        self._push(idx, l, r)
        mid = (l + r) // 2
        left_child = idx * LEFT_CHILD_MULTIPLIER
        right_child = idx * LEFT_CHILD_MULTIPLIER + RIGHT_CHILD_OFFSET
        left = self.range_query(left_child, l, mid, ql, qr)
        right = self.range_query(right_child, mid + 1, r, ql, qr)
        return [
            left[0] + right[0],
            left[1] + right[1],
            left[2] + right[2],
            left[3] + right[3],
            left[4] + right[4],
            left[5] + right[5],
        ]


def round_to_2(x: float) -> float:
    """Round value to 2 decimal places."""
    return round(float(x), 2)


def financial_segment_tree(
        prices: List[int],
        weights: List[float],
        multipliers: List[float],
        operations: List[List]
) -> List[float]:
    """
    Compute financial metrics over stock price ranges using a segment tree with lazy propagation.
    
    Args:
        prices: List of integers representing stock prices in chronological order.
        weights: List of floats representing weight factors for each price point.
        multipliers: List of floats for custom weighted aggregation operations.
        operations: List of operations, each as [name, start_idx, end_idx, value_or_None].
            Valid names: 'sum', 'average', 'weighted_avg', 'variance', 'custom_weighted',
            'range_update', 'point_update'. For queries, value_or_None is None.
    
    Returns:
        List[float]: Results for each operation (queries return metric values rounded to 2 decimals,
        updates return 0.0).
    """
    n = len(prices)
    seg_tree = FinancialSegmentTree(prices, weights, multipliers)

    out: List[float] = []

    for op in operations:
        name = op[0]
        l = op[1]
        r = op[2]
        val = op[3]

        # Handle reversed range (start_idx > end_idx)
        if l > r:
            out.append(round_to_2(0.0))
            continue

        # Clamp to valid range [0, n-1]
        ql = max(0, min(n - 1, l))
        qr = max(0, min(n - 1, r))

        # Check if entire range is out of bounds
        if l >= n or r < 0:
            out.append(round_to_2(0.0))
            continue

        if name == 'sum':
            result = seg_tree.range_query(1, 0, n - 1, ql, qr)
            out.append(round_to_2(result[0]))
        elif name == 'average':
            result = seg_tree.range_query(1, 0, n - 1, ql, qr)
            cnt_val = result[5]
            avg = result[0] / cnt_val if cnt_val > 0 else 0.0
            out.append(round_to_2(avg))
        elif name == 'weighted_avg':
            result = seg_tree.range_query(1, 0, n - 1, ql, qr)
            sW = result[1]
            sPW = result[2]
            wavg = (sPW / sW) if sW != 0.0 else 0.0
            out.append(round_to_2(wavg))
        elif name == 'variance':
            result = seg_tree.range_query(1, 0, n - 1, ql, qr)
            cnt_val = result[5]
            if cnt_val == 0:
                out.append(round_to_2(0.0))
            else:
                sP = result[0]
                sPP = result[3]
                mean = sP / cnt_val
                var = (sPP / cnt_val) - (mean * mean)
                out.append(round_to_2(var))
        elif name == 'custom_weighted':
            result = seg_tree.range_query(1, 0, n - 1, ql, qr)
            out.append(round_to_2(result[4]))
        elif name == 'range_update':
            delta = float(val if val is not None else 0.0)
            seg_tree.range_add(1, 0, n - 1, ql, qr, delta)
            out.append(round_to_2(0.0))
        elif name == 'point_update':
            pos = l
            if pos < 0 or pos >= n:
                out.append(round_to_2(0.0))
            else:
                new_price = float(val if val is not None else 0.0)
                seg_tree.point_set(1, 0, n - 1, pos, new_price)
                out.append(round_to_2(0.0))

    return out


if __name__ == "__main__":
    prices = [100, 105, 98, 110, 95]
    weights = [1.0, 1.2, 0.8, 1.5, 0.9]
    multipliers = [1.1, 0.9, 1.3, 0.7, 1.2]
    operations = [["sum", 0, 2, None], ["average", 1, 3, None], ["weighted_avg", 0, 4, None], ["variance", 2, 4, None], ["custom_weighted", 0, 3, None], ["range_update", 1, 3, 5]]
    print(financial_segment_tree(prices, weights, multipliers, operations))