from collections import defaultdict


MAX_VARIABLES = 5000
# Maximum number of 2-CNF clauses allowed
MAX_CLAUSES = 50000
# Minimum and maximum weight values for clauses
MIN_WEIGHT = 1
MAX_WEIGHT = 1000
# Base maximum iterations for local search optimization
BASE_MAX_ITERATIONS = 100
# Multiplier for calculating max iterations based on problem size
ITERATIONS_PER_VARIABLE = 10


class ImplicationGraph:
    """Directed graph for 2-SAT implications."""

    def __init__(self, num_vertices):
        """Initialize with specified vertices."""
        self.num_vertices = num_vertices
        self.adj = defaultdict(list)
        self.adj_transpose = defaultdict(list)
        self.edge_count = 0

    def add_edge(self, u, v):
        """Add directed edge from u to v."""
        if v not in self.adj[u]:
            self.adj[u].append(v)
            self.edge_count += 1
        if u not in self.adj_transpose[v]:
            self.adj_transpose[v].append(u)

    def get_neighbors(self, vertex):
        """Get outgoing neighbors."""
        return self.adj.get(vertex, [])

    def get_transpose_neighbors(self, vertex):
        """Get incoming neighbors from transpose."""
        return self.adj_transpose.get(vertex, [])


class SCCFinder:
    """Find strongly connected components using Kosaraju algorithm."""

    def __init__(self, graph):
        """Initialize with graph."""
        self.graph = graph
        self.visited = [False] * graph.num_vertices
        self.finish_order = []
        self.component_id = [-1] * graph.num_vertices
        self.num_components = 0

    def dfs_first_pass(self, start_vertex):
        """First DFS to compute finish times."""
        stack = [(start_vertex, False)]

        while stack:
            vertex, processed = stack.pop()

            if processed:
                self.finish_order.append(vertex)
                continue

            if self.visited[vertex]:
                continue

            self.visited[vertex] = True
            stack.append((vertex, True))

            for neighbor in reversed(self.graph.get_neighbors(vertex)):
                if not self.visited[neighbor]:
                    stack.append((neighbor, False))

    def dfs_second_pass(self, start_vertex, comp_id):
        """Second DFS on transpose to find SCCs."""
        stack = [start_vertex]

        while stack:
            vertex = stack.pop()

            if self.component_id[vertex] != -1:
                continue

            self.component_id[vertex] = comp_id

            for neighbor in self.graph.get_transpose_neighbors(vertex):
                if self.component_id[neighbor] == -1:
                    stack.append(neighbor)

    def find_sccs(self):
        """Execute Kosaraju algorithm."""
        for vertex in range(self.graph.num_vertices):
            if not self.visited[vertex]:
                self.dfs_first_pass(vertex)

        comp_id = 0
        for i in range(len(self.finish_order) - 1, -1, -1):
            vertex = self.finish_order[i]
            if self.component_id[vertex] == -1:
                self.dfs_second_pass(vertex, comp_id)
                comp_id += 1

        self.num_components = comp_id
        return self.component_id, self.num_components


