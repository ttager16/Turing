from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

DECIMAL_PRECISION = Decimal("0.0001")
CONTEXT_PREC = 50

getcontext().prec = CONTEXT_PREC

def quantize_out(d: Decimal) -> float:
    """Round Decimal to 4 decimal places and return float."""
    q = d.quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)
    return float(q)

def manage_stock_data(operations: list) -> list:
    """
    Process a sequence of stock management operations across multiple companies.

    Maintains internal state and immutable audit logs for all updates, rollbacks, queries,
    and snapshots. Returns one output per operation, where "init", "update", and "rollback"
    yield None, and "query" or "snapshot" yield computed results or error messages.
    """

    companies_state: Dict[str, List[Optional[Decimal]]] = {}
    audit_logs: Dict[str, List[Dict[str, Any]]] = {}
    results: List[Any] = []
    expected_length: Optional[int] = None

    def is_update_active(ticker: str, update_idx: int) -> bool:
        """Determine whether the update at update_idx is still active by scanning later logs for inactivations referencing it."""
        for j in range(update_idx + 1, len(audit_logs[ticker])):
            e = audit_logs[ticker][j]
            if e.get("type") == "update_inactivated" and e.get("original_index") == update_idx:
                return False
        return True

    for op in operations:
        if not isinstance(op, (list, tuple)) or len(op) == 0:
            results.append(None)
            continue

        op_type = op[0]

        if op_type == "init":
            try:
                ticker = op[1]
                prices = op[2]
            except Exception:
                results.append("Error: All companies must have non-empty price lists of equal length.")
                continue

            if not isinstance(prices, list) or len(prices) == 0:
                results.append("Error: All companies must have non-empty price lists of equal length.")
                continue
            if not all(isinstance(p, (int, float)) and p > 0 for p in prices):
                results.append("Error: Invalid price. Must be positive.")
                continue

            if expected_length is None:
                expected_length = len(prices)
            else:
                if len(prices) != expected_length:
                    results.append("Error: All companies must have non-empty price lists of equal length.")
                    continue

            companies_state[ticker] = [Decimal(str(p)) for p in prices]
            audit_logs[ticker] = []
            results.append(None)
            continue

        if op_type == "update":
            try:
                ticker = op[1]
                day = op[2]
                new_price = op[3]
            except Exception:
                results.append("Error: Invalid ticker or day index.")
                continue

            if ticker not in companies_state:
                results.append("Error: Invalid ticker or day index.")
                continue

            if not isinstance(new_price, (int, float)) or new_price <= 0:
                results.append("Error: Invalid price. Must be positive.")
                continue

            if not isinstance(day, int) or day < 0 or day >= len(companies_state[ticker]):
                results.append("Error: Invalid ticker or day index.")
                continue

            old_price = companies_state[ticker][day]
            new_price_dec = Decimal(str(new_price))

            log_entry = {
                "type": "update",
                "day": day,
                "old_price": old_price,
                "new_price": new_price_dec,
                "active": True
            }
            audit_logs[ticker].append(log_entry)
            companies_state[ticker][day] = new_price_dec

            results.append(None)
            continue

        if op_type == "rollback":
            try:
                ticker = op[1]
                steps = op[2]
                day = op[3] if len(op) > 3 else None
            except Exception:
                results.append("Error: Invalid ticker or day index.")
                continue

            if ticker not in companies_state:
                results.append("Error: Invalid ticker.")
                continue

            if not isinstance(steps, int) or steps <= 0:
                results.append("Error: Invalid input.")
                continue

            if day is None:
                target_day = len(companies_state[ticker]) - 1
            else:
                target_day = day

            if target_day < 0 or target_day >= len(companies_state[ticker]):
                results.append("Error: Invalid ticker or day index.")
                continue

            cand_indices = []
            for idx in range(len(audit_logs[ticker]) - 1, -1, -1):
                entry = audit_logs[ticker][idx]
                if entry["type"] != "update":
                    continue
                if not is_update_active(ticker, idx):
                    continue
                if entry["day"] == target_day:
                    cand_indices.append(idx)
                    if len(cand_indices) == steps:
                        break

            if len(cand_indices) < steps:
                results.append("Error: Rollback exceeds update history.")
                continue

            rolled_update_ids = []
            for idx in cand_indices:
                entry = audit_logs[ticker][idx]
                companies_state[ticker][entry["day"]] = entry["old_price"]

                # Mark the original update as inactive
                audit_logs[ticker][idx]["active"] = False

                # Add an immutable inactivation log entry
                inactivation_log = {
                    "type": "update_inactivated",
                    "reverted_update_day": entry["day"],
                    "reverted_old_price": entry["old_price"],
                    "reverted_new_price": entry["new_price"],
                    "original_index": idx,
                    "active": False
                }
                audit_logs[ticker].append(inactivation_log)
                rolled_update_ids.append(len(audit_logs[ticker]) - 1)

            rollback_log = {
                "type": "rollback",
                "steps": steps,
                "target_day": target_day,
                "rolled_inactivation_log_ids": rolled_update_ids,
                "active": True
            }
            audit_logs[ticker].append(rollback_log)

            results.append(None)
            continue

        if op_type == "query":
            try:
                ticker = op[1]
                mode = op[2]
                start_day = op[3]
                end_day = op[4]
            except Exception:
                results.append("Error: Invalid query range.")
                continue

            if ticker not in companies_state:
                results.append("Error: Invalid ticker.")
                continue

            if mode not in ["sum", "average", "max", "volatility"]:
                results.append("Error: Invalid query mode.")
                continue

            if (not isinstance(start_day, int) or not isinstance(end_day, int)
                or start_day < 0 or end_day < 0 or start_day > end_day
                or end_day >= len(companies_state[ticker])):
                results.append("Error: Invalid query range.")
                continue

            slice_prices: List[Decimal] = []
            for d in range(start_day, end_day + 1):
                val = companies_state[ticker][d]
                if val is not None:
                    slice_prices.append(val)

            if len(slice_prices) == 0:
                results.append("Error: Invalid query range.")
                continue

            if mode == "sum":
                s = sum(slice_prices, Decimal("0"))
                results.append(quantize_out(s))
                continue

            if mode == "average":
                s = sum(slice_prices, Decimal("0"))
                avg = s / Decimal(len(slice_prices))
                results.append(quantize_out(avg))
                continue

            if mode == "max":
                m = max(slice_prices)
                results.append(quantize_out(m))
                continue

            if mode == "volatility":
                n = len(slice_prices)
                if n == 1:
                    results.append(0.0)
                    continue
                s = sum(slice_prices, Decimal("0"))
                mean = s / Decimal(n)
                variance = sum((p - mean) ** 2 for p in slice_prices) / Decimal(n)
                if variance < 0:
                    variance = Decimal("0")
                stddev = variance.sqrt()
                results.append(quantize_out(stddev))
                continue

        if op_type == "snapshot":
            try:
                ticker = op[1]
            except Exception:
                results.append("Error: Invalid ticker.")
                continue

            if ticker not in companies_state:
                results.append("Error: Invalid ticker.")
                continue

            last_index = len(companies_state[ticker]) - 1
            last_value = companies_state[ticker][last_index]

            if last_value is None:
                latest_out = 0.0
            else:
                latest_out = quantize_out(last_value)

            active_prices = [p for p in companies_state[ticker] if p is not None]
            if not active_prices:
                avg_out = 0.0
            else:
                avg_out = quantize_out(sum(active_prices, Decimal("0")) / Decimal(len(active_prices)))

            snapshot = {"latest": latest_out, "average": avg_out}
            results.append(snapshot)
            continue

        results.append(None)

    return results