def circulant_decomposition(adj_matrix):
    """
    Performs compound circulant decomposition on a multi-layer adjacency matrix.
    
    Args:
        adj_matrix: List[List[int]] - Square adjacency matrix
        
    Returns:
        List[List[List[int]]] - List of circulant matrices
    """
    n = len(adj_matrix)
    if n == 0:
        return []
    # copy remaining
    rem = [row[:] for row in adj_matrix]
    result = []
    # helper to build circulant for offset k with value v
    def build_circulant_for_offset(k, v):
        C = [[0]*n for _ in range(n)]
        for i in range(n):
            j = (i + k) % n
            C[i][j] = v
        return C
    # helper to subtract circulant
    def subtract_circulant(C):
        for i in range(n):
            for j in range(n):
                rem[i][j] -= C[i][j]
    # helper to check zeros
    def is_zero():
        for i in range(n):
            for j in range(n):
                if rem[i][j] != 0:
                    return False
        return True
    while not is_zero():
        # consider all non-zero positions as candidate (r,c)
        best_score = -1
        best_choice = None  # tuple (k,v)
        for i in range(n):
            for j in range(n):
                v = rem[i][j]
                if v <= 0:
                    continue
                k = (j - i) % n
                # compute score: number of positions where rem equals v along this offset
                score = 0
                # Also ensure we don't propose negative subtraction: only positions where rem >= v
                valid = True
                for ii in range(n):
                    jj = (ii + k) % n
                    if rem[ii][jj] == v:
                        score += 1
                    if rem[ii][jj] < v:
                        # If any position would go negative, this candidate is invalid
                        valid = False
                        break
                if not valid:
                    continue
                # prefer larger v when tie in score to reduce iterations
                if score > best_score or (score == best_score and (best_choice is None or v > best_choice[1])):
                    best_score = score
                    best_choice = (k, v)
        # If no valid candidate found (due to some positions smaller than any candidate v),
        # fallback: pick smallest positive entry and subtract that single-entry circulant (k such that only positions where rem>=v)
        if best_choice is None:
            # find any positive minimal v and its position
            min_v = None
            pos = None
            for i in range(n):
                for j in range(n):
                    v = rem[i][j]
                    if v > 0 and (min_v is None or v < min_v):
                        min_v = v
                        pos = (i, j)
            if min_v is None:
                break
            k = (pos[1] - pos[0]) % n
            best_choice = (k, min_v)
        k, v = best_choice
        C = build_circulant_for_offset(k, v)
        subtract_circulant(C)
        result.append(C)
    return result