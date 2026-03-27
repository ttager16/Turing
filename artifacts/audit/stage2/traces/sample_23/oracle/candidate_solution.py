from typing import List

LAY_SOURCE = 1 << 120
LAY_CONSUMER = 1 << 121
LAY_FAULT = 1 << 122
LAY_REACTIVE = 1 << 123
LAY_BALANCED = 1 << 124
LAY_FAILOVER = 1 << 125
HEARTBEAT_OK = 1 << 126
HEARTBEAT_FAIL = 1 << 127


class DisjointSetUnion:
    """Minimal DSU to model connectivity groups for failover reroutes."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


class SegmentTree:
    """Simple segment tree for point updates and range sum queries."""

    def __init__(self, size: int) -> None:
        n = 1
        while n < size:
            n <<= 1
        self.n = n
        self.data = [0] * (2 * n)

    def update(self, idx: int, delta: int) -> None:
        i = idx + self.n
        self.data[i] += delta
        i >>= 1
        while i >= 1:
            self.data[i] = self.data[2 * i] + self.data[2 * i + 1]
            i >>= 1

    def range_sum(self, left: int, right: int) -> int:
        # inclusive-exclusive [left, right)
        res = 0
        l = left + self.n
        r = right + self.n
        while l < r:
            if l & 1:
                res += self.data[l]
                l += 1
            if r & 1:
                r -= 1
                res += self.data[r]
            l >>= 1
            r >>= 1
        return res


def _bitwise_or(values: List[int]) -> int:
    """Compute bitwise OR across all integers in a list."""
    result = 0
    for value in values:
        result |= int(value)
    return result


class MinCostMaxFlow:
    """Adjacency-list MCMF with SPFA (sufficient for small B)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.adj = [[] for _ in range(n)]
        self.to = []
        self.cap = []
        self.cost = []
        self.rev = []

    def add_edge(self, u: int, v: int, capacity: int, edge_cost: int) -> None:
        if capacity <= 0:
            return
        self.adj[u].append(len(self.to))
        self.to.append(v)
        self.cap.append(capacity)
        self.cost.append(edge_cost)
        self.rev.append(len(self.to))
        self.adj[v].append(len(self.to))
        self.to.append(u)
        self.cap.append(0)
        self.cost.append(-edge_cost)
        self.rev.append(len(self.to) - 2)

    def min_cost_max_flow(self, s: int, t: int) -> (int, int):
        n = self.n
        total_flow = 0
        total_cost = 0
        INF = 10 ** 18
        while True:
            dist = [INF] * n
            inq = [False] * n
            parent_edge = [-1] * n
            dist[s] = 0
            queue = [s]
            inq[s] = True
            qi = 0
            while qi < len(queue):
                u = queue[qi]
                qi += 1
                inq[u] = False
                for ei in self.adj[u]:
                    if self.cap[ei] <= 0:
                        continue
                    v = self.to[ei]
                    nd = dist[u] + self.cost[ei]
                    if nd < dist[v]:
                        dist[v] = nd
                        parent_edge[v] = ei
                        if not inq[v]:
                            inq[v] = True
                            queue.append(v)
            if parent_edge[t] == -1:
                break
            add_flow = INF
            v = t
            while v != s:
                ei = parent_edge[v]
                add_flow = min(add_flow, self.cap[ei])
                v = self.to[self.rev[ei]]
            v = t
            while v != s:
                ei = parent_edge[v]
                self.cap[ei] -= add_flow
                self.cap[self.rev[ei]] += add_flow
                total_cost += add_flow * self.cost[ei]
                v = self.to[self.rev[ei]]
            total_flow += add_flow
        return total_flow, total_cost


def optimize_energy_distribution(
    nodes: List[int],
    energy_sources: List[int],
    energy_consumers: List[int],
) -> List[int]:
    """Optimize energy distribution using layered bitmask semantics and flow projection."""

    if not nodes and not energy_sources and not energy_consumers:
        return []

    if nodes and not energy_sources and not energy_consumers:
        return list(nodes)

    source_mask = _bitwise_or(energy_sources)
    consumer_mask = _bitwise_or(energy_consumers)

    dsu = DisjointSetUnion(len(nodes) if nodes else 1)
    healthy_indices = []
    failed_indices = []
    for idx, value in enumerate(nodes):
        val = int(value)
        if (val & HEARTBEAT_FAIL) != 0 and (val & HEARTBEAT_OK) == 0:
            failed_indices.append(idx)
        else:
            healthy_indices.append(idx)
    for i in range(len(healthy_indices) - 1):
        dsu.union(healthy_indices[i], healthy_indices[i + 1])

    max_bit = max(source_mask.bit_length(), consumer_mask.bit_length(), 1)
    seg_supply = SegmentTree(max_bit)
    seg_demand = SegmentTree(max_bit)

    supply_counts = [0] * max_bit
    demand_counts = [0] * max_bit
    for src in energy_sources:
        v = int(src)
        b = 0
        while v:
            if v & 1:
                supply_counts[b] += 1
            v >>= 1
            b += 1
    for con in energy_consumers:
        v = int(con)
        b = 0
        while v:
            if v & 1:
                demand_counts[b] += 1
            v >>= 1
            b += 1
    for bit in range(max_bit):
        if supply_counts[bit] > 0:
            seg_supply.update(bit, supply_counts[bit])
        if demand_counts[bit] > 0:
            seg_demand.update(bit, demand_counts[bit])

    total_supply_units = seg_supply.range_sum(0, max_bit)
    total_demand_units = seg_demand.range_sum(0, max_bit)

    num_failed = len(failed_indices)
    any_fault = num_failed > 0

    def run_flow(reduction_per_bit: int) -> int:
        B = max_bit
        s = 0
        t = 1 + 2 * B
        mcmf = MinCostMaxFlow(t + 1)
        for i in range(B):
            cap = max(0, supply_counts[i] - reduction_per_bit)
            if cap > 0:
                mcmf.add_edge(s, 1 + i, cap, 0)
            dem = demand_counts[i]
            if dem > 0:
                mcmf.add_edge(1 + B + i, t, dem, 0)
        for i in range(B):
            cap_i = max(0, supply_counts[i] - reduction_per_bit)
            if cap_i <= 0:
                continue
            for j in range(B):
                if demand_counts[j] <= 0:
                    continue
                cost = abs(i - j)
                mcmf.add_edge(1 + i, 1 + B + j, demand_counts[j], cost)
        flow, _ = mcmf.min_cost_max_flow(s, t)
        return flow

    flow_normal = run_flow(0)
    flow_failover = flow_normal
    if any_fault:
        flow_failover = run_flow(num_failed)

    balanced = flow_failover >= total_demand_units
    reactive_needed = (consumer_mask & ~source_mask) != 0

    projection_mask = source_mask | consumer_mask
    if total_supply_units > 0:
        projection_mask |= LAY_SOURCE
    if total_demand_units > 0:
        projection_mask |= LAY_CONSUMER
    if balanced:
        projection_mask |= LAY_BALANCED
    if reactive_needed:
        projection_mask |= LAY_REACTIVE
    if any_fault:
        projection_mask |= (LAY_FAULT | LAY_FAILOVER)

    optimized_nodes: List[int] = []
    for idx, node_value in enumerate(nodes):
        base = int(node_value)
        if idx in failed_indices:
            new_value = base | (projection_mask & ~(LAY_BALANCED)) | LAY_FAILOVER | LAY_FAULT
        else:
            new_value = base | projection_mask
        optimized_nodes.append(new_value)

    return optimized_nodes