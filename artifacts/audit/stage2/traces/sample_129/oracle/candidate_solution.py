from typing import List, Dict, Any
import re
import math

def analyze_delivery_network(cities: List[Dict], roads: List[Dict], infrastructure_queries: List[Dict], cost_threshold: Dict) -> Dict[str, Any]:
    if not cities:
        return {"error": "No cities provided"}
    
    if not roads:
        return {"error": "No roads provided"}
    
    max_acceptable_cost = cost_threshold.get('max_acceptable_cost', 0)
    high_cost_multiplier = cost_threshold.get('high_cost_multiplier', 0)
    efficiency_target = cost_threshold.get('efficiency_target', 0)
    critical_impact_threshold = cost_threshold.get('critical_impact_threshold')
    medium_impact_threshold = cost_threshold.get('medium_impact_threshold')
    congestion_analysis_count = cost_threshold.get('congestion_analysis_count')
    redundancy_cost_factor = cost_threshold.get('redundancy_cost_factor')
    
    if (max_acceptable_cost < 1 or 
        not isinstance(high_cost_multiplier, (int, float)) or high_cost_multiplier < 1.5 or high_cost_multiplier > 3.0 or
        not isinstance(efficiency_target, int) or efficiency_target < 5 or efficiency_target > 25 or
        not isinstance(critical_impact_threshold, (int, float)) or
        not isinstance(medium_impact_threshold, (int, float)) or
        not isinstance(congestion_analysis_count, int) or
        not isinstance(redundancy_cost_factor, (int, float))):
        return {"error": "Invalid cost threshold configuration"}
    
    city_ids = set()
    for city in cities:
        city_id = city.get('city_id')
        if city_id is None or not isinstance(city_id, int) or city_id < 0 or city_id > 999:
            return {"error": "Input is not valid"}
        
        if city_id in city_ids:
            return {"error": "Input is not valid"}
        city_ids.add(city_id)
        
        city_name = city.get('city_name', '')
        if not isinstance(city_name, str) or len(city_name) < 3 or len(city_name) > 50:
            return {"error": f"Invalid city name for city {city_id}"}
        
        if not re.match(r'^[a-zA-Z0-9]+$', city_name):
            return {"error": f"Invalid city name for city {city_id}"}
        
        region_type = city.get('region_type')
        if region_type not in ["urban", "suburban", "rural", "industrial"]:
            return {"error": "Input is not valid"}
        
        processing_capacity = city.get('processing_capacity')
        if not isinstance(processing_capacity, int) or processing_capacity < 100 or processing_capacity > 10000:
            return {"error": f"Invalid processing capacity for city {city_id}"}
    
    road_ids = set()
    city_pairs = set()
    for road in roads:
        road_id = road.get('road_id')
        if road_id is None or not isinstance(road_id, int) or road_id < 0 or road_id > 9999:
            return {"error": "Input is not valid"}
        
        if road_id in road_ids:
            return {"error": "Input is not valid"}
        road_ids.add(road_id)
        
        city_a = road.get('city_a')
        city_b = road.get('city_b')
        
        if city_a not in city_ids:
            return {"error": f"Invalid city reference in road {road_id}"}
        
        if city_b not in city_ids:
            return {"error": f"Invalid city reference in road {road_id}"}
        
        if city_a == city_b:
            return {"error": f"Self-loop detected for road {road_id}"}
        
        city_pair = tuple(sorted([city_a, city_b]))
        if city_pair in city_pairs:
            return {"error": f"Duplicate road between cities {city_pair[0]} and {city_pair[1]}"}
        city_pairs.add(city_pair)
        
        fuel_cost = road.get('fuel_cost')
        if not isinstance(fuel_cost, int) or fuel_cost < 1 or fuel_cost > 1000:
            return {"error": f"Invalid fuel cost for road {road_id}"}
        
        road_type = road.get('road_type')
        if road_type not in ["highway", "arterial", "local", "service"]:
            return {"error": "Input is not valid"}
        
        maintenance_priority = road.get('maintenance_priority')
        if not isinstance(maintenance_priority, int) or maintenance_priority < 1 or maintenance_priority > 5:
            return {"error": "Input is not valid"}
    
    filtered_roads = [road for road in roads if road['fuel_cost'] <= cost_threshold['max_acceptable_cost']]
    
    if not is_graph_connected(cities, filtered_roads):
        return {"error": "Graph is not connected"}
    
    for query in infrastructure_queries:
        query_id = query.get('query_id')
        if query_id is None or not isinstance(query_id, int) or query_id < 0 or query_id > 99:
            return {"error": "Input is not valid"}
        
        query_type = query.get('query_type')
        if query_type not in ["critical_edge", "bottleneck_path", "edge_addition_impact", "vulnerability_assessment"]:
            return {"error": f"Unsupported query type for query {query_id}"}
        
        parameters = query.get('parameters', {})
        if not validate_query_parameters(query_type, parameters, road_ids, city_ids):
            return {"error": f"Invalid query parameters for query {query_id}"}
    
    mst_result = build_mst(cities, filtered_roads)

    all_costs = [road['fuel_cost'] for road in filtered_roads]
    all_costs.sort()
    q3_threshold = calculate_75th_percentile(all_costs)
    
    mst_edges = []
    for edge in mst_result['mst_edges']:
        classification = "high_cost_segment" if edge['fuel_cost'] > q3_threshold else "standard_cost_segment"
        mst_edges.append({
            "road_id": edge['road_id'],
            "city_a": edge['city_a'],
            "city_b": edge['city_b'],
            "fuel_cost": edge['fuel_cost'],
            "cost_classification": classification
        })
    
    preprocessor = MST_Preprocessor(cities, mst_result, filtered_roads)
    
    query_results = []
    for query in infrastructure_queries:
        result = process_query(query, preprocessor, mst_result, cost_threshold)
        query_results.append(result)
    
    total_weight_sum = sum(road['fuel_cost'] for road in filtered_roads)
    network_efficiency_score = round(mst_result['total_cost'] / total_weight_sum, 2)
    
    recommendations = generate_infrastructure_recommendations(mst_result, q3_threshold, cost_threshold)
    
    network_stats = generate_network_statistics(mst_result, cost_threshold)
    
    return {
        "mst_analysis": {
            "total_mst_cost": mst_result['total_cost'],
            "mst_edges": mst_edges,
            "excluded_roads": sorted([road['road_id'] for road in filtered_roads if road['road_id'] not in {e['road_id'] for e in mst_result['mst_edges']}]),
            "network_efficiency_score": network_efficiency_score
        },
        "query_results": query_results,
        "infrastructure_recommendations": recommendations,
        "network_statistics": network_stats
    }

