from typing import Dict, List, Tuple, Any, Optional, FrozenSet
from collections import defaultdict
import math
import json


def convert_correlation_matrix(
    correlation_list: List[Dict[str, Any]],
) -> Dict[Tuple[str, str], float]:
    """Convert correlation matrix from list format to dict format"""
    correlation_dict = {}
    for item in correlation_list:
        pair = item["asset_pair"]
        correlation = item["correlation"]
        asset1, asset2 = pair[0], pair[1]
        key = tuple(sorted([asset1, asset2]))
        correlation_dict[key] = correlation
    return correlation_dict


class OptimizerState:
    """Encapsulates all state variables for the trading strategy optimizer"""

    def __init__(self):
        self.memo_cache = {}
        self.memo_hits = 0
        self.memo_misses = 0
        self.collision_count = 0
        self.prune_operations = 0
        self.backtrack_count = 0
        self.computation_budget = 0
        self.MAX_COMPUTATION_BUDGET = 10000


def optimize_trading_strategy(
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: List[Dict[str, Any]],
    portfolio_constraints: Dict[str, float],
) -> Dict[str, Any]:
    # Convert correlation matrix to the right format
    correlation_dict = convert_correlation_matrix(correlation_matrix)

    # Create fresh state for this optimization run
    state = OptimizerState()

    if not asset_data:
        return {"error": "No assets provided"}

    min_liquidity = portfolio_constraints.get("min_liquidity", 0)
    max_position_size = portfolio_constraints.get("max_position_size", 1.0)
    max_sector_concentration = portfolio_constraints.get(
        "max_sector_concentration", 1.0
    )
    total_capital = portfolio_constraints.get("total_capital", 0)
    max_portfolio_volatility = portfolio_constraints.get(
        "max_portfolio_volatility", float("inf")
    )

    valid_assets = []
    for asset_id, data in asset_data.items():
        if data.get("liquidity_score", 0) >= min_liquidity:
            valid_assets.append(asset_id)

    if not valid_assets:
        return {"error": "All assets below minimum liquidity threshold"}

    if total_capital <= 0:
        return {"error": "Insufficient capital"}

    segments = partition_by_correlation_union_find(valid_assets, correlation_dict)

    sector_groups = defaultdict(list)
    for asset_id in valid_assets:
        sector = asset_data[asset_id].get("sector", "unknown")
        sector_groups[sector].append(asset_id)

    for sector, assets in sector_groups.items():
        min_sector_weight = len(assets) * (1.0 / len(valid_assets))
        if min_sector_weight > max_sector_concentration * 1.5:
            if len(assets) > 1:
                total_corr = 0
                count = 0
                for i in range(len(assets)):
                    for j in range(i + 1, len(assets)):
                        pair = tuple(sorted([assets[i], assets[j]]))
                        corr = correlation_dict.get(pair, 0)
                        total_corr += corr
                        count += 1
                avg_corr = total_corr / count if count > 0 else 0
                if avg_corr > 0.85:
                    return {"error": "Unsolvable sector concentration constraints"}

    segment_strategies = []
    max_depth_reached = 0
    final_decision_path = []

    for segment in segments:
        segment_assets = [a for a in segment if a in valid_assets]
        if not segment_assets:
            continue

        best_strategy = None
        best_sharpe = float("-inf")
        best_depth = 0

        theoretical_max_sharpe = calculate_theoretical_max_sharpe(
            segment_assets, asset_data
        )

        best_segment_path = []
        for max_depth in [2, 4, 6, 8]:
            strategy, sharpe, depth, path = recursive_strategy_search_advanced(
                state,
                segment_assets,
                asset_data,
                correlation_dict,
                portfolio_constraints,
                depth=0,
                max_depth=max_depth,
                alpha=float("-inf"),
                beta=theoretical_max_sharpe,
            )

            if strategy and sharpe > best_sharpe:
                best_strategy = strategy
                best_sharpe = sharpe
                best_depth = depth
                best_segment_path = path

            if strategy and sharpe > best_sharpe * 1.05:
                break

        max_depth_reached = max(max_depth_reached, best_depth)

        if best_strategy:
            segment_strategies.append((best_strategy, best_sharpe, best_segment_path))
            # Aggregate decision paths from all segments
            final_decision_path.extend(best_segment_path)

    if len(segment_strategies) > 1:
        best_strategy = {}
        total_weight = sum(sharpe for _, sharpe, _ in segment_strategies if sharpe > 0)
        if total_weight > 0:
            for strategy, sharpe, path in segment_strategies:
                if sharpe > 0:
                    weight = sharpe / total_weight
                    for asset_id, allocation in strategy.items():
                        best_strategy[asset_id] = allocation * weight
        else:
            best_strategy = segment_strategies[0][0] if segment_strategies else None
            # final_decision_path already populated from extend() above
    elif segment_strategies:
        best_strategy = segment_strategies[0][0]
        # final_decision_path already populated from extend() above
    else:
        best_strategy = None
        # final_decision_path remains empty list

    if not best_strategy:
        return {"error": "No valid strategy found within depth limit"}

    arbitrage_opportunities = detect_arbitrage_advanced(
        best_strategy, asset_data, correlation_dict
    )
    resolved_conflicts = resolve_cross_segment_conflicts(
        best_strategy, asset_data, correlation_dict, segments
    )

    rebalancing_iterations = 0
    max_rebalancing_iterations = 15
    iteration_history = []
    max_violation = float("inf")

    for iteration in range(max_rebalancing_iterations):
        rebalancing_iterations = iteration + 1
        normalized_strategy = {}
        for asset_id, allocation in best_strategy.items():
            if allocation > 0:
                normalized_strategy[asset_id] = allocation

        total = sum(normalized_strategy.values())
        if total > 0:
            for asset_id in normalized_strategy:
                normalized_strategy[asset_id] /= total

        violations = []

        for asset_id in list(normalized_strategy.keys()):
            if normalized_strategy[asset_id] > max_position_size:
                violations.append(
                    (
                        "position",
                        asset_id,
                        normalized_strategy[asset_id] - max_position_size,
                    )
                )
                normalized_strategy[asset_id] = max_position_size

        sector_allocation = defaultdict(float)
        for asset_id, allocation in normalized_strategy.items():
            sector = asset_data[asset_id].get("sector", "unknown")
            sector_allocation[sector] += allocation

        for sector, alloc in sector_allocation.items():
            if alloc > max_sector_concentration:
                violations.append(("sector", sector, alloc - max_sector_concentration))
                scale_factor = max_sector_concentration / alloc
                for asset_id in normalized_strategy:
                    if asset_data[asset_id].get("sector") == sector:
                        normalized_strategy[asset_id] *= scale_factor

        portfolio_vol = calculate_portfolio_volatility(
            normalized_strategy, asset_data, correlation_dict
        )
        if portfolio_vol > max_portfolio_volatility:
            violations.append(
                ("volatility", "portfolio", portfolio_vol - max_portfolio_volatility)
            )
            for asset_id in normalized_strategy:
                normalized_strategy[asset_id] *= 0.95

        max_violation = max([v[2] for v in violations], default=0.0)
        iteration_history.append(max_violation)

        if max_violation < 0.001:
            best_strategy = normalized_strategy
            break
        else:
            best_strategy = normalized_strategy

    converged = max_violation < 0.001
    convergence_metrics = {
        "final_violation": max_violation,
        "iterations": rebalancing_iterations,
        "converged": converged,
        "iteration_history": iteration_history,
    }

    trades = []
    expected_return = 0
    portfolio_variance = 0

    for asset_id, allocation in best_strategy.items():
        if allocation > 0:
            current_price = asset_data[asset_id].get("current_price", 0)
            prices = asset_data[asset_id].get("prices", [current_price])

            if len(prices) >= 2:
                returns = [
                    (prices[i] - prices[i - 1]) / prices[i - 1]
                    for i in range(1, len(prices))
                ]
                avg_return = sum(returns) / len(returns) if returns else 0
            else:
                avg_return = 0

            expected_return += allocation * avg_return
            quantity = (
                (allocation * total_capital) / current_price if current_price > 0 else 0
            )
            action = determine_action(
                asset_id, asset_data, correlation_dict, allocation
            )

            trades.append(
                {
                    "asset_id": asset_id,
                    "action": action,
                    "quantity": quantity,
                    "price": current_price,
                    "allocation": allocation,
                }
            )

    portfolio_variance = calculate_portfolio_variance(
        best_strategy, asset_data, correlation_dict
    )
    portfolio_volatility = (
        math.sqrt(portfolio_variance) if portfolio_variance > 0 else 0.001
    )
    sharpe_ratio = (
        expected_return / portfolio_volatility if portfolio_volatility > 0 else 0
    )

    segment_names = [f"segment_{i}" for i in range(len(segments))]

    return {
        "trades": trades,
        "expected_return": expected_return,
        "portfolio_volatility": portfolio_volatility,
        "sharpe_ratio": sharpe_ratio,
        "segments": segment_names,
        "tree_depth": max_depth_reached,
        "cache_statistics": {
            "memoization_hits": state.memo_hits,
            "memoization_misses": state.memo_misses,
            "collision_count": state.collision_count,
        },
        "prune_operations": state.prune_operations,
        "backtrack_count": state.backtrack_count,
        "decision_path": final_decision_path[:20],
        "arbitrage_opportunities": arbitrage_opportunities,
        "resolved_conflicts": resolved_conflicts,
        "rebalancing_iterations": rebalancing_iterations,
        "convergence_metrics": convergence_metrics,
    }


