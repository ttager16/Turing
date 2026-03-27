def find_nearest_depot(depots, target_distance, offline_depots=None, zero_capacity_depots=None, 
                      priority_levels=None, operating_hours=None, load_capacities=None, current_hour=12,
                      weather_affected_depots=None, service_types=None, required_service_type=None,
                      maintenance_schedules=None, depot_zones=None, allowed_zones=None, 
                      depot_costs=None, max_budget=None):
	"""Return index of nearest valid depot or -1."""
	# Treat empty dicts/collections/zero as "not provided" (equivalent to None for consistency)
	def is_empty(param):
		"""Check if parameter is empty/not provided."""
		if param is None:
			return True
		if param == {} or param == []:
			return True
		if isinstance(param, (int, float)) and param == 0:
			return True
		return False
	
	# Normalize all empty values to None for consistent handling
	if is_empty(offline_depots):
		offline_depots = None
	if is_empty(zero_capacity_depots):
		zero_capacity_depots = None
	if is_empty(priority_levels):
		priority_levels = None
	if is_empty(operating_hours):
		operating_hours = None
	if is_empty(load_capacities):
		load_capacities = None
	if is_empty(weather_affected_depots):
		weather_affected_depots = None
	if is_empty(service_types):
		service_types = None
	if is_empty(maintenance_schedules):
		maintenance_schedules = None
	if is_empty(depot_zones):
		depot_zones = None
	if is_empty(allowed_zones):
		allowed_zones = None
	if is_empty(depot_costs):
		depot_costs = None
	if is_empty(max_budget):
		max_budget = None
	# Handle current_hour if it's a dict (shouldn't happen, but be safe)
	if isinstance(current_hour, dict):
		current_hour = 12
	
	manager = DepotManager(len(depots), current_hour)
	
	if offline_depots is not None:
		manager.set_offline(offline_depots)
	
	if zero_capacity_depots is not None:
		manager.set_nocap(zero_capacity_depots)
	
	if priority_levels is not None:
		manager.set_priorities(priority_levels)
	
	if operating_hours is not None:
		manager.set_operating_hours(operating_hours)
	
	if load_capacities is not None:
		manager.set_load_capacities(load_capacities)
	
	if weather_affected_depots is not None:
		manager.set_weather_affected(weather_affected_depots)
	
	if service_types is not None:
		manager.set_service_types(service_types)
	
	if maintenance_schedules is not None:
		manager.set_maintenance_schedules(maintenance_schedules)
	
	if depot_zones is not None:
		manager.set_depot_zones(depot_zones)
	
	if depot_costs is not None:
		manager.set_depot_costs(depot_costs)
	
	manager.required_service_type = required_service_type
	manager.allowed_zones = allowed_zones
	manager.max_budget = max_budget
	
	tree = SegmentTree(depots, manager.valid_mask(), manager.priority)
	return tree.query_nearest(target_distance)


class DepotManager:
	"""Track depot online and capacity status."""
	def __init__(self, size, current_hour=12):
		self.size = size
		self.online = [True] * size
		self.capacity = [1] * size
		self.priority = [1] * size
		self.operating_hours = [(0, 24)] * size
		self.load_capacity = [float('inf')] * size
		self.current_hour = current_hour
		self.weather_affected = [False] * size
		self.service_types = ['all'] * size
		self.required_service_type = None
		self.maintenance_schedules = [(0, 0)] * size
		self.depot_zones = ['all'] * size
		self.allowed_zones = None
		self.depot_costs = [0] * size
		self.max_budget = None

	def reset(self, size):
		"""Reset manager with given size."""
		self.size = size
		self.online = [True] * size
		self.capacity = [1] * size
		self.priority = [1] * size
		self.operating_hours = [(0, 24)] * size
		self.load_capacity = [float('inf')] * size

	def set_offline(self, indices):
		"""Set given indices offline."""
		for i in indices:
			if 0 <= i < self.size:
				self.online[i] = False

	def set_nocap(self, indices):
		"""Set capacity zero for indices."""
		for i in indices:
			if 0 <= i < self.size:
				self.capacity[i] = 0

	def set_priorities(self, priorities):
		"""Set priority levels for depots."""
		for i, p in enumerate(priorities):
			if 0 <= i < self.size:
				self.priority[i] = p

	def set_operating_hours(self, hours):
		"""Set operating hours for depots."""
		for i, (start, end) in enumerate(hours):
			if 0 <= i < self.size:
				self.operating_hours[i] = (start, end)

	def set_load_capacities(self, capacities):
		"""Set load capacities for depots."""
		for i, cap in enumerate(capacities):
			if 0 <= i < self.size:
				self.load_capacity[i] = cap
	
	def set_weather_affected(self, weather_affected_depots):
		"""Set weather-affected depots."""
		for idx in weather_affected_depots:
			if 0 <= idx < self.size:
				self.weather_affected[idx] = True
	
	def set_service_types(self, service_types):
		"""Set service types for depots."""
		for i, service_type in enumerate(service_types):
			if i < self.size:
				self.service_types[i] = service_type
	
	def set_maintenance_schedules(self, maintenance_schedules):
		"""Set maintenance schedules for depots."""
		for i, (start, end) in enumerate(maintenance_schedules):
			if i < self.size:
				self.maintenance_schedules[i] = (start, end)
	
	def set_depot_zones(self, depot_zones):
		"""Set zones for depots."""
		for i, zone in enumerate(depot_zones):
			if i < self.size:
				self.depot_zones[i] = zone
	
	def set_depot_costs(self, depot_costs):
		"""Set costs for depots."""
		for i, cost in enumerate(depot_costs):
			if i < self.size:
				self.depot_costs[i] = cost

	def is_valid(self, idx):
		"""Return validity of depot idx."""
		if not self.online[idx] or self.capacity[idx] <= 0:
			return False
		start, end = self.operating_hours[idx]
		if not (start <= self.current_hour < end):
			return False
		if self.load_capacity[idx] <= 0:
			return False
		if self.weather_affected[idx]:
			return False
		if self.required_service_type is not None:
			if self.service_types[idx] != 'all' and self.service_types[idx] != self.required_service_type:
				return False
		maintenance_start, maintenance_end = self.maintenance_schedules[idx]
		if maintenance_start != maintenance_end and maintenance_start <= self.current_hour < maintenance_end:
			return False
		if self.allowed_zones is not None:
			if self.depot_zones[idx] not in self.allowed_zones:
				return False
		if self.max_budget is not None:
			if self.depot_costs[idx] > self.max_budget:
				return False
		return True

	def valid_mask(self):
		"""Return validity mask list."""
		return [self.is_valid(i) for i in range(self.size)]


