def allocate_minimum_companies(demand: List[int], capacities: List[int]) -> int:
    # Greedy practical solution:
    # Each company covers one root-to-descendant path segment (contiguous along parent->child).
    # We model covering by repeatedly assigning the largest remaining capacity to cover a maximal uncovered path demand.
    # This is heuristic but reasonable: compute all root-to-leaf paths as sequences of node indices, compute remaining demand per node,
    # then greedily place companies on the path segment that yields maximum covered demand per company capacity.
    # For scalability, we build all root-to-leaf paths (O(n)) and operate with prefix sums.
    n = len(demand)
    if n == 0:
        return 0
    capacities = sorted(capacities, reverse=True)
    # Build parent array for implicit binary tree
    parent = [-1] * n
    for i in range(1, n):
        parent[i] = (i - 1) // 2
    # Build children lists
    children = [[] for _ in range(n)]
    for i in range(1, n):
        p = parent[i]
        children[p].append(i)
    # Gather root-to-leaf paths
    leaves = [i for i in range(n) if not children[i]]
    paths = []
    for leaf in leaves:
        path = []
        u = leaf
        while u != -1:
            path.append(u)
            u = parent[u]
        path.reverse()  # root to leaf
        paths.append(path)
    # For each path, maintain current remaining demands array and prefix sums
    rem = demand[:]  # remaining demand per node
    # Precompute for each path the list of indices
    # We'll for each company capacity pick best path segment (contiguous) maximizing sum of rem capped by capacity.
    # To do this efficiently, for each path rebuild prefix sums when rem changed; since each assignment reduces rem, number of assignments limited by sum(demand)/min_capacity
    total_demand = sum(demand)
    if total_demand == 0:
        return 0
    # If capacities insufficient individually to cover some node demand, nodes can be split across multiple companies; greedy still works.
    companies_used = 0
    # Use multiset of capacities descending; for each capacity, find best segment
    for cap in capacities:
        if sum(rem) == 0:
            break
        # find best path and segment
        best_gain = 0
        best_path_idx = -1
        best_l = best_r = -1
        for pi, path in enumerate(paths):
            if not path:
                continue
            vals = [rem[idx] for idx in path]
            # sliding window max sum with cap: we want max sum of contiguous vals up to cap
            # Two pointers
            cur = 0
            l = 0
            for r in range(len(vals)):
                cur += vals[r]
                while cur > cap and l <= r:
                    cur -= vals[l]
                    l += 1
                if cur > best_gain:
                    best_gain = cur
                    best_path_idx = pi
                    best_l, best_r = l, r
            # Also consider taking partial of a single node if node>cap: can cover cap at some node
            for i_node, v in enumerate(vals):
                if v > cap and cap > best_gain:
                    best_gain = cap
                    best_path_idx = pi
                    best_l = best_r = i_node
        if best_gain == 0:
            # capacity cannot cover any remaining demand (all rem are zero or cap too small to cover any positive rem)
            # If any rem>0 but less than cap? already caught. If cap < smallest positive rem but nodes can be split: we can reduce some node by cap.
            # Do single-node split: find node with rem>0, subtract cap
            found = False
            for i in range(n):
                if rem[i] > 0:
                    rem[i] = max(0, rem[i] - cap)
                    companies_used += 1
                    found = True
                    break
            if not found:
                break
        else:
            # apply coverage subtract best_gain from nodes in that segment, but distribute proportionally left-to-right up to cap
            path = paths[best_path_idx]
            cap_left = cap
            for idx in range(best_l, best_r + 1):
                node = path[idx]
                take = min(rem[node], cap_left)
                rem[node] -= take
                cap_left -= take
                if cap_left <= 0:
                    break
            companies_used += 1
    # If still remaining demand after using all companies, we need more companies (each with max capacity equal to largest capacity)
    remaining = sum(rem)
    if remaining > 0:
        if not capacities:
            return -1  # impossible
        maxcap = max(capacities)
        more = (remaining + maxcap - 1) // maxcap
        companies_used += more
    return companies_used