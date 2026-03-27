def maximize_station_spacing(locations: List[List[int]],
                             tiers: List[int],
                             bridges: List[List[int]],
                             R: int,
                             k: int) -> float:
    # Union-find for tier connectivity
    max_tier = max(tiers) if tiers else -1
    parent = {}
    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra!=rb:
            parent[rb]=ra
    for a,b in bridges:
        union(a,b)
    # map each point's tier component
    tier_comp = [find(t) if t in parent or bridges else t for t in tiers]
    # build movement graph components using spatial grid to limit edges (distance <= R)
    n = len(locations)
    if k > n:
        return -1.0
    # grid cell size R
    cell_size = R
    grid = defaultdict(list)
    for i,(x,y) in enumerate(locations):
        gx = x//cell_size
        gy = y//cell_size
        grid[(gx,gy)].append(i)
    adj = [[] for _ in range(n)]
    R2 = R*R
    for i,(x,y) in enumerate(locations):
        gx = x//cell_size
        gy = y//cell_size
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for j in grid.get((gx+dx, gy+dy), []):
                    if j<=i: continue
                    if tier_comp[i] != tier_comp[j]:
                        continue
                    dx0 = x - locations[j][0]
                    dy0 = y - locations[j][1]
                    if dx0*dx0 + dy0*dy0 <= R2:
                        adj[i].append(j)
                        adj[j].append(i)
    # find connected components
    comp_id = [-1]*n
    comps = []
    cid = 0
    for i in range(n):
        if comp_id[i]!=-1: continue
        # BFS
        q = [i]
        comp_id[i]=cid
        for u in q:
            for v in adj[u]:
                if comp_id[v]==-1:
                    comp_id[v]=cid
                    q.append(v)
        comps.append(q)
        cid+=1
    # we need exactly k from a single component; consider components with size>=k
    candidate_components = [comp for comp in comps if len(comp)>=k]
    if not candidate_components:
        return -1.0
    # helper to test if in component we can pick k points with pairwise >= D using greedy with spatial hashing
    def feasible_in_comp(comp, D):
        D2 = D*D
        # sort points arbitrarily (e.g., by x)
        pts = [(locations[i][0], locations[i][1], i) for i in comp]
        pts.sort()
        cell = max(1e-9, D)  # cell size D
        grid2 = {}
        chosen = 0
        for x,y,i in pts:
            gx = int(math.floor(x/cell))
            gy = int(math.floor(y/cell))
            ok = True
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    key = (gx+dx, gy+dy)
                    if key in grid2:
                        for jx,jy in grid2[key]:
                            dx0 = x-jx
                            dy0 = y-jy
                            if dx0*dx0 + dy0*dy0 < D2 - 1e-9:
                                ok = False
                                break
                        if not ok:
                            break
                if not ok:
                    break
            if ok:
                grid2.setdefault((gx,gy), []).append((x,y))
                chosen += 1
                if chosen>=k:
                    return True
        return False

    import math
    # binary search D between 0 and max possible distance (use bounding box)
    xs = [p[0] for p in locations]
    ys = [p[1] for p in locations]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    hi = math.hypot(maxx-minx, maxy-miny)
    lo = 0.0
    # check initial feasibility quickly: if any component can pick k with D=0
    possible = False
    for comp in candidate_components:
        if len(comp) >= k:
            possible = True
            break
    if not possible:
        return -1.0
    # binary search with tolerance
    for _ in range(40):
        mid = (lo+hi)/2
        ok_any = False
        for comp in candidate_components:
            if feasible_in_comp(comp, mid):
                ok_any = True
                break
        if ok_any:
            lo = mid
        else:
            hi = mid
    return lo