import logging
import math
import time
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SegmentTree:
    """
    Segment Tree with lazy propagation for efficient range updates.
    Supports O(log n) range assignments and O(log n) point queries.
    """

    def __init__(self, size: int):
        """Initialize segment tree for given size."""
        self.size = 1
        while self.size < size:
            self.size <<= 1
        self.tree: List[Optional[float]] = [None] * (2 * self.size)
        self.lazy: List[Optional[float]] = [None] * (2 * self.size)

    def _push(self, idx: int) -> None:
        """Push lazy value to children."""
        if self.lazy[idx] is not None:
            left = idx << 1
            right = left | 1
            if left < len(self.lazy):
                self.lazy[left] = self.lazy[idx]
                self.tree[left] = self.lazy[idx]
            if right < len(self.lazy):
                self.lazy[right] = self.lazy[idx]
                self.tree[right] = self.lazy[idx]
            self.lazy[idx] = None

    def range_assign(self, left: int, right: int, value: float) -> None:
        """Assign value to range [left, right] in O(log n)."""
        self._range_assign(1, 0, self.size - 1, left, right, value)

    def _range_assign(self, idx: int, node_left: int, node_right: int,
                     query_left: int, query_right: int, value: float) -> None:
        """Helper for range assignment."""
        if query_right < node_left or node_right < query_left:
            return
        if query_left <= node_left and node_right <= query_right:
            self.lazy[idx] = value
            self.tree[idx] = value
            return
        self._push(idx)
        mid = (node_left + node_right) >> 1
        self._range_assign(idx << 1, node_left, mid, query_left, query_right, value)
        self._range_assign((idx << 1) | 1, mid + 1, node_right, query_left, query_right, value)

    def point_query(self, pos: int) -> Optional[float]:
        """Query value at position in O(log n)."""
        idx = 1
        node_left = 0
        node_right = self.size - 1
        result = self.tree[idx]
        
        while node_left != node_right:
            if self.lazy[idx] is not None:
                self._push(idx)
            mid = (node_left + node_right) >> 1
            if pos <= mid:
                idx = idx << 1
                node_right = mid
            else:
                idx = (idx << 1) | 1
                node_left = mid + 1
            if self.tree[idx] is not None:
                result = self.tree[idx]
        
        return result