class UnionFind:
    def __init__(self, assets: List[str]):
        self.parent = {asset: asset for asset in assets}
        self.rank = {asset: 0 for asset in assets}

    def find(self, asset: str) -> str:
        if self.parent[asset] != asset:
            self.parent[asset] = self.find(self.parent[asset])
        return self.parent[asset]

    def union(self, asset1: str, asset2: str):
        root1 = self.find(asset1)
        root2 = self.find(asset2)

        if root1 != root2:
            if self.rank[root1] < self.rank[root2]:
                self.parent[root1] = root2
            elif self.rank[root1] > self.rank[root2]:
                self.parent[root2] = root1
            else:
                self.parent[root2] = root1
                self.rank[root1] += 1

    def get_clusters(self) -> List[List[str]]:
        clusters = defaultdict(list)
        for asset in self.parent:
            root = self.find(asset)
            clusters[root].append(asset)
        return list(clusters.values())


def partition_by_correlation_union_find(
    assets: List[str], correlation_matrix: Dict[Tuple[str, str], float]
) -> List[List[str]]:
    if len(assets) <= 3:
        return [assets]

    uf = UnionFind(assets)

    for i, asset1 in enumerate(assets):
        for asset2 in assets[i + 1 :]:
            pair = tuple(sorted([asset1, asset2]))
            corr = correlation_matrix.get(pair, 0)
            if corr > 0.7:
                uf.union(asset1, asset2)

    return uf.get_clusters()


