from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict


class ProductGraph:
    """
    Hierarchical graph managing product relationships with weighted edges.
    Supports dynamic updates for real-time recommendation systems.
    """
    
    def __init__(self):
        self.adjacency = defaultdict(lambda: defaultdict(float))
        self.product_data = {}
        self.category_products = defaultdict(set)
        self.version = 0
    
    def add_product(self, product_id: int, category: str, related_ids: List[int], weights: Optional[Dict[int, float]] = None):
        """Add product with weighted relationships to the graph."""
        self.product_data[product_id] = category
        self.category_products[category].add(product_id)
        
        for related_id in related_ids:
            weight = weights.get(related_id, 1.0) if weights else 1.0
            self.adjacency[product_id][related_id] = weight
            self.adjacency[related_id][product_id] = weight
        
        self.version += 1
    
    def add_interaction_edge(self, prod1: int, prod2: int, weight: float = 1.0):
        """Add or update weighted interaction edge between products."""
        self.adjacency[prod1][prod2] = max(self.adjacency[prod1].get(prod2, 0.0), weight)
        self.adjacency[prod2][prod1] = max(self.adjacency[prod2].get(prod1, 0.0), weight)
        self.version += 1
    
    def get_neighbors_with_weights(self, product_id: int) -> Dict[int, float]:
        """Get all neighbors with their edge weights."""
        return dict(self.adjacency.get(product_id, {}))
    
    def get_category_products(self, category: str) -> Set[int]:
        """Get all products in a specific category."""
        return self.category_products.get(category, set()).copy()
    
    def get_edge_weight(self, prod1: int, prod2: int) -> float:
        """Get weight of edge between two products."""
        return self.adjacency.get(prod1, {}).get(prod2, 0.0)
    
    def get_graph_version(self) -> int:
        """Get current graph version for cache invalidation."""
        return self.version


class SegmentTreeNode:
    """Node in segment tree for efficient range queries and updates."""
    
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end
        self.sum_score = 0.0
        self.max_score = 0.0
        self.min_score = 0.0
        self.left = None
        self.right = None
        self.lazy = 0.0


class SegmentTree:
    """
    Segment tree for O(log n) range updates.
    Supports lazy propagation for efficient batch operations on product scores.
    """
    
    def __init__(self, size: int):
        self.size = size
        self.root = self._build(0, size - 1) if size > 0 else None
        self.values = [0.0] * size
    
    def _build(self, start: int, end: int) -> SegmentTreeNode:
        """Recursively build segment tree structure."""
        node = SegmentTreeNode(start, end)
        if start == end:
            return node
        
        mid = (start + end) // 2
        node.left = self._build(start, mid)
        node.right = self._build(mid + 1, end)
        return node
    
    def _push_down(self, node: SegmentTreeNode):
        """Apply lazy propagation to child nodes."""
        if node.lazy != 0.0 and node.left and node.right:
            node.left.sum_score += node.lazy * (node.left.end - node.left.start + 1)
            node.left.max_score += node.lazy
            node.left.min_score += node.lazy
            node.left.lazy += node.lazy
            
            node.right.sum_score += node.lazy * (node.right.end - node.right.start + 1)
            node.right.max_score += node.lazy
            node.right.min_score += node.lazy
            node.right.lazy += node.lazy
            
            node.lazy = 0.0
    
    def update_range(self, left: int, right: int, delta: float):
        """Update score range with delta value."""
        if self.root and 0 <= left <= right < self.size:
            self._update_range(self.root, left, right, delta)
            for i in range(left, min(right + 1, self.size)):
                self.values[i] += delta
    
    def _update_range(self, node: Optional[SegmentTreeNode], left: int, right: int, delta: float):
        """Internal recursive range update."""
        if not node or right < node.start or left > node.end:
            return
        
        if left <= node.start and node.end <= right:
            node.sum_score += delta * (node.end - node.start + 1)
            node.max_score += delta
            node.min_score += delta
            node.lazy += delta
            return
        
        self._push_down(node)
        self._update_range(node.left, left, right, delta)
        self._update_range(node.right, left, right, delta)
        
        node.sum_score = (node.left.sum_score if node.left else 0.0) + (node.right.sum_score if node.right else 0.0)
        node.max_score = max(node.left.max_score if node.left else float('-inf'), 
                            node.right.max_score if node.right else float('-inf'))
        node.min_score = min(node.left.min_score if node.left else float('inf'), 
                            node.right.min_score if node.right else float('inf'))
    
    def get_value(self, index: int) -> float:
        """Get score at specific index."""
        if 0 <= index < self.size:
            return self.values[index]
        return 0.0


