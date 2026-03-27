def prioritize_mst(
    graph: List[List],
    priorities: List[List],
    updates: List[List]
) -> List[List[int]]:
    # Build adjacency with costs
    adj: Dict[int, Dict[int, float]] = defaultdict(dict)
    nodes: Set[int] = set()
    for u, v, c in graph:
        adj[u][v] = min(adj[u].get(v, float('inf')), float(c))
        adj[v][u] = min(adj[v].get(u, float('inf')), float(c))
        nodes.add(u); nodes.add(v)
    n = max(nodes) + 1 if nodes else 0

    # Apply updates to priorities list (extend if necessary)
    for vid, new_pr, new_rel in updates:
        if vid >= len(priorities):
            # extend with defaults
            for _ in range(len(priorities), vid + 1):
                priorities.append([0, 0.0])
        priorities[vid][0] = int(new_pr)
        priorities[vid][1] = float(new_rel)

    # Helper: compute a minimum spanning tree with Kruskal
    parent = list(range(n))
    rank = [0]*n
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra==rb: return False
        if rank[ra]<rank[rb]:
            parent[ra]=rb
        else:
            parent[rb]=ra
            if rank[ra]==rank[rb]:
                rank[ra]+=1
        return True

    edges = []
    for u in adj:
        for v,c in adj[u].items():
            if u < v:
                edges.append((c, u, v))
    edges.sort(key=lambda x: x[0])

    mst_edges: Set[Tuple[int,int]] = set()
    parent = list(range(n)); rank = [0]*n
    for c,u,v in edges:
        if union(u,v):
            mst_edges.add((u,v))
    # Ensure connectivity: if graph disconnected, include cheapest edges to connect components
    # (Kruskal did that for all nodes present in edges)

    # For each high-priority node, ensure two edge-disjoint paths to 0.
    # Approach: augment MST by adding cheapest additional edges that create a second edge-disjoint path.
    # We'll treat edge-disjointness: second path requires adding an edge that is not in the unique tree path's edges (i.e., adding any non-tree edge between node and some ancestor gives cycle).
    # For each high-priority node v != 0, find tree path from 0 to v; need at least one extra independent edge not sharing edges with first path -> minimal way is to add one non-tree edge that connects any node on path to any node outside path such that cycle provides alternative route.
    # Simplified heuristic: for each hp node, if there is at least one non-tree edge that connects any vertex on its tree path to any vertex not equal to its immediate tree-edge, add cheapest such non-tree edge. Repeat until all have 2 edge-disjoint paths or no more edges.
    # This is a heuristic aiming to satisfy constraints and keep cost low.

    # Build tree adjacency
    tree_adj = defaultdict(list)
    for u,v in mst_edges:
        tree_adj[u].append(v); tree_adj[v].append(u)

    # parent_tree and path retrieval via BFS from 0
    def build_tree_parent():
        par = [-1]*n
        depth = [-1]*n
        q = deque([0]) if 0 in nodes else deque()
        if q:
            par[0]=0; depth[0]=0
        while q:
            x=q.popleft()
            for y in tree_adj.get(x,[]):
                if depth[y]==-1:
                    depth[y]=depth[x]+1
                    par[y]=x
                    q.append(y)
        return par, depth

    par, depth = build_tree_parent()

    def tree_path(u,v):
        # return edges (a,b) along tree path u->v with ordered tuple (min,max)
        path_u=[]; path_v=[]
        a=u; b=v
        du = depth[a] if a<n and a>=0 else -1
        dv = depth[b] if b<n and b>=0 else -1
        if du==-1 or dv==-1:
            return []
        while a!=b:
            if du>=dv:
                pa = par[a]
                path_u.append((min(a,pa), max(a,pa)))
                a=pa; du-=1
            else:
                pb = par[b]
                path_v.append((min(b,pb), max(b,pb)))
                b=pb; dv-=1
        return path_u + path_v[::-1]

    # Set of non-tree edges
    non_tree = []
    tree_edge_set = set(mst_edges)
    for c,u,v in edges:
        key = (u,v) if u<v else (v,u)
        if key not in tree_edge_set:
            non_tree.append((c,u,v))

    # Function to check edge-disjoint count between node and 0: compute two edge-disjoint paths existence via simple check:
    # If there are at least two edge-disjoint paths in current selected edges set. We'll test by computing max-flow with unit capacities on edges (undirected => split into two directed). Use Edmonds-Karp.
    def has_two_edge_disjoint(v, selected_edges_set):
        if v==0: return True
        # build directed graph
        idx = defaultdict(list)
        cap = {}
        for a,b in selected_edges_set:
            # add both directions with capacity 1
            idx[a].append(b); idx[b].append(a)
            cap[(a,b)] = cap.get((a,b),0) + 1
            cap[(b,a)] = cap.get((b,a),0) + 1
        # Edmonds-Karp from 0 to v
        def bfs(s,t,parent):
            q=deque([s])
            visited=set([s])
            while q:
                x=q.popleft()
                for y in idx.get(x,[]):
                    if (x,y) in cap and cap[(x,y)]>0 and y not in visited:
                        visited.add(y)
                        parent[y]=x
                        if y==t: return True
                        q.append(y)
            return False
        flow=0
        parent={}
        s=0; t=v
        while bfs(s,t,parent):
            # find min residual
            path=[]
            cur=t
            f=float('inf')
            while cur!=s:
                p=parent[cur]
                f=min(f, cap[(p,cur)])
                cur=p
            # apply
            cur=t
            while cur!=s:
                p=parent[cur]
                cap[(p,cur)] -= f
                cap[(cur,p)] = cap.get((cur,p),0) + f
                cur=p
            flow += f
            if flow>=2: return True
            parent={}
        return flow>=2

    # Selected edges start as MST edges
    selected = set(tree_edge_set)

    # Iteratively try to satisfy each high-priority node
    hp_nodes = {i for i in range(len(priorities)) if i < n and int(priorities[i][0])==1}
    # greedy add cheapest non-tree edges when they help any hp node lacking redundancy
    non_tree.sort()
    changed = True
    while True:
        lacking = [v for v in hp_nodes if not has_two_edge_disjoint(v, selected)]
        if not lacking:
            break
        added_any = False
        # evaluate non-tree edges sorted by cost, pick one that increases count of satisfied hp nodes most per cost (greedy)
        best_pick = None
        best_gain = 0
        for c,u,v in non_tree:
            key = (u,v) if u<v else (v,u)
            if key in selected: continue
            # simulate adding
            sim_selected = set(selected)
            sim_selected.add(key)
            gain = 0
            for node in lacking:
                if has_two_edge_disjoint(node, sim_selected):
                    gain += 1
            if gain>0:
                # score = gain / cost ; choose best gain then min cost
                if best_pick is None or (gain>best_gain) or (gain==best_gain and c < best_pick[0]):
                    best_pick = (c,u,v,key)
                    best_gain = gain
        if best_pick:
            _,u,v,key = best_pick
            selected.add(key)
            # if edge is not in tree, also add to tree_adj for future path computations (we keep tree separate; but adding edges to selected)
            added_any = True
            # continue to next iteration
        if not added_any:
            # cannot satisfy more; break
            break

    # Ensure overall connectivity across all nodes: selected edges should connect all nodes; if not, add cheapest edges to connect components
    parent = list(range(n))
    def findp(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def unionp(a,b):
        ra,rb=findp(a),findp(b)
        if ra==rb: return False
        parent[rb]=ra
        return True
    for a,b in selected:
        unionp(a,b)
    for c,u,v in edges:
        key = (u,v) if u<v else (v,u)
        if findp(u)!=findp(v):
            selected.add(key)
            unionp(u,v)
    # Final output as list of [u,v]
    res = [[u,v] for u,v in sorted(selected)]
    return res