from typing import List
from decimal import Decimal, ROUND_FLOOR
import math

def optimize_trades(
    price_updates: List[List],
    budget: float,
    per_stock_cap_frac: float = 0.3,
    min_lot_dollars: float = 100.00
) -> List[List]:

    def is_valid_positive_number(value):
        try:
            val = float(value)
            return math.isfinite(val) and val > 0.0
        except Exception:
            return False

    def dec(value):
        return Decimal(str(value))

    lot_value = dec(min_lot_dollars)
    if not is_valid_positive_number(min_lot_dollars):
        return [['RESERVE', float(dec(budget).quantize(Decimal('0.01')))]]

    lot_precision = -lot_value.as_tuple().exponent if lot_value != 0 else 2
    quant_unit = Decimal('1').scaleb(-lot_precision)
    budget_amount = dec(budget)

    broker_fee = dec(0)
    latest_prices = {}
    broker_fee_set = False

    for entry in price_updates:
        if not (isinstance(entry, list) and len(entry) == 2):
            continue
        key, value = entry

        if isinstance(key, str) and key.upper() == 'BROKER_FEE':
            if is_valid_positive_number(value):
                broker_fee = dec(value)
                broker_fee_set = True
            continue

        if not isinstance(key, str):
            continue

        ticker = key.strip().upper()
        if not (1 <= len(ticker) <= 5 and ticker.isalpha()):
            continue
        if not is_valid_positive_number(value):
            continue

        latest_prices[ticker] = dec(value)

    if not latest_prices:
        return [['RESERVE', float(budget_amount.quantize(Decimal('0.01')))]]

    effective_fee = Decimal(1) + (broker_fee if broker_fee_set else Decimal(0))
    stock_scores = [
        (ticker, price, Decimal(1) / (price * effective_fee))
        for ticker, price in latest_prices.items()
    ]
    stock_scores.sort(key=lambda x: (-x[2], -x[1], x[0]))

    if lot_value <= 0:
        return [['RESERVE', float(budget_amount.quantize(Decimal('0.01')))]]

    total_lots = int((budget_amount / lot_value).to_integral_value(rounding=ROUND_FLOOR))
    cap_fraction = dec(per_stock_cap_frac) if is_valid_positive_number(per_stock_cap_frac) else dec(0)
    cap_amount = budget_amount * cap_fraction
    lots_per_stock_cap = int((cap_amount / lot_value).to_integral_value(rounding=ROUND_FLOOR))

    lots_allocation = {}
    remaining_lots = total_lots

    for ticker, _, _ in stock_scores:
        if remaining_lots <= 0:
            break
        if lots_per_stock_cap <= 0:
            continue
        assign_lots = min(lots_per_stock_cap, remaining_lots)
        if assign_lots > 0:
            lots_allocation[ticker] = assign_lots
            remaining_lots -= assign_lots

    allocations = []
    for ticker, lots in lots_allocation.items():
        amount = (lot_value * Decimal(lots)).quantize(quant_unit)
        if amount > 0:
            allocations.append((ticker, amount))

    allocations.sort(key=lambda x: (-x[1], x[0]))

    total_allocated = sum(amount for _, amount in allocations) if allocations else Decimal(0)
    remaining_amount = (budget_amount - total_allocated)
    remaining_amount = max(remaining_amount, Decimal(0))
    reserve_amount = float(remaining_amount.quantize(quant_unit))

    result = [[ticker, float(amount)] for ticker, amount in allocations]
    result.append(['RESERVE', reserve_amount])

    return result


if __name__ == "__main__": # pragma: no cover
    price_updates = [
        ['aapl', 152.0],
        ['BROKER_FEE', 0.005],
        ['GOOG', 2820.0],
        ['AMZN', 3400.0],
        ['AAPL', 150.0],
        ['BROKER_FEE', 0.010],
        ['MSFT!', 420.0],
        ['GOOG', -1.0],
        ['TSLA', 0.0]
    ]
    budget = 50000.0
    per_stock_cap_frac = 0.30
    min_lot_dollars = 1200.00

    result = optimize_trades(price_updates, budget, per_stock_cap_frac, min_lot_dollars)
    print(result)