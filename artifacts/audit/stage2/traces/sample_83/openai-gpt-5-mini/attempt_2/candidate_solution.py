def financial_segment_tree(
        prices: List[int],
        weights: List[float],
        multipliers: List[float],
        operations: List[List]
) -> List[float]:
    n = len(prices)
    size = 1
    while size < n:
        size <<= 1
    # segment arrays of length 2*size
    sum_p = [0.0] * (2 * size)
    sum_w = [0.0] * (2 * size)
    sum_pw = [0.0] * (2 * size)
    sum_pp = [0.0] * (2 * size)
    sum_pwm = [0.0] * (2 * size)
    cnt = [0] * (2 * size)
    lazy = [0.0] * (2 * size)  # lazy add to prices

    # build leaves
    for i in range(n):
        idx = size + i
        p = float(prices[i])
        w = float(weights[i])
        m = float(multipliers[i])
        sum_p[idx] = p
        sum_w[idx] = w
        sum_pw[idx] = p * w
        sum_pp[idx] = p * p
        sum_pwm[idx] = p * w * m
        cnt[idx] = 1
    for i in range(size - 1, 0, -1):
        l = 2 * i
        r = l + 1
        sum_p[i] = sum_p[l] + sum_p[r]
        sum_w[i] = sum_w[l] + sum_w[r]
        sum_pw[i] = sum_pw[l] + sum_pw[r]
        sum_pp[i] = sum_pp[l] + sum_pp[r]
        sum_pwm[i] = sum_pwm[l] + sum_pwm[r]
        cnt[i] = cnt[l] + cnt[r]

    def apply_add(node: int, add: float):
        if add == 0.0:
            return
        # when prices increase by add: sum_p += add * cnt
        # sum_pp += 2*add*sum_p_old + add^2 * cnt  BUT careful: need old sum_p
        old_sum_p = sum_p[node]
        sum_p[node] = old_sum_p + add * cnt[node]
        sum_pp[node] = sum_pp[node] + 2.0 * add * old_sum_p + (add * add) * cnt[node]
        # sum_pw increases by add * sum_w (since price increased)
        sum_pw[node] = sum_pw[node] + add * sum_w[node]
        # sum_pwm increases by add * sum_w * multipliers per element => add * sum(w*m)
        # But we don't store sum(w*m). We can compute sum_pwm_old = sum(p*w*m). Increase = add * sum(w*m)
        # Need sum_wm: derive from sum_pwm and sum_pw: not possible. So store sum_wm separately.
        # To handle this, we must precompute sum_wm array. We'll add it.
        sum_pwm[node] = sum_pwm[node] + add * sum_wm[node]
        lazy[node] += add

    # We realized we need sum_wm (sum of weight * multiplier) stored.
    sum_wm = [0.0] * (2 * size)
    for i in range(n):
        idx = size + i
        sum_wm[idx] = weights[i] * multipliers[i]
    for i in range(size - 1, 0, -1):
        sum_wm[i] = sum_wm[2 * i] + sum_wm[2 * i + 1]

    # rebuild apply_add to capture closure sum_wm
    def apply_add(node: int, add: float):
        if add == 0.0:
            return
        old_sum_p = sum_p[node]
        sum_p[node] = old_sum_p + add * cnt[node]
        sum_pp[node] = sum_pp[node] + 2.0 * add * old_sum_p + (add * add) * cnt[node]
        sum_pw[node] = sum_pw[node] + add * sum_w[node]
        sum_pwm[node] = sum_pwm[node] + add * sum_wm[node]
        lazy[node] += add

    def push(node: int):
        if lazy[node] != 0.0 and node < size:
            add = lazy[node]
            left = 2 * node
            right = left + 1
            apply_add(left, add)
            apply_add(right, add)
            lazy[node] = 0.0

    def pull(node: int):
        left = 2 * node
        right = left + 1
        sum_p[node] = sum_p[left] + sum_p[right]
        sum_w[node] = sum_w[left] + sum_w[right]
        sum_pw[node] = sum_pw[left] + sum_pw[right]
        sum_pp[node] = sum_pp[left] + sum_pp[right]
        sum_pwm[node] = sum_pwm[left] + sum_pwm[right]
        sum_wm[node] = sum_wm[left] + sum_wm[right]
        cnt[node] = cnt[left] + cnt[right]

    # update point assignment: set price at pos to new_price
    def point_assign(pos: int, new_price: float):
        if pos < 0 or pos >= n:
            return
        node = 1
        l = 0
        r = size - 1
        path = []
        while node < size:
            path.append(node)
            push(node)
            mid = (l + r) // 2
            if pos <= mid:
                node = node * 2
                r = mid
            else:
                node = node * 2 + 1
                l = mid + 1
        # node is leaf
        idx = node
        sum_p[idx] = new_price
        sum_pp[idx] = new_price * new_price
        i = idx - size
        sum_w[idx] = weights[i] if i < n else 0.0
        sum_pw[idx] = new_price * (weights[i] if i < n else 0.0)
        sum_pwm[idx] = new_price * (weights[i] * multipliers[i] if i < n else 0.0)
        # sum_wm leaf unchanged
        # cnt unchanged
        # go up
        for nd in reversed(path):
            pull(nd)

    # range add
    def range_add(a: int, b: int, val: float, node=1, l=0, r=size-1):
        if a > r or b < l or a > b:
            return
        if a <= l and r <= b:
            apply_add(node, val)
            return
        push(node)
        mid = (l + r) // 2
        left = 2 * node
        right = left + 1
        if a <= mid:
            range_add(a, b, val, left, l, mid)
        if b > mid:
            range_add(a, b, val, right, mid+1, r)
        pull(node)

    # range query aggregator
    def range_query(a: int, b: int, node=1, l=0, r=size-1):
        # returns tuple sums for intersection
        if a > r or b < l or a > b:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0)  # sum_p, sum_w, sum_pw, sum_pp, sum_pwm, cnt
        if a <= l and r <= b:
            return (sum_p[node], sum_w[node], sum_pw[node], sum_pp[node], sum_pwm[node], cnt[node])
        push(node)
        mid = (l + r) // 2
        left = range_query(a, b, 2*node, l, mid)
        right = range_query(a, b, 2*node+1, mid+1, r)
        return (left[0]+right[0], left[1]+right[1], left[2]+right[2],
                left[3]+right[3], left[4]+right[4], left[5]+right[5])

    results: List[float] = []
    for op in operations:
        if not op or len(op) < 4:
            results.append(0.0)
            continue
        name = op[0]
        a = op[1]
        b = op[2]
        val = op[3]
        # handle out-of-bounds by intersecting
        if a > b:
            results.append(0.0)
            continue
        aa = max(0, a)
        bb = min(n-1, b)
        if aa > bb:
            # if update, do nothing
            if name in ("range_update", "point_update"):
                results.append(0.0)
                continue
            else:
                results.append(0.0)
                continue
        if name == "sum":
            sp, sw, spw, spp, spwm, scnt = range_query(aa, bb)
            results.append(round(float(sp), 2))
        elif name == "average":
            sp, sw, spw, spp, spwm, scnt = range_query(aa, bb)
            if scnt == 0:
                results.append(0.0)
            else:
                results.append(round(float(sp) / scnt, 2))
        elif name == "weighted_avg":
            sp, sw, spw, spp, spwm, scnt = range_query(aa, bb)
            if sw == 0.0:
                results.append(0.0)
            else:
                results.append(round(float(spw) / sw, 2))
        elif name == "variance":
            sp, sw, spw, spp, spwm, scnt = range_query(aa, bb)
            if scnt == 0:
                results.append(0.0)
            else:
                var = (spp / scnt) - (sp / scnt) ** 2
                results.append(round(float(var), 2))
        elif name == "custom_weighted":
            sp, sw, spw, spp, spwm, scnt = range_query(aa, bb)
            results.append(round(float(spwm), 2))
        elif name == "range_update":
            # val is amount to add
            addv = float(val)
            range_add(aa, bb, addv)
            results.append(0.0)
        elif name == "point_update":
            # val is new price, a==b expected (but may not); apply at intersection indices individually
            newp = float(val)
            # if a..b range, update each index to newp? Spec says start==end for point_update, but handle range by updating points in [aa,bb]
            for pos in range(aa, bb+1):
                # set price at pos
                # need to account for any pending lazy along path: point_assign handles push along path
                point_assign(pos, newp)
            results.append(0.0)
        else:
            results.append(0.0)
    return results