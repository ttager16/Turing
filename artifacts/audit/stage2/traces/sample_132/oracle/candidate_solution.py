import heapq
from collections import defaultdict, deque
from typing import List, Dict, Any, Tuple, Set


def process_offline_graph_queries(road_network: List[Dict], intersection_data: List[Dict], 
                                closure_schedule: List[Dict], query_batch: List[Dict]) -> Dict[str, Any]:
    """
    Processes offline queries on urban road network with intersection closures.
    Returns: Dictionary with query results and network analysis metrics
    """
    
    if not query_batch:
        return {"error": "Empty query batch provided"}
    
    intersection_ids = set()
    for intersection in intersection_data:
        intersection_id = intersection['intersection_id']
        if intersection_id < 0 or intersection_id > 199:
            return {"error": "Input is not valid"}
        
        coordinates = intersection['coordinates']
        if coordinates['x'] < 0 or coordinates['x'] > 10000 or coordinates['y'] < 0 or coordinates['y'] > 10000:
            return {"error": f"Invalid coordinates for intersection {intersection_id}"}
        
        if intersection['intersection_type'] not in ["residential", "commercial", "industrial", "highway"]:
            return {"error": "Input is not valid"}
        
        if intersection['baseline_delay'] < 30 or intersection['baseline_delay'] > 180:
            return {"error": "Input is not valid"}
        
        if intersection['neighborhood_cluster'] < 1 or intersection['neighborhood_cluster'] > 10:
            return {"error": f"Invalid neighborhood cluster assignment for intersection {intersection_id}"}
        
        intersection_ids.add(intersection_id)
    
    edge_ids = set()
    for edge in road_network:
        edge_id = edge['edge_id']
        if edge_id < 0 or edge_id > 999:
            return {"error": "Input is not valid"}
        
        if edge['intersection_a'] not in intersection_ids:
            return {"error": f"Invalid intersection reference in road segment {edge_id}"}
        if edge['intersection_b'] not in intersection_ids:
            return {"error": f"Invalid intersection reference in road segment {edge_id}"}
        
        if edge['segment_length'] < 100 or edge['segment_length'] > 5000:
            return {"error": "Input is not valid"}
        
        if edge['traffic_density'] < 0.1 or edge['traffic_density'] > 1.0:
            return {"error": "Input is not valid"}
        
        if edge['congestion_weight'] < 1 or edge['congestion_weight'] > 20:
            return {"error": "Input is not valid"}
        
        if edge['road_type'] not in ["residential", "arterial", "highway", "local"]:
            return {"error": "Input is not valid"}
        
        if edge['max_speed_limit'] < 30 or edge['max_speed_limit'] > 100:
            return {"error": "Input is not valid"}
        
        edge_ids.add(edge_id)
    
    for intersection in intersection_data:
        intersection_id = intersection['intersection_id']
        connected_roads = intersection['connected_roads']
        
        for edge_id in connected_roads:
            if edge_id < 0 or edge_id > 999:
                return {"error": f"Inconsistent road connections for intersection {intersection_id}"}
            if edge_id not in edge_ids:
                return {"error": f"Inconsistent road connections for intersection {intersection_id}"}
            
            edge = next(e for e in road_network if e['edge_id'] == edge_id)
            if edge['intersection_a'] != intersection_id and edge['intersection_b'] != intersection_id:
                return {"error": f"Inconsistent road connections for intersection {intersection_id}"}
    
    closure_ids = set()
    priority_1_closures = []
    for closure in closure_schedule:
        closure_id = closure['closure_id']
        if closure_id < 0 or closure_id > 99:
            return {"error": "Input is not valid"}
        
        if closure['affected_intersection'] not in intersection_ids:
            return {"error": "Input is not valid"}
        
        if closure['start_time'] < 0 or closure['start_time'] > 168:
            return {"error": "Input is not valid"}
        if closure['end_time'] < 0 or closure['end_time'] > 168:
            return {"error": "Input is not valid"}
        
        if closure['start_time'] >= closure['end_time']:
            return {"error": f"Invalid closure time window for closure {closure_id}"}
        
        if closure['closure_reason'] not in ["construction", "maintenance", "emergency", "event"]:
            return {"error": "Input is not valid"}
        
        if closure['priority_level'] < 1 or closure['priority_level'] > 5:
            return {"error": "Input is not valid"}
        
        if closure['alternative_capacity'] < 0.0 or closure['alternative_capacity'] > 0.8:
            return {"error": "Input is not valid"}
        
        if closure['priority_level'] == 1:
            priority_1_closures.append(closure)
        
        closure_ids.add(closure_id)
    
    for i, closure1 in enumerate(priority_1_closures):
        for j in range(i + 1, len(priority_1_closures)):
            closure2 = priority_1_closures[j]
            if closure1['affected_intersection'] == closure2['affected_intersection']:
                start1, end1 = closure1['start_time'], closure1['end_time']
                start2, end2 = closure2['start_time'], closure2['end_time']
                if not (end1 <= start2 or end2 <= start1):
                    return {"error": "Overlapping high-priority closures detected"}
    
    for query in query_batch:
        query_id = query['query_id']
        if query_id < 0 or query_id > 199:
            return {"error": "Input is not valid"}
        
        if query['query_type'] not in ["shortest_path", "connectivity_check", "alternative_routes", "impact_analysis"]:
            return {"error": "Input is not valid"}
        
        if query['source_intersection'] not in intersection_ids:
            return {"error": "Input is not valid"}
        if query['target_intersection'] not in intersection_ids:
            return {"error": "Input is not valid"}
        
        if query['query_time'] < 0 or query['query_time'] > 168:
            return {"error": f"Query time outside valid range for query {query_id}"}
        
        if query['max_alternative_paths'] < 1 or query['max_alternative_paths'] > 5:
            return {"error": "Input is not valid"}
        
        if query['distance_threshold'] < 1000 or query['distance_threshold'] > 50000:
            return {"error": "Input is not valid"}
    
    graph = build_graph(road_network)
    if not is_connected(graph, intersection_ids):
        return {"error": "Disconnected network components detected"}
    
    intersection_degrees = calculate_intersection_degrees(road_network)
    critical_intersections = identify_critical_intersections(intersection_degrees)
    all_pairs_distances = floyd_warshall(graph, intersection_ids)
    
    for query in query_batch:
        source = query['source_intersection']
        target = query['target_intersection']
        distance_threshold = query['distance_threshold']
        
        theoretical_min_distance = all_pairs_distances.get((source, target), float('inf'))
        
        if theoretical_min_distance != float('inf') and distance_threshold < theoretical_min_distance:
            return {"error": f"Distance threshold too restrictive for query {query['query_id']}"}
    
    query_results = []
    total_detour_distance = 0
    affected_intersection_count = 0
    high_impact_closures = []
    
    for query in query_batch:
        result = process_single_query(
            query, intersection_data, closure_schedule,
            graph, all_pairs_distances, critical_intersections
        )
        query_results.append(result)
        
        if result['affected_closures']:
            affected_intersection_count += 1
            for closure_id in result['affected_closures']:
                if closure_id not in high_impact_closures:
                    high_impact_closures.append(closure_id)
        
        if result['result_status'] == "success":
            direct_distance = all_pairs_distances.get((query['source_intersection'], query['target_intersection']), 0)
            if result['path_distance'] > direct_distance:
                total_detour_distance += (result['path_distance'] - direct_distance)
    
    cluster_connectivity_matrix = build_cluster_connectivity_matrix(intersection_data, graph)
    total_connectivity_score = calculate_total_connectivity_score(cluster_connectivity_matrix)
    
    shortest_path_cache_size = len(all_pairs_distances)
    connectivity_components = count_connected_components(graph, intersection_ids)
    
    return {
        "query_results": query_results,
        "network_analysis": {
            "total_connectivity_score": round(total_connectivity_score, 2),
            "critical_intersections": sorted(critical_intersections),
            "cluster_connectivity_matrix": cluster_connectivity_matrix,
            "closure_impact_summary": {
                "high_impact_closures": sorted(high_impact_closures),
                "affected_intersection_count": affected_intersection_count,
                "total_detour_distance": total_detour_distance
            }
        },
        "preprocessing_metrics": {
            "total_intersections_processed": len(intersection_data),
            "total_road_segments_analyzed": len(road_network),
            "shortest_path_cache_size": shortest_path_cache_size,
            "connectivity_components": connectivity_components
        }
    }