def calculate_75th_percentile(sorted_values):
    if not sorted_values:
        return 0
    
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    
    position = 0.75 * (n - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, n - 1)
    
    if lower_index == upper_index:
        return sorted_values[lower_index]
    
    fraction = position - lower_index
    return sorted_values[lower_index] + fraction * (sorted_values[upper_index] - sorted_values[lower_index])

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
    
    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        return True

def is_graph_connected(cities, roads):
    if not roads:
        return len(cities) <= 1
    
    city_to_index = {city['city_id']: i for i, city in enumerate(cities)}
    uf = UnionFind(len(cities))
    
    for road in roads:
        a_idx = city_to_index[road['city_a']]
        b_idx = city_to_index[road['city_b']]
        uf.union(a_idx, b_idx)
    
    root = uf.find(0)
    return all(uf.find(i) == root for i in range(len(cities)))

def build_mst(cities, roads):
    city_to_index = {city['city_id']: i for i, city in enumerate(cities)}
    
    sorted_roads = sorted(roads, key=lambda x: (x['fuel_cost'], x['road_id']))
    
    uf = UnionFind(len(cities))
    mst_edges = []
    total_cost = 0
    
    for road in sorted_roads:
        a_idx = city_to_index[road['city_a']]
        b_idx = city_to_index[road['city_b']]
        
        if uf.union(a_idx, b_idx):
            mst_edges.append(road)
            total_cost += road['fuel_cost']
            
            if len(mst_edges) == len(cities) - 1:
                break
    
    return {
        'mst_edges': mst_edges,
        'total_cost': total_cost
    }