class SegmentTree:
	"""Segment tree for nearest valid value search."""
	def __init__(self, values, valid_mask, priorities=None):
		self.values = list(values)
		self.n = len(values)
		self.priorities = priorities if priorities is not None else [1] * self.n
		sz = 1
		while sz < self.n:
			sz <<= 1
		self.size_pow2 = sz
		m = sz << 1
		self.minv = [0] * m
		self.maxv = [0] * m
		self.has = [False] * m
		self._build(values, valid_mask)

	def _build(self, values, valid_mask):
		"""Build tree from values and mask."""
		for i in range(self.size_pow2):
			node = i + self.size_pow2
			if i < self.n:
				self.minv[node] = values[i]
				self.maxv[node] = values[i]
				self.has[node] = bool(valid_mask[i])
			else:
				self.minv[node] = 10**18
				self.maxv[node] = -10**18
				self.has[node] = False
		for node in range(self.size_pow2 - 1, 0, -1):
			l = node << 1
			r = l | 1
			self.minv[node] = self.minv[l] if self.minv[l] < self.minv[r] else self.minv[r]
			self.maxv[node] = self.maxv[l] if self.maxv[l] > self.maxv[r] else self.maxv[r]
			self.has[node] = self.has[l] or self.has[r]

	def update_value(self, idx, val):
		"""Update value at index."""
		self.values[idx] = val
		node = idx + self.size_pow2
		self.minv[node] = val
		self.maxv[node] = val
		node >>= 1
		while node:
			l = node << 1
			r = l | 1
			self.minv[node] = self.minv[l] if self.minv[l] < self.minv[r] else self.minv[r]
			self.maxv[node] = self.maxv[l] if self.maxv[l] > self.maxv[r] else self.maxv[r]
			node >>= 1

	def update_valid_mask(self, valid_mask):
		"""Replace validity mask."""
		for i in range(self.size_pow2):
			node = i + self.size_pow2
			if i < self.n:
				self.has[node] = bool(valid_mask[i])
			else:
				self.has[node] = False
		for node in range(self.size_pow2 - 1, 0, -1):
			l = node << 1
			r = l | 1
			self.has[node] = self.has[l] or self.has[r]

	def _lower_bound_dist(self, node, target):
		"""Return lower bound distance for node."""
		if not self.has[node]:
			return 10**18
		mn = self.minv[node]
		mx = self.maxv[node]
		if target < mn:
			return mn - target
		if target > mx:
			return target - mx
		return 0

	def query_nearest(self, target):
		"""Return index of nearest valid by value with tie-breaking."""
		if not self.has[1]:
			return -1
		best_diff = 10**18
		best_idx = -1
		best_priority = 0
		stack = [(1, 0)]
		while stack:
			node, lb = stack.pop()
			if lb > best_diff:
				continue
			if node >= self.size_pow2:
				i = node - self.size_pow2
				if i < self.n and self.has[node]:
					val = self.values[i]
					diff = val - target
					if diff < 0:
						diff = -diff
					priority = self.priorities[i]
					if (diff < best_diff or 
						(diff == best_diff and priority > best_priority) or
						(diff == best_diff and priority == best_priority and i < best_idx)):
						best_diff = diff
						best_idx = i
						best_priority = priority
				continue
			l = node << 1
			r = l | 1
			if self.has[l]:
				lb_l = self._lower_bound_dist(l, target)
				if lb_l <= best_diff:
					stack.append((l, lb_l))
			if self.has[r]:
				lb_r = self._lower_bound_dist(r, target)
				if lb_r <= best_diff:
					stack.append((r, lb_r))
		return best_idx


if __name__ == '__main__':
	depots = [15, 14, 28, 16, 20, 22, 21, 23, 19, 25]
	target_distance = 17
	offline_depots = [1]
	zero_capacity_depots = None
	priority_levels = [3, 1, 5, 2, 4, 1, 3, 2, 4, 1]
	operating_hours = [[8, 18], [6, 22], [0, 24], [9, 17], [7, 19], [8, 20], [6, 18], [9, 21], [7, 17], [8, 16]]
	load_capacities = [100, 50, 200, 75, 150, 25, 125, 80, 175, 30]
	res = find_nearest_depot(depots, target_distance, offline_depots, zero_capacity_depots, 
	                       priority_levels, operating_hours, load_capacities)
	print(res)