def compute_advanced_airflow_network(num_nodes: int, edges: list, boundary_conditions: list) -> dict:
    from math import fabs
    # Validation
    if not isinstance(num_nodes, int) or num_nodes <= 0:
        return {"error": "Number of nodes must be a positive integer."}
    if not isinstance(edges, list) or any((not isinstance(e, list) or len(e) < 3) for e in edges):
        return {"error": "Edges must be a list of lists with at least 3 elements each."}
    if not isinstance(boundary_conditions, list) or len(boundary_conditions) != num_nodes:
        return {"error": "Boundary conditions must be a list of length equal to number of nodes."}
    if any((not isinstance(b, (int, float))) for b in boundary_conditions):
        return {"error": "All boundary conditions must be numeric values."}

    # Constants and helper trigs: PI with 15 decimals
    PI = 3.141592653589793
    def normalize_angle(a):
        # normalize to [-pi,pi]
        while a > PI:
            a -= 2*PI
        while a < -PI:
            a += 2*PI
        return a
    def cos_taylor(x):
        # x in radians, normalized
        x = normalize_angle(x)
        # compute cos via Taylor up to 20 terms
        term = 1.0
        s = term
        x2 = x*x
        for n in range(1,20):
            term *= -x2/((2*n-1)*(2*n))
            s += term
        return s

    # Chebyshev first-kind recurrence
    def chebyshev_T(n, x):
        if n <= 0:
            return 1.0
        if n == 1:
            return x
        T0 = 1.0
        T1 = x
        for k in range(2, n+1):
            Tn = 2.0 * x * T1 - T0
            T0, T1 = T1, Tn
        return T1

    # Chebyshev-Gauss nodes (roots of T_n): return empty if n<=0
    def chebyshev_nodes(n):
        if n <= 0:
            return []
        # roots of T_n: x_k = cos((2k-1)pi/(2n)) k=1..n
        nodes = []
        for k in range(1, n+1):
            angle = (2*k-1)*PI/(2.0*n)
            nodes.append(cos_taylor(angle))
        return nodes

    # Discrete Chebyshev transform (type I-like) from samples at chebyshev nodes of degree N-1 (n samples)
    def discrete_chebyshev_coeffs(samples):
        n = len(samples)
        if n == 0:
            return []
        # compute coefficients c_k = (factor) * sum_{j} samples[j] * T_k(x_j)
        coeffs = []
        for k in range(0, n):
            s = 0.0
            for j in range(n):
                xj = cheb_nodes[j]
                s += samples[j] * chebyshev_T(k, xj)
            factor = (1.0/n) if k==0 else (2.0/n)
            coeffs.append(factor * s)
        return coeffs

    # Clenshaw algorithm for evaluation given coefficients at x
    def clenshaw_eval(coeffs, x):
        if not coeffs:
            return 0.0
        if len(coeffs) == 1:
            return coeffs[0]
        b_kplus1 = 0.0
        b_kplus2 = 0.0
        n = len(coeffs)-1
        for j in range(n, 0, -1):
            b_k = 2.0 * x * b_kplus1 - b_kplus2 + coeffs[j]
            b_kplus2, b_kplus1 = b_kplus1, b_k
        return coeffs[0] + x * b_kplus1 - b_kplus2

    # Derivative coefficients per requirement 9
    def derivative_coeffs(coeffs):
        m = len(coeffs)
        if m <= 1:
            return [0.0]
        d = [0.0]* (m-1)
        for k in range(m-1):
            s = 0.0
            j = k+1
            while j < m:
                s += j * coeffs[j] * (1 if ((j - k) % 2)==1 else -1)
                j += 1
            d[k] = s
        # halve first coefficient
        d[0] *= 0.5
        return d

    # Map to [-1,1] linear normalization, return zeros if range below threshold
    def map_to_domain(vals):
        mn = min(vals)
        mx = max(vals)
        if mx - mn < 1e-10:
            return [0.0]*len(vals)
        return [ -1.0 + 2.0*(v - mn)/(mx - mn) for v in vals ]

    # Linear interpolation sampling between potentials mapped
    def linear_sample(potentials, mapped_index):
        # mapped_index in [0, num_nodes-1]
        if mapped_index >= num_nodes - 1:
            return potentials[-1]
        if mapped_index <= 0:
            return potentials[0]
        idx = mapped_index
        i = int(idx)
        frac = idx - i
        return potentials[i]*(1-frac) + potentials[i+1]*frac

    # Build adjacency and valid edges per constraints
    adj = [[] for _ in range(num_nodes)]
    edges_list = []
    for e in edges:
        u, v, cap = e[0], e[1], e[2]
        if isinstance(u, int) and isinstance(v, int) and 0 <= u < num_nodes and 0 <= v < num_nodes:
            adj[u].append((v, float(cap)))
            edges_list.append((u, v, float(cap)))
    num_edges = len(edges_list)

    # Raw potentials: boundary + 0.3 * capacity-weighted average of neighbor boundary values only if total capacity exceeds threshold
    raw_potentials = []
    for i in range(num_nodes):
        neigh = adj[i]
        total_cap = sum(c for _,c in neigh)
        if total_cap > 1e-10:
            weighted = sum(boundary_conditions[j]*c for j,c in [(v,cap) for v,cap in neigh])
            avg = weighted / total_cap
            raw = boundary_conditions[i] + 0.3 * avg
        else:
            raw = boundary_conditions[i]
        raw_potentials.append(float(raw))

    # Domain mapping for interpolation
    mapped_raw = map_to_domain(raw_potentials)
    # Node position mapping from index to chebyshev domain
    node_positions = []
    for i in range(num_nodes):
        x = -1.0 + 2.0 * i / max(1, num_nodes - 1)
        node_positions.append(x)

    # Choose degree half nodes clamped between 4 and 12
    degree = max(4, min(12, num_nodes//2))
    interp_n = degree + 1

    # Interpolator nodes: generate interp_n chebyshev nodes
    cheb_nodes = chebyshev_nodes(interp_n)
    # Map each cheb node to index space [0, num_nodes-1] and sample potentials by linear interpolation between mapped potentials
    sampled = []
    for x in cheb_nodes:
        # map x in [-1,1] to index space
        mapped_index = (x + 1.0) * 0.5 * (num_nodes - 1)
        if mapped_index >= num_nodes - 1:
            val = raw_potentials[-1]
        elif mapped_index <= 0:
            val = raw_potentials[0]
        else:
            i = int(mapped_index)
            frac = mapped_index - i
            val = raw_potentials[i]*(1-frac) + raw_potentials[i+1]*frac
        sampled.append(val)

    # Compute discrete chebyshev coefficients
    cheb_coeffs = discrete_chebyshev_coeffs(sampled)

    # Evaluate smoothing potentials via Clenshaw at each node position and map back to original domain
    # We evaluated over mapped domain [-1,1], but raw_potentials original domain; we will get smoothed mapped values then remap to original domain
    # First evaluate at node_positions (which already in [-1,1])
    smoothed_mapped = []
    for x in node_positions:
        smoothed_mapped.append(clenshaw_eval(cheb_coeffs, x))
    # Map smoothed_mapped range back to original raw potentials range
    mn_raw = min(raw_potentials)
    mx_raw = max(raw_potentials)
    if mx_raw - mn_raw < 1e-10:
        node_potentials = [mn_raw]*num_nodes
    else:
        # smoothed_mapped in some range; map from its min/max to original
        smn = min(smoothed_mapped)
        smx = max(smoothed_mapped)
        if abs(smx - smn) < 1e-10:
            node_potentials = [mn_raw + 0.5*(mx_raw-mn_raw)]*num_nodes
        else:
            node_potentials = [ mn_raw + (v - smn)*(mx_raw - mn_raw)/(smx - smn) for v in smoothed_mapped ]

    # Edge flows: capacity * (potential_source - potential_dest)
    edge_flows = []
    for (u,v,cap) in edges_list:
        f = cap * (node_potentials[u] - node_potentials[v])
        edge_flows.append(f)

    # Energetics and metrics
    total_energy = sum((cap*(node_potentials[u]-node_potentials[v]))**2 for (u,v,cap) in edges_list)
    total_abs_flow = sum(abs(f) for f in edge_flows)
    network_efficiency = (total_abs_flow / (sum(cap for _,_,cap in edges_list)+1e-12)) if edges_list else 0.0
    # Smoothness: mean of absolute derivative values across node positions
    deriv_coeffs = derivative_coeffs(cheb_coeffs)
    derivatives = []
    for x in node_positions:
        derivatives.append(abs(clenshaw_eval(deriv_coeffs, x)))
    average_smoothness = sum(derivatives)/len(derivatives) if derivatives else 0.0
    # Flow variance
    mean_flow = sum(edge_flows)/len(edge_flows) if edge_flows else 0.0
    flow_variance = sum((f-mean_flow)**2 for f in edge_flows)/len(edge_flows) if edge_flows else 0.0
    # Max potential gradient
    max_potential_gradient = 0.0
    for (u,v,_) in edges_list:
        max_potential_gradient = max(max_potential_gradient, abs(node_potentials[u]-node_potentials[v]))
    # Approximation error: mean abs difference between raw and smoothed node potentials
    approximation_error = sum(abs(raw_potentials[i]-node_potentials[i]) for i in range(num_nodes))/num_nodes
    # Spectral entropy per spec
    spectral_entropy = 0.0
    total_abs = sum(abs(f) for f in edge_flows)
    if total_abs > 0:
        for f in edge_flows:
            prob = abs(f)/total_abs
            if prob > 1e-10:
                spectral_entropy += - (prob * (prob**0.5))
    # Convergence rate: mean of ratios abs(coeff[i]/coeff[i-1]) for consecutive coefficients where denom>1e-10
    ratios = []
    for i in range(1, len(cheb_coeffs)):
        denom = abs(cheb_coeffs[i-1])
        if denom > 1e-10:
            ratios.append(abs(cheb_coeffs[i])/denom)
    convergence_rate = sum(ratios)/len(ratios) if len(ratios)>0 else 0.0

    # Node imbalance tracking
    imbalances = [0.0]*num_nodes
    for idx, (u,v,cap) in enumerate(edges_list):
        f = edge_flows[idx]
        imbalances[u] -= f
        imbalances[v] += f
    abs_imbs = [abs(x) for x in imbalances]
    max_node_imbalance = max(abs_imbs) if abs_imbs else 0.0
    avg_node_imbalance = sum(abs_imbs)/len(abs_imbs) if abs_imbs else 0.0

    # Curvature via finite difference on derivative function: second derivative approx (deriv(x+h)-deriv(x-h))/(2h)
    h = 0.001
    curvatures = []
    for x in node_positions:
        if abs(x+h) <= 1.0 and abs(x-h) <= 1.0:
            dph = clenshaw_eval(deriv_coeffs, x+h)
            dmh = clenshaw_eval(deriv_coeffs, x-h)
            sec = (dph - dmh) / (2.0 * h)
            curvatures.append(abs(sec))
    average_curvature = sum(curvatures)/len(curvatures) if curvatures else 0.0
    max_curvature = max(curvatures) if curvatures else 0.0

    # Resilience score: 1.0 / (1.0 + gradient_variance) where gradient_variance is variance of absolute potential differences across all edges
    grads = [abs(node_potentials[u]-node_potentials[v]) for (u,v,_) in edges_list]
    if grads:
        m = sum(grads)/len(grads)
        gradient_variance = sum((g-m)**2 for g in grads)/len(grads)
    else:
        gradient_variance = 0.0
    resilience_score = 1.0/(1.0+gradient_variance)

    # Composite flow metric: 0.4*energy + 2.0*efficiency + -0.1*smoothness
    optimized_flow_metric = 0.4*total_energy + 2.0*network_efficiency - 0.1*average_smoothness

    # Rounding at final stage per spec
    def r(v, digits):
        return round(v, digits)
    out = {
        'optimized_flow_metric': r(optimized_flow_metric, 5),
        'total_energy': r(total_energy, 4),
        'network_efficiency': r(network_efficiency, 4),
        'average_smoothness': r(average_smoothness, 4),
        'flow_variance': r(flow_variance, 5),
        'max_potential_gradient': r(max_potential_gradient, 5),
        'approximation_error': r(approximation_error, 7),
        'total_flow': r(total_abs_flow, 5),
        'spectral_entropy': r(spectral_entropy, 6),
        'convergence_rate': r(convergence_rate, 6),
        'max_node_imbalance': r(max_node_imbalance, 5),
        'avg_node_imbalance': r(avg_node_imbalance, 6),
        'average_curvature': r(average_curvature, 5),
        'max_curvature': r(max_curvature, 5),
        'resilience_score': r(resilience_score, 5),
        'edge_flows': [r(f,3) for f in edge_flows],
        'node_potentials': [r(v,5) for v in node_potentials],
        'raw_potentials': [r(v,5) for v in raw_potentials],
        'chebyshev_coefficients': [r(v,6) for v in cheb_coeffs],
        'num_nodes': num_nodes,
        'num_edges': num_edges,
        'chebyshev_degree': degree
    }
    return out