class LCA:
    def __init__(self, n, adj, root=0):
        self.n = n
        self.LOG = int(math.log2(n)) + 1
        self.parent = [[-1] * self.LOG for _ in range(n)]
        self.depth = [0] * n
        self.max_edge = [[-1] * self.LOG for _ in range(n)]
        self.max_edge_id = [[-1] * self.LOG for _ in range(n)]
        
        self._dfs(root, -1, 0, adj, -1, 0)
        self._preprocess()
    
    def _dfs(self, u, p, d, adj, edge_id, edge_cost):
        self.parent[u][0] = p
        self.depth[u] = d
        self.max_edge[u][0] = edge_cost
        self.max_edge_id[u][0] = edge_id
        
        for v, eid, cost in adj[u]:
            if v != p:
                self._dfs(v, u, d + 1, adj, eid, cost)
    
    def _preprocess(self):
        for j in range(1, self.LOG):
            for i in range(self.n):
                if self.parent[i][j-1] != -1:
                    self.parent[i][j] = self.parent[self.parent[i][j-1]][j-1]
                    if self.max_edge[i][j-1] >= self.max_edge[self.parent[i][j-1]][j-1]:
                        self.max_edge[i][j] = self.max_edge[i][j-1]
                        self.max_edge_id[i][j] = self.max_edge_id[i][j-1]
                    else:
                        self.max_edge[i][j] = self.max_edge[self.parent[i][j-1]][j-1]
                        self.max_edge_id[i][j] = self.max_edge_id[self.parent[i][j-1]][j-1]
    
    def lca(self, u, v):
        if self.depth[u] < self.depth[v]:
            u, v = v, u
        
        diff = self.depth[u] - self.depth[v]
        for i in range(self.LOG):
            if (diff >> i) & 1:
                u = self.parent[u][i]
        
        if u == v:
            return u
        
        for i in range(self.LOG - 1, -1, -1):
            if self.parent[u][i] != self.parent[v][i]:
                u = self.parent[u][i]
                v = self.parent[v][i]
        
        return self.parent[u][0]
    
    def query_max_edge(self, u, v):
        if self.depth[u] < self.depth[v]:
            u, v = v, u
        
        max_cost = 0
        max_edge_id = -1
        
        diff = self.depth[u] - self.depth[v]
        for i in range(self.LOG):
            if (diff >> i) & 1:
                if self.max_edge[u][i] > max_cost:
                    max_cost = self.max_edge[u][i]
                    max_edge_id = self.max_edge_id[u][i]
                u = self.parent[u][i]
        
        if u == v:
            return max_cost, max_edge_id
        
        for i in range(self.LOG - 1, -1, -1):
            if self.parent[u][i] != self.parent[v][i]:
                if self.max_edge[u][i] > max_cost:
                    max_cost = self.max_edge[u][i]
                    max_edge_id = self.max_edge_id[u][i]
                if self.max_edge[v][i] > max_cost:
                    max_cost = self.max_edge[v][i]
                    max_edge_id = self.max_edge_id[v][i]
                u = self.parent[u][i]
                v = self.parent[v][i]
        
        if self.max_edge[u][0] > max_cost:
            max_cost = self.max_edge[u][0]
            max_edge_id = self.max_edge_id[u][0]
        if self.max_edge[v][0] > max_cost:
            max_cost = self.max_edge[v][0]
            max_edge_id = self.max_edge_id[v][0]
        
        return max_cost, max_edge_id

