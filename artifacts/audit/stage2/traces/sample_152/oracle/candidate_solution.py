# main.py
class JacobiPolynomialComputer:
    """
    A dataclass-style computer for Jacobi polynomials with comprehensive analysis.

    This class encapsulates all computation logic, helper methods, and mathematical
    functions needed for computing Jacobi polynomials and their properties.
    """

    def __init__(self, alpha: float, beta: float, n: int, x: float):
        """
        Initialize the Jacobi polynomial computer.

        Args:
            alpha: Weight parameter (alpha > -1)
            beta: Weight parameter (beta > -1)
            n: Polynomial degree (n >= 0)
            x: Evaluation point
        """
        self.alpha = alpha
        self.beta = beta
        self.n = n
        self.x = x

    def compute(self) -> dict:
        """
        Compute Jacobi polynomial with comprehensive analysis.

        Returns:
            Dictionary containing polynomial value and detailed metrics.
        """
        # Core computation
        polynomial_value = self._compute_polynomial(self.alpha, self.beta, self.n, self.x)

        # Collect intermediate values for analysis
        intermediate_values = []
        for k in range(self.n + 1):
            intermediate_values.append(self._compute_polynomial(self.alpha, self.beta, k, self.x))

        # Compute leading coefficient using the explicit formula
        leading_coefficient = self._compute_leading_coefficient(self.alpha, self.beta, self.n)

        # Compute normalization constant (L2 norm squared)
        normalization_constant = self._compute_normalization_constant(self.alpha, self.beta, self.n)

        # Normalized value
        normalized_value = polynomial_value / (normalization_constant ** 0.5) if normalization_constant > 0 else 0.0

        # Coefficient sum: evaluate at x=1 to get sum of coefficients
        coefficient_sum = self._compute_polynomial(self.alpha, self.beta, self.n, 1.0)

        # Derivative estimate
        derivative_estimate = self._estimate_derivative(self.alpha, self.beta, self.n, self.x)

        # Symmetry measure
        symmetry_measure = self._compute_symmetry_measure(self.alpha, self.beta, self.n, self.x)

        # Convergence ratio: ratio of consecutive intermediate values
        convergence_ratio = self._compute_convergence_ratio(intermediate_values)

        # Stability index: measures numerical stability based on value magnitudes
        stability_index = self._compute_stability_index(intermediate_values, polynomial_value)

        return {
            "polynomial_value": round(polynomial_value, 6),
            "normalized_value": round(normalized_value, 6),
            "degree": self.n,
            "alpha": self.alpha,
            "beta": self.beta,
            "x": self.x,
            "leading_coefficient": round(leading_coefficient, 5),
            "normalization_constant": round(normalization_constant, 5),
            "recursion_depth": self.n,
            "intermediate_values": [round(v, 5) for v in intermediate_values],
            "coefficient_sum": round(coefficient_sum, 4),
            "derivative_estimate": round(derivative_estimate, 4),
            "symmetry_measure": round(symmetry_measure, 5),
            "convergence_ratio": round(convergence_ratio, 5),
            "stability_index": round(stability_index, 5)
        }

    def _compute_polynomial(self, alpha: float, beta: float, n: int, x: float) -> float:
        """
        Compute Jacobi polynomial using three-term recurrence relation.

        The recurrence relation is:
        2n(n+alpha+beta)(2n+alpha+beta-2) P_n =
            (2n+alpha+beta-1)[(2n+alpha+beta)(2n+alpha+beta-2)x + alpha^2-beta^2] P_{n-1}
            - 2(n+alpha-1)(n+beta-1)(2n+alpha+beta) P_{n-2}

        With initial conditions:
        P_0^(alpha,beta)(x) = 1
        P_1^(alpha,beta)(x) = (alpha+1) + (alpha+beta+2)(x-1)/2

        Args:
            alpha: Weight parameter
            beta: Weight parameter
            n: Polynomial degree
            x: Evaluation point

        Returns:
            Value of P_n^(alpha,beta)(x)
        """
        # Constants
        SMALL_NUMBER = 1e-15

        if n == 0:
            return 1.0

        if n == 1:
            return 0.5 * ((alpha + beta + 2) * x + (alpha - beta))

        # Initialize for iterative computation
        p_prev2 = 1.0  # P_0
        p_prev1 = 0.5 * ((alpha + beta + 2) * x + (alpha - beta))  # P_1

        # Iteratively compute up to P_n
        for k in range(2, n + 1):
            # Coefficients for the recurrence relation
            a1 = 2 * k * (k + alpha + beta) * (2 * k + alpha + beta - 2)

            if abs(a1) < SMALL_NUMBER:  # Avoid division by very small numbers
                a1 = SMALL_NUMBER

            a2 = (2 * k + alpha + beta - 1) * (2 * k + alpha + beta) * (2 * k + alpha + beta - 2)
            a3 = (2 * k + alpha + beta - 1) * (alpha * alpha - beta * beta)
            a4 = -2 * (k + alpha - 1) * (k + beta - 1) * (2 * k + alpha + beta)

            # Apply recurrence relation
            p_current = ((a2 * x + a3) * p_prev1 + a4 * p_prev2) / a1

            # Update for next iteration
            p_prev2 = p_prev1
            p_prev1 = p_current

        return p_prev1

    def _compute_leading_coefficient(self, alpha: float, beta: float, n: int) -> float:
        """
        Compute the leading coefficient of Jacobi polynomial P_n^(alpha,beta)(x).

        The leading coefficient is given by:
        c_n = (2n+alpha+beta choose n) * 2^{-n}
            = Gamma(2n+alpha+beta+1) / (Gamma(n+1) * Gamma(n+alpha+beta+1)) * 2^{-n}

        For numerical stability, we use the binomial coefficient formula.

        Args:
            alpha: Weight parameter
            beta: Weight parameter
            n: Polynomial degree

        Returns:
            Leading coefficient value
        """
        if n == 0:
            return 1.0

        # Use logarithms to avoid overflow for large n
        # log(c_n) = sum_{k=1}^{n} log(n+alpha+beta+k) - log(k) - n*log(2)
        log_coeff = 0.0

        for k in range(1, n + 1):
            log_coeff += self._safe_log(n + alpha + beta + k)
            log_coeff -= self._safe_log(k)

        log_coeff -= n * self._safe_log(2.0)

        return self._safe_exp(log_coeff)

    def _compute_normalization_constant(self, alpha: float, beta: float, n: int) -> float:
        """
        Compute the L2 normalization constant for Jacobi polynomial.

        The normalization constant (squared L2 norm) is:
        h_n = integral_{-1}^{1} [P_n^(alpha,beta)(x)]^2 (1-x)^alpha (1+x)^beta dx
            = 2^{alpha+beta+1} / (2n+alpha+beta+1) *
              Gamma(n+alpha+1) * Gamma(n+beta+1) / (Gamma(n+1) * Gamma(n+alpha+beta+1))

        Args:
            alpha: Weight parameter
            beta: Weight parameter
            n: Polynomial degree

        Returns:
            Normalization constant value
        """
        if n == 0:
            numerator = 2.0 ** (alpha + beta + 1)
            denominator = alpha + beta + 1
            return numerator / denominator if denominator > 0 else 1.0

        # Use logarithms for numerical stability
        log_norm = (alpha + beta + 1) * self._safe_log(2.0)
        log_norm -= self._safe_log(2 * n + alpha + beta + 1)

        # Add gamma function ratios using log-gamma
        log_norm += self._log_gamma(n + alpha + 1)
        log_norm += self._log_gamma(n + beta + 1)
        log_norm -= self._log_gamma(n + 1)
        log_norm -= self._log_gamma(n + alpha + beta + 1)

        return self._safe_exp(log_norm)

    def _estimate_derivative(self, alpha: float, beta: float, n: int, x: float) -> float:
        """
        Estimate the derivative of P_n^(alpha,beta)(x) using analytical formula.

        The derivative is computed using:
        d/dx P_n^(alpha,beta)(x) = 0.5 * (n+alpha+beta+1) * P_{n-1}^(alpha+1,beta+1)(x)

        Args:
            alpha: Weight parameter
            beta: Weight parameter
            n: Polynomial degree
            x: Evaluation point

        Returns:
            Derivative value
        """
        if n == 0:
            return 0.0

        # Use analytical formula
        if n >= 1:
            factor = 0.5 * (n + alpha + beta + 1)
            p_prev = self._compute_polynomial(alpha + 1, beta + 1, n - 1, x)
            return factor * p_prev

        return 0.0

    def _compute_symmetry_measure(self, alpha: float, beta: float, n: int, x: float) -> float:
        """
        Compute a symmetry measure for the Jacobi polynomial.

        Jacobi polynomials satisfy the symmetry relation:
        P_n^(alpha,beta)(-x) = (-1)^n * P_n^(beta,alpha)(x)

        The symmetry measure quantifies how this relation holds.

        Args:
            alpha: Weight parameter
            beta: Weight parameter
            n: Polynomial degree
            x: Evaluation point

        Returns:
            Symmetry measure (close to 0 indicates perfect symmetry)
        """
        # Constants
        THRESHOLD = 1e-10

        p_at_minus_x = self._compute_polynomial(alpha, beta, n, -x)
        p_swapped = self._compute_polynomial(beta, alpha, n, x)

        # Expected relation: P_n^(alpha,beta)(-x) = (-1)^n * P_n^(beta,alpha)(x)
        sign = 1 if n % 2 == 0 else -1
        expected = sign * p_swapped

        # Measure deviation from expected symmetry
        if abs(expected) > THRESHOLD:
            return abs(p_at_minus_x - expected) / abs(expected)
        else:
            return abs(p_at_minus_x - expected)

    def _compute_convergence_ratio(self, intermediate_values: list) -> float:
        """
        Compute convergence ratio from intermediate polynomial values.

        The ratio |P_n / P_{n-1}| can indicate convergence behavior.

        Args:
            intermediate_values: List of polynomial values from degree 0 to n

        Returns:
            Convergence ratio (or 0 if not computable)
        """
        # Constants
        THRESHOLD = 1e-10
        NOT_COMPUTABLE_VALUE = 0.0

        if len(intermediate_values) < 2:
            return NOT_COMPUTABLE_VALUE

        # Use the ratio of last two values
        if abs(intermediate_values[-2]) > THRESHOLD:
            return abs(intermediate_values[-1] / intermediate_values[-2])
        else:
            return NOT_COMPUTABLE_VALUE

    def _compute_stability_index(self, intermediate_values: list, final_value: float) -> float:
        """
        Compute a numerical stability index.

        This measures the ratio of maximum intermediate value to final value,
        indicating potential numerical instability if very large.

        Args:
            intermediate_values: List of polynomial values from degree 0 to n
            final_value: Final polynomial value

        Returns:
            Stability index (1.0 is ideal, higher values indicate potential issues)
        """
        if not intermediate_values:
            return 1.0

        max_abs_value = max(abs(v) for v in intermediate_values)

        if abs(final_value) > 1e-10:
            return max_abs_value / abs(final_value)
        elif max_abs_value > 1e-10:
            return max_abs_value
        else:
            return 1.0

    def _safe_log(self, x: float) -> float:
        """
        Compute natural logarithm with safeguards.

        Args:
            x: Input value

        Returns:
            Natural logarithm of x
        """
        # Constants
        LARGE_NEGATIVE = -1e10

        if x <= 0:
            return LARGE_NEGATIVE  # Return large negative value for invalid input

        return self._log_approximation(x)

    def _safe_exp(self, x: float) -> float:
        """
        Compute exponential with overflow protection.

        Args:
            x: Input value

        Returns:
            e^x with overflow protection
        """
        # Constants
        MAX_EXP = 700
        MIN_EXP = -700
        INF_VALUE = 1e308

        if x > MAX_EXP:  # Prevent overflow
            return INF_VALUE
        if x < MIN_EXP:  # Prevent underflow
            return 0.0

        return self._exp_approximation(x)

    def _log_approximation(self, x: float) -> float:
        """
        Compute natural logarithm using Taylor series and range reduction.

        Uses the identity: log(x) = log(m * 2^e) = log(m) + e*log(2)
        where m is in [1, 2) (mantissa) and e is the exponent.

        Args:
            x: Positive real number

        Returns:
            Natural logarithm of x
        """
        # Constants
        LN2 = 0.6931471805599453  # Natural log of 2 with 16 decimal places
        NUM_TERMS = 50  # Number of terms in Taylor series for log
        MANTISSA_LOW = 1.0
        MANTISSA_HIGH = 2.0

        if x <= 0:
            return float('-inf')
        if x == 1.0:
            return 0.0

        # Range reduction: express x = m * 2^e where m in [1, 2)
        exponent = 0
        mantissa = x

        while mantissa >= MANTISSA_HIGH:
            mantissa /= 2.0
            exponent += 1

        while mantissa < MANTISSA_LOW:
            mantissa *= 2.0
            exponent -= 1

        # Now compute log(mantissa) where mantissa in [1, 2)
        # Use transformation: log(m) = log((1+z)/(1-z)) = 2(z + z^3/3 + z^5/5 + ...)
        # where z = (m-1)/(m+1)
        z = (mantissa - 1.0) / (mantissa + 1.0)
        z_squared = z * z

        # Taylor series for log((1+z)/(1-z)) = 2 * sum_{k=0}^{inf} z^(2k+1) / (2k+1)
        result = 0.0
        term = z

        for k in range(NUM_TERMS):  # 50 terms for good precision
            result += term / (2 * k + 1)
            term *= z_squared

        result *= 2.0

        # Add back the exponent contribution: e * log(2)
        result += exponent * LN2

        return result

    def _exp_approximation(self, x: float) -> float:
        """
        Compute exponential function using Taylor series.

        e^x = 1 + x + x^2/2! + x^3/3! + ...

        Args:
            x: Real number

        Returns:
            e^x
        """
        # Constants
        E_VALUE = 2.718281828459045  # e with 16 decimal places
        NUM_TERMS = 100  # Number of terms in Taylor series
        CONVERGENCE_THRESHOLD = 1e-15

        if x == 0:
            return 1.0

        # For large x, use exp(x) = exp(n)*exp(r) where x = n + r, |r| < 1
        n = int(x)
        r = x - n

        # Compute exp(r) using Taylor series
        result = 1.0
        term = 1.0

        for k in range(1, NUM_TERMS):
            term *= r / k
            result += term
            if abs(term) < CONVERGENCE_THRESHOLD:  # Convergence check
                break

        # Compute exp(n) by repeated squaring if needed
        if n > 0:
            exp_n = 1.0
            base = E_VALUE
            power = n
            while power > 0:
                if power % 2 == 1:
                    exp_n *= base
                base *= base
                power //= 2
            result *= exp_n
        elif n < 0:
            exp_n = 1.0
            base = E_VALUE
            power = -n
            while power > 0:
                if power % 2 == 1:
                    exp_n *= base
                base *= base
                power //= 2
            result /= exp_n

        return result

    def _log_gamma(self, x: float) -> float:
        """
        Compute logarithm of gamma function using Stirling's approximation.

        Uses Stirling's formula:
        log(Gamma(x)) ≈ (x-0.5)*log(x) - x + 0.5*log(2π) + corrections

        Args:
            x: Positive real number

        Returns:
            Natural logarithm of Gamma(x)
        """
        # Constants
        X_UPPER_LIMIT = 20
        LOG_2PI = 1.8378770664093453  # Natural log of 2*pi with 16 decimal places
        CORRECTION_TERMS = [1.0 / 12.0, -1.0 / 360.0, 1.0 / 1260.0]

        if x <= 0:
            return float('inf')

        # For small integers, use factorial
        if x == int(x) and x <= X_UPPER_LIMIT:
            n = int(x)
            factorial = 1
            for i in range(2, n):
                factorial *= i
            return self._log_approximation(float(factorial))

        # Stirling's approximation with correction terms
        result = (x - 0.5) * self._log_approximation(x) - x + 0.5 * LOG_2PI

        # Add correction terms
        if x > 1:
            result += CORRECTION_TERMS[0] / x
            result += CORRECTION_TERMS[1] / (x * x * x)
            result += CORRECTION_TERMS[2] / (x * x * x * x * x)

        return result


