def maxProductKIncreasing(nums: List[int], K: int, D: int) -> int:
    n = len(nums)
    if K > n:
        return 0

    # Precompute possible next indices for each i (including virtual start -1)
    # For start -1, allowed next are any index
    nexts = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            if nums[j] > nums[i] and nums[j] - nums[i] >= D:
                nexts[i].append(j)
    starts = [i for i in range(n)]  # possible starts

    # We'll attempt DP with memoization: state is (used_mask, last_index_of_current_chain, chains_done)
    # But mask 2^200 impossible. Instead, we model by assigning elements in order to chains.
    # Alternative approach: dynamic programming by positions: we process nums in order,
    # and maintain for each chain its last value and length. K <=10 and n<=200.
    # Represent last values as tuple of indices or None, and lengths tuple.
    # To reduce states, store last indices (or -1) and lengths. Use pruning by canonical ordering of chains:
    # sort chains by last value then by length to break symmetry.

    # Represent chain last value as value (number) and last pos to enforce order of picks
    from collections import defaultdict, deque

    @lru_cache(None)
    def dp(pos, lasts_vals, lasts_pos, lengths):
        # pos: next index to consider (0..n)
        # lasts_vals: tuple of K numbers or a sentinel None -> use large negative for None
        # lasts_pos: tuple of K ints (-1 for empty)
        # lengths: tuple of K ints
        if pos == n:
            # all elements assigned; verify no empty chain
            if 0 in lengths:
                return 0
            prod = 1
            for L in lengths:
                prod *= L
            return prod

        v = nums[pos]
        best = 0
        # try assign nums[pos] to any chain i where allowed:
        for i in range(K):
            lp = lasts_pos[i]
            if lp == -1:
                # empty chain: can always start
                can = True
            else:
                # must be later in sequence and value increase + D
                if v > lasts_vals[i] and v - lasts_vals[i] >= D:
                    # also must maintain relative order: pos > lp always true since we process in order
                    can = True
                else:
                    can = False
            if not can:
                continue
            # assign
            new_lasts_vals = list(lasts_vals)
            new_lasts_pos = list(lasts_pos)
            new_lengths = list(lengths)
            new_lasts_vals[i] = v
            new_lasts_pos[i] = pos
            new_lengths[i] += 1
            # To reduce symmetric states, we canonicalize chains by sorting them with key (last_pos==-1, last_val, length)
            combined = list(zip(new_lasts_vals, new_lasts_pos, new_lengths))
            # Sorting key: empty chains go last to keep starts consistent; non-empty ordered by last_pos then val
            def key(t):
                val, p, L = t
                return (p == -1, p if p!=-1 else 10**9, val if p!=-1 else 10**9, -L)
            combined.sort(key=key)
            nl_vals = tuple(x[0] for x in combined)
            nl_pos = tuple(x[1] for x in combined)
            nl_len = tuple(x[2] for x in combined)
            res = dp(pos+1, nl_vals, nl_pos, nl_len)
            if res > best:
                best = res
        return best

    # initial tuples
    neg = -10**9
    init_vals = tuple([neg]*K)
    init_pos = tuple([-1]*K)
    init_len = tuple([0]*K)
    return dp(0, init_vals, init_pos, init_len)