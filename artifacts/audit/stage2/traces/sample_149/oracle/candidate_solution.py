# main.py
from typing import List, Tuple, Dict, Optional
import math


class UnionFind:
    """
    Union-Find (Disjoint Set Union) data structure for managing connected components
    of feasible arm configurations. Enables efficient connectivity queries.
    """

    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size
        self.size = [1] * size

    def find(self, x: int) -> int:
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """Union by rank. Returns True if union was performed."""
        root_x, root_y = self.find(x), self.find(y)
        if root_x == root_y:
            return False

        if self.rank[root_x] < self.rank[root_y]:
            root_x, root_y = root_y, root_x

        self.parent[root_y] = root_x
        self.size[root_x] += self.size[root_y]

        if self.rank[root_x] == self.rank[root_y]:
            self.rank[root_x] += 1

        return True

    def connected(self, x: int, y: int) -> bool:
        """Check if two elements are in the same set."""
        return self.find(x) == self.find(y)


class SegmentTreeNode:
    """Node for 3D spatial segment tree used in collision detection."""

    def __init__(self, bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]]):
        self.bounds = bounds  # ((min_x, min_y, min_z), (max_x, max_y, max_z))
        self.obstacles = []
        self.left = None
        self.right = None
        self.mid_point = None


class SpatialSegmentTree:
    """
    3D Segment Tree for efficient spatial queries and collision detection.
    Partitions space hierarchically for O(log n) range queries.
    """

    def __init__(self, workspace_bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]]):
        self.root = SegmentTreeNode(workspace_bounds)
        self.max_depth = 8  # Control tree depth for performance

    def insert_obstacle(self, obstacle: Dict, node: SegmentTreeNode = None, depth: int = 0):
        """Insert obstacle into segment tree."""
        if node is None:
            node = self.root

        node.obstacles.append(obstacle)

        # Stop subdivision at max depth or if few obstacles
        if depth >= self.max_depth or len(node.obstacles) <= 4:
            return

        # Subdivide space along longest axis
        (min_x, min_y, min_z), (max_x, max_y, max_z) = node.bounds
        dx, dy, dz = max_x - min_x, max_y - min_y, max_z - min_z

        if dx >= dy and dx >= dz:
            # Split along x-axis
            mid = (min_x + max_x) / 2
            node.mid_point = ('x', mid)
            node.left = SegmentTreeNode(((min_x, min_y, min_z), (mid, max_y, max_z)))
            node.right = SegmentTreeNode(((mid, min_y, min_z), (max_x, max_y, max_z)))
        elif dy >= dz:
            # Split along y-axis
            mid = (min_y + max_y) / 2
            node.mid_point = ('y', mid)
            node.left = SegmentTreeNode(((min_x, min_y, min_z), (max_x, mid, max_z)))
            node.right = SegmentTreeNode(((min_x, mid, min_z), (max_x, max_y, max_z)))
        else:
            # Split along z-axis
            mid = (min_z + max_z) / 2
            node.mid_point = ('z', mid)
            node.left = SegmentTreeNode(((min_x, min_y, min_z), (max_x, max_y, mid)))
            node.right = SegmentTreeNode(((min_x, min_y, mid), (max_x, max_y, max_z)))

    def query_region(self, region: Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                     node: SegmentTreeNode = None) -> List[Dict]:
        """Query obstacles in a given 3D region."""
        if node is None:
            node = self.root

        if not self._intersects(region, node.bounds):
            return []

        result = node.obstacles.copy()

        if node.left:
            result.extend(self.query_region(region, node.left))
        if node.right:
            result.extend(self.query_region(region, node.right))

        return result

    @staticmethod
    def _intersects(region1: Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                    region2: Tuple[Tuple[float, float, float], Tuple[float, float, float]]) -> bool:
        """Check if two 3D bounding boxes intersect."""
        (min1_x, min1_y, min1_z), (max1_x, max1_y, max1_z) = region1
        (min2_x, min2_y, min2_z), (max2_x, max2_y, max2_z) = region2

        return (min1_x <= max2_x and max1_x >= min2_x and
                min1_y <= max2_y and max1_y >= min2_y and
                min1_z <= max2_z and max1_z >= min2_z)


