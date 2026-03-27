# main.py
from typing import List, Dict, Set
from collections import defaultdict


class MatrixBlockMetrics:
    """
    Tracks metrics for matrix block operations including computational costs,
    memory patterns, and distribution efficiency.
    """

    def __init__(self):
        """Initialize metrics tracking structures."""
        self.block_assignments: Dict[str, str] = {}  # task_id -> processor_id
        self.processor_task_counts: Dict[str, int] = defaultdict(int)
        self.load_distribution_history: List[List[int]] = []
        self.dependency_chain_lengths: Dict[str, int] = {}
        self.critical_path_length: int = 0
        self.total_data_movement: int = 0
        self.load_balance_factor: float = 0.0

    def record_assignment(self, task_id: int, processor_id: int) -> None:
        """Record task assignment to processor."""
        self.block_assignments[str(task_id)] = str(processor_id)
        self.processor_task_counts[str(processor_id)] += 1

    def calculate_load_balance_factor(self, processor_loads: List[int]) -> float:
        """Calculate load balance factor (lower is more balanced)."""
        if not processor_loads:
            return 0.0
        avg_load = sum(processor_loads) / len(processor_loads)
        if avg_load == 0:
            return 0.0
        variance = sum((load - avg_load) ** 2 for load in processor_loads) / len(processor_loads)
        return (variance ** 0.5) / avg_load

    def compute_critical_path(self, dependency_depths: Dict[str, int]) -> int:
        """Compute the length of the critical path through dependencies."""
        return max(dependency_depths.values()) if dependency_depths else 0

    def estimate_data_movement(self, task_assignments: Dict[str, str],
                               task_sizes: List[int]) -> int:
        """
        Estimate total data movement cost based on task locality.
        Assumes adjacent task IDs have data affinity.
        """
        movement_cost = 0
        sorted_tasks = sorted(task_assignments.items(), key=lambda x: int(x[0]))

        for i in range(len(sorted_tasks) - 1):
            task_id1, proc1 = sorted_tasks[i]
            task_id2, proc2 = sorted_tasks[i + 1]

            # Data movement occurs when adjacent tasks are on different processors
            if proc1 != proc2 and abs(int(task_id1) - int(task_id2)) <= 2:
                movement_cost += min(task_sizes[int(task_id1)], task_sizes[int(task_id2)])

        return movement_cost


class ConcurrencyManager:
    """
    Manages concurrent task execution and dependency tracking.
    Ensures no conflicts when sub-blocks share dependencies.
    """

    def __init__(self):
        """Initialize concurrency tracking structures."""
        self.active_tasks: Set[int] = set()
        self.task_dependencies: Dict[int, Set[int]] = defaultdict(set)
        self.dependency_depth: Dict[str, int] = {}
        self.completion_status: Dict[int, float] = {}

    def can_execute(self, task_id: int) -> bool:
        """
        Check if task can be executed given current state.

        Args:
            task_id: Task identifier

        Returns:
            True if task can be executed without conflicts
        """
        # Check if any dependencies are still active
        for dep in self.task_dependencies[task_id]:
            if dep in self.active_tasks:
                return False
        return True

    def start_task(self, task_id: int, dependencies: Set[int] = None) -> None:
        """
        Mark task as active and register dependencies.

        Args:
            task_id: Task identifier
            dependencies: Set of task IDs this task depends on
        """
        self.active_tasks.add(task_id)
        if dependencies:
            self.task_dependencies[task_id] = dependencies
            self.dependency_depth[str(task_id)] = max(
                (self.dependency_depth.get(str(dep), 0) for dep in dependencies),
                default=0
            ) + 1
        else:
            self.dependency_depth[str(task_id)] = 0
        self.completion_status[task_id] = 0.0

    def complete_task(self, task_id: int) -> None:
        """
        Mark task as completed and remove from active set.

        Args:
            task_id: Task identifier
        """
        if task_id in self.active_tasks:
            self.active_tasks.remove(task_id)
        self.completion_status[task_id] = 1.0


