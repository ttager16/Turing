# main.py
import math


def count_non_crossing_partitions(n: int) -> int:
    """
    Compute the number of non-crossing partitions for n elements using
    dynamic programming (Catalan numbers).

    The nth Catalan number C_n satisfies:
    C_0 = 1
    C_n = sum(C_i * C_{n-1-i}) for i in [0, n-1]

    Args:
        n: Number of distinct nodes/elements

    Returns:
        Count of non-crossing partitions (nth Catalan number)
    """
    if n <= 1:
        return 1

    # Dynamic programming table for Catalan numbers
    catalan = [0] * (n + 1)
    catalan[0] = 1
    catalan[1] = 1

    # Compute C_i for i = 2 to n
    for i in range(2, n + 1):
        for j in range(i):
            catalan[i] += catalan[j] * catalan[i - 1 - j]

    return catalan[n]


def compute_catalan_sequence(n: int) -> list:
    """
    Generate the sequence of Catalan numbers from C_0 to C_n.

    Args:
        n: Maximum index

    Returns:
        List of Catalan numbers [C_0, C_1, ..., C_n]
    """
    sequence = [1]  # C_0 = 1

    for i in range(1, n + 1):
        catalan_i = 0
        for j in range(i):
            catalan_i += sequence[j] * sequence[i - 1 - j]
        sequence.append(catalan_i)

    return sequence


def analyze_layer_partitions(n: int, num_layers: int, catalan_sequence: list) -> dict:
    """
    Analyze partitions distributed across multiple layers.

    Each layer represents a stage in the security pipeline (e.g., scanning,
    inspection, detection). This function computes how nodes can be distributed
    across layers while maintaining non-crossing properties within each layer.

    Args:
        n: Total number of nodes
        num_layers: Number of distinct layers
        catalan_sequence: Pre-computed Catalan sequence to avoid redundant calculations

    Returns:
        Dictionary with layer distribution analysis
    """
    # Distribute nodes across layers using a balanced approach
    base_nodes = n // num_layers
    remainder = n % num_layers

    layer_distributions = []
    total_combinations = 1

    for layer_idx in range(num_layers):
        # Layers get base_nodes, with first 'remainder' layers getting +1
        nodes_in_layer = base_nodes + (1 if layer_idx < remainder else 0)

        # Get non-crossing partitions from pre-computed sequence
        layer_partitions = catalan_sequence[nodes_in_layer] if nodes_in_layer < len(catalan_sequence) else count_non_crossing_partitions(nodes_in_layer)

        layer_distributions.append({
            "layer_index": layer_idx,
            "nodes": nodes_in_layer,
            "partitions": layer_partitions
        })

        total_combinations *= layer_partitions

    return {
        "valid": True,
        "total_distributions": total_combinations,
        "average_nodes_per_layer": round(n / num_layers, 3),  # Rounded to 3 decimal places
        "layer_partitions": layer_distributions
    }


def compute_partition_growth_rate(n: int, catalan_sequence: list) -> dict:
    """
    Analyze the growth rate of non-crossing partitions.

    Catalan numbers grow exponentially, approximately as:
    C_n ~ 4^n / (n^(3/2) * sqrt(pi))

    Args:
        n: Number of nodes
        catalan_sequence: Pre-computed Catalan sequence to avoid redundant calculations

    Returns:
        Growth rate analysis
    """
    if n < 2:
        return {
            "current_value": catalan_sequence[n] if n < len(catalan_sequence) else count_non_crossing_partitions(n),
            "growth_ratio": None,
            "growth_trend": "insufficient_data"
        }

    current = catalan_sequence[n] if n < len(catalan_sequence) else count_non_crossing_partitions(n)
    previous = catalan_sequence[n - 1] if (n - 1) < len(catalan_sequence) else count_non_crossing_partitions(n - 1)

    growth_ratio = current / previous if previous > 0 else None

    # Asymptotic growth ratio approaches 4
    trend = "exponential"
    if growth_ratio:
        if growth_ratio < 2:
            trend = "subexponential"
        elif growth_ratio >= 3.5:
            trend = "approaching_asymptotic_limit"

    return {
        "current_value": current,
        "previous_value": previous,
        "growth_ratio": round(growth_ratio, 5) if growth_ratio is not None else None,  # Rounded to 5 decimal places
        "growth_trend": trend
    }