class CardinalityValidator:
    """Validates cardinality constraints."""

    @staticmethod
    def validate_structure(cardinality_constraints):
        """Validate cardinality constraint structure."""
        if not isinstance(cardinality_constraints, list):
            return {"error": "cardinality_constraints must be list"}

        for constraint in cardinality_constraints:
            if not isinstance(constraint, dict):
                return {"error": "each cardinality constraint must be dictionary"}

            if "variables" not in constraint or "count" not in constraint:
                return {"error": "each cardinality constraint must have 'variables' and 'count' keys"}

            if not isinstance(constraint["variables"], list):
                return {"error": "cardinality constraint 'variables' must be list"}

            if not isinstance(constraint["count"], int):
                return {"error": "cardinality constraint 'count' must be integer"}

            if len(constraint["variables"]) == 0:
                return {"error": "cardinality constraint 'variables' cannot be empty"}

            if len(constraint["variables"]) != len(set(constraint["variables"])):
                return {"error": "cardinality constraint 'variables' cannot have duplicates"}

            if constraint["count"] < 0:
                return {"error": "cardinality constraint 'count' cannot be negative"}

            if constraint["count"] > len(constraint["variables"]):
                return {"error": "cardinality constraint 'count' cannot exceed variable count"}

        return None

    @staticmethod
    def validate_indices(cardinality_constraints, num_variables):
        """Validate variable indices in cardinality constraints."""
        for constraint in cardinality_constraints:
            for var_idx in constraint["variables"]:
                if not isinstance(var_idx, int) or var_idx < 0 or var_idx >= num_variables:
                    return {"error": "cardinality constraint variable indices must be in range [0, num_variables-1]"}
        return None

    @staticmethod
    def check_feasibility(cardinality_constraints, forced_assignments):
        """Check if cardinality constraints are feasible with forced assignments."""
        for constraint in cardinality_constraints:
            variables = constraint["variables"]
            required_count = constraint["count"]

            forced_true_count = 0
            forced_false_count = 0
            unforced_count = 0

            for var_idx in variables:
                key_str = str(var_idx)
                if key_str in forced_assignments:
                    if forced_assignments[key_str]:
                        forced_true_count += 1
                    else:
                        forced_false_count += 1
                else:
                    unforced_count += 1

            if forced_true_count > required_count:
                return {"error": "cardinality constraints conflict with forced_assignments"}

            if forced_true_count + unforced_count < required_count:
                return {"error": "cardinality constraints conflict with forced_assignments"}

        return None


class InputValidator:
    """Validates all input parameters."""

    @staticmethod
    def validate_all(num_variables, clauses, clause_weights, forced_assignments, optimization_mode, cardinality_constraints):
        """Perform comprehensive validation."""
        # Validate num_variables
        if not isinstance(num_variables, int) or num_variables < 1 or num_variables > MAX_VARIABLES:
            return {"error": f"num_variables must be integer between 1 and {MAX_VARIABLES}"}

        # Validate clauses
        if not isinstance(clauses, list) or len(clauses) > MAX_CLAUSES:
            return {"error": f"clauses must be list with length 0 to {MAX_CLAUSES}"}

        for clause in clauses:
            if not isinstance(clause, list) or len(clause) != 2:
                return {"error": "each clause must contain exactly 2 literals"}

            for literal in clause:
                if not isinstance(literal, list) or len(literal) != 2:
                    return {"error": "each literal must be list [variable_index, is_negated]"}

                var_idx, is_neg = literal[0], literal[1]

                if not isinstance(var_idx, int) or var_idx < 0 or var_idx >= num_variables:
                    return {"error": "variable_index must be integer in range [0, num_variables-1]"}

                if not isinstance(is_neg, bool):
                    return {"error": "is_negated must be boolean True or False"}

            if clause[0][0] == clause[1][0]:
                return {"error": "clause cannot contain same variable twice"}

        # Validate clause_weights
        if not isinstance(clause_weights, list) or len(clause_weights) != len(clauses):
            return {"error": "clause_weights length must equal clauses length"}

        for weight in clause_weights:
            if not isinstance(weight, int) or weight < MIN_WEIGHT or weight > MAX_WEIGHT:
                return {"error": f"each weight must be integer between {MIN_WEIGHT} and {MAX_WEIGHT}"}

        # Validate forced_assignments
        if not isinstance(forced_assignments, dict):
            return {"error": "forced_assignments must be dictionary"}

        for key, value in forced_assignments.items():
            if not isinstance(key, str):
                return {"error": "forced_assignments keys must be string"}

            try:
                key_int = int(key)
            except (ValueError, TypeError):
                return {"error": f"forced_assignments keys must represent integers in range [0, num_variables-1]"}

            if not (0 <= key_int < num_variables):
                return {"error": f"forced_assignments keys must represent integers in range [0, num_variables-1]"}

            if not isinstance(value, bool):
                return {"error": "forced_assignments values must be boolean"}

        # Validate optimization_mode
        if optimization_mode not in ["satisfiability", "weighted"]:
            return {"error": "optimization_mode must be 'satisfiability' or 'weighted'"}

        # Validate cardinality_constraints
        card_error = CardinalityValidator.validate_structure(cardinality_constraints)
        if card_error is not None:
            return card_error

        card_idx_error = CardinalityValidator.validate_indices(cardinality_constraints, num_variables)
        if card_idx_error is not None:
            return card_idx_error

        card_feasibility_error = CardinalityValidator.check_feasibility(cardinality_constraints, forced_assignments)
        if card_feasibility_error is not None:
            return card_feasibility_error

        return None


