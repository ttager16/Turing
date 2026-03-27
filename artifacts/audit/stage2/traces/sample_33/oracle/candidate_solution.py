from typing import List, Dict, Any

def optimize_traffic_flow(sensor_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Optimizes traffic flow by adjusting signal timings and suggesting alternate routes.
    
    Args:
        sensor_data: List of dictionaries containing intersection sensor data
        
    Returns:
        Dictionary with signal_adjustments and alternate_routes
    """
    if not sensor_data:
        return {
            "signal_adjustments": [],
            "alternate_routes": []
        }
    
    signal_adjustments = []
    
    # Calculate signal adjustment for each intersection
    for data in sensor_data:
        intersection_id = data["intersection_id"]
        vehicle_count = data["vehicle_count"]
        average_speed = data["average_speed"]
        congestion_level = data["congestion_level"]
        
        # Apply the proportional control formula
        calculation = 1 - (0.5 * congestion_level + 0.3 * (vehicle_count / 300) - 0.2 * (average_speed / 60))
        signal_adjustment = max(0.1, min(1.0, calculation))
        
        # Round to 2 decimal places for consistency
        signal_adjustment = round(signal_adjustment, 2)
        
        signal_adjustments.append({
            "intersection_id": intersection_id,
            "signal_adjustment": signal_adjustment
        })
    
    # Sort intersections by ID for route generation
    sorted_data = sorted(sensor_data, key=lambda x: x["intersection_id"])
    
    # Generate alternate routes
    alternate_routes = []
    
    # Need at least 3 intersections to generate any routes
    if len(sorted_data) >= 3:
        # Find the most congested intersection
        most_congested = max(sensor_data, key=lambda x: x["congestion_level"])
        most_congested_id = most_congested["intersection_id"]
        
        # Find position of most congested in sorted list
        congested_idx = next((i for i, d in enumerate(sorted_data) 
                             if d["intersection_id"] == most_congested_id), None)
        
        if congested_idx is not None:
            # Generate routes for OTHER intersections that bypass the most congested
            for i in range(len(sorted_data)):
                # Skip the most congested intersection itself
                if i == congested_idx:
                    continue
                
                # Check if we can generate a route that skips the congested node
                # We need the congested node to be between current and destination
                if i < congested_idx:
                    # Current is before congested, route should skip over it
                    # Need at least 2 intersections after congested
                    if congested_idx + 2 < len(sorted_data):
                        from_id = sorted_data[i]["intersection_id"]
                        via_id = sorted_data[congested_idx + 1]["intersection_id"]
                        to_id = sorted_data[congested_idx + 2]["intersection_id"]
                        route = f"Alternate Route: From {from_id} to {to_id} via {via_id}"
                        alternate_routes.append(route)
                elif i > congested_idx:
                    # Current is after congested, route forward (doesn't include congested)
                    # Need at least 2 intersections after current
                    if i + 2 < len(sorted_data):
                        from_id = sorted_data[i]["intersection_id"]
                        via_id = sorted_data[i + 1]["intersection_id"]
                        to_id = sorted_data[i + 2]["intersection_id"]
                        route = f"Alternate Route: From {from_id} to {to_id} via {via_id}"
                        alternate_routes.append(route)
    
    return {
        "signal_adjustments": signal_adjustments,
        "alternate_routes": alternate_routes
    }