class RobotKinematics:
    """Forward kinematics and geometric computations for k-linkage arm."""

    @staticmethod
    def compute_end_effector_positions(joint_lengths: List[float],
                                       angles: List[float]) -> List[Tuple[float, float, float]]:
        """
        Compute 3D positions of all joints including end effector.
        Uses forward kinematics with joints rotating in 3D space.
        """
        positions = [(0.0, 0.0, 0.0)]  # Base position
        x, y, z = 0.0, 0.0, 0.0
        cumulative_angle_xy = 0.0  # Angle in XY plane
        cumulative_angle_z = 0.0   # Elevation angle

        for i, (length, angle) in enumerate(zip(joint_lengths, angles)):
            # Alternate between XY plane rotation and Z-axis elevation for 3D movement
            if i % 2 == 0:
                cumulative_angle_xy += angle
                dx = length * math.cos(cumulative_angle_xy) * math.cos(cumulative_angle_z)
                dy = length * math.sin(cumulative_angle_xy) * math.cos(cumulative_angle_z)
                dz = length * math.sin(cumulative_angle_z)
            else:
                cumulative_angle_z += angle * 0.3  # Dampened z-rotation
                dx = length * math.cos(cumulative_angle_xy) * math.cos(cumulative_angle_z)
                dy = length * math.sin(cumulative_angle_xy) * math.cos(cumulative_angle_z)
                dz = length * math.sin(cumulative_angle_z)

            x, y, z = x + dx, y + dy, z + dz
            positions.append((x, y, z))

        return positions

    @staticmethod
    def compute_bounding_box(positions: List[Tuple[float, float, float]],
                             margin: float = 0.1) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Compute axis-aligned bounding box for arm configuration."""
        if not positions:
            return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

        xs, ys, zs = zip(*positions)
        return (
            (min(xs) - margin, min(ys) - margin, min(zs) - margin),
            (max(xs) + margin, max(ys) + margin, max(zs) + margin)
        )

    @staticmethod
    def segment_sphere_collision(seg_start: Tuple[float, float, float],
                                 seg_end: Tuple[float, float, float],
                                 sphere_center: Tuple[float, float, float],
                                 sphere_radius: float) -> bool:
        """Check if line segment collides with sphere (simplified obstacle)."""
        # Vector from seg_start to seg_end
        dx = seg_end[0] - seg_start[0]
        dy = seg_end[1] - seg_start[1]
        dz = seg_end[2] - seg_start[2]

        # Vector from seg_start to sphere center
        fx = seg_start[0] - sphere_center[0]
        fy = seg_start[1] - sphere_center[1]
        fz = seg_start[2] - sphere_center[2]

        a = dx*dx + dy*dy + dz*dz
        b = 2*(fx*dx + fy*dy + fz*dz)
        c = fx*fx + fy*fy + fz*fz - sphere_radius*sphere_radius

        discriminant = b*b - 4*a*c

        if discriminant < 0:
            return False

        # Check if intersection occurs within segment
        if a < 1e-9:  # Degenerate segment
            return c <= 0

        t1 = (-b - math.sqrt(discriminant)) / (2*a)
        t2 = (-b + math.sqrt(discriminant)) / (2*a)

        return (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1)


class CollisionDetector:
    """
    Hierarchical collision detection system using bounding volumes and
    segment trees for efficient obstacle queries.
    """

    def __init__(self, workspace_bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                 obstacles: List[Dict]):
        self.workspace_bounds = workspace_bounds
        self.spatial_tree = SpatialSegmentTree(workspace_bounds)
        self.obstacles = obstacles

        # Insert obstacles into spatial tree
        for obs in obstacles:
            self.spatial_tree.insert_obstacle(obs)

    def check_configuration_collision(self, joint_lengths: List[float],
                                      angles: List[float]) -> bool:
        """Check if configuration collides with any obstacle."""
        positions = RobotKinematics.compute_end_effector_positions(joint_lengths, angles)

        # Get bounding box for configuration
        bbox = RobotKinematics.compute_bounding_box(positions)

        # Query nearby obstacles
        nearby_obstacles = self.spatial_tree.query_region(bbox)

        # Check each segment against nearby obstacles
        for i in range(len(positions) - 1):
            seg_start, seg_end = positions[i], positions[i + 1]

            for obstacle in nearby_obstacles:
                if self._check_segment_obstacle_collision(seg_start, seg_end, obstacle):
                    return True

        return False

    def _check_segment_obstacle_collision(self, seg_start: Tuple[float, float, float],
                                          seg_end: Tuple[float, float, float],
                                          obstacle: Dict) -> bool:
        """Check if segment collides with obstacle."""
        # Simplified: treat obstacles as spheres
        center = obstacle.get('center', (0, 0, 0))
        radius = obstacle.get('radius', 0.5)

        return RobotKinematics.segment_sphere_collision(seg_start, seg_end, center, radius)

    def check_workspace_bounds(self, joint_lengths: List[float],
                               angles: List[float]) -> bool:
        """Check if configuration stays within workspace bounds."""
        positions = RobotKinematics.compute_end_effector_positions(joint_lengths, angles)
        (min_x, min_y, min_z), (max_x, max_y, max_z) = self.workspace_bounds

        for x, y, z in positions:
            if not (min_x <= x <= max_x and min_y <= y <= max_y and min_z <= z <= max_z):
                return False

        return True


class CalibrationErrorModel:
    """
    Deterministic model for joint calibration errors and compensation.
    Uses pseudorandom number generation with fixed seed for reproducibility.
    """

    def __init__(self, k: int, error_magnitude: float = 0.01):
        self.k = k
        self.error_magnitude = error_magnitude
        # Deterministic error offsets based on joint index
        self.error_offsets = [math.sin(i * 0.7) * error_magnitude for i in range(k)]

    def apply_calibration_error(self, angles: List[float]) -> List[float]:
        """Apply deterministic calibration error to angles."""
        return [angle + offset for angle, offset in zip(angles, self.error_offsets)]

    def compensate_error(self, angles: List[float]) -> List[float]:
        """Compensate for known calibration errors."""
        return [angle - offset for angle, offset in zip(angles, self.error_offsets)]


class PathOptimizer:
    """
    Multi-criteria path optimizer considering time, energy, torque, velocity,
    and acceleration constraints. Implements A* with custom heuristics.
    """

    def __init__(self, k: int, joint_lengths: List[float],
                 max_torque: float = 10.0, max_velocity: float = 1.0,
                 max_acceleration: float = 0.5):
        self.k = k
        self.joint_lengths = joint_lengths
        self.max_torque = max_torque
        self.max_velocity = max_velocity
        self.max_acceleration = max_acceleration

    def compute_energy_cost(self, config1: List[Tuple[float, float]],
                            config2: List[Tuple[float, float]]) -> float:
        """
        Compute energy cost for transition between configurations.
        Energy proportional to angular displacement and torque.
        """
        total_energy = 0.0

        for i, (length, (a1, v1), (a2, v2)) in enumerate(zip(self.joint_lengths, config1, config2)):
            # Angular displacement
            delta_angle = abs(a2 - a1)
            # Velocity change
            delta_velocity = abs(v2 - v1)
            # Approximated torque (mass * length * angular_acceleration)
            mass_factor = length * (self.k - i)  # Outer joints carry more mass
            acceleration = delta_velocity + 0.1  # Add small baseline
            torque = mass_factor * acceleration

            # Energy = torque * angular_displacement + velocity penalty
            kinetic_energy = 0.5 * mass_factor * (v2 * v2 - v1 * v1)
            work_energy = torque * delta_angle
            velocity_penalty = 0.1 * (abs(v1) + abs(v2))

            energy = abs(kinetic_energy) + work_energy + velocity_penalty
            total_energy += energy

        return total_energy

    def compute_time_cost(self, config1: List[Tuple[float, float]],
                          config2: List[Tuple[float, float]]) -> float:
        """Compute time cost for transition."""
        max_time = 0.0

        for (a1, v1), (a2, v2) in zip(config1, config2):
            delta_angle = abs(a2 - a1)
            avg_velocity = max((abs(v1) + abs(v2)) / 2, 0.01)
            time = delta_angle / avg_velocity
            max_time = max(max_time, time)

        return max_time

    def check_constraints(self, config1: List[Tuple[float, float]],
                          config2: List[Tuple[float, float]],
                          time_step: float = 0.1) -> bool:
        """Check if transition satisfies torque, velocity, and acceleration constraints."""
        for i, (length, (a1, v1), (a2, v2)) in enumerate(zip(self.joint_lengths, config1, config2)):
            # Velocity constraint
            if abs(v2) > self.max_velocity:
                return False

            # Acceleration constraint
            acceleration = abs(v2 - v1) / time_step
            if acceleration > self.max_acceleration:
                return False

            # Torque constraint (simplified)
            mass_factor = length * (self.k - i)
            torque = mass_factor * acceleration
            if torque > self.max_torque:
                return False

        return True

    def interpolate_configuration(self, config1: List[Tuple[float, float]],
                                  config2: List[Tuple[float, float]],
                                  t: float) -> List[Tuple[float, float]]:
        """Interpolate between two configurations with parameter t in [0, 1]."""
        result = []
        for (a1, v1), (a2, v2) in zip(config1, config2):
            angle = a1 + t * (a2 - a1)
            velocity = v1 + t * (v2 - v1)
            result.append((angle, velocity))
        return result


class ConfigurationGraph:
    """
    Manages graph of feasible configurations with connectivity tracking.
    """

    def __init__(self, k: int):
        self.k = k
        self.nodes: List[List[Tuple[float, float]]] = []
        self.node_map: Dict[str, int] = {}
        self.edges: List[List[int]] = []
        self.union_find: Optional[UnionFind] = None

    def add_configuration(self, config: List[Tuple[float, float]]) -> int:
        """Add configuration to graph, return node index."""
        key = self._config_to_key(config)
        if key in self.node_map:
            return self.node_map[key]

        idx = len(self.nodes)
        self.nodes.append(config)
        self.node_map[key] = idx
        self.edges.append([])

        return idx

    def add_edge(self, idx1: int, idx2: int):
        """Add bidirectional edge between configurations."""
        if idx2 not in self.edges[idx1]:
            self.edges[idx1].append(idx2)
        if idx1 not in self.edges[idx2]:
            self.edges[idx2].append(idx1)

    def initialize_union_find(self):
        """Initialize union-find structure for connectivity queries."""
        self.union_find = UnionFind(len(self.nodes))

        for idx, neighbors in enumerate(self.edges):
            for neighbor_idx in neighbors:
                self.union_find.union(idx, neighbor_idx)

    @staticmethod
    def _config_to_key(config: List[Tuple[float, float]]) -> str:
        """Convert configuration to hashable key."""
        # Round to 3 decimal places for deterministic hashing
        rounded = [(round(a, 3), round(v, 3)) for a, v in config]
        return str(rounded)


def optimize_k_linkage_path(k: int,
                            joint_lengths: List[float],
                            start_config: List[Tuple[float, float]],
                            target_config: List[Tuple[float, float]],
                            obstacles: List[Dict] = None,
                            workspace_bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]] = None,
                            max_steps: int = 50) -> Dict:
    """
    Optimize k-linkage robotic arm path with multi-criteria optimization.

    Args:
        k: Number of joints
        joint_lengths: Length of each joint segment
        start_config: Initial configuration [(angle, velocity), ...]
        target_config: Target configuration [(angle, velocity), ...]
        obstacles: List of obstacle dictionaries with 'center' and 'radius'
        workspace_bounds: 3D workspace boundaries
        max_steps: Maximum interpolation steps for path

    Returns:
        Dictionary containing:
            - path: List of configurations from start to target
            - total_energy: Total energy consumption
            - total_time: Total time taken
            - total_distance: Total angular distance
            - collision_free: Boolean indicating collision-free path
            - num_configurations: Number of waypoints
            - connectivity_components: Number of disconnected components
            - metrics: Additional optimization metrics
    """
    # Default workspace bounds
    if workspace_bounds is None:
        total_reach = sum(joint_lengths) * 1.5
        workspace_bounds = (
            (-total_reach, -total_reach, -total_reach),
            (total_reach, total_reach, total_reach)
        )

    # Default obstacles
    if obstacles is None:
        obstacles = []

    # Initialize components
    collision_detector = CollisionDetector(workspace_bounds, obstacles)
    path_optimizer = PathOptimizer(k, joint_lengths)
    error_model = CalibrationErrorModel(k)
    config_graph = ConfigurationGraph(k)

    # Add start and target to graph
    _ = config_graph.add_configuration(start_config)
    _ = config_graph.add_configuration(target_config)

    # Generate intermediate configurations using deterministic sampling
    num_steps = min(max_steps, 50)  # Limit for performance
    path = []

    # Simple interpolation-based path generation
    for step in range(num_steps + 1):
        t = step / num_steps
        interpolated = path_optimizer.interpolate_configuration(start_config, target_config, t)

        # Apply and compensate calibration error
        with_error = error_model.apply_calibration_error([a for a, v in interpolated])
        compensated = error_model.compensate_error(with_error)

        # Reconstruct configuration with compensated angles
        compensated_config = [(a, v) for a, (_, v) in zip(compensated, interpolated)]

        # Check collision
        angles = [a for a, _ in compensated_config]

        if not collision_detector.check_configuration_collision(joint_lengths, angles):
            if collision_detector.check_workspace_bounds(joint_lengths, angles):
                # Valid configuration
                idx = config_graph.add_configuration(compensated_config)

                # Connect to previous configuration
                if path:
                    prev_idx = config_graph.add_configuration(path[-1])
                    if path_optimizer.check_constraints(path[-1], compensated_config):
                        config_graph.add_edge(prev_idx, idx)

                path.append(compensated_config)

    # Ensure start and target are in path
    if not path or path[0] != start_config:
        path.insert(0, start_config)
    
    # Check if target is already in path (with tolerance for floating point errors)
    target_in_path = False
    if path:
        # Compare with tolerance of 1e-9 for floating point precision
        target_in_path = all(
            abs(a1 - a2) < 1e-9 and abs(v1 - v2) < 1e-9
            for (a1, v1), (a2, v2) in zip(path[-1], target_config)
        )
    
    if not target_in_path:
        path.append(target_config)

    # Compute metrics
    total_energy = 0.0
    total_time = 0.0
    total_distance = 0.0
    collision_free = True

    for i in range(len(path) - 1):
        energy = path_optimizer.compute_energy_cost(path[i], path[i + 1])
        time = path_optimizer.compute_time_cost(path[i], path[i + 1])

        # Angular distance
        distance = sum(abs(a2 - a1) for (a1, v1), (a2, v2) in zip(path[i], path[i + 1]))

        total_energy += energy
        total_time += time
        total_distance += distance

        # Check collision
        angles = [a for a, v in path[i + 1]]
        if collision_detector.check_configuration_collision(joint_lengths, angles):
            collision_free = False

    # Initialize connectivity analysis
    config_graph.initialize_union_find()

    # Count connected components
    components = set()
    for i in range(len(config_graph.nodes)):
        components.add(config_graph.union_find.find(i))

    num_components = len(components)

    # Build metrics
    metrics = {
        'average_energy_per_step': total_energy / max(len(path) - 1, 1),
        'average_time_per_step': total_time / max(len(path) - 1, 1),
        'average_angular_velocity': total_distance / max(total_time, 0.01),
        'path_efficiency': (total_distance / max(sum(abs(a2 - a1)
                            for (a1, _), (a2, _) in zip(start_config, target_config)), 0.01)),
        'workspace_utilization': sum(joint_lengths) / (
            (workspace_bounds[1][0] - workspace_bounds[0][0]) * 0.5
        ),
        'constraint_violations': 0,  # Track violations
        'calibration_error_magnitude': error_model.error_magnitude,
        'num_obstacles': len(obstacles)
    }

    # Check for constraint violations
    for i in range(len(path) - 1):
        if not path_optimizer.check_constraints(path[i], path[i + 1]):
            metrics['constraint_violations'] += 1

    return {
        'path': path,
        'total_energy': round(total_energy, 6),
        'total_time': round(total_time, 6),
        'total_distance': round(total_distance, 6),
        'collision_free': collision_free,
        'num_configurations': len(path),
        'connectivity_components': num_components,
        'metrics': metrics,
        'workspace_bounds': workspace_bounds,
        'num_obstacles': len(obstacles)
    }


def _validate_input(input_data: Dict) -> Dict:
    """Validate input data structure and types."""
    required_keys = ['k', 'joint_lengths', 'start_config', 'target_config']
    missing_keys = []
    for key in required_keys:
        if key not in input_data:
            missing_keys.append(key)
    if missing_keys:
        return {"error": f"Missing required keys: {', '.join(missing_keys)}."}

    if not isinstance(input_data['k'], int) or input_data['k'] <= 0:
        return {"error": "Parameter 'k' must be a positive integer."}

    if not isinstance(input_data['joint_lengths'], list) or len(input_data['joint_lengths']) != input_data['k']:
        return {"error": "Parameter 'joint_lengths' must be a list of length 'k'."}

    if not isinstance(input_data['start_config'], list) or len(input_data['start_config']) != input_data['k']:
        return {"error": "Parameter 'start_config' must be a list of length 'k'."}

    if not isinstance(input_data['target_config'], list) or len(input_data['target_config']) != input_data['k']:
        return {"error": "Parameter 'target_config' must be a list of length 'k'."}

    return {"status": "valid"}


def main_trigger(input_data: Dict) -> Dict:
    """
    Main entry point for k-linkage optimization system.

    Args:
        input_data: Dictionary containing:
            - k: int, number of joints
            - joint_lengths: List[float], length of each segment
            - start_config: List[List[float]], [[angle, velocity], ...]
            - target_config: List[List[float]], [[angle, velocity], ...]
            - obstacles: Optional[List[Dict]], obstacles with 'center' and 'radius'
            - workspace_bounds: Optional[List], [[min_x, min_y, min_z], [max_x, max_y, max_z]]
            - max_steps: Optional[int], maximum path steps

    Returns:
        Dictionary with optimization results including path, metrics, and costs
    """
    # Validate input
    validation_result = _validate_input(input_data)
    if 'error' in validation_result:
        return validation_result

    # Extract parameters
    k = input_data['k']
    joint_lengths = input_data['joint_lengths']

    # Convert nested lists to tuples
    start_config = [tuple(pair) for pair in input_data['start_config']]
    target_config = [tuple(pair) for pair in input_data['target_config']]

    # Optional parameters
    obstacles = input_data.get('obstacles', [])
    workspace_bounds_list = input_data.get('workspace_bounds')
    max_steps = input_data.get('max_steps', 50)

    # Convert workspace bounds if provided
    workspace_bounds = None
    if workspace_bounds_list:
        workspace_bounds = (
            tuple(workspace_bounds_list[0]),
            tuple(workspace_bounds_list[1])
        )

    # Run optimization
    result = optimize_k_linkage_path(
        k=k,
        joint_lengths=joint_lengths,
        start_config=start_config,
        target_config=target_config,
        obstacles=obstacles,
        workspace_bounds=workspace_bounds,
        max_steps=max_steps
    )

    # Convert path tuples back to lists
    result['path'] = [[list(pair) for pair in config] for config in result['path']]

    # Round numerical results
    result['total_energy'] = round(result['total_energy'], 6)
    result['total_time'] = round(result['total_time'], 6)
    result['total_distance'] = round(result['total_distance'], 6)
    for key in result['metrics']:
        if isinstance(result['metrics'][key], float):
            result['metrics'][key] = round(result['metrics'][key], 3)
    result['path'] = [
        [[round(angle, 2), round(velocity, 4)] for angle, velocity in config]
        for config in result['path']
    ]

    # Set workspace bounds back to list format
    if result['workspace_bounds']:
        result['workspace_bounds'] = [
            list(result['workspace_bounds'][0]),
            list(result['workspace_bounds'][1])
        ]

    return result


# Example usage
if __name__ == "__main__":
    input_data = {
        'k': 3,
        'joint_lengths': [2.0, 2.0, 1.5],
        'start_config': [[0.0, 0.0], [0.1, 0.0], [0.0, 0.0]],
        'target_config': [[1.57, 0.0], [0.78, 0.0], [0.78, 0.0]],
        'obstacles': [
            {'center': [3.0, 1.0, 0.5], 'radius': 0.5},
            {'center': [1.5, 2.5, 0.3], 'radius': 0.4}
        ],
        'max_steps': 30
    }
    result = main_trigger(input_data)
    print(result)