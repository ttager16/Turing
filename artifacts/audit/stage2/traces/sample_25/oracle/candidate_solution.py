from typing import List, Optional, Tuple
import threading
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# ----- Module-level configuration constants -----
# Worker sizing
MAX_WORKERS_BASE: int = 2
MAX_WORKERS_CAP: int = 32
DEFAULT_CPU_COUNT: int = 4
WORKERS_PER_CPU: int = 2

# Timeouts
DEFAULT_TIMEOUT_PER_TASK_S: float = 0.050

# Scoring weights
WEIGHT_OVERLAP_S: float = 0.45
WEIGHT_OVERLAP_M: float = 0.20
WEIGHT_MATCH_OVERLAP_M: float = 0.20
WEIGHT_BREADTH: float = 0.10
WEIGHT_CONSENSUS: float = 0.05

# Decision thresholds
BUY_THRESHOLD: float = 0.75
BUY_PARTIAL_THRESHOLD: float = 0.55
SELL_THRESHOLD: float = 0.15
SELL_PARTIAL_THRESHOLD: float = 0.30

# Penalty calculation parameters
MAX_CROWDING_PENALTY: float = 0.20
PENALTY_FACTOR: float = 0.5


def _sanitize_inputs(seq: List[int]) -> List[int]:
    """Sanitize input sequence to non-negative integers, dropping invalid entries."""
    out: List[int] = []
    for x in seq:
        try:
            xi = int(x)
        except (ValueError, TypeError):
            continue
        if xi < 0:
            xi = 0
        out.append(xi)
    return out


class AtomicInteger:
    def __init__(self, initial: int = 0) -> None:
        self._value = initial
        self._lock = threading.Lock()

    def get(self) -> int:
        with self._lock:
            return self._value

    def set(self, v: int) -> None:
        with self._lock:
            self._value = v

    def add_and_get(self, delta: int) -> int:
        with self._lock:
            self._value += delta
            return self._value


def count_set_bits(n: int) -> int:
    count = 0
    while n:
        n &= n - 1
        count += 1
    return count


def msb_index(n: int) -> int:
    if n <= 0:
        return -1
    return n.bit_length() - 1


def mask_bit_width(values_a: List[int], values_b: List[int]) -> int:
    max_val = 0
    for v in values_a:
        if v > max_val:
            max_val = v
    for v in values_b:
        if v > max_val:
            max_val = v
    idx = msb_index(max_val)
    return max(1, idx + 1)


class BitsetTrieNode:
    def __init__(self) -> None:
        self.zero: Optional[BitsetTrieNode] = None
        self.one: Optional[BitsetTrieNode] = None
        self.count: int = 0
        self.lock = threading.Lock()


class BitsetTrie:
    """
    Thread-safe bitset trie for storing integers as bit paths.
    Supports insert and best_match queries that greedily match a target mask.
    """

    def __init__(self, bit_width: int) -> None:
        self.root = BitsetTrieNode()
        self.bit_width = bit_width

    def insert(self, value: int) -> None:
        node = self.root
        node.lock.acquire()
        try:
            node.count += 1
            for i in range(self.bit_width - 1, -1, -1):
                bit = (value >> i) & 1
                if bit == 0:
                    if node.zero is None:
                        node.zero = BitsetTrieNode()
                    next_node = node.zero
                else:
                    if node.one is None:
                        node.one = BitsetTrieNode()
                    next_node = node.one
                next_node.lock.acquire()
                try:
                    node.lock.release()
                except RuntimeError:
                    # Already released in error scenario; proceed
                    pass
                node = next_node
                node.count += 1
        finally:
            # Ensure the final node lock is released
            try:
                node.lock.release()
            except RuntimeError:
                pass

    def best_match(self, target: int) -> int:
        """
        Greedily chooses path aligning with target's bits to maximize overlap.
        Returns an integer constructed from the traversed path.
        """
        node = self.root
        path_value = 0
        for i in range(self.bit_width - 1, -1, -1):
            desired_bit = (target >> i) & 1
            preferred = node.one if desired_bit == 1 else node.zero
            alt = node.zero if desired_bit == 1 else node.one
            chosen: Optional[BitsetTrieNode] = None
            # Avoid relying on mutable counters without locks; presence implies viability
            if preferred is not None:
                chosen = preferred
                bit = desired_bit
            elif alt is not None:
                chosen = alt
                bit = 1 - desired_bit
            else:
                bit = 0
                chosen = None
            path_value = (path_value << 1) | (bit & 1)
            if chosen is None:
                path_value <<= i
                break
            node = chosen
        return path_value


