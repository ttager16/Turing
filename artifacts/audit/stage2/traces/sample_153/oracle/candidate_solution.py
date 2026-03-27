# main.py
class ChebyshevPolynomials:
    """
    Core implementation of Chebyshev polynomial operations.
    Provides first kind polynomials and optimal node generation.
    """
    # Constants
    PI = 3.141592653589793
    NUM_TAYLOR_TERMS = 20

    @staticmethod
    def chebyshev_first_kind(n: int, x: float) -> float:
        """
        Evaluate Chebyshev polynomial of the first kind T_n(x).
        Uses recurrence relation: T_0(x) = 1, T_1(x) = x,
        T_(n+1)(x) = 2xT_n(x) - T_(n-1)(x)

        Args:
            n: Polynomial degree
            x: Evaluation point in [-1, 1]

        Returns:
            Value of T_n(x)
        """
        if n == 0:
            return 1.0
        if n == 1:
            return x

        t_prev_prev = 1.0
        t_prev = x

        for _ in range(2, n + 1):
            t_current = 2.0 * x * t_prev - t_prev_prev
            t_prev_prev = t_prev
            t_prev = t_current

        return t_prev

    @staticmethod
    def chebyshev_nodes(n: int) -> list:
        """
        Generate Chebyshev nodes of the first kind (Chebyshev-Gauss points).
        These are the roots of T_n(x) and provide optimal interpolation points.

        Formula: x_k = cos((2k - 1) * pi / (2n)) for k = 1, 2, ..., n

        Args:
            n: Number of nodes

        Returns:
            List of n Chebyshev nodes in [-1, 1]
        """
        if n <= 0:
            return []

        nodes = []

        for k in range(1, n + 1):
            angle = (2 * k - 1) * ChebyshevPolynomials.PI / (2 * n)
            node = ChebyshevPolynomials._cos(angle)
            nodes.append(node)

        return nodes

    @staticmethod
    def _cos(x: float) -> float:
        """
        Compute cosine using Taylor series for deterministic results.
        Formula: cos(x) = 1 - x^2/2! + x^4/4! - x^6/6! + ...

        Args:
            x: Angle in radians

        Returns:
            Cosine value
        """
        # Normalize to [-pi, pi]
        two_pi = 2 * ChebyshevPolynomials.PI

        while x > ChebyshevPolynomials.PI:
            x -= two_pi
        while x < -ChebyshevPolynomials.PI:
            x += two_pi

        # Taylor series
        result = 0.0
        term = 1.0
        x_squared = x * x

        for n in range(ChebyshevPolynomials.NUM_TAYLOR_TERMS):
            result += term
            term *= -x_squared / ((2 * n + 1) * (2 * n + 2))

        return result


class ChebyshevInterpolation:
    """
    Implements Chebyshev interpolation for function approximation.
    Provides superior approximation properties compared to uniform interpolation.
    """

    def __init__(self, degree: int):
        """
        Initialize Chebyshev interpolation with given degree.

        Args:
            degree: Maximum polynomial degree
        """
        self.degree = degree
        self.coefficients = []
        self.nodes = ChebyshevPolynomials.chebyshev_nodes(degree + 1)

    def fit(self, values: list) -> "ChebyshevInterpolation":
        """
        Compute Chebyshev coefficients from function values at Chebyshev nodes.
        Uses discrete Chebyshev transform.

        Args:
            values: Function values at Chebyshev nodes

        Returns:
            Self for method chaining
        """
        n = len(values)
        self.coefficients = []

        for k in range(n):
            coeff = 0.0
            for j in range(n):
                t_k = ChebyshevPolynomials.chebyshev_first_kind(k, self.nodes[j])
                coeff += values[j] * t_k

            # Normalization (1/n for k=0, 2/n for k>0)
            if k == 0:
                coeff *= 1.0 / n
            else:
                coeff *= 2.0 / n

            self.coefficients.append(coeff)

        return self

    def evaluate(self, x: float) -> float:
        """
        Evaluate interpolating polynomial at point x using Clenshaw algorithm.

        Args:
            x: Evaluation point

        Returns:
            Interpolated value
        """
        if not self.coefficients:
            return 0.0

        # Clenshaw algorithm for stable evaluation
        n = len(self.coefficients)
        if n == 0:
            return 0.0
        if n == 1:
            return self.coefficients[0]

        b_k_plus_2 = 0.0
        b_k_plus_1 = 0.0

        for k in range(n - 1, -1, -1):
            b_k = self.coefficients[k] + 2.0 * x * b_k_plus_1 - b_k_plus_2
            b_k_plus_2 = b_k_plus_1
            b_k_plus_1 = b_k

        return b_k_plus_1 - x * b_k_plus_2

    def derivative(self, x: float) -> float:
        """
        Compute derivative of interpolating polynomial at point x.
        Uses Chebyshev derivative coefficients.

        Args:
            x: Evaluation point

        Returns:
            Derivative value
        """
        if len(self.coefficients) <= 1:
            return 0.0

        # Compute derivative coefficients
        n = len(self.coefficients)
        deriv_coeffs = [0.0] * max(0, n - 1)

        for k in range(n - 2, -1, -1):
            deriv_coeffs[k] = 0.0
            for j in range(k + 1, n):
                if (j - k) % 2 == 1:
                    deriv_coeffs[k] += 2.0 * j * self.coefficients[j]

        # Handle first coefficient
        if len(deriv_coeffs) > 0:
            deriv_coeffs[0] *= 0.5

        # Evaluate using Clenshaw
        if not deriv_coeffs:
            return 0.0

        m = len(deriv_coeffs)
        if m == 1:
            return deriv_coeffs[0]

        b_k_plus_2 = 0.0
        b_k_plus_1 = 0.0

        for k in range(m - 1, -1, -1):
            b_k = deriv_coeffs[k] + 2.0 * x * b_k_plus_1 - b_k_plus_2
            b_k_plus_2 = b_k_plus_1
            b_k_plus_1 = b_k

        return b_k_plus_1 - x * b_k_plus_2


