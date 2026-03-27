def _parse_graph(graph: Dict[str, List[int]]) -> Tuple[Dict[int, List[Tuple[int,int,int]]], Dict[Tuple[int,int], List[Tuple[int,int]]]]:
    """
    Parse the flat graph into adjacency lists.
    Returns:
      adj: node -> list of (neighbor, cost, security)
      lanes: (u,v) -> list of lanes as (lane_id, security) [simulated single lane if not provided]
    """
    adj = defaultdict(list)
    lanes = defaultdict(list)
    lane_id_counter = 0
    for key, val in graph.items():
        try:
            u_str, v_str = key.split(",")
            u = int(u_str.strip())
            v = int(v_str.strip())
        except Exception:
            continue
        if not (isinstance(val, list) and len(val) >= 2):
            continue
        cost = int(val[0])
        security = int(val[1])
        # Insert adjacency and a simulated single-lane structure.
        adj[u].append((v, cost, security))
        lanes[(u, v)].append((lane_id_counter, security))
        lane_id_counter += 1
    return adj, lanes

def _dijkstra_with_security(adj: Dict[int, List[Tuple[int,int,int]]], start: int, end: int, min_sec: int) -> List[int]:
    """
    Dijkstra that prunes edges with security < min_sec.
    Returns path as list of nodes or [] if unreachable.
    Complexity: O(E log V)
    """
    dist = {}
    prev = {}
    pq = []
    heapq.heappush(pq, (0, start))
    dist[start] = 0
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist.get(u, None):
            continue
        if u == end:
            break
        for v, cost, security in adj.get(u, ()):
            if security < min_sec:
                continue
            nd = d + cost
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if end not in dist:
        return []
    # Reconstruct path
    path = []
    cur = end
    while cur != start:
        path.append(cur)
        cur = prev.get(cur)
        if cur is None:
            return []
    path.append(start)
    path.reverse()
    return path

def compute_secure_shortest_path(
    graph: Dict[str, List[int]],
    start: int,
    end: int,
    min_security_level: int
) -> List[int]:
    """
    Compute shortest path from start to end using only edges with security >= min_security_level.
    The input 'graph' uses "u,v" string keys mapping to [cost, security].
    This function is thread-safe for concurrent readers and simple writers via an internal lock.
    """
    # Basic validation
    if not isinstance(graph, dict):
        return []
    with _lock:
        adj, lanes = _parse_graph(graph)
        path = _dijkstra_with_security(adj, start, end, min_security_level)
        return path[:] if path else []