def _dec(x):
    return Decimal(str(x))

class SegmentTree:
    def __init__(self, n):
        self.n = n
        size = 1
        while size < n: size <<= 1
        self.size = size
        # store per-leaf base metrics: price, volume
        # tree nodes store aggregate: sum_pv, sum_v, max_p, min_p, mpd, ls
        self.sum_pv = [Decimal('0')] * (2 * size)
        self.sum_v = [Decimal('0')] * (2 * size)
        self.max_p = [Decimal('-Infinity')] * (2 * size)
        self.min_p = [Decimal('Infinity')] * (2 * size)
        # lazy for price delta and volume delta to apply to range
        self.lazy_price = [Decimal('0')] * (2 * size)
        self.lazy_volume = [Decimal('0')] * (2 * size)
        # track which leaves have nonzero volume for mpd rules: if all zero, mpd=0
        self.leaf_price = [Decimal('0')] * size  # index 0..size-1
        self.leaf_volume = [Decimal('0')] * size

    def _pull(self, idx):
        l = idx*2
        r = l+1
        self.sum_pv[idx] = self.sum_pv[l] + self.sum_pv[r]
        self.sum_v[idx] = self.sum_v[l] + self.sum_v[r]
        # max/min only consider leaves with volume>0. If child has none, its max_p may be -Inf
        self.max_p[idx] = self.max_p[l] if self.max_p[l] > self.max_p[r] else self.max_p[r]
        self.min_p[idx] = self.min_p[l] if self.min_p[l] < self.min_p[r] else self.min_p[r]

    def _apply_node(self, idx, length, price_delta, vol_delta):
        # price_delta applied to all prices in node; volumes increased by vol_delta per element
        # But vol_delta is per-element delta; length is number of elements
        # Update sum_pv: sum_pv += price_delta * sum_v + vol_delta * avg_price? Actually we apply price change to each element's price:
        # For each element: price += price_delta; volume += vol_delta
        # New sum_pv = sum(price_i*volume_i) + price_delta*sum_v + sum_price_after_vol_change_due_to_volume_delta
        # When volume changes by vol_delta, the new contribution is price_i * vol_delta summed = vol_delta * sum(price_i)
        # We don't store sum(price_i) directly. But we can approximate by sum_pv / sum_v = WAP, and sum(price_i) = ? Not available.
        # To handle correctly, we will apply lazy only at leaves in this implementation for correctness.
        # So here, we won't implement complex lazy; instead use range update by iterating leaves when needed.
        pass

    # leaf operations
    def set_point(self, pos:int, price:Decimal, volume:Decimal):
        # set leaf to given base metrics
        idx = pos
        self.leaf_price[idx] = price
        self.leaf_volume[idx] = volume
        node = 1
        l = 0
        r = self.size
        # update tree by setting leaf at pos in internal arrays
        tree_idx = 1
        left = 0
        right = self.size
        while tree_idx < self.size:
            mid = (left + right)//2
            if pos < mid:
                tree_idx = tree_idx*2
                right = mid
            else:
                tree_idx = tree_idx*2+1
                left = mid
        # tree_idx is leaf
        if volume > 0:
            self.sum_v[tree_idx] = volume
            self.sum_pv[tree_idx] = price * volume
            self.max_p[tree_idx] = price
            self.min_p[tree_idx] = price
        else:
            self.sum_v[tree_idx] = Decimal('0')
            self.sum_pv[tree_idx] = Decimal('0')
            self.max_p[tree_idx] = Decimal('-Infinity')
            self.min_p[tree_idx] = Decimal('Infinity')
        # pull up
        tree_idx //= 2
        while tree_idx >= 1:
            self._pull(tree_idx)
            tree_idx //= 2

    def range_add(self, l:int, r:int, price_delta:Decimal, vol_delta:Decimal):
        # apply by updating each leaf in [l,r]
        if l > r: return
        for pos in range(l, r+1):
            p = self.leaf_price[pos] + price_delta
            v = self.leaf_volume[pos] + vol_delta
            if v < Decimal('0'):
                v = Decimal('0')
            self.set_point(pos, p, v)

    def query_range(self, l:int, r:int) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        # aggregate over leaves l..r
        total_pv = Decimal('0')
        total_v = Decimal('0')
        max_p = Decimal('-Infinity')
        min_p = Decimal('Infinity')
        for pos in range(l, r+1):
            v = self.leaf_volume[pos]
            p = self.leaf_price[pos]
            if v > 0:
                total_v += v
                total_pv += p * v
                if p > max_p: max_p = p
                if p < min_p: min_p = p
        if total_v == 0:
            wap = Decimal('0')
            mpd = Decimal('0')
        else:
            wap = total_pv / total_v
            if max_p == Decimal('-Infinity'):
                mpd = Decimal('0')
            else:
                mpd = max_p - min_p
        ls = (total_v / (Decimal('1') + mpd)) if (Decimal('1') + mpd) != 0 else Decimal('0')
        return wap, mpd, total_v, ls

    def apply_price_boost(self, l:int, r:int, boost:Decimal):
        for pos in range(l, r+1):
            p = self.leaf_price[pos] + boost
            self.set_point(pos, p, self.leaf_volume[pos])

    def snapshot_state(self):
        return {
            'leaf_price': self.leaf_price.copy(),
            'leaf_volume': self.leaf_volume.copy(),
        }

    def restore_state(self, state):
        self.leaf_price = state['leaf_price'].copy()
        self.leaf_volume = state['leaf_volume'].copy()
        # rebuild tree
        for pos in range(self.size):
            if pos < self.n:
                self.set_point(pos, self.leaf_price[pos], self.leaf_volume[pos])
            else:
                # clear extra leaves
                self.set_point(pos, Decimal('0'), Decimal('0'))

