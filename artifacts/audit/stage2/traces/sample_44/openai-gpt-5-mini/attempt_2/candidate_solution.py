def optimize_trades(
    price_updates: List[List],
    budget: float,
    per_stock_cap_frac: float = 0.3,
    min_lot_dollars: float = 100.00
) -> List[List]:
    getcontext().prec = 28
    # Helpers
    def is_finite_positive(x):
        try:
            d = Decimal(x)
        except (InvalidOperation, TypeError):
            return False
        if not d.is_finite():
            return False
        return d > 0

    # Consolidate updates: latest valid per ticker (case-insensitive alpha 1-5) and latest broker fee
    prices = {}  # ticker -> Decimal price
    fee = None
    for upd in price_updates:
        if not isinstance(upd, (list, tuple)) or len(upd) != 2:
            continue
        key, val = upd[0], upd[1]
        if not isinstance(key, str):
            continue
        key_up = key.strip()
        if key_up.upper() == 'BROKER_FEE':
            if is_finite_positive(val):
                fee = Decimal(val)
            # invalid fee ignored
        else:
            ticker = key_up.upper()
            if not (1 <= len(ticker) <= 5 and ticker.isalpha()):
                continue
            if is_finite_positive(val):
                prices[ticker] = Decimal(val)
            # invalid price ignored

    if fee is None:
        fee = Decimal('0')

    # Build list of valid stocks
    stocks = []
    for t, p in prices.items():
        # score = 1 / (price * (1 + fee))
        denom = p * (Decimal('1') + fee)
        if denom > 0:
            score = Decimal('1') / denom
            stocks.append((t, p, score))
    if not stocks:
        # Nothing to allocate; all budget is reserve
        reserve = Decimal(budget).quantize(Decimal('0.01'))
        return [['RESERVE', float(reserve)]]

    # Sort by score desc, tie-breaker: higher raw price, then ticker alphabetical
    stocks.sort(key=lambda x: (x[2], x[1], ''.join(x[0])), reverse=True)

    # Allocation parameters
    B = Decimal(budget)
    per_stock_cap = (Decimal(per_stock_cap_frac) * B).quantize(Decimal('0.01'))
    lot = Decimal(min_lot_dollars).quantize(Decimal('0.01'))
    # Max lots per stock: floor(cap / lot)
    allocations = {t: Decimal('0') for t, _, _ in stocks}
    remaining = B

    # Greedy allocate: iterate stocks in order, for each allocate as many full lots as possible up to cap and remaining
    for t, p, s in stocks:
        if remaining < lot:
            break
        max_by_cap = (per_stock_cap // lot)
        if max_by_cap <= 0:
            continue
        # current allocated lots for t is 0 initially
        max_by_budget = (remaining // lot)
        lots = int(min(max_by_cap, max_by_budget))
        if lots <= 0:
            continue
        alloc = (Decimal(lots) * lot).quantize(Decimal('0.01'))
        allocations[t] = alloc
        remaining -= alloc

    # After single pass greedy per spec (give as much as possible to top stock then next...), but above already did that.
    # Prepare output: include only stocks with positive allocation, sorted by allocated amount desc then ticker name alpha
    out_stocks = [(t, a) for t, a in allocations.items() if a > 0]
    out_stocks.sort(key=lambda x: (x[1], x[0]), reverse=True)
    # Reserve must be present; remainder possibly with pennies; ensure total sums to budget (adjust rounding)
    # remaining is Decimal with cents precision
    remaining = remaining.quantize(Decimal('0.01'))
    # Build result list with floats rounded to 2 decimals
    result = []
    for t, a in out_stocks:
        result.append([t, float(a.quantize(Decimal('0.01')))])
    result.append(['RESERVE', float(remaining)])
    return result