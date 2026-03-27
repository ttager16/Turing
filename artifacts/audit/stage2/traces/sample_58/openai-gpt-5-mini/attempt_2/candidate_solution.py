def __init__(self):
        self.block_partitioning: Dict[str, List[int]] = {}
        self.task_assignments: Dict[str, str] = {}
        self.completion_registry: Set[int] = set()
        self.load_history: List[List[int]] = []
        self.tasks_per_processor: Dict[int, int] = defaultdict(int)

    def record_partition(self, task_id: int, row_block: int, col_block: int, size: int):
        self.block_partitioning[str(task_id)] = [row_block, col_block, size]

    def record_assignment(self, task_id: int, processor_id: int):
        self.task_assignments[str(task_id)] = str(processor_id)
        self.tasks_per_processor[processor_id] += 1

    def mark_complete(self, task_id: int):
        self.completion_registry.add(task_id)

    def snapshot_loads(self, loads: List[int]):
        self.load_history.append(list(loads))

class ConcurrencyManager:
    def __init__(self, total_tasks: int, block_map: Dict[int, List[int]], costs: List[int]):
        self.dependencies: Dict[int, List[int]] = defaultdict(list)
        self.depths: Dict[int, int] = {}
        self.active: Set[int] = set()
        self.block_map = block_map
        self.costs = costs
        self.total_tasks = total_tasks
        self._build_dependencies()

    def _build_dependencies(self):
        # dependency if other has lower id, shares row or col block, and smaller cost
        for i in range(self.total_tasks):
            rb_i, cb_i = self.block_map[i]
            for j in range(0, i):
                rb_j, cb_j = self.block_map[j]
                if (rb_i == rb_j or cb_i == cb_j) and self.costs[j] < self.costs[i]:
                    self.dependencies[i].append(j)
        # initialize depths
        for i in range(self.total_tasks):
            self.depths[i] = -1
        for i in range(self.total_tasks):
            self._compute_depth(i)

    def _compute_depth(self, task_id: int) -> int:
        if self.depths[task_id] != -1:
            return self.depths[task_id]
        deps = self.dependencies.get(task_id, [])
        if not deps:
            self.depths[task_id] = 0
        else:
            self.depths[task_id] = 1 + max((self._compute_depth(d) for d in deps), default=0)
        return self.depths[task_id]

    def can_execute(self, task_id: int) -> bool:
        deps = self.dependencies.get(task_id, [])
        return all(d not in self.active for d in deps)

    def activate(self, task_id: int):
        self.active.add(task_id)

    def complete(self, task_id: int):
        if task_id in self.active:
            self.active.remove(task_id)

