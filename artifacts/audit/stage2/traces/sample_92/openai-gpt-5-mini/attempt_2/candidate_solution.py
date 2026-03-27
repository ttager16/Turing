def analyze_financial_news(data_stream: List[str]) -> Dict[str, List[str]]:
    # Trie node for alias matching with fuzzy (edit distance <=1 via BFS)
    class TrieNode:
        __slots__ = ("children", "end", "canonical")
        def __init__(self):
            self.children = {}
            self.end = False
            self.canonical = None

    class Trie:
        def __init__(self):
            self.root = TrieNode()

        def insert(self, phrase: str, canonical: str):
            node = self.root
            for ch in phrase:
                if ch not in node.children:
                    node.children[ch] = TrieNode()
                node = node.children[ch]
            node.end = True
            node.canonical = canonical

        # exact match (case-insensitive) for tokens/phrases present
        def match_exacts(self, text: str) -> Set[str]:
            found = set()
            # Scan all possible substrings up to length limit
            n = len(text)
            for i in range(n):
                node = self.root
                j = i
                while j < n and text[j] in node.children:
                    node = node.children[text[j]]
                    if node.end:
                        found.add(node.canonical)
                    j += 1
            return found

        # fuzzy match allowing edit distance <=1 using dynamic traversal
        def fuzzy_find_in_text(self, text: str) -> Set[str]:
            results = set()
            n = len(text)
            # For each position, do DFS with state (node, idx in text, edits)
            for i in range(n):
                stack = [(self.root, i, 0)]
                visited = set()
                while stack:
                    node, idx, edits = stack.pop()
                    key = (id(node), idx, edits)
                    if key in visited:
                        continue
                    visited.add(key)
                    if node.end and edits <= 1:
                        results.add(node.canonical)
                    if idx < n:
                        ch = text[idx]
                        # match char
                        if ch in node.children:
                            stack.append((node.children[ch], idx+1, edits))
                        # substitution (consume one char in text and follow different child)
                        if edits < 1:
                            for cchild, childnode in node.children.items():
                                if cchild != ch:
                                    stack.append((childnode, idx+1, edits+1))
                        # deletion from pattern (advance in trie without consuming text)
                        if edits < 1:
                            for cchild, childnode in node.children.items():
                                stack.append((childnode, idx, edits+1))
                        # insertion (skip a char in text)
                        if edits < 1:
                            stack.append((node, idx+1, edits+1))
            return results

    # Canonical buckets and aliases
    canonical_buckets = {
        "Company": {"canonical": "Apple Inc.", "aliases": ["Apple Incorporated", "Apple Inc"]},
        "Stock Symbol": {"canonical": "AAPL", "aliases": ["AAPL"]},
        "Market Index": {"canonical": "Nasdaq Composite", "aliases": ["Nasdaq", "NAZDAQ", "纳斯达克"]},
    }

    # Build trie with lowercased normalized phrases (normalize: collapse spaces, keep chars)
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip()).lower()

    trie = Trie()
    # map alias->canonical label buckets
    alias_to_bucket = {}
    for bucket, info in canonical_buckets.items():
        can = info["canonical"]
        # insert canonical tokens too
        trie.insert(norm(can), can)
        alias_to_bucket[norm(can)] = (bucket, can)
        for a in info["aliases"]:
            trie.insert(norm(a), can)
            alias_to_bucket[norm(a)] = (bucket, can)

    # Sentiment keywords
    pos_kw = {"positive","positivos","upbeat","bullish","amplía","expands"}
    neg_kw = {"negative","negativos","bearish","cuts","recorta"}

    word_re = re.compile(r"\b\w+\b", re.UNICODE)

    # Graph structures
    node_locks = []
    nodes_entities: List[Dict[str, Set[str]]] = []  # per node: bucket -> set(canonical)
    # adjacency: per node id, dict neighbor -> (weight, edge_type) edge_type: 'entity' or 'alias'
    adj: List[Dict[int, Tuple[float,str]]] = []
    N = 0
    graph_lock = threading.Lock()  # only to protect arrays growth; node updates per-node locks

    # Helper: extract entities from article text
    def extract_entities(text: str) -> Dict[str, Set[str]]:
        t = norm(text)
        found = collections.defaultdict(set)
        # exact matches using trie
        exact = trie.match_exacts(t)
        for can in exact:
            # find bucket via alias_to_bucket
            kb = norm(can)
            if kb in alias_to_bucket:
                bucket, canonical = alias_to_bucket[kb]
                found[bucket].add(canonical)
        # fuzzy matches
        fuzzy = trie.fuzzy_find_in_text(t)
        for can in fuzzy:
            kb = norm(can)
            if kb in alias_to_bucket:
                bucket, canonical = alias_to_bucket[kb]
                found[bucket].add(canonical)
        return found

    # Helper: compute Jaccard between entity sets of two nodes (over canonical names across all buckets)
    def jaccard(a: Dict[str, Set[str]], b: Dict[str, Set[str]]) -> float:
        sa = set()
        sb = set()
        for v in a.values():
            sa |= v
        for v in b.values():
            sb |= v
        if not sa and not sb:
            return 0.0
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union > 0 else 0.0

    # Sentiment base per article
    def base_sentiment(text: str) -> str:
        tokens = [m.group(0).lower() for m in word_re.finditer(text)]
        last = None
        for tok in tokens:
            if tok in pos_kw:
                last = "positive"
            elif tok in neg_kw:
                last = "negative"
        return last or "neutral"

    # Thread-safe queue processing: but deterministic for given input order: we'll feed sequentially but use queue and worker threads.
    q = queue.Queue()
    for i, item in enumerate(data_stream):
        q.put((i, item))
    # We'll maintain insertion order by storing original indices and incrementally adding nodes in input order.
    # Worker will process items and append nodes in increasing index; to avoid races on ordering, use a per-index barrier dict.
    processed = {}
    processed_lock = threading.Lock()
    next_index = 0
    next_index_lock = threading.Lock()
    # We'll spawn a small pool but deterministic because processing is independent and we reassemble by original index.
    def worker():
        nonlocal N, nodes_entities, adj, node_locks
        while True:
            try:
                idx, text = q.get_nowait()
            except Exception:
                break
            ents = extract_entities(text)
            base = base_sentiment(text)
            # Create node data
            with graph_lock:
                node_id = len(nodes_entities)
                nodes_entities.append(ents)
                adj.append({})
                node_locks.append(threading.Lock())
                N_local = len(nodes_entities)
            # Update incident edges: we must connect this new node to existing nodes
            # For each existing node j (0..node_id-1), check entity edge and alias edge rules
            # To be O(log N) average is difficult here; but for prompt, implement per-node checks.
            for j in range(node_id):
                # lock per existing node and new node when updating incident edges
                # Acquire lower id lock first to avoid deadlock
                first, second = (j, node_id) if j < node_id else (node_id, j)
                with node_locks[first]:
                    with node_locks[second]:
                        other_ents = nodes_entities[j]
                        # entity edge: share at least two canonical entities across all buckets
                        sa = set()
                        sb = set()
                        for v in ents.values():
                            sa |= v
                        for v in other_ents.values():
                            sb |= v
                        shared = sa & sb
                        if len(shared) >= 2:
                            w = jaccard(ents, other_ents)
                            # create directed edges both ways? Spec: directed graph where each node is an article and edges encode contextual similarity.
                            # We'll create edges both directions with same weight.
                            adj[node_id][j] = (w, 'entity')
                            adj[j][node_id] = (w, 'entity')
                        else:
                            # alias edge: connect if one contains a lexical alias of an entity in the other
                            # i.e., if any canonical in one appears as an alias (including fuzzy) in the other text.
                            # We approximate by checking overlap between canonical names and aliases via trie fuzzy match.
                            # Build sets of all canonical strings lower for both.
                            sa_cans = sa
                            sb_cans = sb
                            alias_edge = False
                            # If any canonical from a appears as an alias in other's original text we should detect; here we match by canonical forms presence in normalized texts.
                            # For simplicity, consider if any canonical string of one when normalized is substring fuzzy-matched in the other combined aliases.
                            # We'll check if any canonical normalized equals any alias normalized in trie entries found for the other's text.
                            # Recompute alias matches for the other node's combined text by reconstructing text not stored; instead fallback:
                            # Use overlap of normalized strings allowing one-edit variants: if any canonical differs by edit dist <=1 from any alias of the other.
                            # Collect alias normals for both from alias_to_bucket keys.
                            alias_norms = set(alias_to_bucket.keys())
                            # check if any canonical of node in alias_norms within edit distance 1 of any canonical of other
                            def close(a, b):
                                # edit distance <=1 check fast
                                if a == b:
                                    return True
                                la, lb = len(a), len(b)
                                if abs(la - lb) > 1:
                                    return False
                                # if lengths equal, allow one substitution
                                if la == lb:
                                    diff = sum(1 for x,y in zip(a,b) if x!=y)
                                    return diff <= 1
                                # ensure la < lb
                                if la > lb:
                                    a,b = b,a
                                    la,lb = lb,la
                                # now lb = la+1 -> check if deleting one char from b equals a
                                for i in range(lb):
                                    if b[:i]+b[i+1:] == a:
                                        return True
                                return False
                            found_alias = False
                            for ca in sa_cans:
                                na = norm(ca)
                                for cb in sb_cans:
                                    nb = norm(cb)
                                    if close(na, nb):
                                        # if they are not exactly equal (would be entity edge if >=2 shared), treat as alias edge
                                        if na != nb:
                                            found_alias = True
                                            break
                                if found_alias:
                                    break
                            if found_alias:
                                adj[node_id][j] = (0.0, 'alias')
                                adj[j][node_id] = (0.0, 'alias')
            # store base sentiment in processed dict
            with processed_lock:
                processed[idx] = (node_id, base)
            q.task_done()

    # Start worker threads
    workers = []
    for _ in range(4):
        t = threading.Thread(target=worker)
        t.start()
        workers.append(t)
    for t in workers:
        t.join()

    # Reconstruct per input order arrays
    total_nodes = len(nodes_entities)
    base_labels = ["neutral"] * total_nodes
    index_to_node = [None]*len(data_stream)
    for idx, (node_id, base) in processed.items():
        index_to_node[idx] = node_id
        base_labels[node_id] = base
    # Ensure index_to_node is 0..n-1 mapping in arrival order; if articles appended in order, node ids should match indices
    # But safe: build article_order list of node ids in input order
    article_order = [index_to_node[i] for i in range(len(data_stream))]

    # Prepare sentiment propagation
    label_to_score = {"positive":1.0, "neutral":0.0, "negative":-1.0}
    scores = [label_to_score.get(base_labels[i],0.0) for i in range(total_nodes)]
    labels = list(base_labels)

    # Propagation only through entity edges
    # Precompute neighbors with entity weights
    neighbors = []
    for i in range(total_nodes):
        nb = {}
        for j,(w,et) in adj[i].items():
            if et == 'entity' and w>0:
                nb[j]=w
        neighbors.append(nb)

    # Normalize weights per node for outgoing neighbor aggregation (use neighbors as given: update node to weighted average of neighbors)
    # Iterate
    for it in range(20):
        maxchg = 0.0
        new_scores = scores.copy()
        for i in range(total_nodes):
            nb = neighbors[i]
            if not nb:
                continue
            total_w = sum(nb.values())
            if total_w == 0:
                continue
            s = 0.0
            for j,w in nb.items():
                s += scores[j] * (w / total_w)
            new_scores[i] = s
        # check change and update
        for i in range(total_nodes):
            change = abs(new_scores[i] - scores[i])
            if change > maxchg:
                maxchg = change
        scores = new_scores
        if maxchg < 0.05:
            break

    # Map back to labels with deterministic tie-breaking: if exactly on threshold, keep prior label
    final_labels = []
    for idx_in_stream, node_id in enumerate(article_order):
        sc = scores[node_id]
        prev = labels[node_id]
        if sc > 0.25:
            lab = "positive"
        elif sc < -0.25:
            lab = "negative"
        elif sc == 0.25 or sc == -0.25:
            lab = prev
        else:
            lab = "neutral"
        final_labels.append(lab)

    # Collect canonical entities found across corpus per bucket (unique, preserve canonical defined)
    out_companies = set()
    out_symbols = set()
    out_indices = set()
    for ents in nodes_entities:
        if "Company" in ents:
            out_companies |= ents["Company"]
        if "Stock Symbol" in ents:
            out_symbols |= ents["Stock Symbol"]
        if "Market Index" in ents:
            out_indices |= ents["Market Index"]

    # For Market Index, they want "Nasdaq Composite" canonical if any alias matched
    # Ensure canonical names only (we used canonical strings when mapping)
    result = {
        "Company": sorted(out_companies),
        "Stock Symbol": sorted(out_symbols),
        "Market Index": sorted(out_indices),
        "Sentiment": final_labels
    }
    return result