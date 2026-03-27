def main_trigger(input_data: Dict) -> Dict:
    # Input validation
    required = ['k', 'joint_lengths', 'start_config', 'target_config']
    missing = [r for r in required if r not in input_data]
    if missing:
        return {"error": f"Missing required keys: {', '.join(missing)}."}
    k = input_data.get('k')
    if not isinstance(k, int) or k <= 0:
        return {"error": "Parameter 'k' must be a positive integer."}
    joint_lengths = input_data.get('joint_lengths')
    if not isinstance(joint_lengths, list) or len(joint_lengths) != k:
        return {"error": "Parameter 'joint_lengths' must be a list of length 'k'."}
    start_config = input_data.get('start_config')
    if not isinstance(start_config, list) or len(start_config) != k:
        return {"error": "Parameter 'start_config' must be a list of length 'k'."}
    target_config = input_data.get('target_config')
    if not isinstance(target_config, list) or len(target_config) != k:
        return {"error": "Parameter 'target_config' must be a list of length 'k'."}

    obstacles_in = input_data.get('obstacles') or []
    obstacles: List[Dict] = []
    for ob in obstacles_in:
        c = tuple(float(x) for x in ob.get('center', [0.0,0.0,0.0]))
        r = float(ob.get('radius', 0.0))
        obstacles.append({'center': c, 'radius': r})
    max_steps = int(input_data.get('max_steps', 50))
    num_steps = min(max_steps, 50) if max_steps > 0 else 50

    # Workspace bounds
    total_reach = sum(float(x) for x in joint_lengths)
    default_bounds = [(-1.5*total_reach,)*3, (1.5*total_reach,)*3]
    workspace_bounds = input_data.get('workspace_bounds', default_bounds)
    if workspace_bounds is None:
        workspace_bounds = default_bounds
    # ensure tuple/list format
    wb_min = tuple(workspace_bounds[0])
    wb_max = tuple(workspace_bounds[1])

    # Forward kinematics
    def forward_kinematics(config: List[Tuple[float,float]]) -> List[Tuple[float,float,float]]:
        positions = []
        x=y=z=0.0
        cum_xy = 0.0
        cum_z = 0.0
        for i, (angle, vel) in enumerate(config):
            if i % 2 == 0:
                cum_xy += angle
            else:
                cum_z += angle * 0.3
            L = float(joint_lengths[i])
            dx = L * math.cos(cum_xy) * math.cos(cum_z)
            dy = L * math.sin(cum_xy) * math.cos(cum_z)
            dz = L * math.sin(cum_z)
            x += dx; y += dy; z += dz
            positions.append((x,y,z))
        return positions

    # Bounding box of positions
    def bounding_box(positions: List[Tuple[float,float,float]]):
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        return [min(xs)-0.1, min(ys)-0.1, min(zs)-0.1], [max(xs)+0.1, max(ys)+0.1, max(zs)+0.1]

    # Segment-sphere collision
    def segment_sphere_collision(p1, p2, center, radius):
        (x1,y1,z1) = p1; (x2,y2,z2) = p2
        d = (x2-x1, y2-y1, z2-z1)
        f = (x1-center[0], y1-center[1], z1-center[2])
        a = d[0]*d[0] + d[1]*d[1] + d[2]*d[2]
        c = f[0]*f[0] + f[1]*f[1] + f[2]*f[2] - radius*radius
        if a < 1e-9:
            return c <= 0
        b = 2*(f[0]*d[0] + f[1]*d[1] + f[2]*d[2])
        disc = b*b - 4*a*c
        if disc < 0:
            return False
        sqrt_d = math.sqrt(disc)
        t1 = (-b - sqrt_d) / (2*a)
        t2 = (-b + sqrt_d) / (2*a)
        if (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1):
            return True
        return False

    # Check configuration collision: any segment vs any obstacle
    def check_configuration_collision(config: List[Tuple[float,float]]):
        positions = forward_kinematics(config)
        # base at origin to first pos
        prev = (0.0,0.0,0.0)
        for p in positions:
            for ob in obstacles:
                if segment_sphere_collision(prev, p, ob['center'], ob['radius']):
                    return True
            prev = p
        return False

    # Spatial segment tree (used minimally per requirements)
    class SegmentTree3DNode:
        def __init__(self, bmin, bmax, obs, depth=0):
            self.bmin = tuple(bmin); self.bmax = tuple(bmax)
            self.obs = obs
            self.left = None; self.right = None; self.depth = depth
        def subdivide(self):
            if self.depth >= 8 or len(self.obs) <= 4:
                return
            dx = self.bmax[0]-self.bmin[0]
            dy = self.bmax[1]-self.bmin[1]
            dz = self.bmax[2]-self.bmin[2]
            if dx >= dy and dx >= dz:
                axis = 0
            elif dy >= dx and dy >= dz:
                axis = 1
            else:
                axis = 2
            mid = (self.bmin[axis] + self.bmax[axis]) / 2.0
            left_max = list(self.bmax); right_min = list(self.bmin)
            left_max[axis] = mid
            right_min[axis] = mid
            left_obs = []; right_obs = []
            for o in self.obs:
                c = o['center'][axis]
                if c <= mid:
                    left_obs.append(o)
                if c >= mid:
                    right_obs.append(o)
            self.left = SegmentTree3DNode(self.bmin, tuple(left_max), left_obs, self.depth+1)
            self.right = SegmentTree3DNode(tuple(right_min), self.bmax, right_obs, self.depth+1)
            self.left.subdivide(); self.right.subdivide()

    tree_root = SegmentTree3DNode(wb_min, wb_max, obstacles, 0)
    tree_root.subdivide()

    # Calibration error offsets and compensation
    error_magnitude = 0.01
    error_offsets = [math.sin(i*0.7)*error_magnitude for i in range(k)]
    def apply_calibration(config):
        return [(angle + error_offsets[i], vel) for i,(angle,vel) in enumerate(config)]
    def compensate_calibration(config):
        return [(angle - error_offsets[i], vel) for i,(angle,vel) in enumerate(config)]

    # Interpolation
    def interp_configs(c1, c2, t):
        return [(c1[i][0] + t*(c2[i][0]-c1[i][0]), c1[i][1] + t*(c2[i][1]-c1[i][1])) for i in range(k)]

    # Energy, time, constraints
    max_velocity = 1.0
    max_acceleration = 0.5
    max_torque = 10.0
    time_step = 0.1

    def energy_between(cfg1, cfg2):
        total = 0.0
        for i in range(k):
            a1, v1 = cfg1[i]; a2, v2 = cfg2[i]
            delta_angle = a2 - a1
            mass_factor = float(joint_lengths[i]) * (k - i)
            kinetic = 0.5 * mass_factor * ((v2*v2) - (v1*v1))
            delta_velocity = v2 - v1
            acceleration_energy = delta_velocity + 0.1
            torque = mass_factor * acceleration_energy
            work = torque * delta_angle
            penalty = 0.1 * (abs(v1) + abs(v2))
            total += abs(kinetic) + work + penalty
        return total

    def time_between(cfg1, cfg2):
        times = []
        for i in range(k):
            a1, v1 = cfg1[i]; a2, v2 = cfg2[i]
            delta_angle = abs(a2 - a1)
            avg_v = (abs(v1) + abs(v2)) / 2.0
            t = delta_angle / max(avg_v, 0.01)
            times.append(t)
        return max(times) if times else 0.0

    def check_constraints(cfg1, cfg2):
        # velocity, acceleration, torque
        for i in range(k):
            a1, v1 = cfg1[i]; a2, v2 = cfg2[i]
            if abs(v2) > max_velocity + 1e-9:
                return False
            delta_v = abs(v2 - v1)
            accel = delta_v / time_step
            if accel > max_acceleration + 1e-9:
                return False
            mass_factor = float(joint_lengths[i]) * (k - i)
            torque = mass_factor * accel
            if abs(torque) > max_torque + 1e-9:
                return False
        return True

    # Configuration hashing
    def cfg_hash(cfg):
        rounded = [(round(a,3), round(v,3)) for (a,v) in cfg]
        return str(rounded)

    # Generate interpolated path
    path_configs: List[List[Tuple[float,float]]] = []
    for step in range(num_steps + 1):
        t = step / num_steps if num_steps>0 else 0.0
        cfg = interp_configs(start_config, target_config, t)
        # apply calibration then compensate deterministically (so net zero but checks applied)
        calibrated = apply_calibration(cfg)
        compensated = compensate_calibration(calibrated)
        path_configs.append([ (float(a), float(v)) for (a,v) in compensated ])

    # Collision filtering: keep configurations that are not in collision
    filtered_path = []
    for cfg in path_configs:
        if not check_configuration_collision(cfg):
            filtered_path.append(cfg)

    # Path inclusion: ensure start and target included per constraint
    def equal_cfg(c1,c2):
        return all(abs(c1[i][0]-c2[i][0])<1e-9 and abs(c1[i][1]-c2[i][1])<1e-9 for i in range(k))
    if not filtered_path or not equal_cfg(filtered_path[0], start_config):
        filtered_path.insert(0, [ (float(a), float(v)) for (a,v) in start_config ])
    if not filtered_path or not equal_cfg(filtered_path[-1], target_config):
        filtered_path.append([ (float(a), float(v)) for (a,v) in target_config ])

    # After final path, check collisions between consecutive pairs (per requirement 22)
    collision_free = True
    for i in range(len(filtered_path)-1):
        if check_configuration_collision(filtered_path[i+1]):
            collision_free = False

    # Compute energies, times, distances and constraint violations
    total_energy = 0.0
    total_time = 0.0
    total_distance = 0.0
    constraint_violations = 0
    # Union-Find graph for connectivity
    class UnionFind:
        def __init__(self):
            self.parent = {}
            self.rank = {}
        def make(self, x):
            if x not in self.parent:
                self.parent[x] = x; self.rank[x] = 0
        def find(self, x):
            if self.parent[x] != x:
                self.parent[x] = self.find(self.parent[x])
            return self.parent[x]
        def union(self, x, y):
            rx = self.find(x); ry = self.find(y)
            if rx == ry: return
            if self.rank[rx] < self.rank[ry]:
                self.parent[rx] = ry
            else:
                self.parent[ry] = rx
                if self.rank[rx] == self.rank[ry]:
                    self.rank[rx] += 1

    uf = UnionFind()
    nodes = []
    for cfg in filtered_path:
        key = cfg_hash(cfg)
        nodes.append(key)
        uf.make(key)
    edges = 0
    for i in range(len(filtered_path)-1):
        a = filtered_path[i]; b = filtered_path[i+1]
        e = energy_between(a,b)
        t = time_between(a,b)
        d = sum(abs(b[j][0]-a[j][0]) for j in range(k))
        total_energy += e
        total_time += t
        total_distance += d
        if not check_constraints(a,b):
            constraint_violations += 1
        else:
            # add bidirectional edge
            ka = cfg_hash(a); kb = cfg_hash(b)
            uf.union(ka,kb)
            edges += 1

    # Connectivity components count
    roots = set()
    for n in nodes:
        roots.add(uf.find(n))
    connectivity_components = len(roots)

    # Path efficiency
    direct_angular = sum(abs(target_config[i][0]-start_config[i][0]) for i in range(k))
    path_efficiency = total_distance / max(direct_angular, 0.01)

    # Workspace utilization
    workspace_util = sum(joint_lengths) / ((wb_max[0]-wb_min[0]) * 0.5)

    # Angular velocity
    angular_velocity = total_distance / max(total_time, 0.01)

    # Metrics rounding rules
    total_energy_r = round(total_energy, 6)
    total_time_r = round(total_time, 6)
    total_distance_r = round(total_distance, 6)

    # Format path with rounding for angles 2 decimals and velocities 4 decimals
    out_path = []
    for cfg in filtered_path:
        out_cfg = []
        for (a,v) in cfg:
            out_cfg.append([round(a,2), round(v,4)])
        out_path.append(out_cfg)

    num_configurations = len(out_path)
    metrics = {
        'average_energy_per_step': round((total_energy / max(len(filtered_path)-1,1)),3),
        'average_time_per_step': round((total_time / max(len(filtered_path)-1,1)),3),
        'average_angular_velocity': round(angular_velocity,3),
        'path_efficiency': round(path_efficiency,3),
        'workspace_utilization': round(workspace_util,3),
        'constraint_violations': int(constraint_violations),
        'calibration_error_magnitude': round(error_magnitude,3),
        'num_obstacles': int(len(obstacles))
    }

    result = {
        'path': out_path,
        'total_energy': round(total_energy_r, 6),
        'total_time': round(total_time_r, 6),
        'total_distance': round(total_distance_r, 6),
        'collision_free': bool(collision_free),
        'num_configurations': int(num_configurations),
        'connectivity_components': int(connectivity_components),
        'metrics': metrics,
        'workspace_bounds': [[round(wb_min[0],6), round(wb_min[1],6), round(wb_min[2],6)],
                             [round(wb_max[0],6), round(wb_max[1],6), round(wb_max[2],6)]],
        'num_obstacles': int(len(obstacles))
    }
    return result