def build_graph(road_network: List[Dict]) -> Dict[int, List[Dict]]:
    graph = defaultdict(list)
    
    for edge in road_network:
        a, b = edge['intersection_a'], edge['intersection_b']
        edge_data = {
            'target': b,
            'edge_id': edge['edge_id'],
            'segment_length': edge['segment_length'],
            'traffic_density': edge['traffic_density'],
            'congestion_weight': edge['congestion_weight'],
            'max_speed_limit': edge['max_speed_limit']
        }
        graph[a].append(edge_data)
        
        edge_data_reverse = {
            'target': a,
            'edge_id': edge['edge_id'],
            'segment_length': edge['segment_length'],
            'traffic_density': edge['traffic_density'],
            'congestion_weight': edge['congestion_weight'],
            'max_speed_limit': edge['max_speed_limit']
        }
        graph[b].append(edge_data_reverse)
    
    return dict(graph)


def is_connected(graph: Dict[int, List[Dict]], intersection_ids: Set[int]) -> bool:
    if not intersection_ids:
        return True
    
    start_node = next(iter(intersection_ids))
    visited = set()
    queue = deque([start_node])
    visited.add(start_node)
    
    while queue:
        node = queue.popleft()
        for edge in graph.get(node, []):
            target = edge['target']
            if target not in visited:
                visited.add(target)
                queue.append(target)
    
    return len(visited) == len(intersection_ids)


