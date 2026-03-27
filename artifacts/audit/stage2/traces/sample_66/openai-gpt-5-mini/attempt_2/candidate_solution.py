def manage_trust_relationships(participants: List[str], operations: List[List[str]]) -> List[bool]:
    # Validation of participants
    if participants is None or operations is None:
        return []
    if not isinstance(participants, list) or not isinstance(operations, list):
        return []
    # Participants must be unique, non-empty strings of letters
    seen = set()
    for p in participants:
        if not isinstance(p, str) or p == "" or not p.isalpha():
            return []
        if p in seen:
            return []
        seen.add(p)
    # Determine deterministic ordering of nodes
    nodes = sorted(participants)

    node_set = set(nodes)

    # Validate operations structure and content
    if not all(isinstance(op, list) and len(op) == 3 for op in operations):
        return []
    valid_ops = {"union", "split", "rekey", "find"}
    for op in operations:
        typ, a, b = op
        if not (isinstance(typ, str) and isinstance(a, str) and isinstance(b, str)):
            return []
        if typ not in valid_ops:
            return []
        if a == "" or b == "" or not a.isalpha() or not b.isalpha():
            return []
        if a not in node_set or b not in node_set:
            return []
        if a == b:
            return []
    # Represent undirected edges as frozenset of two nodes; but for deterministic iteration, store tuple sorted
    # Maintain adjacency dict mapping node -> sorted list of neighbors (kept as set but deterministic when traversing)
    adj = {n: set() for n in nodes}
    direct_edges = set()  # store as tuple (min,max)

    # Helper to edge key
    def edge_key(u, v):
        return (u, v) if u < v else (v, u)

    # Helper to do deterministic BFS/DFS for connectivity - use BFS with queue respecting lexicographic order
    def connected(u, v):
        if u == v:
            return True
        visited = set()
        # queue as list for deterministic pop(0)
        q = [u]
        visited.add(u)
        while q:
            cur = q.pop(0)
            # neighbors in sorted order
            nbrs = sorted(adj[cur])
            for nb in nbrs:
                if nb == v:
                    return True
                if nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        return False

    results = []
    # Process operations in order
    for typ, a, b in operations:
        ek = edge_key(a, b)
        if typ == "union":
            # If direct edge exists -> invalid
            if ek in direct_edges:
                return []
            # Add direct edge
            direct_edges.add(ek)
            adj[a].add(b)
            adj[b].add(a)
        elif typ == "split":
            if ek not in direct_edges:
                return []
            direct_edges.remove(ek)
            # remove adjacency
            adj[a].remove(b)
            adj[b].remove(a)
        elif typ == "rekey":
            # no-op
            continue
        elif typ == "find":
            res = connected(a, b)
            results.append(bool(res))
        else:
            return []
    return results