class TwoSATCore:
    """Core 2-SAT solver implementation."""

    def __init__(self, num_variables, clauses, clause_weights, forced_assignments):
        """Initialize solver."""
        self.num_variables = num_variables
        self.clauses = clauses
        self.clause_weights = clause_weights
        self.forced_assignments = forced_assignments
        self.graph = ImplicationGraph(2 * num_variables)
        self.assignment = []
        self.scc_count = 0
        self.forced_count = len(forced_assignments)

        self._build_graph()

    def _literal_to_vertex(self, var_idx, is_negated):
        """Convert literal to vertex index."""
        return 2 * var_idx + (1 if is_negated else 0)

    def _negate_vertex(self, vertex):
        """Get negation of vertex."""
        return vertex ^ 1

    def _build_graph(self):
        """Construct implication graph."""
        for clause in self.clauses:
            var1, neg1 = clause[0][0], clause[0][1]
            var2, neg2 = clause[1][0], clause[1][1]

            v1 = self._literal_to_vertex(var1, neg1)
            v2 = self._literal_to_vertex(var2, neg2)

            self.graph.add_edge(self._negate_vertex(v1), v2)
            self.graph.add_edge(self._negate_vertex(v2), v1)

        for key, value in self.forced_assignments.items():
            var_idx = int(key)
            true_vertex = self._literal_to_vertex(var_idx, False)
            false_vertex = self._literal_to_vertex(var_idx, True)

            if value:
                self.graph.add_edge(false_vertex, true_vertex)
            else:
                self.graph.add_edge(true_vertex, false_vertex)

    def solve(self):
        """Solve 2-SAT instance."""
        scc_finder = SCCFinder(self.graph)
        component_ids, self.scc_count = scc_finder.find_sccs()

        for var_idx in range(self.num_variables):
            pos = 2 * var_idx
            neg = 2 * var_idx + 1

            if component_ids[pos] == component_ids[neg]:
                return False, component_ids

        self.assignment = []
        for var_idx in range(self.num_variables):
            pos = 2 * var_idx
            neg = 2 * var_idx + 1
            self.assignment.append(component_ids[pos] > component_ids[neg])

        for key, value in self.forced_assignments.items():
            var_idx = int(key)
            self.assignment[var_idx] = value

        return True, component_ids


class CardinalityEvaluator:
    """Evaluates cardinality constraint satisfaction."""

    @staticmethod
    def evaluate_cardinality(cardinality_constraints, assignment):
        """Evaluate all cardinality constraints."""
        details = []
        all_satisfied = True

        for idx, constraint in enumerate(cardinality_constraints):
            variables = constraint["variables"]
            required_count = constraint["count"]

            assigned_count = sum(1 for var_idx in variables if assignment[var_idx])
            satisfied = assigned_count == required_count

            details.append({
                "constraint_index": idx,
                "satisfied": satisfied,
                "assigned_count": assigned_count,
                "required_count": required_count
            })

            if not satisfied:
                all_satisfied = False

        return details, all_satisfied


class CardinalityAdjuster:
    """Adjusts assignment to satisfy cardinality constraints."""

    @staticmethod
    def adjust_for_cardinality(assignment, cardinality_constraints, forced_assignments):
        """Adjust unforced variables to satisfy cardinality constraints."""
        adjusted = assignment[:]

        for constraint in cardinality_constraints:
            variables = constraint["variables"]
            required_count = constraint["count"]

            current_count = 0
            unforced_indices = []

            for var_idx in variables:
                key_str = str(var_idx)
                if key_str in forced_assignments:
                    if forced_assignments[key_str]:
                        current_count += 1
                else:
                    unforced_indices.append(var_idx)

            needed_true = required_count - current_count

            for var_idx in unforced_indices:
                if needed_true > 0:
                    adjusted[var_idx] = True
                    needed_true -= 1
                else:
                    adjusted[var_idx] = False

        return adjusted


