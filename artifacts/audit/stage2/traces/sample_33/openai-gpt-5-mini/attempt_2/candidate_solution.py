def optimize_traffic_flow(sensor_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Prepare outputs
    signal_adjustments = []
    alternate_routes = []

    if not sensor_data:
        return {"signal_adjustments": [], "alternate_routes": []}

    # Ensure order is the given sequence order
    intersections = sensor_data  # assume provided order is the network sequence

    # Compute signal adjustments
    for entry in intersections:
        vid = entry.get("vehicle_count", 0)
        spd = entry.get("average_speed", 0)
        cong = entry.get("congestion_level", 0)
        raw = 1 - (0.5 * cong + 0.3 * (vid / 300.0) - 0.2 * (spd / 60.0))
        adj = max(0.1, min(1.0, raw))
        # round to 2 decimal places as in sample
        signal_adjustments.append({
            "intersection_id": entry.get("intersection_id"),
            "signal_adjustment": round(adj, 2)
        })

    # Alternate routes
    n = len(intersections)
    if n >= 3:
        # Identify most congested intersection (highest congestion_level; tie -> first)
        max_idx = 0
        max_cong = intersections[0].get("congestion_level", 0)
        for i in range(1, n):
            c = intersections[i].get("congestion_level", 0)
            if c > max_cong:
                max_cong = c
                max_idx = i

        # For each other intersection, suggest alternate route bypassing the most congested one.
        # The alternate route should connect to the next two consecutive intersections ahead in the sequence, if available.
        # Interpret "next two consecutive intersections ahead" relative to the bypassed intersection position:
        # For an intersection at index i (not the congested one), we need destination and via as the two nodes after i (i+1 and i+2),
        # but must also ensure the route bypasses the congested index. The prompt examples suggest skipping the congested node
        # and using the next two available nodes ahead in sequence.
        ids = [e.get("intersection_id") for e in intersections]

        for i in range(n):
            if i == max_idx:
                continue
            # Build list of nodes ahead of i, excluding the congested node
            ahead = []
            for j in range(i+1, n):
                if j == max_idx:
                    continue
                ahead.append((j, ids[j]))
                if len(ahead) >= 2:
                    break
            if len(ahead) < 2:
                continue
            # Construct route: From current to destination (second ahead) via first ahead
            start = ids[i]
            via = ahead[0][1]
            dest = ahead[1][1]
            alternate_routes.append(f"Alternate Route: From {start} to {dest} via {via}")

    return {"signal_adjustments": signal_adjustments, "alternate_routes": alternate_routes}