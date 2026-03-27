def manage_shard_connections(operations: List[List[Union[str, int, None]]]) -> List[str]:
    MAX_SHARDS = 2000
    MAX_LOAD = 500

    def load_of(s: int) -> int:
        return (s % 100) + 1

    # Current state
    parent = {}  # node -> parent
    rank = {}
    comp_load = {}  # root -> total load
    members = {}  # root -> set of members

    # Version history: list of snapshots. Version 0 is initial.
    # To keep memory reasonable and allow historical queries efficiently for up to 2000 shards,
    # we snapshot the parent mapping of roots and comp_load and members at each version.
    # Since operations <=10000 and shards<=2000 this is acceptable.
    versions = []

    def ensure_node(x: int):
        if x in parent:
            return
        parent[x] = x
        rank[x] = 0
        lw = load_of(x)
        comp_load[x] = lw
        members[x] = set([x])

    def find(x: int) -> int:
        # path compression
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union_op(a: int, b: int) -> bool:
        ensure_node(a)
        ensure_node(b)
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return True
        total = comp_load[ra] + comp_load[rb]
        if total > MAX_LOAD:
            return False
        # union by rank
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1
        # merge members and loads
        comp_load[ra] = total
        members[ra].update(members[rb])
        # remove rb data
        del comp_load[rb]
        del members[rb]
        return True

    def split_op(a: int, b: int) -> bool:
        # split b into its own singleton if a and b connected
        if a not in parent or b not in parent:
            # if either missing, they are singleton; then not connected unless equal
            if a == b:
                return False  # can't split self
            return False
        if a == b:
            return False
        ra = find(a)
        rb = find(b)
        if ra != rb:
            return False
        # isolate b: remove from members[ra], create new root for b
        # We must handle if b is root; but split semantics isolate b only.
        # Remove b from current component and make it its own root.
        # parent pointers: set parent[b]=b and adjust others. For nodes where parent path went through b,
        # path compression will handle later. Ensure consistency: if b was root, need to pick new root for remaining members.
        # We'll create new root for remaining members by choosing another member (if any).
        # Approach: if b is root ra, then we need to make one of other members the new root and reassign parents.
        # Simpler: rebuild component of remaining members: pick one member m != b as root and set parent of each accordingly.
        # Members set available.
        comp_members = members[ra]
        # remove b
        comp_members.remove(b)
        # create new singleton for b
        parent[b] = b
        rank[b] = 0
        comp_load[b] = load_of(b)
        members[b] = set([b])
        # Update remaining component:
        if len(comp_members) == 0:
            # no remaining members, remove old component data
            del comp_load[ra]
            del members[ra]
            # ra might be b; handled
        else:
            # choose new root m0
            m0 = next(iter(comp_members))
            # reassign parent for all members to m0 and set ranks
            for m in comp_members:
                parent[m] = m0
            parent[m0] = m0
            # compute new load
            new_load = sum(load_of(m) for m in comp_members)
            # update structures: remove old root ra entries if different
            if ra != m0:
                if ra in comp_load:
                    del comp_load[ra]
                if ra in members:
                    del members[ra]
            comp_load[m0] = new_load
            members[m0] = set(comp_members)
            # set rank for m0 (reset)
            rank[m0] = 0
        return True

    def snapshot():
        # store deep copies of parent for existing nodes, comp_load, members
        # To save space, we store parent mapping for nodes (integers) existing now.
        versions.append({
            'parent': parent.copy(),
            'comp_load': comp_load.copy(),
            'members': {r: set(s) for r, s in members.items()},
        })

    # initialize version 0
    snapshot()  # initial empty state

    results: List[str] = []
    current_version = 0

    for op in operations:
        typ = op[0]
        a = op[1]
        b = op[2]
        v = op[3]

        if typ == "union":
            ensure_node(a)
            ensure_node(b)
            res = union_op(a, b)
            snapshot()
            current_version += 1
            results.append("True" if res else "False")
        elif typ == "split":
            ensure_node(a)
            ensure_node(b)
            res = split_op(a, b)
            snapshot()
            current_version += 1
            results.append("True" if res else "False")
        elif typ == "find":
            # ensure nodes exist per spec
            if a not in parent or b not in parent:
                # if absent, they are singletons possibly not equal
                if a == b:
                    results.append("True")
                else:
                    results.append("False")
            else:
                res = (find(a) == find(b))
                results.append("True" if res else "False")
        elif typ == "find_versioned":
            ver = v
            if not isinstance(ver, int) or ver < 0 or ver > current_version:
                results.append("False")
            else:
                snap = versions[ver]
                par = snap['parent']
                mem = snap['members']
                # if nodes absent in that version, they are singletons
                def find_in_snap(x: int) -> int:
                    if x not in par:
                        return x
                    # iterative find without compression
                    while par[x] != x:
                        x = par[x]
                    return x
                if a == b:
                    results.append("True")
                else:
                    ra = find_in_snap(a)
                    rb = find_in_snap(b)
                    results.append("True" if ra == rb else "False")
        else:
            # unknown op
            results.append("False")

    return results