def process_operations(n: int, operations: list) -> list:
    st = SegmentTree(n)
    # operation log for rollback: list of dicts with timestamp and type and data to revert
    op_log: List[Dict[str, Any]] = []
    snapshots: Dict[Any, Dict[str, Any]] = {}
    results: List[List[float]] = []

    for op in operations:
        if not op: continue
        cmd = op[0]
        if cmd == 'update':
            _, idx, price, volume, timestamp = op
            idx = int(idx)
            price_d = _dec(price)
            vol_d = _dec(volume)
            # record previous base metrics
            prev_p = st.leaf_price[idx]
            prev_v = st.leaf_volume[idx]
            op_log.append({'timestamp': int(timestamp), 'type':'update', 'idx':idx, 'prev_p':prev_p, 'prev_v':prev_v})
            st.set_point(idx, price_d, vol_d)
        elif cmd == 'range_update':
            _, start, end, price_delta, volume_delta, timestamp = op
            l = int(start); r = int(end)
            pd = _dec(price_delta); vd = _dec(volume_delta)
            # record previous for all affected
            prev = [(i, st.leaf_price[i], st.leaf_volume[i]) for i in range(l, r+1)]
            op_log.append({'timestamp': int(timestamp), 'type':'range_update', 'prev': prev})
            st.range_add(l, r, pd, vd)
        elif cmd == 'query':
            _, start, end = op
            l = int(start); r = int(end)
            wap, mpd, cv, ls = st.query_range(l, r)
            # round to 2 decimals
            def rnd(d):
                return float(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            results.append([rnd(wap), rnd(mpd), rnd(cv), rnd(ls)])
        elif cmd == 'rollback':
            # ["rollback", t_start, t_end, metrics_to_rollback(optional)]
            if len(op) >= 3:
                t1 = int(op[1]); t2 = int(op[2])
            else:
                continue
            metrics = None
            if len(op) >= 4:
                metrics = op[3]
            # find operations with timestamp in range, reverse chronological
            to_rollback = [ (i,entry) for i,entry in enumerate(op_log) if t1 <= entry['timestamp'] <= t2 ]
            # sort by timestamp desc, then by index desc to reverse apply
            to_rollback.sort(key=lambda x: (x[1]['timestamp'], x[0]), reverse=True)
            indices = set(i for i,_ in to_rollback)
            for i,entry in to_rollback:
                if entry['type'] == 'update':
                    idx = entry['idx']
                    prev_p = entry['prev_p']
                    prev_v = entry['prev_v']
                    st.set_point(idx, prev_p, prev_v)
                elif entry['type'] == 'range_update':
                    for pos, pp, pv in entry['prev']:
                        st.set_point(pos, pp, pv)
                # remove from log
            # purge those entries from op_log
            op_log = [e for e in op_log if not (t1 <= e['timestamp'] <= t2)]
        elif cmd == 'snapshot':
            _, snap_id, timestamp = op
            snapshots[snap_id] = {
                'state': st.snapshot_state(),
                'op_log': copy.deepcopy(op_log),
                'timestamp': int(timestamp)
            }
        elif cmd == 'restore':
            _, snap_id = op
            if snap_id in snapshots:
                snap = snapshots[snap_id]
                st.restore_state(snap['state'])
                op_log = copy.deepcopy(snap['op_log'])
            else:
                # do nothing
                pass
        elif cmd == 'conditional_check':
            (_, src_start, src_end, mpd_threshold, dst_start, dst_end, cv_threshold, price_boost) = op
            ss = int(src_start); se = int(src_end)
            ds = int(dst_start); de = int(dst_end)
            mpd_t = _dec(mpd_threshold)
            cv_t = _dec(cv_threshold)
            boost = _dec(price_boost)
            wap_s, mpd_s, cv_s, ls_s = st.query_range(ss, se)
            wap_d, mpd_d, cv_d, ls_d = st.query_range(ds, de)
            if mpd_s > mpd_t and cv_d < cv_t:
                # apply as range_update with synthetic timestamp  - use timestamp 0
                prev = [(i, st.leaf_price[i], st.leaf_volume[i]) for i in range(ds, de+1)]
                op_log.append({'timestamp': 0, 'type':'range_update', 'prev': prev})
                st.apply_price_boost(ds, de, boost)
        else:
            # unknown; ignore
            pass

    return results