class CommunityDetector:
    """
    Weighted community detection using Louvain-inspired modularity optimization.
    """
    
    def __init__(self, graph: ProductGraph):
        self.graph = graph
        self.communities = {}
        self.community_scores = {}
    
    def detect_communities(self, product_ids: Set[int], interaction_weights: Dict[int, float]) -> Dict[int, int]:
        """Detect communities using weighted graph analysis."""
        if not product_ids:
            return {}
        
        communities = {pid: pid for pid in product_ids}
        improved = True
        iteration = 0
        max_iterations = 5
        
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1
            
            for pid in product_ids:
                best_community = communities[pid]
                best_gain = 0.0
                
                neighbors = self.graph.get_neighbors_with_weights(pid)
                neighbor_communities = defaultdict(float)
                
                for neighbor, weight in neighbors.items():
                    if neighbor in communities:
                        comm = communities[neighbor]
                        interaction_boost = interaction_weights.get(neighbor, 0.5)
                        neighbor_communities[comm] += weight * (1.0 + interaction_boost)
                
                for comm, total_weight in neighbor_communities.items():
                    if comm != communities[pid]:
                        modularity_gain = total_weight
                        if modularity_gain > best_gain:
                            best_gain = modularity_gain
                            best_community = comm
                
                if best_community != communities[pid] and best_gain > 0.1:
                    communities[pid] = best_community
                    improved = True
        
        unique_comms = sorted(set(communities.values()))
        comm_mapping = {old: new for new, old in enumerate(unique_comms)}
        communities = {pid: comm_mapping[comm] for pid, comm in communities.items()}
        
        self.communities = communities
        self._compute_community_scores(product_ids, interaction_weights)
        
        return communities
    
    def _compute_community_scores(self, product_ids: Set[int], interaction_weights: Dict[int, float]):
        """Compute aggregate scores for each community."""
        community_scores = defaultdict(lambda: {'size': 0, 'total_weight': 0.0, 'density': 0.0})
        
        for pid in product_ids:
            if pid in self.communities:
                comm = self.communities[pid]
                community_scores[comm]['size'] += 1
                community_scores[comm]['total_weight'] += interaction_weights.get(pid, 0.0)
        
        for comm, data in community_scores.items():
            members = [p for p, c in self.communities.items() if c == comm]
            
            if len(members) > 20:
                data['density'] = 0.5
                continue
            
            edges = 0
            possible_edges = len(members) * (len(members) - 1) / 2
            
            if possible_edges > 0:
                for i, p1 in enumerate(members):
                    for p2 in members[i+1:]:
                        if self.graph.get_edge_weight(p1, p2) > 0:
                            edges += 1
                data['density'] = edges / possible_edges
        
        self.community_scores = dict(community_scores)
    
    def get_community_size(self, product_id: int) -> int:
        """Get size of product's community."""
        comm = self.communities.get(product_id, -1)
        if comm < 0:
            return 1
        return self.community_scores.get(comm, {}).get('size', 1)
    
    def get_community_metrics(self, product_id: int) -> Dict[str, float]:
        """Get comprehensive community metrics for a product."""
        comm = self.communities.get(product_id, -1)
        if comm < 0:
            return {'size': 1, 'total_weight': 0.0, 'density': 0.0}
        return self.community_scores.get(comm, {'size': 1, 'total_weight': 0.0, 'density': 0.0})


