def manage_shard_connections(operations: List[List[Union[str, int, None]]]) -> List[str]:
    MAX_SHARDS = 2000
    MAX_LOAD = 500

    def load_of(s: int) -> int:
        return (s % 100) + 1

    # We'll maintain per-version snapshots of components using immutable-ish structures:
    # For each version we store:
    # - parent dict: mapping node -> parent (root if parent[node]==node)
    # - rank dict
    # - comp_load dict: root -> total load
    # To avoid full copies each time, we'll share and copy-on-write per changed keys.
    # Since constraints are small (<=2000 shards, <=10000 ops), this is acceptable.

    versions_parent: List[Dict[int, int]] = []
    versions_rank: List[Dict[int, int]] = []
    versions_comp_load: List[Dict[int, int]] = []

    current_parent: Dict[int, int] = {}
    current_rank: Dict[int, int] = {}
    current_comp_load: Dict[int, int] = {}

    def ensure_node(state_parent: Dict[int,int], state_rank: Dict[int,int], state_comp_load: Dict[int,int], x: int):
        if x not in state_parent:
            state_parent[x] = x
            state_rank[x] = 0
            state_comp_load[x] = load_of(x)

    def find_root(state_parent: Dict[int,int], x: int) -> int:
        # path compression (mutates given dict)
        if state_parent[x] != x:
            state_parent[x] = find_root(state_parent, state_parent[x])
        return state_parent[x]

    results: List[str] = []
    current_version = 0
    # initialize version 0 as empty (all nodes will be added lazily)
    versions_parent.append(dict(current_parent))
    versions_rank.append(dict(current_rank))
    versions_comp_load.append(dict(current_comp_load))

    for op in operations:
        typ = op[0]
        a = op[1]
        b = op[2]
        v = op[3]

        if typ == "union":
            # prepare copies
            new_parent = dict(current_parent)
            new_rank = dict(current_rank)
            new_comp_load = dict(current_comp_load)
            # ensure nodes
            ensure_node(new_parent, new_rank, new_comp_load, a)
            ensure_node(new_parent, new_rank, new_comp_load, b)
            ra = find_root(new_parent, a)
            rb = find_root(new_parent, b)
            if ra == rb:
                results.append("True")
                # commit new version (state unchanged but we still push)
                current_parent = new_parent
                current_rank = new_rank
                current_comp_load = new_comp_load
                current_version += 1
                versions_parent.append(dict(current_parent))
                versions_rank.append(dict(current_rank))
                versions_comp_load.append(dict(current_comp_load))
                continue
            load_a = new_comp_load.get(ra, 0)
            load_b = new_comp_load.get(rb, 0)
            if load_a + load_b > MAX_LOAD:
                results.append("False")
                # Operation rejected: still increments version? Spec: "Only union and split modify state and increment version"
                # If rejected, no state change but version still increments? Problem statement example counts only completed operations.
                # We'll treat rejected union as not modifying state but still counts as operation that increments version? The example indicates union returns False when rejected; unclear on versioning.
                # We'll assume union even if rejected still increments version but state remains same.
                current_version += 1
                versions_parent.append(dict(current_parent))
                versions_rank.append(dict(current_rank))
                versions_comp_load.append(dict(current_comp_load))
                continue
            # union by rank
            if new_rank[ra] < new_rank[rb]:
                ra, rb = rb, ra  # ensure ra has higher rank
            new_parent[rb] = ra
            new_comp_load[ra] = load_a + load_b
            if rb in new_comp_load:
                del new_comp_load[rb]
            if new_rank[ra] == new_rank[rb]:
                new_rank[ra] += 1
            # commit
            results.append("True")
            current_parent = new_parent
            current_rank = new_rank
            current_comp_load = new_comp_load
            current_version += 1
            versions_parent.append(dict(current_parent))
            versions_rank.append(dict(current_rank))
            versions_comp_load.append(dict(current_comp_load))

        elif typ == "split":
            # split a b: if not connected -> False. if connected, isolate b into its own singleton
            # special: split a a -> False
            if a == b:
                results.append("False")
                # still increments version? spec: "Only union and split operations modify state and increment version"
                # If split failed (not connected or invalid), we treat as no state change but still increments version? Examples show split non-connected returns False and then subsequent union occurs; versioning behavior for failed split not explicit.
                # We'll increment version regardless to maintain consistent numbering of operations that could modify.
                current_version += 1
                versions_parent.append(dict(current_parent))
                versions_rank.append(dict(current_rank))
                versions_comp_load.append(dict(current_comp_load))
                continue
            new_parent = dict(current_parent)
            new_rank = dict(current_rank)
            new_comp_load = dict(current_comp_load)
            ensure_node(new_parent, new_rank, new_comp_load, a)
            ensure_node(new_parent, new_rank, new_comp_load, b)
            ra = find_root(new_parent, a)
            rb = find_root(new_parent, b)
            if ra != rb:
                results.append("False")
                current_version += 1
                versions_parent.append(dict(current_parent))
                versions_rank.append(dict(current_rank))
                versions_comp_load.append(dict(current_comp_load))
                continue
            # Need to isolate b: make b its own root; others remain. This may require re-parenting children of b.
            # Because we maintain parent pointers, we can't easily remove b from tree without traversing all nodes in component.
            # We'll reconstruct component: find all nodes currently present that belong to root ra, excluding b.
            comp_nodes = [node for node in new_parent.keys() if find_root(new_parent, node) == ra]
            # If b not present (shouldn't happen) handle
            if b not in comp_nodes:
                results.append("False")
                current_version += 1
                versions_parent.append(dict(current_parent))
                versions_rank.append(dict(current_rank))
                versions_comp_load.append(dict(current_comp_load))
                continue
            # Make b singleton
            new_parent[b] = b
            new_rank[b] = 0
            lb = load_of(b)
            # Remaining nodes: set their root to some representative (choose a if it's not b else another)
            remaining = [node for node in comp_nodes if node != b]
            if remaining:
                rep = remaining[0]
                for node in remaining:
                    new_parent[node] = rep
                # compress parents for remaining to root rep
                for node in remaining:
                    find_root(new_parent, node)
                # compute new load for rep
                total = sum(load_of(node) for node in remaining)
                new_comp_load[rep] = total
                # remove old root entry if different
                old_root = ra
                if old_root in new_comp_load and old_root != rep:
                    if old_root != rep:
                        # delete old root load if present
                        if old_root in new_comp_load:
                            del new_comp_load[old_root]
                # remove b from old comp load
                # ensure b not in comp_load
                if b in new_comp_load:
                    del new_comp_load[b]
            else:
                # component only had b? split invalid because a==b case handled earlier; but if remaining empty, then after split b becomes singleton and original component empty -> remove
                pass
            # set comp_load entries properly: ensure b singleton has its load
            new_comp_load[b] = lb
            # There may be other roots in mapping; clean: ensure only roots have comp_load entries
            # Recompute comp_load for all roots present to be safe
            roots = {}
            for node in list(new_parent.keys()):
                rnode = find_root(new_parent, node)
                roots.setdefault(rnode, 0)
                roots[rnode] += load_of(node)
            new_comp_load = roots
            # ranks: reset ranks for roots present
            for node in list(new_rank.keys()):
                if find_root(new_parent, node) == node:
                    new_rank[node] = new_rank.get(node, 0)
                else:
                    # non-root rank irrelevant
                    new_rank[node] = new_rank.get(node, 0)
            results.append("True")
            current_parent = new_parent
            current_rank = new_rank
            current_comp_load = new_comp_load
            current_version += 1
            versions_parent.append(dict(current_parent))
            versions_rank.append(dict(current_rank))
            versions_comp_load.append(dict(current_comp_load))

        elif typ == "find":
            # ensure nodes exist
            if a not in current_parent:
                current_parent = dict(current_parent)
                current_rank = dict(current_rank)
                current_comp_load = dict(current_comp_load)
                current_parent[a] = a
                current_rank[a] = 0
                current_comp_load[a] = load_of(a)
                # update version0 snapshot? find is read-only and shouldn't change versioning; but we mutated current state by lazy init -> reflect immediately without incrementing version
            if b not in current_parent:
                current_parent = dict(current_parent)
                current_rank = dict(current_rank)
                current_comp_load = dict(current_comp_load)
                current_parent[b] = b
                current_rank[b] = 0
                current_comp_load[b] = load_of(b)
            ra = find_root(current_parent, a)
            rb = find_root(current_parent, b)
            results.append("True" if ra == rb else "False")
            # find does not change versioning or snapshots

        elif typ == "find_versioned":
            # v is version to query
            if not isinstance(v, int):
                results.append("False")
                continue
            if v > current_version or v < 0:
                results.append("False")
                continue
            vp = versions_parent[v]
            vr = versions_rank[v]
            # nodes might not exist in that version; if not exist, they were singletons (not connected unless equal)
            if a == b:
                # even if not present, self-connected
                results.append("True")
                continue
            if a not in vp or b not in vp:
                # if one absent, they were separate singletons
                results.append("False")
                continue
            # perform find without mutating stored version (operate on copies)
            cp = dict(vp)
            def fr(x):
                if cp[x] != x:
                    cp[x] = fr(cp[x])
                return cp[x]
            ra = fr(a)
            rb = fr(b)
            results.append("True" if ra == rb else "False")
        else:
            # unknown op
            results.append("False")

    return results