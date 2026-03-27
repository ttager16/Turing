# main.py
from typing import Any, Dict, List, Tuple


class TransactionCostContext:
    """Context for tracking transaction costs during optimization."""

    def __init__(self, cost_per_unit: float | None, budget: float | None):
        self.cost_per_unit = cost_per_unit
        self.budget = [budget] if budget is not None else None


class SegmentTree:
    """
    Array range sum segment tree for efficient range queries.

    This data structure allows for O(log n) point updates and range sum queries,
    which is used to efficiently track allocation changes during optimization.
    """

    def __init__(self, data: List[int]):
        """
        Initialize the segment tree with the given data.

        Args:
            data: List of integers to build the tree from
        """
        # Find the next power of 2 >= len(data) for tree size
        self.n = 1
        while self.n < len(data):
            self.n <<= 1

        # Initialize tree with 2*n nodes (internal + leaf nodes)
        self.tree = [0] * (2 * self.n)

        # Copy data to leaf nodes
        for i, v in enumerate(data):
            self.tree[self.n + i] = v

        # Build internal nodes bottom-up
        for i in range(self.n - 1, 0, -1):
            self.tree[i] = self.tree[i << 1] + self.tree[(i << 1) | 1]

    def update(self, idx: int, value: int) -> None:
        """
        Update element at index to new value.

        Args:
            idx: Index to update (0-based)
            value: New value to set
        """
        # Start from leaf node
        i = self.n + idx
        self.tree[i] = value

        # Propagate changes up to root
        i >>= 1
        while i:
            self.tree[i] = self.tree[i << 1] + self.tree[(i << 1) | 1]
            i >>= 1


