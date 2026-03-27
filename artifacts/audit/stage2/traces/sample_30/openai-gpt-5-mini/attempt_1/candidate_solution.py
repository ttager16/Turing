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
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> str:
        self.add(a)
        self.add(b)
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return ra
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
    # Edge case: empty interactions and empty interests
    if not user_interactions and not interests:
        return {"communities": [], "visualization_data": {"nodes": [], "edges": [], "clusters": []}}

    uf = UnionFind()
    trie = InterestTrie()

    # Build interest trie and nodes list
    nodes = []
    for user, tags in interests.items():
        for t in tags:
            trie.insert(t)
        nodes.append({'id': user, 'interests': list(dict.fromkeys(tags))})

    # Track first appearance timestamps and events
    first_seen = {}
    events_per_user = {}
    edges_output = []

    # Collect all users mentioned even if no interests
    users_set = set(interests.keys())

    # Process interactions sequentially (assumed ordered by timestamp in input; if not, sort)
    interactions = list(user_interactions)
    # If timestamps present, sort by timestamp then by source,target to stabilize
    try:
        interactions.sort(key=lambda x: (x[2], x[0], x[1]))
    except Exception:
        pass

    for inter in interactions:
        if len(inter) < 3:
            continue
        a, b, ts = inter[0], inter[1], inter[2]
        users_set.add(a)
        users_set.add(b)
        # Add nodes for users without interests
        if a not in interests:
            # ensure node appears with empty interests later
            pass
        if b not in interests:
            pass
        # record first seen
        if a not in first_seen:
            first_seen[a] = ts
            events_per_user.setdefault(a, []).append({'user': a, 'type': 'joined_cluster', 'timestamp': ts})
        if b not in first_seen:
            first_seen[b] = ts
            events_per_user.setdefault(b, []).append({'user': b, 'type': 'joined_cluster', 'timestamp': ts})
        # record edge
        edges_output.append({'source': a, 'target': b, 'timestamp': ts})
        # check if already connected
        already_connected = False
        uf.add(a)
        uf.add(b)
        ra = uf.find(a)
        rb = uf.find(b)
        if ra == rb:
            already_connected = True
        # perform union
        uf.union(a, b)
        # create connected event if repeated within same cluster (after merging they may be)
        if already_connected:
            # create connected_with_other event for both users
            if a == b:
                events_per_user.setdefault(a, []).append({'user': a, 'type': 'connected_with_self', 'timestamp': ts})
            else:
                events_per_user.setdefault(a, []).append({'user': a, 'type': f'connected_with_{b}', 'timestamp': ts})
                events_per_user.setdefault(b, []).append({'user': b, 'type': f'connected_with_{a}', 'timestamp': ts})

    # Add nodes entries for users without interests
    for u in users_set:
        if u not in interests:
            nodes.append({'id': u, 'interests': []})
    # ensure nodes unique and stable order: sort by id
    nodes_dict = {n['id']: n for n in nodes}
    nodes = [nodes_dict[k] for k in sorted(nodes_dict.keys())]

    # Build groups
    groups = uf.groups()
    # Include users who had interests but no interactions: ensure they are their own groups
    for u in interests.keys():
        if u not in uf.parent:
            uf.add(u)
            groups = uf.groups()

    groups = uf.groups()

    # Build communities list
    communities = []
    # For deterministic order, sort groups by smallest user id
    for root in sorted(groups.keys()):
        members = sorted(groups[root])
        # aggregate interests
        shared_set = set()
        for m in members:
            for tag in interests.get(m, []):
                shared_set.add(tag)
        shared_interests = sorted(shared_set)
        # collect transition_events: gather events for members, flatten and filter to those in this community
        evts = []
        for m in members:
            for e in events_per_user.get(m, []):
                # format according to rules: joined_cluster or connected_with_x/self
                if e['type'] == 'joined_cluster':
                    evts.append({m: 'joined_cluster', 'timestamp': e['timestamp']})
                elif e['type'] == 'connected_with_self':
                    evts.append({m: 'connected_with_self', 'timestamp': e['timestamp']})
                elif e['type'].startswith('connected_with_'):
                    evts.append({m: e['type'], 'timestamp': e['timestamp']})
        # sort events by timestamp then by user id (keys)
        def evt_sort_key(x):
            ts = x.get('timestamp', 0)
            # get user id deterministically
            user = next(iter(k for k in x.keys() if k != 'timestamp'))
            return (ts, user)
        evts.sort(key=evt_sort_key)
        communities.append({
            'members': members,
            'shared_interests': shared_interests,
            'transition_events': evts
        })

    # Handle users with interests but no interactions: must be individual communities with empty transition_events
    interacted_users = set(first_seen.keys())
    for u in sorted(set(interests.keys()) - interacted_users):
        communities.append({
            'members': [u],
            'shared_interests': sorted(list(dict.fromkeys(interests.get(u, [])))),
            'transition_events': []
        })
        if u not in nodes_dict:
            nodes.append({'id': u, 'interests': interests.get(u, [])})

    # Edge case: empty interactions but interests present handled above: communities created for each user, no transition_events

    # Build visualization clusters: roots and their members
    vis_clusters = []
    # Recompute groups to ensure consistency
    groups = uf.groups()
    for root in sorted(groups.keys()):
        vis_clusters.append({'root': root, 'members': sorted(groups[root])})

    visualization_data = {
        'nodes': nodes,
        'edges': edges_output,
        'clusters': vis_clusters
    }

    # If interests empty dict, set shared_interests to [] for communities
    if not interests:
        for c in communities:
            c['shared_interests'] = []

    return {'communities': communities, 'visualization_data': visualization_data}

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
    sys.stdout.write(json.dumps(result, indent=4))