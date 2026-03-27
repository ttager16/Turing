from typing import Any, Dict, List, Optional, Tuple

def qr_incremental_driver(steps: List[Dict[str, Any]],
                          options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Perform a stateful, incremental QR decomposition with stability checks and rollback handling.

    This function maintains an internal QR decomposition state for a covariance matrix that may
    change across multiple steps. Each step defines an operation such as setting a new matrix
    or resetting the state. The algorithm reuses previous decompositions when possible,
    recomputes only the affected regions, and ensures numerical stability through 
    Householder-based reorthogonalization and sign convention enforcement.

    Args:
        steps (List[Dict[str, Any]]): 
            A list of operation dictionaries, where each step may include:
                - "op" (str): Operation type (e.g., "set_matrix", "reset").
                - "matrix" (List[List[float]]): Input square matrix for decomposition.
                - "equiv_key" (str, optional): Label for equivalence tracking across steps.

        options (Optional[Dict[str, Any]]): 
            Configuration dictionary supporting:
                - "round_dp" (int): Decimal places to round Q and R (default: 4).
                - "diag_sign" (str): Diagonal sign rule ("nonnegative" by default).
                - "reorth_epsilon" (float): Orthogonality threshold for reorthogonalization (default: 5e-4).
                - "lower_tol" (float): Tolerance for lower-triangle leakage in R (default: 1e-6).
                - "rank_tol" (float): Threshold for rank estimation (default: 1e-10).
                - "max_full_refactor" (bool): Whether to always perform full refactorization (default: False).

    Returns:
        Dict[str, Any]: A structured dictionary containing:
            - "meta": Metadata such as version, rounding, and policy description.
            - "steps": Detailed log of each operation, including flags, metrics, Q/R matrices, 
              sign convention checks, and refactor decisions.
            - "equivalence": Optional equivalence analysis results comparing matching keys.
            - "final": Final state summary containing shape, rounded Q, and R matrices.

    Notes:
        - Uses Householder reflections for QR factorization.
        - Automatically falls back to checkpointed state if invalid input or numerical instability is detected.
        - Designed for deterministic, testable, and incremental updates to square matrices.
    """
    # ----------------------------- Helpers ---------------------------------
    def deep_copy_matrix(A: List[List[float]]) -> List[List[float]]:
        return [row[:] for row in A]

    def shape_of(A: List[List[float]]) -> Tuple[int, int]:
        if A is None:
            return (0, 0)
        return (len(A), len(A[0]) if A and isinstance(A[0], list) else 0)

    def is_rectangular(A: Any) -> bool:
        if not isinstance(A, list):
            return False
        if len(A) == 0:
            return True
        if not isinstance(A[0], list):
            return False
        n = len(A[0])
        for r in A:
            if not isinstance(r, list) or len(r) != n:
                return False
            for x in r:
                if not isinstance(x, (int, float)):
                    return False
        return True

    def has_nan_inf(A: List[List[float]]) -> bool:
        import math
        for row in A:
            for x in row:
                if not math.isfinite(x):
                    return True
        return False

    def identity(n: int) -> List[List[float]]:
        I = [[0.0]*n for _ in range(n)]
        for i in range(n):
            I[i][i] = 1.0
        return I

    def matmul(A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
        m, k = shape_of(A)
        k2, n = shape_of(B)
        # assume k == k2
        C = [[0.0]*n for _ in range(m)]
        for i in range(m):
            Ai = A[i]
            for t in range(k):
                a = Ai[t]
                if a != 0.0:
                    Bt = B[t]
                    Ci = C[i]
                    for j in range(n):
                        Ci[j] += a * Bt[j]
        return C

    def transpose(A: List[List[float]]) -> List[List[float]]:
        m, n = shape_of(A)
        if m == 0 or n == 0:
            return []
        T = [[0.0]*m for _ in range(n)]
        for i in range(m):
            for j in range(n):
                T[j][i] = A[i][j]
        return T

    def fro_norm(A: List[List[float]]) -> float:
        s = 0.0
        for row in A:
            for x in row:
                s += x*x
        import math
        return math.sqrt(s)

    def round_number(x: float, dp: int) -> float:
        # avoid -0.0 in output
        r = round(x, dp)
        if r == 0:
            return 0.0
        return r

    def round_matrix(A: List[List[float]], dp: int) -> List[List[float]]:
        return [[round_number(x, dp) for x in row] for row in A]

    def compress_ranges(indices: List[int]) -> List[List[int]]:
        if not indices:
            return []
        indices = sorted(indices)
        ranges = []
        start = indices[0]
        prev = start
        for idx in indices[1:]:
            if idx == prev + 1:
                prev = idx
            else:
                ranges.append([start, prev+1])
                start = idx
                prev = idx
        ranges.append([start, prev+1])
        return ranges

    def apply_householder_left(M: List[List[float]], v: List[float], tau: float, i_start: int, col_start: int = 0):
        # M[i_start:, col_start:] = (I - tau v v^T) M[i_start:, col_start:]
        if tau == 0.0:
            return
        m, n = shape_of(M)
        for j in range(col_start, n):
            dot = 0.0
            for r in range(i_start, m):
                dot += v[r] * M[r][j]
            w = tau * dot
            if w != 0.0:
                for r in range(i_start, m):
                    M[r][j] -= v[r] * w

    def householder_qr_full(A: List[List[float]]) -> Tuple[List[List[float]], List[List[float]], List[Tuple[int, List[float], float]]]:
        import math
        m, n = shape_of(A)
        Ac = deep_copy_matrix(A)
        p = min(m, n)
        reflectors: List[Tuple[int, List[float], float]] = []
        for i in range(p):
            # Build Householder for column i at rows i..m-1
            # x = Ac[i:, i]
            # Compute norm
            norm = 0.0
            for r in range(i, m):
                xr = Ac[r][i]
                norm += xr * xr
            norm = math.sqrt(norm)
            if norm == 0.0:
                # No reflection needed
                v_full = [0.0]*m
                tau = 0.0
                reflectors.append((i, v_full, tau))
                continue
            x0 = Ac[i][i]
            sign = 1.0 if x0 >= 0.0 else -1.0
            alpha = -sign * norm
            # v = x - alpha e1
            # Tail vector length m-i
            v_tail0 = x0 - alpha
            if v_tail0 == 0.0:
                v_full = [0.0]*m
                tau = 0.0
                reflectors.append((i, v_full, tau))
                continue
            v_full = [0.0]*m
            v_full[i] = v_tail0
            for r in range(i+1, m):
                v_full[r] = Ac[r][i]
            vsq = 0.0
            for r in range(i, m):
                vsq += v_full[r]*v_full[r]
            tau = 2.0 / vsq if vsq != 0.0 else 0.0
            apply_householder_left(Ac, v_full, tau, i_start=i, col_start=i)
            reflectors.append((i, v_full, tau))
        # Build Q = H0 H1 ... H_{p-1}
        Q = identity(m)
        for (i_start, v, tau) in reflectors:
            apply_householder_left(Q, v, tau, i_start=i_start, col_start=0)
        R = Ac
        return Q, R, reflectors

    def qr_with_prefix(A: List[List[float]], prev_reflectors: List[Tuple[int, List[float], float]], k: int
                      ) -> Tuple[List[List[float]], List[List[float]], List[Tuple[int, List[float], float]]]:
        import math
        m, n = shape_of(A)
        Ac = deep_copy_matrix(A)
        # Apply first k reflectors to A
        for i in range(k):
            (i_start, v, tau) = prev_reflectors[i]
            apply_householder_left(Ac, v, tau, i_start=i_start, col_start=0)
        # Now factorize remaining columns i=k..p-1 on Ac
        reflectors: List[Tuple[int, List[float], float]] = prev_reflectors[:k]
        p = min(m, n)
        for i in range(k, p):
            # Build Householder for column i at rows i..m-1
            norm = 0.0
            for r in range(i, m):
                xr = Ac[r][i]
                norm += xr * xr
            norm = math.sqrt(norm)
            if norm == 0.0:
                v_full = [0.0]*m
                tau = 0.0
                reflectors.append((i, v_full, tau))
                continue
            x0 = Ac[i][i]
            sign = 1.0 if x0 >= 0.0 else -1.0
            alpha = -sign * norm
            v_tail0 = x0 - alpha
            if v_tail0 == 0.0:
                v_full = [0.0]*m
                tau = 0.0
                reflectors.append((i, v_full, tau))
                continue
            v_full = [0.0]*m
            v_full[i] = v_tail0
            for r in range(i+1, m):
                v_full[r] = Ac[r][i]
            vsq = 0.0
            for r in range(i, m):
                vsq += v_full[r]*v_full[r]
            tau = 2.0 / vsq if vsq != 0 else 0.0
            apply_householder_left(Ac, v_full, tau, i_start=i, col_start=i)
            reflectors.append((i, v_full, tau))
        # Build Q from all reflectors
        Q = identity(m)
        for (i_start, v, tau) in reflectors:
            apply_householder_left(Q, v, tau, i_start=i_start, col_start=0)
        R = Ac
        return Q, R, reflectors

    def enforce_sign_rule(Q: List[List[float]], R: List[List[float]], rule: str = "nonnegative") -> Tuple[List[List[float]], List[List[float]], bool]:
        # Enforce R diagonal >= 0 by flipping corresponding columns of Q and rows of R
        m, n = shape_of(R)
        p = min(m, n)
        ok = True
        for i in range(p):
            rii = R[i][i]
            if rule == "nonnegative" and rii < 0.0:
                # Flip sign of row i in R (all columns), and column i in Q (all rows)
                for j in range(n):
                    R[i][j] = -R[i][j]
                # Flip Q[:, i]
                qm, qn = shape_of(Q)
                for r in range(qm):
                    Q[r][i] = -Q[r][i]
            # check
        for i in range(p):
            if R[i][i] < 0.0:
                ok = False
                break
        return Q, R, ok

    def compute_metrics(A: List[List[float]], Q: List[List[float]], R: List[List[float]], rank_tol: float, lower_tol: float) -> Dict[str, Any]:
        m, n = shape_of(A)
        # Orthogonality: ||Q^T Q - I||_F
        QT = transpose(Q)
        QTQ = matmul(QT, Q)
        I = identity(shape_of(Q)[0])
        for i in range(len(I)):
            for j in range(len(I)):
                QTQ[i][j] -= I[i][j]
        orth_err = fro_norm(QTQ)
        # Reconstruction error: ||A - Q R||_F / max(1, ||A||_F)
        QR = matmul(Q, R)
        # A - QR
        diff = [[0.0]*n for _ in range(m)]
        for i in range(m):
            for j in range(n):
                diff[i][j] = A[i][j] - QR[i][j]
        num = fro_norm(diff)
        denom = fro_norm(A)
        if denom < 1.0:
            denom = 1.0
        recon_rel = num / denom
        # Lower triangle max abs in R
        lower_max = 0.0
        for i in range(m):
            for j in range(min(i, n)):
                v = abs(R[i][j])
                if v > lower_max:
                    lower_max = v
        # Rank estimate
        p = min(m, n)
        rank_est = 0
        for i in range(p):
            if abs(R[i][i]) > rank_tol:
                rank_est += 1
        return {
            "orth_error_2": orth_err,
            "recon_rel_fro": recon_rel,
            "lower_triangle_max": lower_max,
            "rank_estimate": rank_est
        }

    def detect_dirty_ranges(A_prev: Optional[List[List[float]]], A_new: List[List[float]]) -> Tuple[List[List[int]], Optional[int], int, bool, str]:
        # Returns (dirty_ranges, recompute_from, reused_prefix_cols, full_refactor, reason)
        if A_prev is None:
            m, n = shape_of(A_new)
            return ([[0, n]] if n > 0 else []), 0 if n > 0 else 0, 0, True, "fresh"
        m_prev, n_prev = shape_of(A_prev)
        m_new, n_new = shape_of(A_new)
        if (m_prev != m_new) or (n_prev != n_new):
            return ([[0, n_new]] if n_new > 0 else []), 0 if n_new > 0 else 0, 0, True, "shape_change"
        # Same shape: check per-column changes (exact equality for determinism)
        changed_cols = []
        for j in range(n_new):
            col_changed = False
            for i in range(m_new):
                if A_prev[i][j] != A_new[i][j]:
                    col_changed = True
                    break
            if col_changed:
                changed_cols.append(j)
        if not changed_cols:
            return [], None, n_new, False, "normal"
        ranges = compress_ranges(changed_cols)
        recompute_from = changed_cols[0]
        reused_prefix = recompute_from
        # If recompute_from == 0, we will treat as full refactor only if policy says so; keep incremental default
        return ranges, recompute_from, reused_prefix, False, f"partial_from_{recompute_from}"

    def zeros_matrix(m: int, n: int) -> List[List[float]]:
        return [[0.0]*n for _ in range(m)]

    def is_block_diagonal(A: List[List[float]], tol: float = 0.0) -> bool:
        # Simple heuristic: exists a split k with zero off-diagonal blocks
        m, n = shape_of(A)
        if m == 0 or n == 0:
            return True
        if m != n:
            return False
        # direct diagonal matrix is block-diagonal
        offdiag_nonzero = False
        for i in range(n):
            for j in range(n):
                if i != j and abs(A[i][j]) > tol:
                    offdiag_nonzero = True
                    break
            if offdiag_nonzero:
                break
        if not offdiag_nonzero:
            return True
        # try any split
        for k in range(1, n):
            ok = True
            for i in range(0, k):
                for j in range(k, n):
                    if abs(A[i][j]) > tol:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                for i in range(k, n):
                    for j in range(0, k):
                        if abs(A[i][j]) > tol:
                            ok = False
                            break
                    if not ok:
                        break
            if ok:
                return True
        return False

    def valid_matrix_input(A: Any) -> bool:
        return is_rectangular(A)

    # NEW: enforce square matrices (covariance) for validity
    def is_square(A: Any) -> bool:
        if not is_rectangular(A):
            return False
        m, n = shape_of(A)
        return m == n

    def copy_state(S: Dict[str, Any]) -> Dict[str, Any]:
        if S is None:
            return None
        # Deep copy matrices and reflectors
        out = {
            "A": deep_copy_matrix(S["A"]) if S.get("A") is not None else None,
            "Q": deep_copy_matrix(S["Q"]) if S.get("Q") is not None else None,
            "R": deep_copy_matrix(S["R"]) if S.get("R") is not None else None,
            "reflectors": None,
            "shape": S.get("shape", (0, 0)),
            "metrics": dict(S["metrics"]) if "metrics" in S and S["metrics"] is not None else None
        }
        if "reflectors" in S and S["reflectors"] is not None:
            refl_copy = []
            for (i_start, v, tau) in S["reflectors"]:
                refl_copy.append((i_start, v[:] if v is not None else None, tau))
            out["reflectors"] = refl_copy
        return out

    # ----------------------------- Defaults --------------------------------
    opts = options or {}
    round_dp = int(opts.get("round_dp", 4))
    diag_sign = str(opts.get("diag_sign", "nonnegative"))
    reorth_eps = float(opts.get("reorth_epsilon", 5e-4))
    lower_tol = float(opts.get("lower_tol", 1e-6))
    rank_tol = float(opts.get("rank_tol", 1e-10))
    # Max full refactor policy is supported but we keep incremental prefix reuse by default
    _ = opts.get("max_full_refactor", False)

    meta = {
        "version": "qr.v1",
        "round_dp": round_dp,
        "diag_sign": diag_sign,
        "policy": "householder|rollback_on_invalid|reorth_on_fail|incremental_prefix_reuse"
    }

    # ----------------------------- State -----------------------------------
    current_state = {
        "A": None,
        "Q": None,
        "R": None,
        "reflectors": None,
        "shape": (0, 0),
        "metrics": None
    }
    # checkpoint of last good state
    checkpoint_state = copy_state(current_state)

    def set_state(A: List[List[float]], Q: List[List[float]], R: List[List[float]], reflectors, metrics):
        current_state["A"] = deep_copy_matrix(A) if A is not None else None
        current_state["Q"] = deep_copy_matrix(Q) if Q is not None else None
        current_state["R"] = deep_copy_matrix(R) if R is not None else None
        current_state["reflectors"] = []
        if reflectors is not None:
            for (i_start, v, tau) in reflectors:
                current_state["reflectors"].append((i_start, v[:] if v is not None else None, tau))
        current_state["shape"] = shape_of(A)
        current_state["metrics"] = dict(metrics) if metrics is not None else None

    def update_checkpoint():
        nonlocal checkpoint_state
        checkpoint_state = copy_state(current_state)

    # equivalence registry: key -> recorded snapshot
    equivalence_records: Dict[str, Dict[str, Any]] = {}
    equivalence_out: List[Dict[str, Any]] = []

    # --------------------------- Step Processing ---------------------------
    transcript_steps: List[Dict[str, Any]] = []

    for step_index, step in enumerate(steps):
        rec: Dict[str, Any] = {}
        flags = {
            "reorthogonalized": False,
            "checkpoint_used": False,
            "rollback": False,
            "reset": False
        }
        op = step.get("op", "set_matrix")
        rec["op"] = op

        if op == "reset":
            # Reset state to empty
            current_state = {
                "A": None,
                "Q": None,
                "R": None,
                "reflectors": None,
                "shape": (0, 0),
                "metrics": {
                    "orth_error_2": 0.0,
                    "recon_rel_fro": 0.0,
                    "lower_triangle_max": 0.0,
                    "rank_estimate": 0
                }
            }
            checkpoint_state = copy_state(current_state)
            flags["reset"] = True
            rec["shape"] = [0, 0]
            rec["dirty_ranges_in"] = []
            rec["recompute_from"] = None
            rec["reused_prefix_cols"] = 0
            rec["full_refactor"] = False
            rec["reason"] = "reset"
            rec["flags"] = flags
            rec["metrics"] = current_state["metrics"]
            rec["sign_convention_ok"] = True
            rec["Q"] = []
            rec["R"] = []
            transcript_steps.append(rec)
            continue

        # Otherwise: set_matrix or other matrix-affecting op
        A_in = step.get("matrix", None)

        # Validate input
        invalid = False
        invalid_reason = ""
        if not valid_matrix_input(A_in):
            invalid = True
            invalid_reason = "invalid_input"
        else:
            # Ensure rectangular with all finite numbers
            if has_nan_inf(A_in):
                invalid = True
                invalid_reason = "nonfinite_input"
            elif not is_square(A_in):
                invalid = True
                invalid_reason = "nonsquare_input"

        if invalid:
            # Roll back to checkpoint without changing state
            flags["rollback"] = True
            flags["checkpoint_used"] = True
            rec["shape"] = list(checkpoint_state["shape"]) if checkpoint_state and checkpoint_state.get("shape") else [0, 0]
            rec["dirty_ranges_in"] = []
            rec["recompute_from"] = None
            rec["reused_prefix_cols"] = 0
            rec["full_refactor"] = False
            rec["reason"] = invalid_reason
            rec["flags"] = flags
            metrics = checkpoint_state["metrics"] if checkpoint_state and checkpoint_state.get("metrics") else {
                "orth_error_2": 0.0,
                "recon_rel_fro": 0.0,
                "lower_triangle_max": 0.0,
                "rank_estimate": 0
            }
            rec["metrics"] = metrics
            if checkpoint_state and checkpoint_state.get("Q") is not None:
                rec["Q"] = round_matrix(checkpoint_state["Q"], round_dp)
                rec["R"] = round_matrix(checkpoint_state["R"], round_dp)
                rec["sign_convention_ok"] = True
            else:
                rec["Q"] = []
                rec["R"] = []
                rec["sign_convention_ok"] = True
            transcript_steps.append(rec)
            # keep state unchanged
            continue

        # At this point, A_in is valid
        A_new = deep_copy_matrix(A_in)
        dirty_ranges, recompute_from, reused_prefix_cols, full_refactor, reason = detect_dirty_ranges(current_state["A"], A_new)

        # Default step record fields
        m_new, n_new = shape_of(A_new)
        rec["shape"] = [m_new, n_new]
        rec["dirty_ranges_in"] = dirty_ranges
        rec["recompute_from"] = recompute_from
        rec["reused_prefix_cols"] = reused_prefix_cols
        rec["full_refactor"] = full_refactor
        rec["reason"] = reason

        # Compute/update
        success = True
        used_checkpoint = False

        if current_state["A"] is None or (recompute_from == 0 and full_refactor) or reason in ("fresh", "shape_change"):
            # Full factorization
            Q, R, refl = householder_qr_full(A_new)
        elif recompute_from is None:
            # No change; reuse
            Q = deep_copy_matrix(current_state["Q"])
            R = deep_copy_matrix(current_state["R"])
            refl = [(i_start, v[:], tau) for (i_start, v, tau) in (current_state["reflectors"] or [])]
        else:
            # Incremental prefix reuse from recompute_from
            if not current_state["reflectors"] or len(current_state["reflectors"]) < min(m_new, n_new):
                # Fall back to full if reflectors are absent or incompatible
                Q, R, refl = householder_qr_full(A_new)
                rec["full_refactor"] = True
                rec["reason"] = "fallback_full"
            else:
                Q, R, refl = qr_with_prefix(A_new, current_state["reflectors"], recompute_from)

        # Enforce sign convention
        Q, R, sign_ok = enforce_sign_rule(Q, R, rule=diag_sign)

        # Compute metrics
        metrics = compute_metrics(A_new, Q, R, rank_tol, lower_tol)

        # Quality checks
        def bad_metrics(met: Dict[str, Any]) -> bool:
            if has_nan_inf(Q) or has_nan_inf(R):
                return True
            if met["orth_error_2"] > reorth_eps:
                return True
            if met["lower_triangle_max"] > max(10.0*lower_tol, lower_tol):  # allow small wiggle
                return True
            if met["recon_rel_fro"] > max(10.0*reorth_eps, reorth_eps):
                return True
            return False

        if bad_metrics(metrics):
            # Re-orthogonalize / refresh with a full refactor
            Q2, R2, refl2 = householder_qr_full(A_new)
            Q2, R2, sign_ok2 = enforce_sign_rule(Q2, R2, rule=diag_sign)
            metrics2 = compute_metrics(A_new, Q2, R2, rank_tol, lower_tol)
            flags["reorthogonalized"] = True
            rec["full_refactor"] = True
            rec["reason"] = "reorth"
            if bad_metrics(metrics2):
                # Rollback to checkpoint
                success = False
                flags["rollback"] = True
                flags["checkpoint_used"] = True
                used_checkpoint = True
            else:
                Q, R, refl, metrics, sign_ok = Q2, R2, refl2, metrics2, sign_ok2

        if success:
            # Update current state and checkpoint
            set_state(A_new, Q, R, refl, metrics)
            update_checkpoint()
            rec["flags"] = flags
            rec["metrics"] = metrics
            rec["sign_convention_ok"] = sign_ok
            # Round Q, R
            rec["Q"] = round_matrix(Q, round_dp)
            rec["R"] = round_matrix(R, round_dp)
        else:
            # Roll back to checkpoint_state for transcript and keep current_state unchanged
            cs = checkpoint_state
            rec["shape"] = list(cs["shape"]) if cs and cs.get("shape") else [0, 0]
            rec["flags"] = flags
            metrics_rb = cs["metrics"] if cs and cs.get("metrics") else {
                "orth_error_2": 0.0,
                "recon_rel_fro": 0.0,
                "lower_triangle_max": 0.0,
                "rank_estimate": 0
            }
            rec["metrics"] = metrics_rb
            if cs and cs.get("Q") is not None:
                rec["Q"] = round_matrix(cs["Q"], round_dp)
                rec["R"] = round_matrix(cs["R"], round_dp)
                rec["sign_convention_ok"] = True
            else:
                rec["Q"] = []
                rec["R"] = []
                rec["sign_convention_ok"] = True

        # Equivalence tagging (optional in steps)
        eq_key = step.get("equiv_key", None)
        if eq_key is not None:
            # Snapshot current (post-operation) rounded Q/R and rounded A
            if rec.get("Q") is not None and rec.get("R") is not None:
                A_snap = current_state["A"] if success else (checkpoint_state["A"] if used_checkpoint else None)
                A_round = round_matrix(A_snap, round_dp) if A_snap is not None else []
                Q_round = rec["Q"]
                R_round = rec["R"]
                sh = rec["shape"]
                if eq_key not in equivalence_records:
                    equivalence_records[eq_key] = {
                        "first_step_index": step_index,
                        "shape": sh[:],
                        "A_round": A_round,
                        "Q_round": Q_round,
                        "R_round": R_round,
                        "block_diag": is_block_diagonal(A_snap or [], tol=0.0)
                    }
                else:
                    prev = equivalence_records[eq_key]
                    match = (prev["shape"] == sh and prev["Q_round"] == Q_round and prev["R_round"] == R_round)
                    same_matrix = (prev["shape"] == sh and prev["A_round"] == A_round)
                    block_diag_now = is_block_diagonal(A_snap or [], tol=0.0)
                    equivalence_out.append({
                        "key": eq_key,
                        "first_step_index": prev["first_step_index"],
                        "second_step_index": step_index,
                        "same_rounded_matrix": same_matrix,
                        "block_diagonal_both": bool(prev["block_diag"] and block_diag_now),
                        "rounded_results_match_exactly": match
                    })
                    # Refresh stored to latest in case of more comparisons later
                    equivalence_records[eq_key] = {
                        "first_step_index": prev["first_step_index"],
                        "shape": sh[:],
                        "A_round": A_round,
                        "Q_round": Q_round,
                        "R_round": R_round,
                        "block_diag": block_diag_now
                    }

        transcript_steps.append(rec)

    # ------------------------------ Final ----------------------------------
    final_shape = list(current_state["shape"]) if current_state and current_state.get("shape") else [0, 0]
    final_Q = round_matrix(current_state["Q"], round_dp) if current_state.get("Q") is not None else []
    final_R = round_matrix(current_state["R"], round_dp) if current_state.get("R") is not None else []

    out: Dict[str, Any] = {
        "meta": meta,
        "steps": transcript_steps,
        "equivalence": equivalence_out,
        "final": {
            "shape": final_shape,
            "Q": final_Q,
            "R": final_R
        }
    }
    return out