def floyd_warshall(graph: Dict[int, List[Dict]], intersection_ids: Set[int]) -> Dict[Tuple[int, int], int]:
    distances = {}
    
    for i in intersection_ids:
        for j in intersection_ids:
            if i == j:
                distances[(i, j)] = 0
            else:
                distances[(i, j)] = float('inf')
    
    for node in graph:
        for edge in graph[node]:
            target = edge['target']
            distance = edge['segment_length']
            distances[(node, target)] = min(distances.get((node, target), float('inf')), distance)
    
    for k in intersection_ids:
        for i in intersection_ids:
            for j in intersection_ids:
                if distances[(i, k)] + distances[(k, j)] < distances[(i, j)]:
                    distances[(i, j)] = distances[(i, k)] + distances[(k, j)]
    
    return {k: v for k, v in distances.items() if v != float('inf')}


def calculate_intersection_degrees(road_network: List[Dict]) -> Dict[int, int]:
    degrees = defaultdict(int)
    
    for edge in road_network:
        degrees[edge['intersection_a']] += 1
        degrees[edge['intersection_b']] += 1
    
    return dict(degrees)


def identify_critical_intersections(intersection_degrees: Dict[int, int]) -> List[int]:
    critical = []
    for intersection_id, degree in intersection_degrees.items():
        if degree > 4:
            critical.append(intersection_id)
    return critical


def get_active_closures(closure_schedule: List[Dict], query_time: int) -> Set[int]:
    closed_intersections = set()
    for closure in closure_schedule:
        if closure['start_time'] <= query_time <= closure['end_time']:
            closed_intersections.add(closure['affected_intersection'])
    return closed_intersections


def dijkstra_with_closures(graph: Dict[int, List[Dict]], start: int, end: int, 
                          closed_intersections: Set[int], intersection_data: List[Dict]) -> Tuple[List[int], int]:
    if start in closed_intersections or end in closed_intersections:
        return [], float('inf')
    
    distances = {node: float('inf') for node in graph}
    distances[start] = 0
    previous = {}
    heap = [(0, start)]
    visited = set()
    
    while heap:
        current_dist, current = heapq.heappop(heap)
        
        if current in visited:
            continue
        visited.add(current)
        
        if current == end:
            break
        
        if current in closed_intersections:
            continue
        
        for edge in graph.get(current, []):
            neighbor = edge['target']
            if neighbor in closed_intersections:
                continue
            
            distance = current_dist + edge['segment_length']
            
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = current
                heapq.heappush(heap, (distance, neighbor))
    
    if distances[end] == float('inf'):
        return [], float('inf')
    
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = previous.get(current)
    path.reverse()
    
    return path, distances[end]


