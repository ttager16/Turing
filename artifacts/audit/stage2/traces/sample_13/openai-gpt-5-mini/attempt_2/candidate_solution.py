def allocate_minimum_agencies(population: List[int], demands: List[int], max_cost: int) -> int:
    n = len(population)
    if n == 0:
        return 0
    # Precompute base costs
    base = [(population[i] / 1000.0) + (demands[i] * 1.5) + (i * 0.5) for i in range(n)]
    is_priority = [(demands[i] > 40 or population[i] > 8000) for i in range(n)]
    # Helper to compute shared cost between i and i+1 given sharing placed at j (j is higher demand region)
    def shared_cost(i, j):
        # j is index where agency is placed (either i or i+1)
        pop_i = population[i]
        pop_j = population[i+1]
        # Determine discount rules per statement:
        # If both regions have population < 3000: discount = 0.80
        # Else if one region has population >=3000 and <6000: discount = 0.85
        # Else if one region has population >=6000: discount = 0.90
        # However priority share with non-priority has multiplier 1.0 (no discount)
        if is_priority[i] or is_priority[i+1]:
            # If both priority -> invalid sharing handled earlier; if one priority and one not -> no discount
            if is_priority[i] and is_priority[i+1]:
                return None
            else:
                discount = 1.0
        else:
            if population[i] < 3000 and population[i+1] < 3000:
                discount = 0.80
            elif (population[i] >= 6000) or (population[i+1] >= 6000):
                discount = 0.90
            else:
                # at least one in [3000,5999]
                discount = 0.85
        return discount * base[j]
    # Cost for individual placement at i
    def individual_cost(i):
        return base[i]
    # Minimum placement demand constraint: regions with demands>=35 must be covered by an agency placed at a region with demand>=30
    # For individual coverage, placed at same region so check demands[i] >=30
    # For shared coverage, placement at higher demand region must have demand>=30 if any covered region has demand>=35.
    # We'll enforce when building transitions.
    INF = float('inf')
    # DP over positions with state describing previous sharing to enforce chain and cluster penalties.
    # We'll minimize tuple: (num_agencies, total_cost, consecutive_individuals)
    # But we must find minimal num_agencies subject to cost<=max_cost. So do DP where for each position we keep map:
    # For each possible number of agencies up to i+1, minimal cost achievable and minimal consecutive individual tail.
    # However n up to 1e5, agencies <= n. But we can instead do DP by scanning minimizing agencies using BFS-like increasing agencies using pruning by cost.
    # We'll perform dynamic programming where dp[i][state] = minimal cost to cover up to index i-1 with given last_was_shared flag and consecutive individual tail length.
    # State encoding: last_shared: 0 or 1 meaning previous placement was shared (i-1 with i-2) or not.
    # If last_shared==1, chain prevents next (i) from sharing with i+1? Chain constraint: if i-1 was part of shared with i, then i+1 cannot share with i. Equivalent: if previous placement was sharing covering (i-2,i-1) then sharing (i-1,i) is invalid. For DP at position pos we consider covering region pos.
    # We'll define dp[pos][last_shared][consec_individuals] = minimal (num_agencies, cost)
    # To keep states small, consecutive individual count capped at 3 (>=3 matters only for penalty counting once per extra? Penalty applies for each sequence of 3+ individual agencies add 5.0 per such sequence. That equals for every time a run reaches length 3 add 5, and for longer run don't add extra until maybe overlapping? Interpretation: Each sequence of length L>=3 adds 5.0 once. So we only need to know whether current run length >=3 (flag).
    # So consec_ind in {0,1,2,3} where 3 means >=3.
    from collections import defaultdict
    # dp at position 0 (no regions covered): map key=(last_shared_flag, consec_ind) -> tuple(min_agencies, cost)
    # last_shared is whether previous placement was a shared that involved previous region (for pos=0 it's 0)
    dp = { (0,0): (0, 0.0) }
    for i in range(n):
        ndp = dict()
        for (last_shared, consec), (num_ag, cost_so_far) in dp.items():
            # Option 1: Place individual agency at i
            # Check priority: priority regions can be individual -> allowed
            place_cost = individual_cost(i)
            new_cost = cost_so_far + place_cost
            new_consec = consec + 1 if last_shared==0 else 1
            if new_consec >= 3:
                # if newly reached 3 from 2 to 3, we need to add cluster penalty once when we make it reach >=3.
                if consec < 3:
                    new_cost += 5.0
                new_consec = 3
            # Minimum coverage: if demands[i] >=35, placement region demand must be >=30 -> individual placed at i so check demands[i]>=30
            if demands[i] >= 35 and demands[i] < 30:
                pass  # impossible, but demands[i]>=35 implies >=30 always, so no need
            # Accept if cost within bounds (we can prune >max_cost)
            if new_cost <= max_cost:
                key = (0, new_consec)
                val = (num_ag + 1, new_cost)
                prev = ndp.get(key)
                if (prev is None) or (val[0] < prev[0]) or (val[0]==prev[0] and val[1] < prev[1]):
                    ndp[key] = val
            # Option 2: Share with i+1 (if exists)
            if i+1 < n:
                # Can't if last_shared==1 because chain constraint: previous shared involved i-1 and i, so cannot share i and i+1
                if last_shared == 1:
                    pass
                else:
                    # Sharing must be placed at higher demand region; if equal demand use higher population; if equal both use lower index
                    # Determine placement index j among i and i+1
                    if demands[i] > demands[i+1]:
                        j = i
                    elif demands[i] < demands[i+1]:
                        j = i+1
                    else:
                        # equal demands
                        if population[i] > population[i+1]:
                            j = i
                        elif population[i] < population[i+1]:
                            j = i+1
                        else:
                            j = i  # lower index
                    # Priority constraints: two adjacent priority cannot share
                    if is_priority[i] and is_priority[i+1]:
                        pass
                    else:
                        # If one priority and one not, sharing allowed but no discount (handled in shared_cost)
                        sc = shared_cost(i, j)
                        if sc is not None:
                            # Minimum coverage: if either region has demand>=35, placement region demand must be >=30
                            if (demands[i] >= 35 or demands[i+1] >= 35) and demands[j] < 30:
                                pass
                            else:
                                # also if priority region sharing with non-priority allowed but only one adjacent non-priority; that's ensured locally
                                new_cost2 = cost_so_far + sc
                                # Sharing resets consecutive individual run
                                new_consec2 = 0
                                # No cluster penalty addition here unless previous consec reached >=3 was already accounted earlier
                                if new_cost2 <= max_cost:
                                    key2 = (1, new_consec2)
                                    val2 = (num_ag + 1, new_cost2)
                                    prev2 = ndp.get(key2)
                                    if (prev2 is None) or (val2[0] < prev2[0]) or (val2[0]==prev2[0] and val2[1] < prev2[1]):
                                        ndp[key2] = val2
            # Note: we do not consider covering i by a share started at i-1 because that was already represented by previous state last_shared==1 covering i as second of pair; but our DP transitions always cover region i now. To allow being covered as second of previous share, we must have had in dp a state where previous step chose sharing covering previous and current. However our dp iterates per region and choices made at previous i included sharing to cover i. The current loop over dp entries is for covering i; entries in dp assume coverage up to i-1. So option to be covered as second was included when at i-1 we chose to share with i and advanced i by covering both. But our loop processes one region per iteration; to account for jump when choosing share at i-1 we need to skip next index. Simpler approach: when choosing share at i in dp[pos], we should advance pos by 2. Current design processes i sequentially; when we choose share option at i we must ensure next iteration does not re-cover i+1. To implement, we need to manage advancement. Current loop doesn't support skipping. So change approach: iterate pos and transitions produce states for next position index.
            # Therefore we must rework to include skipping. We'll break and reimplement outside loop.
        # At end of inner loop
        # We'll replace dp with ndp and proceed to next i. BUT above share option didn't skip i+1 -> incorrect.
        # To fix properly, we must implement DP over position index with transitions to next_pos.
        # Therefore abandon this incremental attempt and implement full DP below.
        break

    # Proper DP over positions with transitions to next_pos
    # State: pos -> dict of (last_shared_flag, consec_ind) -> (num_ag, cost)
    dp_pos = [defaultdict(lambda: (10**9, float('inf'))) for _ in range(n+1)]
    # start at pos=0
    dp_pos[0][(0,0)] = (0, 0.0)
    for pos in range(n):
        for (last_shared, consec), (num_ag, cost_so_far) in list(dp_pos[pos].items()):
            # Option 1: place individual at pos -> advances to pos+1
            place_cost = individual_cost(pos)
            new_cost = cost_so_far + place_cost
            new_consec = consec + 1 if last_shared == 0 else 1
            if new_consec >= 3:
                if consec < 3:
                    new_cost += 5.0
                new_consec = 3
            # Minimum coverage: if demands[pos]>=35 ensure placement demand>=30 (always true)
            if new_cost <= max_cost:
                key = (0, new_consec)
                cur = dp_pos[pos+1].get(key, (10**9, float('inf')))
                cand = (num_ag+1, new_cost)
                if (cand[0] < cur[0]) or (cand[0]==cur[0] and cand[1] < cur[1]):
                    dp_pos[pos+1][key] = cand
            # Option 2: share pos with pos+1 -> advances to pos+2
            if pos+1 < n:
                if last_shared == 1:
                    pass
                else:
                    # Determine placement index j
                    if demands[pos] > demands[pos+1]:
                        j = pos
                    elif demands[pos] < demands[pos+1]:
                        j = pos+1
                    else:
                        if population[pos] > population[pos+1]:
                            j = pos
                        elif population[pos] < population[pos+1]:
                            j = pos+1
                        else:
                            j = pos
                    if is_priority[pos] and is_priority[pos+1]:
                        pass
                    else:
                        sc = shared_cost(pos, j)
                        if sc is not None:
                            if (demands[pos] >= 35 or demands[pos+1] >= 35) and demands[j] < 30:
                                pass
                            else:
                                new_cost2 = cost_so_far + sc
                                new_consec2 = 0
                                if new_cost2 <= max_cost:
                                    key2 = (1, new_consec2)
                                    cur2 = dp_pos[pos+2].get(key2, (10**9, float('inf')))
                                    cand2 = (num_ag+1, new_cost2)
                                    if (cand2[0] < cur2[0]) or (cand2[0]==cur2[0] and cand2[1] < cur2[1]):
                                        dp_pos[pos+2][key2] = cand2
    # After finishing, examine dp_pos[n] entries and pick minimal agencies with cost<=max_cost
    best = None
    for (last_shared, consec), (num_ag, cost) in dp_pos[n].items():
        if cost <= max_cost:
            if best is None or num_ag < best:
                best = num_ag
    return -1 if best is None else best