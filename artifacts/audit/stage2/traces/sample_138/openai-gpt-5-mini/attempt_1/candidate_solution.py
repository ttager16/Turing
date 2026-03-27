def process_network_operations(n: int, operations: list[list[str]]) -> list[int]:
    from collections import defaultdict
    results = []
    # State history: list of tuples (edges_dict, valid)
    # edges_dict: mapping (u,v) with u<=v -> (cost, priority)
    # We'll store edges as frozenset({u,v}) key as tuple (min,max)
    history_edges = []
    history_valid = []
    # initial state
    history_edges.append(dict())
    history_valid.append(True)
    op_count = 0  # operations processed
    for op in operations:
        op_count += 1
        typ = op[0]
        if typ == "ADD":
            # parse
            try:
                u = int(op[1])
                v = int(op[2])
                c = int(op[3])
                p = int(op[4])
            except:
                # malformed -> become invalid
                prev_edges = history_edges[-1].copy()
                history_edges.append(prev_edges)
                history_valid.append(False)
                continue
            prev_edges = history_edges[-1].copy()
            prev_valid = history_valid[-1]
            if u == v:
                # invalidates
                prev_edges = prev_edges
                history_edges.append(prev_edges)
                history_valid.append(False)
                continue
            a, b = (u, v) if u <= v else (v, u)
            prev_edges[(a, b)] = (c, 1 if p else 0)
            # adding/updating is valid
            history_edges.append(prev_edges)
            history_valid.append(True)
        elif typ == "REMOVE":
            try:
                u = int(op[1])
                v = int(op[2])
            except:
                prev_edges = history_edges[-1].copy()
                history_edges.append(prev_edges)
                history_valid.append(False)
                continue
            prev_edges = history_edges[-1].copy()
            prev_valid = history_valid[-1]
            a, b = (u, v) if u <= v else (v, u)
            if (a, b) in prev_edges:
                del prev_edges[(a, b)]
                history_edges.append(prev_edges)
                history_valid.append(True)
            else:
                # becomes invalid until next successful modification
                history_edges.append(prev_edges)
                history_valid.append(False)
        elif typ == "ROLLBACK":
            try:
                k = int(op[1])
            except:
                history_edges.append(history_edges[-1].copy())
                history_valid.append(False)
                continue
            if 0 <= k <= len(operations):
                # restore state immediately after k-th operation
                # which corresponds to history index k
                # but our history has initial state at index 0, op1 at 1, ...
                if k <= len(history_edges)-1:
                    edges_copy = history_edges[k].copy()
                    valid_flag = history_valid[k]
                    history_edges.append(edges_copy)
                    history_valid.append(valid_flag)
                else:
                    # out of range
                    history_edges.append(history_edges[-1].copy())
                    history_valid.append(False)
            else:
                history_edges.append(history_edges[-1].copy())
                history_valid.append(False)
        elif typ == "QUERY":
            curr_edges = history_edges[-1]
            curr_valid = history_valid[-1]
            if not curr_valid:
                results.append(-1)
                history_edges.append(curr_edges.copy())
                history_valid.append(curr_valid)
                continue
            if not curr_edges:
                results.append(0)
                history_edges.append(curr_edges.copy())
                history_valid.append(curr_valid)
                continue
            # Build edge index and adjacency
            edges_list = list(curr_edges.items())  # [((u,v),(cost,pri)), ...]
            m = len(edges_list)
            # Map edge idx
            idx_of = {}
            for i, (uv, cp) in enumerate(edges_list):
                idx_of[uv] = i
            # adjacency: which edges are dominated by selecting edge i (itself and those sharing endpoint)
            adj = [0]*m  # bitmask of edges covered
            endpoints = []
            for i, (uv, (cost, pri)) in enumerate(edges_list):
                u,v = uv
                endpoints.append((u,v))
            for i in range(m):
                u1,v1 = endpoints[i]
                mask = 0
                for j in range(m):
                    u2,v2 = endpoints[j]
                    if i==j or u1==u2 or u1==v2 or v1==u2 or v1==v2:
                        mask |= (1<<j)
                adj[i] = mask
            # forced picks: priority edges must be selected
            forced = 0
            forced_cost = 0
            costs = [cp[0] for (_,cp) in edges_list]
            pri_flags = [cp[1] for (_,cp) in edges_list]
            for i in range(m):
                if pri_flags[i]:
                    forced |= (1<<i)
                    forced_cost += costs[i]
            covered = 0
            for i in range(m):
                if (forced>>i)&1:
                    covered |= adj[i]
            full = (1<<m)-1
            if covered == full:
                results.append(forced_cost)
                history_edges.append(curr_edges.copy())
                history_valid.append(curr_valid)
                continue
            remaining = full & (~covered)
            rem_count = remaining.bit_count()
            # If small (<=20 edges), compute exact via DP over subsets of edges to pick
            if m <= 20:
                # Try selecting subset S that includes all forced bits and covers all edges, minimize cost
                best = None
                # enumerate subsets superset of forced: iterate over subsets of non-forced edges
                nonforced_indices = [i for i in range(m) if not ((forced>>i)&1)]
                nf = len(nonforced_indices)
                # Precompute adj for selection of forced + subset
                best_cost = None
                for s in range(1<<nf):
                    sel_mask = forced
                    cost = forced_cost
                    for j in range(nf):
                        if (s>>j)&1:
                            i = nonforced_indices[j]
                            sel_mask |= (1<<i)
                            cost += costs[i]
                    # compute coverage
                    cov = 0
                    for i in range(m):
                        if (sel_mask>>i)&1:
                            cov |= adj[i]
                    if cov == full:
                        if best_cost is None or cost < best_cost:
                            best_cost = cost
                results.append(best_cost if best_cost is not None else -1)
                history_edges.append(curr_edges.copy())
                history_valid.append(curr_valid)
                continue
            # For larger graphs use greedy deterministic heuristic:
            # Start with forced picks, then greedily pick edge with best (new_covered_cost_ratio),
            # tie-breaker by lower cost, then by smaller index to be deterministic.
            sel = 0
            sel_cost = 0
            sel |= forced
            sel_cost += forced_cost
            covered = 0
            for i in range(m):
                if (sel>>i)&1:
                    covered |= adj[i]
            while covered != full:
                best_i = None
                best_new = -1
                best_ratio = None
                for i in range(m):
                    if (sel>>i)&1:
                        continue
                    new_cov = adj[i] & (~covered)
                    new_cnt = new_cov.bit_count()
                    if new_cnt == 0:
                        continue
                    ratio = costs[i] / new_cnt
                    if best_i is None or ratio < best_ratio or (abs(ratio - best_ratio) < 1e-12 and costs[i] < costs[best_i]) or (abs(ratio - best_ratio) < 1e-12 and costs[i]==costs[best_i] and i < best_i):
                        best_i = i
                        best_ratio = ratio
                        best_new = new_cnt
                if best_i is None:
                    # cannot cover remaining edges
                    sel_cost = -1
                    break
                sel |= (1<<best_i)
                sel_cost += costs[best_i]
                covered |= adj[best_i]
            results.append(sel_cost if sel_cost >= 0 else -1)
            history_edges.append(curr_edges.copy())
            history_valid.append(curr_valid)
        else:
            # unknown op -> state unchanged but invalid
            history_edges.append(history_edges[-1].copy())
            history_valid.append(False)
    return results