def maximize_station_spacing(locations: List[List[int]],
                             tiers: List[int],
                             bridges: List[List[int]],
                             R: int,
                             k: int) -> float:
    # Union-find for tiers
    max_tier = max(tiers) if tiers else -1
    parent = {}
    def find(a):
        if parent.setdefault(a, a) != a:
            parent[a] = find(parent[a])
        return parent[a]
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra!=rb:
            parent[rb]=ra
    for a,b in bridges:
        union(a,b)
    # Map each point to tier component id
    comp_tier = [find(t) for t in tiers]
    n = len(locations)
    # Build movement graph components: edges between points with same tier-component and dist <= R
    # Use grid hashing with cell size = R to find neighbors efficiently
    if n < k:
        return -1.0
    cell_size = R
    def cell_key(x,y,cs):
        return (x//cs, y//cs)
    cells = defaultdict(list)
    for i,(x,y) in enumerate(locations):
        cells[cell_key(x,y,cell_size)].append(i)
    adj = [[] for _ in range(n)]
    R2 = R*R
    for (cx,cy), idxs in list(cells.items()):
        for i in idxs:
            xi, yi = locations[i]
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    nbcell = (cx+dx, cy+dy)
                    for j in cells.get(nbcell,()):
                        if j<=i: continue
                        if comp_tier[i]!=comp_tier[j]: continue
                        xj,yj = locations[j]
                        dxij = xi-xj; dyij = yi-yj
                        if dxij*dxij+dyij*dyij <= R2:
                            adj[i].append(j)
                            adj[j].append(i)
    # Find connected components in movement graph
    comp_id = [-1]*n
    comps = []
    cid = 0
    for i in range(n):
        if comp_id[i]!=-1: continue
        # BFS
        q=[i]; comp_id[i]=cid
        for u in q:
            for v in adj[u]:
                if comp_id[v]==-1:
                    comp_id[v]=cid
                    q.append(v)
        comps.append(q)
        cid+=1
    # Only components with size >= k are usable
    usable = [c for c in comps if len(c)>=k]
    if not usable:
        return -1.0
    # For each component, we will attempt greedy maximal independent set with min distance D using grid of cell size = D
    def can_with_D(D):
        Df = float(D)
        D2 = Df*Df
        for comp in usable:
            # greedy select points in comp to get k spaced by >=D
            if len(comp) < k: continue
            if D==0.0:
                if len(comp) >= k:
                    return True
                continue
            cs = Df
            grid = {}
            selected = 0
            for i in comp:
                x,y = locations[i]
                gx = int(math.floor(x/cs))
                gy = int(math.floor(y/cs))
                ok = True
                for dx in (-1,0,1):
                    for dy in (-1,0,1):
                        cell = (gx+dx, gy+dy)
                        for j in grid.get(cell,()):
                            dxij = x - locations[j][0]
                            dyij = y - locations[j][1]
                            if dxij*dxij + dyij*dyij < D2 - 1e-9:
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok:
                        break
                if ok:
                    grid.setdefault((gx,gy), []).append(i)
                    selected += 1
                    if selected >= k:
                        return True
        return False

    # Binary search over D in [0, max_possible]
    # max_possible can be bounding box diagonal
    xs = [p[0] for p in locations]; ys = [p[1] for p in locations]
    maxd = math.hypot(max(xs)-min(xs), max(ys)-min(ys))
    lo = 0.0; hi = maxd
    # if can't even pick k with D=0 (should be true) check
    if not can_with_D(0.0):
        return -1.0
    for _ in range(40):
        mid = (lo+hi)/2
        if can_with_D(mid):
            lo = mid
        else:
            hi = mid
    return lo