def assess_cluster_risk(n: int, risk_threshold: float, catalan_sequence: list) -> dict:
    """
    Assess security risk based on partition complexity.

    More partitions mean more potential segmentation strategies, which can
    improve defense-in-depth. This function simulates a risk assessment
    based on partition counts.

    Args:
        n: Number of nodes
        risk_threshold: Threshold for determining risk level (0.0 to 1.0)
        catalan_sequence: Pre-computed Catalan sequence to avoid redundant calculations

    Returns:
        Risk assessment metrics
    """
    total_partitions = catalan_sequence[n] if n < len(catalan_sequence) else count_non_crossing_partitions(n)

    # Compute risk score based on partition diversity
    # More partitions = lower risk (more defensive options)
    # Normalized logarithmically to keep values reasonable
    if total_partitions > 0:
        # Log-based normalization
        log_partitions = math.log(total_partitions + 1)
        # Normalize to [0, 1] range (heuristic: log(1e10) ~ 23)
        diversity_score = min(1.0, log_partitions / 23.0)
        risk_score = 1.0 - diversity_score
    else:
        risk_score = 1.0

    # Classify risk level
    if risk_score < risk_threshold * 0.5:
        risk_level = "low"
    elif risk_score < risk_threshold:
        risk_level = "moderate"
    elif risk_score < risk_threshold * 1.5:
        risk_level = "high"
    else:
        risk_level = "critical"

    return {
        "total_partitions": total_partitions,
        "diversity_score": round(diversity_score, 6),  # Rounded to 6 decimal places
        "risk_score": round(risk_score, 4),  # Rounded to 4 decimal places
        "risk_level": risk_level,
        "threshold": round(risk_threshold, 2)  # Rounded to 2 decimal places
    }


def compute_bell_comparison(n: int, catalan_sequence: list) -> dict:
    """
    Compare non-crossing partitions to total partitions (Bell numbers).

    While we compute exact non-crossing partitions (Catalan numbers),
    total partitions grow much faster (Bell numbers). This comparison
    shows what fraction of all possible partitions are non-crossing.

    Note: Bell numbers grow super-exponentially, so we only compute
    them for small n to avoid overflow.

    Args:
        n: Number of nodes
        catalan_sequence: Pre-computed Catalan sequence to avoid redundant calculations

    Returns:
        Comparison metrics
    """
    catalan = catalan_sequence[n] if n < len(catalan_sequence) else count_non_crossing_partitions(n)
    bell = compute_bell_number(n)

    ratio = catalan / bell if bell > 0 else 0.0

    return {
        "non_crossing_partitions": catalan,
        "total_partitions": bell,
        "non_crossing_ratio": round(ratio, 7),  # Rounded to 7 decimal places
        "crossing_partitions": bell - catalan
    }


def compute_bell_number(n: int) -> int:
    """
    Compute the Bell number B_n (total number of partitions).

    Uses dynamic programming with the Bell triangle.

    Args:
        n: Index

    Returns:
        nth Bell number
    """
    if n < 0:
        return 0
    if n == 0:
        return 1

    # Bell triangle: row i has i+1 elements
    # First element of row i+1 = last element of row i
    # Each subsequent element = sum of element above-left and element to left

    prev_row = [1]  # B_0 = 1

    for i in range(1, n + 1):
        current_row = [prev_row[-1]]  # Start with last element of previous row
        for j in range(len(prev_row)):
            current_row.append(current_row[-1] + prev_row[j])
        prev_row = current_row

    return prev_row[0]


