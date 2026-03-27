def sort_investment_portfolios(portfolios: list[dict]) -> list[dict]:
    # Validation: empty input returns []
    if portfolios is None:
        return []
    if not isinstance(portfolios, list):
        return []
    if len(portfolios) == 0:
        return []
    # Validate each item and gather names, also ensure exact keys
    required_keys = {'name', 'risk', 'return', 'references', 'sub_portfolios'}
    name_to_node: Dict[str, Dict[str, Any]] = {}
    all_names_in_input_order: List[str] = []
    def is_valid_name(n):
        return isinstance(n, str) and n != "" and n.isalpha()
    for item in portfolios:
        if not isinstance(item, dict):
            return []
        if set(item.keys()) != required_keys:
            return []
        name = item.get('name')
        if not is_valid_name(name):
            return []
        if name in name_to_node:
            return []  # duplicate names
        # risk and return must be numeric
        rsk = item.get('risk')
        rtn = item.get('return')
        if not (isinstance(rsk, (int, float)) and isinstance(rtn, (int, float))):
            return []
        try:
            # risk strictly >0
            if not (float(rsk) > 0 and math.isfinite(float(rsk))):
                return []
            if not math.isfinite(float(rtn)):
                return []
        except Exception:
            return []
        refs = item.get('references')
        subs = item.get('sub_portfolios')
        if not isinstance(refs, list) or not isinstance(subs, list):
            return []
        # maintain original object but do not modify lists
        name_to_node[name] = item
        all_names_in_input_order.append(name)
    # Validate sub_portfolios structure: ensure nested names unique across entire hierarchy
    seen_names = set()
    # We must ensure all names unique across entire hierarchy: that means sub_portfolios list elements are names? Problem statement: each portfolio may contain nested sub-portfolios -> but input top-level list contains all portfolios; sub_portfolios likely list of names. Validate that each sub_portfolios contains strings that are existing names? It says references to unknown names are ignored but for hierarchy uniqueness, "All portfolio names must be unique across the entire hierarchy." Probably sub_portfolios contain names; validate types.
    for name, node in name_to_node.items():
        # validate references entries types and detect self-reference
        for ref in node['references']:
            if not isinstance(ref, str):
                return []
            if ref == name:
                return []
            if ref == "":
                return []
            if not ref.isalpha():
                return []
        for sub in node['sub_portfolios']:
            if not isinstance(sub, str):
                return []
            if sub == "":
                return []
            if not sub.isalpha():
                return []
    # Ensure that all names across hierarchy are unique: meaning that sub_portfolios should refer to names that are present and no duplicates among all names? The earlier uniqueness check of top-level names suffices; but ensure no name appears as both top-level and nested? Ambiguous. We'll ensure that union of all names referenced in sub_portfolios plus top-level names has no duplicates beyond top-level set -> check that no sub_portfolio name duplicates another top-level name? Actually must be names unique across hierarchy: ensure every sub_portfolio name refers to an existing unique portfolio and not duplicated in multiple parents? We'll ensure that every sub_portfolio referenced refers to an existing portfolio name and that no portfolio is listed as sub_portfolio of more than one parent.
    # Build parent mapping for sub_portfolios
    parent_count = {}
    for parent, node in name_to_node.items():
        for sub in node['sub_portfolios']:
            if sub not in name_to_node:
                # references to unknown are allowed for references, but for sub_portfolios hierarchy probably must exist. Statement ambiguous; treat missing sub_portfolios as invalid structure.
                return []
            parent_count[sub] = parent_count.get(sub, 0) + 1
            if parent_count[sub] > 1:
                return []
    # Also ensure no cycles in hierarchy (a portfolio being ancestor of itself) - detect using DFS
    # Build hierarchical adjacency (parent->child) from sub_portfolios lists
    hierarchy_adj = {name: list(node['sub_portfolios'])[:] for name, node in name_to_node.items()}
    # Validate that sub_portfolios entries are unique per list? The adjacency deduplication rules apply to internal graph but input order must be preserved in output; duplicates in input sub_portfolios? Structural validation says lists; not explicit about duplicates. We'll allow duplicates but uniqueness across hierarchy already enforced by parent_count.
    # Detect hierarchy cycles
    visiting = set()
    visited = set()
    def dfs_h(u):
        visiting.add(u)
        for v in hierarchy_adj.get(u, []):
            if v not in name_to_node:
                return False
            if v in visiting:
                return False
            if v not in visited:
                ok = dfs_h(v)
                if not ok:
                    return False
        visiting.remove(u)
        visited.add(u)
        return True
    for n in name_to_node:
        if n not in visited:
            if not dfs_h(n):
                return []
    # Construct graph for scoring: nodes and reference edges plus hierarchical edges? Problem says capture both sub-portfolio (hierarchical) and reference edges. So adjacency includes both.
    adj = {}
    for name, node in name_to_node.items():
        refs = node['references']
        subs = node['sub_portfolios']
        # deduplicate and sort lexicographically for internal processing
        combined = list(dict.fromkeys(refs + subs))  # preserve first occurrence but we'll lex sort next
        # But requirement: All adjacency relationships must be deduplicated and sorted lexicographically.
        dedup_set = sorted(set(combined))
        adj[name] = dedup_set
    # Self-reference already checked
    # Compute base scores: return/risk finite and no division by zero
    base_score = {}
    try:
        for name, node in name_to_node.items():
            r = float(node['return'])
            s = float(node['risk'])
            val = r / s
            if not math.isfinite(val):
                return []
            base_score[name] = val
    except Exception:
        return []
    # Find strongly connected components using Tarjan on the constructed adjacency (lex order traversal)
    index = {}
    lowlink = {}
    index_counter = [0]
    stack = []
    onstack = set()
    sccs: List[List[str]] = []
    def strongconnect(v):
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        onstack.add(v)
        # process neighbors in lex order
        for w in sorted(adj.get(v, [])):
            if w not in name_to_node:
                continue
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in onstack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(sorted(comp))  # sort members lexicographically for determinism
    for v in sorted(name_to_node.keys()):
        if v not in index:
            strongconnect(v)
    # Map node to its scc leader (lexicographically smallest)
    node_to_scc = {}
    scc_leader = {}
    for comp in sccs:
        leader = min(comp)
        scc_leader[leader] = comp
        for n in comp:
            node_to_scc[n] = leader
    # Compute SCC base scores: for singletons not in cycle, they are their own comp; but cycles are components with size>1 or self-loop? Self-loops were invalid. So size>1 indicates cycle.
    scc_base_score = {}
    for leader, members in scc_leader.items():
        # arithmetic mean of members base scores
        vals = [base_score[m] for m in members]
        mean = sum(vals) / len(vals)
        if not math.isfinite(mean):
            return []
        scc_base_score[leader] = mean
    # Prepare graph of SCCs for acyclic processing: edges between scc leaders if any member references another member in different scc
    scc_adj = {}
    for name in sorted(name_to_node.keys()):
        src = node_to_scc[name]
        for nbr in adj.get(name, []):
            if nbr not in name_to_node:
                continue
            dst = node_to_scc[nbr]
            if dst == src:
                continue
            scc_adj.setdefault(src, set()).add(dst)
    # Convert adjacency sets to sorted lists
    for k in list(scc_adj.keys()):
        scc_adj[k] = sorted(scc_adj[k])
    # Now compute final scores for each SCC node. For SCCs that are cycles (size>1), score is scc_base_score and no further reference averaging for their members. For other SCCs (singletons), apply iterative or topological DP since graph of SCCs is acyclic.
    # Topologically sort SCC graph
    # Build in-degree
    all_sccs = sorted(scc_leader.keys())
    indeg = {s:0 for s in all_sccs}
    for u, nbrs in scc_adj.items():
        for v in nbrs:
            indeg[v] = indeg.get(v,0)+1
    # Kahn's algorithm with lex order
    queue = [s for s in sorted(all_sccs) if indeg.get(s,0)==0]
    topo = []
    while queue:
        u = queue.pop(0)
        topo.append(u)
        for v in scc_adj.get(u, []):
            indeg[v]-=1
            if indeg[v]==0:
                # insert maintaining lex order
                queue.append(v)
                queue.sort()
    if len(topo)!=len(all_sccs):
        return []
    # Initialize scc_score. For cycle SCCs (size>1) they are fixed to scc_base_score. For singleton, compute using referenced scores; formula: score(p) = base + 0.1 * average(score(references))
    # Because references can be to unknown, ignore them. References within same cycle treated per rules: members in cycle use cycle base score and do not get reference averaging.
    scc_score = {}
    # For determinism process topo order
    # First mark cycles
    scc_members = {leader: scc_leader[leader] for leader in all_sccs}
    is_cycle = {leader: (len(members)>1) for leader,members in scc_members.items()}
    # For each scc in topo:
    for s in topo:
        if is_cycle[s]:
            scc_score[s] = scc_base_score[s]
            continue
        # singleton
        member = scc_members[s][0]
        # gather references from original node (preserve duplicates ignored)
        refs = name_to_node[member]['references'][:]
        # ignore missing refs
        ref_scores = []
        seen = set()
        # deduplicate refs lexicographically for internal processing
        for r in sorted(set(refs)):
            if r not in name_to_node:
                continue
            # determine its scc and score
            r_scc = node_to_scc[r]
            # If referenced node is in a cycle, its score is scc_score (will be computed earlier if topo order ensures dependencies satisfied)
            if r_scc not in scc_score:
                # This can happen if reference points to a later topo node; but topo ensures dependencies before dependents; however references might be to nodes not connected in scc graph edges due to same-scc edges excluded. To be safe, process: if not available, treat as missing (ignored)
                continue
            ref_scores.append(scc_score[r_scc])
        if ref_scores:
            avg = sum(ref_scores)/len(ref_scores)
        else:
            avg = 0.0
        val = scc_base_score[s] + 0.1 * avg
        if not math.isfinite(val):
            return []
        scc_score[s] = val
    # Now assign final scores to individual portfolios: if in cycle, score = scc_score[leader]; else singleton scc score.
    final_scores = {}
    for name in sorted(name_to_node.keys()):
        leader = node_to_scc[name]
        final_scores[name] = scc_score[leader]
    # Round floating point values to exactly 10 decimal places before returning
    def round10(x):
        try:
            d = Decimal(str(float(x))).quantize(Decimal('0.0000000001'), rounding=ROUND_HALF_UP)
            return float(d)
        except (InvalidOperation, ValueError):
            return None
    rounded_scores = {}
    for k,v in final_scores.items():
        r = round10(v)
        if r is None or not math.isfinite(r):
            return []
        rounded_scores[k] = r
    # Prepare top-level portfolios: those not appearing as sub_portfolios of any other (roots)
    child_set = set()
    for node in name_to_node.values():
        for sub in node['sub_portfolios']:
            child_set.add(sub)
    top_level = [name for name in all_names_in_input_order if name not in child_set]
    if not top_level:
        return []
    # Sort top-level by descending _score then ascending name. Use floating tolerance 1e-12 for equality.
    def cmp(a,b):
        sa = rounded_scores[a]
        sb = rounded_scores[b]
        if abs(sa - sb) > 1e-12:
            return -1 if sa > sb else 1
        if a < b:
            return -1
        if a > b:
            return 1
        return 0
    top_level_sorted = sorted(top_level, key=lambda x: ( -rounded_scores[x], x ))
    # Build output list preserving original node dicts plus adding _score and _rank. Must preserve sub_portfolios and references exactly as in input.
    output = []
    rank = 1
    for name in top_level_sorted:
        orig = name_to_node[name]
        # create shallow copy to avoid mutating input
        out = {
            'name': orig['name'],
            'risk': orig['risk'],
            'return': orig['return'],
            'references': orig['references'],
            'sub_portfolios': orig['sub_portfolios'],
            '_score': round(rounded_scores[name], 10),
            '_rank': rank
        }
        output.append(out)
        rank += 1
    return output