def find_nearest_depot(depots, target_distance, offline_depots=None, zero_capacity_depots=None, 
                      priority_levels=None, operating_hours=None, load_capacities=None, current_hour=12,
                      weather_affected_depots=None, service_types=None, required_service_type=None,
                      maintenance_schedules=None, depot_zones=None, allowed_zones=None, 
                      depot_costs=None, max_budget=None):
	"""Return index of nearest valid depot or -1."""
	# Normalize "empty" params to None
	def normalize(x):
		if x is None:
			return None
		if isinstance(x, dict) and len(x) == 0:
			return None
		if isinstance(x, (list, tuple)) and len(x) == 0:
			return None
		if isinstance(x, (int, float)) and x == 0:
			return None
		return x

	offline_depots = normalize(offline_depots)
	zero_capacity_depots = normalize(zero_capacity_depots)
	priority_levels = normalize(priority_levels)
	operating_hours = normalize(operating_hours)
	load_capacities = normalize(load_capacities)
	weather_affected_depots = normalize(weather_affected_depots)
	service_types = normalize(service_types)
	maintenance_schedules = normalize(maintenance_schedules)
	depot_zones = normalize(depot_zones)
	allowed_zones = normalize(allowed_zones)
	depot_costs = normalize(depot_costs)
	max_budget = normalize(max_budget)

	n = len(depots)
	# Helper checks
	offline_set = set(offline_depots) if offline_depots is not None else set()
	zero_capacity_set = set(zero_capacity_depots) if zero_capacity_depots is not None else set()
	weather_set = set(weather_affected_depots) if weather_affected_depots is not None else set()

	# If priority_levels not given, default 1 for all
	if priority_levels is None:
		priority_levels = [1] * n
	else:
		# pad or trim if wrong length
		if len(priority_levels) < n:
			priority_levels = list(priority_levels) + [1] * (n - len(priority_levels))
		else:
			priority_levels = list(priority_levels)[:n]

	# operating_hours: default 24/7
	if operating_hours is None:
		operating_hours = [[0, 24]] * n
	else:
		oh = []
		for i in range(n):
			if i < len(operating_hours) and operating_hours[i] is not None:
				oh.append(list(operating_hours[i]))
			else:
				oh.append([0, 24])
		operating_hours = oh

	# load capacities default large
	if load_capacities is None:
		load_capacities = [10**18] * n
	else:
		lc = []
		for i in range(n):
			if i < len(load_capacities) and load_capacities[i] is not None:
				lc.append(load_capacities[i])
			else:
				lc.append(10**18)
		load_capacities = lc

	# service types default all
	if service_types is None:
		service_types = [None] * n
	else:
		st = []
		for i in range(n):
			if i < len(service_types):
				st.append(service_types[i])
			else:
				st.append(None)
		service_types = st

	# maintenance schedules default none
	if maintenance_schedules is None:
		maintenance_schedules = [None] * n
	else:
		ms = []
		for i in range(n):
			if i < len(maintenance_schedules):
				ms.append(maintenance_schedules[i])
			else:
				ms.append(None)
		maintenance_schedules = ms

	# depot_zones default all allowed
	if depot_zones is None:
		depot_zones = [None] * n
	else:
		dz = []
		for i in range(n):
			if i < len(depot_zones):
				dz.append(depot_zones[i])
			else:
				dz.append(None)
		depot_zones = dz

	# depot_costs default none (treat as 0/unbounded)
	if depot_costs is None:
		depot_costs = [None] * n
	else:
		dc = []
		for i in range(n):
			if i < len(depot_costs):
				dc.append(depot_costs[i])
			else:
				dc.append(None)
		depot_costs = dc

	# Utility to check if hour is within [start, end). If end <= start, treat as wrap-around.
	def in_hours(hour, start, end):
		if start is None or end is None:
			return True
		start = int(start)
		end = int(end)
		hour = int(hour) % 24
		if start < end:
			return start <= hour < end
		if start == end:
			# full day
			return True
		# wrap
		return hour >= start or hour < end

	# Validate each depot against constraints, collect candidates with metrics
	best = None  # tuple (absdiff, -priority, index)
	best_index = -1

	for i in range(n):
		# Online
		if i in offline_set:
			continue
		# Zero capacity
		if i in zero_capacity_set:
			continue
		# load capacity > 0
		if load_capacities is not None and (load_capacities[i] is None or load_capacities[i] <= 0):
			continue
		# operating hours
		start_end = operating_hours[i]
		if start_end is None:
			pass
		else:
			if not in_hours(current_hour, start_end[0], start_end[1]):
				continue
		# weather
		if i in weather_set:
			continue
		# service type compatibility
		if required_service_type is not None:
			st = service_types[i]
			# None in service_types means supports all
			if st is not None:
				# allow either exact match or list/collection containing required
				if isinstance(st, (list, tuple, set)):
					if required_service_type not in st:
						continue
				else:
					if st != required_service_type:
						continue
		# maintenance
		ms = maintenance_schedules[i]
		if ms is not None:
			# assume single window [start,end)
			if len(ms) >= 2 and not (ms[0] is None or ms[1] is None):
				if in_hours(current_hour, ms[0], ms[1]):
					continue
		# zone
		if allowed_zones is not None:
			zone = depot_zones[i]
			if zone is not None:
				if zone not in allowed_zones:
					continue
		# budget
		if max_budget is not None:
			cost = depot_costs[i]
			if cost is None:
				# treat None as allowed (no cost info)
				pass
			else:
				try:
					if cost > max_budget:
						continue
				except:
					pass

		# Passed filters. Compute selection metrics.
		dist = depots[i]
		absdiff = abs(dist - target_distance)
		priority = priority_levels[i] if priority_levels is not None else 1
		metric = (absdiff, -priority, i)
		if best is None or metric < best:
			best = metric
			best_index = i

	return best_index if best_index is not None else -1