class MST_Preprocessor:
    def __init__(self, cities, mst_result, all_roads):
        self.cities = cities
        self.mst_edges = mst_result['mst_edges']
        self.all_roads = all_roads
        self.city_to_index = {city['city_id']: i for i, city in enumerate(cities)}
        self.index_to_city = {i: city['city_id'] for i, city in enumerate(cities)}
        
        self.mst_adj = [[] for _ in range(len(cities))]
        self.edge_lookup = {}
        
        for edge in self.mst_edges:
            u_idx = self.city_to_index[edge['city_a']]
            v_idx = self.city_to_index[edge['city_b']]
            
            self.mst_adj[u_idx].append((v_idx, edge['road_id'], edge['fuel_cost']))
            self.mst_adj[v_idx].append((u_idx, edge['road_id'], edge['fuel_cost']))
            
            key1 = (edge['city_a'], edge['city_b'])
            key2 = (edge['city_b'], edge['city_a'])
            self.edge_lookup[key1] = edge
            self.edge_lookup[key2] = edge
        
        self.lca = LCA(len(cities), self.mst_adj, 0)
        
        self.precompute_replacement_costs()
    
    def precompute_replacement_costs(self):
        self.replacement_costs = {}
        
        for mst_edge in self.mst_edges:
            self.replacement_costs[mst_edge['road_id']] = float('inf')
        
        mst_edge_ids = {edge['road_id'] for edge in self.mst_edges}
        
        for road in self.all_roads:
            if road['road_id'] in mst_edge_ids:
                continue
            
            u_idx = self.city_to_index[road['city_a']]
            v_idx = self.city_to_index[road['city_b']]
            
            cycle_edges = self.find_cycle_edges(u_idx, v_idx)
            
            for edge_id in cycle_edges:
                if edge_id in self.replacement_costs:
                    self.replacement_costs[edge_id] = min(self.replacement_costs[edge_id], road['fuel_cost'])
        
        for edge_id in self.replacement_costs:
            if self.replacement_costs[edge_id] == float('inf'):
                self.replacement_costs[edge_id] = None
    
    def find_cycle_edges(self, u_idx, v_idx):
        cycle_edges = []
        
        lca_node = self.lca.lca(u_idx, v_idx)
        
        current = u_idx
        while current != lca_node:
            for neighbor, edge_id, cost in self.mst_adj[current]:
                if self.lca.depth[neighbor] < self.lca.depth[current]:
                    cycle_edges.append(edge_id)
                    current = neighbor
                    break
        
        current = v_idx
        while current != lca_node:
            for neighbor, edge_id, cost in self.mst_adj[current]:
                if self.lca.depth[neighbor] < self.lca.depth[current]:
                    cycle_edges.append(edge_id)
                    current = neighbor
                    break
        
        return cycle_edges
    
    def query_bottleneck(self, city_a, city_b):
        u_idx = self.city_to_index[city_a]
        v_idx = self.city_to_index[city_b]
        
        max_cost, edge_id = self.lca.query_max_edge(u_idx, v_idx)
        
        return max_cost, edge_id
    
    def find_cycle_max_edge(self, new_city_a, new_city_b):
        max_cost, edge_id = self.query_bottleneck(new_city_a, new_city_b)
        return max_cost, edge_id

def validate_query_parameters(query_type, parameters, road_ids, city_ids):
    if query_type == "critical_edge":
        edge_road_id = parameters.get("edge_road_id")
        return isinstance(edge_road_id, int) and edge_road_id in road_ids
    
    elif query_type == "bottleneck_path":
        source = parameters.get("source_city_id")
        target = parameters.get("target_city_id")
        return (isinstance(source, int) and source in city_ids and
                isinstance(target, int) and target in city_ids)
    
    elif query_type == "edge_addition_impact":
        new_city_a = parameters.get("new_city_a")
        new_city_b = parameters.get("new_city_b")
        new_fuel_cost = parameters.get("new_fuel_cost")
        return (isinstance(new_city_a, int) and new_city_a in city_ids and
                isinstance(new_city_b, int) and new_city_b in city_ids and
                isinstance(new_fuel_cost, int) and new_fuel_cost > 0)
    
    elif query_type == "vulnerability_assessment":
        analysis_scope = parameters.get("analysis_scope")
        k_value = parameters.get("k_value")
        return (analysis_scope in ["single_edge", "top_k_edges"] and
                isinstance(k_value, int) and 1 <= k_value <= 10)
    
    return False

