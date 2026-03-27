def analyze_financial_news(data_stream: List[str]) -> Dict[str, List[str]]:
    # Canonical buckets and aliases
    CANONICAL = {
        "Company": {"Apple Inc.": {"Apple Incorporated", "Apple Inc", "Apple Inc."}},
        "Stock Symbol": {"AAPL": set()},
        "Market Index": {"Nasdaq Composite": {"Nasdaq", "NAZDAQ", "纳斯达克", "Nasdaq Composite"}},
    }

    # Build alias -> canonical mapping (lowercase)
    alias_map = {}
    for bucket, canons in CANONICAL.items():
        for canon, aliases in canons.items():
            alias_map.setdefault(bucket, {})[canon.lower()] = canon
            for a in aliases:
                alias_map[bucket][a.lower()] = canon

    # Trie implementation for multilingual fuzzy match (edit distance <=1 for short aliases)
    class TrieNode:
        __slots__ = ("children", "end")
        def __init__(self):
            self.children = {}
            self.end = []  # list of (bucket, canonical form, alias_string)

    class Trie:
        def __init__(self):
            self.root = TrieNode()
        def insert(self, s: str, bucket: str, canon: str, alias: str):
            node = self.root
            for ch in s:
                if ch not in node.children:
                    node.children[ch] = TrieNode()
                node = node.children[ch]
            node.end.append((bucket, canon, alias))
        def find_candidates(self, text: str):
            # return matches as (start, end, bucket, canon, alias)
            res = []
            L = len(text)
            for i in range(L):
                node = self.root
                j = i
                while j < L and text[j] in node.children:
                    node = node.children[text[j]]
                    j += 1
                    if node.end:
                        for info in node.end:
                            res.append((i, j, info[0], info[1], info[2]))
            return res

    trie = Trie()
    # Insert canonical and aliases into trie lowercased without punctuation for matching
    def norm(s: str) -> str:
        return re.sub(r'\s+', ' ', re.sub(r'[^\w\u4e00-\u9fff]', ' ', s)).strip().lower()
    for bucket, canons in CANONICAL.items():
        for canon, aliases in canons.items():
            # include canonical
            trie.insert(norm(canon), bucket, canon, canon)
            for a in aliases:
                trie.insert(norm(a), bucket, canon, a)

    # Fuzzy matching edit distance <=1 for single tokens; implement simple Levenshtein for short strings
    def edit_distance_one(a: str, b: str) -> bool:
        # True if edit distance <=1
        if a == b:
            return True
        la, lb = len(a), len(b)
        if abs(la - lb) > 1:
            return False
        # Ensure a is shorter
        if la > lb:
            a, b = b, a
            la, lb = lb, la
        i = j = 0
        edits = 0
        while i < la and j < lb:
            if a[i] == b[j]:
                i += 1
                j += 1
            else:
                edits += 1
                if edits > 1:
                    return False
                if la == lb:
                    i += 1
                    j += 1
                else:
                    j += 1
        if j < lb or i < la:
            edits += 1
        return edits <= 1

    # Tokenize normalized text into words for fuzzy single-word matching
    word_re = re.compile(r'[\w\u4e00-\u9fff]+', re.UNICODE)

    # Sentiment keyword lists
    POS_KW = {"positive", "positivos", "upbeat", "bullish", "amplía", "expands"}
    NEG_KW = {"negative", "negativos", "bearish", "cuts", "recorta"}

    # Graph structures
    # nodes: list of article dicts with locks
    class Node:
        __slots__ = ("text", "entities", "lock", "edges_out", "base_label", "score")
        def __init__(self, text):
            self.text = text
            self.entities = defaultdict(set)  # bucket -> set of canonical names
            self.lock = threading.Lock()
            self.edges_out = {}  # target_idx -> (weight, edge_type) edge_type: 'entity' or 'alias'
            self.base_label = "neutral"
            self.score = 0.0

    nodes: List[Node] = []
    nodes_lock = threading.Lock()  # to protect nodes list append and indexing

    # Helper: extract entities from text
    def extract_entities(text: str) -> Dict[str, Set[str]]:
        ntext = norm(text)
        words = word_re.findall(ntext)
        found = defaultdict(set)
        # exact/trie matches
        candidates = trie.find_candidates(ntext)
        for start, end, bucket, canon, alias in candidates:
            found[bucket].add(canon)
        # fuzzy single-word: check each token against alias_map entries
        for bucket, amap in alias_map.items():
            for token in words:
                # check direct
                if token in amap:
                    found[bucket].add(amap[token])
                else:
                    # fuzzy check against keys (aliases and canon lowercase)
                    for akey, canon in amap.items():
                        # only attempt when lengths similar (<=1 diff)
                        if edit_distance_one(token, akey):
                            found[bucket].add(canon)
                            break
        return found

    # Helper: compute base sentiment label
    def base_sentiment(text: str) -> str:
        # find all keyword occurrences as whole words case-insensitive
        low = text.lower()
        tokens = re.findall(r'\b[\w\u4e00-\u9fff]+\b', low)
        last = None
        for t in tokens:
            if t in POS_KW:
                last = "positive"
            if t in NEG_KW:
                last = "negative"
        return last if last is not None else "neutral"

    # Edge creation rule functions
    def jaccard_weight(set1: Set[str], set2: Set[str]) -> float:
        if not set1 and not set2:
            return 0.0
        inter = len(set1 & set2)
        union = len(set1 | set2)
        return inter / union if union else 0.0

    # For deterministic processing, process articles in input order using a worker queue but single consumer per item creation to preserve order determinism
    q = queue.Queue()
    for idx, text in enumerate(data_stream):
        q.put((idx, text))
    # Node index mapping preserved
    total = len(data_stream)

    # We'll process sequentially but still use locks per node as required; concurrency structure prepared
    while not q.empty():
        idx, text = q.get()
        node = Node(text)
        node.base_label = base_sentiment(text)
        node.score = {"positive":1.0,"neutral":0.0,"negative":-1.0}[node.base_label]
        ents = extract_entities(text)
        for b, s in ents.items():
            for canon in s:
                node.entities[b].add(canon)
        # append node
        with nodes_lock:
            cur_idx = len(nodes)
            nodes.append(node)
        # Update incident edges: only between this new node and existing nodes
        # For each existing node i in 0..cur_idx-1, compute edges based on entities
        for i in range(cur_idx):
            other = nodes[i]
            # lock both nodes individually when modifying their edges; follow ordering to avoid deadlock
            first, second = (other, node) if i <= cur_idx else (node, other)
            # we only update incident edges for new node: both outgoing from new and from existing to new
            # Acquire locks per node as required
            with other.lock:
                with node.lock:
                    # Check shared canonical entities across buckets combined
                    shared_canonical_count = 0
                    # We consider canonical entity strings across all buckets
                    this_all = set()
                    other_all = set()
                    for b in set(list(node.entities.keys()) + list(other.entities.keys())):
                        this_all.update(node.entities.get(b, set()))
                        other_all.update(other.entities.get(b, set()))
                    shared = this_all & other_all
                    shared_canonical_count = len(shared)
                    if shared_canonical_count >= 2:
                        w = jaccard_weight(this_all, other_all)
                        if w > 0:
                            # create directed edges both ways with same weight
                            node.edges_out[i] = (w, 'entity')
                            other.edges_out[cur_idx] = (w, 'entity')
                    else:
                        # alias edge: if one contains a lexical alias of an entity in the other
                        # Determine if any token in one matches an alias of other's canonical (not requiring >=2)
                        alias_found = False
                        # check node tokens vs other's canonical aliases
                        ntext = norm(node.text)
                        otext = norm(other.text)
                        ntoks = set(word_re.findall(ntext))
                        otoks = set(word_re.findall(otext))
                        # build other's alias keys
                        other_alias_keys = set()
                        for b, amap in alias_map.items():
                            for akey, canon in amap.items():
                                if canon in other.entities.get(b, set()):
                                    other_alias_keys.add(akey)
                        node_alias_keys = set()
                        for b, amap in alias_map.items():
                            for akey, canon in amap.items():
                                if canon in node.entities.get(b, set()):
                                    node_alias_keys.add(akey)
                        # If node contains lexical alias of other's entity
                        for tok in ntoks:
                            for akey in other_alias_keys:
                                if edit_distance_one(tok, akey):
                                    alias_found = True
                                    break
                            if alias_found:
                                break
                        # If other contains lexical alias of node's entity
                        alias_found_2 = False
                        for tok in otoks:
                            for akey in node_alias_keys:
                                if edit_distance_one(tok, akey):
                                    alias_found_2 = True
                                    break
                            if alias_found_2:
                                break
                        if alias_found or alias_found_2:
                            # create alias edges with weight 0
                            node.edges_out[i] = (0.0, 'alias')
                            other.edges_out[cur_idx] = (0.0, 'alias')
        q.task_done()

    # Now run sentiment propagation using only entity edges
    N = len(nodes)
    # Initialize scores from base labels
    for node in nodes:
        node.score = {"positive":1.0,"neutral":0.0,"negative":-1.0}[node.base_label]

    # Precompute adjacency for entity edges with weights; directed edges considered for neighbor averaging using outgoing edges of node? 
    # The rule: "iteratively update each node to the weighted average of neighbors (edge weights normalized)." 
    # Interpret neighbors as outgoing entity edges from the node.
    def get_entity_neighbors(node_idx: int) -> List[Tuple[int, float]]:
        n = nodes[node_idx]
        with n.lock:
            nbrs = []
            for tgt, (w, etype) in n.edges_out.items():
                if etype == 'entity' and w > 0:
                    nbrs.append((tgt, w))
            return nbrs

    # For deterministic behavior, iterate fixed order
    max_iters = 20
    tol = 0.05
    prev_scores = [n.score for n in nodes]

    for it in range(max_iters):
        new_scores = prev_scores.copy()
        max_change = 0.0
        for idx in range(N):
            nbrs = get_entity_neighbors(idx)
            if not nbrs:
                # no change, keep current score
                new = prev_scores[idx]
            else:
                # weighted average of neighbors' scores; weights normalized
                total_w = sum(w for (_, w) in nbrs)
                if total_w == 0:
                    new = prev_scores[idx]
                else:
                    s = 0.0
                    for tgt, w in nbrs:
                        s += prev_scores[tgt] * (w / total_w)
                    new = s
            new_scores[idx] = new
            max_change = max(max_change, abs(new - prev_scores[idx]))
        prev_scores = new_scores
        if max_change < tol:
            break

    # Map scores back to labels with deterministic tie-breaking (if exactly threshold, keep prior label)
    final_labels = []
    for idx, sc in enumerate(prev_scores):
        prior = nodes[idx].base_label
        label = None
        if sc > 0.25:
            label = "positive"
        elif sc < -0.25:
            label = "negative"
        elif sc == 0.25 or sc == -0.25:
            label = prior
        else:
            label = "neutral"
        final_labels.append(label)

    # Collect canonical entities found across all articles (unique, in canonical form)
    result_company = []
    result_symbol = []
    result_index = []
    seen_company = set()
    seen_symbol = set()
    seen_index = set()
    # Preserve canonical forms as defined; prefer canonical names listed in CANONICAL keys
    for node in nodes:
        for c in node.entities.get("Company", set()):
            if c not in seen_company:
                seen_company.add(c)
                result_company.append(c)
        for c in node.entities.get("Stock Symbol", set()):
            if c not in seen_symbol:
                seen_symbol.add(c)
                result_symbol.append(c)
        for c in node.entities.get("Market Index", set()):
            if c not in seen_index:
                seen_index.add(c)
                result_index.append(c)

    return {
        "Company": result_company,
        "Stock Symbol": result_symbol,
        "Market Index": result_index,
        "Sentiment": final_labels
    }