class ClauseEvaluator:
    """Evaluates clause satisfaction."""

    @staticmethod
    def evaluate_literal(var_value, is_negated):
        """Check if literal is satisfied."""
        return (not is_negated and var_value) or (is_negated and not var_value)

    @staticmethod
    def evaluate_clauses(clauses, clause_weights, assignment):
        """Evaluate all clauses and compute metrics."""
        satisfied_indices = []
        unsatisfied_indices = []
        total_weight = 0

        for idx, clause in enumerate(clauses):
            var1, neg1 = clause[0][0], clause[0][1]
            var2, neg2 = clause[1][0], clause[1][1]

            lit1_sat = ClauseEvaluator.evaluate_literal(assignment[var1], neg1)
            lit2_sat = ClauseEvaluator.evaluate_literal(assignment[var2], neg2)

            if lit1_sat or lit2_sat:
                satisfied_indices.append(idx)
                total_weight += clause_weights[idx]
            else:
                unsatisfied_indices.append(idx)

        return satisfied_indices, unsatisfied_indices, total_weight


class ConflictClusterFinder:
    """Identifies conflict clusters in variable assignments."""

    def __init__(self, num_variables, clauses, assignment):
        """Initialize conflict finder."""
        self.num_variables = num_variables
        self.clauses = clauses
        self.assignment = assignment

    def find_clusters(self):
        """Find minimal conflict clusters."""
        conflict_clusters = []
        seen_pairs = set()

        for clause_idx, clause in enumerate(self.clauses):
            var1, neg1 = clause[0][0], clause[0][1]
            var2, neg2 = clause[1][0], clause[1][1]

            lit1_sat = ClauseEvaluator.evaluate_literal(self.assignment[var1], neg1)
            lit2_sat = ClauseEvaluator.evaluate_literal(self.assignment[var2], neg2)

            if not (lit1_sat or lit2_sat):
                pair_key = tuple(sorted([var1, var2]))
                if pair_key not in seen_pairs:
                    conflict_clusters.append([var1, var2])
                    seen_pairs.add(pair_key)

        return conflict_clusters


class WeightedLocalSearch:
    """Local search optimizer for weighted mode."""

    def __init__(self, num_variables, clauses, clause_weights, assignment, cardinality_constraints):
        """Initialize optimizer."""
        self.num_variables = num_variables
        self.clauses = clauses
        self.clause_weights = clause_weights
        self.assignment = assignment[:]
        self.cardinality_constraints = cardinality_constraints
        self.best_weight = 0

        # Calculate max_iterations based on problem size
        # Larger problems get more iterations for better solution quality
        self.max_iterations = min(BASE_MAX_ITERATIONS, num_variables * ITERATIONS_PER_VARIABLE)

        self._compute_initial_weight()

    def _compute_initial_weight(self):
        """Compute initial total weight."""
        _, _, self.best_weight = ClauseEvaluator.evaluate_clauses(
            self.clauses, self.clause_weights, self.assignment
        )

    def _compute_weight_after_flip(self, var_idx):
        """Compute weight if variable is flipped."""
        test_assignment = self.assignment[:]
        test_assignment[var_idx] = not test_assignment[var_idx]

        _, _, total_weight = ClauseEvaluator.evaluate_clauses(
            self.clauses, self.clause_weights, test_assignment
        )

        card_details, card_satisfied = CardinalityEvaluator.evaluate_cardinality(
            self.cardinality_constraints, test_assignment
        )

        if not card_satisfied:
            return self.best_weight, self.assignment

        return total_weight, test_assignment

    def optimize(self):
        """Run local search optimization."""
        iteration = 0
        improved = True

        while improved and iteration < self.max_iterations:
            improved = False
            iteration += 1

            for var_idx in range(self.num_variables):
                new_weight, new_assignment = self._compute_weight_after_flip(var_idx)

                if new_weight > self.best_weight:
                    self.assignment = new_assignment
                    self.best_weight = new_weight
                    improved = True
                    break

        return self.assignment


