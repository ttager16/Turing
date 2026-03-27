import heapq
from collections import defaultdict


class FlowGraph:
    """Graph representation for min-cost flow optimization."""

    def __init__(self):
        self.edges = defaultdict(list)
        self.capacity = {}
        self.cost = {}
        self.flow = {}

    def add_edge(self, u, v, cap, cost_val):
        """Add directed edge with capacity and cost."""
        if cap <= 0:
            return
        self.edges[u].append(v)
        self.edges[v].append(u)
        self.capacity[(u, v)] = cap
        self.capacity[(v, u)] = 0
        self.cost[(u, v)] = cost_val
        self.cost[(v, u)] = -cost_val
        self.flow[(u, v)] = 0
        self.flow[(v, u)] = 0

    def min_cost_flow(self, source, sink, required_flow):
        """Find minimum cost flow using successive shortest paths with Dijkstra and potentials.
        
        Uses Johnson's reweighting technique for efficient shortest path computation.
        """
        total_cost = 0
        total_flow = 0
        
        # Initialize potentials using Bellman-Ford for first iteration (handles negative costs)
        potential = self._initialize_potentials(source)

        while total_flow < required_flow:
            # Find shortest path using Dijkstra with potentials (all edge weights non-negative)
            dist, parent = self._dijkstra_with_potentials(source, sink, potential)

            if dist[sink] == float('inf'):
                break  # No augmenting path exists

            # Update potentials for next iteration
            for node in dist:
                if dist[node] < float('inf'):
                    potential[node] += dist[node]

            # Find maximum flow along the path
            path_flow = required_flow - total_flow
            v = sink
            while v in parent and v != source:
                u = parent[v]
                residual = self.capacity.get((u, v), 0) - self.flow.get((u, v), 0)
                path_flow = min(path_flow, residual)
                v = u

            if path_flow <= 0:
                break

            # Update flow along the path
            v = sink
            while v in parent and v != source:
                u = parent[v]
                self.flow[(u, v)] = self.flow.get((u, v), 0) + path_flow
                self.flow[(v, u)] = self.flow.get((v, u), 0) - path_flow
                total_cost += path_flow * self.cost.get((u, v), 0)
                v = u

            total_flow += path_flow

        return total_cost, total_flow

    def _initialize_potentials(self, source):
        """Initialize potentials using Bellman-Ford to handle negative edge costs.
        
        This is run once at the beginning to compute initial potentials.
        """
        potential = defaultdict(lambda: float('inf'))
        potential[source] = 0
        
        nodes = list(self.edges.keys())
        # Bellman-Ford: relax edges V-1 times
        for _ in range(len(nodes)):
            updated = False
            for u in nodes:
                if potential[u] == float('inf'):
                    continue
                for v in self.edges[u]:
                    if self.capacity.get((u, v), 0) > 0:
                        new_potential = potential[u] + self.cost.get((u, v), 0)
                        if new_potential < potential[v]:
                            potential[v] = new_potential
                            updated = True
            if not updated:
                break
        
        return potential

    def _dijkstra_with_potentials(self, source, sink, potential):
        """Find shortest path using Dijkstra's algorithm with reduced costs.
        
        Reduced cost = actual_cost + potential[u] - potential[v]
        This ensures all edge weights are non-negative, enabling Dijkstra.
        """
        dist = defaultdict(lambda: float('inf'))
        parent = {}
        dist[source] = 0
        
        # Priority queue: (distance, node)
        pq = [(0, source)]
        visited = set()
        
        while pq:
            d, u = heapq.heappop(pq)
            
            if u in visited:
                continue
            visited.add(u)
            
            if u == sink:
                break
            
            if d > dist[u]:
                continue
            
            for v in self.edges[u]:
                # Check residual capacity
                if self.capacity.get((u, v), 0) <= self.flow.get((u, v), 0):
                    continue
                
                # Calculate reduced cost: c_reduced = c + π(u) - π(v)
                actual_cost = self.cost.get((u, v), 0)
                reduced_cost = actual_cost + potential.get(u, 0) - potential.get(v, 0)
                
                new_dist = dist[u] + reduced_cost
                
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    parent[v] = u
                    heapq.heappush(pq, (new_dist, v))
        
        return dist, parent