class MinCostFlowSolver:
    """Min-cost max-flow solver using successive shortest path algorithm."""
    
    def __init__(self, graph: ProductGraph):
        self.graph = graph
        self.flow_network = defaultdict(lambda: defaultdict(lambda: {'capacity': 0.0, 'cost': 0.0, 'flow': 0.0}))
    
    def build_flow_network(self, products: List[Dict[str, Any]], user_interactions: Dict[int, float]):
        """Build flow network with source, sink, and product nodes."""
        source = -1
        sink = -2
        product_ids = {p['id'] for p in products}
        
        for product in products:
            pid = product['id']
            popularity = product.get('popularity', 0)
            
            self.flow_network[source][pid] = {
                'capacity': max(popularity, 1.0),
                'cost': 1.0 / (popularity + 1.0),
                'flow': 0.0
            }
            
            interaction = user_interactions.get(pid, 0.1)
            self.flow_network[pid][sink] = {
                'capacity': interaction + 1.0,
                'cost': 1.0 / (interaction + 1.0),
                'flow': 0.0
            }
            
            related_ids = product.get('related_products', [])
            for related_id in related_ids:
                if related_id in product_ids:
                    edge_weight = self.graph.get_edge_weight(pid, related_id)
                    self.flow_network[pid][related_id] = {
                        'capacity': max(edge_weight + 0.5, 0.5),
                        'cost': 1.0 / (edge_weight + 1.0),
                        'flow': 0.0
                    }
    
    def _bellman_ford(self, source: int, sink: int, nodes: Set[int]) -> Tuple[Dict[int, float], Dict[int, Optional[int]]]:
        """Find shortest path using Bellman-Ford algorithm."""
        dist = {node: float('inf') for node in nodes}
        dist[source] = 0.0
        pred = {node: None for node in nodes}
        
        for iteration in range(min(len(nodes) - 1, 20)):
            updated = False
            for u in nodes:
                if dist[u] == float('inf'):
                    continue
                
                if u not in self.flow_network:
                    continue
                    
                for v, edge_data in self.flow_network[u].items():
                    if v in nodes:
                        residual = edge_data['capacity'] - edge_data['flow']
                        if residual > 1e-6:
                            new_dist = dist[u] + edge_data['cost']
                            if new_dist < dist[v]:
                                dist[v] = new_dist
                                pred[v] = u
                                updated = True
            
            if not updated:
                break
        
        return dist, pred
    
    def compute_min_cost_flow(self, products: List[Dict[str, Any]]) -> Dict[int, float]:
        """Compute min-cost max-flow scores for all products."""
        source = -1
        sink = -2
        nodes = {source, sink}
        nodes.update(p['id'] for p in products)
        
        max_iterations = 20
        iteration = 0
        total_flow = 0.0
        
        while iteration < max_iterations:
            iteration += 1
            
            dist, pred = self._bellman_ford(source, sink, nodes)
            
            if dist[sink] == float('inf'):
                break
            
            path = []
            current = sink
            min_capacity = float('inf')
            
            while pred[current] is not None:
                prev = pred[current]
                path.append((prev, current))
                
                if prev not in self.flow_network or current not in self.flow_network[prev]:
                    min_capacity = 0.0
                    break
                
                residual = self.flow_network[prev][current]['capacity'] - self.flow_network[prev][current]['flow']
                min_capacity = min(min_capacity, residual)
                current = prev
            
            if min_capacity < 1e-6:
                break
            
            for u, v in path:
                self.flow_network[u][v]['flow'] += min_capacity
                if v not in self.flow_network:
                    self.flow_network[v] = {}
                if u not in self.flow_network[v]:
                    self.flow_network[v][u] = {
                        'capacity': 0.0, 
                        'cost': -self.flow_network[u][v]['cost'], 
                        'flow': 0.0
                    }
                self.flow_network[v][u]['flow'] -= min_capacity
            
            total_flow += min_capacity
            
            if total_flow > len(products) * 2:
                break
        
        scores = {}
        for product in products:
            pid = product['id']
            
            incoming_flow = 0.0
            if source in self.flow_network and pid in self.flow_network[source]:
                incoming_flow = self.flow_network[source][pid]['flow']
            
            outgoing_flow = 0.0
            if pid in self.flow_network and sink in self.flow_network[pid]:
                outgoing_flow = self.flow_network[pid][sink]['flow']
            
            cost_efficiency = 0.0
            if pid in self.flow_network:
                for v, edge in self.flow_network[pid].items():
                    if edge['flow'] > 0:
                        cost_efficiency += edge['flow'] / (edge['cost'] + 0.1)
            
            scores[pid] = incoming_flow + outgoing_flow * 0.5 + cost_efficiency * 0.3
        
        return scores