def find_k_shortest_paths(graph: Dict[int, List[Dict]], source: int, target: int,
                         closed_intersections: Set[int], intersection_data: List[Dict],
                         k: int, distance_threshold: int) -> List[Tuple[List[int], int]]:
    if source == target:
        return []
    
    paths = []
    potential_paths = []
    
    shortest_path, shortest_distance = dijkstra_with_closures(graph, source, target, closed_intersections, intersection_data)
    if shortest_path and shortest_distance <= distance_threshold:
        paths.append((shortest_path, shortest_distance))
    
    if not shortest_path:
        return paths
    
    for i in range(len(shortest_path) - 1):
        spur_node = shortest_path[i]
        root_path = shortest_path[:i+1]
        
        removed_edges = set()
        temp_closed = closed_intersections.copy()
        
        for path, _ in paths:
            if len(path) > i and path[:i+1] == root_path:
                if i+1 < len(path):
                    next_node = path[i+1]
                    removed_edges.add((spur_node, next_node))
        
        for node in root_path[:-1]:
            temp_closed.add(node)
        
        temp_graph = defaultdict(list)
        for node in graph:
            for edge in graph[node]:
                if (node, edge['target']) not in removed_edges:
                    temp_graph[node].append(edge)
        
        spur_path, spur_distance = dijkstra_with_temp_graph(temp_graph, spur_node, target, temp_closed)
        
        if spur_path:
            total_path = root_path[:-1] + spur_path
            total_distance = 0
            for j in range(len(total_path) - 1):
                current = total_path[j]
                next_node = total_path[j + 1]
                for edge in graph.get(current, []):
                    if edge['target'] == next_node:
                        total_distance += edge['segment_length']
                        break
            
            if total_distance <= distance_threshold:
                potential_paths.append((total_path, total_distance))
    
    potential_paths.sort(key=lambda x: x[1])
    
    for path, distance in potential_paths:
        if len(paths) >= k:
            break
        if (path, distance) not in paths:
            paths.append((path, distance))
    
    return paths


def dijkstra_with_temp_graph(temp_graph: Dict[int, List[Dict]], start: int, end: int, 
                            closed_intersections: Set[int]) -> Tuple[List[int], int]:
    if start in closed_intersections or end in closed_intersections:
        return [], float('inf')
    
    distances = {node: float('inf') for node in temp_graph}
    distances[start] = 0
    previous = {}
    heap = [(0, start)]
    visited = set()
    
    while heap:
        current_dist, current = heapq.heappop(heap)
        
        if current in visited:
            continue
        visited.add(current)
        
        if current == end:
            break
        
        if current in closed_intersections:
            continue
        
        for edge in temp_graph.get(current, []):
            neighbor = edge['target']
            if neighbor in closed_intersections:
                continue
            
            distance = current_dist + edge['segment_length']
            
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = current
                heapq.heappush(heap, (distance, neighbor))
    
    if distances[end] == float('inf'):
        return [], float('inf')
    
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = previous.get(current)
    path.reverse()
    
    return path, distances[end]