def process_query(query, preprocessor, mst_result, cost_threshold):
    query_id = query['query_id']
    query_type = query['query_type']
    parameters = query['parameters']
    
    result = {}
    processing_time_category = "instant"
    
    if query_type == "critical_edge":
        edge_road_id = parameters["edge_road_id"]
        replacement_cost = preprocessor.replacement_costs.get(edge_road_id)
        
        if replacement_cost is None:
            impact_severity = "critical"
            replacement_cost = 0
        else:
            original_edge = next((e for e in mst_result['mst_edges'] if e['road_id'] == edge_road_id), None)
            if original_edge:
                critical_threshold = original_edge['fuel_cost'] * cost_threshold['critical_impact_threshold']
                medium_threshold = original_edge['fuel_cost'] * cost_threshold['medium_impact_threshold']
                
                if replacement_cost > critical_threshold:
                    impact_severity = "high"
                elif replacement_cost > medium_threshold:
                    impact_severity = "medium"
                else:
                    impact_severity = "low"
            else:
                impact_severity = "low"
        
        result = {"replacement_cost": replacement_cost or 0, "impact_severity": impact_severity}
    
    elif query_type == "bottleneck_path":
        source_city_id = parameters["source_city_id"]
        target_city_id = parameters["target_city_id"]
        
        max_cost, edge_id = preprocessor.query_bottleneck(source_city_id, target_city_id)
        result = {
            "bottleneck_edge_id": edge_id,
            "max_cost_segment": max_cost
        }
    
    elif query_type == "edge_addition_impact":
        new_city_a = parameters["new_city_a"]
        new_city_b = parameters["new_city_b"]
        new_fuel_cost = parameters["new_fuel_cost"]
        
        max_cycle_edge_cost, _ = preprocessor.find_cycle_max_edge(new_city_a, new_city_b)
        
        if new_fuel_cost < max_cycle_edge_cost:
            cost_reduction = max_cycle_edge_cost - new_fuel_cost
            efficiency_gain = round(cost_reduction / mst_result['total_cost'] * 100, 2)
        else:
            cost_reduction = 0
            efficiency_gain = 0.0
        
        result = {"cost_reduction": cost_reduction, "efficiency_gain": efficiency_gain}
        processing_time_category = "fast"
    
    elif query_type == "vulnerability_assessment":
        analysis_scope = parameters["analysis_scope"]
        k_value = parameters["k_value"]
        
        vulnerabilities = []
        for edge in mst_result['mst_edges']:
            replacement_cost = preprocessor.replacement_costs.get(edge['road_id'])
            if replacement_cost is None:
                vulnerability_score = float('inf')
            else:
                vulnerability_score = replacement_cost - edge['fuel_cost']
            
            vulnerabilities.append((edge['road_id'], vulnerability_score))
        
        vulnerabilities.sort(key=lambda x: (x[1] == float('inf'), x[1]), reverse=True)
        
        if analysis_scope == "single_edge":
            critical_edges = [vulnerabilities[0][0]] if vulnerabilities else []
            max_impact_edge = critical_edges[0] if critical_edges else -1
        else:
            critical_edges = [v[0] for v in vulnerabilities[:k_value]]
            max_impact_edge = critical_edges[0] if critical_edges else -1
        
        result = {"critical_edges": critical_edges, "max_impact_edge": max_impact_edge}
        processing_time_category = "moderate"
    
    return {
        "query_id": query_id,
        "query_type": query_type,
        "result": result,
        "processing_time_category": processing_time_category
    }