def compute_jacobi_polynomials(alpha: float, beta: float, n: int, x: float) -> dict:
    """
    Compute Jacobi Polynomial P_n^(alpha,beta)(x) with comprehensive analysis.

    Args:
        alpha: Weight parameter (alpha > -1)
        beta: Weight parameter (beta > -1)
        n: Polynomial degree (n >= 0)
        x: Evaluation point (typically in [-1, 1], but extends to real line)

    Returns:
        Dictionary containing:
            - polynomial_value: The computed P_n^(alpha,beta)(x)
            - normalized_value: Value normalized by leading coefficient
            - degree: Input polynomial degree
            - alpha: Input alpha parameter
            - beta: Input beta parameter
            - x: Input evaluation point
            - leading_coefficient: Coefficient of highest degree term
            - normalization_constant: L2 norm normalization factor
            - recursion_depth: Number of recursion steps used
            - intermediate_values: List of P_0, P_1, ..., P_n
            - coefficient_sum: Sum of all polynomial coefficients
            - derivative_estimate: Numerical estimate of first derivative
            - symmetry_measure: Measure of polynomial symmetry
            - convergence_ratio: Ratio indicating convergence rate
            - stability_index: Numerical stability indicator
            - error: Error message if inputs are invalid
    """
    # Validate inputs
    if not isinstance(n, int) or n < 0:
        return {"error": f"Degree n must be a non-negative integer, got {n}."}
    if not isinstance(alpha, (int, float)) or not isinstance(beta, (int, float)):
        return {"error": "Alpha and Beta must be real numbers."}
    if not isinstance(x, (int, float)):
        return {"error": "Evaluation point x must be a real number."}
    if alpha <= -1:
        return {"error": f"Alpha must be greater than -1, got {alpha}."}
    if beta <= -1:
        return {"error": f"Beta must be greater than -1, got {beta}."}

    computer = JacobiPolynomialComputer(alpha, beta, n, x)
    return computer.compute()


# Example usage and testing
if __name__ == "__main__":
    alpha = 1.5
    beta = 2.0
    n = 12
    x = 0.75
    result = compute_jacobi_polynomials(alpha=alpha, beta=beta, n=n, x=x)
    print(result)