def calculate_path_quality_score(path: List[int], graph: Dict[int, List[Dict]], 
                                intersection_data: List[Dict], closure_schedule: List[Dict],
                                query_time: int, critical_intersections: List[int], 
                                all_pairs_distances: Dict, all_closed_intersections: Set[int] = None) -> float:
    if len(path) < 2:
        return 0.0
    
    if all_closed_intersections is None:
        all_closed_intersections = get_active_closures(closure_schedule, query_time)
    
    base_distance_cost = 0
    traffic_densities = []
    congestion_weights = []
    
    for i in range(len(path) - 1):
        current = path[i]
        next_node = path[i + 1]
        
        edge_found = False
        for edge in graph.get(current, []):
            if edge['target'] == next_node:
                base_distance_cost += edge['segment_length']
                traffic_densities.append(edge['traffic_density'])
                congestion_weights.append(edge['congestion_weight'])
                edge_found = True
                break
        
        if not edge_found:
            return float('inf')
    
    closed_intersections_on_path = 0
    total_closure_duration = 0
    
    for intersection in path:
        if intersection in all_closed_intersections:
            closed_intersections_on_path += 1
    
    for closure in closure_schedule:
        if closure['affected_intersection'] in path:
            if closure['start_time'] <= query_time <= closure['end_time']:
                total_closure_duration += (closure['end_time'] - closure['start_time'])
    
    closure_penalty = (closed_intersections_on_path * 100) + (total_closure_duration * 0.5)
    
    affected_segments = 0
    for i in range(len(path) - 1):
        current = path[i]
        next_node = path[i + 1]
        
        segment_connects_to_closed = False
        for edge in graph.get(current, []):
            if edge['target'] == next_node:
                for node in graph.keys():
                    if node in all_closed_intersections:
                        for connected_edge in graph.get(node, []):
                            if connected_edge['target'] == current or connected_edge['target'] == next_node:
                                segment_connects_to_closed = True
                                break
                        if segment_connects_to_closed:
                            break
                        for connected_edge in graph.get(current, []):
                            if connected_edge['target'] == node:
                                segment_connects_to_closed = True
                                break
                        if segment_connects_to_closed:
                            break
                        for connected_edge in graph.get(next_node, []):
                            if connected_edge['target'] == node:
                                segment_connects_to_closed = True
                                break
                        if segment_connects_to_closed:
                            break
                break
        
        if segment_connects_to_closed:
            affected_segments += 1
    
    average_traffic_density = sum(traffic_densities) / len(traffic_densities) if traffic_densities else 0
    traffic_impact_factor = average_traffic_density * 25
    
    congestion_level = sum(congestion_weights)
    
    source = path[0]
    target = path[-1]
    direct_distance = all_pairs_distances.get((source, target), base_distance_cost)
    detour_complexity = (base_distance_cost - direct_distance) * 10
    
    all_alternative_paths = find_k_shortest_paths(graph, source, target, all_closed_intersections, intersection_data, 10, 50000)
    alternative_routes_count = len(all_alternative_paths)
    
    path_quality_score = (base_distance_cost + 
                         (closure_penalty * affected_segments) + 
                         (traffic_impact_factor * congestion_level) + 
                         (detour_complexity * alternative_routes_count))
    
    impact_multiplier = 1.0
    for intersection in path:
        if intersection in critical_intersections:
            impact_multiplier = 1.5
            break
    
    return path_quality_score * impact_multiplier


def calculate_travel_time_estimate(path: List[int], graph: Dict[int, List[Dict]], 
                                 intersection_data: List[Dict]) -> int:
    if len(path) < 2:
        return 0
    
    intersection_lookup = {inter['intersection_id']: inter for inter in intersection_data}
    total_time_minutes = 0
    
    for i in range(len(path) - 1):
        current = path[i]
        next_node = path[i + 1]
        
        for edge in graph.get(current, []):
            if edge['target'] == next_node:
                segment_length_meters = edge['segment_length']
                speed_kmh = edge['max_speed_limit']
                segment_time_minutes = (segment_length_meters / speed_kmh) * 60 / 1000
                total_time_minutes += segment_time_minutes
                break
    
    for intersection in path:
        baseline_delay_seconds = intersection_lookup[intersection]['baseline_delay']
        total_time_minutes += baseline_delay_seconds / 60
    
    return int(round(total_time_minutes))


def find_alternative_paths(graph: Dict[int, List[Dict]], source: int, target: int,
                          closed_intersections: Set[int], intersection_data: List[Dict],
                          max_alternatives: int, distance_threshold: int,
                          optimal_path: List[int], closure_schedule: List[Dict],
                          query_time: int, critical_intersections: List[int],
                          all_pairs_distances: Dict) -> List[Dict]:
    alternatives = []
    
    if source == target:
        return alternatives
    
    k_shortest_paths = find_k_shortest_paths(graph, source, target, closed_intersections, intersection_data, max_alternatives + 1, distance_threshold)
    
    filtered_alternatives = []
    for alt_path, alt_distance in k_shortest_paths:
        if alt_path != optimal_path:
            filtered_alternatives.append((alt_path, alt_distance))
    
    for alt_path, alt_distance in filtered_alternatives[:max_alternatives]:
        if len(alt_path) >= 2:
            quality_score = calculate_path_quality_score(
                alt_path, graph, intersection_data, closure_schedule,
                query_time, critical_intersections, all_pairs_distances, closed_intersections
            )
            
            optimal_distance = 0
            for i in range(len(optimal_path) - 1):
                current = optimal_path[i]
                next_node = optimal_path[i + 1]
                for edge in graph.get(current, []):
                    if edge['target'] == next_node:
                        optimal_distance += edge['segment_length']
                        break
            
            detour_factor = alt_distance / optimal_distance if optimal_distance > 0 else 1.0
            
            alternatives.append({
                "path_intersections": alt_path,
                "path_distance": alt_distance,
                "quality_score": round(quality_score, 1),
                "detour_factor": round(detour_factor, 2)
            })
    
    alternatives.sort(key=lambda x: x['quality_score'])
    
    return alternatives