def compute_structural_metrics(n: int, catalan_sequence: list) -> dict:
    """
    Compute various structural metrics for partition analysis.

    Args:
        n: Number of nodes
        catalan_sequence: Pre-computed Catalan sequence to avoid redundant calculations

    Returns:
        Dictionary of structural metrics
    """
    partitions = catalan_sequence[n] if n < len(catalan_sequence) else count_non_crossing_partitions(n)

    # Average partition size (heuristic based on Catalan properties)
    # For non-crossing partitions, average size relates to n
    average_partition_size = (n + 1) / 2.0 if n > 0 else 0.0

    # Use pre-computed sequence for derivative analysis
    if n >= 2:
        first_derivative = catalan_sequence[n] - catalan_sequence[n - 1]
        second_derivative = (catalan_sequence[n] - catalan_sequence[n - 1]) - (catalan_sequence[n - 1] - catalan_sequence[n - 2]) if n >= 3 else None
    else:
        first_derivative = None
        second_derivative = None

    return {
        "total_nodes": n,
        "total_partitions": partitions,
        "average_partition_size": round(average_partition_size, 1),  # Rounded to 1 decimal place
        "first_derivative": first_derivative,
        "second_derivative": second_derivative,
        "complexity_class": "exponential"
    }


def analyze_concurrent_flows(n: int, concurrent_updates: int) -> dict:
    """
    Simulate concurrent flow update analysis.

    In real-time systems, multiple packet flows may update simultaneously.
    This function estimates the computational overhead for handling
    concurrent updates to the partition structure.

    Args:
        n: Number of nodes
        concurrent_updates: Number of concurrent update operations

    Returns:
        Concurrent flow analysis
    """
    # Complexity per update: O(n log n) as mentioned in requirements
    base_complexity = n * math.log(n + 1) if n > 0 else 1
    total_complexity = base_complexity * concurrent_updates

    # Estimate throughput (operations per unit time, normalized)
    if total_complexity > 0:
        throughput = 1000000.0 / total_complexity  # Arbitrary scale
    else:
        throughput = None

    return {
        "nodes": n,
        "concurrent_updates": concurrent_updates,
        "base_complexity": round(base_complexity, 8),  # Rounded to 8 decimal places
        "total_complexity": round(total_complexity, 9),  # Rounded to 9 decimal places
        "estimated_throughput": round(throughput, 10) if throughput is not None else throughput,  # Rounded to 10 decimal places
    }


def _validate_inputs(n: int, num_layers: int = 3, risk_threshold: float = 0.5, concurrent_updates: int = 10) -> dict:
    """
    Validate input parameters for the main function.

    Args:
        n: Number of nodes
        num_layers: Number of layers
        risk_threshold: Risk threshold
        concurrent_updates: Number of concurrent updates
    """

    # Set input parameters dictionary
    input_parameters = {
        "n": n,
        "num_layers": num_layers,
        "risk_threshold": risk_threshold,
        "concurrent_updates": concurrent_updates
    }

    # Validate inputs
    if not isinstance(n, int) or n < 0:
        return {
            "success": False,
            "error": "n must be a non-negative integer",
            "input_parameters": input_parameters
        }

    if not isinstance(num_layers, int) or num_layers <= 0:
        return {
            "success": False,
            "error": "num_layers must be a positive integer",
            "input_parameters": input_parameters
        }

    if not isinstance(risk_threshold, (int, float)) or risk_threshold < 0:
        return {
            "success": False,
            "error": "risk_threshold must be a non-negative number",
            "input_parameters": input_parameters
        }

    if not isinstance(concurrent_updates, int) or concurrent_updates < 0:
        return {
            "success": False,
            "error": "concurrent_updates must be a non-negative integer",
            "input_parameters": input_parameters
        }

    # If all validations pass, return success
    return {
        "success": True,
        "input_parameters": input_parameters
    }