class SegmentAggregate:
    __slots__ = ("or_mask", "and_mask", "size")

    def __init__(self, or_mask: int = 0, and_mask: int = -1, size: int = 0) -> None:
        self.or_mask = or_mask
        self.and_mask = and_mask
        self.size = size

    @staticmethod
    def combine(a: "SegmentAggregate", b: "SegmentAggregate") -> "SegmentAggregate":
        if a.size == 0:
            return b
        if b.size == 0:
            return a
        out = SegmentAggregate()
        out.size = a.size + b.size
        out.or_mask = a.or_mask | b.or_mask
        out.and_mask = a.and_mask & b.and_mask
        return out


class SegmentTree:
    """
    Thread-safe segment tree for aggregating bitmasks across ranges.
    Stores OR and AND masks for quick breadth/consensus queries.
    """

    def __init__(self, values: List[int]) -> None:
        self.n = len(values)
        self.size = 1
        while self.size < self.n:
            self.size <<= 1
        self._tree: List[SegmentAggregate] = [SegmentAggregate() for _ in range(2 * self.size)]
        self._locks: List[threading.Lock] = [threading.Lock() for _ in range(2 * self.size)]
        for i, v in enumerate(values):
            idx = i + self.size
            self._tree[idx] = SegmentAggregate(or_mask=v, and_mask=v, size=1)
        for idx in range(self.size - 1, 0, -1):
            left = self._tree[idx * 2]
            right = self._tree[idx * 2 + 1]
            self._tree[idx] = SegmentAggregate.combine(left, right)

    def update(self, index: int, value: int) -> None:
        if not (0 <= index < self.n):
            return
        idx = index + self.size
        with self._locks[idx]:
            self._tree[idx] = SegmentAggregate(or_mask=value, and_mask=value, size=1)
        idx //= 2
        while idx >= 1:
            with self._locks[idx]:
                left = self._tree[idx * 2]
                right = self._tree[idx * 2 + 1]
                self._tree[idx] = SegmentAggregate.combine(left, right)
            idx //= 2

    def query(self, l: int, r: int) -> SegmentAggregate:
        """
        Query inclusive range [l, r].
        """
        if l > r:
            return SegmentAggregate()
        l = max(0, l)
        r = min(self.n - 1, r)
        l += self.size
        r += self.size
        res_left = SegmentAggregate()
        res_right = SegmentAggregate()
        while l <= r:
            if (l % 2) == 1:
                with self._locks[l]:
                    res_left = SegmentAggregate.combine(res_left, self._tree[l])
                l += 1
            if (r % 2) == 0:
                with self._locks[r]:
                    res_right = SegmentAggregate.combine(self._tree[r], res_right)
                r -= 1
            l //= 2
            r //= 2
        return SegmentAggregate.combine(res_left, res_right)


