def __init__(self, elements: Optional[List[str]] = None) -> None:
        self.parent = {}
        self.size = {}
        if elements:
            for e in elements:
                self.add(e)

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.add(x)
        while self.parent[x] != x:
            # path compression one step
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> str:
        self.add(a); self.add(b)
        ra = self.find(a); rb = self.find(b)
        if ra == rb:
            return ra
        # union by size
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size.get(rb, 0)
        return ra

    def groups(self) -> Dict[str, List[str]]:
        roots = {}
        for x in list(self.parent.keys()):
            r = self.find(x)
            roots.setdefault(r, []).append(x)
        return roots

class InterestTrieNode:
    def __init__(self):
        self.children = {}
        self.end = False

class InterestTrie:
    def __init__(self) -> None:
        self.root = InterestTrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = InterestTrieNode()
            node = node.children[ch]
        node.end = True

    def contains(self, word: str) -> bool:
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.end

def detect_and_visualize_communities(user_interactions: List[List], interests: Dict[str, List[str]]) -> Dict[str, Any]:
    # Edge cases: empty interactions
    if not user_interactions:
        if not interests:
            return {"communities": [], "visualization_data": {"nodes": [], "edges": [], "clusters": []}}
        # create individual communities for each interest user
        nodes = []
        communities = []
        clusters = []
        for u, ints in interests.items():
            nodes.append({"id": u, "interests": list(dict.fromkeys(ints))})
            communities.append({"members": [u], "shared_interests": list(dict.fromkeys(ints)), "transition_events": []})
            clusters.append({"root": u, "members": [u]})
        return {"communities": communities, "visualization_data": {"nodes": nodes, "edges": [], "clusters": clusters}}
    # Prepare structures
    uf = UnionFind()
    trie = InterestTrie()
    for uid, ints in interests.items():
        for tag in ints:
            trie.insert(tag)
    # Track first appearance timestamps
    first_seen = {}
    # Track events list per cluster root (we'll aggregate later)
    events = []  # list of tuples (timestamp, user_id, event_str)
    edges_out = []
    users_set = set()
    # Process interactions in chronological order
    # Ensure sorted by timestamp
    interactions = [list(it) for it in user_interactions]
    interactions.sort(key=lambda x: (int(x[2]), x[0], x[1]))
    for a, b, ts in interactions:
        a = str(a); b = str(b)
        ts = int(ts)
        users_set.add(a); users_set.add(b)
        # record first appearance
        if a not in first_seen:
            first_seen[a] = ts
            events.append((ts, a, "joined_cluster"))
        if b not in first_seen:
            first_seen[b] = ts
            events.append((ts, b, "joined_cluster"))
        # check if already in same cluster
        same_before = False
        if a in uf.parent and b in uf.parent:
            if uf.find(a) == uf.find(b):
                same_before = True
        # record edge
        edges_out.append({"source": a, "target": b, "timestamp": ts})
        # If same cluster and repeated interaction, special event
        if same_before:
            if a == b:
                events.append((ts, a, "connected_with_self"))
            else:
                events.append((ts, a, f"connected_with_{b}"))
        # union them (this may merge clusters)
        uf.union(a, b)
    # Include users from interests only (no interactions)
    for u in interests.keys():
        users_set.add(u)
        if u not in uf.parent:
            uf.add(u)
    # Build groups
    groups = uf.groups()  # root -> members
    # Aggregate shared interests per group
    communities = []
    # Prepare mapping from user to root at final state
    user_root = {}
    for r, members in groups.items():
        for m in members:
            user_root[m] = r
    # Aggregate events per final group: apply rules and sort
    events_sorted = sorted(events, key=lambda x: (x[0], x[1]))
    events_per_group = defaultdict(list)
    for ts, user, ev in events_sorted:
        root = user_root.get(user, user)
        events_per_group[root].append({user: ev, "timestamp": ts})
    # For users who had interactions first_seen but no repeated events, they still have joined events present
    # Now build communities list
    for root, members in groups.items():
        # members sorted for determinism
        members_sorted = sorted(members)
        # Aggregate interests
        shared = []
        seen_int = set()
        for m in members_sorted:
            for tag in interests.get(m, []):
                if tag not in seen_int:
                    seen_int.add(tag)
                    shared.append(tag)
        # If interests dict empty, shared should be []
        if not interests:
            shared = []
        comm_events = events_per_group.get(root, [])
        communities.append({
            "members": members_sorted,
            "shared_interests": shared,
            "transition_events": comm_events
        })
    # Handle users with interests but no interactions who didn't get transition_events (should have empty)
    # Visualization data
    nodes = []
    for u in sorted(users_set):
        nodes.append({"id": u, "interests": list(dict.fromkeys(interests.get(u, [])))})
    clusters_vis = []
    for root, members in groups.items():
        clusters_vis.append({"root": root, "members": sorted(members)})
    visualization_data = {"nodes": nodes, "edges": edges_out, "clusters": clusters_vis}
    return {"communities": communities, "visualization_data": visualization_data}

if __name__ == "__main__":
    user_interactions = [
        ['user1', 'user2', 1620000000],
        ['user2', 'user3', 1620000100],
        ['user1', 'user4', 1620000200],
        ['user4', 'user5', 1620000300],
        ['user3', 'user5', 1620000400],
        ['user1', 'user2', 1620000500],
        ['user6', 'user7', 1620000600]
    ]
    interests = {
        'user1': ['sports', 'music'],
        'user2': ['music', 'travel'],
        'user3': ['sports', 'travel'],
        'user4': ['cooking', 'tech'],
        'user5': ['cooking', 'travel', 'sports'],
        'user6': ['gaming', 'tech'],
        'user7': ['music', 'gaming']
    }
    result = detect_and_visualize_communities(user_interactions, interests)
    print(json.dumps(result, indent=4))