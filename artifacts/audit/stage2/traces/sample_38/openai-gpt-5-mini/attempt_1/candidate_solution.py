def __init__(self, cost_per_unit: float | None, budget: float | None):
        self.cost_per_unit = cost_per_unit
        # budget stored as single-element list to allow mutation by reference
        self.budget = [float(budget)] if budget is not None else None


class SegmentTree:
    def __init__(self, data: List[float]):
        n = 1
        while n < len(data):
            n <<= 1
        self.n = n
        self.size = n << 1
        self.tree = [0.0] * (self.size)
        for i, v in enumerate(data):
            self.tree[self.n + i] = float(v)
        for i in range(self.n - 1, 0, -1):
            self.tree[i] = self.tree[i << 1] + self.tree[(i << 1) | 1]

    def update(self, idx: int, value: float):
        i = self.n + idx
        self.tree[i] = float(value)
        while i > 1:
            i >>= 1
            self.tree[i] = self.tree[i << 1] + self.tree[(i << 1) | 1]

    def query_all(self) -> float:
        return self.tree[1]


def _safe_get_stock_fields(d: Dict[str, Any]) -> Tuple[str, float, List[str]]:
    symbol = str(d.get("symbol", ""))
    volatility = float(d.get("volatility", 0.0))
    correlated_with = d.get("correlated_with") or []
    correlated_with = [str(x) for x in correlated_with]
    return symbol, volatility, correlated_with


def _build_corr_map(symbols: List[str], corr_lists: Dict[str, List[str]]) -> Dict[str, List[str]]:
    corr_map: Dict[str, List[str]] = {s: [] for s in symbols}
    for s, lst in corr_lists.items():
        for t in lst:
            if t in corr_map and t != s:
                if t not in corr_map[s]:
                    corr_map[s].append(t)
                if s not in corr_map[t]:
                    corr_map[t].append(s)
    return corr_map


def _calculate_scores(vols: Dict[str, float], corr_lists: Dict[str, List[str]]) -> Dict[str, float]:
    scores = {}
    for s, v in vols.items():
        base = max(0.0, 1.0 - v)
        penalty = 0.01 * len(corr_lists.get(s, []))
        sc = max(0.0, base - penalty)
        scores[s] = sc
    total = sum(scores.values()) or 1.0
    for s in scores:
        scores[s] = scores[s] / total
    return scores


def _calculate_risk(alloc: Dict[str, int], vols: Dict[str, float], corr_map: Dict[str, List[str]]) -> float:
    total_units = max(1, sum(alloc.values()))
    # Volatility risk
    vol_risk = 0.0
    weights: Dict[str, float] = {}
    for s in vols:
        w = alloc.get(s, 0) / total_units
        weights[s] = w
        vol_risk += w * vols[s]
    # Correlation penalty
    corr_pen = 0.0
    seen = set()
    for s in corr_map:
        for t in corr_map[s]:
            if s < t and (s, t) not in seen:
                ws = weights.get(s, 0.0)
                wt = weights.get(t, 0.0)
                if ws > 0 and wt > 0:
                    avg_vol = 0.5 * (vols.get(s, 0.0) + vols.get(t, 0.0))
                    corr_pen += 0.5 * min(ws, wt) * avg_vol * 0.5
                seen.add((s, t))
    # Concentration HHI
    hhi = 0.0
    for s in weights:
        hhi += (weights[s] ** 2)
    conc_pen = 0.005 * hhi
    # Degree penalty
    deg_pen = 0.0
    for s in corr_map:
        degree = float(len(corr_map[s]))
        deg_pen += 0.002 * weights.get(s, 0.0) * (degree / (degree + 1.0)) if degree >= 0.0 else 0.0
    return vol_risk + corr_pen + conc_pen + deg_pen


def _can_afford_transaction(cost: float | None, ctx: TransactionCostContext) -> bool:
    if ctx.cost_per_unit is None or ctx.budget is None or cost is None:
        return True
    return ctx.budget[0] >= float(cost)


def _deduct_cost(cost: float | None, ctx: TransactionCostContext):
    if ctx.cost_per_unit is not None and ctx.budget is not None and cost is not None:
        ctx.budget[0] -= float(cost)


def _refund_cost(cost: float | None, ctx: TransactionCostContext):
    if ctx.cost_per_unit is not None and ctx.budget is not None and cost is not None:
        ctx.budget[0] += float(cost)


