from typing import Any, Dict, List, Tuple, Optional
import json


class UnionFind:
    """Disjoint set union with path compression, union by size, and rollback capability."""

    def __init__(self, elements: Optional[List[str]] = None) -> None:
        """Initialize union-find structure with temporal tracking."""
        self.parent: Dict[str, str] = {}
        self.size: Dict[str, int] = {}
        # Track history for rollback: (timestamp, operation_type, data)
        self.history: List[Tuple[int, str, Any]] = []
        self.current_timestamp: int = 0
        if elements:
            for e in elements:
                self.add(e)

    def add(self, x: str) -> None:
        """Add a new element as its own set."""
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1

    def find(self, x: str) -> str:
        """Find the representative of the set containing x with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> str:
        """Union the sets of a and b, record operation, and return new root."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        # Record operation for potential rollback
        self.history.append((self.current_timestamp, 'union', (ra, rb, self.size[ra], self.size[rb])))
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return ra

    def set_timestamp(self, t: int) -> None:
        """Set current timestamp for tracking temporal operations."""
        self.current_timestamp = t

    def groups(self) -> Dict[str, List[str]]:
        """Return mapping root->members."""
        result: Dict[str, List[str]] = {}
        for x in self.parent:
            r = self.find(x)
            result.setdefault(r, []).append(x)
        for r in result:
            result[r].sort()
        return result


class InterestTrie:
    """Simple trie for interest terms."""

    def __init__(self) -> None:
        """Initialize trie root."""
        self.root: Dict[str, Any] = {"#": False, "children": {}}

    def insert(self, word: str) -> None:
        """Insert a word into the trie."""
        node = self.root
        for ch in word:
            if ch not in node["children"]:
                node["children"][ch] = {"#": False, "children": {}}
            node = node["children"][ch]
        node["#"] = True

    def contains(self, word: str) -> bool:
        """Check if a word exists in the trie."""
        node = self.root
        for ch in word:
            nxt = node["children"].get(ch)
            if not nxt:
                return False
            node = nxt
        return bool(node.get("#"))


def detect_and_visualize_communities(user_interactions: List[List], interests: Dict[str, List[str]]) -> Dict[str, Any]:
    """Compute dynamic communities and visualization data with batch processing."""
    # Phase 1: Initialize users and structures 
    users: List[str] = []
    seen_users_set = set()
    for a, b, _ in user_interactions:
        if a not in seen_users_set:
            users.append(a)
            seen_users_set.add(a)
        if b not in seen_users_set:
            users.append(b)
            seen_users_set.add(b)
    for u in interests.keys():
        if u not in seen_users_set:
            users.append(u)
            seen_users_set.add(u)

    # Initialize UnionFind and tracking structures
    uf = UnionFind(users)
    active_users: set = set()
    # Track events per user for O(1) community assignment later
    user_events: Dict[str, List[Dict[str, Any]]] = {u: [] for u in users}

    # Phase 2: Build interest trie upfront for efficient lookups
    interest_trie = InterestTrie()
    for lst in interests.values():
        for tag in lst:
            interest_trie.insert(tag)

    # Phase 3: Process interactions in batches (sorted by timestamp for temporal ordering)
    # Group interactions into batches by timestamp to simulate streaming
    batch_size = max(1, len(user_interactions) // 10)  # Process in ~10 batches
    edges_sorted = sorted(user_interactions, key=lambda x: (x[2], x[0], x[1]))

    all_edges_for_viz: List[Dict[str, Any]] = []

    # Process batches
    for batch_start in range(0, len(edges_sorted), batch_size):
        batch_end = min(batch_start + batch_size, len(edges_sorted))
        batch = edges_sorted[batch_start:batch_end]

        # Process each interaction in the batch
        for a, b, t in batch:
            uf.set_timestamp(t)

            # Track user activation
            if a not in active_users:
                event = {a: "joined_cluster", "timestamp": t}
                user_events[a].append(event)
                active_users.add(a)
            if b not in active_users:
                event = {b: "joined_cluster", "timestamp": t}
                user_events[b].append(event)
                active_users.add(b)

            # Check if union needed or already connected
            ra = uf.find(a)
            rb = uf.find(b)
            if ra == rb:
                event = {a: f"connected_with_{b}", "timestamp": t}
                user_events[a].append(event)
            else:
                # Union operation - track for both users
                _ = uf.union(ra, rb)

            all_edges_for_viz.append({"source": a, "target": b, "timestamp": t})

    # Phase 4: Build communities with efficient event aggregation
    groups = uf.groups()
    communities: List[Dict[str, Any]] = []

    for root, members in groups.items():
        # Aggregate interests efficiently
        agg: List[str] = []
        acc_set = set()
        for m in members:
            for tag in interests.get(m, []):
                if interest_trie.contains(tag) and tag not in acc_set:
                    acc_set.add(tag)
                    agg.append(tag)
        agg.sort()

        # Efficiently collect events: O(sum of member events) instead of O(total events)
        ev = []
        for m in members:
            ev.extend(user_events[m])
        ev.sort(key=lambda x: (x["timestamp"], next(k for k in x.keys() if k != "timestamp")))

        communities.append({"members": members, "shared_interests": agg, "transition_events": ev})

    communities.sort(key=lambda c: (len(c["members"]), c["members"][0] if c["members"] else ""))

    # Phase 5: Build visualization data
    nodes = [{"id": u, "interests": sorted(interests.get(u, []))} for u in sorted(seen_users_set)]
    cluster_layers = [{"root": r, "members": m} for r, m in sorted(groups.items())]
    visualization_data = {"nodes": nodes, "edges": all_edges_for_viz, "clusters": cluster_layers}

    return {"communities": communities, "visualization_data": visualization_data}


if __name__ == "__main__":
    user_interactions = [
        ["user1", "user2", 1620000000],
        ["user2", "user3", 1620000100],
        ["user1", "user4", 1620000200],
        ["user4", "user5", 1620000300],
        ["user3", "user5", 1620000400],
        ["user1", "user2", 1620000500],
        ["user6", "user7", 1620000600],
    ]
    interests = {
        "user1": ["sports", "music"],
        "user2": ["music", "travel"],
        "user3": ["sports", "travel"],
        "user4": ["cooking", "tech"],
        "user5": ["cooking", "travel", "sports"],
        "user6": ["gaming", "tech"],
        "user7": ["music", "gaming"],
    }
    result = detect_and_visualize_communities(user_interactions, interests)
    print(json.dumps(result))