def fnv1a_hash(state: FrozenSet[Tuple[str, float]]) -> int:
    FNV_prime = 16777619
    offset_basis = 2166136261
    hash_value = offset_basis

    for item in sorted(state):
        for byte in str(item).encode():
            hash_value = (hash_value ^ byte) * FNV_prime
            hash_value &= 0xFFFFFFFF

    return hash_value


def create_state_key_advanced(
    strategy: Dict[str, float],
) -> Tuple[FrozenSet[Tuple[str, float]], int]:
    rounded = tuple(
        (asset_id, round(alloc, 3)) for asset_id, alloc in sorted(strategy.items())
    )
    frozen_state = frozenset(rounded)
    hash_val = fnv1a_hash(frozen_state)
    return frozen_state, hash_val


def get_cached_sharpe(
    optimizer_state: OptimizerState,
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
) -> float:
    """Get Sharpe ratio from cache or compute and cache it"""
    state, hash_val = create_state_key_advanced(strategy)

    probe_offset = 0
    while True:
        probe_key = hash_val + probe_offset
        cached = optimizer_state.memo_cache.get(probe_key)

        if cached is None:
            optimizer_state.memo_misses += 1
            sharpe = calculate_sharpe(strategy, asset_data, correlation_matrix)
            optimizer_state.memo_cache[probe_key] = (state, sharpe)
            return sharpe
        else:
            cached_state, cached_sharpe = cached
            if cached_state == state:
                optimizer_state.memo_hits += 1
                return cached_sharpe
            else:
                optimizer_state.collision_count += 1
                probe_offset += 1
                if probe_offset > 100:
                    optimizer_state.memo_misses += 1
                    sharpe = calculate_sharpe(strategy, asset_data, correlation_matrix)
                    return sharpe


