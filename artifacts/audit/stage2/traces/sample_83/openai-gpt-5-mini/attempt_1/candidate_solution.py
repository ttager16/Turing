def financial_segment_tree(
        prices: List[int],
        weights: List[float],
        multipliers: List[float],
        operations: List[List]
) -> List[float]:
    n = len(prices)
    if n == 0:
        return []
    size = 1
    while size < n:
        size <<= 1
    # tree arrays
    tree_sum = [0.0] * (2 * size)
    tree_sum_sq = [0.0] * (2 * size)
    tree_wsum = [0.0] * (2 * size)      # sum price*weight
    tree_w = [0.0] * (2 * size)         # sum weights
    tree_cw = [0.0] * (2 * size)        # sum price*weight*multiplier
    tree_cnt = [0] * (2 * size)
    lazy_add = [0.0] * (2 * size)
    # build leaves
    for i in range(size):
        idx = i + size
        if i < n:
            p = float(prices[i])
            w = float(weights[i])
            m = float(multipliers[i])
            tree_sum[idx] = p
            tree_sum_sq[idx] = p * p
            tree_wsum[idx] = p * w
            tree_w[idx] = w
            tree_cw[idx] = p * w * m
            tree_cnt[idx] = 1
        else:
            tree_sum[idx] = 0.0
            tree_sum_sq[idx] = 0.0
            tree_wsum[idx] = 0.0
            tree_w[idx] = 0.0
            tree_cw[idx] = 0.0
            tree_cnt[idx] = 0
    for i in range(size - 1, 0, -1):
        left = 2 * i
        right = left + 1
        tree_sum[i] = tree_sum[left] + tree_sum[right]
        tree_sum_sq[i] = tree_sum_sq[left] + tree_sum_sq[right]
        tree_wsum[i] = tree_wsum[left] + tree_wsum[right]
        tree_w[i] = tree_w[left] + tree_w[right]
        tree_cw[i] = tree_cw[left] + tree_cw[right]
        tree_cnt[i] = tree_cnt[left] + tree_cnt[right]

    def apply_add(node: int, seg_len: int, addv: float):
        # when adding addv to each price in segment:
        # sum increases by addv * seg_len
        # sum_sq increases by 2*addv*sum + seg_len*addv^2 (but sum is pre-change; use current sum)
        # wsum increases by addv * sum_weights
        # cw increases by addv * sum_weights * multipliers averaged? Actually multipliers are per-element: sum(price*weight*multiplier) increases by addv * sum(weight*multiplier)
        # But we don't have sum(weight*multiplier) stored; need to precompute per leaf and tree for that.
        pass

    # We realize we need sum of weight*multiplier per segment. Add that.
    tree_wm = [0.0] * (2 * size)
    # initialize tree_wm leaves and internal
    for i in range(size):
        idx = i + size
        if i < n:
            tree_wm[idx] = weights[i] * multipliers[i]
        else:
            tree_wm[idx] = 0.0
    for i in range(size - 1, 0, -1):
        tree_wm[i] = tree_wm[2*i] + tree_wm[2*i+1]

    def apply_add(node: int, seg_len: int, addv: float):
        # update sums
        # sum_sq' = sum_sq + 2*addv*sum + seg_len*addv^2
        s = tree_sum[node]
        tree_sum_sq[node] += 2.0 * addv * s + seg_len * (addv * addv)
        tree_sum[node] += addv * seg_len
        # wsum increases by addv * sum_weights
        tree_wsum[node] += addv * tree_w[node]
        # cw increases by addv * sum(weight*multiplier)
        tree_cw[node] += addv * tree_wm[node]
        # sum weights, cnt unchanged
        lazy_add[node] += addv

    def push(node: int, l_len: int, r_len: int):
        v = lazy_add[node]
        if v != 0.0:
            left = node * 2
            right = left + 1
            apply_add(left, l_len, v)
            apply_add(right, r_len, v)
            lazy_add[node] = 0.0

    def update_range(node: int, nl: int, nr: int, ql: int, qr: int, val: float):
        if ql > nr or qr < nl:
            return
        if ql <= nl and nr <= qr:
            apply_add(node, nr - nl + 1, val)
            return
        mid = (nl + nr) // 2
        push(node, mid - nl + 1, nr - mid)
        update_range(node*2, nl, mid, ql, qr, val)
        update_range(node*2+1, mid+1, nr, ql, qr, val)
        left = node*2
        right = left+1
        tree_sum[node] = tree_sum[left] + tree_sum[right]
        tree_sum_sq[node] = tree_sum_sq[left] + tree_sum_sq[right]
        tree_wsum[node] = tree_wsum[left] + tree_wsum[right]
        tree_w[node] = tree_w[left] + tree_w[right]
        tree_cw[node] = tree_cw[left] + tree_cw[right]
        tree_cnt[node] = tree_cnt[left] + tree_cnt[right]
        tree_wm[node] = tree_wm[left] + tree_wm[right]

    def point_update(node: int, nl: int, nr: int, idx: int, new_price: float):
        if nl == nr:
            # set leaf
            old_cnt = tree_cnt[node]
            if old_cnt == 0:
                # outside original n, ignore
                return
            w = weights[idx]
            m = multipliers[idx]
            tree_sum[node] = new_price
            tree_sum_sq[node] = new_price * new_price
            tree_wsum[node] = new_price * w
            tree_cw[node] = new_price * w * m
            # weights and wm and cnt unchanged
            return
        mid = (nl + nr) // 2
        push(node, mid - nl + 1, nr - mid)
        if idx <= mid:
            point_update(node*2, nl, mid, idx, new_price)
        else:
            point_update(node*2+1, mid+1, nr, idx, new_price)
        left = node*2
        right = left+1
        tree_sum[node] = tree_sum[left] + tree_sum[right]
        tree_sum_sq[node] = tree_sum_sq[left] + tree_sum_sq[right]
        tree_wsum[node] = tree_wsum[left] + tree_wsum[right]
        tree_w[node] = tree_w[left] + tree_w[right]
        tree_cw[node] = tree_cw[left] + tree_cw[right]
        tree_cnt[node] = tree_cnt[left] + tree_cnt[right]
        tree_wm[node] = tree_wm[left] + tree_wm[right]

    def query(node: int, nl: int, nr: int, ql: int, qr: int):
        if ql > nr or qr < nl:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0)  # sum, sum_sq, wsum, w, cw, cnt
        if ql <= nl and nr <= qr:
            return (tree_sum[node], tree_sum_sq[node], tree_wsum[node], tree_w[node], tree_cw[node], tree_cnt[node])
        mid = (nl + nr) // 2
        push(node, mid - nl + 1, nr - mid)
        L = query(node*2, nl, mid, ql, qr)
        R = query(node*2+1, mid+1, nr, ql, qr)
        return (L[0]+R[0], L[1]+R[1], L[2]+R[2], L[3]+R[3], L[4]+R[4], L[5]+R[5])

    results: List[float] = []
    for op in operations:
        if not op or len(op) < 4:
            results.append(0.0)
            continue
        name, a, b, val = op[0], op[1], op[2], op[3]
        # normalize range intersection with [0,n-1]
        if a is None or b is None:
            results.append(0.0)
            continue
        l = max(0, min(n-1, a))
        r = max(0, min(n-1, b))
        if a > b:
            # empty
            results.append(0.0)
            continue
        if l > r:
            results.append(0.0)
            continue
        if name == "sum":
            s, _, _, _, _, _ = query(1, 0, size-1, l, r)
            results.append(round(float(s), 2))
        elif name == "average":
            s, _, _, _, _, cnt = query(1, 0, size-1, l, r)
            if cnt == 0:
                results.append(0.0)
            else:
                avg = s / cnt
                results.append(round(float(avg), 2))
        elif name == "weighted_avg":
            _, _, wsum, wsum_w, _, _ = query(1, 0, size-1, l, r)
            # here wsum is price*weight sum, wsum_w is sum weights
            if wsum_w == 0.0:
                results.append(0.0)
            else:
                results.append(round(float(wsum / wsum_w), 2))
        elif name == "variance":
            s, ssq, _, _, _, cnt = query(1, 0, size-1, l, r)
            if cnt == 0:
                results.append(0.0)
            else:
                var = (ssq / cnt) - (s / cnt) * (s / cnt)
                results.append(round(float(var), 2))
        elif name == "custom_weighted":
            _, _, _, _, cw, _ = query(1, 0, size-1, l, r)
            results.append(round(float(cw), 2))
        elif name == "range_update":
            if val is None:
                results.append(0.0)
            else:
                v = float(val)
                update_range(1, 0, size-1, l, r, v)
                results.append(0.0)
        elif name == "point_update":
            if val is None:
                results.append(0.0)
            else:
                if a < 0 or a >= n:
                    results.append(0.0)
                else:
                    point_update(1, 0, size-1, a, float(val))
                    results.append(0.0)
        else:
            results.append(0.0)
    # ensure floats with two decimals
    out = [float(f"{x:.2f}") for x in results]
    return out