class ConcurrentScoreAggregator:
    """Score aggregation with versioning and batch updates."""
    
    def __init__(self):
        self.score_components = defaultdict(dict)
        self.version = 0
    
    def get_score_breakdown(self, product_id: int) -> Dict[str, float]:
        """Get detailed score breakdown by component."""
        return dict(self.score_components.get(product_id, {}))
    
    def batch_update(self, score_dict: Dict[int, float], component: str = 'total'):
        """Batch update scores for multiple products."""
        for pid, score in score_dict.items():
            if pid not in self.score_components:
                self.score_components[pid] = {}
            self.score_components[pid][component] = score
        self.version += 1


class RecommendationEngine:
    """
    Multi-stage recommendation pipeline with modular scoring components.
    """
    
    def __init__(self):
        self.graph = ProductGraph()
        self.segment_tree = None
        self.community_detector = None
        self.flow_solver = None
        self.score_aggregator = ConcurrentScoreAggregator()
        self.product_index_map = {}
        self.index_product_map = {}
        self.category_ranges = {}
        self.last_graph_version = -1
        self.score_cache = {}
    
    def build_product_index(self, products: List[Dict[str, Any]]):
        """Build index mapping between products and segment tree positions."""
        sorted_products = sorted(products, key=lambda p: (p.get('category', ''), p['id']))
        
        current_category = None
        category_start = 0
        
        for idx, product in enumerate(sorted_products):
            pid = product['id']
            category = product.get('category', 'Unknown')
            
            self.product_index_map[pid] = idx
            self.index_product_map[idx] = pid
            
            if category != current_category:
                if current_category is not None:
                    self.category_ranges[current_category] = (category_start, idx - 1)
                current_category = category
                category_start = idx
        
        if current_category is not None:
            self.category_ranges[current_category] = (category_start, len(sorted_products) - 1)
    
    def initialize_graph(self, products: List[Dict[str, Any]]):
        """Initialize product graph with relationships and weights."""
        for product in products:
            pid = product['id']
            category = product.get('category', 'Unknown')
            related = product.get('related_products', [])
            
            weights = {}
            popularity = product.get('popularity', 0)
            for related_id in related:
                related_product = next((p for p in products if p['id'] == related_id), None)
                if related_product:
                    related_pop = related_product.get('popularity', 0)
                    weight = 1.0 + min(popularity, related_pop) / (max(popularity, related_pop) + 1.0)
                    weights[related_id] = weight
            
            self.graph.add_product(pid, category, related, weights)
    
    def process_user_sessions(self, sessions: List[Dict[str, Any]]) -> Dict[int, float]:
        """Process user session data to extract interaction weights."""
        interaction_weights = defaultdict(float)
        
        for session_idx, session in enumerate(sessions):
            browse_history = session.get('browse_history', [])
            purchase_history = session.get('purchase_history', [])
            
            recency_factor = 1.0 / ((len(sessions) - session_idx) ** 0.5)
            
            for pid in browse_history:
                interaction_weights[pid] += 1.5 * recency_factor
            
            for pid in purchase_history:
                interaction_weights[pid] += 10.0 * recency_factor
            
            for i in range(len(browse_history) - 1):
                for j in range(i + 1, min(i + 4, len(browse_history))):
                    distance_decay = 1.0 / (j - i)
                    weight = 0.8 * recency_factor * distance_decay
                    self.graph.add_interaction_edge(browse_history[i], browse_history[j], weight)
        
        return dict(interaction_weights)
    
    def compute_category_affinity(self, user_data: Dict[str, Any]) -> Dict[str, float]:
        """Compute normalized category affinity scores from user data."""
        category_affinity = defaultdict(float)
        
        sessions = user_data.get('sessions', [])
        for session in sessions:
            time_spent = session.get('time_spent', {})
            for category, time_val in time_spent.items():
                category_affinity[category] += (time_val ** 0.7)
        
        preferences = user_data.get('preferences', {})
        preferred_categories = preferences.get('categories', [])
        for category in preferred_categories:
            category_affinity[category] += 150.0
        
        total = sum(category_affinity.values())
        if total > 0:
            return {cat: score / total for cat, score in category_affinity.items()}
        
        return {}
    
    def compute_interaction_scores(self, products: List[Dict[str, Any]], 
                                   interaction_weights: Dict[int, float]) -> Dict[int, float]:
        """Stage 1: Compute interaction-based scores."""
        scores = {}
        max_weight = max(interaction_weights.values()) if interaction_weights else 1.0
        
        for product in products:
            pid = product['id']
            raw_weight = interaction_weights.get(pid, 0.0)
            normalized = raw_weight / (max_weight + 0.1)
            score = 10.0 * (normalized / (1.0 + normalized))
            scores[pid] = score
        
        return scores
    
    def compute_community_scores(self, products: List[Dict[str, Any]], 
                                 interaction_weights: Dict[int, float]) -> Dict[int, float]:
        """Stage 2: Compute community-based scores."""
        product_ids = {p['id'] for p in products}
        
        self.community_detector = CommunityDetector(self.graph)
        communities = self.community_detector.detect_communities(product_ids, interaction_weights)
        
        scores = {}
        for product in products:
            pid = product['id']
            metrics = self.community_detector.get_community_metrics(pid)
            
            size_score = min(metrics['size'] / 5.0, 3.0)
            density_score = metrics['density'] * 2.0
            weight_score = min(metrics['total_weight'] / 10.0, 2.0)
            
            scores[pid] = size_score + density_score + weight_score
        
        return scores
    
    def compute_flow_scores(self, products: List[Dict[str, Any]], 
                       interaction_weights: Dict[int, float]) -> Dict[int, float]:
        """Stage 3: Compute min-cost flow scores."""
        try:
            self.flow_solver = MinCostFlowSolver(self.graph)
            self.flow_solver.build_flow_network(products, interaction_weights)
            flow_scores = self.flow_solver.compute_min_cost_flow(products)
            
            if not flow_scores:
                return {p['id']: 0.0 for p in products}
            
            max_flow = max(flow_scores.values()) if flow_scores else 1.0
            if max_flow < 1e-6:
                return {pid: 0.0 for pid in flow_scores.keys()}
            
            return {pid: score / (max_flow + 0.1) * 5.0 for pid, score in flow_scores.items()}
        except Exception as e:
            print(f"Warning: Flow score computation failed: {e}")
            return {p['id']: 0.0 for p in products}
    
    def compute_category_scores(self, products: List[Dict[str, Any]], 
                                category_affinity: Dict[str, float]) -> Dict[int, float]:
        """Stage 4: Compute category affinity scores."""
        scores = {}
        for product in products:
            pid = product['id']
            category = product.get('category', 'Unknown')
            affinity = category_affinity.get(category, 0.0)
            scores[pid] = affinity * 30.0
        
        return scores
    
    def update_segment_tree_scores(self, product_scores: Dict[int, float]):
        """Update segment tree with computed scores."""
        if not self.segment_tree:
            return
        
        for pid, score in product_scores.items():
            idx = self.product_index_map.get(pid)
            if idx is not None:
                current_val = self.segment_tree.get_value(idx)
                delta = score - current_val
                self.segment_tree.update_range(idx, idx, delta)
    
    def apply_category_boost_via_segment_tree(self, category_affinity: Dict[str, float]):
        """Apply category-level boosts using segment tree range updates."""
        if not self.segment_tree:
            return
        
        for category, affinity in category_affinity.items():
            if category in self.category_ranges:
                start, end = self.category_ranges[category]
                boost = affinity * 5.0
                self.segment_tree.update_range(start, end, boost)
    
    def compute_popularity_scores(self, products: List[Dict[str, Any]]) -> Dict[int, float]:
        """Compute normalized popularity scores."""
        scores = {}
        max_pop = max((p.get('popularity', 0) for p in products), default=1)
        
        for product in products:
            pid = product['id']
            pop = product.get('popularity', 0)
            normalized = pop / (max_pop + 1.0)
            scores[pid] = 2.0 * (normalized ** 0.6)
        
        return scores
    
    def handle_sparse_data(self, products: List[Dict[str, Any]], 
                          interaction_weights: Dict[int, float]) -> Dict[int, float]:
        """Handle products with sparse interaction data."""
        fallback_scores = {}
        
        for product in products:
            pid = product['id']
            interaction = interaction_weights.get(pid, 0.0)
            
            if interaction < 0.5:
                popularity = product.get('popularity', 0)
                category = product.get('category', 'Unknown')
                
                category_products = self.graph.get_category_products(category)
                similar_scores = []
                
                for similar_pid in category_products:
                    if similar_pid != pid and similar_pid in interaction_weights:
                        edge_weight = self.graph.get_edge_weight(pid, similar_pid)
                        if edge_weight > 0:
                            similar_scores.append(interaction_weights[similar_pid] * edge_weight)
                
                if similar_scores:
                    fallback = sum(similar_scores) / len(similar_scores) * 0.7
                else:
                    fallback = popularity * 0.3
                
                fallback_scores[pid] = fallback
        
        return fallback_scores
    
    def compute_final_scores(self, products: List[Dict[str, Any]], 
                        user_data: Dict[str, Any]) -> Dict[int, float]:
        """Orchestrate multi-stage scoring pipeline."""
        
        current_version = self.graph.get_graph_version()
        needs_full_recompute = (current_version != self.last_graph_version)
        
        if not needs_full_recompute and self.score_cache:
            return self.score_cache
        
        interaction_weights = self.process_user_sessions(user_data.get('sessions', []))
        
        sparse_scores = self.handle_sparse_data(products, interaction_weights)
        for pid, score in sparse_scores.items():
            if pid not in interaction_weights or interaction_weights[pid] < 0.5:
                interaction_weights[pid] = max(interaction_weights.get(pid, 0.0), score)
        
        category_affinity = self.compute_category_affinity(user_data)
        
        interaction_scores = self.compute_interaction_scores(products, interaction_weights)
        self.score_aggregator.batch_update(interaction_scores, 'interaction')
        
        popularity_scores = self.compute_popularity_scores(products)
        self.score_aggregator.batch_update(popularity_scores, 'popularity')
        
        category_scores = self.compute_category_scores(products, category_affinity)
        self.score_aggregator.batch_update(category_scores, 'category')
        
        if len(products) < 100:
            community_scores = self.compute_community_scores(products, interaction_weights)
            self.score_aggregator.batch_update(community_scores, 'community')
            
            flow_scores = self.compute_flow_scores(products, interaction_weights)
            self.score_aggregator.batch_update(flow_scores, 'flow')
        else:
            default_scores = {p['id']: 0.0 for p in products}
            self.score_aggregator.batch_update(default_scores, 'community')
            self.score_aggregator.batch_update(default_scores, 'flow')
        
        total_component_scores = {}
        for product in products:
            pid = product['id']
            components = self.score_aggregator.get_score_breakdown(pid)
            total_component_scores[pid] = sum(components.values())
        
        if self.segment_tree:
            self.update_segment_tree_scores(total_component_scores)
            self.apply_category_boost_via_segment_tree(category_affinity)
            
            final_scores = {}
            for product in products:
                pid = product['id']
                idx = self.product_index_map.get(pid)
                
                if idx is not None:
                    segment_score = self.segment_tree.get_value(idx)
                    final_scores[pid] = segment_score
                else:
                    final_scores[pid] = total_component_scores.get(pid, 0.0)
        else:
            final_scores = total_component_scores
        
        self.score_cache = final_scores
        self.last_graph_version = current_version
        
        return final_scores