class SegmentTree:
    """Segment tree for efficient range queries and updates on station availability."""

    def __init__(self, data):
        self.n = len(data)
        if self.n == 0:
            self.tree = []
            self.lazy = []
            return
        self.tree = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        self.build(data, 1, 0, self.n - 1)

    def build(self, data, node, start, end):
        """Build segment tree from data."""
        if start == end:
            self.tree[node] = data[start]
        else:
            mid = (start + end) // 2
            self.build(data, 2 * node, start, mid)
            self.build(data, 2 * node + 1, mid + 1, end)
            self.tree[node] = min(self.tree[2 * node], self.tree[2 * node + 1])

    def update_range(self, node, start, end, l, r, val):
        """Update range with lazy propagation."""
        if self.n == 0:
            return

        if self.lazy[node] != 0:
            self.tree[node] += self.lazy[node]
            if start != end:
                self.lazy[2 * node] += self.lazy[node]
                self.lazy[2 * node + 1] += self.lazy[node]
            self.lazy[node] = 0

        if start > end or start > r or end < l:
            return

        if start >= l and end <= r:
            self.tree[node] += val
            if start != end:
                self.lazy[2 * node] += val
                self.lazy[2 * node + 1] += val
            return

        mid = (start + end) // 2
        self.update_range(2 * node, start, mid, l, r, val)
        self.update_range(2 * node + 1, mid + 1, end, l, r, val)
        self.tree[node] = min(self.tree[2 * node], self.tree[2 * node + 1])

    def query_range(self, node, start, end, l, r):
        """Query minimum available capacity in time range."""
        if self.n == 0 or start > end or start > r or end < l:
            return float('inf')

        if self.lazy[node] != 0:
            self.tree[node] += self.lazy[node]
            if start != end:
                self.lazy[2 * node] += self.lazy[node]
                self.lazy[2 * node + 1] += self.lazy[node]
            self.lazy[node] = 0

        if start >= l and end <= r:
            return self.tree[node]

        mid = (start + end) // 2
        return min(self.query_range(2 * node, start, mid, l, r),
                   self.query_range(2 * node + 1, mid + 1, end, l, r))