def check_constraints_during_recursion(
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    portfolio_constraints: Dict[str, float],
    correlation_matrix: Dict[Tuple[str, str], float],
) -> Tuple[bool, List[str]]:
    """Check if strategy violates hard constraints that make it impossible to rebalance. Returns (is_valid, violated_constraints)"""
    violated = []

    max_position_size = portfolio_constraints.get("max_position_size", 1.0)
    max_sector_concentration = portfolio_constraints.get(
        "max_sector_concentration", 1.0
    )

    total_alloc = sum(strategy.values())
    if total_alloc <= 0:
        return False, ["zero_allocation"]

    normalized = {k: v / total_alloc for k, v in strategy.items()}

    sector_alloc = defaultdict(float)
    for asset_id, alloc in normalized.items():
        sector = asset_data[asset_id].get("sector", "unknown")
        sector_alloc[sector] += alloc

    for sector, alloc in sector_alloc.items():
        if alloc > max_sector_concentration * 1.5:
            violated.append(f"sector_{sector}")

    return len(violated) == 0, violated


def recursive_strategy_search_advanced(
    optimizer_state: OptimizerState,
    assets: List[str],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
    portfolio_constraints: Dict[str, float],
    depth: int,
    max_depth: int,
    alpha: float = float("-inf"),
    beta: float = float("inf"),
) -> Tuple[Optional[Dict[str, float]], float, int, List[Dict[str, Any]]]:
    optimizer_state.computation_budget += 1
    if optimizer_state.computation_budget > optimizer_state.MAX_COMPUTATION_BUDGET:
        return None, float("-inf"), depth, []

    if depth >= max_depth or not assets:
        return None, float("-inf"), depth, []

    if len(assets) == 1:
        asset = assets[0]
        strategy = {asset: 1.0}
        is_valid, violated = check_constraints_during_recursion(
            strategy, asset_data, portfolio_constraints, correlation_matrix
        )
        if not is_valid:
            optimizer_state.backtrack_count += 1
            return None, float("-inf"), depth, []
        sharpe = calculate_sharpe(strategy, asset_data, correlation_matrix)
        path = [
            {
                "depth": depth,
                "asset_chosen": asset,
                "allocation": 1.0,
                "sharpe_delta": sharpe,
                "constraints_active": ["single_asset"],
            }
        ]
        return strategy, sharpe, depth + 1, path

    best_strategy = None
    best_sharpe = float("-inf")
    max_depth_reached = depth
    best_path = []

    if len(assets) >= 2 and depth == 0:
        equal_weight = {}
        for asset in assets[: min(10, len(assets))]:
            equal_weight[asset] = 1.0 / min(10, len(assets))

        equal_sharpe = get_cached_sharpe(
            optimizer_state, equal_weight, asset_data, correlation_matrix
        )

        is_valid, violated = check_constraints_during_recursion(
            equal_weight, asset_data, portfolio_constraints, correlation_matrix
        )
        if not is_valid:
            optimizer_state.backtrack_count += 1
        else:
            diversification_bonus = 0.05 * len(equal_weight)
            if equal_sharpe + diversification_bonus > best_sharpe:
                best_sharpe = equal_sharpe + diversification_bonus
                best_strategy = equal_weight
                max_depth_reached = max(max_depth_reached, 1)
                best_path = [
                    {
                        "depth": 0,
                        "asset_chosen": "equal_weight",
                        "allocation": 1.0 / len(equal_weight),
                        "sharpe_delta": equal_sharpe,
                        "constraints_active": list(equal_weight.keys()),
                    }
                ]

    # Explore all assets (no artificial limit)
    for i, asset in enumerate(assets):
        if optimizer_state.computation_budget > optimizer_state.MAX_COMPUTATION_BUDGET:
            break

        current_strategy = {asset: 1.0}
        current_sharpe = get_cached_sharpe(
            optimizer_state, current_strategy, asset_data, correlation_matrix
        )

        is_valid, violated = check_constraints_during_recursion(
            current_strategy, asset_data, portfolio_constraints, correlation_matrix
        )
        if not is_valid:
            optimizer_state.backtrack_count += 1
            continue

        # Calculate theoretical max Sharpe (best possible returns / min volatility)
        theoretical_max = calculate_theoretical_max_sharpe(assets, asset_data)
        upper_bound = min(current_sharpe + theoretical_max * 0.5, theoretical_max)

        # Update beta for alpha-beta pruning
        beta = min(beta, upper_bound)

        if upper_bound <= alpha:
            optimizer_state.prune_operations += 1
            continue

        if current_sharpe > best_sharpe + 0.1:
            best_sharpe = current_sharpe
            best_strategy = current_strategy

        if depth < max_depth - 1:
            remaining_assets = [a for j, a in enumerate(assets) if j != i]

            if len(remaining_assets) > 0:
                sub_strategy, sub_sharpe, sub_depth, sub_path = (
                    recursive_strategy_search_advanced(
                        optimizer_state,
                        remaining_assets,
                        asset_data,
                        correlation_matrix,
                        portfolio_constraints,
                        depth + 1,
                        max_depth,
                        alpha,
                        beta,
                    )
                )

                max_depth_reached = max(max_depth_reached, sub_depth)

                if sub_strategy is None:
                    optimizer_state.backtrack_count += 1

                if sub_strategy:
                    # Explore multiple allocation combinations systematically
                    for weight_split in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
                        combined_strategy = {asset: weight_split}
                        for sub_asset, sub_alloc in sub_strategy.items():
                            if sub_asset in combined_strategy:
                                combined_strategy[sub_asset] += sub_alloc * (
                                    1 - weight_split
                                )
                            else:
                                combined_strategy[sub_asset] = sub_alloc * (
                                    1 - weight_split
                                )

                        combined_sharpe = get_cached_sharpe(
                            optimizer_state,
                            combined_strategy,
                            asset_data,
                            correlation_matrix,
                        )
                        combined_bonus = (
                            0.02 * len(combined_strategy)
                            if len(combined_strategy) > 1
                            else 0
                        )

                        is_valid_combined, violated_combined = (
                            check_constraints_during_recursion(
                                combined_strategy,
                                asset_data,
                                portfolio_constraints,
                                correlation_matrix,
                            )
                        )
                        if not is_valid_combined:
                            optimizer_state.backtrack_count += 1
                            continue

                        # Tie-breaking: if Sharpe ratios within 0.001, prefer fewer trades
                        sharpe_diff = abs(
                            combined_sharpe + combined_bonus - best_sharpe
                        )
                        if sharpe_diff < 0.001:
                            # Tie detected - prefer strategy with fewer trades
                            current_trades = len(combined_strategy)
                            best_trades = (
                                len(best_strategy) if best_strategy else float("inf")
                            )
                            should_update = current_trades < best_trades
                        else:
                            should_update = (
                                combined_sharpe + combined_bonus > best_sharpe
                            )

                        if should_update:
                            best_sharpe = combined_sharpe + combined_bonus
                            best_strategy = combined_strategy

                            current_decision = {
                                "depth": depth,
                                "asset_chosen": asset,
                                "allocation": weight_split,
                                "sharpe_delta": combined_sharpe - current_sharpe,
                                "constraints_active": list(combined_strategy.keys()),
                            }
                            best_path = [current_decision] + sub_path

                        alpha = max(alpha, best_sharpe)
                        if beta <= alpha:
                            optimizer_state.prune_operations += 1
                            break

                if beta <= alpha:
                    break

    return best_strategy, best_sharpe, max_depth_reached, best_path


