def _dot(A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
    if not A or not B: return []
    m, k = len(A), len(A[0])
    k2 = len(B)
    n = len(B[0])
    out = [[0.0]*n for _ in range(m)]
    for i in range(m):
        for j in range(n):
            s = 0.0
            for t in range(k):
                s += A[i][t]*B[t][j]
            out[i][j] = s
    return out

def _transpose(A: List[List[float]]) -> List[List[float]]:
    if not A: return []
    return [list(row) for row in zip(*A)]

def _eye(n: int) -> List[List[float]]:
    return [[1.0 if i==j else 0.0 for j in range(n)] for i in range(n)]

def _zeros(m:int,n:int) -> List[List[float]]:
    return [[0.0]*n for _ in range(m)]

def _frobenius(A: List[List[float]]) -> float:
    s=0.0
    for row in A:
        for v in row:
            s+=v*v
    return math.sqrt(s)

def _sub(A,B):
    if not A or not B: return []
    m=len(A); n=len(A[0])
    return [[A[i][j]-B[i][j] for j in range(n)] for i in range(m)]

def _round_matrix(A: List[List[float]], dp:int) -> List[List[float]]:
    return [[round(float(v), dp) for v in row] for row in A]

def _upper_triangularize(R: List[List[float]], tol: float) -> List[List[float]]:
    m = len(R)
    n = len(R[0]) if R else 0
    out = [[R[i][j] if j>=i else 0.0 for j in range(n)] for i in range(m)]
    # small values to zero
    for i in range(m):
        for j in range(n):
            if abs(out[i][j]) <= tol:
                out[i][j] = 0.0
    return out

def _householder_qr(A: List[List[float]], tol: float=1e-12) -> Tuple[List[List[float]], List[List[float]]]:
    # Classic Householder QR producing Q (m x m) and R (m x n)
    if not A:
        return [], []
    m = len(A); n = len(A[0])
    R = [row[:] for row in A]
    Q = _eye(m)
    for k in range(min(m,n)):
        # form vector x
        x = [R[i][k] for i in range(k,m)]
        # norm
        normx = math.sqrt(sum(v*v for v in x))
        if normx <= tol:
            continue
        # sign to avoid cancellation: use deterministic sign rule (nonnegative first element of reflected)
        s = 1.0 if x[0] >= 0 else -1.0
        u1 = x[0] + s*normx
        v = [u1] + x[1:]
        vnorm = math.sqrt(sum(vi*vi for vi in v))
        if vnorm <= tol:
            continue
        v = [vi / vnorm for vi in v]
        # apply to R
        for j in range(k, n):
            dot = 0.0
            for i in range(len(v)):
                dot += v[i]*R[k+i][j]
            for i in range(len(v)):
                R[k+i][j] -= 2.0*v[i]*dot
        # apply to Q
        for j in range(m):
            dot = 0.0
            for i in range(len(v)):
                dot += v[i]*Q[k+i][j]
            for i in range(len(v)):
                Q[k+i][j] -= 2.0*v[i]*dot
    Q = _transpose(Q)
    return Q, R

def _sign_fix(R: List[List[float]], Q: List[List[float]], policy: str='nonnegative') -> Tuple[List[List[float]], List[List[float]]]:
    # enforce diagonal sign rule: make diagonal of R nonnegative deterministically
    if not R:
        return Q, R
    m = len(R); n = len(R[0])
    for i in range(min(m,n)):
        diag = R[i][i]
        if diag < 0:
            # multiply column i of R by -1, and row i of Q by -1 (since Q*R)
            for j in range(n):
                R[i][j] = -R[i][j]
            for j in range(len(Q)):
                Q[j][i] = -Q[j][i]
    return Q, R

def _orthogonality_error(Q: List[List[float]]) -> float:
    if not Q: return 0.0
    m = len(Q); n = len(Q[0])
    QTQ = _dot(_transpose(Q), Q)
    I = _eye(n)
    D = _sub(QTQ, I)
    return _frobenius(D)

def _reconstruction_error(A: List[List[float]], Q: List[List[float]], R: List[List[float]]) -> float:
    if not A: return 0.0
    QR = _dot(Q, R)
    D = _sub(QR, A)
    return _frobenius(D) / ( _frobenius(A) if _frobenius(A)>0 else 1.0 )

def _lower_triangle_max(R: List[List[float]]) -> float:
    if not R: return 0.0
    m = len(R); n = len(R[0])
    mx = 0.0
    for i in range(m):
        for j in range(min(i,n)):
            mx = max(mx, abs(R[i][j]))
    return mx

def _estimate_rank(R: List[List[float]], tol: float) -> int:
    if not R: return 0
    r = 0
    for i in range(min(len(R), len(R[0]))):
        if abs(R[i][i]) > tol:
            r += 1
    return r

def _detect_dirty_ranges(prev_mat: Optional[List[List[float]]], mat: Optional[List[List[float]]]) -> List[List[int]]:
    if prev_mat is None or mat is None:
        return []
    if len(prev_mat)!=len(mat) or (mat and len(prev_mat[0])!=len(mat[0])):
        # shape change: mark full
        return [[0, len(mat[0]) if mat else 0]]
    m = len(mat); n = len(mat[0]) if mat else 0
    dirty = []
    start = None
    for j in range(n):
        col_prev = [prev_mat[i][j] for i in range(m)]
        col_new = [mat[i][j] for i in range(m)]
        if any(abs(col_prev[i]-col_new[i])>1e-15 for i in range(m)):
            if start is None:
                start = j
        else:
            if start is not None:
                dirty.append([start, j])
                start = None
    if start is not None:
        dirty.append([start, n])
    return dirty

def qr_incremental_driver(steps: List[Dict[str, Any]],
                          options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    opts = {
        "round_dp": 4,
        "diag_sign": "nonnegative",
        "reorth_epsilon": 5e-4,
        "lower_tol": 1e-6,
        "rank_tol": 1e-10,
        "max_full_refactor": True
    }
    if options:
        opts.update(options)
    round_dp = int(opts.get("round_dp",4))
    reorth_epsilon = float(opts.get("reorth_epsilon",5e-4))
    lower_tol = float(opts.get("lower_tol",1e-6))
    rank_tol = float(opts.get("rank_tol",1e-10))
    # state
    state_mat = None
    state_Q = None
    state_R = None
    checkpoint = {"mat": None, "Q": None, "R": None}
    transcript_steps = []
    equivalences = []
    last_shapes_outputs = {}
    for step in steps:
        op = step.get("op")
        record = {}
        record["op"] = op
        flags = {"reorthogonalized": False, "checkpoint_used": False, "rollback": False, "reset": False}
        record["flags"] = flags
        reason = ""
        dirty_ranges_in = []
        recompute_from = None
        reused_prefix_cols = 0
        full_refactor = False
        sign_convention_ok = True
        metrics = {"orth_error_2": 0.0, "recon_rel_fro": 0.0, "lower_triangle_max": 0.0, "rank_estimate": 0}
        Q_out = []
        R_out = []
        try:
            if op == "reset":
                state_mat = None
                state_Q = None
                state_R = None
                checkpoint = {"mat": None, "Q": None, "R": None}
                flags["reset"] = True
                reason = "reset"
                full_refactor = False
                dirty_ranges_in = []
                recompute_from = None
                reused_prefix_cols = 0
                metrics = {"orth_error_2": 0.0, "recon_rel_fro": 0.0, "lower_triangle_max": 0.0, "rank_estimate": 0}
                Q_out = []
                R_out = []
                record["shape"] = [0,0]
            elif op == "set_matrix":
                mat = step.get("matrix", [])
                m = len(mat)
                n = len(mat[0]) if mat and mat[0] else 0
                record["shape"] = [m,n]
                # detect dirty
                if state_mat is None:
                    dirty_ranges_in = [[0,n]] if n>0 else []
                else:
                    dirty_ranges_in = _detect_dirty_ranges(state_mat, mat)
                # compute earliest changed column
                if dirty_ranges_in:
                    recompute_from = dirty_ranges_in[0][0]
                else:
                    recompute_from = None
                # reuse prefix: if no dirty, reuse all columns
                if recompute_from is None and state_R and state_Q and state_mat and len(state_mat[0])==n:
                    reused_prefix_cols = n
                    full_refactor = False
                    reason = "normal"
                    Q_use = state_Q
                    R_use = state_R
                else:
                    # full refactor if no prior or shape change or dirty starting at 0
                    if state_mat is None or (state_mat is not None and (len(state_mat)!=m or (m>0 and len(state_mat[0])!=n))) or recompute_from==0:
                        # fresh
                        full_refactor = True
                        reason = "fresh" if state_mat is None or recompute_from==0 else "shape_change"
                        # perform full QR
                        Q_calc, R_calc = _householder_qr(mat)
                        Q_calc, R_calc = _sign_fix(R_calc, Q_calc, opts.get("diag_sign"))
                        # metrics
                        orth_err = _orthogonality_error(Q_calc)
                        recon_err = _reconstruction_error(mat, Q_calc, R_calc)
                        lower_max = _lower_triangle_max(R_calc)
                        rank = _estimate_rank(R_calc, rank_tol)
                        # reorth if orth_err large
                        if orth_err > reorth_epsilon:
                            # reorthogonalize via fresh QR on Q_calc to enforce orthonormal
                            flags["reorthogonalized"] = True
                            Q2, R2 = _householder_qr(Q_calc)
                            Q2, R2 = _sign_fix(R2, Q2, opts.get("diag_sign"))
                            # rebuild R by Q2^T * A
                            R_calc = _dot(_transpose(Q2), mat)
                            Q_calc = Q2
                            orth_err = _orthogonality_error(Q_calc)
                            recon_err = _reconstruction_error(mat, Q_calc, R_calc)
                            lower_max = _lower_triangle_max(R_calc)
                            rank = _estimate_rank(R_calc, rank_tol)
                        # sanitize R upper
                        R_calc = _upper_triangularize(R_calc, lower_tol)
                        state_mat = copy.deepcopy(mat)
                        state_Q = Q_calc
                        state_R = R_calc
                        checkpoint = {"mat": copy.deepcopy(state_mat), "Q": copy.deepcopy(state_Q), "R": copy.deepcopy(state_R)}
                        Q_use = state_Q
                        R_use = state_R
                        metrics = {"orth_error_2": orth_err, "recon_rel_fro": recon_err, "lower_triangle_max": lower_max, "rank_estimate": rank}
                    else:
                        # partial update: for simplicity perform full refactor from recompute_from to end by slicing columns
                        # but keep reused prefix columns from state
                        if state_mat is None:
                            start = 0
                        else:
                            start = recompute_from if recompute_from is not None else n
                        reused_prefix_cols = start
                        # build matrix to factor: take full mat but try to reuse
                        # For determinism and robustness, we'll refactor entire matrix if reused_prefix_cols < n
                        if reused_prefix_cols < n:
                            full_refactor = True
                            reason = "partial_refresh"
                            Q_calc, R_calc = _householder_qr(mat)
                            Q_calc, R_calc = _sign_fix(R_calc, Q_calc, opts.get("diag_sign"))
                            orth_err = _orthogonality_error(Q_calc)
                            recon_err = _reconstruction_error(mat, Q_calc, R_calc)
                            lower_max = _lower_triangle_max(R_calc)
                            rank = _estimate_rank(R_calc, rank_tol)
                            if orth_err > reorth_epsilon:
                                flags["reorthogonalized"] = True
                                Q2, R2 = _householder_qr(Q_calc)
                                Q2, R2 = _sign_fix(R2, Q2, opts.get("diag_sign"))
                                R_calc = _dot(_transpose(Q2), mat)
                                Q_calc = Q2
                                orth_err = _orthogonality_error(Q_calc)
                                recon_err = _reconstruction_error(mat, Q_calc, R_calc)
                                lower_max = _lower_triangle_max(R_calc)
                                rank = _estimate_rank(R_calc, rank_tol)
                            R_calc = _upper_triangularize(R_calc, lower_tol)
                            state_mat = copy.deepcopy(mat)
                            state_Q = Q_calc
                            state_R = R_calc
                            checkpoint = {"mat": copy.deepcopy(state_mat), "Q": copy.deepcopy(state_Q), "R": copy.deepcopy(state_R)}
                            Q_use = state_Q
                            R_use = state_R
                            metrics = {"orth_error_2": orth_err, "recon_rel_fro": recon_err, "lower_triangle_max": lower_max, "rank_estimate": rank}
                        else:
                            # nothing changed
                            full_refactor = False
                            reason = "normal"
                            Q_use = state_Q
                            R_use = state_R
                            metrics = {"orth_error_2": _orthogonality_error(Q_use), "recon_rel_fro": _reconstruction_error(mat, Q_use, R_use), "lower_triangle_max": _lower_triangle_max(R_use), "rank_estimate": _estimate_rank(R_use, rank_tol)}
                # finalize outputs
                sign_convention_ok = True
                Q_out = _round_matrix(Q_use, round_dp) if Q_use else []
                R_out = _round_matrix(R_use, round_dp) if R_use else []
                record["dirty_ranges_in"] = dirty_ranges_in
                record["recompute_from"] = recompute_from
                record["reused_prefix_cols"] = reused_prefix_cols
                record["full_refactor"] = full_refactor
                record["reason"] = reason
                record["sign_convention_ok"] = sign_convention_ok
                record["metrics"] = {k:(round(v, round_dp) if isinstance(v,float) else v) for k,v in metrics.items()}
                record["Q"] = Q_out
                record["R"] = R_out
            else:
                # unknown op - ignore
                record["shape"] = [len(state_mat), len(state_mat[0])] if state_mat else [0,0]
                record["dirty_ranges_in"] = []
                record["recompute_from"] = None
                record["reused_prefix_cols"] = 0
                record["full_refactor"] = False
                record["reason"] = "noop"
                record["sign_convention_ok"] = True
                record["metrics"] = metrics
                record["Q"] = []
                record["R"] = []
        except Exception as e:
            # rollback to checkpoint
            state_mat = checkpoint["mat"]
            state_Q = checkpoint["Q"]
            state_R = checkpoint["R"]
            flags["rollback"] = True
            flags["checkpoint_used"] = True
            record["shape"] = [len(state_mat), len(state_mat[0])] if state_mat else [0,0]
            record["dirty_ranges_in"] = []
            record["recompute_from"] = None
            record["reused_prefix_cols"] = 0
            record["full_refactor"] = False
            record["reason"] = "rollback_on_exception"
            record["sign_convention_ok"] = True
            record["metrics"] = {"orth_error_2": 0.0, "recon_rel_fro": 0.0, "lower_triangle_max": 0.0, "rank_estimate": 0}
            record["Q"] = _round_matrix(state_Q, round_dp) if state_Q else []
            record["R"] = _round_matrix(state_R, round_dp) if state_R else []
        # finalize flags
        record["flags"] = flags
        # ensure presence of keys
        if "shape" not in record:
            if state_mat:
                record["shape"] = [len(state_mat), len(state_mat[0])]
            else:
                record["shape"] = [0,0]
        # For steps that weren't set_matrix, ensure fields
        if "dirty_ranges_in" not in record:
            record["dirty_ranges_in"] = dirty_ranges_in
        if "recompute_from" not in record:
            record["recompute_from"] = recompute_from
        if "reused_prefix_cols" not in record: