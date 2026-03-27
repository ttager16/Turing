# main.py
import math
from collections import defaultdict
from typing import Any, Dict, List


class CorrelatedAssetSimulator:
    """
    Main simulator class that integrates all components for correlated asset trading.
    """

    def __init__(
        self,
        initial_prices: Dict[str, float],
        correlation_graph: Dict[str, List[List]],
        time_steps: int,
        capital_limit: float,
        transaction_cost_factor: float,
        seed: int = 42
    ):
        # Deterministic seed for price simulation
        self.seed = seed

        self.initial_prices = initial_prices
        self.correlation_graph = correlation_graph
        self.time_steps = time_steps
        self.capital_limit = capital_limit
        self.transaction_cost_factor = transaction_cost_factor

        # Sort assets for deterministic ordering
        self.assets = sorted(initial_prices.keys())
        self.asset_to_idx = {asset: idx for idx, asset in enumerate(self.assets)}

        # Initialize data structures
        self.memo = {}

        # Path tracking
        self.explored_paths = []

    def simulate_price_path(self, current_prices: Dict[str, float], time_step: int) -> Dict[str, float]:
        """
        Simulate next price state based on correlations using deterministic GBM.
        """
        new_prices = {}

        for asset_idx, asset in enumerate(self.assets):
            # Base drift and volatility
            drift = 0.0001  # Small positive drift
            volatility = 0.02

            # Correlation-based adjustment
            correlation_adjustment = 0.0
            if asset in self.correlation_graph:
                for correlated_asset, correlation in self.correlation_graph[asset]:
                    if correlated_asset in current_prices:
                        # Price change of correlated asset affects this asset
                        price_change_ratio = (
                            current_prices[correlated_asset] / self.initial_prices[correlated_asset]
                        ) - 1.0
                        correlation_adjustment += correlation * price_change_ratio * 0.1

            # Generate deterministic shock using mathematical formula
            # Based on time_step, asset_idx, and seed for full determinism
            deterministic_value = math.sin(self.seed * 0.1 + time_step * 2.5 + asset_idx * 3.7) * math.cos(time_step * 1.3 + asset_idx * 2.1)
            # Scale to approximate standard normal distribution (mean 0, std 1)
            z = deterministic_value * 1.5

            # GBM formula
            dt = 1.0  # Time step unit
            adjusted_drift = drift + correlation_adjustment
            price_multiplier = math.exp((adjusted_drift - 0.5 * volatility ** 2) * dt + volatility * math.sqrt(dt) * z)

            new_prices[asset] = max(current_prices[asset] * price_multiplier, 0.01)  # Prevent negative prices

        return new_prices

    def backtrack_trades(
        self,
        time_step: int,
        current_prices: Dict[str, float],
        current_positions: Dict[str, float],
        current_capital: float,
        current_trades: List[List[List]],
        current_cost: float
    ) -> None:
        """
        Recursive backtracking to explore different trade sequences with memoization.
        """

        # Base case: reached final time step
        if time_step >= self.time_steps:
            # Calculate final portfolio value
            final_value = current_capital
            for asset, position in current_positions.items():
                final_value += position * current_prices[asset]

            # Create state key for memoization
            state_key = (
                time_step,
                tuple(sorted((a, round(p, 1)) for a, p in current_positions.items())),
                round(current_capital, 0)
            )

            # Only store if this is a better result for this state
            if state_key not in self.memo or self.memo[state_key]['value'] < final_value:
                self.memo[state_key] = {
                    'value': final_value,
                    'trades': [t[:] for t in current_trades],
                    'cost': current_cost
                }

            return

        # Simulate price evolution
        next_prices = self.simulate_price_path(current_prices, time_step)

        # Generate deterministic trade options (limited branching)
        trade_options = self._generate_trade_options(current_prices, current_positions, current_capital, time_step)

        # Explore each trade option
        for trades in trade_options:
            new_positions = current_positions.copy()
            new_capital = current_capital
            trade_cost = 0.0

            valid_trades = True
            for asset, quantity in trades:
                if quantity > 0:  # Buy
                    base_cost = quantity * current_prices[asset]
                    transaction_fee = base_cost * self.transaction_cost_factor
                    cost = base_cost + transaction_fee
                    if cost <= new_capital:
                        new_positions[asset] = new_positions.get(asset, 0.0) + quantity
                        new_capital -= cost
                        trade_cost += transaction_fee
                    else:
                        valid_trades = False
                        break
                elif quantity < 0:  # Sell
                    if new_positions.get(asset, 0.0) >= abs(quantity):
                        base_proceeds = abs(quantity) * current_prices[asset]
                        transaction_fee = base_proceeds * self.transaction_cost_factor
                        proceeds = base_proceeds - transaction_fee
                        new_positions[asset] = new_positions.get(asset, 0.0) + quantity
                        new_capital += proceeds
                        trade_cost += transaction_fee
                    else:
                        valid_trades = False
                        break

            if valid_trades:
                new_trades = [t[:] for t in current_trades]
                new_trades.append(trades)

                # Recursive call
                self.backtrack_trades(
                    time_step + 1,
                    next_prices,
                    new_positions,
                    new_capital,
                    new_trades,
                    current_cost + trade_cost
                )

    def _generate_trade_options(
        self,
        current_prices: Dict[str, float],
        current_positions: Dict[str, float],
        current_capital: float,
        time_step: int
    ) -> List[List[List]]:
        """
        Generate a deterministic set of trade options based on correlations and prices.
        """
        options = []

        # Option 1: No trade
        options.append([])

        # Limit options based on time step to reduce branching
        if time_step >= self.time_steps - 2:
            # Near end, focus on liquidation or simple holds
            return options

        # Option 2: Buy undervalued correlated assets (only first asset to limit branching)
        added_buy = False
        for asset in self.assets:
            if added_buy:
                break
            if asset in self.correlation_graph and len(self.correlation_graph[asset]) > 0:
                avg_correlation = sum(corr for _, corr in self.correlation_graph[asset]) / len(self.correlation_graph[asset])
                if avg_correlation > 0.5:
                    max_buy = min(10.0, current_capital / (current_prices[asset] * 2))
                    if max_buy > 0.1:
                        options.append([[asset, round(max_buy, 2)]])
                        added_buy = True

        # Option 3: Rebalance portfolio (only if we have positions)
        if current_positions and time_step < self.time_steps // 2:
            rebalance_trades = []
            for asset in self.assets[:2]:  # Limit to first 2 assets
                current_pos = current_positions.get(asset, 0.0)
                target_pos = 5.0  # Target position
                diff = target_pos - current_pos
                if abs(diff) > 0.1:
                    rebalance_trades.append([asset, round(diff, 2)])
            if rebalance_trades:
                options.append(rebalance_trades[:2])  # Limit trades

        # Option 4: Correlation-based pairs trade (only one pair)
        if time_step < self.time_steps // 3:
            for i, asset_i in enumerate(self.assets):
                if asset_i in self.correlation_graph:
                    for asset_j, correlation in self.correlation_graph[asset_i]:
                        if correlation > 0.7 and asset_j in self.assets:
                            # High correlation: pairs trade
                            trade_size = 5.0
                            options.append([
                                [asset_i, trade_size],
                                [asset_j, trade_size]
                            ])
                            break
                    break  # Only first pair

        return options[:5]  # Strict limit on total options

    def run_simulation(self) -> List[Dict[str, Any]]:
        """
        Execute the full simulation and return optimal trading strategies.
        """
        # Initialize positions
        initial_positions = {asset: 0.0 for asset in self.assets}
        initial_capital = self.capital_limit

        # Run backtracking exploration
        self.backtrack_trades(
            time_step=0,
            current_prices=self.initial_prices.copy(),
            current_positions=initial_positions,
            current_capital=initial_capital,
            current_trades=[],
            current_cost=0.0
        )

        # Extract top paths from memoization
        results = []
        sorted_states = sorted(
            self.memo.items(),
            key=lambda x: x[1]['value'],
            reverse=True
        )[:10]  # Top 10 paths

        for path_id, (state, data) in enumerate(sorted_states):
            # Calculate total transaction costs
            flow_cost = data['cost']

            # Generate explanation
            explanation = self._generate_explanation(data['trades'], data['value'])

            results.append({
                'path_id': path_id,
                'trades': data['trades'],
                'flow_cost': round(flow_cost, 2),
                'final_portfolio_value': round(data['value'], 2),
                'optimal_strategy_explanation': explanation
            })

        return results

    def _generate_explanation(self, trades: List[List[List]], final_value: float) -> str:
        """
        Generate a detailed explanation of the trading strategy.
        """
        if not trades or all(len(t) == 0 for t in trades):
            return "Hold strategy: No trades executed. Market conditions did not favor active trading."

        total_trades = sum(len(t) for t in trades)
        active_steps = sum(1 for t in trades if len(t) > 0)

        # Analyze which assets were most traded
        asset_activity = defaultdict(int)
        for time_trades in trades:
            for asset, quantity in time_trades:
                asset_activity[asset] += 1

        most_active = sorted(asset_activity.items(), key=lambda x: x[1], reverse=True)[:2]

        explanation = (
            f"Active trading strategy with {total_trades} total trades across {active_steps} time steps. "
        )

        if most_active:
            explanation += f"Focused on {most_active[0][0]} "
            if len(most_active) > 1:
                explanation += f"and {most_active[1][0]} "
            explanation += "based on correlation dynamics. "

        explanation += (
            f"Strategy exploited correlation structure to maximize returns while respecting "
            f"capital constraints and transaction costs. Final portfolio value: ${final_value:,.2f}."
        )

        return explanation


def simulate_correlated_trades(
    initial_asset_prices: Dict[str, float],
    correlation_graph: Dict[str, List[List]],
    time_steps: int,
    capital_limit: float,
    transaction_cost_factor: float,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Multi-layer recursive simulator integrating advanced data structures
    and DP-based backtracking to identify optimal cross-asset trading strategies.

    Args:
        initial_asset_prices: Dictionary mapping asset names to initial prices
        correlation_graph: Graph structure defining correlations between assets
        time_steps: Number of discrete time intervals to simulate
        capital_limit: Maximum capital available for trading
        transaction_cost_factor: Proportional transaction cost (e.g., 0.001 = 0.1%)
        seed: Random seed for deterministic simulations

    Returns:
        List of dictionaries containing optimal trading paths with detailed metrics
    """
    # Input validation
    if not initial_asset_prices:
        return []

    if time_steps <= 0:
        return [{
            'path_id': 0,
            'trades': [],
            'flow_cost': 0.0,
            'final_portfolio_value': capital_limit,
            'optimal_strategy_explanation': 'No time steps to simulate.'
        }]

    if capital_limit <= 0:
        return [{
            'path_id': 0,
            'trades': [[] for _ in range(time_steps)],
            'flow_cost': 0.0,
            'final_portfolio_value': 0.0,
            'optimal_strategy_explanation': 'No capital available for trading.'
        }]

    # Validate prices
    for asset, price in initial_asset_prices.items():
        if price <= 0:
            raise ValueError(f"Invalid price for {asset}: {price}")

    # Create simulator instance
    simulator = CorrelatedAssetSimulator(
        initial_prices=initial_asset_prices,
        correlation_graph=correlation_graph,
        time_steps=time_steps,
        capital_limit=capital_limit,
        transaction_cost_factor=transaction_cost_factor,
        seed=seed
    )

    # Run simulation
    results = simulator.run_simulation()

    # Ensure we always return at least one result
    if not results:
        results = [{
            'path_id': 0,
            'trades': [[] for _ in range(time_steps)],
            'flow_cost': 0.0,
            'final_portfolio_value': capital_limit,
            'optimal_strategy_explanation': 'No profitable trading opportunities found.'
        }]

    return results


# Example usage
if __name__ == "__main__":
    # Sample arguments
    initial_asset_prices = {
        'AssetA': 100.0,
        'AssetB': 150.0,
        'AssetC': 200.0
    }

    correlation_graph = {
        'AssetA': [['AssetB', 0.8], ['AssetC', 0.5]],
        'AssetB': [['AssetA', 0.8], ['AssetC', 0.3]],
        'AssetC': [['AssetA', 0.5], ['AssetB', 0.3]]
    }
    time_steps = 5
    capital_limit = 10000.0
    transaction_cost_factor = 0.001
    seed = 42

    # Call the function
    results = simulate_correlated_trades(
        initial_asset_prices=initial_asset_prices,
        correlation_graph=correlation_graph,
        time_steps=time_steps,
        capital_limit=capital_limit,
        transaction_cost_factor=transaction_cost_factor,
        seed=seed
    )

    # Display results
    print(results)