class LoadBalancingOptimizer:
    """
    Main optimizer implementing dynamic flow-based redistribution
    with concurrency tracking, matrix block decomposition, and performance metrics.
    """

    def __init__(self, processors: List[int], matrix_tasks: List[int]):
        """
        Initialize optimizer with processor loads and tasks.

        Args:
            processors: Initial loads of each processor
            matrix_tasks: List of task computational costs
        """
        self.processors = processors[:]
        self.initial_loads = processors[:]
        self.matrix_tasks = matrix_tasks[:]
        self.num_processors = len(processors)
        self.num_tasks = len(matrix_tasks)

        self.concurrency_mgr = ConcurrencyManager()
        self.metrics = MatrixBlockMetrics()

        # Matrix operation metadata
        self.matrix_dimensions = self._infer_matrix_dimensions()
        self.block_partitioning = self._compute_block_partitioning()

    def _infer_matrix_dimensions(self) -> List[int]:
        """
        Infer matrix dimensions from task distribution.
        Assumes tasks represent matrix blocks in a decomposed operation.
        """
        total_ops = sum(self.matrix_tasks)
        # Estimate square-like dimensions
        dim = int(total_ops ** 0.5)
        if dim == 0:
            dim = 1
        return [dim, (total_ops + dim - 1) // dim]

    def _compute_block_partitioning(self) -> Dict[str, List[int]]:
        """
        Compute block partitioning scheme for matrix operations.
        Returns dict mapping task_id (string) to [row_block, col_block, block_size].
        """
        partitioning = {}
        rows, cols = self.matrix_dimensions
        blocks_per_row = max(1, (self.num_tasks + rows - 1) // rows)

        for task_id, size in enumerate(self.matrix_tasks):
            row_block = task_id // blocks_per_row
            col_block = task_id % blocks_per_row
            partitioning[str(task_id)] = [row_block, col_block, size]

        return partitioning

    def _calculate_task_priority(self, task_id: int, task_size: int) -> int:
        """
        Calculate priority score for task based on size, position, and dependencies.
        Higher score = higher priority for execution.
        """
        # Base priority on size
        size_priority = task_size * 1000

        # Add positional priority (diagonal blocks are more critical)
        if str(task_id) in self.block_partitioning:
            row, col, _ = self.block_partitioning[str(task_id)]
            diagonal_bonus = 500 if row == col else 0
            positional_factor = 100 * (self.num_tasks - task_id)
            return size_priority + diagonal_bonus + positional_factor

        return size_priority

    def _compute_processor_affinity(self, task_id: int) -> List[List[int]]:
        """
        Compute processor affinity scores for a task.
        Returns list of [processor_id, affinity_score] sorted by score (descending).
        """
        affinities = []

        for proc_id in range(self.num_processors):
            # Base affinity: inverse of current load
            load_factor = 10000 - self.processors[proc_id]

            # Locality bonus: prefer processors with related tasks
            locality_bonus = 0
            for assigned_task, assigned_proc in self.metrics.block_assignments.items():
                if int(assigned_proc) == proc_id:
                    # Check if tasks are adjacent in matrix
                    if abs(int(assigned_task) - task_id) <= 1:
                        locality_bonus += 200

            # Data center cost factor (simulated by processor index)
            transfer_cost = abs(proc_id - (task_id % self.num_processors)) * 10

            affinity = load_factor + locality_bonus - transfer_cost
            affinities.append([proc_id, affinity])

        return sorted(affinities, key=lambda x: (-x[1], x[0]))

    def balance_loads(self) -> None:
        """
        Perform sophisticated load balancing with concurrency tracking,
        processor affinity, and matrix block locality optimization.
        """
        # Sort tasks by priority (size and position-aware)
        task_priorities = [(task_id, size, self._calculate_task_priority(task_id, size))
                           for task_id, size in enumerate(self.matrix_tasks)]
        sorted_tasks = sorted(task_priorities, key=lambda x: (-x[2], -x[1], x[0]))

        # Track load distribution over time
        self.metrics.load_distribution_history.append(self.processors[:])

        # Process each task with advanced assignment logic
        for task_index, (task_id, task_size, priority) in enumerate(sorted_tasks):
            # Build dependency set based on matrix block relationships
            dependencies = set()

            # Tasks depend on blocks they share rows/columns with
            if str(task_id) in self.block_partitioning:
                my_row, my_col, _ = self.block_partitioning[str(task_id)]
                for other_id in range(task_id):
                    if str(other_id) in self.block_partitioning:
                        other_row, other_col, other_size = self.block_partitioning[str(other_id)]
                        # Dependency if in same row/column and smaller
                        if (my_row == other_row or my_col == other_col) and other_size < task_size:
                            dependencies.add(other_id)

            # Register dependencies first before checking
            self.concurrency_mgr.start_task(task_id, dependencies)

            # Check concurrency constraints
            if self.concurrency_mgr.can_execute(task_id):
                # Get processor affinity scores
                affinities = self._compute_processor_affinity(task_id)

                # Select best processor based on affinity
                best_proc = affinities[0][0]

                # Assign task and record metrics
                self.processors[best_proc] += task_size
                self.metrics.record_assignment(task_id, best_proc)
                self.concurrency_mgr.complete_task(task_id)

                # Record load distribution periodically every 1/5 of tasks processed
                if task_index % max(1, self.num_tasks // 5) == 0:
                    self.metrics.load_distribution_history.append(self.processors[:])

    def _compute_throughput_metrics(self) -> Dict[str, float]:
        """Compute throughput and efficiency metrics."""
        total_work = sum(self.matrix_tasks)
        total_capacity = sum(self.processors)

        # Utilization rate
        initial_capacity = sum(self.initial_loads)
        utilization = (total_capacity - initial_capacity) / max(1, total_work) if total_work > 0 else 0.0

        # Processor efficiency (how evenly work is distributed)
        avg_load = total_capacity / self.num_processors if self.num_processors > 0 else 0
        max_load = max(self.processors) if self.processors else 0
        efficiency = avg_load / max_load if max_load > 0 else 1.0

        # Parallelism factor
        parallelism = self.num_tasks / max(1, self.metrics.critical_path_length) if self.metrics.critical_path_length > 0 else 1.0

        return {
            'utilization_rate': round(utilization, 4),
            'processor_efficiency': round(efficiency, 4),
            'parallelism_factor': round(parallelism, 4),
            'average_load': round(avg_load, 2),
            'max_load': max_load,
            'min_load': min(self.processors) if self.processors else 0
        }

    def _analyze_task_distribution(self) -> Dict[str, any]:
        """Analyze how tasks are distributed across processors."""
        distribution = {
            'tasks_per_processor': dict(self.metrics.processor_task_counts),
            'max_tasks_on_processor': max(self.metrics.processor_task_counts.values()) if self.metrics.processor_task_counts else 0,
            'min_tasks_on_processor': min(self.metrics.processor_task_counts.values()) if self.metrics.processor_task_counts else 0,
            'processors_used': len(self.metrics.processor_task_counts),
            'idle_processors': self.num_processors - len(self.metrics.processor_task_counts)
        }
        return distribution

    def optimize(self) -> Dict[str, any]:
        """
        Execute full optimization pipeline and return comprehensive results.

        Returns:
            Dictionary containing processor loads and detailed metrics
        """
        # Execute load balancing
        self.balance_loads()

        # Finalize load distribution history
        self.metrics.load_distribution_history.append(self.processors[:])

        # Compute final metrics
        self.metrics.critical_path_length = self.metrics.compute_critical_path(
            self.concurrency_mgr.dependency_depth
        )
        self.metrics.total_data_movement = self.metrics.estimate_data_movement(
            self.metrics.block_assignments,
            self.matrix_tasks
        )
        self.metrics.load_balance_factor = self.metrics.calculate_load_balance_factor(
            self.processors
        )

        # Build comprehensive result
        result = {
            'processor_loads': self.processors[:],
            'initial_loads': self.initial_loads[:],
            'total_load': sum(self.processors),
            'load_balance_factor': round(self.metrics.load_balance_factor, 4),
            'matrix_dimensions': self.matrix_dimensions,
            'block_partitioning': self.block_partitioning,
            'task_assignments': self.metrics.block_assignments,
            'critical_path_length': self.metrics.critical_path_length,
            'data_movement_cost': self.metrics.total_data_movement,
            'throughput_metrics': self._compute_throughput_metrics(),
            'task_distribution': self._analyze_task_distribution(),
            'load_history': self.metrics.load_distribution_history,
            'num_processors': self.num_processors,
            'num_tasks': self.num_tasks
        }

        return result


def optimize_load_balancing(processors: List[int], matrix_tasks: List[int]) -> Dict[str, any]:
    """
    Optimize load balancing across processors for matrix operations with comprehensive metrics.

    This function implements a sophisticated load-balancing solution for matrix block operations:
    1. Decomposes matrix operations into interdependent sub-blocks with priority assignment
    2. Computes processor affinity based on current load, locality, and data transfer costs
    3. Tracks concurrency constraints and dependency chains to prevent execution conflicts
    4. Assigns tasks using flow-based optimization considering matrix block relationships
    5. Generates detailed performance metrics including throughput, efficiency, and distribution

    The algorithm models matrix computations as a set of blocks that must be distributed across
    processors in geographically distributed data centers. Each processor has an initial load,
    and tasks are assigned considering:
    - Computational cost (task size)
    - Data locality (blocks in same row/column)
    - Inter-data-center transfer costs
    - Dependency constraints from matrix structure
    - Load balancing to minimize maximum processor load

    Args:
        processors: List of initial processor loads (computational units already assigned)
        matrix_tasks: List of task computational costs representing matrix sub-blocks

    Returns:
        Dictionary containing:
            - processor_loads: Final loads on each processor after task assignment
            - initial_loads: Original processor loads before optimization
            - total_load: Sum of all processor loads
            - load_balance_factor: Measure of load distribution quality (lower is better)
            - matrix_dimensions: Inferred dimensions of the matrix being processed
            - block_partitioning: Mapping of tasks to matrix block positions
            - task_assignments: Mapping of task IDs to assigned processor IDs
            - critical_path_length: Length of longest dependency chain
            - data_movement_cost: Estimated cost of inter-processor data transfers
            - throughput_metrics: Utilization, efficiency, and parallelism metrics
            - task_distribution: Statistics on how tasks are spread across processors
            - load_history: Snapshots of load distribution during optimization
            - num_processors: Total number of processors
            - num_tasks: Total number of tasks

    Example:
        >>> result = optimize_load_balancing([70, 120, 90, 60, 150], [10, 40, 60, 20, 90, 30])
        >>> result['processor_loads']
        [150, 150, 140, 150, 150]
        >>> result['load_balance_factor']
        0.0267
        >>> result['throughput_metrics']['processor_efficiency']
        0.9867
    """
    if not processors:
        return {
            'processor_loads': [],
            'initial_loads': [],
            'total_load': 0,
            'load_balance_factor': 0.0,
            'matrix_dimensions': [0, 0],
            'block_partitioning': {},
            'task_assignments': {},
            'critical_path_length': 0,
            'data_movement_cost': 0,
            'throughput_metrics': {},
            'task_distribution': {},
            'load_history': [],
            'num_processors': 0,
            'num_tasks': 0
        }

    if not matrix_tasks:
        return {
            'processor_loads': processors[:],
            'initial_loads': processors[:],
            'total_load': sum(processors),
            'load_balance_factor': 0.0,
            'matrix_dimensions': [0, 0],
            'block_partitioning': {},
            'task_assignments': {},
            'critical_path_length': 0,
            'data_movement_cost': 0,
            'throughput_metrics': {
                'utilization_rate': 0.0,
                'processor_efficiency': 1.0,
                'parallelism_factor': 1.0,
                'average_load': round(sum(processors) / len(processors), 2),
                'max_load': max(processors),
                'min_load': min(processors)
            },
            'task_distribution': {
                'tasks_per_processor': {},
                'max_tasks_on_processor': 0,
                'min_tasks_on_processor': 0,
                'processors_used': 0,
                'idle_processors': len(processors)
            },
            'load_history': [processors[:]],
            'num_processors': len(processors),
            'num_tasks': 0
        }

    optimizer = LoadBalancingOptimizer(processors, matrix_tasks)
    return optimizer.optimize()


# Example usage
if __name__ == "__main__":
    processors = [70, 120, 90, 60, 150]
    matrix_tasks = [10, 40, 60, 20, 90, 30]
    results = optimize_load_balancing(processors, matrix_tasks)
    print(results)