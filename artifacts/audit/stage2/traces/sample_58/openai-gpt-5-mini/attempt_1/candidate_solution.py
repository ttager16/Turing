def __init__(self):
        self.block_partitioning = {}  # task_id:str -> [row_block,int col_block,int size]
        self.task_assignments = {}    # task_id:str -> processor_id:str
        self.assignment_order = []    # list of task_ids in assignment order
        self.completion_registry = [] # completed task ids
        self.load_history = []        # snapshots of processor loads

    def record_partition(self, task_id: int, row: int, col: int, size: int):
        self.block_partitioning[str(task_id)] = [row, col, size]

    def record_assignment(self, task_id: int, processor_id: int):
        self.task_assignments[str(task_id)] = str(processor_id)
        self.assignment_order.append(task_id)

    def record_completion(self, task_id: int):
        self.completion_registry.append(task_id)

    def record_load_snapshot(self, loads: List[int]):
        # snapshot copy
        self.load_history.append([int(x) for x in loads])

class ConcurrencyManager:
    def __init__(self):
        self.dependencies = defaultdict(set)  # task -> set of task ids it depends on
        self.dependents = defaultdict(set)   # reverse edges
        self.active = set()
        self.depth = {}  # task -> depth

    def add_task(self, task_id: int):
        self.active.add(task_id)
        if task_id not in self.depth:
            self.depth[task_id] = 0

    def add_dependency(self, task: int, depends_on: int):
        if depends_on == task:
            return
        self.dependencies[task].add(depends_on)
        self.dependents[depends_on].add(task)

    def compute_depths(self):
        # depth: one greater than max depth of its dependencies; tasks without deps depth 0
        # process in increasing task id for determinism
        tasks = sorted(set(list(self.active) + list(self.dependencies.keys())))
        for t in tasks:
            self._compute_depth_recursive(t, set())

    def _compute_depth_recursive(self, t: int, visiting: Set[int]) -> int:
        if t in visiting:
            return self.depth.get(t, 0)
        visiting.add(t)
        deps = sorted(self.dependencies.get(t, []))
        if not deps:
            self.depth[t] = 0
            visiting.remove(t)
            return 0
        maxd = -1
        for d in deps:
            if d not in self.depth:
                self._compute_depth_recursive(d, visiting)
            maxd = max(maxd, self.depth.get(d, 0))
        self.depth[t] = maxd + 1
        visiting.remove(t)
        return self.depth[t]

    def can_execute(self, task_id: int) -> bool:
        deps = self.dependencies.get(task_id, set())
        return all(d not in self.active for d in deps)

    def mark_complete(self, task_id: int):
        if task_id in self.active:
            self.active.remove(task_id)

