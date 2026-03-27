def __init__(self):
        self.children = {}  # char -> TrieNode
        self.words = set()  # set of full words ending in subtree

    def insert(self, word: str):
        node = self
        node.words.add(word)
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
            node.words.add(word)

    def remove(self, word: str):
        # Remove word from words sets along its path if present
        node = self
        if word in node.words:
            node.words.discard(word)
        for ch in word:
            node = node.children.get(ch)
            if not node:
                return
            if word in node.words:
                node.words.discard(word)

    def search_prefix(self, prefix: str):
        node = self
        for ch in prefix:
            node = node.children.get(ch)
            if not node:
                return set()
        return set(node.words)

class Segment:
    __slots__ = ('name', 'versions', 'active_words')
    def __init__(self, name: str):
        self.name = name
        # versions: list of tuples (user_id, op_type, content)
        # We'll store insertions as set of words per version; deletions as markers
        self.versions = []  # list of dicts: {'user':..., 'type': 'insert'/'delete', 'word':...}
        self.active_words = set()  # current active words in segment after merging

    def record(self, user: str, op_type: str, word: str):
        self.versions.append({'user': user, 'type': op_type, 'word': word})

    def deterministic_merge(self):
        # Apply versions in deterministic order: sort by (index) but deterministic across users.
        # We will simulate CRDT-like merging: collect inserts and deletes and preserve all inserts unless deleted.
        # To be deterministic even with concurrent edits, we'll apply versions in recorded order but
        # when multiple inserts of same word exist, all are same word -> keep one.
        active = set()
        deletes = set()
        for v in self.versions:
            if v['type'] == 'insert':
                if v['word'] not in deletes:
                    active.add(v['word'])
            elif v['type'] == 'delete':
                # deletion removes word if present or marks so future inserts don't revive it unless later insert occurs
                if v['word'] in active:
                    active.discard(v['word'])
                deletes.add(v['word'])
        self.active_words = active

def parse_data_field(data: str):
    # expected "segment_x:content"
    if ':' not in data:
        return None, None
    seg, content = data.split(':', 1)
    seg = seg.strip()
    content = content.strip()
    return seg, content

def collaborative_editor(operations: List[Dict[str, str]]) -> Dict[str, List[str]]:
    segments: Dict[str, Segment] = {}
    trie = TrieNode()
    last_search_result: Optional[List[str]] = None

    for op_dict in operations:
        user = op_dict.get('user_id', '')
        operation = op_dict.get('operation', '')
        data = op_dict.get('data', '')
        seg_name, content = parse_data_field(data)
        if operation == 'insert':
            if not seg_name or content == '':
                continue
            # treat content as a single word token
            seg = segments.setdefault(seg_name, Segment(seg_name))
            seg.record(user, 'insert', content)
            # immediate merge for real-time behavior: merge segment deterministic and update trie
            seg.deterministic_merge()
            # rebuild trie entries for this segment: remove all previous words from trie for this segment, then add active
            # To track per-segment words in trie, we will rebuild whole trie from all segments for simplicity (acceptable <=500 ops)
            # Rebuild:
            trie = TrieNode()
            for s in segments.values():
                # ensure latest merge
                s.deterministic_merge()
                for w in s.active_words:
                    trie.insert(w)
        elif operation == 'delete':
            if not seg_name or content == '':
                continue
            seg = segments.setdefault(seg_name, Segment(seg_name))
            seg.record(user, 'delete', content)
            seg.deterministic_merge()
            # rebuild trie
            trie = TrieNode()
            for s in segments.values():
                s.deterministic_merge()
                for w in s.active_words:
                    trie.insert(w)
        elif operation == 'merge_offline':
            # data may represent "segment_x:word" or "segment_x:" meaning merge entire offline buffer
            if not seg_name:
                continue
            seg = segments.setdefault(seg_name, Segment(seg_name))
            # For offline merge, we simulate that this user's offline edits come as a single insert if content present
            if content != '':
                # tag as insert by this user (could be multiple)
                seg.record(user, 'insert', content)
            # perform deterministic merge combining all versions
            seg.deterministic_merge()
            # rebuild trie
            trie = TrieNode()
            for s in segments.values():
                s.deterministic_merge()
                for w in s.active_words:
                    trie.insert(w)
        elif operation == 'search':
            if not seg_name:
                # global prefix search
                prefix = content
                matches = sorted(trie.search_prefix(prefix))
                last_search_result = matches
            else:
                prefix = content
                # Search limited to segment: ensure merged state
                seg = segments.get(seg_name)
                if not seg:
                    last_search_result = []
                else:
                    seg.deterministic_merge()
                    # filter active words by prefix
                    matches = [w for w in seg.active_words if w.startswith(prefix)]
                    last_search_result = sorted(matches)
        else:
            # unknown operation: ignore
            continue

    if last_search_result is None:
        return {}
    return {"matches": last_search_result}