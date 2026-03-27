def manage_high_freq_trades(
    markets: List[List[float]],
    operations: List[str],
    prices: List[float],
    market_indices: List[int]
) -> List[int]:
    # Represent each market as a list kept mostly sorted; use bisect for operations.
    # For efficiency, wrap markets in lists (they already are). We'll maintain sorted order on updates.
    results: List[int] = []
    n_ops = len(operations)
    for i in range(n_ops):
        op = operations[i]
        price = prices[i]
        midx = market_indices[i]
        if midx < 0 or midx >= len(markets):
            # invalid market index: for FIND return -1, for UPDATE ignore
            if op == "FIND":
                results.append(-1)
            continue
        market = markets[midx]
        if op == "FIND":
            # binary search for exact price
            lo = bisect.bisect_left(market, price)
            if lo < len(market) and market[lo] == price:
                results.append(lo)
            else:
                results.append(-1)
        elif op == "UPDATE":
            # Update behavior: if price exists replace (no-op), else insert maintaining sorted order.
            lo = bisect.bisect_left(market, price)
            if lo < len(market) and market[lo] == price:
                market[lo] = price
            else:
                market.insert(lo, price)
        else:
            # Unknown op: ignore; if FIND expected, return -1
            if op == "FIND":
                results.append(-1)
    return results