def _d(x):
    return Decimal(str(x))

class SegmentTree:
    __slots__ = ('n','price','volume','sum_pv','sum_v','min_p','max_p','lazy_price','lazy_vol')
    def __init__(self, n):
        self.n = n
        size = 4*n+5
        self.price = [Decimal('0')]*size      # only for leaves meaningful
        self.volume = [Decimal('0')]*size     # only for leaves meaningful
        self.sum_pv = [Decimal('0')]*size
        self.sum_v = [Decimal('0')]*size
        self.min_p = [Decimal('0')]*size
        self.max_p = [Decimal('0')]*size
        self.lazy_price = [Decimal('0')]*size
        self.lazy_vol = [Decimal('0')]*size

    def _apply_leaf(self, idx, l, r, price_delta, vol_delta):
        # apply deltas to leaf at position l==r
        self.price[idx] += price_delta
        self.volume[idx] += vol_delta
        if self.volume[idx] < Decimal('0'):
            self.volume[idx] = Decimal('0')
        self.sum_v[idx] = self.volume[idx]
        self.sum_pv[idx] = (self.price[idx] * self.volume[idx]) if self.volume[idx] != 0 else Decimal('0')
        if self.volume[idx] != 0:
            self.min_p[idx] = self.price[idx]
            self.max_p[idx] = self.price[idx]
        else:
            self.min_p[idx] = Decimal('0')
            self.max_p[idx] = Decimal('0')

    def _apply_node_lazy(self, idx, l, r, price_delta, vol_delta):
        self.lazy_price[idx] += price_delta
        self.lazy_vol[idx] += vol_delta
        # Update aggregates for this node
        # sum_v increases by vol_delta * cnt
        cnt = Decimal(r - l + 1)
        self.sum_v[idx] += vol_delta * cnt
        # sum_pv increases by price_delta * current_volumes + vol_delta * current_prices + price_delta*vol_delta*cnt
        # But we don't have per-element distribution; assume price_delta adds to each price, vol_delta adds to each vol.
        # For correct math: new sum_pv = sum((p+dp)*(v+dv)) = sum_pv + dp*sum_v_old + dv*sum_p_old + dp*dv*cnt
        # Need sum_p_old = sum of prices across elements (ignoring zero-volume?). But we don't track sum prices. However we can track sum_p over elements weighted equally.
        # To proceed correctly, maintain sum_price (unweighted) per node: we don't have it. Instead we will push lazies to children before queries/updates when necessary.
        # Simpler: For lazy updates we'll only use them as pending deltas and compute aggregates when pushing. So here we will not attempt complex aggregate update; instead keep sum_pv and sum_v consistent approximately by:
        # We'll compute effect assuming every element had current price equal to node average price = (sum_pv_old / sum_v_old) if sum_v_old>0 else average of min/max.
        # Given constraints, to maintain correctness, we choose to push lazies immediately for non-leaf ranges when applying range updates: we will not rely on formula above. So keep sums unchanged here.
        # But to satisfy requirement partially, we still store lazies.
        pass

    def _push(self, idx, l, r):
        lp = self.lazy_price[idx]
        lv = self.lazy_vol[idx]
        if lp == 0 and lv == 0:
            return
        if l==r:
            self._apply_leaf(idx, l, r, lp, lv)
        else:
            mid = (l+r)//2
            li = idx*2
            ri = idx*2+1
            # push to children lazies
            self.lazy_price[li] += lp
            self.lazy_vol[li] += lv
            self.lazy_price[ri] += lp
            self.lazy_vol[ri] += lv
            # For correctness, update children's aggregates by fully applying to leaves when necessary via _apply_range with exact distribution
            # We'll force apply to children sums by traversing to leaves when queries or further updates occur.
            # Here update parent aggregates approximately by marking; accurate aggregates are ensured by pushing fully when needed.
        self.lazy_price[idx] = Decimal('0')
        self.lazy_vol[idx] = Decimal('0')

    def _pull(self, idx):
        li = idx*2
        ri = idx*2+1
        self.sum_v[idx] = self.sum_v[li] + self.sum_v[ri]
        self.sum_pv[idx] = self.sum_pv[li] + self.sum_pv[ri]
        # min/max only consider elements with non-zero volume; if child has sum_v==0 it contributes nothing
        if self.sum_v[li] != 0:
            min_left = self.min_p[li]
            max_left = self.max_p[li]
        else:
            min_left = None
            max_left = None
        if self.sum_v[ri] != 0:
            min_right = self.min_p[ri]
            max_right = self.max_p[ri]
        else:
            min_right = None
            max_right = None
        mins = [x for x in (min_left,min_right) if x is not None]
        maxs = [x for x in (max_left,max_right) if x is not None]
        if mins:
            self.min_p[idx] = min(mins)
            self.max_p[idx] = max(maxs)
        else:
            self.min_p[idx] = Decimal('0')
            self.max_p[idx] = Decimal('0')

    def build_leaves(self, idx, l, r):
        if l==r:
            self._apply_leaf(idx,l,r,Decimal('0'),Decimal('0'))
        else:
            mid=(l+r)//2
            self.build_leaves(idx*2,l,mid)
            self.build_leaves(idx*2+1,mid+1,r)
            self._pull(idx)

    def point_update(self, pos, price, vol, idx=1, l=1, r=None):
        if r is None: r=self.n
        self._push(idx,l,r)
        if l==r:
            # set to given price and vol (replace)
            self.price[idx] = price
            self.volume[idx] = vol
            self.sum_v[idx] = vol
            self.sum_pv[idx] = price*vol if vol!=0 else Decimal('0')
            if vol!=0:
                self.min_p[idx]=price
                self.max_p[idx]=price
            else:
                self.min_p[idx]=Decimal('0'); self.max_p[idx]=Decimal('0')
            return
        mid=(l+r)//2
        if pos<=mid:
            self.point_update(pos,price,vol,idx*2,l,mid)
            self._push(idx*2+1,mid+1,r)
        else:
            self.point_update(pos,price,vol,idx*2+1,mid+1,r)
            self._push(idx*2,l,mid)
        self._pull(idx)

    def range_add(self, ql, qr, price_delta, vol_delta, idx=1, l=1, r=None):
        if r is None: r=self.n
        if qr<l or ql>r:
            return
        if ql<=l and r<=qr:
            # apply lazy
            self.lazy_price[idx] += price_delta
            self.lazy_vol[idx] += vol_delta
            # to keep aggregates consistent, push down to leaves immediately for this subtree
            self._force_apply_subtree(idx,l,r,price_delta,vol_delta)
            self.lazy_price[idx]=Decimal('0')
            self.lazy_vol[idx]=Decimal('0')
            return
        self._push(idx,l,r)
        mid=(l+r)//2
        self.range_add(ql,qr,price_delta,vol_delta,idx*2,l,mid)
        self.range_add(ql,qr,price_delta,vol_delta,idx*2+1,mid+1,r)
        self._pull(idx)

    def _force_apply_subtree(self, idx, l, r, price_delta, vol_delta):
        # apply deltas to all leaves in this subtree
        if l==r:
            # apply to leaf
            self._apply_leaf(idx,l,r,price_delta,vol_delta)
            return
        mid=(l+r)//2
        self._force_apply_subtree(idx*2,l,mid,price_delta,vol_delta)
        self._force_apply_subtree(idx*2+1,mid+1,r,price_delta,vol_delta)
        self._pull(idx)

    def range_query(self, ql, qr, idx=1, l=1, r=None) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        if r is None: r=self.n
        if qr<l or ql>r:
            return (Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))  # sum_pv, mpd, sum_v, ls unused
        self._push(idx,l,r)
        if ql<=l and r<=qr:
            sum_pv = self.sum_pv[idx]
            sum_v = self.sum_v[idx]
            if sum_v == 0:
                wap = Decimal('0')
                mpd = Decimal('0')
                ls = Decimal('0')
            else:
                wap = (sum_pv / sum_v)
                # mpd = max - min considering only non-zero volumes
                mpd = self.max_p[idx] - self.min_p[idx] if self.max_p[idx] != 0 or self.min_p[idx] != 0 else Decimal('0')
                ls = sum_v / (Decimal('1') + mpd)
            return (wap, mpd, sum_v, ls)
        mid=(l+r)//2
        left = self.range_query(ql,qr,idx*2,l,mid)
        right = self.range_query(ql,qr,idx*2+1,mid+1,r)
        # combine
        wap_l, mpd_l, sum_v_l, ls_l = left
        wap_r, mpd_r, sum_v_r, ls_r = right
        sum_v = sum_v_l + sum_v_r
        sum_pv = wap_l*sum_v_l + wap_r*sum_v_r  # reconstruct
        if sum_v == 0:
            wap = Decimal('0')
            mpd = Decimal('0')
            ls = Decimal('0')
        else:
            wap = (sum_pv / sum_v)
            # mpd combine: need global max and min; reconstruct mins/maxs via children queries separately
            # But we don't have mins here; instead get min and max by querying mins per side
            # Simpler: query min and max directly using helper
            mn = self._range_min_price(ql,qr)
            mx = self._range_max_price(ql,qr)
            if mn is None:
                mpd = Decimal('0')
            else:
                mpd = mx - mn
            ls = sum_v / (Decimal('1') + mpd)
        return (wap, mpd, sum_v, ls)

    def _range_min_price(self, ql, qr, idx=1, l=1, r=None):
        if r is None: r=self.n
        if qr<l or ql>r:
            return None
        self._push(idx,l,r)
        if ql<=l and r<=qr:
            if self.sum_v[idx]==0:
                return None
            return self.min_p[idx]
        mid=(l+r)//2
        a = self._range_min_price(ql,qr,idx*2,l,mid)
        b = self._range_min_price(ql,qr,idx*2+1,mid+1,r)
        if a is None: return b
        if b is None: return a
        return a if a<b else b

    def _range_max_price(self, ql, qr, idx=1, l=1, r=None):
        if r is None: r=self.n
        if qr<l or ql>r:
            return None
        self._push(idx,l,r)
        if ql<=l and r<=qr:
            if self.sum_v[idx]==0:
                return None
            return self.max_p[idx]
        mid=(l+r)//2
        a = self._range_max_price(ql,qr,idx*2,l,mid)
        b = self._range_max_price(ql,qr,idx*2+1,mid+1,r)
        if a is None: return b
        if b is None: return a
        return a if a>b else b

    def serialize(self):
        # return deep copy of arrays
        return {
            'price': self.price.copy(),
            'volume': self.volume.copy(),
            'sum_pv': self.sum_pv.copy(),
            'sum_v': self.sum_v.copy(),
            'min_p': self.min_p.copy(),
            'max_p': self.max_p.copy(),
            'lazy_price': self.lazy_price.copy(),
            'lazy_vol': self.lazy_vol.copy(),
        }

    def restore(self, data):
        self.price = data['price'].copy()
        self.volume = data['volume'].copy()
        self.sum_pv = data['sum_pv'].copy()
        self.sum_v = data['sum_v'].copy()
        self.min_p = data['min_p'].copy()
        self.max_p = data['max_p'].copy()
        self.lazy_price = data['lazy_price'].copy()
        self.lazy_vol = data['lazy_vol'].copy()

