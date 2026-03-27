import threading
import queue
import re
from itertools import combinations
from typing import Dict, List, Optional

def analyze_financial_news(data_stream: List[str]) -> Dict[str, List[str]]:
    """Extract canonical entities and final sentiments from multilingual financial articles.
    Why: Fixes Py<3.10 type-hint incompatibilities and ensures thread-safe shared-structure updates.
    """

    # =========================
    # Canonical buckets & aliases (lowercased for matching)
    # =========================
    BUCKETS = {
        "Company": [
            ("Apple Inc.", {"apple inc.", "apple incorporated", "apple inc"}, set())
        ],
        "Stock Symbol": [
            ("AAPL", {"aapl"}, set())  # IMPORTANT: no aliases -> no fuzzy for tickers
        ],
        "Market Index": [
            ("Nasdaq Composite", {"nasdaq composite", "nasdaq"}, {"nazdaq", "纳斯达克"})
        ],
    }

    # Build sets for canonical & alias phrases; and a map to the primary canonical name
    canonicals_per_bucket = {b: set() for b in BUCKETS}
    aliases_per_bucket = {b: set() for b in BUCKETS}
    primary_for_phrase = {}  # (bucket, phrase_lower) -> primary name
    for b, items in BUCKETS.items():
        for primary, canon_set, alias_set in items:
            for p in canon_set:
                canonicals_per_bucket[b].add(p)
                primary_for_phrase[(b, p)] = primary
            for a in alias_set:
                aliases_per_bucket[b].add(a)
                primary_for_phrase[(b, a)] = primary

    # =========================
    # Sentiment keywords (case-insensitive, whole-word)
    # =========================
    POS_WORDS = {"positive", "positivos", "upbeat", "bullish", "amplía", "expands"}
    NEG_WORDS = {"negative", "negativos", "bearish", "cuts", "recorta"}

    # =========================
    # Helpers (local to maintain single top-level function)
    # =========================
    def normalize_text(txt: str) -> str:
        cleaned = re.sub(r"[^\w\s\.\-]", " ", txt.lower(), flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def tokenize(txt: str) -> List[str]:
        return [t for t in re.split(r"\s+", txt) if t]

    def edit_dist_leq1(a: str, b: str) -> bool:
        if a == b:
            return True
        la, lb = len(a), len(b)
        if abs(la - lb) > 1:
            return False
        i = j = edits = 0
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
                elif la > lb:
                    i += 1
                else:
                    j += 1
        if i < la or j < lb:
            edits += 1
        return edits <= 1

    # =========================
    # Token-level Trie for multi-word phrases (canonical & aliases)
    #   node = {"_end": [(bucket, primary, is_alias)], <token>: child_node}
    #   Canonicals match exactly; aliases allow per-token edit<=1
    # =========================
    def build_token_trie():
        root = {}

        def insert(phrase: str, bucket: str, primary: str, is_alias: bool):
            node = root
            for tok in tokenize(phrase):
                node = node.setdefault(tok, {})
            node.setdefault("_end", []).append((bucket, primary, is_alias))

        for b in BUCKETS:
            for p in canonicals_per_bucket[b]:
                insert(p, b, primary_for_phrase[(b, p)], False)
            for a in aliases_per_bucket[b]:
                insert(a, b, primary_for_phrase[(b, a)], True)
        return root

    TRIE = build_token_trie()

    def trie_scan_exact(tokens: List[str], start: int):
        """Exact token match from start using trie; yields matches (end_index_exclusive, bucket, primary, is_alias)."""
        node = TRIE
        i = start
        out = []
        while i < len(tokens) and tokens[i] in node:
            node = node[tokens[i]]
            i += 1
            if "_end" in node:
                for (b, primary, is_alias) in node["_end"]:
                    out.append((i, b, primary, is_alias))
        return out

    def trie_scan_alias_fuzzy(tokens: List[str], start: int):
        """
        Alias fuzzy match: walk trie against tokens allowing per-token edit distance <=1,
        but only along paths that correspond to alias phrases (is_alias=True).
        """
        out = []
        stack = [(TRIE, start)]
        while stack:
            node, i = stack.pop()
            if "_end" in node:
                for (b, primary, is_alias) in node["_end"]:
                    if is_alias:
                        out.append((i, b, primary, True))
            if i >= len(tokens):
                continue
            tok = tokens[i]
            for child_tok, child_node in node.items():
                if child_tok == "_end":
                    continue
                if edit_dist_leq1(tok, child_tok):
                    stack.append((child_node, i + 1))
        return out

    # =========================
    # Concurrency & Indices
    # =========================
    N = len(data_stream)
    q_ingest: "queue.Queue" = queue.Queue()
    for i, txt in enumerate(data_stream):
        q_ingest.put((i, txt))
    # Sentinel per worker
    WORKERS = 2
    for _ in range(WORKERS):
        q_ingest.put(None)

    node_locks = [threading.Lock() for _ in range(N)]

    # Per-article state
    article_canon = [None] * N            # dict[bucket] -> set(primary)
    article_alias = [None] * N            # dict[bucket] -> set(primary)
    base_sent_scores = [0.0] * N
    canon_sets = [set() for _ in range(N)]  # set of (bucket, primary)

    # Indices (shared) + locks (WHY: avoid race on dict resize)
    canonical_index = {b: {} for b in BUCKETS}   # bucket -> primary -> set(article indices)
    alias_index = {b: {} for b in BUCKETS}       # bucket -> primary -> set(article indices)
    pair_index = {}                               # key=((b1,p1),(b2,p2)) -> set(article indices)
    idx_lock = threading.Lock()
    pair_lock = threading.Lock()

    # Directed adjacency (entity edges only; alias edges not used for propagation)
    entity_adj_dir = [{} for _ in range(N)]  # i -> {j: weight}

    def worker():
        while True:
            item = q_ingest.get()
            if item is None:
                break
            i, raw = item
            text_norm = normalize_text(raw)
            tokens = tokenize(text_norm)

            # ---- Base sentiment (last keyword wins) ----
            last_label = None
            for tok in tokens:
                if tok in POS_WORDS:
                    last_label = "positive"
                elif tok in NEG_WORDS:
                    last_label = "negative"
            base = 1.0 if last_label == "positive" else (-1.0 if last_label == "negative" else 0.0)

            # ---- Entity extraction ----
            c_hits = {b: set() for b in BUCKETS}
            a_hits = {b: set() for b in BUCKETS}

            # Canonicals (exact trie)
            for s in range(len(tokens)):
                for _, b, primary, is_alias in trie_scan_exact(tokens, s):
                    if not is_alias:
                        c_hits[b].add(primary)

            # Aliases (trie + per-token edit<=1), but don't double-add if canonical already present
            for s in range(len(tokens)):
                for _, b, primary, is_alias in trie_scan_alias_fuzzy(tokens, s):
                    if primary not in c_hits[b]:
                        a_hits[b].add(primary)

            # ---- Commit node-local state ----
            with node_locks[i]:
                article_canon[i] = c_hits
                article_alias[i] = a_hits
                base_sent_scores[i] = base
                cs = set()
                for b, names in c_hits.items():
                    for nm in names:
                        cs.add((b, nm))
                canon_sets[i] = cs

            # ---- Incident ENTITY edges via pair_index (>=2 shared canonicals) ----
            cs_list = sorted(list(canon_sets[i]))
            seen_neighbors = set()
            if len(cs_list) >= 2:
                for a_ent, b_ent in combinations(cs_list, 2):
                    key = (a_ent, b_ent) if a_ent <= b_ent else (b_ent, a_ent)
                    with pair_lock:
                        prior = pair_index.get(key)
                    if prior:
                        for j in prior:
                            if j == i or j in seen_neighbors:
                                continue
                            # Lock in index order to avoid deadlocks
                            lo, hi = (i, j) if i < j else (j, i)
                            with node_locks[lo]:
                                with node_locks[hi]:
                                    shared = canon_sets[i].intersection(canon_sets[j])
                                    if len(shared) >= 2:
                                        denom = len(canon_sets[i].union(canon_sets[j])) or 1
                                        w = len(shared) / denom
                                        if w > 0:
                                            entity_adj_dir[i][j] = w
                                            entity_adj_dir[j][i] = w
                            seen_neighbors.add(j)
            # Register this article's pairs for future neighbors
            if len(cs_list) >= 2:
                for a_ent, b_ent in combinations(cs_list, 2):
                    key = (a_ent, b_ent) if a_ent <= b_ent else (b_ent, a_ent)
                    with pair_lock:
                        s = pair_index.setdefault(key, set())
                        s.add(i)

            # ---- Maintain indices for alias/canonical presence ----
            with idx_lock:
                for b, names in c_hits.items():
                    ci = canonical_index[b]
                    for nm in names:
                        ci.setdefault(nm, set()).add(i)
                for b, names in a_hits.items():
                    ai = alias_index[b]
                    for nm in names:
                        ai.setdefault(nm, set()).add(i)

    # Run workers
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # =========================
    # Sentiment propagation (ENTITY edges only)
    # =========================
    scores = base_sent_scores[:]
    for _ in range(20):
        max_delta = 0.0
        new_scores = scores[:]
        for i in range(N):
            neighbors = entity_adj_dir[i]
            if not neighbors:
                continue
            total_w = sum(neighbors.values())
            if total_w <= 0:
                continue
            agg = 0.0
            for j, w in neighbors.items():
                agg += (w / total_w) * scores[j]
            if abs(agg - scores[i]) > max_delta:
                max_delta = abs(agg - scores[i])
            new_scores[i] = agg
        scores = new_scores
        if max_delta < 0.05:
            break

    def score_to_label(prev_label: Optional[str], s: float) -> str:
        if s > 0.25:
            return "positive"
        if s < -0.25:
            return "negative"
        # If exactly on threshold, keep base label to satisfy "last keyword wins" tie cases
        if abs(s - 0.25) < 1e-12 or abs(s + 0.25) < 1e-12:
            return prev_label if prev_label is not None else "neutral"
        return "neutral"

    base_labels = ["positive" if b > 0 else "negative" if b < 0 else "neutral" for b in base_sent_scores]
    final_labels = [score_to_label(base_labels[i], s) for i, s in enumerate(scores)]

    # =========================
    # Output aggregation (deterministic; include alias-derived primaries too)
    # =========================
    out_company, out_symbol, out_index = set(), set(), set()
    for i in range(N):
        # Canonical detections
        for b, names in (article_canon[i] or {}).items():
            if b == "Company":
                out_company |= names
            elif b == "Stock Symbol":
                out_symbol |= names
            elif b == "Market Index":
                out_index |= names
        # Alias detections → include their canonical primaries as well
        for b, names in (article_alias[i] or {}).items():
            if b == "Company":
                out_company |= names
            elif b == "Stock Symbol":
                out_symbol |= names
            elif b == "Market Index":
                out_index |= names

    result = {
        "Company": sorted(out_company),
        "Stock Symbol": sorted(out_symbol),
        "Market Index": sorted(out_index),
        "Sentiment": final_labels,
    }
    return result