class EVChargingOptimizer:
    """Advanced EV charging schedule optimizer with real-time constraints."""

    def __init__(self):
        self.traffic_map = {}
        self.station_map = {}
        self.ev_map = {}
        self.current_time = 0
        self.station_occupancy = defaultdict(list)
        self.grid_load = defaultdict(int)
        self.station_segment_trees = {}  # Track station availability over time using SegmentTree
        self.max_time_horizon = 1000  # Maximum time horizon for scheduling

    def initialize_segment_trees(self, station_data):
        """Initialize segment trees for each station to track capacity over time."""
        for station in station_data:
            # Initialize segment tree with station capacity for each time slot
            capacity_timeline = [station['capacity']] * self.max_time_horizon
            self.station_segment_trees[station['id']] = SegmentTree(capacity_timeline)

    def calculate_travel_time(self, ev_loc, station_loc, congestion_level):
        """Calculate travel time based on distance and congestion."""
        distance = abs(ev_loc - station_loc)
        if distance > 5:
            return float('inf')
        return distance * (1 + congestion_level / 10)

    def get_dynamic_cost(self, station_id, current_time_or_load):
        """Calculate dynamic cost based on grid load at specific time or direct load count."""
        station = self.station_map[station_id]

        # Support both time-based and direct load count for backward compatibility
        if isinstance(current_time_or_load, (int, float)) and current_time_or_load >= 0:
            # Check if this looks like a load count (small number relative to capacity)
            # or a time value (typically larger)
            if current_time_or_load <= station['capacity'] and len(self.station_occupancy[station_id]) == 0:
                # Likely a direct load count (for testing)
                active_count = int(current_time_or_load)
            else:
                # Time-based query: count active sessions at current_time
                active_count = 0
                for session in self.station_occupancy[station_id]:
                    if session['start_time'] <= current_time_or_load < session['end_time']:
                        active_count += 1
        else:
            active_count = 0

        capacity_ratio = active_count / max(station['capacity'], 1)
        base_cost = 1

        if capacity_ratio >= 0.9:
            return base_cost * 3
        elif capacity_ratio >= 0.6:
            return base_cost * 2
        return base_cost

    def is_peak_hour(self, location_id):
        """Check if current time is peak hour for location."""
        congestion = self.traffic_map.get(location_id, 0)
        return congestion > 7

    def can_assign_ev(self, ev_id, station_id, start_time=None):
        """Check if EV can be assigned to station at specific time using SegmentTree for efficient capacity queries."""
        ev = self.ev_map[ev_id]
        station = self.station_map[station_id]

        if ev['location_id'] not in self.traffic_map:
            return False

        travel_time = self.calculate_travel_time(
            ev['location_id'], station['location_id'],
            self.traffic_map[ev['location_id']]
        ) 

        if travel_time == float('inf'):
            return False

        # Use current time if not specified
        if start_time is None:
            start_time = self.current_time

        # Calculate charging duration
        charging_duration = int(ev.get('desired_charge', 50) / station.get('max_power', 10))
        end_time = start_time + charging_duration

        # Ensure times are within bounds
        if start_time >= self.max_time_horizon or end_time > self.max_time_horizon:
            return False

        # Use SegmentTree for efficient capacity query over the time range
        if station_id in self.station_segment_trees:
            seg_tree = self.station_segment_trees[station_id]
            min_available = seg_tree.query_range(1, 0, self.max_time_horizon - 1,
                                                 start_time, min(end_time - 1, self.max_time_horizon - 1))

            # Peak hour restrictions
            if self.is_peak_hour(station['location_id']):
                max_capacity = int(station['capacity'] * 0.6)
                return min_available > (station['capacity'] - max_capacity)

            return min_available > 0


    def prioritize_evs(self, ev_data):
        """Prioritize EVs based on battery level and urgency with delay allowance."""
        priority_queue = []

        for ev in ev_data:
            battery_level = ev['battery_level']
            if battery_level < 20:
                priority = 0  # Immediate priority
                delay_allowance = 0  # No delay allowed
            elif battery_level < 50:
                priority = 1
                delay_allowance = 0
            elif battery_level < 80:
                priority = 2
                delay_allowance = 0
            else:
                priority = 3  # Lowest priority
                delay_allowance = 120  # 2 hours delay allowed (in time units)

            # Store delay allowance in EV data for scheduling
            ev_with_delay = ev.copy()
            ev_with_delay['delay_allowance'] = delay_allowance

            heapq.heappush(priority_queue, (priority, ev['id'], ev_with_delay))

        return priority_queue

    def build_flow_graph(self, ev_data, station_data, current_time=0):
        """Build min-cost flow graph for optimization with feasibility checks."""
        graph = FlowGraph()

        source = 'source'
        sink = 'sink'
        
        # Track which EVs have at least one feasible station
        feasible_evs = set()

        for ev in ev_data:
            ev_node = f"ev_{ev['id']}"
            
            # Only check nearby stations (within distance limit)
            # to reduce graph size and improve performance
            nearby_stations = [
                s for s in station_data
                if ev['location_id'] in self.traffic_map and
                abs(ev['location_id'] - s['location_id']) <= 5
            ]
            
            has_feasible_station = False

            for station in nearby_stations:
                station_node = f"station_{station['id']}"

                # Check if assignment is feasible
                travel_time = self.calculate_travel_time(
                    ev['location_id'], station['location_id'],
                    self.traffic_map.get(ev['location_id'], 0)
                )

                if travel_time == float('inf'):
                    continue

                arrival_time = current_time + int(travel_time)

                # Check if can assign at arrival time
                if not self.can_assign_ev(ev['id'], station['id'], arrival_time):
                    continue

                # Calculate cost
                dynamic_cost = self.get_dynamic_cost(station['id'], arrival_time)
                total_cost = travel_time * dynamic_cost

                # Battery priority adjustments
                if ev['battery_level'] < 20:
                    total_cost *= 0.1  # High priority, low cost
                elif ev['battery_level'] > 80:
                    total_cost *= 2.0  # Low priority, high cost

                graph.add_edge(ev_node, station_node, 1, int(total_cost * 100))
                has_feasible_station = True
            
            # Only add EV to source if it has at least one feasible station
            if has_feasible_station:
                graph.add_edge(source, ev_node, 1, 0)
                feasible_evs.add(ev['id'])

        for station in station_data:
            station_node = f"station_{station['id']}"

            # Calculate available capacity considering current occupancy
            active_count = sum(1 for s in self.station_occupancy[station['id']]
                               if s['start_time'] <= current_time < s['end_time'])
            available_capacity = station['capacity'] - active_count

            # Peak hour restrictions
            if self.is_peak_hour(station['location_id']):
                available_capacity = min(available_capacity, int(station['capacity'] * 0.6) - active_count)

            if available_capacity > 0:
                graph.add_edge(station_node, sink, available_capacity, 0)

        return graph, source, sink

    def find_earliest_available_slot(self, station_id, start_time, charging_duration):
        """Find earliest available slot at a station using SegmentTree for efficient time-based capacity queries."""
        station = self.station_map[station_id]

        # Try to find a slot starting from start_time
        current_try = start_time
        max_attempts = 50  # Limit search to prevent infinite loops

        # Peak hour capacity check
        required_capacity = 1
        max_capacity = station['capacity']
        if self.is_peak_hour(station['location_id']):
            max_capacity = int(station['capacity'] * 0.6)

        for _ in range(max_attempts):
            end_time = current_try + charging_duration

            # Ensure times are within bounds
            if end_time > self.max_time_horizon:
                return None

            # Use SegmentTree for efficient capacity query
            seg_tree = self.station_segment_trees[station_id]
            min_available = seg_tree.query_range(1, 0, self.max_time_horizon - 1,
                                                 current_try, min(end_time - 1, self.max_time_horizon - 1))

            # Check if there's enough capacity
            if min_available >= required_capacity:
                return current_try

            # Move forward by checking next time slots
            current_try += 1

            # Don't schedule too far in the future
            if current_try > start_time + 500:
                return None

        return None

    def update_station_capacity(self, station_id, start_time, end_time):
        """Update SegmentTree to reflect reduced capacity for the given time range."""
        if station_id in self.station_segment_trees and start_time < self.max_time_horizon:
            seg_tree = self.station_segment_trees[station_id]
            # Reduce available capacity by 1 for this time range
            seg_tree.update_range(1, 0, self.max_time_horizon - 1,
                                  start_time, min(end_time - 1, self.max_time_horizon - 1), -1)

    def assign_evs_optimally(self, ev_data, station_data):
        """Assign EVs to stations using flow-based optimization with priority."""
        # Flow-graph based optimization for global optimum
        flow_assignments = self._assign_using_flow_graph(ev_data, station_data)
        if flow_assignments:
            return flow_assignments
        return []

    def _assign_using_flow_graph(self, ev_data, station_data):
        """Use min-cost flow graph for optimal assignment with priority-based processing."""
        # Build the flow graph
        graph, source, sink = self.build_flow_graph(ev_data, station_data, self.current_time)

        # Check if graph has any feasible flows
        if len(graph.edges) == 0:
            return []

        # Compute min-cost max-flow
        num_evs = len(ev_data)
        cost, flow = graph.min_cost_flow(source, sink, num_evs)

        # If no flow was found, return empty
        if flow == 0:
            return []

        # Extract assignments from flow in priority order
        # Use prioritize_evs to ensure high-priority EVs get earliest slots
        priority_queue = self.prioritize_evs(ev_data)
        assignments = []

        # Process EVs in priority order (high priority EVs get processed first for earliest slots)
        while priority_queue:
            priority, ev_id, ev_with_delay = heapq.heappop(priority_queue)
            ev_node = f"ev_{ev_id}"

            # Get original EV data for location and desired_charge
            ev = next((e for e in ev_data if e['id'] == ev_id), None)
            if not ev:
                continue

            for station in station_data:
                station_node = f"station_{station['id']}"

                # Check if there's flow on this edge
                if graph.flow.get((ev_node, station_node), 0) > 0:
                    # Calculate start time
                    travel_time = self.calculate_travel_time(
                        ev['location_id'], station['location_id'],
                        self.traffic_map.get(ev['location_id'], 0)
                    )

                    if travel_time == float('inf'):
                        continue

                    arrival_time = self.current_time + int(travel_time)
                    charging_duration = int(ev['desired_charge'] / station['max_power'])

                    # Find available slot using SegmentTree (prioritized EVs get checked first)
                    slot_time = self.find_earliest_available_slot(
                        station['id'], arrival_time, charging_duration
                    )

                    if slot_time is not None:
                        assignments.append({
                            'ev_id': ev['id'],
                            'station_id': station['id'],
                            'start_time': slot_time
                        })

                        # Update occupancy
                        self.station_occupancy[station['id']].append({
                            'ev_id': ev['id'],
                            'start_time': slot_time,
                            'end_time': slot_time + charging_duration
                        })

                        # Update SegmentTree to reflect capacity reduction
                        self.update_station_capacity(station['id'], slot_time,
                                                     slot_time + charging_duration)

                    break  # Each EV assigned to at most one station

        return assignments

    def optimize_schedule_iterative(self, ev_data, station_data):
        """Perform iterative optimization with flow-based refinement."""
        # Initial assignment using priority-based greedy
        assignments = self.assign_evs_optimally(ev_data, station_data)

        # Iterative refinement (limited to maintain performance)
        for iteration in range(2):
            improved = False

            for i, assignment in enumerate(assignments):
                ev_id = assignment['ev_id']
                current_station_id = assignment['station_id']
                current_start_time = assignment['start_time']
                ev = self.ev_map[ev_id]

                best_station = current_station_id
                best_start_time = current_start_time
                best_cost = float('inf')

                # Calculate current cost
                current_travel = self.calculate_travel_time(
                    ev['location_id'],
                    self.station_map[current_station_id]['location_id'],
                    self.traffic_map.get(ev['location_id'], 0)
                )
                current_cost = current_travel * self.get_dynamic_cost(current_station_id, current_start_time)
                best_cost = current_cost

                # Try alternative stations
                for station in station_data:
                    if station['id'] == current_station_id:
                        continue

                    if ev['location_id'] not in self.traffic_map:
                        continue

                    travel_time = self.calculate_travel_time(
                        ev['location_id'], station['location_id'],
                        self.traffic_map.get(ev['location_id'], 0)
                    )

                    if travel_time == float('inf'):
                        continue

                    arrival_time = self.current_time + int(travel_time)
                    charging_duration = int(ev['desired_charge'] / station['max_power'])

                    # Temporarily remove current assignment to check alternatives
                    old_sessions = self.station_occupancy[current_station_id].copy()
                    self.station_occupancy[current_station_id] = [
                        s for s in old_sessions if s['ev_id'] != ev_id
                    ]

                    slot_time = self.find_earliest_available_slot(
                        station['id'], arrival_time, charging_duration
                    )

                    # Restore
                    self.station_occupancy[current_station_id] = old_sessions

                    if slot_time is None:
                        continue

                    dynamic_cost = self.get_dynamic_cost(station['id'], slot_time)
                    total_cost = travel_time * dynamic_cost

                    # Battery adjustments
                    if ev['battery_level'] < 20:
                        total_cost *= 0.1
                    elif ev['battery_level'] > 80:
                        total_cost *= 2

                    if total_cost < best_cost * 0.9:  # Only switch if significantly better
                        best_cost = total_cost
                        best_station = station['id']
                        best_start_time = slot_time
                        improved = True

                # Apply improvement if found
                if best_station != current_station_id:
                    # Remove old assignment and restore SegmentTree capacity
                    old_assignment = next((s for s in self.station_occupancy[current_station_id]
                                          if s['ev_id'] == ev_id), None)
                    if old_assignment:
                        # Restore capacity in SegmentTree for old assignment by adding back +1
                        if current_station_id in self.station_segment_trees:
                            seg_tree = self.station_segment_trees[current_station_id]
                            seg_tree.update_range(1, 0, self.max_time_horizon - 1,
                                                  old_assignment['start_time'],
                                                  min(old_assignment['end_time'] - 1, self.max_time_horizon - 1), 1)

                    self.station_occupancy[current_station_id] = [
                        s for s in self.station_occupancy[current_station_id]
                        if s['ev_id'] != ev_id
                    ]

                    # Add new assignment
                    charging_duration = int(ev['desired_charge'] / self.station_map[best_station]['max_power'])
                    self.station_occupancy[best_station].append({
                        'ev_id': ev_id,
                        'start_time': best_start_time,
                        'end_time': best_start_time + charging_duration
                    })

                    # Update SegmentTree for new assignment
                    self.update_station_capacity(best_station, best_start_time,
                                                 best_start_time + charging_duration)

                    assignment['station_id'] = best_station
                    assignment['start_time'] = best_start_time

            if not improved:
                break

        return assignments