def calculate_portfolio_variance(
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
) -> float:
    """Helper function to calculate portfolio variance (consolidated logic)"""
    portfolio_variance = 0

    asset_list = list(strategy.keys())
    for i, asset_i in enumerate(asset_list):
        if asset_i not in asset_data:
            continue
        alloc_i = strategy[asset_i]
        vol_i = asset_data[asset_i].get("volatility", 0)
        portfolio_variance += (alloc_i**2) * (vol_i**2)

        for asset_j in asset_list[i + 1 :]:
            if asset_j not in asset_data:
                continue
            alloc_j = strategy[asset_j]
            vol_j = asset_data[asset_j].get("volatility", 0)
            pair = tuple(sorted([asset_i, asset_j]))
            corr = correlation_matrix.get(pair, 0)
            portfolio_variance += 2 * alloc_i * alloc_j * vol_i * vol_j * corr

    return portfolio_variance


def calculate_sharpe(
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
) -> float:
    expected_return = 0

    for asset_id, allocation in strategy.items():
        if asset_id not in asset_data:
            continue

        prices = asset_data[asset_id].get("prices", [])
        if len(prices) >= 2:
            returns = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices))
            ]
            avg_return = sum(returns) / len(returns) if returns else 0
        else:
            avg_return = 0

        expected_return += allocation * avg_return

    portfolio_variance = calculate_portfolio_variance(
        strategy, asset_data, correlation_matrix
    )
    portfolio_volatility = (
        math.sqrt(portfolio_variance) if portfolio_variance > 0 else 0.001
    )
    sharpe_ratio = (
        expected_return / portfolio_volatility if portfolio_volatility > 0 else 0
    )

    return sharpe_ratio


