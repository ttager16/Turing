def in_bounds(r,c):
    return 0<=r<5 and 0<=c<5

def neighbors8(r,c):
    for dr,dc in DIRS_8:
        nr,nc = r+dr, c+dc
        if in_bounds(nr,nc):
            yield nr,nc

def line_steps(r,c,dr,dc,dist):
    for k in range(1,dist+1):
        nr, nc = r+dr*k, c+dc*k
        if not in_bounds(nr,nc):
            return []
    return [(r+dr*k, c+dc*k) for k in range(1,dist+1)]

def calculate_min_power(grid: list[list[int]], builder_pos: list[int], scout_pos: list[int],
                        unstable_cells: list[list[int]], target_pos: list[int]) -> float:
    start_builder = tuple(builder_pos)
    start_scout = tuple(scout_pos)
    unstable_set = frozenset(tuple(x) for x in unstable_cells)
    target = tuple(target_pos)
    # state: (builder_pos, scout_pos, tuple of flattened heights (25), unstable frozenset)
    def pack_heights(h):
        return tuple(h[r][c] for r in range(5) for c in range(5))
    init_heights = [row[:] for row in grid]
    start_heights = pack_heights(init_heights)
    start_state = (start_builder, start_scout, start_heights, unstable_set)
    # Dijkstra
    pq = [(0.0, start_state)]
    dist = {start_state:0.0}
    while pq:
        cost, state = heapq.heappop(pq)
        if dist.get(state, float('inf')) < cost - 1e-12:
            continue
        builder, scout, heights_flat, unstable = state
        # Termination: Builder at target and can perform Finalize Site (cost 10)
        if builder == target:
            # Finalize Site is an action; check if builder's cell is not height 4 (can't be on height 4 per rules it might be allowed but building not allowed on 4)
            # The finalize action requires only being at target. Check and return cost +10
            final_cost = cost + 10.0
            return float(final_cost)
        # Reconstruct heights 2D view via tuple access
        def h_at(pos):
            r,c = pos
            return heights_flat[r*5 + c]
        def set_h(heights_flat, pos, newh):
            lst = list(heights_flat)
            r,c = pos
            lst[r*5 + c] = newh
            return tuple(lst)
        # Generate Builder moves: move to any adjacent (8)
        for nb in neighbors8(*builder):
            if nb == scout:
                continue
            if nb in unstable:
                continue
            h_old = h_at(builder)
            h_new = h_at(nb)
            if h_new == 4:
                continue
            move_cost = 1 + max(0, h_new - h_old)
            new_cost = cost + move_cost
            # After moving, Builder may perform Build action: deposit on an adjacent square to its new position (increase that square's elevation by one).
            # Build is optional; we must consider both with and without building.
            # First: without build -> state updated builder pos
            new_state = (nb, scout, heights_flat, unstable)
            if new_cost < dist.get(new_state, float('inf')) - 1e-12:
                dist[new_state] = new_cost
                heapq.heappush(pq, (new_cost, new_state))
            # With build: choose an adjacent sq to nb to increase by one, subject to height<4 and not unstable and not occupied by scout or builder
            for btarget in neighbors8(*nb):
                if btarget == scout:
                    continue
                if btarget in unstable:
                    continue
                ht = h_at(btarget)
                if ht >= 4:
                    continue
                build_cost = 2.0
                newh = ht + 1
                new_heights = set_h(heights_flat, btarget, newh)
                new_cost2 = new_cost + build_cost
                new_state2 = (nb, scout, new_heights, unstable)
                if new_cost2 < dist.get(new_state2, float('inf')) - 1e-12:
                    dist[new_state2] = new_cost2
                    heapq.heappush(pq, (new_cost2, new_state2))
        # Scout actions:
        # Move: can move 1 or 2 in straight line (8 directions)
        for dr,dc in DIRS_8:
            for dist_step in (1,2):
                path = line_steps(scout[0], scout[1], dr, dc, dist_step)
                if not path:
                    break
                blocked = False
                for step in path:
                    if step == builder:
                        blocked = True; break
                    if step in unstable:
                        blocked = True; break
                    if h_at(step) == 4:
                        blocked = True; break
                if blocked:
                    continue
                final_pos = path[-1]
                # compute cost: (1 + max(0, h_final - h_initial)) * distance
                h_initial = h_at(scout)
                h_final = h_at(final_pos)
                move_cost = (1 + max(0, h_final - h_initial)) * dist_step
                new_cost = cost + move_cost
                new_state = (builder, final_pos, heights_flat, unstable)
                if new_cost < dist.get(new_state, float('inf')) - 1e-12:
                    dist[new_state] = new_cost
                    heapq.heappush(pq, (new_cost, new_state))
        # Scout Scan: can scan an adjacent unstable cell, costing 3, making it stable (remove from unstable set)
        for adj in neighbors8(*scout):
            if adj in unstable:
                new_unstable = frozenset(x for x in unstable if x != adj)
                new_cost = cost + 3.0
                new_state = (builder, scout, heights_flat, new_unstable)
                if new_cost < dist.get(new_state, float('inf')) - 1e-12:
                    dist[new_state] = new_cost
                    heapq.heappush(pq, (new_cost, new_state))
    return float('inf')