class GraphAnalyzer:
    """
    Network topology analyzer for identifying critical network channels.
    """

    def __init__(self, num_nodes: int, edges: List[List[int]]):
        """
        Initialize network topology analyzer.

        Args:
            num_nodes: Number of transmission channels in the network
            edges: Directional microwave links as [source, destination] pairs
        """
        self.num_nodes = num_nodes
        self.adjacency_list: Dict[int, List[int]] = {i: [] for i in range(num_nodes)}
        self.reverse_adjacency_list: Dict[int, List[int]] = {i: [] for i in range(num_nodes)}
        self.in_degree: List[int] = [0] * num_nodes
        self.out_degree: List[int] = [0] * num_nodes

        for source, dest in edges:
            if 0 <= source < num_nodes and 0 <= dest < num_nodes:
                self.adjacency_list[source].append(dest)
                self.reverse_adjacency_list[dest].append(source)
                self.out_degree[source] += 1
                self.in_degree[dest] += 1

        # Compute strongly connected components (SCCs)
        self.scc_ids = self._compute_sccs()
        
        # Identify nodes that participate in cycles
        self.in_cycle = self._find_cycle_nodes()
        
        # Pre-compute bridge nodes for efficient O(1) lookup
        self.bridge_nodes = self._find_all_bridge_nodes()
        # Union with undirected articulation points to catch bridges in trees/DAGs
        self.bridge_nodes |= self._undirected_articulation_points()
        
        logger.debug(f"Graph initialized with {num_nodes} nodes and {len(edges)} edges")

    def _compute_sccs(self) -> List[int]:
        """Compute strongly connected components using Tarjan's algorithm."""
        # Initialize
        index = 0
        indices = [-1] * self.num_nodes
        lowlinks = [-1] * self.num_nodes
        on_stack = [False] * self.num_nodes
        stack = []
        scc_id = 0
        scc_ids = [-1] * self.num_nodes
        
        def strongconnect(v):
            nonlocal index, scc_id
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack[v] = True
            
            for w in self.adjacency_list[v]:
                if indices[w] == -1:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack[w]:
                    lowlinks[v] = min(lowlinks[v], indices[w])
            
            if lowlinks[v] == indices[v]:
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc_ids[w] = scc_id
                    if w == v:
                        break
                scc_id += 1
        
        for v in range(self.num_nodes):
            if indices[v] == -1:
                strongconnect(v)
        
        return scc_ids

    def _find_cycle_nodes(self) -> List[bool]:
        """Find nodes that participate in cycles."""
        in_cycle = [False] * self.num_nodes
        
        # Nodes in SCCs with size > 1 are in cycles
        scc_sizes = {}
        for scc_id in self.scc_ids:
            scc_sizes[scc_id] = scc_sizes.get(scc_id, 0) + 1
        
        for i in range(self.num_nodes):
            if scc_sizes[self.scc_ids[i]] > 1:
                in_cycle[i] = True
        
        return in_cycle

    def has_outgoing_edges(self, node: int) -> bool:
        """Check if a node has outgoing edges."""
        return self.out_degree[node] > 0

    def has_incoming_edges(self, node: int) -> bool:
        """Check if a node has incoming edges."""
        return self.in_degree[node] > 0

    def get_neighbors(self, node: int) -> List[int]:
        """Get all neighbors (outgoing edges) of a node."""
        return self.adjacency_list.get(node, [])

    def _find_all_bridge_nodes(self) -> set:
        """Pre-compute all bridge nodes in O(n+m) time during initialization."""
        bridge_nodes = set()
        
        # For each SCC with size > 1, check which nodes are bridges
        scc_sizes = {}
        for scc_id in self.scc_ids:
            scc_sizes[scc_id] = scc_sizes.get(scc_id, 0) + 1
        
        # Process each non-trivial SCC
        for scc_id, size in scc_sizes.items():
            if size <= 1:
                continue
            
            # Get all nodes in this SCC
            nodes_in_scc = [i for i in range(self.num_nodes) if self.scc_ids[i] == scc_id]
            
            # Check each node in the SCC
            for node in nodes_in_scc:
                if self._is_bridge_in_scc(node, nodes_in_scc):
                    bridge_nodes.add(node)
        
        return bridge_nodes
    
    def _is_bridge_in_scc(self, node: int, nodes_in_scc: List[int]) -> bool:
        """Check if a node is a bridge within its SCC (helper method)."""
        if len(nodes_in_scc) <= 1:
            return False
        
        # Build local adjacency without this node
        local_adj = {}
        for u in nodes_in_scc:
            if u == node:
                continue
            if u not in local_adj:
                local_adj[u] = []
            for v in self.adjacency_list[u]:
                if v != node and v in nodes_in_scc:
                    local_adj[u].append(v)
        
        # Count SCCs in the reduced graph
        remaining_nodes = [u for u in nodes_in_scc if u != node]
        if not remaining_nodes:
            return False
        
        local_scc_count = self._count_sccs_in_subgraph(remaining_nodes, local_adj)
        
        # If removal increased SCC count from 1 to > 1, it's a bridge
        return local_scc_count > 1
    
    def is_bridge_node(self, node: int) -> bool:
        """Check if this channel is a bridge node (prevents network fragmentation).
        
        Uses pre-computed results from initialization for O(1) lookup.
        """
        return node in self.bridge_nodes
    
    def _count_sccs_in_subgraph(self, nodes: List[int], local_adj: Dict[int, List[int]]) -> int:
        """Count strongly connected components in a subgraph using Tarjan's algorithm."""
        if not nodes:
            return 0
        
        index = 0
        indices = {}
        lowlinks = {}
        on_stack = {}
        stack = []
        scc_count = 0
        
        for node in nodes:
            indices[node] = -1
            on_stack[node] = False
        
        def strongconnect(v: int):
            nonlocal index, scc_count
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack[v] = True
            
            if v in local_adj:
                for w in local_adj[v]:
                    if w not in indices or indices[w] == -1:
                        strongconnect(w)
                        lowlinks[v] = min(lowlinks[v], lowlinks[w])
                    elif on_stack[w]:
                        lowlinks[v] = min(lowlinks[v], indices[w])
            
            if lowlinks[v] == indices[v]:
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    if w == v:
                        break
                scc_count += 1
        
        for node in nodes:
            if indices[node] == -1:
                strongconnect(node)
        
        return scc_count

    def is_articulation_point(self, node: int) -> bool:
        """Check if this channel is a critical articulation point (maintains redundancy)."""
        return (self.in_degree[node] >= 1 and self.out_degree[node] >= 1 
                and self.in_cycle[node])

    def is_critical_node(self, node: int) -> bool:
        """Determine if a node is critical (legacy method for compatibility)."""
        return self.has_incoming_edges(node) and self.has_outgoing_edges(node)

    def is_source_node(self, node: int) -> bool:
        """Check if this channel is a source (tower uplink with no incoming connections)."""
        return self.in_degree[node] == 0 and self.out_degree[node] > 0

    def is_sink_node(self, node: int) -> bool:
        """Check if this channel is a sink (customer-facing endpoint with no outgoing connections)."""
        return self.in_degree[node] > 0 and self.out_degree[node] == 0

    def _undirected_articulation_points(self) -> set:
        """Find articulation points on the undirected projection (O(n+m))."""
        # Build undirected adjacency
        undirected = {i: set() for i in range(self.num_nodes)}
        for u in range(self.num_nodes):
            for v in self.adjacency_list[u]:
                undirected[u].add(v)
                undirected[v].add(u)

        time = 0
        disc = [-1] * self.num_nodes
        low = [0] * self.num_nodes
        parent = [-1] * self.num_nodes
        ap = set()

        def dfs(u: int):
            nonlocal time
            children = 0
            disc[u] = low[u] = time
            time += 1
            for v in undirected[u]:
                if disc[v] == -1:
                    parent[v] = u
                    children += 1
                    dfs(v)
                    low[u] = min(low[u], low[v])
                    # root with 2+ children OR non-root where low[v] >= disc[u]
                    if (parent[u] == -1 and children > 1) or (parent[u] != -1 and low[v] >= disc[u]):
                        ap.add(u)
                elif v != parent[u]:
                    low[u] = min(low[u], disc[v])

        for u in range(self.num_nodes):
            if disc[u] == -1:
                dfs(u)

        return ap


