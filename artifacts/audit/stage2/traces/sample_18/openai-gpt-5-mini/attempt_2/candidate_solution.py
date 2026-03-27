def allocate_minimum_companies(demand: List[int], capacities: List[int]) -> int:
    # Greedy feasible approximation: cover node demands by companies each assigned to a single-node path first,
    # then try to merge along parent-child chains where capacity allows to reduce count.
    n = len(demand)
    if n == 0:
        return 0
    # Sort capacities descending for greedy usage
    caps = sorted(capacities, reverse=True)
    if not caps:
        return float('inf')
    # Initially, each node needs demand[i] units. We'll assign companies to cover connected paths,
    # but because exact optimal is NP-hard-like, use heuristic: pack from leaves upward merging segments when possible.
    # Represent for each node the multiset of segment sums starting at node downward that are not yet fully covered.
    # We'll perform bottom-up: at each node, merge children's segments and try to extend with node demand.
    from collections import deque
    # Build tree indices
    children = [[] for _ in range(n)]
    for i in range(n):
        l = 2*i+1
        r = 2*i+2
        if l < n: children[i].append(l)
        if r < n: children[i].append(r)
    # For performance, represent segments as list of sums (sorted)
    segments = [None]*n
    for i in range(n-1, -1, -1):
        segs = []
        # take all child segments
        for c in children[i]:
            if segments[c]:
                segs.extend(segments[c])
        # add this node as a new segment
        segs.append(demand[i])
        # try to merge pairs of smallest segments if there exists a capacity large enough for their sum
        segs.sort()
        merged = []
        # Greedy pairwise merge from smallest upward where possible using largest capacity
        # We'll attempt to merge as long as there exists any capacity >= sum, choose largest capacity available.
        # For feasibility, precompute max capacity.
        maxcap = caps[0] if caps else 0
        dq = deque(segs)
        while dq:
            x = dq.popleft()
            if dq and x + dq[0] <= maxcap:
                y = dq.popleft()
                dq.appendleft(x+y)  # merged, attempt further merges
            else:
                merged.append(x)
        merged.sort()
        segments[i] = merged
    # Now we have top-level segments that must be covered by companies; pack them into capacities using best-fit decreasing
    all_segs = segments[0] if segments[0] else []
    # If there are segments from other disconnected parts (shouldn't), include them
    for i in range(1, n):
        if segments[i]:
            # include only those segments that are not descendants of others: skip since segments propagated upward
            pass
    # All segments sums must be <= max capacity; if any segment > maxcap, we must split into unit nodes (worst-case)
    # Split oversized segments into node-sized pieces greedily (approx): use demand values as base pieces
    pieces = []
    # collect node demands as base pieces
    for val in demand:
        pieces.append(val)
    pieces.sort(reverse=True)
    # capacities sorted descending; we'll assign companies greedily filling up to capacity
    caps_sorted = sorted(capacities, reverse=True)
    if not caps_sorted:
        return float('inf')
    used = 0
    # If any single demand > max capacity, we must split it across multiple companies: treat as multiple units equal to demand
    # Assign using First-Fit-Decreasing with multiple identical bins (companies) available by capacities list repeated.
    # We'll assume unlimited use of each capacity value but count number used.
    # For each piece, place into existing open company if fits, else open new company choosing largest capacity available.
    open_bins = []  # remaining capacities of opened companies (max-heap via negative)
    import heapq
    open_bins = []
    # For choosing new company capacity use largest that can fit piece
    for piece in pieces:
        # Try to fit into existing
        if open_bins:
            # pop the bin with largest remaining
            rem = -heapq.heappop(open_bins)
            if rem >= piece:
                rem -= piece
                heapq.heappush(open_bins, -rem)
                continue
            else:
                # cannot fit, push back and open new
                heapq.heappush(open_bins, -rem)
        # open new company: pick smallest capacity that >= piece to be efficient; capacities list may be reused multiple times
        idx = bisect.bisect_left(sorted(capacities), piece)
        if idx == len(capacities):
            # no single capacity can fit piece; need multiple companies: split piece into units of maxcap
            maxcap = max(capacities)
            cnt = piece // maxcap
            rem = piece % maxcap
            for _ in range(cnt):
                used += 1
            if rem > 0:
                # open one more for remainder
                used += 1
                heapq.heappush(open_bins, -(maxcap - rem))
            continue
        # choose capacity at idx (smallest >= piece)
        cap_chosen = sorted(capacities)[idx]
        used += 1
        if cap_chosen > piece:
            heapq.heappush(open_bins, -(cap_chosen - piece))
    # total used is used + currently opened bins count (they were counted when opened)
    # used already counted opens; any bins in open_bins were opened and counted; so final answer is used
    return used