def get_affected_closures_for_path(path: List[int], closure_schedule: List[Dict], query_time: int) -> List[int]:
    affected_closures = []
    
    for closure in closure_schedule:
        if closure['start_time'] <= query_time <= closure['end_time']:
            if closure['affected_intersection'] in path:
                affected_closures.append(closure['closure_id'])
    
    return affected_closures


def process_single_query(query: Dict, intersection_data: List[Dict], closure_schedule: List[Dict],
                        graph: Dict[int, List[Dict]], all_pairs_distances: Dict, 
                        critical_intersections: List[int]) -> Dict:
    
    source = query['source_intersection']
    target = query['target_intersection']
    query_time = query['query_time']
    query_type = query['query_type']
    max_alternatives = query['max_alternative_paths']
    distance_threshold = query['distance_threshold']
    
    closed_intersections = get_active_closures(closure_schedule, query_time)
    
    optimal_path, path_distance = dijkstra_with_closures(graph, source, target, closed_intersections, intersection_data)
    
    if not optimal_path or path_distance > distance_threshold:
        return {
            "query_id": query['query_id'],
            "query_type": query_type,
            "result_status": "no_path_found",
            "optimal_path": [],
            "path_distance": 0,
            "path_quality_score": 0.0,
            "travel_time_estimate": 0,
            "affected_closures": [],
            "alternative_paths": []
        }
    
    affected_closures = get_affected_closures_for_path(optimal_path, closure_schedule, query_time)
    
    quality_score = calculate_path_quality_score(
        optimal_path, graph, intersection_data, closure_schedule,
        query_time, critical_intersections, all_pairs_distances, closed_intersections
    )
    
    travel_time = calculate_travel_time_estimate(optimal_path, graph, intersection_data)
    
    alternative_paths = []
    if query_type in ["alternative_routes", "connectivity_check"]:
        alternative_paths = find_alternative_paths(
            graph, source, target, closed_intersections, intersection_data,
            max_alternatives, distance_threshold, optimal_path, closure_schedule,
            query_time, critical_intersections, all_pairs_distances
        )
    
    return {
        "query_id": query['query_id'],
        "query_type": query_type,
        "result_status": "success",
        "optimal_path": optimal_path,
        "path_distance": path_distance,
        "path_quality_score": round(quality_score, 1),
        "travel_time_estimate": travel_time,
        "affected_closures": affected_closures,
        "alternative_paths": alternative_paths
    }


def build_cluster_connectivity_matrix(intersection_data: List[Dict], graph: Dict[int, List[Dict]]) -> List[List[float]]:
    clusters = set(inter['neighborhood_cluster'] for inter in intersection_data)
    cluster_list = sorted(clusters)
    matrix_size = len(cluster_list)
    
    matrix = [[0.0 for _ in range(matrix_size)] for _ in range(matrix_size)]
    
    cluster_intersections = defaultdict(list)
    for inter in intersection_data:
        cluster_intersections[inter['neighborhood_cluster']].append(inter['intersection_id'])
    
    for i, cluster1 in enumerate(cluster_list):
        for j, cluster2 in enumerate(cluster_list):
            if i == j:
                matrix[i][j] = 1.0
            else:
                connectivity = calculate_cluster_connectivity(
                    cluster_intersections[cluster1],
                    cluster_intersections[cluster2],
                    graph
                )
                matrix[i][j] = round(connectivity, 1)
    
    return matrix


