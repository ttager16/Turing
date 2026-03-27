from decimal import Decimal, getcontext, ROUND_HALF_UP
from fractions import Fraction

INT64_MIN = -2**63
INT64_MAX = 2**63 - 1
MAX_BATCH_SIZE = 100  # batch_update operations support k ≤ 100 sub-operations
SEGMENT_TREE_SIZE_MULTIPLIER = 4  # Segment trees require 4×n array size for complete binary tree representation


class _Helpers:
    """Error helpers, int64 checks, and HALF_UP rounding."""
    def err(self, msg: str) -> dict:
        return {"error": msg}

    def in_int64(self, x: int) -> bool:
        return INT64_MIN <= x <= INT64_MAX

    def half_up_round_fraction(self, fr: Fraction) -> int:
        # Default precision (28 digits) is sufficient for int64 range calculations
        d = Decimal(fr.numerator) / Decimal(fr.denominator)
        return int(d.to_integral_value(rounding=ROUND_HALF_UP))

    def half_up_round_decimal(self, x: Decimal) -> int:
        return int(x.to_integral_value(rounding=ROUND_HALF_UP))


def process_stock_movements(n: int, operations: list) -> dict:
    """Executes list-encoded range ops with reversible updates, returning results, audit, and summary.

    - Ops: update, query (sum/min/max/mean/var/unique/rms/trend), reverse, batch_update, conditional.
    - Indices are 1-based; non-integer results use HALF_UP; trend scales by 1000.
    - Returns {'results', 'audit', 'summary'} or {'error': msg}.
    """
    _h = _Helpers()
    err = _h.err
    in_int64 = _h.in_int64
    half_up_round_fraction = _h.half_up_round_fraction
    half_up_round_decimal = _h.half_up_round_decimal

    def check_bounds_after_update(op_i):
        mn, mx = seg_query_min(1, 1, n), seg_query_max(1, 1, n)
        if not (in_int64(mn) and in_int64(mx)):
            return err(f"cumulative value out of range after op {op_i}")
        return None

    if not isinstance(n, int) or n <= 0:
        return err("n must be a positive integer")

    if not isinstance(operations, list):
        return err("operations must be a list")

    Sx_prefix = [0] * (n + 1)
    Sxx_prefix = [0] * (n + 1)
    for i in range(1, n + 1):
        Sx_prefix[i] = Sx_prefix[i - 1] + i
        Sxx_prefix[i] = Sxx_prefix[i - 1] + i * i

    def sum_x(l, r):
        return Sx_prefix[r] - Sx_prefix[l - 1]

    def sum_xx(l, r):
        return Sxx_prefix[r] - Sxx_prefix[l - 1]

    size = SEGMENT_TREE_SIZE_MULTIPLIER * n
    # Segment tree node fields:
    #  seg_sum: sum of y, seg_min: min(y), seg_max: max(y), seg_sumsq: sum of y^2, seg_sumxy: sum of (x*y)
    #  seg_lazy: pending +delta for lazy propagation; seg_L/seg_R: covered index range
    seg_sum = [0] * size
    seg_min = [0] * size
    seg_max = [0] * size
    seg_sumsq = [0] * size
    seg_sumxy = [0] * size
    seg_lazy = [0] * size
    seg_L = [0] * size
    seg_R = [0] * size

    def build(idx, l, r):
        seg_L[idx], seg_R[idx] = l, r
        if l == r:
            seg_sum[idx] = 0
            seg_min[idx] = 0
            seg_max[idx] = 0
            seg_sumsq[idx] = 0
            seg_sumxy[idx] = 0
            seg_lazy[idx] = 0
            return
        m = (l + r) // 2
        build(idx * 2, l, m)
        build(idx * 2 + 1, m + 1, r)
        # initial merge: zeros (array starts all zeros)
        seg_sum[idx] = 0
        seg_min[idx] = 0
        seg_max[idx] = 0
        seg_sumsq[idx] = 0
        seg_sumxy[idx] = 0
        seg_lazy[idx] = 0

    def apply_add(idx, delta):
        l, r = seg_L[idx], seg_R[idx]
        length = r - l + 1
        old_sum = seg_sum[idx]
        seg_sum[idx] = old_sum + delta * length
        seg_min[idx] += delta
        seg_max[idx] += delta
        # (y + delta)^2 = y^2 + 2*delta*y + delta^2, and sum(x*y) increases by delta * sum(x)
        seg_sumsq[idx] = seg_sumsq[idx] + 2 * delta * old_sum + (delta * delta) * length
        seg_sumxy[idx] = seg_sumxy[idx] + delta * sum_x(l, r)
        seg_lazy[idx] += delta

    def push(idx):
        if seg_lazy[idx] != 0:
            d = seg_lazy[idx]
            apply_add(idx * 2, d)
            apply_add(idx * 2 + 1, d)
            seg_lazy[idx] = 0

    def pull(idx):
        left = idx * 2
        right = idx * 2 + 1
        seg_sum[idx] = seg_sum[left] + seg_sum[right]
        seg_min[idx] = min(seg_min[left], seg_min[right])
        seg_max[idx] = max(seg_max[left], seg_max[right])
        seg_sumsq[idx] = seg_sumsq[left] + seg_sumsq[right]
        seg_sumxy[idx] = seg_sumxy[left] + seg_sumxy[right]

    def range_add(idx, l, r, val):
        if r < seg_L[idx] or seg_R[idx] < l:
            return
        if l <= seg_L[idx] and seg_R[idx] <= r:
            apply_add(idx, val)
            return
        push(idx)
        range_add(idx * 2, l, r, val)
        range_add(idx * 2 + 1, l, r, val)
        pull(idx)

    def range_query(idx, l, r):
        if r < seg_L[idx] or seg_R[idx] < l:
            return (0, None, None, 0, 0)
        if l <= seg_L[idx] and seg_R[idx] <= r:
            return (seg_sum[idx], seg_min[idx], seg_max[idx], seg_sumsq[idx], seg_sumxy[idx])
        push(idx)
        a = range_query(idx * 2, l, r)
        b = range_query(idx * 2 + 1, l, r)
        total_sum = a[0] + b[0]
        if a[1] is None: mn = b[1]
        elif b[1] is None: mn = a[1]
        else: mn = min(a[1], b[1])
        if a[2] is None: mx = b[2]
        elif b[2] is None: mx = a[2]
        else: mx = max(a[2], b[2])
        total_sumsq = a[3] + b[3]
        total_sumxy = a[4] + b[4]
        return (total_sum, mn, mx, total_sumsq, total_sumxy)

    def seg_query_sum(idx, l, r):
        return range_query(idx, l, r)[0]

    def seg_query_min(idx, l, r):
        return range_query(idx, l, r)[1]

    def seg_query_max(idx, l, r):
        return range_query(idx, l, r)[2]

    def seg_query_sumsq(idx, l, r):
        return range_query(idx, l, r)[3]

    def seg_query_sumxy(idx, l, r):
        return range_query(idx, l, r)[4]

    def collect_values(idx, l, r, out_list):
        if r < seg_L[idx] or seg_R[idx] < l:
            return
        if seg_L[idx] == seg_R[idx]:
            out_list.append(seg_sum[idx])
            return
        push(idx)
        collect_values(idx * 2, l, r, out_list)
        collect_values(idx * 2 + 1, l, r, out_list)

    build(1, 1, n)

    update_history = {}
    next_id = 1

    results = []
    audit = []
    num_updates = 0
    num_queries = 0
    num_reverses = 0
    num_batches = 0

    allowed_types = {'update', 'query', 'reverse', 'batch_update', 'conditional'}
    allowed_modes = {'sum', 'min', 'max', 'mean', 'var', 'unique', 'rms', 'trend'}

    for op_i, op in enumerate(operations, start=1):
        if not isinstance(op, list):
            return err(f"operation at index {op_i} must be a list")
        if len(op) == 0 or not isinstance(op[0], str):
            return err(f"operation at index {op_i} has invalid type or argument count")
        typ = op[0]

        if typ not in allowed_types:
            return err(f"operation type not supported at op {op_i}")

        if typ == 'update':
            if len(op) != 4:
                return err(f"operation at index {op_i} has invalid type or argument count")
            _, L, R, delta = op
            if not (isinstance(L, int) and isinstance(R, int) and 1 <= L <= n and 1 <= R <= n and L <= R):
                return err(f"operation indices out of bounds at op {op_i}: L={L}, R={R}")
            if not isinstance(delta, int):
                return err(f"delta at op {op_i} must be an integer")
            range_add(1, L, R, delta)
            num_updates += 1
            update_history[next_id] = (L, R, delta, True)
            err_check = check_bounds_after_update(op_i)
            if err_check:
                return err_check
            audit.append({'op_idx': op_i, 'type': 'update', 'args': [L, R, delta], 'result': None, 'affected_range': [L, R]})
            next_id += 1

        elif typ == 'query':
            if len(op) != 4:
                return err(f"operation at index {op_i} has invalid type or argument count")
            _, mode, L, R = op
            if mode not in allowed_modes:
                return err(f"query mode not supported at op {op_i}")
            if not (isinstance(L, int) and isinstance(R, int) and 1 <= L <= n and 1 <= R <= n and L <= R):
                return err(f"operation indices out of bounds at op {op_i}: L={L}, R={R}")

            length = R - L + 1
            res_val = None

            if mode in ('sum', 'min', 'max', 'mean', 'var', 'rms', 'trend'):
                sum_y = seg_query_sum(1, L, R)
                if not in_int64(sum_y):
                    return err(f"cumulative value out of range after op {op_i}")
                if mode == 'sum':
                    res_val = sum_y
                elif mode == 'min':
                    res_val = seg_query_min(1, L, R)
                elif mode == 'max':
                    res_val = seg_query_max(1, L, R)
                elif mode == 'mean':
                    res_val = half_up_round_fraction(Fraction(sum_y, length))
                elif mode == 'var':
                    # Population variance via sums: (n * sum(y^2) - (sum(y))^2) / n^2
                    s2 = seg_query_sumsq(1, L, R)
                    num = length * s2 - sum_y * sum_y
                    den = length * length
                    res_val = half_up_round_fraction(Fraction(num, den))
                elif mode == 'rms':
                    s2 = seg_query_sumsq(1, L, R)
                    # Default precision (28 digits) is sufficient for square root of int64 values
                    d = (Decimal(s2) / Decimal(length)).sqrt()
                    res_val = half_up_round_decimal(d)
                elif mode == 'trend':
                    if length == 1:
                        res_val = 0
                    else:
                        # Shift x to 1..length so slope matches prompt definition
                        sxy_abs = seg_query_sumxy(1, L, R)
                        sx_abs = sum_x(L, R)
                        sxx_abs = sum_xx(L, R)
                        sum_y = sum_y
                        c = L - 1
                        sxy_rel = sxy_abs - c * sum_y
                        sx_rel = sx_abs - c * length
                        sxx_rel = sxx_abs - 2 * c * sx_abs + (c * c) * length
                        num = length * sxy_rel - sx_rel * sum_y
                        den = length * sxx_rel - sx_rel * sx_rel
                        if den == 0:
                            return err(f"unknown error at op {op_i}")
                        # Default precision (28 digits) is sufficient for slope calculations
                        # Scale slope by 1000 before HALF_UP rounding
                        val = (Decimal(num) * Decimal(1000)) / Decimal(den)
                        res_val = half_up_round_decimal(val)
            elif mode == 'unique':
                # Gather values in [L..R] by visiting leaves
                vals = []
                collect_values(1, L, R, vals)
                res_val = len(set(vals))

            # Ensure result in int64
            if not in_int64(res_val):
                return err(f"cumulative value out of range after op {op_i}")

            results.append(res_val)
            num_queries += 1
            audit.append({'op_idx': op_i, 'type': 'query', 'args': [mode, L, R], 'result': res_val, 'affected_range': [L, R]})

        elif typ == 'reverse':
            if len(op) != 2:
                return err(f"operation at index {op_i} has invalid type or argument count")
            _, op_id = op
            if not (isinstance(op_id, int) and op_id > 0):
                return err("operation id must be a positive integer")
            if op_id not in update_history or update_history[op_id][3] is False:
                return err(f"reverse references non-existent or already reversed op id {op_id}")
            L, R, delta, _active = update_history[op_id]
            range_add(1, L, R, -delta)
            update_history[op_id] = (L, R, delta, False)
            num_reverses += 1
            err_check = check_bounds_after_update(op_i)
            if err_check:
                return err_check
            audit.append({'op_idx': op_i, 'type': 'reverse', 'args': [op_id], 'result': None, 'affected_range': [L, R]})

        elif typ == 'batch_update':
            if len(op) != 2 or not isinstance(op[1], list):
                return err(f"operation at index {op_i} has invalid type or argument count")
            subops = op[1]
            if len(subops) > MAX_BATCH_SIZE:
                return err(f"batch_update at op {op_i} exceeds max batch size")
            # Validate all sub-ops before applying to ensure atomicity
            for sub in subops:
                if (not isinstance(sub, list)) or len(sub) != 3:
                    return err(f"operation at index {op_i} has invalid type or argument count")
                L, R, delta = sub
                if not (isinstance(L, int) and isinstance(R, int) and 1 <= L <= n and 1 <= R <= n and L <= R):
                    return err(f"operation indices out of bounds at op {op_i}: L={L}, R={R}")
                if not isinstance(delta, int):
                    return err(f"delta at op {op_i} must be an integer")
            affected_ranges = []
            applied = []  # track applied sub-ops to rollback on failure
            for L, R, delta in subops:
                range_add(1, L, R, delta)
                applied.append((L, R, delta))
                affected_ranges.append([L, R])
            err_check = check_bounds_after_update(op_i)
            if err_check:
                # Rollback all applied changes on error to preserve atomicity
                for L, R, delta in reversed(applied):
                    range_add(1, L, R, -delta)
                return err_check
            for L, R, delta in subops:
                update_history[next_id] = (L, R, delta, True)
                next_id += 1
                num_updates += 1
            num_batches += 1
            audit.append({'op_idx': op_i, 'type': 'batch_update', 'args': [[L, R, d] for (L, R, d) in subops], 'result': None, 'affected_range': affected_ranges})

        elif typ == 'conditional':
            if len(op) != 4:
                return err(f"operation at index {op_i} has invalid type or argument count")
            _, L, R, threshold = op
            if not (isinstance(L, int) and isinstance(R, int) and 1 <= L <= n and 1 <= R <= n and L <= R):
                return err(f"operation indices out of bounds at op {op_i}: L={L}, R={R}")
            if not isinstance(threshold, int):
                return err(f"conditional query at op {op_i} requires integer threshold")
            s = seg_query_sum(1, L, R)
            if not in_int64(s):
                return err(f"cumulative value out of range after op {op_i}")
            ans = s if s > threshold else 0
            results.append(ans)
            num_queries += 1
            audit.append({'op_idx': op_i, 'type': 'conditional', 'args': [L, R, threshold], 'result': ans, 'affected_range': [L, R]})

        else:
            return err(f"unknown error at op {op_i}")

    final_sum = seg_query_sum(1, 1, n)
    final_min = seg_query_min(1, 1, n)
    final_max = seg_query_max(1, 1, n)
    vals_all = []
    collect_values(1, 1, n, vals_all)
    final_unique = len(set(vals_all))

    summary = {
        'num_updates': num_updates,
        'num_queries': num_queries,
        'num_reverses': num_reverses,
        'num_batches': num_batches,
        'final_sum': final_sum,
        'final_min': final_min,
        'final_max': final_max,
        'final_unique': final_unique
    }

    return {
        'results': results,
        'audit': audit,
        'summary': summary
    }

if __name__ == "__main__":
    n = 5
    operations = [
        ['update', 1, 3, 5],
        ['update', 2, 5, 2],
        ['query', 'sum', 1, 3],
        ['query', 'rms', 3, 5],
        ['conditional', 1, 5, 20],
        ['reverse', 1],
        ['query', 'trend', 1, 5],
    ]
    print(process_stock_movements(n, operations))