class FlowNetwork:
    """
    Represents a directed flow network with Chebyshev-enhanced optimization.
    """

    def __init__(self, num_nodes: int):
        """
        Initialize flow network.

        Args:
            num_nodes: Number of nodes in the network
        """
        self.num_nodes = num_nodes
        self.adjacency = [[] for _ in range(num_nodes)]
        self.edges = []
        self.boundary_conditions = [0.0] * num_nodes

    def add_edge(self, u: int, v: int, capacity: float):
        """
        Add directed edge to the network.

        Args:
            u: Source node
            v: Destination node
            capacity: Edge capacity/weight
        """
        self.adjacency[u].append((v, capacity))
        self.edges.append((u, v, capacity))

    def set_boundary_conditions(self, conditions: list) -> None:
        """
        Set boundary conditions for nodes.

        Args:
            conditions: List of boundary values for each node
        """
        self.boundary_conditions = conditions[:self.num_nodes]

    def compute_flow_potential(self, node: int) -> float:
        """
        Compute flow potential at a node using weighted boundary conditions.

        Args:
            node: Node index

        Returns:
            Flow potential value
        """
        # Method constants
        WEIGHT_FACTOR = 0.3
        MIN_WEIGHT = 1e-10

        if node < 0 or node >= self.num_nodes:
            return 0.0

        # Weighted sum of boundary condition and neighbor influences
        potential = self.boundary_conditions[node]

        neighbor_count = len(self.adjacency[node])
        if neighbor_count > 0:
            neighbor_contribution = 0.0
            total_weight = 0.0

            for neighbor, capacity in self.adjacency[node]:
                neighbor_contribution += capacity * self.boundary_conditions[neighbor]
                total_weight += capacity

            if total_weight > MIN_WEIGHT:
                potential += WEIGHT_FACTOR * neighbor_contribution / total_weight

        return potential