class ResultBuilder:
    """Builds output dictionary."""

    @staticmethod
    def build_satisfiable_result(assignment, satisfied_count, total_weight, 
                                  unsatisfied_indices, scc_count, edge_count,
                                  cardinality_details, all_cardinality_satisfied,
                                  conflict_clusters, forced_count):
        """Build result for satisfiable instance."""
        return {
            "satisfiable": True,
            "assignment": assignment,
            "satisfied_clauses": satisfied_count,
            "total_weight": total_weight,
            "unsatisfied_clauses": unsatisfied_indices,
            "strongly_connected_components": scc_count,
            "implication_graph_edges": edge_count,
            "cardinality_satisfied": all_cardinality_satisfied,
            "cardinality_details": cardinality_details,
            "conflict_clusters": conflict_clusters,
            "forced_assignments_applied": forced_count
        }

    @staticmethod
    def build_unsatisfiable_result(num_clauses, scc_count, edge_count):
        """Build result for unsatisfiable instance."""
        return {
            "satisfiable": False,
            "assignment": [],
            "satisfied_clauses": 0,
            "total_weight": 0,
            "unsatisfied_clauses": list(range(num_clauses)),
            "strongly_connected_components": scc_count,
            "implication_graph_edges": edge_count,
            "cardinality_satisfied": False,
            "cardinality_details": [],
            "conflict_clusters": [],
            "forced_assignments_applied": 0
        }


def main(num_variables, clauses, clause_weights, forced_assignments, optimization_mode, cardinality_constraints):
    """
    Solve weighted 2-SAT with cardinality constraints.

    Returns dict with satisfiability, assignment, metrics, cardinality details, or error.
    """
    validation_error = InputValidator.validate_all(
        num_variables, clauses, clause_weights, forced_assignments, optimization_mode, cardinality_constraints
    )

    if validation_error is not None:
        return validation_error

    try:
        solver = TwoSATCore(num_variables, clauses, clause_weights, forced_assignments)

        is_sat, component_ids = solver.solve()

        if not is_sat:
            result = ResultBuilder.build_unsatisfiable_result(
                len(clauses), solver.scc_count, solver.graph.edge_count
            )
            return result

        assignment = solver.assignment

        adjusted_assignment = CardinalityAdjuster.adjust_for_cardinality(
            assignment, cardinality_constraints, forced_assignments
        )
        assignment = adjusted_assignment

        card_details, card_satisfied = CardinalityEvaluator.evaluate_cardinality(
            cardinality_constraints, assignment
        )

        if not card_satisfied:
            result = ResultBuilder.build_unsatisfiable_result(
                len(clauses), solver.scc_count, solver.graph.edge_count
            )
            return result

        if optimization_mode == "weighted" and len(clauses) > 0:
            optimizer = WeightedLocalSearch(num_variables, clauses, clause_weights, assignment, cardinality_constraints)
            assignment = optimizer.optimize()

        satisfied_indices, unsatisfied_indices, total_weight = ClauseEvaluator.evaluate_clauses(
            clauses, clause_weights, assignment
        )

        card_details, card_satisfied = CardinalityEvaluator.evaluate_cardinality(
            cardinality_constraints, assignment
        )

        conflict_finder = ConflictClusterFinder(num_variables, clauses, assignment)
        conflict_clusters = conflict_finder.find_clusters()

        result = ResultBuilder.build_satisfiable_result(
            assignment,
            len(satisfied_indices),
            total_weight,
            unsatisfied_indices,
            solver.scc_count,
            solver.graph.edge_count,
            card_details,
            card_satisfied,
            conflict_clusters,
            solver.forced_count
        )

        return result

    except Exception as e:
        return {"error": "internal error: " + str(e)}


if __name__ == "__main__":
    num_variables = 4
    clauses = [
        [[0, False], [1, False]],
        [[1, True], [2, False]],
        [[2, True], [3, False]]
    ]
    clause_weights = [10, 20, 30]
    forced_assignments = {"2": True}
    optimization_mode = "weighted"
    cardinality_constraints = [
        {"variables": [0, 1, 2, 3], "count": 2}
    ]

    result = main(num_variables, clauses, clause_weights, forced_assignments, optimization_mode, cardinality_constraints)
    print(result)