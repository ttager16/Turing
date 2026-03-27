from collections import defaultdict, deque
from typing import List, Tuple


class TwoSATSolver:
    def __init__(self, num_variables: int, clauses: List[List[int]]):
        self.num_variables = num_variables
        self.clauses = clauses
        self.graph = defaultdict(list)
        self.transpose_graph = defaultdict(list)
        self.scc_indices = {}
        self.num_sccs = 0
        self.visited = set()
        self.finish_stack = []
        self.current_scc_index = 0
        
    def literal_to_node(self, literal: int) -> int:
        """Convert literal to node index. Positive x maps to 2x, negative -x maps to 2x+1."""
        if literal > 0:
            return 2 * literal
        else:
            return 2 * (-literal) + 1
    
    def node_to_literal(self, node: int) -> int:
        """Convert node index back to literal."""
        if node % 2 == 0:
            return node // 2
        else:
            return -(node // 2)
    
    def build_implication_graph(self):
        """Build implication graph from clauses. Clause (a OR b) creates edges: -a -> b and -b -> a."""
        for clause in self.clauses:
            a, b = clause[0], clause[1]
            neg_a = -a
            neg_b = -b
            
            node_neg_a = self.literal_to_node(neg_a)
            node_b = self.literal_to_node(b)
            node_neg_b = self.literal_to_node(neg_b)
            node_a = self.literal_to_node(a)
            
            self.graph[node_neg_a].append(node_b)
            self.graph[node_neg_b].append(node_a)
            
            self.transpose_graph[node_b].append(node_neg_a)
            self.transpose_graph[node_a].append(node_neg_b)
    
    def dfs_first_pass(self, node: int):
        """First DFS to compute finish times."""
        self.visited.add(node)
        for neighbor in self.graph.get(node, []):
            if neighbor not in self.visited:
                self.dfs_first_pass(neighbor)
        self.finish_stack.append(node)
    
    def dfs_second_pass(self, node: int, scc_index: int):
        """Second DFS on transpose graph to assign SCC indices."""
        self.visited.add(node)
        literal = self.node_to_literal(node)
        self.scc_indices[str(literal)] = scc_index
        
        for neighbor in self.transpose_graph.get(node, []):
            if neighbor not in self.visited:
                self.dfs_second_pass(neighbor, scc_index)
    
    def kosaraju_scc(self):
        """Run Kosaraju's algorithm to find strongly connected components."""
        self.visited = set()
        self.finish_stack = []
        
        for var in range(1, self.num_variables + 1):
            for literal in [var, -var]:
                node = self.literal_to_node(literal)
                if node not in self.visited:
                    self.dfs_first_pass(node)
        
        self.visited = set()
        self.current_scc_index = 0
        
        while self.finish_stack:
            node = self.finish_stack.pop()
            if node not in self.visited:
                self.dfs_second_pass(node, self.current_scc_index)
                self.current_scc_index += 1
        
        self.num_sccs = self.current_scc_index
    
    def is_satisfiable(self) -> bool:
        """Check if the instance is satisfiable."""
        for var in range(1, self.num_variables + 1):
            pos_scc = self.scc_indices.get(str(var), -1)
            neg_scc = self.scc_indices.get(str(-var), -1)
            if pos_scc == neg_scc:
                return False
        return True
    
    def get_conflicting_variables(self) -> List[int]:
        """Get list of variables whose literals are in same SCC."""
        conflicting = []
        for var in range(1, self.num_variables + 1):
            pos_scc = self.scc_indices.get(str(var), -1)
            neg_scc = self.scc_indices.get(str(-var), -1)
            if pos_scc == neg_scc:
                conflicting.append(var)
        return sorted(conflicting)
    
    def compute_assignment(self) -> List[int]:
        """Compute lexicographically smallest satisfying assignment."""
        if not self.is_satisfiable():
            return []
        
        assignment = []
        for var in range(1, self.num_variables + 1):
            pos_scc = self.scc_indices[str(var)]
            neg_scc = self.scc_indices[str(-var)]
            
            if pos_scc > neg_scc:
                assignment.append(var)
            else:
                assignment.append(-var)
        
        return assignment
    
    def get_scc_sizes(self) -> List[int]:
        """Get list of SCC sizes."""
        scc_size_count = defaultdict(int)
        for literal_str, scc_idx in self.scc_indices.items():
            scc_size_count[scc_idx] += 1
        
        sizes = list(scc_size_count.values())
        return sorted(sizes, reverse=True)
    
    def compute_implication_closure(self, query_literal: int) -> List[int]:
        """Compute all literals reachable from query literal via DFS."""
        start_node = self.literal_to_node(query_literal)
        visited = set()
        stack = [start_node]
        reachable_literals = []
        
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            
            literal = self.node_to_literal(node)
            reachable_literals.append(literal)
            
            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    stack.append(neighbor)
        
        reachable_literals.sort(key=lambda x: (abs(x), x < 0))
        return reachable_literals
    
    def compute_equivalence_classes(self) -> List[List[int]]:
        """Find variables that must have same truth value."""
        scc_to_vars = defaultdict(list)
        for var in range(1, self.num_variables + 1):
            pos_scc = self.scc_indices[str(var)]
            scc_to_vars[pos_scc].append(var)
        
        equivalence_classes = []
        for scc_idx, vars_list in scc_to_vars.items():
            if len(vars_list) > 1:
                equivalence_classes.append(sorted(vars_list))
        
        equivalence_classes.sort(key=lambda x: x[0])
        return equivalence_classes
    
    def compute_opposition_classes(self) -> List[List[int]]:
        """Find variables that must have opposite truth values."""
        opposition_pairs = defaultdict(list)
        
        for var in range(1, self.num_variables + 1):
            pos_scc = self.scc_indices[str(var)]
            
            for other_var in range(var + 1, self.num_variables + 1):
                neg_other_scc = self.scc_indices[str(-other_var)]
                
                if pos_scc == neg_other_scc:
                    opposition_pairs[pos_scc].append((var, other_var))
        
        opposition_classes = []
        processed = set()
        
        for scc_idx, pairs in opposition_pairs.items():
            for var1, var2 in pairs:
                if var1 not in processed and var2 not in processed:
                    opp_class = [var1, var2]
                    processed.add(var1)
                    processed.add(var2)
                    opposition_classes.append(sorted(opp_class))
        
        opposition_classes.sort(key=lambda x: x[0])
        return opposition_classes
    
    def extract_conflict_core_bfs(self) -> List[List[int]]:
        """Extract conflict core using BFS for first conflicting variable."""
        conflicting_vars = self.get_conflicting_variables()
        if not conflicting_vars:
            return []
        
        first_var = conflicting_vars[0]
        pos_node = self.literal_to_node(first_var)
        neg_node = self.literal_to_node(-first_var)
        
        visited = set()
        queue = deque([pos_node])
        parent_map = {pos_node: None}
        found = False
        
        while queue and not found:
            node = queue.popleft()
            if node == neg_node:
                found = True
                break
            
            if node in visited:
                continue
            visited.add(node)
            
            for neighbor in self.graph.get(node, []):
                if neighbor not in parent_map:
                    parent_map[neighbor] = node
                    queue.append(neighbor)
        
        if not found:
            return []
        
        path_edges = set()
        current = neg_node
        while parent_map.get(current) is not None:
            parent = parent_map[current]
            path_edges.add((parent, current))
            current = parent
        
        core_clauses = []
        for clause in self.clauses:
            a, b = clause[0], clause[1]
            neg_a_node = self.literal_to_node(-a)
            b_node = self.literal_to_node(b)
            neg_b_node = self.literal_to_node(-b)
            a_node = self.literal_to_node(a)
            
            if (neg_a_node, b_node) in path_edges or (neg_b_node, a_node) in path_edges:
                if clause not in core_clauses:
                    core_clauses.append(clause)
        
        return core_clauses
    
    def compute_scc_outdegrees(self) -> List[int]:
        """Compute out-degree of each SCC in condensation graph."""
        outdegrees = [0] * self.num_sccs
        
        for node, neighbors in self.graph.items():
            source_literal = self.node_to_literal(node)
            source_scc = self.scc_indices[str(source_literal)]
            
            neighbor_sccs = set()
            for neighbor in neighbors:
                target_literal = self.node_to_literal(neighbor)
                target_scc = self.scc_indices[str(target_literal)]
                if target_scc != source_scc:
                    neighbor_sccs.add(target_scc)
            
            outdegrees[source_scc] += len(neighbor_sccs)
        
        return outdegrees
    
    def get_sink_sccs(self, outdegrees: List[int]) -> List[int]:
        """Get indices of sink SCCs (out-degree = 0)."""
        sinks = []
        for idx, degree in enumerate(outdegrees):
            if degree == 0:
                sinks.append(idx)
        return sorted(sinks)


class BackboneComputer:
    def __init__(self, num_variables: int, clauses: List[List[int]]):
        self.num_variables = num_variables
        self.clauses = clauses
    
    def is_forced_literal(self, variable: int, value: bool) -> bool:
        """Check if flipping this variable makes formula unsatisfiable."""
        unit_literal = variable if value else -variable
        opposite_literal = -unit_literal
        
        extended_clauses = self.clauses + [[opposite_literal, opposite_literal]]
        
        temp_solver = TwoSATSolver(self.num_variables, extended_clauses)
        temp_solver.build_implication_graph()
        temp_solver.kosaraju_scc()
        
        return not temp_solver.is_satisfiable()
    
    def compute_backbone(self, initial_assignment: List[int], max_tests: int) -> List[int]:
        """Compute backbone by testing which variables are forced."""
        backbone = []
        tests_done = 0
        
        for assigned_literal in initial_assignment:
            if tests_done >= max_tests:
                break
            
            var = abs(assigned_literal)
            current_value = assigned_literal > 0
            
            if self.is_forced_literal(var, current_value):
                backbone.append(assigned_literal)
            
            tests_done += 1
        
        return sorted(backbone, key=lambda x: (abs(x), x < 0))


def validate_inputs(num_variables: int, clauses: List[List[int]], 
                    compute_backbone: bool, query_literals_for_closure: List[int],
                    identify_equivalence_classes: bool, identify_opposition_classes: bool,
                    extract_conflict_core: bool, compute_scc_outdegrees: bool,
                    max_backbone_tests: int) -> Tuple[bool, str]:
    """Validate all input constraints."""
    try:
        if not (20 <= num_variables <= 350):
            return False, "Number of variables must be between 20 and 350 inclusive"
        
        if not (15 <= len(clauses) <= 1200):
            return False, "Number of clauses must be between 15 and 1200 inclusive"
        
        unique_clauses = set()
        appearing_vars = set()
        positive_literals = set()
        negative_literals = set()
        
        for clause in clauses:
            if len(clause) != 2:
                return False, "Each clause must contain exactly 2 distinct integers representing literals"
            
            a, b = clause[0], clause[1]
            
            if a == 0 or b == 0:
                return False, "Each literal must be non-zero with absolute value between 1 and num_variables inclusive"
            
            if abs(a) > num_variables or abs(b) > num_variables:
                return False, "Each literal must be non-zero with absolute value between 1 and num_variables inclusive"
            
            if a == b:
                return False, "Each clause must contain exactly 2 distinct integers representing literals"
            
            if a == -b or b == -a:
                return False, "Clause cannot contain both x and -x for any variable x"
            
            clause_tuple = tuple(sorted([a, b]))
            if clause_tuple in unique_clauses:
                return False, "No two clauses in the input can be identical"
            unique_clauses.add(clause_tuple)
            
            appearing_vars.add(abs(a))
            appearing_vars.add(abs(b))
            
            if a > 0:
                positive_literals.add(a)
            else:
                negative_literals.add(-a)
            
            if b > 0:
                positive_literals.add(b)
            else:
                negative_literals.add(-b)
        
        if len(appearing_vars) < 12:
            return False, "At least 12 distinct variables must appear across all clauses"
        
        if not (0 <= len(query_literals_for_closure) <= 10):
            return False, "Query literals list length must be between 0 and 10 inclusive"
        
        if len(query_literals_for_closure) != len(set(query_literals_for_closure)):
            return False, "Query literals must not contain duplicates"
        
        query_vars = set()
        for lit in query_literals_for_closure:
            if abs(lit) > num_variables or lit == 0:
                return False, "Each query literal must have absolute value between 1 and num_variables inclusive"
            
            if abs(lit) in query_vars:
                return False, "Query literals must not contain both x and -x for any variable x"
            query_vars.add(abs(lit))
        
        if not (0 <= max_backbone_tests <= num_variables):
            return False, "Maximum backbone tests must be between 0 and num_variables inclusive"
        
        if compute_backbone and max_backbone_tests < 1:
            return False, "When compute_backbone is true, max_backbone_tests must be at least 1"
        
        return True, "Valid"
    
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def main(num_variables: int, clauses: List[List[int]], compute_backbone: bool,
         query_literals_for_closure: List[int], identify_equivalence_classes: bool,
         identify_opposition_classes: bool, extract_conflict_core: bool,
         compute_scc_outdegrees: bool, max_backbone_tests: int) -> dict:
    """Main function to solve 2-SAT and perform analysis."""
    
    valid, message = validate_inputs(num_variables, clauses, compute_backbone,
                                     query_literals_for_closure, identify_equivalence_classes,
                                     identify_opposition_classes, extract_conflict_core,
                                     compute_scc_outdegrees, max_backbone_tests)
    
    if not valid:
        return {"error": message}
    
    solver = TwoSATSolver(num_variables, clauses)
    solver.build_implication_graph()
    solver.kosaraju_scc()
    
    satisfiable = solver.is_satisfiable()
    assignment = solver.compute_assignment()
    
    total_nodes = 2 * num_variables
    total_edges = 2 * len(clauses)
    
    scc_sizes = solver.get_scc_sizes()
    largest_scc_size = max(scc_sizes) if scc_sizes else 0
    average_scc_size = round(sum(scc_sizes) / len(scc_sizes), 2) if scc_sizes else 0.0
    
    result = {
        "satisfiable": satisfiable,
        "assignment": assignment,
        "num_sccs": solver.num_sccs,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "largest_scc_size": largest_scc_size,
        "average_scc_size": average_scc_size,
        "scc_indices": solver.scc_indices,
        "backbone_literals": [],
        "backbone_size": 0,
        "implication_closures": {},
        "equivalence_classes": [],
        "equivalence_class_count": 0,
        "opposition_classes": [],
        "opposition_class_count": 0,
        "conflicting_variables": [],
        "conflict_core": [],
        "conflict_core_size": 0,
        "scc_outdegrees": [],
        "sink_scc_indices": [],
        "sink_scc_count": 0
    }
    
    if not satisfiable:
        result["conflicting_variables"] = solver.get_conflicting_variables()
        if extract_conflict_core:
            conflict_core = solver.extract_conflict_core_bfs()
            result["conflict_core"] = conflict_core
            result["conflict_core_size"] = len(conflict_core)
    else:
        if compute_backbone and max_backbone_tests > 0:
            backbone_computer = BackboneComputer(num_variables, clauses)
            backbone = backbone_computer.compute_backbone(assignment, max_backbone_tests)
            result["backbone_literals"] = backbone
            result["backbone_size"] = len(backbone)
        
        if identify_equivalence_classes:
            equiv_classes = solver.compute_equivalence_classes()
            result["equivalence_classes"] = equiv_classes
            result["equivalence_class_count"] = len(equiv_classes)
        
        if identify_opposition_classes:
            opp_classes = solver.compute_opposition_classes()
            result["opposition_classes"] = opp_classes
            result["opposition_class_count"] = len(opp_classes)
    
    if query_literals_for_closure:
        closures = {}
        for query_lit in query_literals_for_closure:
            closure = solver.compute_implication_closure(query_lit)
            closures[str(query_lit)] = closure
        result["implication_closures"] = closures
    
    if compute_scc_outdegrees:
        outdegrees = solver.compute_scc_outdegrees()
        result["scc_outdegrees"] = outdegrees
        sink_sccs = solver.get_sink_sccs(outdegrees)
        result["sink_scc_indices"] = sink_sccs
        result["sink_scc_count"] = len(sink_sccs)
    
    return result


if __name__ == "__main__":
    num_variables = 30
    clauses = [
        [1, 2], [-1, 3], [-2, 3], [3, 4], [-3, 5], [-4, 5],
        [5, 6], [-5, 7], [-6, 7], [7, 8], [-7, 9], [-8, 9],
        [9, 10], [-9, 11], [-10, 11], [11, 12], [-11, 13], [-12, 13],
        [13, 14], [-13, 15], [-14, 15], [15, 16], [-15, 17], [-16, 17],
        [17, 18], [-17, 19], [-18, 19], [19, 20], [-19, 21], [-20, 21],
        [21, 22], [-21, 23], [-22, 23], [23, 24], [-23, 25], [-24, 25],
        [25, 26], [-25, 27], [-26, 27], [27, 28], [-27, 29], [-28, 29],
        [29, 30], [-29, -30], [1, 10], [2, 11], [4, 12], [6, 14],
        [8, 16], [10, 18], [12, 20], [14, 22], [16, 24], [18, 26],
        [20, 28], [-30, 1]
    ]
    compute_backbone = True
    query_literals_for_closure = [1, -5, 10, -15, 20]
    identify_equivalence_classes = True
    identify_opposition_classes = True
    extract_conflict_core = True
    compute_scc_outdegrees = True
    max_backbone_tests = 30
    
    result = main(num_variables, clauses, compute_backbone, query_literals_for_closure,
                identify_equivalence_classes, identify_opposition_classes,
                extract_conflict_core, compute_scc_outdegrees, max_backbone_tests)
    
    print(result)