def calculate_portfolio_volatility(
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
) -> float:
    portfolio_variance = calculate_portfolio_variance(
        strategy, asset_data, correlation_matrix
    )
    return math.sqrt(portfolio_variance) if portfolio_variance > 0 else 0.0


def detect_arbitrage_advanced(
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
) -> List[Dict[str, Any]]:
    arbitrage_opportunities = []

    asset_list = list(strategy.keys())
    for i, asset_i in enumerate(asset_list):
        for asset_j in asset_list[i + 1 :]:
            pair = tuple(sorted([asset_i, asset_j]))
            corr = correlation_matrix.get(pair, 0)

            if corr > 0.8:
                prices_i = asset_data[asset_i].get("prices", [])
                prices_j = asset_data[asset_j].get("prices", [])

                if len(prices_i) >= 2 and len(prices_j) >= 2:
                    return_i = (
                        (prices_i[-1] - prices_i[-2]) / prices_i[-2]
                        if prices_i[-2] != 0
                        else 0
                    )
                    return_j = (
                        (prices_j[-1] - prices_j[-2]) / prices_j[-2]
                        if prices_j[-2] != 0
                        else 0
                    )

                    divergence = (
                        abs(return_i - return_j) / abs(corr) if corr != 0 else 0
                    )
                    if divergence > 0.05:
                        action = (
                            "long_A_short_B"
                            if return_i > return_j
                            else "long_B_short_A"
                        )
                        arbitrage_opportunities.append(
                            {
                                "asset_pair": (asset_i, asset_j),
                                "correlation": corr,
                                "divergence": divergence,
                                "action": action,
                            }
                        )

    return arbitrage_opportunities


def resolve_cross_segment_conflicts(
    strategy: Dict[str, float],
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
    segments: List[List[str]],
) -> List[Dict[str, Any]]:
    resolved_conflicts = []

    for i, seg1 in enumerate(segments):
        for seg2 in segments[i + 1 :]:
            for asset1 in seg1:
                if asset1 not in strategy:
                    continue
                for asset2 in seg2:
                    if asset2 not in strategy:
                        continue

                    pair = tuple(sorted([asset1, asset2]))
                    corr = correlation_matrix.get(pair, 0)

                    if corr > 0.7:
                        action1 = determine_action(
                            asset1, asset_data, correlation_matrix
                        )
                        action2 = determine_action(
                            asset2, asset_data, correlation_matrix
                        )

                        if (action1 == "BUY" and action2 == "SELL") or (
                            action1 == "SELL" and action2 == "BUY"
                        ):
                            # Calculate Sharpe ratios for both assets
                            sharpe1 = calculate_individual_sharpe(asset1, asset_data)
                            sharpe2 = calculate_individual_sharpe(asset2, asset_data)

                            # Perform Sharpe-weighted merge
                            total_sharpe = abs(sharpe1) + abs(sharpe2)
                            if total_sharpe > 0:
                                weight1 = abs(sharpe1) / total_sharpe
                                weight2 = abs(sharpe2) / total_sharpe

                                # Merge allocations weighted by Sharpe ratios
                                old_alloc1 = strategy[asset1]
                                old_alloc2 = strategy[asset2]

                                # Weighted merge: favor higher Sharpe asset
                                strategy[asset1] = (
                                    old_alloc1 * weight1 + old_alloc2 * weight1 * 0.5
                                )
                                strategy[asset2] = (
                                    old_alloc2 * weight2 + old_alloc1 * weight2 * 0.5
                                )

                                resolved_conflicts.append(
                                    {
                                        "pair": (asset1, asset2),
                                        "conflict_type": "opposing_positions",
                                        "resolution": "weighted_merge_by_sharpe",
                                        "sharpe_weights": (weight1, weight2),
                                    }
                                )

    return resolved_conflicts


