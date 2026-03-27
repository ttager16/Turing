def optimize_ride_matching(driver_profiles: List[Dict], passenger_requests: List[Dict], 
                         service_zones: List[Dict], temporal_constraints: Dict) -> Dict[str, Any]:
    # Validation
    if not isinstance(passenger_requests, list) or len(passenger_requests) == 0:
        return {"error": "No passenger requests provided"}
    zone_map = {}
    for z in service_zones:
        zid = z.get("zone_id")
        zb = z.get("zone_boundaries", {})
        if zb.get("min_x") is None or zb.get("max_x") is None or zb.get("min_y") is None or zb.get("max_y") is None:
            return {"error": f"Invalid zone boundaries for zone {zid}"}
        if zb["min_x"] >= zb["max_x"] or zb["min_y"] >= zb["max_y"]:
            return {"error": f"Invalid zone boundaries for zone {zid}"}
        zone_map[zid] = z
    # temporal constraints validation
    peak_hours = temporal_constraints.get("peak_hours", [])
    for p in peak_hours:
        if p.get("start_time") is None or p.get("end_time") is None or p["start_time"] >= p["end_time"]:
            return {"error": "Invalid peak hours configuration"}
    # maintenance windows present
    maintenance = temporal_constraints.get("maintenance_windows", [])
    maintenance_zones = set()
    current_time = temporal_constraints.get("current_system_time", 0)
    for m in maintenance:
        mzid = m.get("zone_id")
        if mzid in zone_map and m.get("start_time") is not None and m.get("end_time") is not None:
            if m["start_time"] <= current_time < m["end_time"]:
                maintenance_zones.add(mzid)
    surge_threshold = temporal_constraints.get("surge_threshold", 2.0)
    # driver validations
    for d in driver_profiles:
        did = d.get("driver_id")
        a_s = d.get("availability_start")
        a_e = d.get("availability_end")
        if a_s is None or a_e is None or a_s >= a_e:
            return {"error": f"Invalid driver availability window for driver {did}"}
        loc = d.get("current_location", {})
        if loc.get("x") is None or loc.get("y") is None:
            return {"error": f"Invalid coordinates for driver {did}"}
        if not (0 <= loc["x"] <= 2000 and 0 <= loc["y"] <= 2000):
            return {"error": f"Invalid coordinates for driver {did}"}
        cap = d.get("vehicle_capacity")
        cpc = d.get("current_passenger_count")
        if cpc is None or cap is None or cpc > cap:
            return {"error": f"Current passenger count exceeds vehicle capacity for driver {did}"}
        sz = d.get("service_zones")
        if not isinstance(sz, list) or len(sz) == 0:
            return {"error": f"Driver {did} has no valid service zones"}
        for s in sz:
            if s not in zone_map:
                # allow driver referencing non-existent zone? spec doesn't explicitly require, but later counts rely on mapping
                return {"error": "Input is not valid"}
    # passenger validations
    for p in passenger_requests:
        pid = p.get("passenger_id")
        rt = p.get("request_time")
        mwt = p.get("max_wait_time")
        if rt is None or rt < 0 or rt > 1440 or mwt is None or mwt <= 0:
            return {"error": f"Invalid passenger request time for passenger {pid}"}
        gs = p.get("group_size")
        if gs is None or gs <= 0 or gs > 4:
            return {"error": f"Invalid group size for passenger {pid}"}
        sz = p.get("service_zone")
        if sz not in zone_map:
            return {"error": f"Invalid service zone reference for passenger {pid}"}
    # Helper functions
    def euclid(a,b):
        return math.hypot(a["x"]-b["x"], a["y"]-b["y"])
    # Build available drivers list with remaining capacity and not in maintenance zones (driver can serve multiple zones)
    drivers = {}
    for d in driver_profiles:
        did = d["driver_id"]
        remaining = d["vehicle_capacity"] - d["current_passenger_count"]
        drivers[did] = dict(d)
        drivers[did]["remaining_capacity"] = remaining
    # Count passengers per zone (by declared service_zone)
    passengers_in_zone = {}
    for p in passenger_requests:
        z = p["service_zone"]
        passengers_in_zone[z] = passengers_in_zone.get(z, 0) + 1
    # Count available drivers per zone (driver lists zone and remaining_capacity>0 and zone not under maintenance)
    drivers_in_zone = {}
    for d in drivers.values():
        if d["remaining_capacity"] <= 0:
            continue
        for z in d["service_zones"]:
            if z in maintenance_zones:
                continue
            drivers_in_zone[z] = drivers_in_zone.get(z, 0) + 1
    # Surge zones detection
    surge_zones = []
    for zid, pcount in passengers_in_zone.items():
        dcount = drivers_in_zone.get(zid, 0)
        ratio = pcount / dcount if dcount>0 else float('inf')
        if ratio > surge_threshold:
            surge_zones.append(zid)
    # Construct edges with scores
    edges = []  # (driver_id, passenger_id, score, pickup_distance, zone_id, overlap_duration)
    for p in passenger_requests:
        pid = p["passenger_id"]
        p_loc = p["pickup_location"]
        p_zone = p["service_zone"]
        if p_zone in maintenance_zones:
            continue
        # zone boundary check: pickup must be within zone boundaries
        zb = zone_map[p_zone]["zone_boundaries"]
        if not (zb["min_x"] <= p_loc["x"] <= zb["max_x"] and zb["min_y"] <= p_loc["y"] <= zb["max_y"]):
            continue
        for d in drivers.values():
            did = d["driver_id"]
            if d["remaining_capacity"] < p["group_size"]:
                continue
            if p_zone not in d["service_zones"]:
                continue
            # driver availability vs passenger request window
            overlap_start = max(d["availability_start"], p["request_time"])
            overlap_end = min(d["availability_end"], p["request_time"] + p["max_wait_time"])
            if overlap_end <= overlap_start:
                continue
            # distance constraint: use zone's max_pickup_distance
            pickup_dist = euclid(d["current_location"], p_loc)
            max_pd = zone_map[p_zone]["max_pickup_distance"]
            if pickup_dist > max_pd:
                continue
            # capacity ok
            # compute match quality
            base_distance_cost = pickup_dist
            overlap_duration = overlap_end - overlap_start
            time_window_bonus = (overlap_duration / p["max_wait_time"]) * 100
            priority_weight = (6 - p["priority_level"]) * 15
            zone_congestion = zone_map[p_zone]["congestion_level"]
            zone_efficiency = (1.0 / zone_congestion) * 20
            capacity_util = (d["current_passenger_count"] / d["vehicle_capacity"]) * 10 if d["vehicle_capacity"]>0 else 0
            score = base_distance_cost + (time_window_bonus * priority_weight) + (zone_efficiency * capacity_util)
            # surge adjustment
            if p_zone in surge_zones:
                score *= 0.85
            edges.append((did, pid, score, pickup_dist, p_zone, overlap_duration))
    # If no edges, return empty results
    if not edges:
        # compile basic outputs
        return {
            "successful_matches": [],
            "system_efficiency_metrics": {
                "total_matches": 0,
                "average_wait_time": 0.0,
                "average_match_quality": 0.0,
                "zone_utilization_rates": {z["zone_id"]: 0.0 for z in service_zones}
            },
            "unmatched_passengers": [p["passenger_id"] for p in passenger_requests],
            "available_drivers": [d["driver_id"] for d in driver_profiles if d["vehicle_capacity"]-d["current_passenger_count"]>0],
            "surge_zones": surge_zones
        }
    # Build bipartite matching maximizing total score. Use greedy with tie-breakers due to complexity (deterministic)
    # Sort edges by score desc, then driver_id asc
    edges.sort(key=lambda x: (-x[2], x[0], x[1]))
    matched_drivers = {}
    matched_passengers = {}
    successful = []
    for did, pid, score, pdist, pzone, overlap in edges:
        if pid in matched_passengers:
            continue
        if did in matched_drivers:
            # check remaining capacity after previous assignments
            assigned = matched_drivers[did]["assigned_count"]
            dprofile = next(d for d in driver_profiles if d["driver_id"]==did)
            if assigned + next(p for p in passenger_requests if p["passenger_id"]==pid)["group_size"] > dprofile["vehicle_capacity"] - dprofile["current_passenger_count"]:
                continue
        # assign
        # recalc estimated times
        p = next(pp for pp in passenger_requests if pp["passenger_id"]==pid)
        # estimated pickup time = request_time + travel time at 30 units/min (distance/pickup_speed) rounded down
        travel_to_pickup_minutes = int(pdist / 30)
        estimated_pickup_time = p["request_time"] + travel_to_pickup_minutes
        # pickup to destination distance
        dest_dist = euclid(p["pickup_location"], p["destination_location"])
        estimated_travel_time = int(dest_dist / 40)
        successful.append({
            "driver_id": did,
            "passenger_id": pid,
            "pickup_distance": round(pdist, 2),
            "match_quality_score": round(score, 2),
            "estimated_pickup_time": estimated_pickup_time,
            "estimated_travel_time": estimated_travel_time,
            "service_zone": pzone
        })
        matched_passengers[pid] = True
        if did not in matched_drivers:
            matched_drivers[did] = {"assigned_count": p["group_size"]}
        else:
            matched_drivers[did]["assigned_count"] += p["group_size"]
    # After greedy assignment, compute metrics
    total_matches = len(successful)
    # average wait time: estimated_pickup_time - request_time averaged
    if total_matches > 0:
        total_wait = 0
        total_score = 0
        zone_match_counts = {}
        for m in successful:
            pid = m["passenger_id"]
            p = next(pp for pp in passenger_requests if pp["passenger_id"]==pid)
            total_wait += max(0, m["estimated_pickup_time"] - p["request_time"])
            total_score += m["match_quality_score"]
            zone_match_counts[m["service_zone"]] = zone_match_counts.get(m["service_zone"], 0) + 1
        average_wait = total_wait / total_matches
        average_score = total_score / total_matches
    else:
        average_wait = 0.0
        average_score = 0.0
        zone_match_counts = {}
    # zone utilization rates
    zone_util = {}
    for z in service_zones:
        zid = z["zone_id"]
        matches = zone_match_counts.get(zid, 0)
        avail_drivers = drivers_in_zone.get(zid, 0)
        denom = min(avail_drivers, passengers_in_zone.get(zid, 0)) if min(avail_drivers, passengers_in_zone.get(zid, 0))>0 else 0
        if denom == 0:
            rate = 0.0
        else:
            rate = matches / denom
        zone_util[zid] = round(rate, 2)
    unmatched_passengers = [p["passenger_id"] for p in passenger_requests if p["passenger_id"] not in matched_passengers]
    available_drivers = [d["driver_id"] for d in driver_profiles if d["vehicle_capacity"] - d["current_passenger_count"] > 0 and d["driver_id"] not in matched_drivers]
    return {
        "successful_matches": successful,
        "system_efficiency_metrics": {
            "total_matches": total_matches,
            "average_wait_time": round(average_wait, 2),
            "average_match_quality": round(average_score, 2),
            "zone_utilization_rates": zone_util
        },
        "unmatched_passengers": unmatched_passengers,
        "available_drivers": available_drivers,
        "surge_zones": surge_zones
    }