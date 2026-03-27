def _dec(x):
    return Decimal(str(x))

def _round4(d: Decimal) -> float:
    q = d.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return float(q)

def manage_stock_data(operations: list) -> list:
    # State
    outputs: List[Any] = []
    # tickers -> {
    #   'length': int,
    #   'initial': [Decimal],
    #   'audits': [ list of audit entries per day ],
    #   'updates_global': list of update entries (ordered)
    # }
    # audit entry: { 'value': Decimal, 'active': bool, 'op_index': int }
    # update entry: { 'day': int, 'value': Decimal, 'active': bool, 'audit_idx': int }
    state: Dict[str, Dict[str, Any]] = {}
    op_counter = 0  # monotonic op index for audit

    def validate_companies_equal_lengths(tkr, prices):
        # ensure all existing companies have same length as new init
        if not prices:
            return False
        l = len(prices)
        for other in state.values():
            if other['length'] != l:
                return False
        return True

    for op in operations:
        op_counter += 1
        if not op:
            outputs.append("Error: Invalid input.")
            continue
        cmd = op[0]

        if cmd == "init":
            # ["init", ticker: str, prices: list[float]]
            if len(op) != 3:
                outputs.append("Error: Invalid input.")
                continue
            ticker = op[1]
            prices = op[2]
            if not isinstance(prices, list) or not prices:
                outputs.append("Error: All companies must have non-empty price lists of equal length.")
                continue
            if ticker in state:
                # re-init not allowed; treat as error
                outputs.append("Error: Invalid input.")
                continue
            if not validate_companies_equal_lengths(ticker, prices) and state:
                outputs.append("Error: All companies must have non-empty price lists of equal length.")
                continue
            # build
            dec_prices = []
            audits_per_day = []
            for p in prices:
                if p is None:
                    outputs.append("Error: Invalid input.")
                    break
                d = _dec(p)
                if d <= 0:
                    outputs.append("Error: Invalid price. Must be positive.")
                    break
                dec_prices.append(d)
                # initial baseline audit entry is active
                audits_per_day.append([{'value': d, 'active': True, 'op_index': op_counter}])
            else:
                state[ticker] = {
                    'length': len(dec_prices),
                    'initial': dec_prices.copy(),
                    'audits': audits_per_day,  # list per day of list of audit entries (history)
                    'updates_global': []  # list of dicts: day, value, active, audit_idx
                }
                outputs.append(None)
                continue
            # if break occurred, no state change; already appended error
            continue

        elif cmd == "update":
            # ["update", ticker: str, day: int, new_price: float]
            if len(op) != 4:
                outputs.append("Error: Invalid input.")
                continue
            ticker, day, new_price = op[1], op[2], op[3]
            if ticker not in state:
                outputs.append("Error: Invalid ticker.")
                continue
            if not isinstance(day, int) or day < 0 or day >= state[ticker]['length']:
                outputs.append("Error: Invalid ticker or day index.")
                continue
            try:
                dnew = _dec(new_price)
            except Exception:
                outputs.append("Error: Invalid price. Must be positive.")
                continue
            if dnew <= 0:
                outputs.append("Error: Invalid price. Must be positive.")
                continue
            # append audit entry for that day
            audit_entry = {'value': dnew, 'active': True, 'op_index': op_counter}
            audits_day = state[ticker]['audits'][day]
            # mark prior active for that day inactive
            for a in audits_day:
                if a['active']:
                    a['active'] = False
            audits_day.append(audit_entry)
            # add to global updates list
            upd = {'day': day, 'value': dnew, 'active': True, 'audit_idx': len(audits_day)-1, 'op_index': op_counter}
            state[ticker]['updates_global'].append(upd)
            outputs.append(None)
            continue

        elif cmd == "rollback":
            # ["rollback", ticker, steps, day?]
            if len(op) not in (3,4,5):
                outputs.append("Error: Invalid input.")
                continue
            # allowed forms: ["rollback", ticker, steps] or ["rollback", ticker, steps, day]
            ticker = op[1]
            if ticker not in state:
                outputs.append("Error: Invalid ticker.")
                continue
            steps = op[2]
            day_provided = None
            if len(op) >= 4:
                day_provided = op[3]
            if not isinstance(steps, int) or steps <= 0:
                outputs.append("Error: Invalid input.")
                continue
            length = state[ticker]['length']
            if day_provided is None:
                day = length - 1
            else:
                if not isinstance(day_provided, int) or day_provided < 0 or day_provided >= length:
                    outputs.append("Error: Invalid ticker or day index.")
                    continue
                day = day_provided
            # find updates to revert: most recent 'steps' updates for this ticker that affect that day
            # If day provided, only those whose day == day; else default day index above.
            # We must consider update order (updates_global list). Rollback most recent affecting that day.
            updates = state[ticker]['updates_global']
            # collect indices in updates list of active updates that affect day
            candidates = []
            for idx in range(len(updates)-1, -1, -1):
                u = updates[idx]
                if u['active'] and u['day'] == day:
                    candidates.append(idx)
            if len(candidates) < steps:
                outputs.append("Error: Rollback exceeds update history.")
                continue
            # deactivate the last 'steps' of those
            to_revert = candidates[:steps]
            # For each revert index, mark update inactive and mark corresponding audit entry inactive, and reactivate previous audit for that day if any
            for upd_idx in to_revert:
                u = updates[upd_idx]
                if not u['active']:
                    continue  # shouldn't happen
                u['active'] = False
                d = u['day']
                audits_day = state[ticker]['audits'][d]
                # mark the specific audit entry inactive (by matching op_index and value)
                # find matching audit entry index equal to u['audit_idx'] or by op_index
                if 0 <= u.get('audit_idx', -1) < len(audits_day):
                    audits_day[u['audit_idx']]['active'] = False
                else:
                    # fallback: find last matching op_index
                    for a in reversed(audits_day):
                        if a['op_index'] == u.get('op_index'):
                            a['active'] = False
                            break
                # now reactivate the most recent prior audit entry for that day if any
                for a in reversed(audits_day):
                    if a['active']:
                        break
                else:
                    # no active found, so if there exists any prior entries, reactivate the latest prior (this would be baseline)
                    # but baseline would be present in audits list; we only deactivated the audit just appended; prior baseline should remain active unless multiple updates were rolled back out of order.
                    # ensure at least one active: activate last audit_entry if exists
                    if audits_day:
                        audits_day[-1]['active'] = True
            # record rollback action into audit log as non-price-affecting but for immutability we won't need separate structure beyond marking updates inactive
            outputs.append(None)
            continue

        elif cmd == "query":
            # ["query", ticker, mode, start_day, end_day]
            if len(op) != 5:
                outputs.append("Error: Invalid input.")
                continue
            ticker, mode, start_day, end_day = op[1], op[2], op[3], op[4]
            if ticker not in state:
                outputs.append("Error: Invalid ticker.")
                continue
            if mode not in ("sum", "average", "max", "volatility"):
                outputs.append("Error: Invalid query mode.")
                continue
            if not (isinstance(start_day, int) and isinstance(end_day, int)):
                outputs.append("Error: Invalid query range.")
                continue
            if start_day < 0 or end_day < 0 or start_day >= state[ticker]['length'] or end_day >= state[ticker]['length'] or start_day > end_day:
                outputs.append("Error: Invalid query range.")
                continue
            # gather active prices for days in range
            prices: List[Decimal] = []
            for d in range(start_day, end_day+1):
                audits_day = state[ticker]['audits'][d]
                # find active audit entry (last active)
                val = None
                for a in reversed(audits_day):
                    if a['active']:
                        val = a['value']
                        break
                if val is None:
                    outputs.append("Error: Invalid ticker or day index.")
                    break
                prices.append(val)
            else:
                n = len(prices)
                if mode == "sum":
                    s = sum(prices, Decimal(0))
                    outputs.append(_round4(s))
                    continue
                if mode == "average":
                    s = sum(prices, Decimal(0))
                    avg = s / Decimal(n)
                    outputs.append(_round4(avg))
                    continue
                if mode == "max":
                    m = max(prices)
                    outputs.append(_round4(m))
                    continue
                if mode == "volatility":
                    if n == 1:
                        outputs.append(_round4(Decimal(0)))
                        continue
                    s = sum(prices, Decimal(0))
                    mu = s / Decimal(n)
                    # compute population variance
                    var = sum((p - mu) ** 2 for p in prices) / Decimal(n)
                    # numerical stability: ensure non-negative small negatives clamp to zero
                    if var < Decimal('0'):
                        # clamp tiny negatives
                        if abs(var) < Decimal('1e-25'):
                            var = Decimal(0)
                        else:
                            # shouldn't happen; but guard
                            var = abs(var)
                    # sqrt using Decimal: use context sqrt if available
                    try:
                        sigma = var.sqrt()
                    except Exception:
                        # fallback via float but ensure non-negative
                        sigma = _dec(float(var) ** 0.5)
                    outputs.append(_round4(sigma))
                    continue
            # if broke due to error appended
            continue

        elif cmd == "snapshot":
            # ["snapshot", ticker]
            if len(op) != 2:
                outputs.append("Error: Invalid input.")
                continue
            ticker = op[1]
            if ticker not in state:
                outputs.append("Error: Invalid ticker.")
                continue
            length = state[ticker]['length']
            prices: List[Decimal] = []
            for d in range(length):
                audits_day = state[ticker]['audits'][d]
                val = None
                for a in reversed(audits_day):
                    if a['active']:
                        val = a['value']
                        break
                if val is None:
                    outputs.append("Error: Invalid ticker or day index.")
                    break
                prices.append(val)
            else:
                latest = prices[-1] if prices else Decimal(0)
                avg = (sum(prices, Decimal(0)) / Decimal(len(prices))) if prices else Decimal(0)
                outputs.append({"latest": _round4(latest), "average": _round4(avg)})
                continue
            continue

        else:
            outputs.append("Error: Invalid input.")
            continue

    return outputs