class ChebyshevFlowOptimizer:
    """
    Advanced flow optimizer using Chebyshev polynomial approximations.
    """

    def __init__(self, network, interpolation_degree=8):
        """
        Initialize optimizer.

        Args:
            network: FlowNetwork instance
            interpolation_degree: Degree for Chebyshev interpolation
        """
        self.network = network
        self.degree = interpolation_degree
        self.interpolator = ChebyshevInterpolation(interpolation_degree)

    def map_to_chebyshev_domain(self, values):
        """
        Map arbitrary values to Chebyshev domain [-1, 1].

        Args:
            values: List of values to map

        Returns:
            Tuple of (mapped_values, min_val, max_val) for reverse mapping
        """
        # Method constants
        PRECISION_THRESHOLD = 1e-10
        NORMALIZATION_FACTOR = 2.0

        if not values:
            return [], 0.0, 1.0

        min_val = min(values)
        max_val = max(values)

        if abs(max_val - min_val) < PRECISION_THRESHOLD:
            return [0.0] * len(values), min_val, max_val

        mapped = []
        for v in values:
            normalized = NORMALIZATION_FACTOR * (v - min_val) / (max_val - min_val) - 1.0
            mapped.append(normalized)

        return mapped, min_val, max_val

    def compute_flow_distribution(self):
        """
        Compute optimal flow distribution using Chebyshev approximation.

        Returns:
            Dictionary containing flow metrics
        """
        # Compute flow potentials at all nodes
        potentials = []
        for node in range(self.network.num_nodes):
            potential = self.network.compute_flow_potential(node)
            potentials.append(potential)

        # Map to Chebyshev domain
        mapped_potentials, min_pot, max_pot = self.map_to_chebyshev_domain(potentials)

        # Generate Chebyshev nodes for sampling
        cheb_nodes = ChebyshevPolynomials.chebyshev_nodes(self.degree + 1)

        # Sample potentials at Chebyshev nodes (interpolate linearly from actual potentials)
        sampled_values = []
        for node in cheb_nodes:
            # Map Chebyshev node to index space
            index_float = (node + 1.0) * 0.5 * (self.network.num_nodes - 1)
            index_int = int(index_float)

            if index_int >= self.network.num_nodes - 1:
                sampled_values.append(mapped_potentials[-1] if mapped_potentials else 0.0)
            else:
                # Linear interpolation
                frac = index_float - index_int
                val = (1.0 - frac) * mapped_potentials[index_int] + frac * mapped_potentials[index_int + 1]
                sampled_values.append(val)

        # Fit Chebyshev interpolation
        self.interpolator.fit(sampled_values)

        # Compute smoothed potentials
        smoothed_potentials = []
        for i in range(self.network.num_nodes):
            # Map index to [-1, 1]
            x = -1.0 + 2.0 * i / max(1, self.network.num_nodes - 1)
            smooth_val = self.interpolator.evaluate(x)

            # Map back to original domain
            original_val = min_pot + (smooth_val + 1.0) * 0.5 * (max_pot - min_pot)
            smoothed_potentials.append(original_val)

        return {
            'potentials': potentials,
            'smoothed_potentials': smoothed_potentials,
            'min_potential': min_pot,
            'max_potential': max_pot
        }

    def compute_edge_flows(self, potentials):
        """
        Compute flow on each edge based on potential differences.

        Args:
            potentials: Node potentials

        Returns:
            List of edge flows
        """
        edge_flows = []

        for u, v, capacity in self.network.edges:
            if u < len(potentials) and v < len(potentials):
                # Flow proportional to potential difference and capacity
                potential_diff = potentials[u] - potentials[v]
                flow = capacity * potential_diff
                edge_flows.append(flow)
            else:
                edge_flows.append(0.0)

        return edge_flows

    def compute_optimization_metrics(self):
        """
        Compute comprehensive optimization metrics using Chebyshev methods.

        Returns:
            Dictionary with multiple metrics
        """
        # Method Constants
        FLOW_WEIGHTS = [0.4, 2.0, -0.1]  # Weights for energy, efficiency, smoothness

        # Get flow distribution
        flow_dist = self.compute_flow_distribution()
        potentials = flow_dist['potentials']
        smoothed = flow_dist['smoothed_potentials']

        # Compute edge flows
        edge_flows = self.compute_edge_flows(smoothed)

        # Total flow energy (sum of squared flows weighted by capacity)
        total_energy = 0.0
        for i, (u, v, capacity) in enumerate(self.network.edges):
            if i < len(edge_flows):
                total_energy += capacity * edge_flows[i] * edge_flows[i]

        # Network efficiency (ratio of useful flow to total capacity)
        total_capacity = sum(cap for _, _, cap in self.network.edges)
        active_flow = sum(abs(f) for f in edge_flows)
        efficiency = active_flow / total_capacity if total_capacity > 1e-10 else 0.0

        # Smoothness metric (using Chebyshev derivative)
        smoothness_scores = []
        for i in range(self.network.num_nodes):
            x = -1.0 + 2.0 * i / max(1, self.network.num_nodes - 1)
            deriv = self.interpolator.derivative(x)
            smoothness_scores.append(abs(deriv))

        avg_smoothness = sum(smoothness_scores) / len(smoothness_scores) if smoothness_scores else 0.0

        # Flow variance (measure of distribution uniformity)
        mean_flow = sum(edge_flows) / len(edge_flows) if edge_flows else 0.0
        flow_variance = sum((f - mean_flow) ** 2 for f in edge_flows) / len(edge_flows) if edge_flows else 0.0

        # Potential gradient (max potential difference)
        max_gradient = 0.0
        for u, v, _ in self.network.edges:
            if u < len(smoothed) and v < len(smoothed):
                gradient = abs(smoothed[u] - smoothed[v])
                max_gradient = max(max_gradient, gradient)

        # Chebyshev approximation error
        approx_error = 0.0
        for i in range(self.network.num_nodes):
            error = abs(potentials[i] - smoothed[i])
            approx_error += error
        approx_error /= self.network.num_nodes if self.network.num_nodes > 0 else 1.0

        # Optimized flow metric (composite score)
        optimized_flow = total_energy * FLOW_WEIGHTS[0] + efficiency * FLOW_WEIGHTS[1] + avg_smoothness * FLOW_WEIGHTS[2]

        # Spectral flow entropy (measure of flow distribution disorder)
        flow_entropy = 0.0
        if edge_flows:
            total_abs_flow = sum(abs(f) for f in edge_flows)
            if total_abs_flow > 1e-10:
                for flow in edge_flows:
                    prob = abs(flow) / total_abs_flow
                    if prob > 1e-10:
                        flow_entropy -= prob * (prob ** 0.5)

        # Chebyshev convergence rate (coefficient decay analysis)
        convergence_rate = 0.0
        if len(self.interpolator.coefficients) > 1:
            coeff_ratios = []
            for i in range(1, len(self.interpolator.coefficients)):
                if abs(self.interpolator.coefficients[i-1]) > 1e-10:
                    ratio = abs(self.interpolator.coefficients[i] / self.interpolator.coefficients[i-1])
                    coeff_ratios.append(ratio)
            convergence_rate = sum(coeff_ratios) / len(coeff_ratios) if coeff_ratios else 0.0

        # Nodal flow conservation deficit (imbalance metric)
        node_imbalances = [0.0] * self.network.num_nodes
        for i, (u, v, _) in enumerate(self.network.edges):
            if i < len(edge_flows):
                node_imbalances[u] -= edge_flows[i]  # Outflow
                node_imbalances[v] += edge_flows[i]  # Inflow

        max_imbalance = max(abs(imb) for imb in node_imbalances) if node_imbalances else 0.0
        avg_imbalance = sum(abs(imb) for imb in node_imbalances) / len(node_imbalances) if node_imbalances else 0.0

        # Potential field curvature (second derivative analysis)
        curvature_scores = []
        for i in range(self.network.num_nodes):
            x = -1.0 + 2.0 * i / max(1, self.network.num_nodes - 1)
            # Approximate second derivative using finite differences
            h = 0.001
            if abs(x + h) <= 1.0 and abs(x - h) <= 1.0:
                deriv_plus = self.interpolator.derivative(x + h)
                deriv_minus = self.interpolator.derivative(x - h)
                second_deriv = (deriv_plus - deriv_minus) / (2.0 * h)
                curvature_scores.append(abs(second_deriv))

        avg_curvature = sum(curvature_scores) / len(curvature_scores) if curvature_scores else 0.0
        max_curvature = max(curvature_scores) if curvature_scores else 0.0

        # Network resilience score (gradient variance-based stability)
        resilience_score = 0.0
        gradients = []
        for u, v, _ in self.network.edges:
            if u < len(smoothed) and v < len(smoothed):
                gradients.append(abs(smoothed[u] - smoothed[v]))

        if gradients:
            mean_gradient = sum(gradients) / len(gradients)
            gradient_variance = sum((g - mean_gradient) ** 2 for g in gradients) / len(gradients)
            resilience_score = 1.0 / (1.0 + gradient_variance)

        return {
            'optimized_flow_metric': round(optimized_flow, 5),
            'total_energy': round(total_energy, 4),
            'network_efficiency': round(efficiency, 4),
            'average_smoothness': round(avg_smoothness, 4),
            'flow_variance': round(flow_variance, 5),
            'max_potential_gradient': round(max_gradient, 5),
            'approximation_error': round(approx_error, 7),
            'total_flow': round(active_flow, 5),
            'spectral_entropy': round(flow_entropy, 6),
            'convergence_rate': round(convergence_rate, 6),
            'max_node_imbalance': round(max_imbalance, 5),
            'avg_node_imbalance': round(avg_imbalance, 6),
            'average_curvature': round(avg_curvature, 5),
            'max_curvature': round(max_curvature, 5),
            'resilience_score': round(resilience_score, 5),
            'edge_flows': [round(flow, 3) for flow in edge_flows],
            'node_potentials': [round(potential, 5) for potential in smoothed],
            'raw_potentials': [round(potential, 5) for potential in potentials],
            'chebyshev_coefficients': [round(c, 6) for c in self.interpolator.coefficients]
        }


