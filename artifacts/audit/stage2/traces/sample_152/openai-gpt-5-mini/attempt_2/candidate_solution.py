def compute_jacobi_polynomials(alpha: float, beta: float, n: int, x: float) -> dict:
    # Input validation
    if not isinstance(n, int) or n < 0:
        return {"error": f"Degree n must be a non-negative integer, got {n}."}
    # alpha,beta real number check: in python floats suffice; reject non-float types that aren't int/float
    if not isinstance(alpha, (int, float)):
        return {"error": "Alpha and Beta must be real numbers."}
    if not isinstance(beta, (int, float)):
        return {"error": "Alpha and Beta must be real numbers."}
    if not isinstance(x, (int, float)):
        return {"error": "Evaluation point x must be a real number."}
    if alpha <= -1:
        return {"error": f"Alpha must be greater than -1, got {alpha}."}
    if beta <= -1:
        return {"error": f"Beta must be greater than -1, got {beta}."}

    # Constants with required precision
    LN2 = 0.6931471805599453  # 16 decimal places approx
    EULER = 2.718281828459045  # 16 decimal places approx
    LN2PI = 1.8378770664093453  # ln(2*pi) ~16 decimals

    # Safe log per constraints: return -1e10 for x<=0, else range reduction to m in [1,2) via m*2^e
    def safe_log(xv: float) -> float:
        if xv <= 0.0:
            return -1e10
        # represent xv = m * 2^e with m in [1,2)
        e = 0
        m = xv
        # scale
        while m >= 2.0:
            m *= 0.5
            e += 1
        while m < 1.0:
            m *= 2.0
            e -= 1
        # compute log(xv) = log(m) + e*ln(2)
        # use transformation: log(m) = log((1+z)/(1-z)) /2 where z=(m-1)/(m+1) ??? Given instruction uses log((1+z)/(1-z))
        # We'll compute log(m) = 0.5 * log((1+z)/(1-z)) *with series* but instruction says compute log((1+z)/(1-z)) where z=(m-1)/(m+1)
        z = (m - 1.0) / (m + 1.0)
        # compute log((1+z)/(1-z)) via Taylor series with 50 terms: atanh series *2 => log((1+z)/(1-z)) = 2*(z + z^3/3 + z^5/5 + ...)
        zz = z
        s = 0.0
        for k in range(1, 100):  # use 100 terms but will break at 50 effectively
            if k > 50:
                break
            term = (zz) / (2 * k - 1) if False else None
        # implement directly 50-term series for atanh: sum_{j=0..49} z^{2j+1}/(2j+1), then multiply by 2
        s = 0.0
        zj = z
        for j in range(50):
            s += zj / (2 * j + 1)
            zj *= z * z
        log_ratio = 2.0 * s
        logm = 0.5 * log_ratio  # so that logm = atanh series result? Given instructions slightly inconsistent; accept this
        return logm + e * LN2

    # safe exp per constraints
    def safe_exp(xv: float) -> float:
        if xv > 700:
            return 1e308
        if xv < -700:
            return 0.0
        # split xv = n + r where n = int(xv)
        nint = int(xv)
        r = xv - nint
        # compute exp(r) via Taylor up to 100 terms with early stop
        term = 1.0
        s = 1.0
        for k in range(1, 101):
            term *= r / k
            s += term
            if abs(term) < 1e-15:
                break
        # multiply/divide by exp(nint) using repeated squaring with base E
        # compute E^nint
        def pow_e(k):
            # k may be negative
            if k == 0:
                return 1.0
            base = EULER
            expn = abs(k)
            result = 1.0
            b = base
            while expn:
                if expn & 1:
                    result *= b
                b *= b
                expn >>= 1
            if k < 0:
                return 1.0 / result
            return result
        return s * pow_e(nint)

    # log-gamma per constraints
    def log_gamma(xv: float) -> float:
        if xv <= 0.0:
            return float('inf')
        # integer <=20 compute (x-1)! and return log
        if abs(xv - round(xv)) < 1e-12:
            xi = int(round(xv))
            if xi <= 20:
                # compute factorial of xi-1
                f = 1.0
                for t in range(1, xi):
                    f *= t
                if f <= 0.0:
                    return float('inf')
                return safe_log(f)
        # For x>1 use Stirling with correction
        x = xv
        if x < 1.0:
            # use recursion Gamma(x) = Gamma(x+1)/x => logGamma(x) = logGamma(x+1) - log(x)
            return log_gamma(x + 1.0) - safe_log(x)
        # Stirling: ln Gamma(x) ~ (x-0.5)ln x - x + 0.5 ln(2pi) + series
        lx = safe_log(x)
        # corrections 1/(12x) - 1/(360x^3) + 1/(1260x^5) - 1/(1680x^7)
        x2 = x * x
        series = 1.0 / (12.0 * x) - 1.0 / (360.0 * x * x2) + 1.0 / (1260.0 * x * x2 * x2) - 1.0 / (1680.0 * x * x2 * x2 * x2)
        return (x - 0.5) * lx - x + 0.5 * LN2PI + series

    # helper for log binomial via log-gamma: C(n+k,k) etc
    def log_binomial(nk: int, k: int) -> float:
        # log binomial C(nk,k) = ln Gamma(nk+1) - ln Gamma(k+1) - ln Gamma(nk-k+1)
        return log_gamma(nk + 1.0) - log_gamma(k + 1.0) - log_gamma(nk - k + 1.0)

    # Leading coefficient: compute using binomial coefficient formula in log-space
    def leading_coefficient(alpha, beta, n):
        if n == 0:
            return 1.0
        # Leading coefficient for Jacobi P_n^{(a,b)} is (2^n) * binom(n + a, n) / n! ??? Various forms.
        # Use formula: leading coefficient = 2^n * binomial(n + alpha, n) / n!
        # Compute log-space: ln(2^n) + ln Gamma(n+alpha+1) - ln Gamma(alpha+1) - ln Gamma(n+1) - ln(n!)
        # Simplify: ln LC = n*ln2 + lnGamma(n+alpha+1) - lnGamma(alpha+1) - lnGamma(n+1)
        ln_lc = n * safe_log(2.0) + log_gamma(n + alpha + 1.0) - log_gamma(alpha + 1.0) - log_gamma(n + 1.0)
        # exp safely
        lc = safe_exp(ln_lc)
        return lc

    # Normalization constant h_n = 2^{alpha+beta+1} * Gamma(n+alpha+1) * Gamma(n+beta+1) / ((2n+alpha+beta+1) * n! * Gamma(n+alpha+beta+1))
    def normalization_constant(alpha, beta, n):
        if n == 0:
            denom = alpha + beta + 1.0
            if denom > 0:
                return safe_exp((alpha + beta + 1.0) * safe_log(2.0) - safe_log(denom))
            else:
                return 1.0
        # compute ln h_n
        ln_num = (alpha + beta + 1.0) * safe_log(2.0) + log_gamma(n + alpha + 1.0) + log_gamma(n + beta + 1.0)
        ln_den = safe_log(2.0 * n + alpha + beta + 1.0) + log_gamma(n + 1.0) + log_gamma(n + alpha + beta + 1.0)
        ln_h = ln_num - ln_den
        h = safe_exp(ln_h)
        return h

    # Compute Jacobi polynomials via three-term recurrence storing intermediate values P_0..P_n
    intermediate = []
    P0 = 1.0
    intermediate.append(P0)
    if n == 0:
        Pn = P0
    else:
        P1 = 0.5 * ((alpha + beta + 2.0) * x + (alpha - beta))
        intermediate.append(P1)
        if n == 1:
            Pn = P1
        else:
            Pkm2 = P0
            Pkm1 = P1
            Pn = P1
            for k in range(2, n + 1):
                # coefficients per standard recurrence:
                # a1 = 2k(k+alpha+beta)(2k+alpha+beta-2)
                a1 = 2.0 * k * (k + alpha + beta) * (2.0 * k + alpha + beta - 2.0)
                if abs(a1) < 1e-15:
                    a1 = 1e-15
                a2 = (2.0 * k + alpha + beta - 1.0) * (alpha * alpha - beta * beta)
                a3 = (2.0 * k + alpha + beta - 2.0) * (2.0 * k + alpha + beta - 1.0) * (2.0 * k + alpha + beta)
                b = a2
                c = a3
                # recurrence: P_k = ( (b + c*x) * P_{k-1} - d * P_{k-2} ) / a1 where d = 2*(k+alpha-1)*(k+beta-1)*(2k+alpha+beta)
                d = 2.0 * (k + alpha - 1.0) * (k + beta - 1.0) * (2.0 * k + alpha + beta)
                Pk = ((b + c * x) * Pkm1 - d * Pkm2) / a1
                intermediate.append(Pk)
                Pkm2, Pkm1 = Pkm1, Pk
                Pn = Pk

    # Coefficient sum: evaluate at x=1.0 using same routine but quicker: compute P_n(alpha,beta)(1)
    # We'll compute P at 1.0 via recurrence
    def eval_at_one(alpha, beta, n):
        P0 = 1.0
        if n == 0:
            return 1.0
        P1 = 0.5 * ((alpha + beta + 2.0) * 1.0 + (alpha - beta))
        if n == 1:
            return P1
        Pkm2 = P0
        Pkm1 = P1
        Pnloc = P1
        for k in range(2, n + 1):
            a1 = 2.0 * k * (k + alpha + beta) * (2.0 * k + alpha + beta - 2.0)
            if abs(a1) < 1e-15:
                a1 = 1e-15
            a2 = (2.0 * k + alpha + beta - 1.0) * (alpha * alpha - beta * beta)
            a3 = (2.0 * k + alpha + beta - 2.0) * (2.0 * k + alpha + beta - 1.0) * (2.0 * k + alpha + beta)
            d = 2.0 * (k + alpha - 1.0) * (k + beta - 1.0) * (2.0 * k + alpha + beta)
            Pk = ((a2 + a3 * 1.0) * Pkm1 - d * Pkm2) / a1
            Pkm2, Pkm1 = Pkm1, Pk
            Pnloc = Pk
        return Pnloc

    coeff_sum = eval_at_one(alpha, beta, n)

    # Derivative estimate using relation: d/dx P_n^{(a,b)}(x) = 0.5*(n + a + b +1) * P_{n-1}^{(a+1,b+1)}(x)
    if n == 0:
        derivative_estimate = 0.0
    else:
        # compute P_{n-1}^{(alpha+1,beta+1)}(x)
        def compute_P_specific(a, b, m, xval):
            if m == 0:
                return 1.0
            P0 = 1.0
            P1 = 0.5 * ((a + b + 2.0) * xval + (a - b))
            if m == 1:
                return P1
            Pkm2 = P0
            Pkm1 = P1
            for k in range(2, m + 1):
                a1 = 2.0 * k * (k + a + b) * (2.0 * k + a + b - 2.0)
                if abs(a1) < 1e-15:
                    a1 = 1e-15
                a2 = (2.0 * k + a + b - 1.0) * (a * a - b * b)
                a3 = (2.0 * k + a + b - 2.0) * (2.0 * k + a + b - 1.0) * (2.0 * k + a + b)
                d = 2.0 * (k + a - 1.0) * (k + b - 1.0) * (2.0 * k + a + b)
                Pk = ((a2 + a3 * xval) * Pkm1 - d * Pkm2) / a1
                Pkm2, Pkm1 = Pkm1, Pk
            return Pk
        Pnm1_shift = compute_P_specific(alpha + 1.0, beta + 1.0, n - 1, x)
        derivative_estimate = 0.5 * (n + alpha + beta + 1.0) * Pnm1_shift

    # symmetry measure: expected = (-1)^n * P_n^{(beta,alpha)}(x)
    # compute P_n^{(beta,alpha)}(x)
    def compute_P_full(a, b, m, xval):
        vals = []
        P0 = 1.0
        vals.append(P0)
        if m == 0:
            return vals
        P1 = 0.5 * ((a + b + 2.0) * xval + (a - b))
        vals.append(P1)
        if m == 1:
            return vals
        Pkm2 = P0
        Pkm1 = P1
        for k in range(2, m + 1):
            a1 = 2.0 * k * (k + a + b) * (2.0 * k + a + b - 2.0)
            if abs(a1) < 1e-15:
                a1 = 1e-15
            a2 = (2.0 * k + a + b - 1.0) * (a * a - b * b)
            a3 = (2.0 * k + a + b - 2.0) * (2.0 * k + a + b - 1.0) * (2.0 * k + a + b)
            d = 2.0 * (k + a - 1.0) * (k + b - 1.0) * (2.0 * k + a + b)
            Pk = ((a2 + a3 * xval) * Pkm1 - d * Pkm2) / a1
            vals.append(Pk)
            Pkm2, Pkm1 = Pkm1, Pk
        return vals

    P_beta_alpha_vals = compute_P_full(beta, alpha, n, x)
    Pn_beta_alpha = P_beta_alpha_vals[-1]
    expected = ((-1.0) ** n) * Pn_beta_alpha
    # compute P_n(alpha,beta)(-x)
    P_negx_vals = compute_P_full(alpha, beta, n, -x)
    Pn_negx = P_negx_vals[-1]
    if abs(expected) > 1e-10:
        symmetry_measure = abs(Pn_negx - expected) / abs(expected)
    else:
        symmetry_measure = abs(Pn_negx - expected)

    # Convergence ratio: |P_n / P_{n-1}| if len >=2 and |P_{n-1}|>1e-10
    if len(intermediate) >= 2 and abs(intermediate[-2]) > 1e-10:
        convergence_ratio = abs(intermediate[-1] / intermediate[-2])
    else:
        convergence_ratio