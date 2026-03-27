def persistent_disjoint_set(
    operations: List[Tuple[str, Optional[int], Optional[int], Optional[int], Optional[Any]]]
) -> List[Union[bool, List[int]]]:
    # We'll implement a pragmatic persistent forest using per-version maps:
    # For each version we store:
    #  - parent: dict node->parent (tree parent; root maps to itself)
    #  - depth: dict node->depth
    #  - up: dict node->list of ancestors for binary lifting
    #  - min_up, max_up: dict node->list of min/max capacity to that ancestor
    # Also store adjacency of direct edges to support split and merges: edges set of frozenset(a,b)->capacity
    # Structural sharing: versions keep references to previous dicts and copy-on-write shallow for changed nodes.
    outputs: List[Union[bool, List[int]]] = []
    versions = []
    # initial empty version 0
    versions.append({
        'parent': {}, 'depth': {}, 'up': {}, 'min_up': {}, 'max_up': {}, 'edges': {}
    })
    LOG = 17  # supports up to 1e5 nodes ~17; extend dynamically if needed
    def ensure_log(n):
        nonlocal LOG
        needed = max(1, math.ceil(math.log2(max(2, n))))
        if needed+1 > LOG:
            LOG = needed+1
    def clone_version(idx):
        v = versions[idx]
        return {
            'parent': dict(v['parent']),
            'depth': dict(v['depth']),
            'up': {k:list(v['up'][k]) for k in v['up']},
            'min_up': {k:list(v['min_up'][k]) for k in v['min_up']},
            'max_up': {k:list(v['max_up'][k]) for k in v['max_up']},
            'edges': dict(v['edges'])
        }
    def make_node_structs(vdict, node):
        if node not in vdict['parent']:
            vdict['parent'][node] = node
            vdict['depth'][node] = 0
            vdict['up'][node] = [node]*LOG
            vdict['min_up'][node] = [10**18]*LOG
            vdict['max_up'][node] = [-10**18]*LOG
    def find_root(vdict, x):
        # no path compression; follow parent pointers
        if x not in vdict['parent']:
            return x
        while vdict['parent'][x] != x:
            x = vdict['parent'][x]
        return x
    def lca_and_agg(vdict, a, b):
        if a not in vdict['parent'] or b not in vdict['parent']:
            return None
        if a==b:
            return (0,0)
        da = vdict['depth'][a]
        db = vdict['depth'][b]
        minv = 10**18
        maxv = -10**18
        if da < db:
            a, b = b, a
            da, db = db, da
        diff = da - db
        i = 0
        while diff:
            if diff & 1:
                minv = min(minv, vdict['min_up'][a][i])
                maxv = max(maxv, vdict['max_up'][a][i])
                a = vdict['up'][a][i]
            diff >>= 1
            i += 1
        if a == b:
            return (minv if minv!=10**18 else 0, maxv if maxv!=-10**18 else 0)
        for i in range(LOG-1, -1, -1):
            if vdict['up'][a][i] != vdict['up'][b][i]:
                minv = min(minv, vdict['min_up'][a][i], vdict['min_up'][b][i])
                maxv = max(maxv, vdict['max_up'][a][i], vdict['max_up'][b][i])
                a = vdict['up'][a][i]
                b = vdict['up'][b][i]
        # now parents are same and are LCA
        minv = min(minv, vdict['min_up'][a][0], vdict['min_up'][b][0])
        maxv = max(maxv, vdict['max_up'][a][0], vdict['max_up'][b][0])
        return (minv, maxv)
    def add_edge_union(vdict, a, b, cap):
        # link roots: make parent of root_b = root_a
        ra = find_root(vdict, a)
        rb = find_root(vdict, b)
        if ra == rb:
            return False
        # attach rb under ra
        # ensure nodes exist
        make_node_structs(vdict, ra)
        make_node_structs(vdict, rb)
        # set parent of rb to ra and set up[rb][0]=ra with cap
        vdict['parent'][rb] = ra
        vdict['depth'][rb] = vdict['depth'][ra] + 1  # attach as child; depth of component roots arbitrary but keep tree
        # ensure up arrays length
        up_rb = [None]*LOG
        min_rb = [10**18]*LOG
        max_rb = [-10**18]*LOG
        up_rb[0] = ra
        min_rb[0] = cap
        max_rb[0] = cap
        for i in range(1, LOG):
            up_rb[i] = vdict['up'].get(up_rb[i-1], [up_rb[i-1]]*LOG)[i-1]
            min_rb[i] = min(min_rb[i-1], vdict['min_up'].get(up_rb[i-1], [10**18]*LOG)[i-1])
            max_rb[i] = max(max_rb[i-1], vdict['max_up'].get(up_rb[i-1], [-10**18]*LOG)[i-1])
        vdict['up'][rb] = up_rb
        vdict['min_up'][rb] = min_rb
        vdict['max_up'][rb] = max_rb
        # For all existing children of rb their ancestor tables remain valid (we treat rb as representative, subtree unchanged)
        # record edge
        vdict['edges'][frozenset((a,b))] = cap
        return True
    def rebuild_full_from_edges(edgedict):
        # Build forest from edges: edges are list of (a,b,cap). We'll create arbitrary roots and run unions producing parent/up.
        vdict = {'parent':{}, 'depth':{}, 'up':{}, 'min_up':{}, 'max_up':{}, 'edges': dict(edgedict)}
        # determine LOG
        nodes = set()
        for e in edgedict:
            a,b = tuple(e)
            nodes.add(a); nodes.add(b)
        ensure_log(max(2, len(nodes)))
        # Start by making each node its own root
        for node in nodes:
            vdict['parent'][node] = node
            vdict['depth'][node] = 0
            vdict['up'][node] = [node]*LOG
            vdict['min_up'][node] = [10**18]*LOG
            vdict['max_up'][node] = [-10**18]*LOG
        # Iteratively add edges ensuring no cycles (it's given edges form forest)
        for e, cap in edgedict.items():
            a,b = tuple(e)
            ra = find_root(vdict, a)
            rb = find_root(vdict, b)
            if ra == rb:
                continue
            # attach rb under ra
            vdict['parent'][rb] = ra
            vdict['depth'][rb] = vdict['depth'][ra] + 1
            up_rb = [None]*LOG
            min_rb = [10**18]*LOG
            max_rb = [-10**18]*LOG
            up_rb[0] = ra
            min_rb[0] = cap
            max_rb[0] = cap
            for i in range(1, LOG):
                up_rb[i] = vdict['up'].get(up_rb[i-1], [up_rb[i-1]]*LOG)[i-1]
                min_rb[i] = min(min_rb[i-1], vdict['min_up'].get(up_rb[i-1], [10**18]*LOG)[i-1])
                max_rb[i] = max(max_rb[i-1], vdict['max_up'].get(up_rb[i-1], [-10**18]*LOG)[i-1])
            vdict['up'][rb] = up_rb
            vdict['min_up'][rb] = min_rb
            vdict['max_up'][rb] = max_rb
        return vdict
    # process ops
    for op in operations:
        typ, a, b, vnum, extra = op
        cur_max = len(versions)-1
        if typ == 'union':
            base_v = versions[vnum]
            newv = clone_version(vnum)
            ensure_log(1000)  # approximate; LOG may be adjusted in rebuild
            # ensure nodes exist
            make_node_structs(newv, a)
            make_node_structs(newv, b)
            success = add_edge_union(newv, a, b, int(extra))
            versions.append(newv)
        elif typ == 'find':
            vdict = versions[vnum]
            ra = find_root(vdict, a)
            rb = find_root(vdict, b)
            outputs.append(ra == rb)
        elif typ == 'attributes':
            vdict = versions[vnum]
            if a==b:
                outputs.append([0,0])
            else:
                if a not in vdict['parent'] or b not in vdict['parent']:
                    outputs.append([])
                else:
                    if find_root(vdict, a) != find_root(vdict, b):
                        outputs.append([])
                    else:
                        res = lca_and_agg(vdict, a, b)
                        if res is None:
                            outputs.append([])
                        else:
                            outputs.append([res[0], res[1]])
        elif typ == 'branch':
            from_v = vnum
            newv = clone_version(from_v)
            versions.append(newv)
        elif typ == 'split':
            base_v = versions[vnum]
            newv = clone_version(vnum)
            key = frozenset((a,b))
            if key in newv['edges']:
                del newv['edges'][key]
            # rebuild structures from edges to ensure forest consistent
            new_rebuilt = rebuild_full_from_edges(newv['edges'])
            versions.append(new_rebuilt)
        elif typ == 'merge_versions':
            vX = vnum
            vY = extra  # note function signature placed vY in extra
            # However per problem, merge_versions tuple is ("merge_versions", None, None, vX, vY)
            # so vnum stores vX and extra stores vY
            # Build combined edges: union edges from both versions; check capacities non-negative
            edges = {}
            for e, cap in versions[vX]['edges'].items():
                edges[e] = cap
            conflict = False
            for e, cap in versions[vY]['edges'].items():
                if e in edges:
                    # capacities must be >=0 and equal? problem says overlapping routes satisfy constraint (e.g., capacity >=0)
                    # We'll require capacity >=0 for both and keep max(cap1,cap2)
                    if cap < 0 or edges[e] < 0:
                        conflict = True
                        break
                    edges[e] = max(edges[e], cap)
                else:
                    if cap < 0:
                        conflict = True
                        break
                    edges[e] = cap
            if conflict:
                # produce new version identical to max_version +1 as copy of vX (deterministic), but merge fails
                versions.append(clone_version(vX))
                outputs.append(False)
            else:
                # ensure result is forest (given constraint), build rebuilt
                ensure_log(1000)
                newv = rebuild_full_from_edges(edges)
                versions.append(newv)
                outputs.append(True)
        else:
            # unknown op: ignore
            versions.append(clone_version(0))
    return outputs