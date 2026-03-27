def allocate_minimum_workshops(
    workshop_slots: List[List[int]],
    student_preferences: List[List[int]]
) -> int:
    # Validate inputs
    if not isinstance(workshop_slots, list) or not isinstance(student_preferences, list):
        raise ValueError("workshop_slots and student_preferences must be lists")
    m = len(workshop_slots)
    n = len(student_preferences)
    for i, w in enumerate(workshop_slots):
        if not isinstance(w, list) or len(w) < 4:
            raise ValueError(f"workshop_slots[{i}] must be a list of at least 4 ints [campus,timeslot,capacity,instructor]")
        campus, timeslot, capacity, instructor = w[:4]
        if not isinstance(campus, int) or not isinstance(timeslot, int) or not isinstance(capacity, int) or not isinstance(instructor, int):
            raise ValueError(f"workshop_slots[{i}] entries must be ints")
        if capacity < 0:
            raise ValueError(f"workshop_slots[{i}] has negative capacity")
    for i, prefs in enumerate(student_preferences):
        if not isinstance(prefs, list):
            raise ValueError(f"student_preferences[{i}] must be a list")
        if len(prefs) == 0:
            # no feasible option
            return -1
        for idx in prefs:
            if not isinstance(idx, int) or idx < 0 or idx >= m:
                raise ValueError(f"student_preferences[{i}] contains invalid workshop index {idx}")

    # Build auxiliary data
    # For instructors, enforce a limit: to model "escalating logistical cost" we'll treat that each instructor can teach unlimited but we prefer fewer workshops overall.
    # We must find minimal set of workshops such that all students can be assigned respecting capacities and that no student assigned to overlapping timeslots on different campuses (student can't be double-booked).
    # Since each student needs exactly one workshop, "double-booking" for students is avoided by assignment to single chosen workshop.
    # The main combinatorial problem reduces to choosing minimal subset of workshops S such that a bipartite matching from students to workshops in S respecting capacities exists.
    # We'll brute-force over subsets by increasing size (m expected small for realistic input). If m large, this may be slow but meets spec.

    # Precompute student->workshop adjacency
    student_opts = [set(p) for p in student_preferences]

    # Quick impossibility: any student with no preferences already handled.
    # Also if total capacity of all workshops < n then impossible
    total_capacity = sum(w[2] for w in workshop_slots)
    if total_capacity < n:
        return -1

    # Helper: check if subset of workshops (indices) can accommodate all students via flow (bipartite matching with capacities)
    def can_assign(subset: Set[int]) -> bool:
        # Build network: source -> each student (cap 1) -> allowed workshops in subset -> sink (cap = workshop capacity)
        # Implement Dinic
        # Node indexing: source=0, students 1..n, workshops n+1 .. n+len(subset), sink = last
        idx_map = {}
        wlist = sorted(subset)
        for i, w in enumerate(wlist):
            idx_map[w] = n + 1 + i
        src = 0
        sink = n + 1 + len(wlist)
        N = sink + 1
        adj = [[] for _ in range(N)]
        def add_edge(u, v, c):
            adj[u].append([v, c, len(adj[v])])
            adj[v].append([u, 0, len(adj[u]) - 1])
        for si in range(n):
            add_edge(src, 1 + si, 1)
            for w in student_opts[si]:
                if w in subset:
                    add_edge(1 + si, idx_map[w], 1)
        for w in wlist:
            cap = workshop_slots[w][2]
            add_edge(idx_map[w], sink, cap)
        # Dinic
        level = [0]*N
        it = [0]*N
        def bfs():
            for i in range(N):
                level[i] = -1
            q = deque()
            level[src] = 0
            q.append(src)
            while q:
                u = q.popleft()
                for v, c, rev in adj[u]:
                    if c > 0 and level[v] < 0:
                        level[v] = level[u] + 1
                        q.append(v)
            return level[sink] >= 0
        def dfs(u, f):
            if u == sink:
                return f
            for i in range(it[u], len(adj[u])):
                v, c, rev = adj[u][i]
                if c > 0 and level[v] == level[u] + 1:
                    ret = dfs(v, min(f, c))
                    if ret > 0:
                        adj[u][i][1] -= ret
                        adj[v][adj[u][i][2]][1] += ret
                        return ret
                it[u] += 1
            return 0
        flow = 0
        while bfs():
            it = [0]*N
            while True:
                pushed = dfs(src, 10**9)
                if pushed == 0:
                    break
                flow += pushed
                if flow == n:
                    return True
        return flow == n

    # Iterate subset sizes from 1..m
    # Quick prune: any workshop with capacity 0 can be ignored
    nonzero_ws = [i for i, w in enumerate(workshop_slots) if w[2] > 0]
    if not nonzero_ws:
        return -1
    # If number of workshops is small, brute force combinations; else use greedy lower bound and heuristics
    MAX_BRUTE = 20  # threshold
    if len(nonzero_ws) <= MAX_BRUTE:
        for k in range(1, len(nonzero_ws)+1):
            for comb in itertools.combinations(nonzero_ws, k):
                subset = set(comb)
                # quick capacity prune
                cap_sum = sum(workshop_slots[w][2] for w in subset)
                if cap_sum < n:
                    continue
                if can_assign(subset):
                    return k
        return -1
    else:
        # Heuristic: greedy select workshops that cover most yet-unassigned students per capacity-weighted score, then try to shrink
        remaining = set(range(m))
        selected = set()
        uncovered_students = set(range(n))
        while uncovered_students:
            # score each workshop by number of uncovered students that prefer it, capped by capacity
            best = None
            best_score = -1
            for w in remaining:
                cap = workshop_slots[w][2]
                if cap <= 0:
                    continue
                canserve = sum(1 for s in uncovered_students if w in student_opts[s])
                score = min(canserve, cap)
                if score > best_score:
                    best_score = score
                    best = w
            if best is None or best_score == 0:
                return -1
            selected.add(best)
            remaining.remove(best)
            # simulate assigning up to capacity arbitrary uncovered students who prefer it
            cap = workshop_slots[best][2]
            assigned = 0
            to_remove = []
            for s in list(uncovered_students):
                if best in student_opts[s]:
                    to_remove.append(s)
                    assigned += 1
                    if assigned >= cap:
                        break
            for s in to_remove:
                uncovered_students.remove(s)
        # Now we have a candidate selected set. Try to minimize by testing subsets of selected
        sel_list = sorted(selected)
        best_count = len(sel_list)
        for k in range(1, best_count+1):
            for comb in itertools.combinations(sel_list, k):
                subset = set(comb)
                if sum(workshop_slots[w][2] for w in subset) < n:
                    continue
                if can_assign(subset):
                    return k
        # if no smaller subset found, verify full selected works
        if can_assign(selected):
            return len(selected)
        return -1