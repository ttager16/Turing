def manage_stock_data(operations: list) -> list:
    # Internal state
    companies = {}  # ticker -> dict with keys: length, audit (list per day), init_prices (list Decimal)
    outputs = []

    def err(msg):
        outputs.append(msg)

    for op in operations:
        if not isinstance(op, list) or len(op) == 0:
            err("Error: Invalid input.")
            continue
        cmd = op[0]
        if cmd == "init":
            # ["init", ticker: str, prices: list[float]]
            if len(op) != 3:
                err("Error: Invalid input.")
                continue
            ticker, prices = op[1], op[2]
            if not isinstance(ticker, str) or not isinstance(prices, list) or len(prices) == 0:
                err("Error: All companies must have non-empty price lists of equal length.")
                continue
            # validate all positive floats
            try:
                decs = [Decimal(str(p)) for p in prices]
            except Exception:
                err("Error: All companies must have non-empty price lists of equal length.")
                continue
            if any((p <= 0 for p in decs)):
                err("Error: Invalid price. Must be positive.")
                continue
            # Ensure equal length across existing companies
            length = len(decs)
            if companies:
                for other in companies.values():
                    if other['length'] != length:
                        err("Error: All companies must have non-empty price lists of equal length.")
                        break
                else:
                    # proceed
                    companies[ticker] = {
                        'length': length,
                        'init_prices': decs[:],
                        'audit': [[] for _ in range(length)]  # list per day of updates; each entry is dict
                    }
                    outputs.append(None)
                    continue
                continue
            else:
                companies[ticker] = {
                    'length': length,
                    'init_prices': decs[:],
                    'audit': [[] for _ in range(length)]
                }
                outputs.append(None)
                continue

        elif cmd == "update":
            # ["update", ticker: str, day: int, new_price: float]
            if len(op) != 4:
                err("Error: Invalid input.")
                continue
            ticker, day, new_price = op[1], op[2], op[3]
            if ticker not in companies:
                err("Error: Invalid ticker.")
                continue
            if not isinstance(day, int) or day < 0 or day >= companies[ticker]['length']:
                err("Error: Invalid ticker or day index.")
                continue
            try:
                newp = Decimal(str(new_price))
            except Exception:
                err("Error: Invalid price. Must be positive.")
                continue
            if newp <= 0:
                err("Error: Invalid price. Must be positive.")
                continue
            # Create update record
            audit_list = companies[ticker]['audit'][day]
            # Determine current active price at day before this update
            # Search audit_list for last active; else use init
            current = None
            for rec in reversed(audit_list):
                if rec['active']:
                    current = rec['new_price']
                    break
            if current is None:
                current = companies[ticker]['init_prices'][day]
            rec = {
                'new_price': newp,
                'prev_price': current,
                'active': True
            }
            audit_list.append(rec)
            outputs.append(None)
            continue

        elif cmd == "rollback":
            # ["rollback", ticker, steps, day(optional)]
            if len(op) not in (3,4):
                err("Error: Invalid input.")
                continue
            ticker = op[1]
            if ticker not in companies:
                err("Error: Invalid ticker.")
                continue
            steps = op[2]
            if not isinstance(steps, int) or steps <= 0:
                err("Error: Invalid input.")
                continue
            if len(op) == 4:
                day = op[3]
                if not isinstance(day, int) or day < 0 or day >= companies[ticker]['length']:
                    err("Error: Invalid ticker or day index.")
                    continue
            else:
                day = companies[ticker]['length'] - 1
            # We need to revert most recent 'steps' updates affecting the specified day.
            audit_list = companies[ticker]['audit'][day]
            # Count active updates in that day's audit history from the end
            active_indices = [i for i,rec in enumerate(audit_list) if rec['active']]
            if len(active_indices) < steps:
                err("Error: Rollback exceeds update history.")
                continue
            # deactivate last 'steps' active updates in that day
            to_remove = steps
            # traverse reversed to mark
            for rec in reversed(audit_list):
                if to_remove == 0:
                    break
                if rec['active']:
                    rec['active'] = False
                    to_remove -= 1
            outputs.append(None)
            continue

        elif cmd == "query":
            # ["query", ticker, mode, start_day, end_day]
            if len(op) != 5:
                err("Error: Invalid input.")
                continue
            ticker, mode, start_day, end_day = op[1], op[2], op[3], op[4]
            if ticker not in companies:
                err("Error: Invalid ticker.")
                continue
            if not isinstance(start_day, int) or not isinstance(end_day, int):
                err("Error: Invalid query range.")
                continue
            if start_day < 0 or end_day < 0 or start_day >= companies[ticker]['length'] or end_day >= companies[ticker]['length'] or start_day > end_day:
                err("Error: Invalid query range.")
                continue
            mode = str(mode)
            if mode not in ("sum","average","max","volatility"):
                err("Error: Invalid query mode.")
                continue
            # collect active prices for days in range
            prices = []
            for d in range(start_day, end_day+1):
                audit_list = companies[ticker]['audit'][d]
                val = None
                for rec in reversed(audit_list):
                    if rec['active']:
                        val = rec['new_price']
                        break
                if val is None:
                    val = companies[ticker]['init_prices'][d]
                prices.append(val)
            n = len(prices)
            if n == 0:
                err("Error: Invalid query range.")
                continue
            if mode == "sum":
                s = sum(prices, Decimal(0))
                res = s
            elif mode == "average":
                s = sum(prices, Decimal(0))
                res = s / Decimal(n)
            elif mode == "max":
                res = max(prices)
            else:  # volatility population std dev
                if n == 1:
                    res = Decimal(0)
                else:
                    s = sum(prices, Decimal(0))
                    mu = s / Decimal(n)
                    ss = sum((p - mu) * (p - mu) for p in prices)
                    var = ss / Decimal(n)
                    # sqrt of Decimal: use quantize via Decimal.sqrt not available; use context
                    try:
                        res = var.sqrt()
                    except Exception:
                        # fallback via float but ensure non-negative
                        vf = float(var) if var >= 0 else 0.0
                        res = Decimal(str(vf**0.5))
            # Round to 4 decimal places with HALF_UP
            q = res.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            outputs.append(float(q))
            continue

        elif cmd == "snapshot":
            # ["snapshot", ticker]
            if len(op) != 2:
                err("Error: Invalid input.")
                continue
            ticker = op[1]
            if ticker not in companies:
                err("Error: Invalid ticker.")
                continue
            comp = companies[ticker]
            active_prices = []
            for d in range(comp['length']):
                audit_list = comp['audit'][d]
                val = None
                for rec in reversed(audit_list):
                    if rec['active']:
                        val = rec['new_price']
                        break
                if val is None:
                    val = comp['init_prices'][d]
                active_prices.append(val)
            if len(active_prices) == 0:
                err("Error: All companies must have non-empty price lists of equal length.")
                continue
            latest = active_prices[-1]
            avg = sum(active_prices, Decimal(0)) / Decimal(len(active_prices))
            q1 = latest.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            q2 = avg.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            outputs.append({"latest": float(q1), "average": float(q2)})
            continue

        else:
            err("Error: Invalid input.")
            continue

    return outputs