def custom_sort(products: List[Dict[str, Any]], user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Multi-stage recommendation pipeline that personalizes product listings.
    
    Args:
        products: List of product dictionaries
        user_data: Dictionary containing user sessions and preferences
    
    Returns:
        List of product dictionaries sorted by computed priority scores
    """
    
    if not products:
        return []
    
    if not isinstance(products, list):
        raise TypeError("Products must be a list")
    
    if not isinstance(user_data, dict):
        raise TypeError("User data must be a dictionary")
    
    for product in products:
        if not isinstance(product, dict):
            raise TypeError("Each product must be a dictionary")
        if 'id' not in product:
            raise ValueError("Each product must have an 'id' field")
        if not isinstance(product['id'], int):
            raise TypeError("Product 'id' must be an integer")
    
    if not user_data or not user_data.get('sessions'):
        sorted_products = sorted(
            products, 
            key=lambda p: p.get('popularity', 0), 
            reverse=True
        )
        return [
            {
                'id': p['id'],
                'name': p.get('name', f"Product {p['id']}"),
                'category': p.get('category', 'Unknown')
            }
            for p in sorted_products
        ]
    
    try:
        engine = RecommendationEngine()
        engine.build_product_index(products)
        engine.initialize_graph(products)
        engine.segment_tree = SegmentTree(len(products))
        
        final_scores = engine.compute_final_scores(products, user_data)
        
        sorted_products = sorted(
            products,
            key=lambda p: final_scores.get(p['id'], 0.0),
            reverse=True
        )
        
        result = []
        for product in sorted_products:
            result.append({
                'id': product['id'],
                'name': product.get('name', f"Product {product['id']}"),
                'category': product.get('category', 'Unknown')
            })
        
        return result
    
    except Exception as e:
        print(f"Error in recommendation pipeline: {str(e)}")
        sorted_products = sorted(
            products,
            key=lambda p: p.get('popularity', 0),
            reverse=True
        )
        return [
            {
                'id': p['id'],
                'name': p.get('name', f"Product {p['id']}"),
                'category': p.get('category', 'Unknown')
            }
            for p in sorted_products
        ]


# Example usage
if __name__ == "__main__":
    products = [
        {
            'id': 101,
            'name': 'Laptop',
            'category': 'Electronics',
            'related_products': [103, 202],
            'popularity': 8
        },
        {
            'id': 202,
            'name': 'Smartphone',
            'category': 'Electronics',
            'related_products': [101],
            'popularity': 9
        },
        {
            'id': 303,
            'name': 'Espresso Machine',
            'category': 'Home Appliances',
            'related_products': [],
            'popularity': 3
        },
        {
            'id': 103,
            'name': 'Wireless Mouse',
            'category': 'Electronics',
            'related_products': [101],
            'popularity': 5
        }
    ]
    
    user_data = {
        'sessions': [
            {
                'browse_history': [101, 202],
                'purchase_history': [101],
                'time_spent': {'Electronics': 240, 'Home Appliances': 15}
            },
            {
                'browse_history': [303],
                'purchase_history': [],
                'time_spent': {'Home Appliances': 55}
            }
        ],
        'preferences': {
            'categories': ['Electronics', 'Home Appliances'],
            'preferred_brands': []
        }
    }
    
    result = custom_sort(products, user_data)
    print("Recommendation Results:")
    for product in result:
        print(f"- {product['name']} (ID: {product['id']}, Category: {product['category']})")