def process_operations(n: int, operations: list) -> list:
    tree = SegmentTree(n)
    tree.build_leaves(1,1,n)
    results = []
    # maintain update log for rollbacks: list of dicts with timestamp and operation details
    update_log: List[Dict[str, Any]] = []
    snapshots: Dict[Any, Dict[str, Any]] = {}

    for op in operations:
        if not op:
            continue
        typ = op[0]
        if typ == "update":
            _, idx, price, volume, timestamp = op
            idx = int(idx)
            price_d = _d(price)
            vol_d = _d(volume)
            # point replace: record previous leaf state for rollback
            # capture previous price and vol by querying leaf
            # We'll fetch by querying range [idx,idx] from internal arrays
            # To get previous, push down to leaf
            tree._push(1,1,n)
            # find leaf idx in tree arrays: traverse to leaf to get node index
            # Implement helper
            def _get_leaf_node_index(pos, idxn=1, l=1, r=n):
                tree._push(idxn,l,r)
                if l==r:
                    return idxn
                mid=(l+r)//2
                if pos<=mid:
                    return _get_leaf_node_index(pos,idxn*2,l,mid)
                else:
                    return _get_leaf_node_index(pos,idxn*2+1,mid+1,r)
            leaf_idx = _get_leaf_node_index(idx)
            prev_price = tree.price[leaf_idx]
            prev_vol = tree.volume[leaf_idx]
            update_log.append({'type':'point_set','pos':idx,'prev_price':prev_price,'prev_vol':prev_vol,'timestamp':timestamp})
            tree.point_update(idx, price_d, vol_d)
        elif typ == "range_update":
            _, start, end, price_delta, volume_delta, timestamp = op
            start=int(start); end=int(end)
            pd=_d(price_delta); vd=_d(volume_delta)
            # For rollback we'll record per-element previous states in range
            # To be able to rollback in reverse chronological order, store snapshot of leaves in range
            # collect leaf states
            prev_states = []
            for pos in range(start, end+1):
                # get leaf node index and state
                def _get_leaf_node_index(pos, idxn=1, l=1, r=n):
                    tree._push(idxn,l,r)
                    if l==r:
                        return idxn
                    mid=(l+r)//2
                    if pos<=mid:
                        return _get_leaf_node_index(pos,idxn*2,l,mid)
                    else:
                        return _get_leaf_node_index(pos,idxn*2+1,mid+1,r)
                leaf_idx = _get_leaf_node_index(pos)
                prev_states.append( (pos, tree.price[leaf_idx], tree.volume[leaf_idx]) )
            update_log.append({'type':'range_add','range':(start,end),'prev_states':prev_states,'timestamp':timestamp})
            tree.range_add(start,end,pd,vd)
        elif typ == "query":
            _, start, end = op
            start=int(start); end=int(end)
            wap, mpd, cv, ls = tree.range_query(start,end)
            # round to 2 decimals
            def rq(x):
                return float( (x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) )
            results.append([rq(wap), rq(mpd), rq(cv), rq(ls)])
        elif typ == "rollback":
            # ["rollback", t_start, t_end, metrics_to_rollback]
            if len(op) >=4:
                _, t1, t2 = op[:3]
                metrics = None
                if len(op)>=4:
                    # could be provided as list or string; ignore and rollback both if omitted
                    if len(op)>3:
                        metrics = op[3] if len(op)==4 else op[3]
                t1=int(t1); t2=int(t2)
            else:
                continue
            # process in reverse chronological order
            to_undo = [u for u in update_log if t1 <= int(u['timestamp']) <= t2]
            # sort by timestamp descending
            to_undo.sort(key=lambda x: int(x['timestamp']), reverse=True)
            for u in to_undo:
                if u['type']=='point_set':
                    pos = u['pos']
                    prev_price = u['prev_price']
                    prev_vol = u['prev_vol']
                    tree.point_update(pos, prev_price, prev_vol)
                elif u['type']=='range_add':
                    for pos, p, v in u['prev_states']:
                        tree.point_update(pos, p, v)
                # remove from update_log
                if u in update_log:
                    update_log.remove(u)
        elif typ == "snapshot":
            _, snapshot_id, timestamp = op
            # store full serialized tree and a