def optimize_portfolio(stock_data: List[Dict[str, Any]], risk_tolerance: float,
                       transaction_cost_per_unit: float | None = None,
                       transaction_cost_budget: float | None = None) -> Dict[str, Any]:
    # Empty input handling
    if not isinstance(stock_data, list) or len(stock_data) == 0:
        return {"portfolio": {}, "expected_return": 0.0, "risk": 0.0}
    # Extract and normalize fields
    symbols: List[str] = []
    vols: Dict[str, float] = {}
    corr_lists: Dict[str, List[str]] = {}
    prices: Dict[str, float] = {}
    for d in stock_data:
        sym, vol, corr = _safe_get_stock_fields(d)
        symbols.append(sym)
        vols[sym] = float(vol)
        corr_lists[sym] = corr
        prices[sym] = float(d.get("price", 0.0))
    # Build correlation map
    corr_map = _build_corr_map(symbols, corr_lists)
    # Scores
    scores = _calculate_scores(vols, corr_lists)
    # Initialize allocation and segment tree (tracking allocations)
    alloc: Dict[str, int] = {s: 0 for s in symbols}
    initial_leaves = [0.0 for _ in symbols]
    seg = SegmentTree(initial_leaves)
    # Transaction context
    ctx = TransactionCostContext(transaction_cost_per_unit, transaction_cost_budget)
    # Base risk
    base_risk = _calculate_risk(alloc, vols, corr_map)
    lam = 0.5  # risk penalty coefficient
    # Main greedy allocation loop: up to 100 iterations allocate one unit each
    for _iter in range(100):
        best_delta = -1e18
        best_idx = -1
        # find best marginal delta
        for idx, s in enumerate(symbols):
            alloc[s] += 1
            seg.update(idx, alloc[s])
            new_risk = _calculate_risk(alloc, vols, corr_map)
            delta = scores[s] - lam * max(0.0, new_risk - base_risk)
            # revert
            alloc[s] -= 1
            seg.update(idx, alloc[s])
            if delta > best_delta:
                best_delta = delta
                best_idx = idx
        if best_idx == -1:
            break
        best_sym = symbols[best_idx]
        # Attempt allocation with backtracking if necessary
        unit_cost = None
        if ctx.cost_per_unit is not None:
            unit_cost = ctx.cost_per_unit
        if not _can_afford_transaction(unit_cost, ctx):
            # cannot afford any more transactions
            break
        # try primary allocation
        _deduct_cost(unit_cost, ctx)
        alloc[best_sym] += 1
        seg.update(best_idx, alloc[best_sym])
        curr_risk = _calculate_risk(alloc, vols, corr_map)
        if curr_risk <= risk_tolerance:
            base_risk = _calculate_risk(alloc, vols, corr_map)
            continue
        # primary violates risk: backtrack primary and try alternatives
        # refund primary cost and revert
        _refund_cost(unit_cost, ctx)
        alloc[best_sym] -= 1
        seg.update(best_idx, alloc[best_sym])
        allocated = False
        # iterate symbols in original order for backtracking
        for idx, s in enumerate(symbols):
            if s == best_sym:
                continue
            if ctx.cost_per_unit is not None:
                alt_cost = ctx.cost_per_unit
            else:
                alt_cost = None
            if not _can_afford_transaction(alt_cost, ctx):
                continue
            _deduct_cost(alt_cost, ctx)
            alloc[s] += 1
            seg.update(idx, alloc[s])
            curr_risk = _calculate_risk(alloc, vols, corr_map)
            if curr_risk <= risk_tolerance:
                base_risk = _calculate_risk(alloc, vols, corr_map)
                allocated = True
                break
            # revert and refund
            alloc[s] -= 1
            seg.update(idx, alloc[s])
            _refund_cost(alt_cost, ctx)
        if not allocated:
            # unable to allocate any unit this iteration
            break
    # Rebalance: move units from low-scoring to high-scoring stocks
    total_units = sum(alloc.values())
    if total_units == 0:
        # ensure all symbols present
        portfolio = {s: int(alloc.get(s, 0)) for s in symbols}
        return {"portfolio": portfolio, "expected_return": 0.0, "risk": round(0.0, 6)}
    max_moves = max(1, total_units // 20)
    moves = 0
    # prepare ordered lists by score
    sorted_high = sorted(symbols, key=lambda x: scores.get(x, 0.0), reverse=True)
    sorted_low = sorted(symbols, key=lambda x: scores.get(x, 0.0))
    for high_sym in sorted_high:
        if moves >= max_moves:
            break
        for low_sym in sorted_low[::-1]:
            if moves >= max_moves:
                break
            if high_sym == low_sym:
                continue
            if alloc.get(low_sym, 0) == 0:
                continue
            # rebalance move validation: need to check affordability of 2 * cost_per_unit
            move_cost = None
            if ctx.cost_per_unit is not None:
                move_cost = 2 * ctx.cost_per_unit
            if not _can_afford_transaction(move_cost, ctx):
                continue
            # deduct move cost (never refunded)
            _deduct_cost(move_cost, ctx)
            # execute move: remove one from low, add one to high
            alloc[low_sym] -= 1
            alloc[high_sym] += 1
            moves += 1
            # no rollback even if risk worsens per spec
            if moves >= max_moves:
                break
    # Post-optimization cleanup: rollback any excess to satisfy risk if violated
    final_risk = _calculate_risk(alloc, vols, corr_map)
    if final_risk > risk_tolerance:
        # attempt risk-based rollback: remove units from highest vol or highest contribution
        # iterate removing one unit at a time until risk <= tolerance or no units
        removal_order = sorted(symbols, key=lambda s: vols.get(s, 0.0), reverse=True)
        while final_risk > risk_tolerance and sum(alloc.values()) > 0:
            removed = False
            for s in removal_order:
                if alloc.get(s, 0) <= 0:
                    continue
                alloc[s] -= 1
                final_risk = _calculate_risk(alloc, vols, corr_map)
                removed = True
                if final_risk <= risk_tolerance:
                    break
            if not removed:
                break
    # Expected return calculation: weighted by allocation and scores
    total_units = max(1, sum(alloc.values()))
    expected_return = 0.0
    for s in symbols:
        w = alloc.get(s, 0) / total_units
        expected_return += w * scores.get(s, 0.0)
    # convert to percentage-like number (as in example they had ~0.03)
    # ensure rounding to 6 decimals
    portfolio = {s: int(alloc.get(s, 0)) for s in symbols}
    return {"portfolio": portfolio,
            "expected_return": round(float(expected_return), 6),
            "risk": round(float(_calculate_risk(alloc, vols, corr_map)), 6)}