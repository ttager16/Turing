def simulate_correlated_trades(
    initial_asset_prices: Dict[str, float],
    correlation_graph: Dict[str, List[List]],
    time_steps: int,
    capital_limit: float,
    transaction_cost_factor: float,
    seed: int = 42
) -> List[Dict[str, Any]]:

    # Edge cases
    if not initial_asset_prices:
        return []
    if any(v <= 0 for v in initial_asset_prices.values()):
        raise ValueError("Initial asset prices must be > 0")
    if time_steps <= 0:
        return [{
            'path_id': 0,
            'trades': [],
            'flow_cost': round(0.0, 2),
            'final_portfolio_value': round(capital_limit, 2),
            'optimal_strategy_explanation': "No time steps to simulate."
        }]
    if capital_limit <= 0:
        return [{
            'path_id': 0,
            'trades': [[] for _ in range(time_steps)],
            'flow_cost': 0.0,
            'final_portfolio_value': 0.0,
            'optimal_strategy_explanation': "No capital available for trading."
        }]

    # Store seed as instance-like variable
    _seed = seed

    assets = sorted(initial_asset_prices.keys())
    n_assets = len(assets)
    drift_base = 0.0001
    vol = 0.02
    dt = 1.0

    # Precompute deterministic shocks z for each time and asset index
    def deterministic_z(t: int, asset_idx: int) -> float:
        deterministic_value = math.sin(_seed * 0.1 + t * 2.5 + asset_idx * 3.7) * math.cos(t * 1.3 + asset_idx * 2.1)
        return deterministic_value * 1.5

    # Simulate prices forward given current prices and time step
    def simulate_step(curr_prices: Dict[str, float], t: int, initial_prices: Dict[str, float]) -> Dict[str, float]:
        new_prices = curr_prices.copy()
        for idx, asset in enumerate(assets):
            price_old = new_prices[asset]
            price_change_ratio = (price_old / initial_prices[asset] - 1.0)
            # compute avg correlation drift adjustment
            corr_list = correlation_graph.get(asset, [])
            adj = 0.0
            for pair in corr_list:
                # pair is [asset_name, correlation_value]
                corr = pair[1] if len(pair) > 1 else 0.0
                adj += corr * price_change_ratio * 0.1
            drift = drift_base + adj
            z = deterministic_z(t, idx)
            price_new = price_old * math.exp((drift - 0.5 * vol * vol) * dt + vol * math.sqrt(dt) * z)
            price_new = max(price_new, 0.01)
            new_prices[asset] = price_new
        return new_prices

    # Memoization dict
    memo: Dict[Tuple[int, Tuple[Tuple[str, float], ...], float], Dict[str, Any]] = {}

    # Helper to round positions for key
    def positions_key(positions: Dict[str, float]) -> Tuple[Tuple[str, float], ...]:
        # rounded to 1dp per constraint
        return tuple(sorted([(a, round(positions.get(a, 0.0), 1)) for a in assets]))

    # Generate trade options per rules
    def gen_trade_options(t: int, prices: Dict[str, float], positions: Dict[str, float], capital: float) -> List[List[List[Any]]]:
        options: List[List[List[Any]]] = []
        # empty option always first
        options.append([])
        # Late-stage behavior
        if t >= time_steps - 2:
            return options[:1]
        # iterate assets sorted
        # Buy options based on avg correlation >0.5
        for asset in assets:
            corr_list = correlation_graph.get(asset, [])
            if corr_list:
                avg_corr = sum(pair[1] for pair in corr_list) / len(corr_list)
            else:
                avg_corr = 0.0
            price = prices[asset]
            if avg_corr > 0.5:
                max_buy = min(10.0, capital / (price * 2))  # as specified
                if max_buy > 0.1:
                    qty = round(max_buy, 2)
                    options.append([[asset, qty]])
                    if len(options) >= 5:
                        return options[:5]
        # Rebalance logic
        if t < time_steps // 2 and any(abs(v) > 0.0 for v in positions.values()):
            target_list = assets[:2]
            trades = []
            for a in target_list:
                current = positions.get(a, 0.0)
                diff = round(5.0 - current, 2)
                if abs(diff) > 0.1:
                    trades.append([a, diff])
            if trades:
                options.append(trades)
                if len(options) >= 5:
                    return options[:5]
        # Pairs trading
        if t < time_steps // 3:
            found = False
            for a in assets:
                for pair in correlation_graph.get(a, []):
                    other = pair[0]
                    corr = pair[1]
                    if corr > 0.7 and other in assets:
                        # trade size 5.0: buy first, sell second
                        options.append([[a, 5.0], [other, -5.0]])
                        found = True
                        break
                if found:
                    break
            if len(options) >= 5:
                return options[:5]
        # Limit total options to 5
        return options[:5]

    # Execute trades producing new positions, capital, and flow cost increment
    def execute_trades(trades: List[List[Any]], prices: Dict[str, float], positions: Dict[str, float], capital: float, flow_cost: float) -> Tuple[Dict[str, float], float, float]:
        pos = positions.copy()
        cap = capital
        fc = flow_cost
        for tr in trades:
            asset, qty = tr[0], tr[1]
            qty = round(qty, 2)
            price = prices[asset]
            if qty > 0:
                cost = qty * price * (1 + transaction_cost_factor)
                if cost <= cap + 1e-9:
                    cap -= cost
                    pos[asset] = round(pos.get(asset, 0.0) + qty, 10)
                    # track flow_cost add cost*factor per constraint: "add cost*factor for buys"
                    fc += cost * transaction_cost_factor
                else:
                    # invalid buy, skip
                    pass
            elif qty < 0:
                sell_qty = abs(qty)
                if pos.get(asset, 0.0) + 1e-9 >= sell_qty:
                    proceeds = sell_qty * price * (1 - transaction_cost_factor)
                    cap += proceeds
                    pos[asset] = round(pos.get(asset, 0.0) - sell_qty, 10)
                    # track flow_cost add abs(proceeds)*factor for sells
                    fc += abs(proceeds) * transaction_cost_factor
                else:
                    # invalid sell, skip
                    pass
        return pos, cap, fc

    results: List[Dict[str, Any]] = []

    # Recursive search
    def dfs(t: int, prices: Dict[str, float], positions: Dict[str, float], capital: float, flow_cost: float, trades_so_far: List[List[List[Any]]]):
        # Memo key
        key = (t, positions_key(positions), round(capital, 0))
        # If memoized and existing final_value >= potential best, skip storing until end
        if key in memo:
            # we still continue because we might find better path; but per constraint, store if better
            pass

        if t >= time_steps:
            # final valuation
            final_val = capital + sum(positions.get(a, 0.0) * prices[a] for a in assets)
            final_val_rounded = round(final_val, 10)
            state = {
                'trades': [list(map(list, step)) for step in trades_so_far],
                'flow_cost': flow_cost,
                'final_portfolio_value': final_val_rounded
            }
            prev = memo.get((t, positions_key(positions), round(capital, 0)))
            # store in memo per rule 14 using key with current t
            end_key = (t, positions_key(positions), round(capital, 0))
            if end_key not in memo or memo[end_key]['final_portfolio_value'] < final_val_rounded:
                memo[end_key] = state
            results.append(state)
            return

        # generate trade options
        options = gen_trade_options(t, prices, positions, capital)
        for opt in options:
            # apply trades (validate inside)
            new_positions, new_capital, new_flow = execute_trades(opt, prices, positions, capital, flow_cost)
            # advance prices
            next_prices = simulate_step(prices, t, initial_asset_prices)
            # append trades for this timestep (ensure rounding quantities 2dp)
            trades_entry = []
            for it in opt:
                trades_entry.append([it[0], round(it[1], 2)])
            trades_so_far.append(trades_entry)
            dfs(t + 1, next_prices, new_positions, new_capital, new_flow, trades_so_far)
            trades_so_far.pop()

    # initial state
    init_positions = {a: 0.0 for a in assets}
    init_prices = initial_asset_prices.copy()
    dfs(0, init_prices, init_positions, capital_limit, 0.0, [])

    # If no results
    if not results:
        return [{
            'path_id': 0,
            'trades': [[] for _ in range(time_steps)],
            'flow_cost': round(0.0, 2),
            'final_portfolio_value': round(capital_limit, 2),
            'optimal_strategy_explanation': "No profitable trading opportunities found."
        }]

    # Prepare final outputs: round values, build explanations
    # Sort by final_portfolio_value desc
    results_sorted = sorted(results, key=lambda x: x['final_portfolio_value'], reverse=True)

    final_list: List[Dict[str, Any]] = []
    for idx, res in enumerate(results_sorted[:1000]):  # guard
        trades = res['trades']
        # Ensure trades length == time_steps
        if len(trades) < time_steps:
            trades = trades + [[] for _ in range(time_steps - len(trades))]
        else:
            trades = trades[:time_steps]
        flow_cost = round(res['flow_cost'], 2)
        final_val = round(res['final_portfolio_value'], 2)
        # Explanation generation
        if not trades or all(len(t) == 0 for t in trades):
            explanation = "Hold strategy: No trades executed. Market conditions did not favor active trading."
        else:
            total_trades = sum(len(t) for t in trades)
            active_steps = sum(1 for t in trades if len(t) > 0)
            # count asset occurrences
            freq = defaultdict(int)
            for step in trades:
                for tr in step:
                    freq[tr[0]] += 1
            freq_items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
            most_active = freq_items[:2]
            expl = f"Active trading strategy with {total_trades} total trades across {active_steps} time steps. "
            if most_active:
                expl += f"Focused on {most_active[0][0]} "
                if len(most_active) > 1:
                    expl += f"and {most_active[1][0]} "
                expl += "based on correlation dynamics. "
            expl += "Strategy exploited correlation structure to maximize returns while respecting capital constraints and transaction costs. Final portfolio value: ${:,.2f}.".format(final_val)
            explanation = expl
        final_list.append({
            'path_id': idx,  # will reassign later but already sorted
            'trades': trades,
            'flow_cost': flow_cost,
            'final_portfolio_value': final_val,
            'optimal_strategy_explanation': explanation
        })
        if len(final_list) >= 10:
            break

    if not final_list:
        return [{
            'path_id': 0,
            'trades': [[] for _ in range(time_steps)],
            'flow_cost': round(0.0, 2),
            'final_portfolio_value': round(capital_limit, 2),
            'optimal_strategy_explanation': "No profitable trading opportunities found."
        }]

    # Assign path_ids sequentially starting from 0 based on sorted order (already)
    for i, item in enumerate(final_list):
        item['path_id'] = i

    return final_list