def multi_stage_adaptive_filter(
    channels: List[float],
    edges: List[List[int]],
    threshold_updates: List[List[float]],
    max_latency_ms: float
) -> List[float]:
    """
    Multi-stage adaptive filter for wireless network performance monitoring.
    """
    start_time = time.perf_counter()
    
    logger.info(f"Starting adaptive filter with {len(channels)} channels, "
                f"{len(edges)} edges, {len(threshold_updates)} threshold updates, "
                f"max latency: {max_latency_ms}ms")

    # Handle empty input
    if not channels:
        logger.info("Empty channel list provided, returning empty result")
        return []

    num_channels = len(channels)
    result = channels.copy()

    # Initialize graph analyzer for topology-aware decisions
    graph_analyzer = GraphAnalyzer(num_channels, edges)

    # Initialize segment tree for O(log n) threshold updates
    seg_tree = SegmentTree(num_channels)

    # Process threshold updates using segment tree for efficiency
    # Supports both 2-tuple (idx, threshold) and 3-tuple (left, right, threshold) formats
    # Total complexity: O(k log n) for k updates
    for update in threshold_updates:
        if not update:
            logger.warning("Malformed threshold update: empty payload; ignoring.")
            continue
        
        if len(update) == 2:
            # Standard point update: O(log n)
            channel_idx, threshold_value = update
            if 0 <= channel_idx < num_channels:
                seg_tree.range_assign(channel_idx, channel_idx, threshold_value)
                logger.debug(f"Applied threshold update: channel {channel_idx} -> {threshold_value}")
        elif len(update) == 3:
            # Range update: O(log n) - critical for performance
            left, right, threshold_value = update
            if left > right:
                left, right = right, left
            left = max(0, left)
            right = min(num_channels - 1, right)
            if left <= right:
                seg_tree.range_assign(left, right, threshold_value)
                logger.debug(f"Applied range threshold update: channels {left}-{right} -> {threshold_value}")
        else:
            logger.warning(f"Malformed threshold update (expected 2 or 3 items): {update}; ignoring.")
            continue

    # Check timing constraint during threshold processing
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if elapsed_ms > max_latency_ms * 0.5:
        logger.warning(f"Threshold processing took {elapsed_ms:.2f}ms (50% of budget)")

    # Query segment tree for each channel: O(n log n)
    # Build threshold mapping for channels that have updates
    thresholds: Dict[int, float] = {}
    for channel_idx in range(num_channels):
        threshold = seg_tree.point_query(channel_idx)
        if threshold is not None:
            thresholds[channel_idx] = threshold

    # Apply multi-stage filtering with graph-aware logic: O(n)
    for channel_idx in range(num_channels):
        if channel_idx in thresholds:
            threshold = thresholds[channel_idx]
            current_value = result[channel_idx]

            # Handle NaN values: always suppress (NaN comparisons are always False)
            if math.isnan(current_value):
                result[channel_idx] = 0.0
                logger.debug(f"Channel {channel_idx} suppressed: NaN value")
                continue

            # Check if channel value meets threshold
            if current_value < threshold:
                # Apply graph-aware decision making
                should_suppress = _evaluate_suppression_policy(
                    channel_idx, current_value, threshold,
                    graph_analyzer, result, thresholds
                )

                if should_suppress:
                    result[channel_idx] = 0.0
                    logger.debug(f"Channel {channel_idx} suppressed: "
                               f"value {current_value} < threshold {threshold}")
                else:
                    logger.debug(f"Channel {channel_idx} preserved despite being below threshold: "
                               f"critical for network topology")

    # Verify latency constraint
    total_elapsed_ms = (time.perf_counter() - start_time) * 1000
    if total_elapsed_ms > max_latency_ms:
        logger.warning(f"Processing exceeded latency budget: {total_elapsed_ms:.2f}ms > {max_latency_ms}ms")
    else:
        logger.info(f"Filtering complete in {total_elapsed_ms:.2f}ms. Result: {result}")

    return result


