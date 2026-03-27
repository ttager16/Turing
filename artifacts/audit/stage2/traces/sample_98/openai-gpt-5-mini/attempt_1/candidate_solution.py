def max_synergy_path(matrix: List[List[int]], water_costs: List[List[int]], budget: int) -> int:
    R = len(matrix)
    if R == 0:
        return 0
    C = len(matrix[0])
    N = R * C
    MAX_F = 10000
    # Build buckets of positions by fertility
    buckets = [[] for _ in range(MAX_F + 1)]
    for r in range(R):
        row = matrix[r]
        for c in range(C):
            f = row[c]
            buckets[f].append((r, c))
    # Arrays: use array module with suitable types
    # length: unsigned short (H) up to 100000 fits in I as well; use I
    length_arr = array('I', [0]) * N
    total_cost_arr = array('I', [0]) * N
    start_fert_arr = array('I', [0]) * N
    start_r_arr = array('I', [0]) * N
    start_c_arr = array('I', [0]) * N
    hash1_arr = array('Q', [0]) * N
    hash2_arr = array('Q', [0]) * N
    last_r_arr = array('I', [0]) * N
    last_c_arr = array('I', [0]) * N
    # Initialization: no states yet. We'll treat length==0 as empty.
    # Constants for hash
    BASE1 = 911382323
    BASE2 = 972663749
    MASK = (1 << 64) - 1
    # Neighbor order: Right, Left, Down, Up
    neigh_d = [(0,1),(0,-1),(1,0),(-1,0)]
    # Helper to index
    def idx(r,c):
        return r*C + c
    # Process in nondecreasing fertility
    for fert in range(MAX_F + 1):
        bucket = buckets[fert]
        if not bucket:
            continue
        # For deterministic processing within same fertility, sort by row then col
        bucket.sort()
        # First, for each cell, consider starting new path at cell
        for (r,c) in bucket:
            i = idx(r,c)
            cost = water_costs[r][c]
            if cost <= budget:
                length_arr[i] = 1
                total_cost_arr[i] = cost
                start_fert_arr[i] = matrix[r][c]
                start_r_arr[i] = r
                start_c_arr[i] = c
                x = r*C + c
                h1 = ( (0 * BASE1) + (x + 1) ) & MASK
                h2 = ( (0 * BASE2) + (x + 1) ) & MASK
                hash1_arr[i] = h1
                hash2_arr[i] = h2
                last_r_arr[i] = r
                last_c_arr[i] = c
            else:
                # leave as zero-length (infeasible)
                length_arr[i] = 0
                total_cost_arr[i] = 0
                start_fert_arr[i] = 0
                start_r_arr[i] = 0
                start_c_arr[i] = 0
                hash1_arr[i] = 0
                hash2_arr[i] = 0
                last_r_arr[i] = 0
                last_c_arr[i] = 0
        # Then, for each cell in bucket, relax from neighbors with lower fertility (since edges from lower to higher)
        # We need to consider neighbors in fixed order when iterating, but relaxations come from neighbors with strictly lower fertility.
        # For deterministic behavior, iterate cells in bucket sorted order and neighbors in fixed order.
        for (r,c) in bucket:
            i_to = idx(r,c)
            fert_to = matrix[r][c]
            cost_to = water_costs[r][c]
            best_len = length_arr[i_to]
            best_cost = total_cost_arr[i_to]
            best_start_fert = start_fert_arr[i_to]
            best_start_r = start_r_arr[i_to]
            best_start_c = start_c_arr[i_to]
            best_h1 = hash1_arr[i_to]
            best_h2 = hash2_arr[i_to]
            best_last_r = last_r_arr[i_to]
            best_last_c = last_c_arr[i_to]
            # Consider each neighbor as predecessor (neighbor must have strictly smaller fertility)
            for dr,dc in neigh_d:
                nr = r + dr
                nc = c + dc
                if not (0 <= nr < R and 0 <= nc < C):
                    continue
                if matrix[nr][nc] >= fert_to:
                    continue
                j = idx(nr,nc)
                Lj = length_arr[j]
                if Lj == 0:
                    continue
                Cj = total_cost_arr[j]
                new_cost = Cj + cost_to
                if new_cost > budget:
                    continue
                # Build candidate state S
                new_L = Lj + 1
                new_C = new_cost
                new_start_fert = start_fert_arr[j]
                new_start_r = start_r_arr[j]
                new_start_c = start_c_arr[j]
                # compute new hashes: take existing hash and append this cell id
                x = r*C + c
                h1j = hash1_arr[j]
                h2j = hash2_arr[j]
                new_h1 = ((h1j * BASE1) + (x + 1)) & MASK
                new_h2 = ((h2j * BASE2) + (x + 1)) & MASK
                new_last_r = r
                new_last_c = c
                # Compare candidate with current best using dominance rules
                replace = False
                if best_len == 0:
                    replace = True
                else:
                    if new_L > best_len:
                        replace = True
                    elif new_L == best_len:
                        if new_C < best_cost:
                            replace = True
                        elif new_C == best_cost:
                            # compare tuple (start_fert, start_r, start_c, h1, h2, last_r, last_c)
                            t1 = (new_start_fert, new_start_r, new_start_c, new_h1, new_h2, new_last_r, new_last_c)
                            t2 = (best_start_fert, best_start_r, best_start_c, best_h1, best_h2, best_last_r, best_last_c)
                            if t1 < t2:
                                replace = True
                if replace:
                    best_len = new_L
                    best_cost = new_C
                    best_start_fert = new_start_fert
                    best_start_r = new_start_r
                    best_start_c = new_start_c
                    best_h1 = new_h1
                    best_h2 = new_h2
                    best_last_r = new_last_r
                    best_last_c = new_last_c
                    # write back
                    length_arr[i_to] = best_len
                    total_cost_arr[i_to] = best_cost
                    start_fert_arr[i_to] = best_start_fert
                    start_r_arr[i_to] = best_start_r
                    start_c_arr[i_to] = best_start_c
                    hash1_arr[i_to] = best_h1
                    hash2_arr[i_to] = best_h2
                    last_r_arr[i_to] = best_last_r
                    last_c_arr[i_to] = best_last_c
    # After processing all, find best among all cells (undominated by the tie-breakers)
    best_overall_len = 0
    best_overall_cost = 0
    best_overall_start_fert = 0
    best_overall_start_r = 0
    best_overall_start_c = 0
    best_overall_h1 = 0
    best_overall_h2 = 0
    best_overall_last_r = 0
    best_overall_last_c = 0
    for r in range(R):
        for c in range(C):
            i = idx(r,c)
            L = length_arr[i]
            if L == 0:
                continue
            Cc = total_cost_arr[i]
            sf = start_fert_arr[i]
            sr = start_r_arr[i]
            sc = start_c_arr[i]
            h1 = hash1_arr[i]
            h2 = hash2_arr[i]
            lr = last_r_arr[i]
            lc = last_c_arr[i]
            replace = False
            if best_overall_len == 0:
                replace = True
            else:
                if L > best_overall_len:
                    replace = True
                elif L == best_overall_len:
                    if Cc < best_overall_cost:
                        replace = True
                    elif Cc == best_overall_cost:
                        t1 = (sf, sr, sc, h1, h2, lr, lc)
                        t2 = (best_overall_start_fert, best_overall_start_r, best_overall_start_c, best_overall_h1, best_overall_h2, best_overall_last_r, best_overall_last_c)
                        if t1 < t2:
                            replace = True
            if replace:
                best_overall_len = L
                best_overall_cost = Cc
                best_overall_start_fert = sf
                best_overall_start_r = sr
                best_overall_start_c = sc
                best_overall_h1 = h1
                best_overall_h2 = h2
                best_overall_last_r = lr
                best_overall_last_c = lc
    return int(best_overall_len)