def calculate_individual_sharpe(
    asset_id: str, asset_data: Dict[str, Dict[str, Any]]
) -> float:
    """Calculate Sharpe ratio for individual asset"""
    prices = asset_data[asset_id].get("prices", [])
    if len(prices) < 2:
        return 0.0

    returns = [
        (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
    ]
    if not returns:
        return 0.0

    avg_return = sum(returns) / len(returns)
    volatility = asset_data[asset_id].get("volatility", 0.01)

    if volatility == 0:
        return 0.0

    return avg_return / volatility


def calculate_theoretical_max_sharpe(
    assets: List[str], asset_data: Dict[str, Dict[str, Any]]
) -> float:
    """Calculate theoretical maximum Sharpe ratio from best possible returns"""
    if not assets:
        return 0.0

    max_returns = []
    min_volatilities = []

    for asset_id in assets:
        prices = asset_data[asset_id].get("prices", [])
        if len(prices) >= 2:
            returns = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices))
            ]
            if returns:
                max_returns.append(max(returns))

        volatility = asset_data[asset_id].get("volatility", 0.1)
        if volatility > 0:
            min_volatilities.append(volatility)

    if not max_returns or not min_volatilities:
        return 1.0  # Default theoretical max

    # Theoretical max: best return / minimum volatility
    best_return = max(max_returns)
    min_vol = min(min_volatilities)

    return best_return / min_vol if min_vol > 0 else 1.0


def determine_action(
    asset_id: str,
    asset_data: Dict[str, Dict[str, Any]],
    correlation_matrix: Dict[Tuple[str, str], float],
    allocation: float = 0.0,
) -> str:
    """
    Determine trading action based on allocation in the optimized portfolio.
    If an asset has positive allocation, the action should be BUY to construct the portfolio.
    """
    # For any asset with positive allocation in the optimized portfolio, action should be BUY
    if allocation > 0:
        return "BUY"

    # For assets not in the portfolio
    prices = asset_data[asset_id].get("prices", [])

    if len(prices) >= 2:
        # Calculate expected return (same method as optimizer)
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] != 0
        ]

        if returns:
            avg_return = sum(returns) / len(returns)

            # Decision based on expected return
            if avg_return > 0.01:  # Positive expected return threshold
                return "BUY"
            elif avg_return < -0.01:  # Negative expected return threshold
                return "SELL"
            else:
                return "HOLD"

    return "HOLD"


if __name__ == "__main__":
    # Sample input from prompt
    asset_data = {
        "AAPL": {
            "prices": [150.0, 152.0, 155.0],
            "volatility": 0.25,
            "liquidity_score": 80,
            "current_price": 155.0,
            "sector": "tech",
        },
        "MSFT": {
            "prices": [300.0, 302.0, 305.0],
            "volatility": 0.22,
            "liquidity_score": 85,
            "current_price": 305.0,
            "sector": "tech",
        },
        "GOLD": {
            "prices": [1800.0, 1820.0, 1850.0],
            "volatility": 0.18,
            "liquidity_score": 90,
            "current_price": 1850.0,
            "sector": "commodity",
        },
    }

    correlation_matrix = [
        {"asset_pair": ["AAPL", "MSFT"], "correlation": 0.75},
        {"asset_pair": ["AAPL", "GOLD"], "correlation": 0.1},
        {"asset_pair": ["GOLD", "MSFT"], "correlation": 0.05},
    ]

    portfolio_constraints = {
        "max_position_size": 0.6,
        "max_sector_concentration": 0.8,
        "min_liquidity": 50,
        "total_capital": 100000.0,
    }

    result = optimize_trading_strategy(
        asset_data, correlation_matrix, portfolio_constraints
    )
    print(json.dumps(result, indent=2))