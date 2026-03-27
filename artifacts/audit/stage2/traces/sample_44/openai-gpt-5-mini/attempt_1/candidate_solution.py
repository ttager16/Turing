def optimize_trades(
    price_updates: List[List],
    budget: float,
    per_stock_cap_frac: float = 0.3,
    min_lot_dollars: float = 100.00
) -> List[List]:
    getcontext().prec = 28
    # Helpers
    def is_valid_number(x):
        try:
            d = Decimal(str(x))
        except (InvalidOperation, TypeError):
            return False
        if not d.is_finite():
            return False
        return d > 0
    # Consolidate updates: last valid per ticker (case-insensitive) and last valid broker fee
    latest_prices = {}  # ticker -> Decimal price
    latest_fee = None
    for upd in price_updates:
        if not isinstance(upd, (list, tuple)) or len(upd) < 2:
            continue
        key = upd[0]
        val = upd[1]
        if not isinstance(key, str):
            continue
        key_up = key.upper()
        if key_up == 'BROKER_FEE':
            if is_valid_number(val):
                latest_fee = Decimal(str(val))
            # invalid fee does not override prior
        else:
            # ticker validation: alphabetic, length 1-5
            if not (1 <= len(key_up) <= 5 and key_up.isalpha()):
                continue
            if is_valid_number(val):
                latest_prices[key_up] = Decimal(str(val))
            # invalid price does not override prior
    fee = latest_fee if latest_fee is not None else Decimal('0')
    budget_d = Decimal(str(budget))
    per_stock_cap = (Decimal(str(per_stock_cap_frac)) * budget_d)
    min_lot = Decimal(str(min_lot_dollars))
    # Build list of valid stocks
    stocks = []
    for ticker, price in latest_prices.items():
        # score = 1 / (price * (1 + fee))
        denom = price * (Decimal('1') + fee)
        if denom <= 0:
            continue
        score = Decimal('1') / denom
        stocks.append((ticker, price, score))
    # Sort by score desc, tie-break: higher raw price wins, then ticker alphabetical
    stocks.sort(key=lambda x: (x[2], x[1], -ord(x[0][0]) ), reverse=True)
    # The above lambda hack negative ord isn't correct for full ticker tie-break; replace with full explicit comparator via tuple:
    stocks.sort(key=lambda x: (x[2], x[1], ''.join(chr(ord(c)) for c in x[0])), reverse=True)
    # Better: create proper sort key: (-score, -price, ticker)
    stocks.sort(key=lambda x: (-x[2], -x[1], x[0]))
    allocations = {}
    remaining = budget_d
    # Greedy allocate: for each stock, allocate as many full lots as possible up to per-stock cap
    # Each allocation must be multiple of min_lot
    for ticker, price, score in stocks:
        if remaining < min_lot:
            break
        cap = per_stock_cap
        max_for_stock = min(cap, remaining)
        # number of full lots possible
        lots = (max_for_stock // min_lot)
        if lots <= 0:
            continue
        alloc = lots * min_lot
        allocations[ticker] = alloc
        remaining -= alloc
    # Ensure total allocations + reserve == budget (remaining is reserve)
    # Prepare output: include only stocks with positive allocated amount, sort by allocated amount desc then ticker
    out_items = []
    sorted_allocs = sorted(allocations.items(), key=lambda x: (-x[1], x[0]))
    for t, a in sorted_allocs:
        if a > 0:
            out_items.append([t, float(a.quantize(Decimal('0.01')))])
    reserve = float(remaining.quantize(Decimal('0.01')))
    out_items.append(['RESERVE', reserve])
    return out_items