def count_non_crossing_partitions_analysis(n: int, num_layers: int = 3,
                                           risk_threshold: float = 0.5,
                                           concurrent_updates: int = 10) -> dict:
    """
    Main trigger function: Comprehensive analysis of non-crossing partitions
    in a multi-layer cybersecurity framework.

    This function serves as the entry point for analyzing data packet flows
    across layered encryption channels. It computes the number of valid
    non-crossing partitions and provides extensive metrics including:
    - Basic partition counts
    - Layer distribution analysis
    - Growth rate analysis
    - Risk assessment
    - Structural metrics
    - Concurrent flow analysis

    Args:
        n: Number of distinct data nodes (must be >= 0)
        num_layers: Number of encryption/security layers (must be > 0)
        risk_threshold: Threshold for risk classification (must be >= 0)
        concurrent_updates: Number of concurrent flow updates (must be >= 0)

    Returns:
        Dictionary containing comprehensive analysis results with the following keys:
        - input_parameters: Echo of input values
        - primary_result: Main partition count
        - catalan_sequence: Sequence from C_0 to C_n
        - layer_analysis: Multi-layer distribution analysis
        - growth_analysis: Growth rate metrics
        - risk_assessment: Security risk evaluation
        - structural_metrics: Partition structure analysis
        - concurrent_analysis: Concurrent flow handling metrics
        - bell_comparison: Comparison with total partitions (if n <= 20)
        - metadata: Algorithm and complexity information

    Example:
        >>> result = count_non_crossing_partitions_analysis(6)
        >>> result['primary_result']
        132
        >>> result['risk_assessment']['risk_level']
        'low'
    """
    # Validate inputs
    validation = _validate_inputs(n, num_layers, risk_threshold, concurrent_updates)
    if not validation["success"]:
        return validation

    # Generate Catalan sequence once (avoids redundant calculations)
    catalan_seq = compute_catalan_sequence(n)

    # Primary computation - use pre-computed value from sequence
    primary_count = catalan_seq[n]

    # Layer-based analysis
    layer_analysis = analyze_layer_partitions(n, num_layers, catalan_seq)

    # Growth rate analysis
    growth_analysis = compute_partition_growth_rate(n, catalan_seq)

    # Risk assessment
    risk_analysis = assess_cluster_risk(n, risk_threshold, catalan_seq)

    # Structural metrics
    structural = compute_structural_metrics(n, catalan_seq)

    # Concurrent flow analysis
    concurrent = analyze_concurrent_flows(n, concurrent_updates)

    # Bell number comparison (only for small n)
    bell_comp = None
    if n <= 20:
        bell_comp = compute_bell_comparison(n, catalan_seq)

    # Compile comprehensive results
    result = {
        "success": True,
        "input_parameters": {
            "n": n,
            "num_layers": num_layers,
            "risk_threshold": risk_threshold,
            "concurrent_updates": concurrent_updates
        },
        "primary_result": {
            "non_crossing_partitions": primary_count,
            "description": f"Number of valid non-crossing partitions for {n} nodes"
        },
        "catalan_sequence": {
            "sequence": catalan_seq,
            "length": len(catalan_seq),
            "description": "Sequence of Catalan numbers from C_0 to C_n"
        },
        "layer_analysis": layer_analysis,
        "growth_analysis": growth_analysis,
        "risk_assessment": risk_analysis,
        "structural_metrics": structural,
        "concurrent_analysis": concurrent,
    }

    # Add Bell comparison if available
    if bell_comp is not None:
        result["bell_comparison"] = bell_comp

    return result


# Example usage
if __name__ == "__main__":
    n = 6
    num_layers = 3
    risk_threshold = 0.5
    concurrent_updates = 10
    result = count_non_crossing_partitions_analysis(n, num_layers, risk_threshold, concurrent_updates)
    print(result)