def generate_infrastructure_recommendations(mst_result, q3_threshold, cost_threshold):
    critical_segments = []
    redundancy_needed = []
    
    redundancy_threshold = q3_threshold * cost_threshold['redundancy_cost_factor']
    
    for edge in mst_result['mst_edges']:
        if edge['fuel_cost'] > q3_threshold:
            critical_segments.append(edge['road_id'])
        
        if edge['fuel_cost'] > redundancy_threshold:
            redundancy_needed.append(edge['road_id'])
    
    total_high_cost = sum(edge['fuel_cost'] for edge in mst_result['mst_edges'] if edge['fuel_cost'] > q3_threshold)
    total_cost = mst_result['total_cost']
    if total_cost > 0:
        cost_optimization_potential = round((total_high_cost / total_cost) * cost_threshold['efficiency_target'], 1)
    else:
        cost_optimization_potential = 0.0
    
    return {
        "critical_segments": sorted(critical_segments),
        "redundancy_needed": sorted(redundancy_needed),
        "cost_optimization_potential": cost_optimization_potential
    }

def generate_network_statistics(mst_result, cost_threshold):
    connectivity_index = 1.0
    
    average_path_cost = round(mst_result['total_cost'] / len(mst_result['mst_edges']), 1) if mst_result['mst_edges'] else 0.0
    
    edge_costs = [(edge['road_id'], edge['fuel_cost']) for edge in mst_result['mst_edges']]
    edge_costs.sort(key=lambda x: x[1], reverse=True)
    
    congestion_count = cost_threshold['congestion_analysis_count']
    most_congested_routes = [x[0] for x in edge_costs[:congestion_count]]
    
    alternative_suggestions = []
    for edge_id, cost in edge_costs[:1]:
        alternative_suggestions.append({
            "current_road_id": edge_id,
            "suggested_improvement": "capacity_upgrade"
        })
    
    return {
        "connectivity_index": connectivity_index,
        "average_path_cost": average_path_cost,
        "bottleneck_analysis": {
            "most_congested_routes": most_congested_routes,
            "alternative_routing_suggestions": alternative_suggestions
        }
    }

if __name__ == "__main__":
    cities = [
        {"city_id": 0, "city_name": "MetroHub", "region_type": "urban", "processing_capacity": 5000},
        {"city_id": 1, "city_name": "SouthPort", "region_type": "industrial", "processing_capacity": 3000},
        {"city_id": 2, "city_name": "NorthVale", "region_type": "suburban", "processing_capacity": 2000},
        {"city_id": 3, "city_name": "EastBridge", "region_type": "rural", "processing_capacity": 1500},
        {"city_id": 4, "city_name": "WestPoint", "region_type": "urban", "processing_capacity": 4000}
    ]

    roads = [
        {"road_id": 0, "city_a": 0, "city_b": 1, "fuel_cost": 150, "road_type": "highway", "maintenance_priority": 2},
        {"road_id": 1, "city_a": 0, "city_b": 2, "fuel_cost": 200, "road_type": "arterial", "maintenance_priority": 3},
        {"road_id": 2, "city_a": 1, "city_b": 2, "fuel_cost": 180, "road_type": "local", "maintenance_priority": 1},
        {"road_id": 3, "city_a": 1, "city_b": 3, "fuel_cost": 220, "road_type": "service", "maintenance_priority": 4},
        {"road_id": 4, "city_a": 2, "city_b": 3, "fuel_cost": 160, "road_type": "highway", "maintenance_priority": 2},
        {"road_id": 5, "city_a": 2, "city_b": 4, "fuel_cost": 190, "road_type": "arterial", "maintenance_priority": 3},
        {"road_id": 6, "city_a": 3, "city_b": 4, "fuel_cost": 170, "road_type": "local", "maintenance_priority": 1}
    ]

    infrastructure_queries = [
        {"query_id": 0, "query_type": "critical_edge", "parameters": {"edge_road_id": 0}},
        {"query_id": 1, "query_type": "bottleneck_path", "parameters": {"source_city_id": 0, "target_city_id": 3}}
    ]

    cost_threshold = {
        "max_acceptable_cost": 500,
        "high_cost_multiplier": 2.0,
        "efficiency_target": 15,
        "critical_impact_threshold": 1.5,
        "medium_impact_threshold": 1.2,
        "congestion_analysis_count": 2,
        "redundancy_cost_factor": 1.0
    }

    result = analyze_delivery_network(cities, roads, infrastructure_queries, cost_threshold)
    print(result)