class LoadBalancingOptimizer:
    def __init__(self, processors: List[int], matrix_tasks: List[int]):
        self.initial_processors = list(processors)
        self.processors = list(processors)
        self.matrix_tasks = list(matrix_tasks)
        self.num_processors = len(processors)
        self.num_tasks = len(matrix_tasks)
        self.metrics = MatrixBlockMetrics()
        self.block_map: Dict[int, List[int]] = {}
        self.total_task_cost = sum(self.matrix_tasks)
        self.matrix_dimensions = [0, 0]

    def infer_dimensions(self):
        total = self.total_task_cost
        if total == 0:
            rows = 1
        else:
            rows = int(math.isqrt(total))
            if rows < 1:
                rows = 1
        cols = math.ceil(total / rows) if rows > 0 else 0
        self.matrix_dimensions = [rows, cols]
        return self.matrix_dimensions

    def partition_blocks(self):
        rows, cols = self.matrix_dimensions
        if self.num_tasks == 0:
            return
        blocks_per_row = math.ceil(self.num_tasks / rows) if rows > 0 else self.num_tasks
        for tid, size in enumerate(self.matrix_tasks):
            row_block = tid // blocks_per_row
            col_block = tid % blocks_per_row
            self.block_map[tid] = [row_block, col_block]
            self.metrics.record_partition(tid, row_block, col_block, size)

    def compute_priority(self, task_id: int, remaining_count: int):
        size = self.matrix_tasks[task_id]
        # diagonal bonus if row_block == col_block
        rb, cb = self.block_map[task_id]
        diagonal = 500 if rb == cb else 0
        position_contrib = 100 * remaining_count
        priority = 1000 * size + diagonal + position_contrib
        return priority

    def affinity_score(self, proc_idx: int, task_id: int, assigned_history: Dict[int, List[int]]):
        load_factor = 10000 - self.processors[proc_idx]
        locality = 0
        # count previously assigned tasks adjacent within 1 position assigned to same processor
        for prev in assigned_history.get(proc_idx, []):
            if abs(prev - task_id) <= 1:
                locality += 200
        preferred_proc = task_id % (self.num_processors if self.num_processors>0 else 1)
        transfer_cost = abs(proc_idx - preferred_proc) * 10
        score = load_factor + locality - transfer_cost
        return score

    def sort_tasks(self):
        remaining = self.num_tasks
        priorities = []
        for tid in range(self.num_tasks):
            pr = self.compute_priority(tid, remaining)
            priorities.append((pr, self.matrix_tasks[tid], tid))
        # sort by priority desc, size desc, id asc
        priorities.sort(key=lambda x: (-x[0], -x[1], x[2]))
        sorted_ids = [t[2] for t in priorities]
        return sorted_ids

    def process(self):
        if self.num_processors == 0:
            # fill empty response handled outside
            return
        if self.num_tasks == 0:
            # record initial snapshot
            self.metrics.snapshot_loads(self.initial_processors)
            return

        self.metrics.snapshot_loads(self.initial_processors)
        assigned_history: Dict[int, List[int]] = defaultdict(list)
        concurrency = ConcurrencyManager(self.num_tasks, self.block_map, self.matrix_tasks)
        sorted_tasks = self.sort_tasks()
        # maintain deterministic enumeration counter
        for idx, task_id in enumerate(sorted_tasks):
            # concurrency: wait until dependencies not active (simulate by checking can_execute)
            if not concurrency.can_execute(task_id):
                # for this simulation, we will complete dependencies proactively in order (since deps have lower ids they appear earlier in sorted list sometimes not — but protocol says require completion)
                # To maintain determinism: complete any active dependencies (simulate finishing them)
                deps = concurrency.dependencies.get(task_id, [])
                for d in deps:
                    if d in concurrency.active:
                        concurrency.complete(d)
            # choose processor with highest affinity score, tie break by lowest id
            best_score = None
            best_proc = 0
            for p in range(self.num_processors):
                score = self.affinity_score(p, task_id, assigned_history)
                if best_score is None or score > best_score or (score == best_score and p < best_proc):
                    best_score = score
                    best_proc = p
            # record assignment then update load then mark complete
            self.metrics.record_assignment(task_id, best_proc)
            assigned_history[best_proc].append(task_id)
            # activation -> update processor load -> completion
            concurrency.activate(task_id)
            self.processors[best_proc] += self.matrix_tasks[task_id]
            # snapshot rule: when idx % floor(total_tasks/5) == 0
            snap_div = max(1, self.num_tasks // 5)
            if (idx % snap_div) == 0:
                self.metrics.snapshot_loads(self.processors)
            # complete
            concurrency.complete(task_id)
            self.metrics.mark_complete(task_id)
            # final snapshot after each assignment as well to track progression
            self.metrics.snapshot_loads(self.processors)
        # ensure final snapshot
        self.metrics.snapshot_loads(self.processors)

    def analyze(self) -> Dict[str, Any]:
        # loads
        processor_loads = list(self.processors)
        initial_loads = list(self.initial_processors)
        total_load = sum(processor_loads)
        # load balance quality: coefficient of variation
        if self.num_processors > 0:
            mean = statistics.mean(processor_loads)
            stdev = statistics.pstdev(processor_loads) if len(processor_loads) > 0 else 0.0
            cov = (stdev / mean) if mean != 0 else 0.0
            load_balance_factor = round(cov, 4)
        else:
            load_balance_factor = 0.0
        # critical path
        if self.num_tasks == 0:
            critical_path_length = 0
        else:
            # compute from concurrency manager depths
            # rebuild concurrency for depths
            concurrency = ConcurrencyManager(self.num_tasks, self.block_map, self.matrix_tasks)
            critical_path_length = max(concurrency.depths.values()) if concurrency.depths else 0
        # data movement cost: examine sorted task assignments, add smaller task size when adjacent tasks within 2 positions are on different processors
        data_movement_cost = 0
        # need ordering: use sorted by priority as earlier
        if self.num_tasks > 0:
            sorted_tasks = self.sort_tasks()
            last_proc = None
            for i, tid in enumerate(sorted_tasks):
                proc = int(self.metrics.task_assignments.get(str(tid), "0"))
                if i > 0:
                    prev_tid = sorted_tasks[i-1]
                    prev_proc = int(self.metrics.task_assignments.get(str(prev_tid), "0"))
                    if abs(i - (i-1)) <= 2 and proc != prev_proc:
                        data_movement_cost += min(self.matrix_tasks[tid], self.matrix_tasks[prev_tid])
        # throughput metrics
        if self.num_tasks == 0:
            utilization_rate = 0.0
        else:
            added_work = sum(processor_loads) - sum(initial_loads)
            denom = max(1, self.total_task_cost)
            utilization_rate = round(added_work / denom if denom else 0.0, 4)
        avg_load = round(statistics.mean(processor_loads) if processor_loads else 0.0, 2)
        max_load = max(processor_loads) if processor_loads else 0
        min_load = min(processor_loads) if processor_loads else 0
        if max_load == 0:
            processor_efficiency = 1.0
        else:
            processor_efficiency = round((avg_load / max_load) if max_load else 1.0, 4)
        # parallelism factor
        if critical_path_length == 0:
            parallelism_factor = 1.0
        else:
            parallelism_factor = round(self.num_tasks / max(1, critical_path_length), 4)
        utilization_rate = round(utilization_rate,4)
        # task distribution
        tasks_per_proc_str = {str(k): v for k, v in sorted(self.metrics.tasks_per_processor.items(), key=lambda x: x[0])}
        if tasks_per_proc_str:
            counts = list(tasks_per_proc_str.values())
            max_tasks_on_processor = max(counts)
            min_tasks_on_processor = min(counts)
            processors_used = sum(1 for v in counts if v > 0)
        else:
            max_tasks_on_processor = 0
            min_tasks_on_processor = 0
            processors_used = 0
        idle_processors = self.num_processors - processors_used
        # average_load rounded already
        throughput_metrics = {
            'utilization_rate': utilization_rate,
            'processor_efficiency': processor_efficiency,
            'parallelism_factor': parallelism_factor,
            'average_load': avg_load,
            'max_load': max_load,
            'min_load': min_load
        }
        task_distribution = {
            'tasks_per_processor': tasks_per_proc_str,
            'max_tasks_on_processor': max_tasks_on_processor,
            'min_tasks_on_processor': min_tasks_on_processor,
            'processors_used': processors_used,
            'idle_processors': idle_processors
        }
        result: Dict[str, Any] = {
            'processor_loads': processor_loads,
            'initial_loads': initial_loads,
            'total_load': total_load,
            'load_balance_factor': load_balance_factor,
            'matrix_dimensions': self.matrix_dimensions,
            'block_partitioning': self.metrics.block_partitioning,
            'task_assignments': self.metrics.task_assignments,
            'critical_path_length': critical_path_length,
            'data_movement_cost': data_movement_cost,
            'throughput_metrics': throughput_metrics,
            'task_distribution': task_distribution,
            'load_history': self.metrics.load_history,
            'num_processors': self.num_processors,
            'num_tasks': self.num_tasks
        }
        return result

def optimize_load_balancing(processors: List[int], matrix_tasks: List[int]) -> Dict[str, any]:
    # Handle empty processors case per constraints
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
    optimizer = LoadBalancingOptimizer(processors, matrix_tasks)
    optimizer.infer_dimensions()
    # special empty tasks handling
    if optimizer.num_tasks == 0:
        optimizer.partition_blocks()  # does nothing
        # compute throughput_metrics per constraint 25
        initial = list(optimizer.initial_processors)
        processor_loads = list(initial)
        total_load = sum(processor_loads)
        avg_load = round(statistics.mean(processor_loads) if processor_loads else 0.0, 2)
        max_load = max(processor_loads) if processor_loads else 0
        min_load = min(processor_loads) if processor_loads else 0
        if max_load == 0:
            proc_eff = 1.0
        else:
            proc_eff = round((avg_load / max_load) if max_load else 1.0, 4)
        throughput_metrics = {
            'utilization_rate': 0.0,
            'processor_efficiency': proc_eff,
            'parallelism_factor': 1.0,
            'average_load': avg_load,
            'max_load': max_load,
            'min_load': min_load
        }
        task_distribution = {
            'tasks_per_processor': {},
            'max_tasks_on_processor': 0,
            'min_tasks_on_processor': 0,
            'processors_used': 0,
            'idle_processors': len(processors)
        }
        load_history = [initial]
        return {
            'processor_loads': processor_loads,
            'initial_loads': initial,
            'total_load': total_load,
            'load_balance_factor': 0.0,
            'matrix_dimensions': [0, 0],
            'block_partitioning': {},
            'task_assignments': {},
            'critical_path_length': 0,
            'data_movement_cost': 0,
            'throughput_metrics': throughput_metrics,
            'task_distribution': task_distribution,
            'load_history': load_history,
            'num_processors': len(processors),
            'num_tasks': 0
        }
    optimizer.partition_blocks()
    optimizer.process()
    result = optimizer.analyze()
    # enforce load conservation: total final load equals initial sum + tasks sum
    expected_total = sum(processors) + sum(matrix_tasks)
    # adjust total_load if minor numeric issues (should be exact ints)
    result['total_load'] = sum(result['processor_loads'])
    # round numeric formatting per requirement: load_balance_factor already rounded, throughput entries rounded appropriately
    # ensure ordering of keys matches required 14 keys order - they are in analyze in correct order
    return result