class LoadBalancingOptimizer:
    def __init__(self, processors: List[int], matrix_tasks: List[int]):
        self.initial_processors = [int(x) for x in processors]
        self.processors = [int(x) for x in processors]
        self.tasks = [int(x) for x in matrix_tasks]
        self.num_processors = len(self.processors)
        self.num_tasks = len(self.tasks)
        self.metrics = MatrixBlockMetrics()
        self.conc = ConcurrencyManager()
        self.tasks_per_processor = defaultdict(int)
        self.data_movement_cost = 0

    def infer_dimensions(self):
        total_cost = sum(self.tasks)
        if total_cost <= 0:
            rows = 1
        else:
            rows = int(math.isqrt(total_cost))
            if rows < 1:
                rows = 1
        cols = (total_cost + rows - 1) // rows if rows else 0
        return [rows, cols]

    def partition_blocks(self, rows):
        # blocks per row = ceil(num_tasks / rows)
        if rows <= 0:
            rows = 1
        blocks_per_row = (self.num_tasks + rows - 1) // rows if rows else self.num_tasks
        for tid, size in enumerate(self.tasks):
            row_block = tid // blocks_per_row if blocks_per_row else 0
            col_block = tid % blocks_per_row if blocks_per_row else 0
            self.metrics.record_partition(tid, row_block, col_block, size)
        return blocks_per_row

    def compute_priority(self, task_id, remaining_count, row_block, col_block, size):
        priority = size * 1000
        # diagonal bonus: if row_block == col_block
        if row_block == col_block:
            priority += 500
        priority += 100 * remaining_count
        return priority

    def processor_affinity(self, proc_idx, proc_load, proc_assigned_tasks, task_id, pref_proc):
        load_factor = 10000 - proc_load
        locality_bonus = 0
        # award 200 per adjacent previously assigned task on same processor
        # check tasks assigned to this processor for adjacency
        for assigned in proc_assigned_tasks:
            if abs(assigned - task_id) <= 1:
                locality_bonus += 200
        transfer_cost = abs(proc_idx - pref_proc) * 10
        score = load_factor + locality_bonus - transfer_cost
        return score

    def preferred_processor_for_task(self, task_id):
        # preferred processor mapped by modulo of task id
        if self.num_processors == 0:
            return 0
        return task_id % self.num_processors

    def determine_dependencies(self, blocks_per_row):
        # For each task, determine dependencies per constraints:
        # depends on other with lower task ID, same row or column block, and smaller cost
        for i in range(self.num_tasks):
            self.conc.add_task(i)
        for i in range(self.num_tasks):
            bi = self.metrics.block_partitioning[str(i)][0]
            ci = self.metrics.block_partitioning[str(i)][1]
            si = self.tasks[i]
            for j in range(0, i):  # other has lower task ID
                bj = self.metrics.block_partitioning[str(j)][0]
                cj = self.metrics.block_partitioning[str(j)][1]
                sj = self.tasks[j]
                if (bj == bi or cj == ci) and (sj < si):
                    self.conc.add_dependency(i, j)
        self.conc.compute_depths()

    def sort_tasks(self):
        # priority calculation: need remaining task count for position: remaining = total - index in original?
        # The prompt says "position contributes 100 times remaining task count" interpreting remaining from end: tasks remaining when evaluating original order
        sorted_priorities = []
        total = self.num_tasks
        for tid in range(self.num_tasks):
            remaining = total - tid - 1
            row, col, size = self.metrics.block_partitioning[str(tid)]
            pri = self.compute_priority(tid, remaining, row, col, size)
            sorted_priorities.append((pri, size, tid))
        # sort primarily by priority desc, then size desc, then task id asc
        sorted_priorities.sort(key=lambda x: (-x[0], -x[1], x[2]))
        return [t[2] for t in sorted_priorities]

    def run(self):
        # handle empty processors constraint
        if self.num_processors == 0:
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
        # handle empty tasks constraint
        if self.num_tasks == 0:
            initial = list(self.initial_processors)
            avg = statistics.mean(initial) if initial else 0.0
            maxl = max(initial) if initial else 0
            minl = min(initial) if initial else 0
            efficiency = 1.0 if maxl == 0 else round((avg / maxl), 4)
            avg_rounded = round(avg, 2)
            load_history = [initial.copy()]
            return {
                'processor_loads': initial.copy(),
                'initial_loads': initial.copy(),
                'total_load': sum(initial),
                'load_balance_factor': 0.0,
                'matrix_dimensions': [0, 0],
                'block_partitioning': {},
                'task_assignments': {},
                'critical_path_length': 0,
                'data_movement_cost': 0,
                'throughput_metrics': {
                    'utilization_rate': 0.0,
                    'processor_efficiency': round(efficiency, 4),
                    'parallelism_factor': 1.0,
                    'average_load': avg_rounded,
                    'max_load': maxl,
                    'min_load': minl
                },
                'task_distribution': {
                    'tasks_per_processor': {},
                    'max_tasks_on_processor': 0,
                    'min_tasks_on_processor': 0,
                    'processors_used': 0,
                    'idle_processors': self.num_processors
                },
                'load_history': load_history,
                'num_processors': self.num_processors,
                'num_tasks': 0
            }

        # Normal flow
        self.metrics.record_load_snapshot(self.processors)  # initial snapshot
        rows, cols = self.infer_dimensions()
        self.metrics_matrix_dimensions = [rows, cols]
        blocks_per_row = self.partition_blocks(rows)
        # determine dependencies and depths
        self.determine_dependencies(blocks_per_row)
        # sort tasks
        sorted_task_ids = self.sort_tasks()
        total_tasks = self.num_tasks
        snapshot_interval = total_tasks // 5 if total_tasks // 5 > 0 else 1
        # map processor -> list of assigned task ids (for locality)
        proc_assigned_lists = defaultdict(list)
        # process tasks in sorted order
        for idx, task_id in enumerate(sorted_task_ids):
            # concurrency: ensure all dependencies completed
            # If cannot execute yet, we will simulate waiting by checking but we must still assign in this framework.
            # According to constraints execution requires dependencies to be completed before marking complete.
            # We'll choose processor now, update load, then mark complete (but only if deps are already completed).
            pref = self.preferred_processor_for_task(task_id)
            best_score = None
            best_proc = 0
            for p in range(self.num_processors):
                score = self.processor_affinity(p, self.processors[p], proc_assigned_lists[p], task_id, pref)
                if best_score is None or score > best_score or (score == best_score and p < best_proc):
                    best_score = score
                    best_proc = p
            # record assignment
            self.metrics.record_assignment(task_id, best_proc)
            proc_assigned_lists[best_proc].append(task_id)
            self.tasks_per_processor[best_proc] += 1
            # update processor load
            self.processors[best_proc] += self.tasks[task_id]
            # assignment recording flow followed by completion protocol
            # mark complete only if dependencies done; otherwise keep active until deps done.
            if self.conc.can_execute(task_id):
                self.conc.mark_complete(task_id)
                self.metrics.record_completion(task_id)
            else:
                # we still mark as active until dependencies cleared; simulate immediate completion after dependencies satisfied:
                # We'll not mark complete now; instead, after each assignment we try to clear any tasks whose deps are satisfied
                pass
            # after assignment, try to clear any tasks that can now execute (deterministic order)
            for tcheck in sorted(self.conc.active):
                if self.conc.can_execute(tcheck):
                    self.conc.mark_complete(tcheck)
                    if tcheck not in self.metrics.completion_registry:
                        self.metrics.record_completion(tcheck)
            # record load snapshot when idx modulo snapshot_interval == 0 (enumeration counter in sorted loop)
            if (idx % snapshot_interval) == 0:
                self.metrics.record_load_snapshot(self.processors)
        # final snapshot
        self.metrics.record_load_snapshot(self.processors)
        # compute data movement cost: examine sorted assignment order and add smaller task size when adjacent tasks within 2 positions on different processors
        assignment_list = [self.metrics.task_assignments[str(t)] for t in self.metrics.assignment_order]
        for i in range(len(self.metrics.assignment_order)):
            for j in range(i+1, min(i+3, len(self.metrics.assignment_order))):
                if assignment_list[i] != assignment_list[j]:
                    ti = self.metrics.assignment_order[i]
                    tj = self.metrics.assignment_order[j]
                    self.data_movement_cost += min(self.tasks[ti], self.tasks[tj])
        # ensure conservation: total final load equals initial sum + sum tasks
        # compute metrics
        initial_sum = sum(self.initial_processors)
        final_sum = sum(self.processors)
        total_tasks_sum = sum(self.tasks)
        # compute load balance quality: coefficient of variation (std / mean)
        mean_load = statistics.mean(self.processors) if self.processors else 0.0
        std_load = statistics.pstdev(self.processors) if self.processors else 0.0
        cov = 0.0
        if mean_load != 0:
            cov = std_load / mean_load
        load_balance_factor = round(cov, 4)
        # critical path length: max depth among tracked dependencies
        critical_path_length = 0
        if self.conc.depth:
            critical_path_length = max(self.conc.depth.values())
        # throughput metrics
        denom = max(1, total_tasks_sum)
        utilization_rate = 0.0
        if total_tasks_sum > 0:
            utilization_rate = (final_sum - initial_sum) / denom
        else:
            utilization_rate = 0.0
        utilization_rate = round(utilization_rate, 4) if self.num_tasks > 0 else 0.0
        avg_load = round(mean_load, 2)
        max_load = max(self.processors) if self.processors else 0
        min_load = min(self.processors) if self.processors else 0
        processor_efficiency = 1.0
        if max_load != 0:
            processor_efficiency = round((mean_load / max_load), 4)
        else:
            processor_efficiency = 1.0
        parallelism_factor = 1.0
        if critical_path_length > 0:
            parallelism_factor = round((self.num_tasks / critical_path_length), 4)
        else:
            parallelism_factor = 1.0
        # task distribution
        tasks_per_proc_str = {str(k): v for k, v in sorted(self.tasks_per_processor.items(), key=lambda x: x[0])}
        if tasks_per_proc_str:
            max_tasks_on_processor = max(tasks_per_proc_str.values())
            min_tasks_on_processor = min(tasks_per_proc_str.values())
            processors_used = sum(1 for v in tasks_per_proc_str.values() if v > 0)
        else:
            max_tasks_on_processor = 0
            min_tasks_on_processor = 0
            processors_used = 0
        idle_processors = sum(1 for p in self.processors if p == 0)  # but spec empties count if no tasks assigned; better count processors with zero tasks
        # adjust idle_processors to count processors with zero assigned tasks
        idle_processors = self.num_processors - processors_used
        # construct final dict with exact 14 keys in specified order
        result = {
            'processor_loads': [int(x) for x in self.processors],
            'initial_loads': [int(x) for x in self.initial_processors],
            'total_load': int(final_sum),
            'load_balance_factor': round(load_balance_factor, 4),
            'matrix_dimensions': [int(rows), int(cols)],
            'block_partitioning': {k: v for k, v in self.metrics.block_partitioning.items()},
            'task_assignments': {k: v for k, v in self.metrics.task_assignments.items()},
            'critical_path_length': int(critical_path_length),
            'data_movement_cost': int(self.data_movement_cost),
            'throughput_metrics': {
                'utilization_rate': round(utilization_rate, 4),
                'processor_efficiency': round(processor_efficiency, 4),
                'parallelism_factor': round(parallelism_factor, 4) if isinstance(parallelism_factor, float) else parallelism_factor,
                'average_load': avg_load,
                'max_load': int(max_load),
                'min_load': int(min_load)
            },
            'task_distribution': {
                'tasks_per_processor': tasks_per_proc_str,
                'max_tasks_on_processor': int(max_tasks_on_processor),
                'min_tasks_on_processor': int(min_tasks_on_processor),
                'processors_used': int(processors_used),
                'idle_processors': int(idle_processors)
            },
            'load_history': [list(snap) for snap in self.metrics.load_history],
            'num_processors': int(self.num_processors),
            'num_tasks': int(self.num_tasks)
        }
        # Verify load conservation
        # final_sum should equal initial_sum + total_tasks_sum
        # If minor discrepancy, adjust (but should match)
        return result

def optimize_load_balancing(processors: List[int], matrix_tasks: List[int]) -> Dict[str, any]:
    optimizer = LoadBalancingOptimizer(processors, matrix_tasks)
    return optimizer.run()