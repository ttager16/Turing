from typing import Any, Dict, List, Tuple, Optional
import threading


def manage_trades(trade_data: List[Dict[str, Any]], market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Manages trades with multi-dimensional priority using segment tree and dependency graph.
    
    Priority formula: score(t) = P * L - 5 * D
    where P = new_profit, L = liquidity_impact, D = number of dependencies
    
    Higher score = higher priority (lower rank number).
    Tie-breakers: smaller D, then lexicographically smaller trade_id.
    """
    if not trade_data:
        return []
    
    with _global_lock:
        # Build dependency graph
        graph = DependencyGraph()
        
        # Create nodes with market data
        for t in trade_data:
            tid = t["trade_id"]
            base_profit = float(t.get("profit", 0))
            deps = list(t.get("dependencies", []))
            
            # Get market data updates
            md = market_data.get(tid, {})
            new_profit = float(md.get("new_profit", base_profit))
            liq_impact = float(md.get("liquidity_impact", 1.0))
            
            graph.add_or_get(tid, new_profit, liq_impact, deps)
        
        graph.rebuild_dependents()
        
        # Handle spawn/merge operations if present
        spawns = market_data.get("__spawn__", [])
        merges = market_data.get("__merge__", [])
        
        for parent, child, ratio in spawns:
            if parent in graph.nodes:
                _spawn_trade(graph, parent, child, float(ratio))
        
        for a_id, b_id, target in merges:
            if a_id in graph.nodes and b_id in graph.nodes:
                _merge_trades(graph, a_id, b_id, target)
        
        # Calculate scores: score = P * L - 5 * D
        scores_list = []
        for tid in sorted(graph.nodes.keys()):
            node = graph.nodes[tid]
            P = node.base_profit
            L = node.liquidity_impact
            D = len(node.dependencies)
            score = P * L - 5 * D
            scores_list.append((score, D, tid, node))
        
        # Sort by: score desc, D asc, trade_id asc
        scores_list.sort(key=lambda x: (-x[0], x[1], x[2]))
        
        # Build output with assigned priorities
        output = []
        for rank, (score, D, tid, node) in enumerate(scores_list, start=1):
            output.append({
                "trade_id": tid,
                "priority": rank,
                "profit": round(node.base_profit, 6),
                "dependencies": list(node.dependencies)
            })
        
        return output


# -----------------------------
# Segment Tree for advanced operations
# -----------------------------

class SegmentTree:
    """Segment tree supporting point updates and range queries."""
    __slots__ = ("n", "size", "tree")
    
    def __init__(self, values: List[float]):
        self.n = len(values)
        size = 1
        while size < self.n:
            size <<= 1
        self.size = size
        self.tree: List[Tuple[float, int]] = [(-float("inf"), -1)] * (2 * size)
        
        for i, v in enumerate(values):
            self.tree[size + i] = (v, i)
        
        for i in range(size - 1, 0, -1):
            self.tree[i] = max(self.tree[i << 1], self.tree[(i << 1) | 1])
    
    def update(self, idx: int, value: float) -> None:
        """Update value at index idx."""
        i = self.size + idx
        self.tree[i] = (value, idx)
        i >>= 1
        while i:
            self.tree[i] = max(self.tree[i << 1], self.tree[(i << 1) | 1])
            i >>= 1
    
    def range_max(self, l: int, r: int) -> Tuple[float, int]:
        """Query max in range [l, r]."""
        l += self.size
        r += self.size
        res = (-float("inf"), -1)
        while l <= r:
            if (l & 1) == 1:
                res = max(res, self.tree[l])
                l += 1
            if (r & 1) == 0:
                res = max(res, self.tree[r])
                r -= 1
            l >>= 1
            r >>= 1
        return res


# -----------------------------
# Trade Node and Dependency Graph
# -----------------------------

class TradeNode:
    """Represents a trade with dependencies."""
    __slots__ = ("trade_id", "base_profit", "dependencies", "dependents", "liquidity_impact")
    
    def __init__(self, trade_id: str, base_profit: float, 
                 liquidity_impact: float = 1.0,
                 dependencies: Optional[List[str]] = None):
        self.trade_id = trade_id
        self.base_profit = float(base_profit)
        self.liquidity_impact = float(liquidity_impact)
        self.dependencies: List[str] = list(dependencies or [])
        self.dependents: List[str] = []


class DependencyGraph:
    """Manages trade dependencies."""
    
    def __init__(self):
        self.nodes: Dict[str, TradeNode] = {}
    
    def add_or_get(self, trade_id: str, base_profit: float = 0.0,
                   liquidity_impact: float = 1.0, 
                   dependencies: Optional[List[str]] = None) -> TradeNode:
        if trade_id in self.nodes:
            node = self.nodes[trade_id]
            if dependencies is not None:
                node.dependencies = list(dependencies)
            node.base_profit = float(base_profit)
            node.liquidity_impact = float(liquidity_impact)
            return node
        
        node = TradeNode(trade_id, base_profit, liquidity_impact, dependencies)
        self.nodes[trade_id] = node
        return node
    
    def rebuild_dependents(self) -> None:
        """Rebuild dependent relationships."""
        for n in self.nodes.values():
            n.dependents.clear()
        for n in self.nodes.values():
            for d in n.dependencies:
                if d in self.nodes:
                    self.nodes[d].dependents.append(n.trade_id)
    
    def topo_order(self) -> List[str]:
        """Topological sort with cycle handling."""
        indeg = {tid: 0 for tid in self.nodes}
        for n in self.nodes.values():
            for d in n.dependencies:
                if d in self.nodes:
                    indeg[n.trade_id] += 1
        
        q = [tid for tid, deg in indeg.items() if deg == 0]
        order = []
        i = 0
        while i < len(q):
            u = q[i]
            i += 1
            order.append(u)
            for v in self.nodes[u].dependents:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        
        # Handle cycles
        remaining = sorted([tid for tid, deg in indeg.items() if deg > 0])
        order.extend(remaining)
        return order


# Global lock for concurrency safety
_global_lock = threading.RLock()


def _spawn_trade(graph: DependencyGraph, parent_id: str, child_id: str, ratio: float) -> None:
    """Spawn a child trade from parent."""
    parent = graph.nodes[parent_id]
    child_profit = max(0.0, parent.base_profit * ratio)
    parent.base_profit *= (1.0 - ratio)
    graph.add_or_get(child_id, child_profit, parent.liquidity_impact, list(parent.dependencies))
    graph.rebuild_dependents()


def _merge_trades(graph: DependencyGraph, a_id: str, b_id: str, target_id: str) -> None:
    """Merge two trades into target."""
    a = graph.nodes[a_id]
    b = graph.nodes[b_id]
    new_profit = a.base_profit + b.base_profit
    new_liq = (a.liquidity_impact + b.liquidity_impact) / 2.0
    new_deps = sorted(set(a.dependencies + b.dependencies) - {target_id})
    graph.add_or_get(target_id, new_profit, new_liq, new_deps)
    
    # Remove merged nodes
    to_remove = {a_id, b_id} - {target_id}
    for rid in to_remove:
        if rid in graph.nodes:
            del graph.nodes[rid]
    
    graph.rebuild_dependents()