import hashlib
import math
import heapq
import random
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set, Any


class PreferenceTrieNode:
    def __init__(self) -> None:
        self.children: Dict[str, PreferenceTrieNode] = {}
        self.module_ids: Set[int] = set()


class PreferenceTrie:
    """Trie for efficient module indexing by attributes."""

    def __init__(self) -> None:
        self.root = PreferenceTrieNode()

    def _insert_path(self, keys: List[str], module_id: int) -> None:
        node = self.root
        for key in keys:
            if key not in node.children:
                node.children[key] = PreferenceTrieNode()
            node = node.children[key]
            node.module_ids.add(module_id)

    def index_module(self, module: Dict[str, Any]) -> None:
        module_id = int(module.get("id"))
        module_type = str(module.get("type", ""))
        subject = str(module.get("subject", ""))
        if module_type or subject:
            self._insert_path([module_type, subject], module_id)
        if subject:
            self._insert_path(["", subject], module_id)

    def update_preference(self, keys: List[str], affected_module_ids: Set[int]) -> None:
        """Update trie nodes with affected module IDs."""
        node = self.root
        for key in keys:
            if key not in node.children:
                node.children[key] = PreferenceTrieNode()
            node = node.children[key]
            node.module_ids.update(affected_module_ids)

    def partial_match(self, keys_prefix: List[str]) -> Set[int]:
        node = self.root
        for key in keys_prefix:
            if key not in node.children:
                return set()
            node = node.children[key]
        return set(node.module_ids)

    def preference_score(self, module: Dict[str, Any], preferences: Dict[str, List[str]]) -> float:
        """Compute preference score using trie validation with type and subject checks."""
        module_id = int(module.get("id"))
        module_type = str(module.get("type", ""))
        subject = str(module.get("subject", ""))

        preferred_types = [str(x) for x in preferences.get("format", [])]
        preferred_subjects = [str(x) for x in preferences.get("topic_focus", [])]

        score = 0.0
        if module_type and module_id in self.partial_match([module_type]):
            if module_type in preferred_types:
                score += 0.5
        if subject and (
            module_id in self.partial_match([module_type, subject])
            or module_id in self.partial_match(["", subject])
        ):
            if subject in preferred_subjects:
                score += 0.5

        return max(0.0, min(1.0, score))


@dataclass
class _Edge:
    to: int
    rev: int
    cap: int
    cost: float