class TradeEngine:
    """
    Multi-step decision engine using both SegmentTree and BitsetTrie.
    Evaluates actions concurrently and applies a small optimizer.
    """

    def __init__(
        self,
        signals: List[int],
        conditions: List[int],
        bit_width: int,
        timeout_per_task_s: float = DEFAULT_TIMEOUT_PER_TASK_S,
    ) -> None:
        self.signals = list(signals)
        self.conditions = list(conditions)
        self.bit_width = bit_width
        self.timeout_per_task_s = timeout_per_task_s

        self.signal_tree = SegmentTree(self.signals)
        self.condition_tree = SegmentTree(self.conditions)

        self.trie = BitsetTrie(bit_width)
        for s in self.signals:
            self.trie.insert(s)

        self._positions_open = AtomicInteger(0)
        self._version = AtomicInteger(0)
        self._ingest_lock = threading.Lock()
        self._engine_locks: dict = {}

    def _score_overlap(self, s: int, m: int) -> Tuple[float, float, int]:
        inter = s & m
        s_bits = count_set_bits(s)
        m_bits = count_set_bits(m)
        inter_bits = count_set_bits(inter)
        overlap_s = inter_bits / s_bits if s_bits else 0.0
        overlap_m = inter_bits / m_bits if m_bits else 0.0
        return overlap_s, overlap_m, inter_bits

    def _market_breadth_and_consensus(self) -> Tuple[float, float]:
        agg_s = self.signal_tree.query(0, len(self.signals) - 1)
        agg_m = self.condition_tree.query(0, len(self.conditions) - 1)
        width = max(1, self.bit_width)
        breadth = count_set_bits(agg_m.or_mask) / width
        consensus = count_set_bits(agg_s.and_mask) / width
        return breadth, consensus

    def _optimize_decision(
        self,
        s: int,
        m: int,
        breadth: float,
        consensus: float,
        base_open_positions: Optional[int] = None,
    ) -> str:
        overlap_s, overlap_m, _ = self._score_overlap(s, m)
        best_signal_match = self.trie.best_match(m)
        _, match_overlap_m, _ = self._score_overlap(best_signal_match, m)
        score = (
            WEIGHT_OVERLAP_S * overlap_s
            + WEIGHT_OVERLAP_M * overlap_m
            + WEIGHT_MATCH_OVERLAP_M * match_overlap_m
            + WEIGHT_BREADTH * breadth
            + WEIGHT_CONSENSUS * consensus
        )
        open_positions = (
            base_open_positions
            if base_open_positions is not None
            else self._positions_open.get()
        )
        crowding_penalty = min(
            MAX_CROWDING_PENALTY,
            open_positions / max(1.0, len(self.signals)) * PENALTY_FACTOR,
        )
        score = max(0.0, score - crowding_penalty)
        if score >= BUY_THRESHOLD:
            return "BUY"
        if score >= BUY_PARTIAL_THRESHOLD:
            return "BUY_PARTIAL"
        if score <= SELL_THRESHOLD:
            return "SELL"
        if score <= SELL_PARTIAL_THRESHOLD:
            return "SELL_PARTIAL"
        return "HOLD"

    def _get_engine_lock(self, engine_id: str) -> threading.Lock:
        """Get or create a lock for the specified engine ID."""
        with self._ingest_lock:
            if engine_id not in self._engine_locks:
                self._engine_locks[engine_id] = threading.Lock()
            return self._engine_locks[engine_id]

    def _evaluate_once(self, idx: int, base_open_positions: Optional[int] = None) -> str:
        """Single evaluation pass for an index."""
        s = self.signals[idx]
        m = self.conditions[idx]
        breadth, consensus = self._market_breadth_and_consensus()
        return self._optimize_decision(s, m, breadth, consensus, base_open_positions)

    def _evaluate_index(self, idx: int, base_open_positions: Optional[int] = None) -> str:
        """Evaluate with reactive recomputation if state changed during evaluation."""
        v0 = self._version.get()
        action = self._evaluate_once(idx, base_open_positions)
        if self._version.get() != v0:
            action = self._evaluate_once(idx, base_open_positions)
        return action

    def evaluate_all(self) -> List[str]:
        n = min(len(self.signals), len(self.conditions))
        if n == 0:
            return []
        trade_actions: List[str] = ["HOLD"] * n

        max_workers = max(
            MAX_WORKERS_BASE,
            min(MAX_WORKERS_CAP, (os.cpu_count() or DEFAULT_CPU_COUNT) * WORKERS_PER_CPU),
        )
        base_open_positions = self._positions_open.get()
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="trade-eval") as pool:
            for i in range(n):
                futures.append((i, pool.submit(self._safe_evaluate_index, i, base_open_positions)))

            # Deterministic: wait for all futures without time-based deadlines
            for i, fut in futures:
                try:
                    trade_actions[i] = fut.result()
                except (FuturesTimeoutError, RuntimeError, ValueError):
                    trade_actions[i] = "HOLD"

        buy_indices = [i for i, a in enumerate(trade_actions) if a == "BUY"]
        if len(buy_indices) > n // 2:
            scored = []
            for i in buy_indices:
                s = self.signals[i]
                m = self.conditions[i]
                overlap_s, overlap_m, _ = self._score_overlap(s, m)
                # Sort by lowest overlap_s, then lowest overlap_m, then by index (deterministic)
                scored.append((overlap_s, overlap_m, i))
            scored.sort()
            to_downgrade = scored[: len(scored) // 2]
            for _, _, i in to_downgrade:
                trade_actions[i] = "BUY_PARTIAL"

        # Update open positions deterministically after all decisions are finalized
        total_opens = sum(1 for a in trade_actions if a in ("BUY", "BUY_PARTIAL"))
        self._positions_open.set(base_open_positions + total_opens)

        return trade_actions

    def apply_update(self, index: int, signal: Optional[int] = None, condition: Optional[int] = None) -> Optional[str]:
        """Apply runtime update to signal/condition and re-evaluate the affected index."""
        if not (0 <= index < min(len(self.signals), len(self.conditions))):
            return None
        updated = False
        if signal is not None and isinstance(signal, int) and signal >= 0:
            self.signals[index] = signal
            self.signal_tree.update(index, signal)
            self.trie.insert(signal)
            updated = True
        if condition is not None and isinstance(condition, int) and condition >= 0:
            self.conditions[index] = condition
            self.condition_tree.update(index, condition)
            updated = True
        if updated:
            self._version.add_and_get(1)
            return self._safe_evaluate_index(index)
        return None

    def ingest_from_engine(self, engine_id: str, updates: List[Tuple[int, Optional[int], Optional[int]]]) -> List[Tuple[int, Optional[str]]]:
        """
        Ingest updates from a specific engine with per-engine serialization.
        
        Args:
            engine_id: Unique identifier for the engine
            updates: List of (index, signal, condition); set any to None to skip
            
        Returns:
            List of (index, action_after_update) for those re-evaluated
        """
        lock = self._get_engine_lock(engine_id)
        results: List[Tuple[int, Optional[str]]] = []
        with lock:
            for idx, sig, cond in updates:
                action = self.apply_update(idx, sig, cond)
                results.append((idx, action))
        return results

    def ingest_one(self, engine_id: str, index: int, signal: Optional[int] = None, condition: Optional[int] = None) -> Optional[str]:
        """Convenience method for single update ingestion."""
        return self.ingest_from_engine(engine_id, [(index, signal, condition)])[0][1]

    def _safe_evaluate_index(self, idx: int, base_open_positions: Optional[int] = None) -> str:
        try:
            return self._evaluate_index(idx, base_open_positions)
        except (RuntimeError, ValueError, IndexError, AttributeError):
            return "HOLD"


def hft_bitmask_framework(trading_signals: List[int], market_conditions: List[int]) -> List[str]:
    """
    Build and manage an advanced data structure for tracking multi-layered
    bitmasks in a high-frequency trading environment, returning a list of
    recommended trade actions.
    """
    try:
        trading_signals = _sanitize_inputs(trading_signals or [])
        market_conditions = _sanitize_inputs(market_conditions or [])
        n = min(len(trading_signals), len(market_conditions))
        if n == 0:
            return []
        trading_signals = trading_signals[:n]
        market_conditions = market_conditions[:n]
        
        bit_width = mask_bit_width(trading_signals, market_conditions)
        engine = TradeEngine(trading_signals, market_conditions, bit_width)
        return engine.evaluate_all()
    except (ValueError, TypeError, RuntimeError, AttributeError):
        n = min(len(trading_signals or []), len(market_conditions or []))
        return ["HOLD"] * n


if __name__ == "__main__":
    sample_signals = [
        0b11111111,
        0b11111110,
        0b11110000,
        0b11111100,
        0b11111111,
        0b00001111,
        0b11001100,
        0b10101010,
        0b11110000,
        0b10000000,
    ]
    sample_markets = [
        0b11111111,
        0b11111100,
        0b01111000,
        0b00000001,
        0b00000000,
        0b00001100,
        0b10101010,
        0b01010101,
        0b00110000,
        0b00000001,
    ]
    
    actions = hft_bitmask_framework(sample_signals, sample_markets)
    print(actions)