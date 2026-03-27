def compute_advanced_airflow_network(num_nodes: int, edges: list, boundary_conditions: list) -> dict:
    import math
    # Constants
    PI = 3.141592653589793
    TAYLOR_TERMS = 20
    EPS = 1e-10

    # Validation
    if not isinstance(num_nodes, int) or num_nodes <= 0:
        return {"error": "Number of nodes must be a positive integer."}
    if not isinstance(edges, list) or any((not isinstance(e, list) or len(e) < 3) for e in edges):
        return {"error": "Edges must be a list of lists with at least 3 elements each."}
    if not isinstance(boundary_conditions, list) or len(boundary_conditions) != num_nodes:
        return {"error": "Boundary conditions must be a list of length equal to number of nodes."}
    try:
        boundary_conditions = [float(x) for x in boundary_conditions]
    except Exception:
        return {"error": "All boundary conditions must be numeric values."}

    # Helpers
    def normalize_angle(a):
        # normalize to [-pi, pi]
        a = float(a)
        while a > PI:
            a -= 2 * PI
        while a < -PI:
            a += 2 * PI
        return a

    def cos_taylor(x):
        x = normalize_angle(x)
        term = 1.0
        s = term
        x2 = x * x
        sign = -1.0
        denom = 2.0
        for n in range(1, TAYLOR_TERMS):
            term *= x2 / ((2*n-1)*(2*n))
            s += sign * term
            sign *= -1.0
        return s

    # Chebyshev T_n(x) via recurrence
    def chebyshev_T(n, x):
        if n == 0:
            return 1.0
        if n == 1:
            return x
        Tn_2 = 1.0
        Tn_1 = x
        Tn = None
        for k in range(2, n+1):
            Tn = 2.0 * x * Tn_1 - Tn_2
            Tn_2, Tn_1 = Tn_1, Tn
        return Tn

    def chebyshev_nodes(n):
        if n <= 0:
            return []
        # nodes are roots of T_n: x_j = cos((2j-1)/(2n) * pi), j=1..n
        nodes = []
        for j in range(1, n+1):
            angle = (2*j - 1) * PI / (2.0 * n)
            nodes.append(cos_taylor(angle))
        return nodes

    # Discrete Chebyshev Transform (type I-like per spec)
    def discrete_chebyshev_transform(values):
        n = len(values)
        if n == 0:
            return []
        coeffs = []
        for k in range(n):
            s = 0.0
            for j in range(n):
                xj = cos_taylor(PI * (j + 0.5) / n)
                Tk = chebyshev_T(k, xj)
                s += values[j] * Tk
            norm = (1.0 / n) if k == 0 else (2.0 / n)
            coeffs.append(s * norm)
        return coeffs

    # Clenshaw algorithm for evaluating Chebyshev series at x in [-1,1]
    def clenshaw_eval(coeffs, x):
        if not coeffs:
            return 0.0
        if len(coeffs) == 1:
            return coeffs[0]
        b_kplus1 = 0.0
        b_kplus2 = 0.0
        n = len(coeffs) - 1
        for k in range(n, -1, -1):
            b_k = 2.0 * x * b_kplus1 - b_kplus2 + coeffs[k]
            b_kplus2 = b_kplus1
            b_kplus1 = b_k
        return b_kplus1 - x * b_kplus2

    def derivative_coeffs_chebyshev(c):
        m = len(c)
        if m <= 1:
            return [0.0]
        cder = [0.0] * (m - 1)
        for k in range(m - 1):
            s = 0.0
            for j in range(k+1, m):
                if ((j - k) % 2) == 1:
                    s += j * c[j]
            cder[k] = s
        # halve the first coefficient
        cder[0] *= 0.5
        return cder

    # Build network
    adj = [[] for _ in range(num_nodes)]
    edge_list = []
    for e in edges:
        try:
            u = int(e[0]); v = int(e[1]); cap = float(e[2])
        except Exception:
            continue
        if 0 <= u < num_nodes and 0 <= v < num_nodes:
            adj[u].append((v, cap))
            edge_list.append((u, v, cap))
    num_edges = len(edge_list)

    # Raw potentials per node: boundary + 0.3 * capacity-weighted average neighbor boundary values if total cap > threshold
    raw_potentials = [float(b) for b in boundary_conditions]
    for i in range(num_nodes):
        neigh = adj[i]
        total_cap = sum(c for (_, c) in neigh)
        if total_cap > 1e-10:
            weighted = sum(boundary_conditions[v] * c for (v, c) in neigh)
            raw_potentials[i] += 0.3 * (weighted / total_cap)

    # Domain mapping to [-1,1] using linear normalization; return zeros if range below threshold
    def map_to_minus1_1(vals):
        mn = min(vals)
        mx = max(vals)
        if mx - mn < 1e-10:
            return [0.0] * len(vals), mn, mx
        return [ -1.0 + 2.0 * (v - mn) / (mx - mn) for v in vals ], mn, mx

    mapped, mn_raw, mx_raw = map_to_minus1_1(raw_potentials)

    # Select degree
    degree = max(4, min(12, num_nodes // 2))
    interp_n = degree + 1

    # Interpolator nodes: generate degree+1 Chebyshev nodes
    interp_nodes = chebyshev_nodes(interp_n)

    # Map Chebyshev nodes to index space and sample via linear interpolation of mapped potentials
    sampled = []
    for x in interp_nodes:
        # Map x in [-1,1] to index space: idx = (x+1)/2 * (num_nodes-1)
        idx = (x + 1.0) * 0.5 * (num_nodes - 1)
        if idx >= num_nodes - 1 - 1e-12:
            sampled.append(mapped[-1])
        else:
            if idx <= 0:
                sampled.append(mapped[0])
            else:
                idx_int = int(math.floor(idx))
                frac = idx - idx_int
                a = mapped[idx_int]
                b = mapped[min(idx_int + 1, num_nodes - 1)]
                sampled.append(a * (1 - frac) + b * frac)

    # Compute Chebyshev coefficients from sampled values (discrete transform)
    cheb_coeffs = discrete_chebyshev_transform(sampled)

    # Derivative coefficients
    cheb_deriv_coeffs = derivative_coeffs_chebyshev(cheb_coeffs)

    # Evaluate smoothed potentials at each node position using Clenshaw, then map back to original domain
    smoothed_mapped = []
    for i in range(num_nodes):
        x = -1.0 + 2.0 * i / max(1, num_nodes - 1)
        val = clenshaw_eval(cheb_coeffs, x)
        smoothed_mapped.append(val)
    if mx_raw - mn_raw < 1e-10:
        node_potentials = [mn_raw for _ in smoothed_mapped]
    else:
        node_potentials = [mn_raw + (v + 1.0) * 0.5 * (mx_raw - mn_raw) for v in smoothed_mapped]

    # Approximation error: mean abs difference between raw and smoothed (original domain)
    approx_error = sum(abs(raw_potentials[i] - node_potentials[i]) for i in range(num_nodes)) / num_nodes

    # Edge flows
    edge_flows = []
    for (u, v, cap) in edge_list:
        flow = cap * (node_potentials[u] - node_potentials[v])
        edge_flows.append(flow)

    # Total energy: sum cap * flow^2
    total_energy = sum(cap * ( (node_potentials[u] - node_potentials[v])**2 ) for (u, v, cap) in edge_list)

    # Network efficiency: total absolute flow / total capacity (flow utilization)
    total_abs_flow = sum(abs(f) for f in edge_flows)
    total_capacity = sum(cap for (_, _, cap) in edge_list) if edge_list else 0.0
    network_efficiency = (total_abs_flow / total_capacity) if total_capacity > 1e-10 else 0.0

    # Smoothness: mean of absolute derivative values across node positions
    # compute derivative at nodes via Chebyshev derivative evaluation
    deriv_vals = []
    if len(cheb_deriv_coeffs) <= 1:
        deriv_vals = [0.0] * num_nodes
    else:
        for i in range(num_nodes):
            x = -1.0 + 2.0 * i / max(1, num_nodes - 1)
            dv = clenshaw_eval(cheb_deriv_coeffs, x)
            # scale derivative because domain mapping from [-1,1] to original: original derivative = dv * (2/(mx-mn))
            scale = 1.0
            if mx_raw - mn_raw > 1e-10:
                scale = 2.0 / (mx_raw - mn_raw)
            deriv_vals.append(abs(dv * scale))
    average_smoothness = sum(deriv_vals) / num_nodes if num_nodes else 0.0

    # Composite flow metric: 0.4*energy + 2.0*efficiency + -0.1*smoothness
    optimized_flow_metric = 0.4 * total_energy + 2.0 * network_efficiency - 0.1 * average_smoothness

    # Flow variance
    flow_mean = (sum(edge_flows) / len(edge_flows)) if edge_flows else 0.0
    flow_variance = (sum((f - flow_mean)**2 for f in edge_flows) / len(edge_flows)) if edge_flows else 0.0

    # Max potential gradient
    max_potential_gradient = 0.0
    for (u, v, _) in edge_list:
        max_potential_gradient = max(max_potential_gradient, abs(node_potentials[u] - node_potentials[v]))

    # Total flow
    total_flow = total_abs_flow

    # Spectral entropy
    spectral_entropy = 0.0
    if total_abs_flow > 1e-10:
        total_abs = total_abs_flow
        for f in edge_flows:
            prob = abs(f) / total_abs
            if prob > 1e-10:
                spectral_entropy += - (prob * math.sqrt(prob))
    else:
        spectral_entropy = 0.0

    # Convergence rate: mean of ratios abs(coeff[i]/coeff[i-1]) for consecutive with denom > 1e-10
    ratios = []
    for i in range(1, len(cheb_coeffs)):
        denom = abs(cheb_coeffs[i-1])
        if denom > 1e-10:
            ratios.append(abs(cheb_coeffs[i]) / denom)
    convergence_rate = sum(ratios) / len(ratios) if len(ratios) >= 1 else 0.0
    if len(ratios) < 1:
        convergence_rate = 0.0

    # Node imbalance tracking
    imbalances = [0.0] * num_nodes
    for idx, (u, v, cap) in enumerate(edge_list):
        f = edge_flows[idx]
        imbalances[u] -= f
        imbalances[v] += f
    max_node_imbalance = max(abs(x) for x in imbalances) if imbalances else 0.0
    avg_node_imbalance = sum(abs(x) for x in imbalances) / num_nodes if num_nodes else 0.0

    # Curvature approximation: finite difference on derivative function
    def deriv_at(x):
        if len(cheb_deriv_coeffs) == 0:
            return 0.0
        return clenshaw_eval(cheb_deriv_coeffs, x) * (2.0 / (mx_raw - mn_raw)) if mx_raw - mn_raw > 1e-10 else 0.0
    h = 0.001
    curvatures = []
    for i in range(num_nodes):
        x = -1.0 + 2.0 * i / max(1, num_nodes - 1)
        if abs(x + h) <= 1.0 and abs(x - h) <= 1.0:
            c = (deriv_at(x + h) - deriv_at(x - h)) / (2.0 * h)
            curvatures.append(abs(c))
    average_curvature = sum(curvatures) / len(curvatures) if curvatures else 0.0
    max_curvature = max(curvatures) if curvatures else 0.0

    # Resilience score
    grad_diffs = [abs(node_potentials[u] - node_potentials[v]) for (u, v, _) in edge_list] if edge_list else [0.0]
    mean_grad = sum(grad_diffs) / len(grad_diffs) if grad_diffs else 0.0
    var_grad = sum((g - mean_grad)**2 for g in grad_diffs) / len(grad_diffs) if grad_diffs else 0.0
    resilience_score = 1.0 / (1.0 + var_grad)

    # Rounding final outputs as specified
    def r(v, digits):
        return round(v, digits)

    out = {
        'optimized_flow_metric': r(optimized_flow_metric, 5),
        'total_energy': r(total_energy, 4),
        'network_efficiency': r(network_efficiency, 4),
        'average_smoothness': r(average_smoothness, 4),
        'flow_variance': r(flow_variance, 5),
        'max_potential_gradient': r(max_potential_gradient, 5),
        'approximation_error': r(approx_error, 7),
        'total_flow': r(total_flow, 5),
        'spectral_entropy': r(spectral_entropy, 6),
        'convergence_rate': r(convergence_rate, 6),
        'max_node_imbalance': r(max_node_imbalance, 5),
        'avg_node_imbalance': r(avg_node_imbalance, 6),
        'average_curvature': r(average_curvature, 5),
        'max_curvature': r(max_curvature, 5),
        'resilience_score': r(resilience_score, 5),
        'edge_flows': [round(f, 3) for f in edge_flows],
        'node_potentials': [r(v, 5) for v in node_potentials],
        'raw_potentials': [r(v, 5) for v in raw_potentials],
        'chebyshev_coefficients': [round(c, 6) for c in cheb_coeffs],
        'num_nodes': num_nodes,
        'num_edges': num_edges,
        'chebyshev_degree': degree
    }
    return out