class MinCostMaxFlow:
    """Min-cost max-flow with Johnson potentials (reduced costs + Dijkstra)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.graph: List[List[_Edge]] = [[] for _ in range(n)]

    def add_edge(self, u: int, v: int, cap: int, cost: float) -> None:
        self.graph[u].append(_Edge(v, len(self.graph[v]), cap, cost))
        self.graph[v].append(_Edge(u, len(self.graph[u]) - 1, 0, -cost))

    def min_cost_flow(self, s: int, t: int, maxf: int) -> Tuple[int, float]:
        flow = 0
        cost = 0.0
        # Potentials
        pi = [0.0] * self.n

        while flow < maxf:
            dist = [math.inf] * self.n
            pv = [-1] * self.n
            pe = [-1] * self.n
            dist[s] = 0.0
            pq: List[Tuple[float, int]] = [(0.0, s)]

            while pq:
                d, u = heapq.heappop(pq)
                if d != dist[u]:
                    continue
                for ei, e in enumerate(self.graph[u]):
                    if e.cap <= 0:
                        continue
                    rcost = e.cost + pi[u] - pi[e.to]
                    nd = d + rcost
                    if nd < dist[e.to]:
                        dist[e.to] = nd
                        pv[e.to] = u
                        pe[e.to] = ei
                        heapq.heappush(pq, (nd, e.to))

            if dist[t] == math.inf:
                break

            # update potentials
            for v in range(self.n):
                if dist[v] < math.inf:
                    pi[v] += dist[v]

            # augment
            addf = maxf - flow
            v = t
            while v != s:
                u = pv[v]
                e = self.graph[u][pe[v]]
                addf = min(addf, e.cap)
                v = u

            v = t
            path_cost = 0.0
            while v != s:
                u = pv[v]
                e = self.graph[u][pe[v]]
                e.cap -= addf
                self.graph[v][e.rev].cap += addf
                path_cost += e.cost
                v = u

            flow += addf
            cost += path_cost * addf

        return flow, cost


class SegmentTree:
    def __init__(self, n: int) -> None:
        self.n = 1
        while self.n < n:
            self.n *= 2
        self.data = [0.0] * (2 * self.n)
        self.lazy = [0.0] * (2 * self.n)

    def _push(self, idx: int) -> None:
        if self.lazy[idx] != 0.0:
            self.data[idx * 2] += self.lazy[idx]
            self.data[idx * 2 + 1] += self.lazy[idx]
            self.lazy[idx * 2] += self.lazy[idx]
            self.lazy[idx * 2 + 1] += self.lazy[idx]
            self.lazy[idx] = 0.0

    def range_add(self, l: int, r: int, val: float) -> None:
        def _add(idx: int, nl: int, nr: int) -> None:
            if r <= nl or nr <= l:
                return
            if l <= nl and nr <= r:
                self.data[idx] += val
                self.lazy[idx] += val
                return
            self._push(idx)
            mid = (nl + nr) // 2
            _add(idx * 2, nl, mid)
            _add(idx * 2 + 1, mid, nr)
        _add(1, 0, self.n)

    def point_get(self, pos: int) -> float:
        idx = 1
        l, r = 0, self.n
        res = 0.0
        while r - l > 1:
            res += self.lazy[idx]
            mid = (l + r) // 2
            if pos < mid:
                idx = idx * 2
                r = mid
            else:
                idx = idx * 2 + 1
                l = mid
        return res + self.data[idx]


class HeavyLightDecomposition:
    """HLD for learning path tree with segment tree support."""

    def __init__(self, root: int, adjacency: Dict[int, List[int]]) -> None:
        self.root = root
        self.adjacency = adjacency
        self.parent: Dict[int, int] = {}
        self.depth: Dict[int, int] = {}
        self.size: Dict[int, int] = {}
        self.heavy: Dict[int, Optional[int]] = {}
        self.head: Dict[int, int] = {}
        self.pos: Dict[int, int] = {}
        self.order: List[int] = []

        self._dfs(root, -1)
        self._decompose(root, root)
        self.segment_tree = SegmentTree(len(self.order))

    def _dfs(self, u: int, p: int) -> None:
        self.parent[u] = p
        self.depth[u] = 0 if p == -1 else self.depth[p] + 1
        self.size[u] = 1
        max_size = 0
        self.heavy[u] = None
        for v in self.adjacency.get(u, []):
            if v == p:
                continue
            self._dfs(v, u)
            self.size[u] += self.size[v]
            if self.size[v] > max_size:
                max_size = self.size[v]
                self.heavy[u] = v

    def _decompose(self, u: int, h: int) -> None:
        self.head[u] = h
        self.pos[u] = len(self.order)
        self.order.append(u)
        if self.heavy[u] is not None:
            self._decompose(self.heavy[u], h)
            for v in self.adjacency.get(u, []):
                if v != self.parent[u] and v != self.heavy[u]:
                    self._decompose(v, v)

    def _apply_path(self, u: int, v: int, value: float) -> None:
        while self.head[u] != self.head[v]:
            if self.depth[self.head[u]] < self.depth[self.head[v]]:
                u, v = v, u
            hu = self.head[u]
            self.segment_tree.range_add(self.pos[hu], self.pos[u] + 1, value)
            u = self.parent[hu]
        if self.depth[u] > self.depth[v]:
            u, v = v, u
        self.segment_tree.range_add(self.pos[u], self.pos[v] + 1, value)

    def add_difficulty_on_path(self, u: int, v: int, delta: float) -> None:
        self._apply_path(u, v, delta)

    def node_difficulty_bias(self, u: int) -> float:
        return self.segment_tree.point_get(self.pos[u])


class ProbabilisticRefiner:
    """Bayesian estimator for mastery probability and difficulty adjustment."""

    def __init__(self, performance_history: List[float], engagement_over_time: List[str], rng_seed: Optional[int] = None) -> None:
        self.performance_history = performance_history[:]
        self.engagement_over_time = engagement_over_time[:]
        self._rng = random.Random(rng_seed)  

    @staticmethod
    def _engagement_weight(level: str) -> float:
        level = level.lower()
        if level == "high":
            return 1.1
        if level == "medium":
            return 1.0
        if level == "low":
            return 0.9
        return 1.0

    def mastery_probability(self) -> float:
        if not self.performance_history:
            return 0.5
        mean_score = sum(self.performance_history) / len(self.performance_history)
        variance = (
            sum((x - mean_score) ** 2 for x in self.performance_history) / max(1, len(self.performance_history) - 1)
        )
        engagement_factor = sum(self._engagement_weight(e) for e in self.engagement_over_time) / max(1, len(self.engagement_over_time))
        z = (mean_score - 70) / 10.0 - math.sqrt(max(0.0, variance)) / 50.0
        z *= engagement_factor
        prob = 1.0 / (1.0 + math.exp(-z))
        return max(0.05, min(0.95, prob))

    def difficulty_adjustment(self, base_difficulty: float) -> float:
        p = self.mastery_probability()
        centered = (p - 0.5) * 1.4
        baseline_factor = 1.0 - (base_difficulty - 3.0) * 0.05
        baseline_factor = max(0.7, min(1.3, baseline_factor))
        return centered * baseline_factor

    def multi_phase_sampling(self, num_questions: int = 5) -> List[Tuple[int, bool]]:
        p = self.mastery_probability()
        results: List[Tuple[int, bool]] = []
        for q in range(num_questions):
            correct = (self._rng.random() < p)
            results.append((q, correct))
            if correct:
                self.performance_history.append(80 + 20 * self._rng.random())
            else:
                self.performance_history.append(50 + 20 * self._rng.random())
        return results


def _build_tree_from_nested_dict(tree: Dict[str, Any]) -> Tuple[int, Dict[int, List[int]]]:
    adjacency: Dict[int, List[int]] = {}

    def dfs(node_obj: Dict[str, Any]) -> int:
        node_id = int(node_obj.get("node"))
        children = node_obj.get("children", [])
        adjacency.setdefault(node_id, [])
        for child in children:
            child_id = dfs(child)
            adjacency[node_id].append(child_id)
            adjacency.setdefault(child_id, []).append(node_id)
        return node_id

    root = dfs(tree)
    return root, adjacency


def _distribute_budget(values: List[float], budget: float) -> List[float]:
    """Largest Remainder (Hare–Niemeyer) to 2 decimals; deterministic."""
    if not values:
        return []
    nonneg = [max(0.0, v) for v in values]
    total = sum(nonneg)
    n = len(values)
    if total <= 0:
        base = budget / n
        raw = [base] * n
    else:
        raw = [budget * v / total for v in nonneg]

    floored = [math.floor(x * 100.0) / 100.0 for x in raw]
    cents = int(round((budget - sum(floored)) * 100.0))
    rema = sorted([(i, raw[i] - floored[i]) for i in range(n)],
                  key=lambda t: t[1], reverse=True)
    out = floored[:]
    for k in range(cents):
        out[rema[k][0]] += 0.01
    return out


def personalize_learning(student_profile: Dict[str, Any], learning_modules: List[Dict[str, Any]], constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Personalize learning path using trie, flow network, HLD, and probabilistic refinement."""
    trie = PreferenceTrie()
    for mod in learning_modules:
        trie.index_module(mod)

    current_tree = student_profile.get("current_path_tree")
    if current_tree and isinstance(current_tree, dict) and current_tree:
        root, adjacency = _build_tree_from_nested_dict(current_tree)
        hld = HeavyLightDecomposition(root, adjacency)
    else:
        root = 1
        hld = HeavyLightDecomposition(root, {root: []})

    performance_history = [float(x) for x in student_profile.get("performance_history", [])]
    engagement_over_time = [str(x) for x in student_profile.get("engagement_over_time", [])]

    # deterministic seed from student_profile["id"] (int or stable hash of string)
    sid = student_profile.get("id", "")
    if isinstance(sid, (int, float)) and not isinstance(sid, bool):
        seed_int = int(sid)
    else:
        seed_int = int(hashlib.md5(str(sid).encode("utf-8")).hexdigest(), 16) % (2**32)

    refiner = ProbabilisticRefiner(performance_history, engagement_over_time, rng_seed=seed_int)
    # Integrate quiz refinement
    _ = refiner.multi_phase_sampling(num_questions=3)

    priority_subjects = [str(x) for x in constraints.get("priority_subjects", [])]

    module_scores: List[float] = []
    updated_difficulties: List[float] = []
    module_ids: List[int] = []

    for mod in learning_modules:
        module_id = int(mod.get("id"))
        module_ids.append(module_id)
        base_difficulty = float(mod.get("difficulty", 3.0))

        pref_score = trie.preference_score(mod, student_profile.get("preferences", {}))
        subject = str(mod.get("subject", ""))

        # slight boost for priority subjects
        if subject in priority_subjects:
            pref_score = min(1.0, pref_score + 0.1)

        # small path-depth bias
        node_for_bias = module_id if module_id in hld.pos else root
        depth_bias = 0.02 * hld.depth.get(node_for_bias, 0)

        diff_adj = refiner.difficulty_adjustment(base_difficulty)

        # bounded aggregate
        score = max(0.0, min(1.0,
                             0.65 * pref_score +
                             0.25 * (0.5 + diff_adj / 2.0) +
                             0.10 * (0.5 + depth_bias)))
        module_scores.append(score)

        updated_difficulties.append(base_difficulty + diff_adj)

    # Build a selection network: pick up to K modules by min cost (cost = 1 - score)
    n = len(learning_modules)
    source = 0
    sink = n + 1
    mcmf = MinCostMaxFlow(n + 2)

    # interpret max_concurrent_modules
    try:
        max_concurrent = int(constraints.get("max_concurrent_modules", n))
    except (ValueError, TypeError):
        max_concurrent = n
    if max_concurrent <= 0:
        max_concurrent = n  

    # edges: source-(cap1,cost)-module, module-(cap1,0)-sink
    unit_costs: List[float] = []
    for i, score in enumerate(module_scores, start=1):
        unit_cost = 1.0 - score  # lower is better
        unit_costs.append(unit_cost)
        mcmf.add_edge(source, i, 1, unit_cost)
        mcmf.add_edge(i, sink, 1, 0.0)

    # run selection
    mcmf.min_cost_flow(source, sink, max_concurrent)

    # determine which modules got selected
    used = [0] * n
    for e in mcmf.graph[source]:
        if 1 <= e.to <= n:
            used[e.to - 1] = 1 - e.cap  # 1 if selected, else 0

    budget = float(constraints.get("max_flow_cost", 100.0))
    sel = [i for i, u in enumerate(used) if u == 1]
    # If unlimited concurrency, all modules will be selectable; if K < n, top K chosen

    allocated_costs = [0.0] * n
    if sel:
        # Pro-quality split among selected modules
        weights = [max(module_scores[i], 1e-9) for i in sel]
        alloc_sel = _distribute_budget(weights, budget)
        for idx, val in zip(sel, alloc_sel):
            allocated_costs[idx] = val
    else:
        # Edge case: no feasible selection -> all zeros
        allocated_costs = [0.0] * n

    # Enforce max difficulty spread
    if updated_difficulties:
        max_spread = float(constraints.get("max_difficulty_spread", 2.0))
        mean_diff = sum(updated_difficulties) / len(updated_difficulties)
        min_allowed = mean_diff - max_spread / 2.0
        max_allowed = mean_diff + max_spread / 2.0
        updated_difficulties = [max(min_allowed, min(max_allowed, d)) for d in updated_difficulties]

    # Build ordered output with 2-decimal rounding
    learning_path = []
    for module_id, alloc, upd in zip(module_ids, allocated_costs, updated_difficulties):
        learning_path.append(
            {
                "module_id": module_id,
                "allocated_flow_cost": float(round(alloc, 2)),
                "updated_difficulty": float(round(upd, 2)),
            }
        )

    return {"learning_path": learning_path}


if __name__ == "__main__":
    student_profile = {
        "id": 456,
        "performance_history": [85, 92, 88],
        "engagement_over_time": ["medium", "high", "low", "medium"],
        "preferences": {
            "format": ["interactive", "game-based"],
            "topic_focus": ["mathematics", "physics"]
        },
        "current_path_tree": {
            "node": 1,
            "children": [
                {"node": 2, "children": []},
                {
                    "node": 3,
                    "children": [
                        {"node": 4, "children": []}
                    ]
                }
            ]
        }
    }

    learning_modules = [
        {"id": 10, "type": "interactive", "subject": "mathematics", "difficulty": 4},
        {"id": 11, "type": "game-based", "subject": "physics", "difficulty": 5},
        {"id": 12, "type": "visual", "subject": "mathematics", "difficulty": 3}
    ]

    constraints = {
        "max_flow_cost": 100,
        "priority_subjects": ["mathematics", "physics"],
        "max_difficulty_spread": 2
    }
    output = personalize_learning(student_profile, learning_modules, constraints)
    print(json.dumps(output, indent=2))