def _evaluate_suppression_policy(
    channel_idx: int,
    current_value: float,
    threshold: float,
    graph_analyzer: GraphAnalyzer,
    channels: List[float],
    thresholds: Dict[int, float]
) -> bool:
    """
    Evaluate whether a channel should be suppressed or preserved based on topology-aware rules.
    """
    if current_value >= threshold:
        return False  # Preserve channels that meet threshold

    # Calculate ratio for preservation rules
    threshold_ratio = current_value / threshold if threshold > 0 else 0

    # Rule 1: Bridge nodes with 0.81 <= ratio <= 0.82
    if graph_analyzer.is_bridge_node(channel_idx) and 0.81 <= threshold_ratio <= 0.82:
        return False

    # Rule 2: Articulation points with 0.79 <= ratio <= 0.81 AND >=2 active neighbors
    if graph_analyzer.is_articulation_point(channel_idx) and 0.79 <= threshold_ratio <= 0.81:
        out_nei = graph_analyzer.get_neighbors(channel_idx)
        in_nei = graph_analyzer.reverse_adjacency_list.get(channel_idx, [])
        # distinct neighbors (exclude self if any self-loop)
        neighbor_set = {n for n in out_nei + in_nei if n != channel_idx}
        active_count = sum(1 for n in neighbor_set if n < len(channels) and channels[n] > 0)
        if active_count >= 2:
            return False

    # Rule 3: Source nodes with ratio > 0.85 AND >=1 active downstream
    if graph_analyzer.is_source_node(channel_idx) and threshold_ratio > 0.85:
        neighbors = graph_analyzer.get_neighbors(channel_idx)
        active_count = sum(1 for n in neighbors if n < len(channels) and channels[n] > 0)
        if active_count >= 1:
            return False

    # Rule 4: Sink nodes with 0.75 <= ratio <= 0.78 AND >=3 active upstream sources
    if graph_analyzer.is_sink_node(channel_idx) and 0.75 <= threshold_ratio <= 0.78:
        active_source_upstreams = set()
        for u in graph_analyzer.reverse_adjacency_list.get(channel_idx, []):
            if (u < len(channels) and channels[u] > 0 and
                graph_analyzer.is_source_node(u)):  # must be a SOURCE
                active_source_upstreams.add(u)      # count distinct sources
                if len(active_source_upstreams) >= 3:
                    return False  # preserve sink

    # Default: suppress
    return True