from typing import List, Tuple, Dict, Iterable
import math


class ArbitrageEngine:
    """Directed graph with direct-edge lookup, per-source min-fee cache, and negative-cycle detection."""

    __slots__ = ("n", "edges", "direct_fee", "adj", "_cache")

    def __init__(self, n: int, edges: Iterable[Tuple[int, int, float]]) -> None:
        self.n = n
        self.edges: List[Tuple[int, int, float]] = list(edges)
        self.direct_fee: Dict[Tuple[int, int], float] = {}
        self.adj: List[List[int]] = [[] for _ in range(n)]  # for propagation
        for u, v, w in self.edges:
            if not (0 <= u < n and 0 <= v < n):
                raise ValueError("edge endpoint out of bounds")
            self.direct_fee[(u, v)] = w  # last wins for duplicates
            self.adj[u].append(v)
        # cache: src -> (dist list, affected_by_neg_cycle list[bool])
        self._cache: Dict[int, Tuple[List[float], List[bool]]] = {}

    def _bf_with_neg_cycle(self, src: int) -> Tuple[List[float], List[bool]]:
        """Bellman–Ford (prev/curr arrays, ≤ N−1 edges) + reachable negative-cycle propagation."""
        if src in self._cache:
            return self._cache[src]

        n = self.n
        prev = [math.inf] * n
        prev[src] = 0.0

        # After i passes, prev reflects paths with ≤ i edges.
        for _ in range(n - 1):
            curr = prev[:]  # read prev; write curr
            changed = False
            for u, v, w in self.edges:
                du = prev[u]
                if du == math.inf:
                    continue
                nv = du + w
                if nv < curr[v]:
                    curr[v] = nv
                    changed = True
            prev = curr
            if not changed:
                break

        # Detect any vertex improved on the Nth pass (reachable neg cycle)
        improved = [False] * n
        for u, v, w in self.edges:
            if prev[u] != math.inf and prev[u] + w < prev[v]:
                improved[v] = True

        # Propagate from improved vertices to mark all targets influenced by a neg cycle
        affected = [False] * n
        queue = [i for i, imp in enumerate(improved) if imp]
        for i in queue:
            affected[i] = True
        qh = 0
        while qh < len(queue):
            x = queue[qh]
            qh += 1
            for y in self.adj[x]:
                if not affected[y]:
                    affected[y] = True
                    queue.append(y)

        self._cache[src] = (prev, affected)
        return prev, affected

    def fee_between(self, u: int, v: int) -> float:
        """
        Return the fee for u→v using direct-edge preference; otherwise the minimum summed-fee path.
        If a reachable negative cycle from u can reach v, return -inf (arbitrarily low fee).
        If v is unreachable from u, return +inf.
        """
        direct = self.direct_fee.get((u, v))
        if direct is not None:
            return direct
        dist, affected = self._bf_with_neg_cycle(u)
        if affected[v]:
            return float("-inf")  # arbitrarily low fee via neg cycle
        return dist[v]           # may be +inf if unreachable


def high_frequency_arbitrage_engine(
    edges: List[Tuple[int, int, float]],
    initial_prices: List[float],
    updates: List[Tuple[int, float]],
    queries: List[Tuple[int, int]]
) -> List[float]:
    """
    Compute arbitrage differentials for requested (u, v) pairs on a directed fee graph.

    Purpose:
        After applying all price updates, compute diff(u, v) for each query:
            diff(u, v) = price[v] - price[u] - fee(u→v)
        Fee selection follows the prompt rules:
          - If a direct edge u→v exists, use its fee (direct-edge preference).
          - Otherwise, use the minimum summed-fee path from u to v.
          - If no path exists, the differential is -inf.
          - If a negative cycle reachable from u can also reach v, the differential is +inf.

    Args:
        edges: List of directed edges as (u, v, fee). Fee may be negative (rebate).
        initial_prices: price[i] is the price of asset i before updates.
        updates: List of (idx, new_price) applied in order before answering queries.
        queries: List of (u, v) pairs for which to compute the differential.

    Returns:
        List[float]: One differential per input query, in the same order. Finite numbers
        for reachable routes; -inf when v is unreachable from u; +inf when a reachable
        negative cycle from u can reach v.

    Raises:
        ValueError: If any edge, update, or query references an index outside the range
                    implied by the inputs (i.e., larger than any provided price index).
                    This ensures invalid graph references are detected early.
    """

    def _stable(vals, ndigits: int = 12):
        """Normalize finite floats for stable, tidy string equality; keep ±inf unchanged."""
        out = []
        for x in vals:
            if isinstance(x, float) and math.isfinite(x):
                out.append(float(f"{x:.{ndigits}g}"))
            else:
                out.append(x)
        return out

    # Determine required node count from all inputs
    max_idx = -1
    for u, v, _ in edges:
        max_idx = max(max_idx, u, v)
    for i, _ in updates:
        max_idx = max(max_idx, i)
    for u, v in queries:
        max_idx = max(max_idx, u, v)
    n = max_idx + 1 if max_idx >= 0 else len(initial_prices)

    if len(initial_prices) < n:
        raise ValueError("initial_prices length is smaller than referenced node indices")

    prices = list(initial_prices)
    for idx, new_price in updates:
        if not (0 <= idx < len(prices)):
            raise ValueError("update index out of bounds")
        prices[idx] = new_price

    engine = ArbitrageEngine(n, edges)

    out: List[float] = []
    for u, v in queries:
        if not (0 <= u < n and 0 <= v < n):
            raise ValueError("query indices out of bounds")
        fee = engine.fee_between(u, v)
        if fee == math.inf:
            out.append(float("-inf"))   # unreachable
        elif fee == float("-inf"):
            out.append(float("inf"))    # neg cycle reachable ⇒ diff = +inf
        else:
            out.append(prices[v] - prices[u] - fee)
    return _stable(out, 12)


if __name__ == "__main__":
    edges = [(0, 1, 0.1), (1, 2, 0.2), (2, 0, 0.05), (0, 2, 0.25), (1, 0, -2.25)]
    initial_prices = [100.0, 101.5, 99.8]
    updates = [(1, 102.3), (2, 100.2), (0, 99.9)]
    queries = [(0, 2), (1, 0)]
    res = high_frequency_arbitrage_engine(edges, initial_prices, updates, queries)
    print([f"{x:.9f}" for x in res])