def compute_advanced_airflow_network(num_nodes: int, edges: list, boundary_conditions: list) -> dict:
    """
    Main entry point: Constructs and optimizes a multi-layer flow network using
    Chebyshev polynomial approximations for real-time CFD-inspired analysis.

    This function leverages Chebyshev polynomials for:
    - Optimal sampling via Chebyshev nodes
    - Superior function approximation and interpolation
    - Smooth derivative computation for gradient analysis
    - Numerically stable polynomial evaluation

    Args:
        num_nodes: Number of nodes in the network (int)
        edges: List of lists [source, dest, capacity] representing directed edges
        boundary_conditions: List of boundary values for each node (floats)

    Returns:
        Dictionary containing:
            - optimized_flow_metric: Primary optimization result (float)
            - total_energy: Sum of squared flows weighted by capacity (float)
            - network_efficiency: Ratio of active flow to total capacity (float)
            - average_smoothness: Mean of absolute Chebyshev derivatives (float)
            - flow_variance: Variance of edge flows (float)
            - max_potential_gradient: Maximum potential difference (float)
            - approximation_error: Mean Chebyshev approximation error (float)
            - total_flow: Sum of absolute edge flows (float)
            - spectral_entropy: Flow distribution disorder measure (float)
            - convergence_rate: Chebyshev coefficient decay rate (float)
            - max_node_imbalance: Maximum flow conservation deficit at nodes (float)
            - avg_node_imbalance: Average flow conservation deficit (float)
            - average_curvature: Mean potential field second derivative (float)
            - max_curvature: Maximum potential field second derivative (float)
            - resilience_score: Network stability metric based on gradient variance (float)
            - edge_flows: List of computed flow values for each edge (list)
            - node_potentials: Smoothed potential values at nodes (list)
            - raw_potentials: Original computed potentials (list)
            - chebyshev_coefficients: Coefficients of Chebyshev interpolation (list)
            - num_nodes: Input node count (int)
            - num_edges: Input edge count (int)
            - chebyshev_degree: Degree of polynomial used (int)
            - error: Error message if inputs are invalid (str, optional)
    """
    # Validate inputs
    if not isinstance(num_nodes, int) or num_nodes <= 0:
        return {"error": "Number of nodes must be a positive integer."}
    if not isinstance(edges, list) or not all(isinstance(edge, list) and len(edge) >= 3 for edge in edges):
        return {"error": "Edges must be a list of lists with at least 3 elements each."}
    if not isinstance(boundary_conditions, list) or len(boundary_conditions) != num_nodes:
        return {"error": "Boundary conditions must be a list of length equal to number of nodes."}
    if not all(isinstance(bc, (int, float)) for bc in boundary_conditions):
        return {"error": "All boundary conditions must be numeric values."}

    # Create network
    network = FlowNetwork(num_nodes)

    # Add edges
    for edge in edges:
        if len(edge) >= 3:
            u, v, capacity = edge[0], edge[1], edge[2]
            if 0 <= u < num_nodes and 0 <= v < num_nodes:
                network.add_edge(u, v, capacity)

    # Set boundary conditions
    network.set_boundary_conditions(boundary_conditions)

    # Determine optimal Chebyshev degree based on network size
    OPTIMAL_MIN_DEGREE = 4
    OPTIMAL_MAX_DEGREE = 12
    optimal_degree = min(max(OPTIMAL_MIN_DEGREE, num_nodes // 2), OPTIMAL_MAX_DEGREE)

    # Create optimizer
    optimizer = ChebyshevFlowOptimizer(network, interpolation_degree=optimal_degree)

    # Compute all metrics
    metrics = optimizer.compute_optimization_metrics()

    # Add metadata
    metrics['num_nodes'] = num_nodes
    metrics['num_edges'] = len(network.edges)
    metrics['chebyshev_degree'] = optimal_degree

    return metrics


if __name__ == "__main__":
    # Example usage with sample network
    num_nodes = 5
    edges = [
        [0, 1, 0.5],
        [1, 2, 0.3],
        [2, 3, 1.0],
        [1, 4, 2.5],
        [0, 3, 0.2]
    ]
    boundary_conditions = [0.8, 0.9, 0.7, 1.2, 0.6]

    result = compute_advanced_airflow_network(num_nodes, edges, boundary_conditions)
    print(result)