def circulant_decomposition(adj_matrix):
    """
    Performs compound circulant decomposition on a multi-layer adjacency matrix.
    
    Args:
        adj_matrix: List[List[int]] - Square adjacency matrix
        
    Returns:
        List[List[List[int]]] - List of circulant matrices
    """
    # Copy input
    n = len(adj_matrix)
    if n == 0:
        return []
    # validate square
    for row in adj_matrix:
        if len(row) != n:
            raise ValueError("Input must be a square matrix")
    rem = [row[:] for row in adj_matrix]
    result = []
    # Helper to build circulant from offset k and value v
    def build_circulant(k, v):
        C = [[0]*n for _ in range(n)]
        for i in range(n):
            j = (i + k) % n
            C[i][j] = v
        return C
    # While there is any non-zero in rem
    while True:
        # find all non-zero positions and candidate offsets and values
        nonzeros = [(i, j, rem[i][j]) for i in range(n) for j in range(n) if rem[i][j] != 0]
        if not nonzeros:
            break
        # For each non-zero position (r,c) with value v, the circulant is defined by offset k = (c - r) mod n and value v.
        # Evaluate score: number of positions where rem[i][j] == v and (j - i) mod n == k
        best = None  # tuple (score, r, c, v, k)
        # To speed a bit, precompute for each k and v the count
        # But values up to 1000; instead compute per seen (k,v) from nonzeros
        counts = {}
        for (r, c, v) in nonzeros:
            k = (c - r) % n
            key = (k, v)
            if key in counts:
                continue
            cnt = 0
            for i in range(n):
                j = (i + k) % n
                if rem[i][j] == v:
                    cnt += 1
            counts[key] = cnt
        # pick best by max count, tie-break larger v then smallest k
        for (r, c, v) in nonzeros:
            k = (c - r) % n
            cnt = counts[(k, v)]
            candidate = (cnt, v, -k, r, c, k)  # prefer larger cnt, larger v, smaller k
            if best is None or candidate > best:
                best = candidate
                best_choice = (r, c, v, k, cnt)
        # Extract chosen circulant
        _, _, v, k, cnt = best_choice[0], best_choice[1], best_choice[2], best_choice[3], best_choice[4]  # unpack
        # But best_choice defined as (r,c,v,k,cnt)
        r, c, v, k, cnt = best_choice
        C = build_circulant(k, v)
        # Subtract C from rem element-wise
        for i in range(n):
            j = (i + k) % n
            rem[i][j] -= v
            if rem[i][j] < 0:
                # Numerical safety: clamp to zero if over-subtracted due to logic error
                rem[i][j] = 0
        result.append(C)
    return result