from typing import List, Dict, Any


# Floating-point tolerance for reliability comparisons to handle precision issues
EPSILON = 1e-9

# Maximum acceptable latency value; values >= 10^9 are considered unreasonably large
LATENCY_MAX = 10**9


class UnionFind:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}
        self.rank = {node: 0 for node in nodes}
    
    def find(self, node):
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]
    
    def union(self, node1, node2):
        root1, root2 = self.find(node1), self.find(node2)
        
        if root1 == root2:
            return False
        
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1
        return True


def optimize_network_mst(
    nodes: List[str],
    edges: List[Dict[str, Any]],
    bandwidth_threshold: int,
    latency_threshold: int,
    reliability_threshold: float
) -> List[Dict[str, str]]:
    """
    Compute minimum-cost spanning tree with multi-constraint filtering.
    
    Builds a minimum spanning tree (MST) across network nodes using Kruskal's algorithm
    with Union-Find, while enforcing bandwidth, latency, and reliability constraints.
    Returns empty list if no feasible connected spanning tree exists.
    
    Args:
        nodes: List of node identifiers (case-sensitive strings)
        edges: List of edge dictionaries with keys:
            - 'start': source node name
            - 'end': destination node name
            - 'cost': edge cost (can be negative)
            - 'bandwidth': bandwidth capacity (must be > 0 and >= threshold)
            - 'latency': latency value (must be >= 0 and < 10^9)
            - 'reliability': reliability score (must be >= threshold - 1e-9)
        bandwidth_threshold: Minimum required bandwidth for valid edges
        latency_threshold: Maximum allowed latency for valid edges
        reliability_threshold: Minimum required reliability for valid edges
    
    Returns:
        List of edge dictionaries with 'start' and 'end' keys forming MST,
        or empty list if no feasible spanning tree exists
    """
    
    if len(nodes) <= 1 or not edges:
        return []
    
    node_set = set(nodes)
    valid_edges = []
    
    for edge in edges:
        start = edge.get('start')
        end = edge.get('end')
        cost = edge.get('cost')
        bandwidth = edge.get('bandwidth')
        latency = edge.get('latency')
        reliability = edge.get('reliability')
        
        if None in (start, end, cost, bandwidth, latency, reliability):
            continue
        
        if start not in node_set or end not in node_set or start == end:
            continue
        
        if bandwidth <= 0 or latency < 0 or latency >= LATENCY_MAX:
            continue
        
        if (bandwidth < bandwidth_threshold or 
            latency > latency_threshold or 
            reliability < reliability_threshold - EPSILON):
            continue
        
        normalized_pair = (min(start, end), max(start, end))
        valid_edges.append({
            'nodes': normalized_pair,
            'start': start,
            'end': end,
            'cost': cost
        })
    
    if not valid_edges:
        return []
    
    edge_map = {}
    for edge in valid_edges:
        key = edge['nodes']
        if key not in edge_map or edge['cost'] < edge_map[key]['cost']:
            edge_map[key] = edge
    
    sorted_edges = sorted(
        edge_map.values(), 
        key=lambda e: (e['cost'], e['nodes'])
    )
    
    uf = UnionFind(nodes)
    mst_edges = []
    target_edge_count = len(nodes) - 1
    
    for edge in sorted_edges:
        if uf.union(edge['start'], edge['end']):
            mst_edges.append({'start': edge['start'], 'end': edge['end']})
            if len(mst_edges) == target_edge_count:
                break
    
    return mst_edges if len(mst_edges) == target_edge_count else []

if __name__ == "__main__":
    nodes = ['HubA', 'HubB', 'HubC', 'HubD', 'HubE']
    edges = [
        {'start': 'HubA', 'end': 'HubB', 'cost': 5, 'bandwidth': 200, 'latency': 5, 'reliability': 0.98},
        {'start': 'HubB', 'end': 'HubC', 'cost': 10, 'bandwidth': 180, 'latency': 10, 'reliability': 0.95},
        {'start': 'HubA', 'end': 'HubC', 'cost': 12, 'bandwidth': 250, 'latency': 15, 'reliability': 0.95},
        {'start': 'HubC', 'end': 'HubD', 'cost': 20, 'bandwidth': 300, 'latency': 12, 'reliability': 0.99},
        {'start': 'HubB', 'end': 'HubD', 'cost': 25, 'bandwidth': 150, 'latency': 10, 'reliability': 0.92},
        {'start': 'HubD', 'end': 'HubE', 'cost': 15, 'bandwidth': 200, 'latency': 12, 'reliability': 0.95},
        {'start': 'HubC', 'end': 'HubE', 'cost': 30, 'bandwidth': 280, 'latency': 14, 'reliability': 0.92}
    ]
    bandwidth_threshold = 150
    latency_threshold = 15
    reliability_threshold = 0.90
    result = optimize_network_mst(nodes, edges, bandwidth_threshold, latency_threshold, reliability_threshold)
    print(result)