def calculate_cluster_connectivity(cluster1_nodes: List[int], cluster2_nodes: List[int], 
                                 graph: Dict[int, List[Dict]]) -> float:
    total_connections = 0
    possible_connections = len(cluster1_nodes) * len(cluster2_nodes)
    
    for node1 in cluster1_nodes:
        for node2 in cluster2_nodes:
            if is_path_exists(graph, node1, node2):
                total_connections += 1
    
    return total_connections / possible_connections if possible_connections > 0 else 0.0


def is_path_exists(graph: Dict[int, List[Dict]], start: int, end: int) -> bool:
    if start == end:
        return True
    
    visited = set()
    queue = deque([start])
    visited.add(start)
    
    while queue:
        current = queue.popleft()
        for edge in graph.get(current, []):
            neighbor = edge['target']
            if neighbor == end:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    return False


def calculate_total_connectivity_score(cluster_matrix: List[List[float]]) -> float:
    if not cluster_matrix:
        return 0.0
    
    total_score = 0.0
    total_pairs = 0
    
    for i in range(len(cluster_matrix)):
        for j in range(len(cluster_matrix[i])):
            if i != j:
                total_score += cluster_matrix[i][j]
                total_pairs += 1
    
    return total_score / total_pairs if total_pairs > 0 else 0.0


def count_connected_components(graph: Dict[int, List[Dict]], intersection_ids: Set[int]) -> int:
    visited = set()
    components = 0
    
    for node in intersection_ids:
        if node not in visited:
            components += 1
            queue = deque([node])
            visited.add(node)
            
            while queue:
                current = queue.popleft()
                for edge in graph.get(current, []):
                    neighbor = edge['target']
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
    
    return components


if __name__ == "__main__":
    road_network = [
        {"edge_id": 0, "intersection_a": 0, "intersection_b": 1, "segment_length": 800, "traffic_density": 0.6, "congestion_weight": 5, "road_type": "arterial", "max_speed_limit": 60},
        {"edge_id": 1, "intersection_a": 1, "intersection_b": 2, "segment_length": 1200, "traffic_density": 0.4, "congestion_weight": 3, "road_type": "residential", "max_speed_limit": 40},
        {"edge_id": 2, "intersection_a": 2, "intersection_b": 3, "segment_length": 900, "traffic_density": 0.8, "congestion_weight": 8, "road_type": "highway", "max_speed_limit": 80},
        {"edge_id": 3, "intersection_a": 0, "intersection_b": 2, "segment_length": 1500, "traffic_density": 0.3, "congestion_weight": 2, "road_type": "local", "max_speed_limit": 30},
        {"edge_id": 4, "intersection_a": 1, "intersection_b": 3, "segment_length": 1100, "traffic_density": 0.7, "congestion_weight": 6, "road_type": "arterial", "max_speed_limit": 50}
    ]

    intersection_data = [
        {"intersection_id": 0, "coordinates": {"x": 1000, "y": 2000}, "intersection_type": "commercial", "baseline_delay": 60, "connected_roads": [0, 3], "neighborhood_cluster": 1},
        {"intersection_id": 1, "coordinates": {"x": 2500, "y": 3000}, "intersection_type": "residential", "baseline_delay": 45, "connected_roads": [0, 1, 4], "neighborhood_cluster": 2},
        {"intersection_id": 2, "coordinates": {"x": 4000, "y": 2500}, "intersection_type": "industrial", "baseline_delay": 90, "connected_roads": [1, 2, 3], "neighborhood_cluster": 3},
        {"intersection_id": 3, "coordinates": {"x": 3500, "y": 4500}, "intersection_type": "highway", "baseline_delay": 30, "connected_roads": [2, 4], "neighborhood_cluster": 3}
    ]

    closure_schedule = [
        {"closure_id": 0, "affected_intersection": 1, "start_time": 24, "end_time": 48, "closure_reason": "construction", "priority_level": 2, "alternative_capacity": 0.3}
    ]

    query_batch = [
        {"query_id": 0, "query_type": "shortest_path", "source_intersection": 0, "target_intersection": 3, "query_time": 30, "max_alternative_paths": 2, "distance_threshold": 5000},
        {"query_id": 1, "query_type": "connectivity_check", "source_intersection": 0, "target_intersection": 2, "query_time": 10, "max_alternative_paths": 1, "distance_threshold": 3000}
    ]

    result = process_offline_graph_queries(road_network, intersection_data, closure_schedule, query_batch)
    print(result)