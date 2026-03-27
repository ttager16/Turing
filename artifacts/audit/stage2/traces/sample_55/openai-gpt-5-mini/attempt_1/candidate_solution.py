def sort_investment_portfolios(portfolios: list[dict]) -> list[dict]:
    # Validation
    if not isinstance(portfolios, list):
        return []
    if len(portfolios) == 0:
        return []
    # collect all names and check structure; also preserve mapping of input top-level
    name_to_obj = {}
    seen_names = set()
    def is_letter_string(s):
        return isinstance(s, str) and len(s) > 0 and s.isalpha()
    # Validate each top-level dict and recursively collect sub_portfolios
    def validate_and_collect(node):
        if not isinstance(node, dict):
            return False
        expected_keys = {'name', 'risk', 'return', 'references', 'sub_portfolios'}
        if set(node.keys()) != expected_keys:
            return False
        name = node.get('name')
        if not is_letter_string(name):
            return False
        if name in seen_names:
            return False
        seen_names.add(name)
        # risk and return numeric
        rsk = node.get('risk')
        ret = node.get('return')
        if not (isinstance(rsk, (int, float)) and isinstance(ret, (int, float))):
            return False
        if not (math.isfinite(rsk) and math.isfinite(ret)):
            return False
        if not (rsk > 0):
            return False
        refs = node.get('references')
        subs = node.get('sub_portfolios')
        if not isinstance(refs, list) or not isinstance(subs, list):
            return False
        # references entries must be strings of letters
        for ref in refs:
            if not isinstance(ref, str):
                return False
            if len(ref) == 0 or not ref.isalpha():
                return False
            if ref == name:
                return False  # self-reference invalid
        # store shallow copy of node to preserve order later
        name_to_obj[name] = node
        # recurse subs
        for sub in subs:
            if not validate_and_collect(sub):
                return False
        return True
    # Validate all top-level
    for p in portfolios:
        if not validate_and_collect(p):
            return []
    # Build graph: edges from name -> references + sub_portfolio names
    # Need adjacency deduped and sorted lexicographically for internal use
    nodes = sorted(name_to_obj.keys())
    adj = {n: [] for n in nodes}
    # Gather edges
    for n in nodes:
        obj = name_to_obj[n]
        # references: deduplicate, ignore unknowns
        refs = []
        seen = set()
        for r in obj['references']:
            if r in seen:
                continue
            seen.add(r)
            if r in name_to_obj:
                refs.append(r)
        refs_sorted = sorted(set(refs))
        # sub_portfolios: entries are objects; extract names
        subs = []
        seen_s = set()
        for s in obj['sub_portfolios']:
            if not isinstance(s, dict):
                return []
            sname = s.get('name')
            # sname must exist in name_to_obj (collected earlier)
            if sname not in name_to_obj:
                return []
            if sname in seen_s:
                continue
            seen_s.add(sname)
            subs.append(sname)
        subs_sorted = sorted(set(subs))
        # adjacency includes both types
        combined = sorted(set(refs_sorted + subs_sorted))
        adj[n] = combined
    # Build references-only adjacency for scoring references (references edges only)
    refs_adj = {n: sorted(set(r for r in name_to_obj[n]['references'] if r in name_to_obj)) for n in nodes}
    # Tarjan SCC on reference+subgraph? Problem states cycles detect in graph of both sub-portfolio (hierarchical) and reference (cross-link) edges.
    # Use adj (both types)
    index = {}
    lowlink = {}
    onstack = {}
    stack = []
    indices = [0]
    sccs = []
    def strongconnect(v):
        index[v] = indices[0]
        lowlink[v] = indices[0]
        indices[0] += 1
        stack.append(v)
        onstack[v] = True
        for w in adj[v]:
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif onstack.get(w, False):
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack[w] = False
                comp.append(w)
                if w == v:
                    break
            sccs.append(sorted(comp))  # sort members lexicographically
    for v in nodes:
        if v not in index:
            strongconnect(v)
    # Map node to scc id and representative name (lexicographically smallest in scc)
    scc_map = {}
    scc_reps = {}
    scc_members = {}
    for i, comp in enumerate(sccs):
        comp_sorted = sorted(comp)
        rep = comp_sorted[0]
        scc_reps[i] = rep
        scc_members[i] = comp_sorted
        for m in comp_sorted:
            scc_map[m] = i
    # Compute base scores: return/risk for each node; check finite
    base_scores = {}
    for n in nodes:
        rsk = name_to_obj[n]['risk']
        ret = name_to_obj[n]['return']
        if rsk == 0:
            return []
        val = ret / rsk
        if not math.isfinite(val):
            return []
        base_scores[n] = val
    # For SCCs that are cycles (size>1 or self-loop), their final score is mean of members base scores and not further adjusted.
    scc_score = {}
    for i in scc_members:
        members = scc_members[i]
        if len(members) == 1:
            # check self-loop: if node has edge to itself in adj, that's a cycle per rules -> then treated as cycle and should have been rejected earlier due self-reference validation prevented self-refs. So singleton SCC treated as non-cycle.
            scc_score[i] = None
        else:
            mean = sum(base_scores[m] for m in members) / len(members)
            if not math.isfinite(mean):
                return []
            scc_score[i] = mean
    # We need to compute scores solving dependencies: For nodes not in cycle, score = base + 0.1 * average(score(references))
    # References to missing ignored. For references that are in cycles, use cycle score as defined.
    # This is system of linear equations but graph is DAG when SCCs collapsed. Build component graph for references edges only? The formula uses references only, so use refs_adj but collapse SCCs.
    comp_nodes = sorted(set(scc_map[n] for n in nodes))
    comp_adj = {c: set() for c in comp_nodes}
    comp_members = {c: scc_members[c] if c in scc_members else [n for n in nodes if scc_map[n]==c]}
    for n in nodes:
        c = scc_map[n]
        for r in refs_adj[n]:
            if r not in name_to_obj:
                continue
            rc = scc_map[r]
            if rc == c:
                continue
            comp_adj[c].add(rc)
    # Convert to sorted lists
    for c in comp_adj:
        comp_adj[c] = sorted(comp_adj[c])
    # We need to compute comp scores. For components with predefined scc_score (non-None), that's fixed.
    # For others, equation: for a node p in component c with single member, score(p) = base + 0.1*avg(scores of references). For component collapsing with single node, comp_score equals node score.
    # For components that are singletons, comp_score unknown. Equations depend only on references which go to other components; since component graph is DAG, we can topologically sort.
    # Topo sort comp graph (detect cycles shouldn't exist)
    # Kahn's algorithm
    indeg = {c:0 for c in comp_nodes}
    for c in comp_nodes:
        for d in comp_adj[c]:
            indeg[d]+=1
    queue = [c for c in sorted(comp_nodes) if indeg[c]==0]
    topo = []
    while queue:
        c = queue.pop(0)
        topo.append(c)
        for d in comp_adj[c]:
            indeg[d]-=1
            if indeg[d]==0:
                queue.append(d)
    if len(topo) != len(comp_nodes):
        return []  # should not happen
    comp_score = {}
    # Process in topo order
    for c in topo:
        if scc_score.get(c,None) is not None:
            comp_score[c] = scc_score[c]
            continue
        # singleton component (one member)
        members = scc_members[c]
        if len(members) != 1:
            # unreachable: multi-member should have been scc_score
            return []
        n = members[0]
        # compute average of references scores; ignore missing refs
        ref_scores = []
        for r in refs_adj[n]:
            if r not in name_to_obj:
                continue
            rc = scc_map[r]
            # rc should have comp_score computed already because of topo order (references edges consistent)
            if rc not in comp_score:
                # if reference inside same comp, would be cycle; but self-ref prevented, so shouldn't happen
                return []
            ref_scores.append(comp_score[rc])
        if len(ref_scores) == 0:
            avg_ref = 0.0
        else:
            avg_ref = sum(ref_scores)/len(ref_scores)
        sc = base_scores[n] + 0.1 * avg_ref
        if not math.isfinite(sc):
            return []
        comp_score[c] = sc
    # Now assign per-node final scores: nodes in cycle components get comp_score (mean base), others get comp_score of their component.
    final_scores = {}
    for n in nodes:
        c = scc_map[n]
        sc = comp_score[c]
        final_scores[n] = sc
    # Round to exactly 10 decimal places
    def round10(x):
        d = Decimal(str(x)).quantize(Decimal('0.0000000000'), rounding=ROUND_HALF_UP)
        return float(d)
    rounded_scores = {n: round10(final_scores[n]) for n in nodes}
    # Prepare output: only top-level portfolios, preserve their internal order of references and sub_portfolios as input
    top_level = list(portfolios)  # original dicts
    # For sorting, need stable sort by descending _score then ascending name. Use rounded_scores; ties within 1e-12 treated lexicographically.
    def cmp(a,b):
        na = a['name']; nb = b['name']
        sa = rounded_scores.get(na, None)
        sb = rounded_scores.get(nb, None)
        if sa is None or sb is None:
            return 0
        # compare with tolerance
        if abs(sa - sb) <= 1e-12:
            if na < nb:
                return -1
            if na > nb:
                return 1
            return 0
        # descending score
        if sa > sb:
            return -1
        else:
            return 1
    sorted_top = sorted(top_level, key=cmp_to_key(cmp))
    # Assign ranks starting at 1 sequentially; but even equal scores get distinct ranks increasing order
    result = []
    rank = 1
    for item in sorted_top:
        n = item['name']
        # copy original dict but must include original fields plus _score and _rank
        out = {
            'name': item['name'],
            'risk': item['risk'],
            'return': item['return'],
            'references': item['references'],
            'sub_portfolios': item['sub_portfolios'],
            '_score': float(Decimal(str(rounded_scores[n])).quantize(Decimal('0.0000000000'), rounding=ROUND_HALF_UP)),
            '_rank': rank
        }
        rank += 1
        result.append(out)
    return result