def _compute_scores(stock_data: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Compute normalized attractiveness scores for each stock.

    The score is based on volatility (lower is better) with penalties for
    correlation with other stocks. Scores are normalized to sum to 1.0.

    Args:
        stock_data: List of stock dictionaries containing symbol, volatility, and correlations

    Returns:
        Dictionary mapping stock symbols to normalized attractiveness scores
    """
    scores: Dict[str, float] = {}

    for entry in stock_data:
        sym = str(entry.get("symbol", ""))
        vol = float(entry.get("volatility", 0.0))
        corr = entry.get("correlated_with", []) or []

        # Base score: lower volatility = higher attractiveness
        base = max(0.0, 1.0 - vol)

        # Penalty for being correlated with many other stocks
        penalty = 0.01 * len(corr)

        # Final score with penalty applied
        score = max(0.0, base - penalty)
        scores[sym] = score

    # Normalize scores to sum to 1.0
    total = sum(scores.values()) or 1.0
    for k in list(scores.keys()):
        scores[k] = scores[k] / total

    return scores


def _risk_of_allocation(symbols: List[str], vols: Dict[str, float], corr_map: Dict[str, List[str]], alloc: Dict[str, int]) -> float:
    """
    Compute aggregate portfolio risk from multiple sources.

    Risk components:
    1. Weighted volatility risk
    2. Correlation penalty for correlated pairs
    3. Concentration penalty (Herfindahl-Hirschman Index)
    4. Degree penalty for highly connected stocks

    Args:
        symbols: List of all stock symbols
        vols: Volatility values for each symbol
        corr_map: Correlation relationships between stocks
        alloc: Current allocation (number of units per stock)

    Returns:
        Total portfolio risk as a float
    """
    total_units = max(1, sum(alloc.values()))

    # 1. Weighted volatility risk
    w_risk = 0.0
    for s in symbols:
        weight = alloc.get(s, 0) / total_units
        w_risk += weight * vols.get(s, 0.0)

    # 2. Correlation penalty for pairs of correlated stocks
    pair_pen = 0.0
    for s in symbols:
        for t in corr_map.get(s, []):
            # Avoid double counting by only considering s < t
            if s < t:
                weight_s = alloc.get(s, 0) / total_units
                weight_t = alloc.get(t, 0) / total_units
                # Apply penalty only if both stocks are held
                if weight_s > 0 and weight_t > 0:
                    avg_vol = (vols.get(s, 0.0) + vols.get(t, 0.0)) * 0.5
                    pair_pen += 0.5 * min(weight_s, weight_t) * avg_vol * 0.5

    # 3. Concentration penalty using Herfindahl-Hirschman Index
    hhi = 0.0
    for s in symbols:
        weight = alloc.get(s, 0) / total_units
        hhi += weight * weight
    conc_pen = 0.005 * hhi

    # 4. Degree penalty for stocks with many correlations
    deg_pen = 0.0
    for s in symbols:
        weight = alloc.get(s, 0) / total_units
        degree = float(len(corr_map.get(s, [])))
        # Normalized degree penalty
        deg_pen += 0.002 * weight * (degree / (degree + 1.0))

    return w_risk + pair_pen + conc_pen + deg_pen


def _marginal_delta(scores: Dict[str, float], s: str, lamb: float, base_risk: float, new_risk: float) -> float:
    """
    Compute the marginal change in objective function for allocating to a stock.

    The objective function balances expected return (from scores) against risk increase.

    Args:
        scores: Attractiveness scores for each stock
        s: Stock symbol to evaluate
        lamb: Risk penalty coefficient (lambda)
        base_risk: Current portfolio risk
        new_risk: Portfolio risk after adding one unit of stock s

    Returns:
        Marginal change in objective value (higher is better)
    """
    return scores.get(s, 0.0) - lamb * max(0.0, new_risk - base_risk)

def _can_afford_transaction(cost: float, ctx: TransactionCostContext) -> bool:
    """
    Check if we can afford a transaction given the current budget.

    Args:
        cost: Transaction cost to check
        ctx: Transaction cost context

    Returns:
        True if transaction is affordable, False otherwise
    """
    if ctx.cost_per_unit is None or ctx.budget is None:
        return True
    return ctx.budget[0] >= cost


def _deduct_transaction_cost(cost: float, ctx: TransactionCostContext) -> None:
    """
    Deduct transaction cost from the budget.

    Args:
        cost: Transaction cost to deduct
        ctx: Transaction cost context
    """
    if ctx.cost_per_unit is not None and ctx.budget is not None:
        ctx.budget[0] -= cost


def _refund_transaction_cost(cost: float, ctx: TransactionCostContext) -> None:
    """
    Refund transaction cost to the budget (for failed allocations).

    Args:
        cost: Transaction cost to refund
        ctx: Transaction cost context
    """
    if ctx.cost_per_unit is not None and ctx.budget is not None:
        ctx.budget[0] += cost


def _initialize_portfolio_data(stock_data: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, float], Dict[str, List[str]], Dict[str, float]]:
    """
    Extract and organize stock data for portfolio optimization.

    Args:
        stock_data: Raw stock data from input

    Returns:
        Tuple of (symbols, volatilities, correlation_map, scores)
    """
    symbols = [str(e.get("symbol", "")) for e in stock_data]
    vols = {str(e.get("symbol", "")): float(e.get("volatility", 0.0)) for e in stock_data}
    corr_map = {str(e.get("symbol", "")): [str(x) for x in (e.get("correlated_with", []) or [])] for e in stock_data}
    scores = _compute_scores(stock_data)

    return symbols, vols, corr_map, scores


def _find_best_allocation_candidate(symbols: List[str], scores: Dict[str, float], vols: Dict[str, float],
                                    corr_map: Dict[str, List[str]], alloc: Dict[str, int],
                                    seg: SegmentTree, lamb: float) -> Tuple[str | None, float]:
    """
    Find the best stock to allocate to based on marginal utility.

    Args:
        symbols: List of stock symbols
        scores: Attractiveness scores
        vols: Volatility values
        corr_map: Correlation relationships
        alloc: Current allocation
        seg: Segment tree for tracking allocations
        lamb: Risk penalty coefficient

    Returns:
        Tuple of (best_symbol, best_delta)
    """
    best_sym = None
    best_delta = -1e18
    base_risk = _risk_of_allocation(symbols, vols, corr_map, alloc)

    for idx, s in enumerate(symbols):
        # Temporarily allocate one unit
        alloc[s] += 1
        seg.update(idx, alloc[s])

        # Calculate marginal benefit
        new_risk = _risk_of_allocation(symbols, vols, corr_map, alloc)
        delta = _marginal_delta(scores, s, lamb, base_risk, new_risk)

        # Revert temporary allocation
        alloc[s] -= 1
        seg.update(idx, alloc[s])

        if delta > best_delta:
            best_delta = delta
            best_sym = s

    return best_sym, best_delta


def _try_allocate_with_risk_constraint(symbols: List[str], best_sym: str, alloc: Dict[str, int],
                                       seg: SegmentTree, vols: Dict[str, float],
                                       corr_map: Dict[str, List[str]], risk_tolerance: float,
                                       ctx: TransactionCostContext) -> bool:
    """
    Try to allocate to the best symbol while respecting risk constraints.

    Args:
        symbols: List of stock symbols
        best_sym: Symbol to allocate to
        alloc: Current allocation
        seg: Segment tree for tracking
        vols: Volatility values
        corr_map: Correlation relationships
        risk_tolerance: Maximum allowed risk
        ctx: Transaction cost context

    Returns:
        True if allocation succeeded, False otherwise
    """
    if not _can_afford_transaction(ctx.cost_per_unit or 0.0, ctx):
        return False

    # Try direct allocation
    idx = symbols.index(best_sym)
    _deduct_transaction_cost(ctx.cost_per_unit or 0.0, ctx)
    alloc[best_sym] += 1
    seg.update(idx, alloc[best_sym])

    current_risk = _risk_of_allocation(symbols, vols, corr_map, alloc)

    if current_risk <= risk_tolerance:
        return True

    # Direct allocation violates risk constraint, try alternative allocations
    _refund_transaction_cost(ctx.cost_per_unit or 0.0, ctx)
    alloc[best_sym] -= 1
    seg.update(idx, alloc[best_sym])

    # Try allocating to other symbols instead
    for s2 in symbols:
        if s2 == best_sym:
            continue

        if not _can_afford_transaction(ctx.cost_per_unit or 0.0, ctx):
            continue

        id2 = symbols.index(s2)
        _deduct_transaction_cost(ctx.cost_per_unit or 0.0, ctx)
        alloc[s2] += 1
        seg.update(id2, alloc[s2])

        r2 = _risk_of_allocation(symbols, vols, corr_map, alloc)
        if r2 <= risk_tolerance:
            return True

        # This allocation also violates constraint, revert
        _refund_transaction_cost(ctx.cost_per_unit or 0.0, ctx)
        alloc[s2] -= 1
        seg.update(id2, alloc[s2])

    return False


def _post_optimization_cleanup(symbols: List[str], alloc: Dict[str, int], seg: SegmentTree,
                               vols: Dict[str, float], corr_map: Dict[str, List[str]],
                               risk_tolerance: float, history: List[Tuple[str, Dict[str, int]]],
                               ctx: TransactionCostContext) -> None:
    """
    Clean up allocation if final risk exceeds tolerance.

    Args:
        symbols: List of stock symbols
        alloc: Current allocation
        seg: Segment tree for tracking
        vols: Volatility values
        corr_map: Correlation relationships
        risk_tolerance: Maximum allowed risk
        history: Allocation history for rollback
        ctx: Transaction cost context
    """
    current_risk = _risk_of_allocation(symbols, vols, corr_map, alloc)
    if current_risk > risk_tolerance and history:
        last_sym, _ = history[-1]
        idx = symbols.index(last_sym)

        if alloc[last_sym] > 0:
            if _can_afford_transaction(ctx.cost_per_unit or 0.0, ctx):
                _deduct_transaction_cost(ctx.cost_per_unit or 0.0, ctx)
            alloc[last_sym] -= 1
            seg.update(idx, alloc[last_sym])


def _can_perform_rebalance_move(high_sym: str, low_sym: str, alloc: Dict[str, int],
                                ctx: TransactionCostContext) -> bool:
    """
    Check if a rebalance move between two symbols is possible.

    Args:
        high_sym: Symbol to move units to (high score)
        low_sym: Symbol to move units from (low score)
        alloc: Current allocation
        ctx: Transaction cost context

    Returns:
        True if the move is possible, False otherwise
    """
    # Can't move between same symbol or from empty allocation
    if high_sym == low_sym or alloc.get(low_sym, 0) == 0:
        return False

    # Check if we can afford the transaction costs (2 units: sell + buy)
    return _can_afford_transaction(2 * (ctx.cost_per_unit or 0.0), ctx)


def _execute_rebalance_move(symbols: List[str], high_sym: str, low_sym: str, alloc: Dict[str, int],
                            vols: Dict[str, float], corr_map: Dict[str, List[str]],
                            risk_tolerance: float, base_risk: float, ctx: TransactionCostContext) -> bool:
    """
    Execute a single rebalance move and check if it improves the portfolio.

    Args:
        symbols: List of stock symbols
        high_sym: Symbol to move units to
        low_sym: Symbol to move units from
        alloc: Current allocation
        vols: Volatility values
        corr_map: Correlation relationships
        risk_tolerance: Maximum allowed risk
        base_risk: Original portfolio risk
        ctx: Transaction cost context

    Returns:
        True if move was successful and kept, False if reverted
    """
    # Deduct transaction costs
    _deduct_transaction_cost(2 * (ctx.cost_per_unit or 0.0), ctx)

    # Execute the move
    alloc[low_sym] -= 1
    alloc[high_sym] += 1

    # Check if new allocation is acceptable
    new_risk = _risk_of_allocation(symbols, vols, corr_map, alloc)

    if new_risk <= max(risk_tolerance, base_risk):
        return True  # Keep the move
    else:
        # Revert the move
        alloc[low_sym] += 1
        alloc[high_sym] -= 1
        return False  # Move was reverted


def _rebalance(symbols: List[str], scores: Dict[str, float], corr_map: Dict[str, List[str]],
               vols: Dict[str, float], alloc: Dict[str, int], risk_tolerance: float,
               ctx: TransactionCostContext) -> None:
    """
    Perform single-pass rebalancing to improve portfolio composition.

    This function attempts to move units from low-scoring stocks to high-scoring stocks
    while maintaining risk constraints and respecting transaction costs.

    Args:
        symbols: List of stock symbols
        scores: Attractiveness scores for each stock
        corr_map: Correlation relationships between stocks
        vols: Volatility values for each stock
        alloc: Current allocation (modified in-place)
        risk_tolerance: Maximum allowed portfolio risk
        ctx: Transaction cost context
    """
    total_units = sum(alloc.values())
    if total_units == 0:
        return

    base_risk = _risk_of_allocation(symbols, vols, corr_map, alloc)

    # Sort symbols by score (high to low, low to high)
    sorted_syms = sorted(symbols, key=lambda x: scores.get(x, 0.0), reverse=True)
    low_syms = sorted(symbols, key=lambda x: scores.get(x, 0.0))

    moved = 0
    max_moves = max(1, total_units // 20)  # Limit moves to avoid excessive rebalancing
    i = j = 0

    while i < len(sorted_syms) and j < len(low_syms) and moved < max_moves:
        high_sym = sorted_syms[i]
        low_sym = low_syms[j]

        # Check if this move is possible
        if not _can_perform_rebalance_move(high_sym, low_sym, alloc, ctx):
            # Move to next symbol as appropriate
            if alloc.get(low_sym, 0) == 0:
                j += 1
            else:
                i += 1
            continue

        # Try to execute the move
        if _execute_rebalance_move(symbols, high_sym, low_sym, alloc, vols, corr_map,
                                   risk_tolerance, base_risk, ctx):
            moved += 1
        else:
            j += 1  # Current low symbol can't be moved from, try next


def _calculate_expected_return(symbols: List[str], scores: Dict[str, float], alloc: Dict[str, int]) -> float:
    """
    Calculate expected portfolio return based on allocation and scores.

    Args:
        symbols: List of stock symbols
        scores: Attractiveness scores for each stock
        alloc: Current allocation

    Returns:
        Expected portfolio return as a percentage
    """
    total_units = sum(alloc.values()) or 1
    expected_return = 0.0

    for s in symbols:
        weight = alloc.get(s, 0) / total_units
        expected_return += scores.get(s, 0.0) * weight

    # Scale by expected market return factor
    return expected_return * 0.15


def _run_main_allocation_loop(symbols: List[str], scores: Dict[str, float], vols: Dict[str, float],
                              corr_map: Dict[str, List[str]], alloc: Dict[str, int],
                              seg: SegmentTree, target_units: int, lamb: float,
                              risk_tolerance: float, ctx: TransactionCostContext) -> List[Tuple[str, Dict[str, int]]]:
    """
    Run the main allocation loop to build the portfolio.

    Args:
        symbols: List of stock symbols
        scores: Attractiveness scores
        vols: Volatility values
        corr_map: Correlation relationships
        alloc: Current allocation (modified in-place)
        seg: Segment tree for tracking
        target_units: Target number of units to allocate
        lamb: Risk penalty coefficient
        risk_tolerance: Maximum allowed risk
        ctx: Transaction cost context

    Returns:
        History of allocation decisions
    """
    history: List[Tuple[str, Dict[str, int]]] = []

    for step in range(target_units):
        # Find the best stock to allocate to
        best_sym, best_delta = _find_best_allocation_candidate(
            symbols, scores, vols, corr_map, alloc, seg, lamb
        )

        if best_sym is None:
            break

        # Try to allocate while respecting risk constraints
        if _try_allocate_with_risk_constraint(
            symbols, best_sym, alloc, seg, vols, corr_map, risk_tolerance, ctx
        ):
            history.append((best_sym, alloc.copy()))

    return history


def optimize_portfolio(stock_data: List[Dict[str, Any]], risk_tolerance: float,
                       transaction_cost_per_unit: float | None = None,
                       transaction_cost_budget: float | None = None) -> Dict[str, Any]:
    """
    Optimize portfolio allocations under risk and transaction cost constraints.

    This function implements a sophisticated portfolio optimization algorithm that:
    1. Computes attractiveness scores for each stock based on volatility and correlations
    2. Iteratively allocates units to maximize risk-adjusted returns
    3. Respects transaction costs and risk tolerance constraints
    4. Performs post-optimization rebalancing for improved composition

    Args:
        stock_data: List of dictionaries containing stock information:
                   - symbol: Stock ticker symbol
                   - price: Current stock price
                   - volatility: Historical volatility (0-1 scale)
                   - correlated_with: List of correlated stock symbols
        risk_tolerance: Maximum acceptable portfolio risk level
        transaction_cost_per_unit: Cost per transaction (optional, defaults to None for no cost)
        transaction_cost_budget: Total budget for transaction costs (optional, defaults to None for unlimited)

    Returns:
        Dictionary containing:
        - portfolio: Allocation of units per stock symbol
        - expected_return: Expected portfolio return (percentage)
        - risk: Calculated portfolio risk level
    """
    # Input validation
    if not isinstance(stock_data, list) or not stock_data:
        return {"portfolio": {}, "expected_return": 0.0, "risk": 0.0}

    # Initialize transaction cost context
    ctx = TransactionCostContext(transaction_cost_per_unit, transaction_cost_budget)

    # Initialize portfolio data structures
    symbols, vols, corr_map, scores = _initialize_portfolio_data(stock_data)

    # Initialize allocation tracking
    alloc: Dict[str, int] = {s: 0 for s in symbols}
    arr = [0] * len(symbols)
    seg = SegmentTree(arr)

    # Optimization parameters
    target_units = 100
    lamb = 0.5  # Risk penalty coefficient

    # Run main allocation loop
    history = _run_main_allocation_loop(
        symbols, scores, vols, corr_map, alloc, seg, target_units, lamb, risk_tolerance, ctx
    )

    # Post-optimization cleanup if risk constraint violated
    _post_optimization_cleanup(symbols, alloc, seg, vols, corr_map, risk_tolerance, history, ctx)

    # Perform rebalancing to improve composition
    _rebalance(symbols, scores, corr_map, vols, alloc, risk_tolerance, ctx)

    # Calculate final metrics
    expected_return = _calculate_expected_return(symbols, scores, alloc)
    risk_val = _risk_of_allocation(symbols, vols, corr_map, alloc)

    return {
        "portfolio": alloc,
        "expected_return": round(expected_return, 6),
        "risk": round(risk_val, 6)
    }


# Example usage
if __name__ == "__main__":
    stock_data = [
        {"symbol": "AAPL", "price": 150.0, "volatility": 0.04, "correlated_with": ["GOOGL"]},
        {"symbol": "GOOGL", "price": 2800.0, "volatility": 0.02, "correlated_with": ["AAPL", "MSFT"]},
        {"symbol": "MSFT", "price": 300.0, "volatility": 0.05, "correlated_with": []},
        {"symbol": "TSLA", "price": 800.0, "volatility": 0.07, "correlated_with": ["AAPL"]},
        {"symbol": "AMZN", "price": 3500.0, "volatility": 0.03, "correlated_with": ["MSFT", "GOOGL"]},
    ]
    risk_tolerance = 0.028
    transaction_cost_per_unit = 1.0
    transaction_cost_budget = 50.0
    result = optimize_portfolio(stock_data, risk_tolerance, transaction_cost_per_unit, transaction_cost_budget)
    print(result)