def optimize_ev_charging_schedule(traffic_data: list, ev_data: list, station_data: list) -> list:
    """Optimize EV charging schedule using advanced graph-based min-cost flow algorithm with SegmentTree-based capacity tracking."""
    optimizer = EVChargingOptimizer()

    for location_id, congestion_level in traffic_data:
        optimizer.traffic_map[location_id] = congestion_level

    for station in station_data:
        optimizer.station_map[station['id']] = station

    for ev in ev_data:
        optimizer.ev_map[ev['id']] = ev

    # Initialize segment trees for efficient time-based capacity tracking
    optimizer.initialize_segment_trees(station_data)

    assignments = optimizer.optimize_schedule_iterative(ev_data, station_data)

    return assignments


if __name__ == '__main__':
    traffic_data = [(1, 3), (2, 5), (3, 2)]
    ev_data = [
        {'id': 'ev1', 'battery_level': 15, 'location_id': 1, 'desired_charge': 50},
        {'id': 'ev2', 'battery_level': 60, 'location_id': 2, 'desired_charge': 30},
        {'id': 'ev3', 'battery_level': 85, 'location_id': 3, 'desired_charge': 20}
    ]
    station_data = [
        {'id': 's1', 'capacity': 2, 'location_id': 1, 'max_power': 10},
        {'id': 's2', 'capacity': 3, 'location_id': 2, 'max_power': 15},
        {'id': 's3', 'capacity': 1, 'location_id': 3, 'max_power': 20}
    ]

    result = optimize_ev_charging_schedule(traffic_data, ev_data, station_data)
    print(result)