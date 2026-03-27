def find_planar_separators(
    graph: Dict[str, List[str]],
    queries: List[List]
) -> List[List[int]]:
    # Convert node ids to ints and build adjacency set
    adj = defaultdict(set)
    def add_edge(u, v):
        if u == v: return
        adj[u].add(v)
        adj[v].add(u)
    def remove_edge(u, v):
        adj[u].discard(v)
        adj[v].discard(u)
        # Do not remove node entries; nodes exist if referenced
    
    # Initialize from graph dict (keys and neighbor ids are strings)
    nodes_set = set()
    for k, nbrs in graph.items():
        try:
            u = int(k)
        except:
            u = int(str(k))
        nodes_set.add(u)
        for w in nbrs:
            try:
                v = int(w)
            except:
                v = int(str(w))
            nodes_set.add(v)
            add_edge(u, v)
    # Also ensure nodes mentioned indirectly are in adj
    for n in nodes_set:
        if n not in adj:
            adj[n] = set()
    # helper: get connected components after removing S (set)
    def components_after_removal(S):
        seen = set()
        comps = []
        for node in adj:
            if node in S or node in seen:
                continue
            # BFS
            q = deque([node])
            seen.add(node)
            cnt = 0
            while q:
                x = q.popleft()
                cnt += 1
                for y in adj[x]:
                    if y in S or y in seen:
                        continue
                    seen.add(y)
                    q.append(y)
            comps.append((node, cnt))  # representative and size
        # return list of sizes
        sizes = [s for (_, s) in comps]
        return sizes, comps
    # helper: check targets separated by S
    def targets_separated(targets, S):
        # map node -> component id via BFS ignoring S
        comp_id = {}
        cid = 0
        for node in adj:
            if node in S or node in comp_id:
                continue
            q = deque([node])
            comp_id[node] = cid
            while q:
                x = q.popleft()
                for y in adj[x]:
                    if y in S or y in comp_id:
                        continue
                    comp_id[y] = cid
                    q.append(y)
            cid += 1
        # nodes absent in adj? Treat as singleton component with unique ids
        for t in targets:
            if t not in adj:
                # unique component per absent node: use negative id unique by t
                comp_id[t] = ('isol', t)
        seen = set()
        for t in targets:
            cid_t = comp_id.get(t, ('isol', t))
            if cid_t in seen:
                return False
            seen.add(cid_t)
        return True
    # compute balance ratio
    def balance_ok(S):
        sizes, comps = components_after_removal(S)
        if not sizes:
            return True
        s_min = min(sizes)
        s_max = max(sizes)
        if s_min == 0:
            return False
        return (s_max / s_min) <= 1.2
    # Try small separators heuristically: single nodes, articulation points, neighborhood cuts
    def find_separator_for_query(targets):
        # ensure targets are ints
        targets = [int(t) for t in targets]
        S = set()
        # Quick check: already separated without removal
        if targets_separated(targets, S):
            return []
        # Candidate set: articulation points via Tarjan (global)
        # Tarjan iterative
        N = list(adj.keys())
        index = {}
        low = {}
        parent = {}
        idx = 0
        artic = set()
        stack = []
        for start in N:
            if start in index:
                continue
            parent[start] = None
            stack.append((start, iter(adj[start])))
            index[start] = idx
            low[start] = idx
            idx += 1
            child_count = {start:0}
            while stack:
                v, it = stack[-1]
                try:
                    w = next(it)
                    if w not in index:
                        parent[w] = v
                        index[w] = idx
                        low[w] = idx
                        idx += 1
                        child_count[w] = 0
                        child_count[v] = child_count.get(v,0) + 1
                        stack.append((w, iter(adj[w])))
                    else:
                        if parent[v] != w:
                            # back edge
                            low[v] = min(low[v], index[w])
                except StopIteration:
                    stack.pop()
                    p = parent[v]
                    if p is not None:
                        low[p] = min(low[p], low[v])
                        if low[v] >= index[p]:
                            # p is articulation if p not root or has multiple children
                            if parent[p] is not None or child_count.get(p,0) > 1:
                                artic.add(p)
                    else:
                        # root handled: if child_count >1 then it's artic; already set
                        if child_count.get(v,0) > 1:
                            artic.add(v)
        # Try single-node separators: articulation points first, then neighborhood nodes of targets
        candidates1 = sorted(artic)
        # also include neighbors of targets and targets themselves
        extra = set()
        for t in targets:
            if t in adj:
                extra.update(adj[t])
            extra.add(t)
        candidates1.extend(sorted(x for x in extra if x not in set(candidates1)))
        # evaluate singletons
        for c in candidates1:
            S = {c}
            if targets_separated(targets, S):
                if balance_ok(S):
                    return sorted(S)
                else:
                    # keep as potential fallback smallest separating
                    fallback = sorted(S)
                    return fallback
        # Try pairs from small frontier: neighbors of targets union targets, limited to first 50 nodes
        frontier = sorted(extra)
        frontier = frontier[:50]
        best_sep = None
        # try pairs
        for i in range(len(frontier)):
            for j in range(i, len(frontier)):
                s = {frontier[i], frontier[j]}
                if targets_separated(targets, s):
                    if balance_ok(s):
                        return sorted(s)
                    if best_sep is None or len(s) < len(best_sep):
                        best_sep = set(s)
            if i > 20:  # bound
                break
        if best_sep:
            return sorted(best_sep)
        # BFS-based multi-source separator growth:
        # Grow distances from each target ignoring others; collect frontier nodes where waves meet
        # Compute multi-source BFS labeling nodes by nearest target
        label = {}
        dist = {}
        q = deque()
        for idx_t, t in enumerate(targets):
            if t in adj:
                label[t] = idx_t
                dist[t] = 0
                q.append(t)
            else:
                label[t] = idx_t
                dist[t] = 0
        meet_nodes = set()
        while q:
            v = q.popleft()
            for w in adj.get(v,()):
                if w in label:
                    if label[w] != label[v]:
                        meet_nodes.add(w)
                else:
                    label[w] = label[v]
                    dist[w] = dist[v] + 1
                    q.append(w)
        # candidate separator: nodes that have neighbors in multiple labels
        border = set()
        for node in adj:
            neigh_labels = set()
            for nb in adj[node]:
                if nb in label:
                    neigh_labels.add(label[nb])
            if len(neigh_labels) >= 2:
                border.add(node)
        border = sorted(border)
        # try incremental sizes up to 10
        from itertools import combinations
        limit = min(len(border), 12)
        for r in range(1, min(4, limit+1)):
            for comb in combinations(border[:limit], r):
                s = set(comb)
                if targets_separated(targets, s):
                    if balance_ok(s):
                        return sorted(s)
                    if best_sep is None or len(s) < len(best_sep):
                        best_sep = set(s)
        if best_sep:
            return sorted(best_sep)
        # As ultimate fallback: separate by cutting all neighbors of one target to isolate it iteratively
        # Try to separate by isolating each target: take its neighborhood as separator
        smallest = None
        for t in targets:
            neigh = set(adj.get(t, set()))
            if targets_separated(targets, neigh):
                if balance_ok(neigh):
                    return sorted(neigh)
                if smallest is None or len(neigh) < len(smallest):
                    smallest = set(neigh)
        if smallest:
            return sorted(smallest)
        # If nothing found, as last resort select union of shortest paths between targets' pairs (internal nodes)
        # BFS to get path between each pair
        sep = set()
        for i in range(len(targets)):
            for j in range(i+1, len(targets)):
                a = targets[i]; b = targets[j]
                if a not in adj or b not in adj:
                    continue
                # BFS from a to b
                prev = {}
                q = deque([a])
                found = False
                prev[a] = None
                while q:
                    x = q.popleft()
                    if x == b:
                        found = True
                        break
                    for y in adj[x]:
                        if y not in prev:
                            prev[y] = x
                            q.append(y)
                if found:
                    # take middle node(s) of path as separator
                    path = []
                    cur = b
                    while cur is not None:
                        path.append(cur)
                        cur = prev[cur]
                    if len(path) >= 3:
                        mid = path[len(path)//2]
                        sep.add(mid)
                    elif len(path) == 2:
                        sep.add(path[0])
                    else:
                        sep.add(path[0])
        if sep:
            # local minimality will prune
            return sorted(sep)
        # nothing possible: return empty
        return []
    # local minimality pruning
    def prune_local_minimal(S_list, targets):
        S = list(sorted(set(S_list)))
        # try removing in ascending ID order
        for x in list(S):
            cand = set(S)
            cand.discard(x)
            if targets_separated(targets, cand):
                if balance_ok(cand):
                    S = sorted(cand)
                else:
                    # if removing still enforces separation but breaks balance,
                    # we only accept removal if original was already not balanced?
                    # But requirement: keep node removed only if separation and balance still hold.
                    # So do not remove if balance breaks.
                    pass
        return sorted(S)
    results = []
    for op in queries:
        if not op:
            continue
        if op[0] == "add":
            try:
                u = int(op[1]); v = int(op[2])
            except:
                u = int(str(op[1])); v = int(str(op[2]))
            nodes_set.add(u); nodes_set.add(v)
            add_edge(u, v)
            if u not in adj: adj[u] = set()
            if v not in adj: adj[v] = set()
        elif op[0] == "remove":
            try:
                u = int(op[1]); v = int(op[2])
            except:
                u = int(str(op[1])); v = int(str(op[2]))
            remove_edge(u, v)
            nodes_set.add(u); nodes_set.add(v)
            if u not in adj: adj[u] = set()
            if v not in adj: adj[v] = set()
        elif op[0] == "query":
            targets_raw = op[1]
            targets = [int(t) for t in targets_raw]
            sep = find_separator_for_query(targets)
            # local minimality pruning as specified: greedily try removing nodes in ascending order
            sep_pruned = prune_local_minimal(sep, targets)
            results.append(sorted(sep_pruned))
        else:
            # ignore unknown
            continue
    return results