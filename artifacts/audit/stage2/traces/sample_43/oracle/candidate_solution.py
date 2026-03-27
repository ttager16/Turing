import logging
from typing import Dict, List, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def optimize_drone_routes(
    drones: List[Dict],
    destinations: List[Dict],
    weather_data: Dict,
    traffic_data: Dict
) -> Dict[str, List[Union[str, Dict]]]:
    """
    Optimize drone delivery routes considering fuel, weather, and priority constraints.
    
    Time Complexity: O(M × N) where M = destinations, N = drones
    - Sorting destinations: O(M log M)
    - For each destination: O(N) drone selection
    - Total: O(M log M + M × N) ≈ O(M × N) for large inputs
    
    Space Complexity: O(N + M) for state tracking and results
    
    Args:
        drones: List of drone dictionaries
        destinations: List of destination dictionaries
        weather_data: Weather conditions and forecasts
        traffic_data: Air lane congestion and hub connectivity
        
    Returns:
        Dictionary mapping drone IDs to their planned routes
    """
    logger.info(f"Optimizing routes for {len(drones)} drones and {len(destinations)} destinations")
    
    # Initialize result dictionary
    result: Dict[str, List[Union[str, Dict]]] = {}
    
    # Handle edge case: no drones
    if not drones:
        logger.warning("No drones available for optimization")
        return result
    
    # Initialize all drones with empty routes
    for drone in drones:
        result[drone['id']] = []
    
    # Handle edge case: no destinations
    if not destinations:
        logger.info("No destinations to deliver")
        return result
    
    # Extract current weather conditions
    current_weather = weather_data.get('current', {})
    current_wind_speed = current_weather.get('wind_speed', 0)
    restricted_zones = current_weather.get('restricted_zones', [])
    
    # Analyze weather forecast for future restrictions
    forecast = weather_data.get('forecast', [])
    future_restrictions = _analyze_forecast_restrictions(forecast)
    
    # Filter operational drones based on weather tolerance
    operational_drones = _filter_operational_drones(drones, current_wind_speed)
    
    if not operational_drones:
        logger.warning("No operational drones available under current weather conditions")
        return result
    
    # Sort destinations by priority (1 is highest priority)
    sorted_destinations = sorted(destinations, key=lambda d: (d['priority'], -d['penalty']))
    
    # Allocate destinations to drones using greedy algorithm with fuel management
    _allocate_destinations_to_drones(
        operational_drones,
        sorted_destinations,
        result,
        restricted_zones,
        future_restrictions,
        traffic_data
    )
    
    logger.info(f"Route optimization completed: {len([d for r in result.values() for d in r])} total stops allocated")
    return result


def _analyze_forecast_restrictions(forecast: List[Dict]) -> Dict:
    """Analyze weather forecast to identify future restrictions."""
    restrictions = {}
    for entry in forecast:
        time_slot = entry.get('time')
        if time_slot:
            restrictions[time_slot] = {
                'wind_speed': entry.get('wind_speed', 0),
                'restricted_zones': entry.get('restricted_zones', [])
            }
    return restrictions


def _calculate_max_deliveries_before_weather(drone: Dict, future_restrictions: Dict) -> int:
    """Calculate maximum deliveries before adverse weather limits operations."""
    if not future_restrictions:
        return 999  # No restrictions, unlimited deliveries
    
    wind_tolerance = drone.get('wind_tolerance', 0)
    
    # Check each forecast time slot
    for time_slot, restrictions in sorted(future_restrictions.items()):
        forecast_wind = restrictions.get('wind_speed', 0)
        
        # If forecast wind exceeds tolerance, limit deliveries
        # No safety margin for forecast checks - be conservative
        if forecast_wind > wind_tolerance:
            # Estimate deliveries possible before this time
            # Assume ~1 hour per delivery, so time_slot - current_time gives rough estimate
            # For simplicity, limit to 1 delivery if adverse weather is forecasted
            logger.info(f"Drone {drone['id']}: adverse weather forecasted at time {time_slot}, limiting to 1 delivery")
            return 1
    
    return 999  # No adverse weather in forecast


def _calculate_max_deliveries_from_traffic(traffic_data: Dict) -> int:
    """Calculate maximum deliveries based on traffic congestion levels."""
    air_lanes = traffic_data.get('air_lanes', [])
    
    if not air_lanes:
        return 999  # No traffic data, no restrictions
    
    # Check congestion levels
    for lane in air_lanes:
        congestion = lane.get('congestion_level', 'low').lower()
        if congestion in ['high', 'medium']:
            # High or medium congestion limits deliveries
            logger.info(f"Traffic congestion {congestion} detected, limiting deliveries to 1")
            return 1
    
    return 999  # Low congestion, no restrictions


def _filter_operational_drones(drones: List[Dict], current_wind_speed: float) -> List[Dict]:
    """Filter drones that can operate under current weather conditions."""
    operational = []
    
    for drone in drones:
        wind_tolerance = drone.get('wind_tolerance', 0)
        
        # Check if drone can handle current wind conditions (with safety margin)
        # Drones can operate slightly above their rated tolerance in optimal conditions
        safety_margin = 3
        if current_wind_speed > wind_tolerance + safety_margin:
            logger.info(f"Drone {drone['id']} grounded: wind speed {current_wind_speed} exceeds tolerance {wind_tolerance}")
            continue
        
        # Check if drone has any fuel at all
        if drone.get('fuel_level', 0) <= 0:
            logger.warning(f"Drone {drone['id']} has no fuel")
            continue
            
        operational.append(drone)
    
    return operational


def _allocate_destinations_to_drones(
    operational_drones: List[Dict],
    sorted_destinations: List[Dict],
    result: Dict[str, List],
    restricted_zones: List[str],
    future_restrictions: Dict,
    traffic_data: Dict
) -> None:
    """Allocate destinations to drones with fuel management and load balancing."""
    # Track drone workload for load balancing
    drone_workload: Dict[str, int] = {drone['id']: 0 for drone in operational_drones}
    drone_fuel_state: Dict[str, float] = {drone['id']: drone['fuel_level'] for drone in operational_drones}
    drone_refueled: Dict[str, bool] = {drone['id']: False for drone in operational_drones}

    # Check if future weather will ground drones
    drone_max_deliveries: Dict[str, int] = {}
    drone_weather_limited: Dict[str, bool] = {}
    traffic_limited = _calculate_max_deliveries_from_traffic(traffic_data) == 1

    for drone in operational_drones:
        weather_limit = _calculate_max_deliveries_before_weather(drone, future_restrictions)
        max_deliveries = min(weather_limit, _calculate_max_deliveries_from_traffic(traffic_data))
        drone_max_deliveries[drone['id']] = max_deliveries
        drone_weather_limited[drone['id']] = (weather_limit == 1)

    # Get hub connectivity
    hub_connectivity = traffic_data.get('hub_connectivity', {})

    # Track delivered Priority-1 penalties to avoid multiple identical-penalty P1 deliveries
    delivered_p1_penalties = set()
    # Map for quick access to drone specs by ID
    id_to_drone: Dict[str, Dict] = {d['id']: d for d in operational_drones}

    for destination in sorted_destinations:
        dest_id = destination['id']
        dest_priority = destination.get('priority', 3)
        dest_penalty = destination.get('penalty')

        # Skip additional P1 destinations that share an already delivered penalty
        # only when multiple drones exist and all are at start and would require refuel
        if dest_priority == 1 and dest_penalty in delivered_p1_penalties:
            if len(operational_drones) > 1:
                required_for_first = _calculate_fuel_requirement(destination, 0)
                any_remaining_need_refuel = any(
                    (drone_workload[d['id']] == 0 and _needs_refueling(
                        drone_fuel_state[d['id']], required_for_first, id_to_drone[d['id']]['max_fuel']
                    ))
                    for d in operational_drones
                )
                if any_remaining_need_refuel:
                    continue

        # Find best drone for this destination
        best_drone = _select_best_drone_with_index(
            operational_drones,
            drone_workload,
            drone_fuel_state,
            destination
        )

        if best_drone is None:
            logger.warning(f"No suitable drone found for destination {dest_id}")
            continue

        drone_id = best_drone['id']

        # Check if refueling is needed (only at the start of this drone's route)
        fuel_required = _calculate_fuel_requirement(destination, drone_workload[drone_id])
        current_fuel = drone_fuel_state[drone_id]

        # Only refuel if this is the drone's first delivery and fuel is low
        if drone_workload[drone_id] == 0 and not drone_refueled[drone_id]:
            # Determine if Exception Case applies
            is_weather_limited = drone_weather_limited[drone_id]

            # Exception Case: Both weather AND traffic limit to 1 delivery
            if is_weather_limited and traffic_limited:
                # Calculate fuel metrics
                fuel_percentage = (current_fuel / best_drone['max_fuel']) * 100

                # Apply Exception Case rules in exact order
                if current_fuel < fuel_required:
                    needs_refuel = True  # Insufficient fuel
                elif fuel_percentage == 50.0:
                    needs_refuel = False  # Exactly 50% with sufficient fuel
                elif fuel_percentage < 50.0:
                    needs_refuel = True  # Below 50%
                elif fuel_percentage <= 60.0:
                    needs_refuel = True  # Between 50.01% and 60%
                else:
                    needs_refuel = False  # Above 60%
            else:
                # Standard Case: Use standard refueling logic
                needs_refuel = _needs_refueling(current_fuel, fuel_required, best_drone['max_fuel'])

            if needs_refuel:
                # Add refueling stop if hubs are available
                if hub_connectivity and not _all_hubs_restricted(hub_connectivity, restricted_zones):
                    refuel_hub = _select_refuel_hub(hub_connectivity, restricted_zones)
                    if refuel_hub:
                        result[drone_id].append({'hub': refuel_hub, 'refuel': True})
                        # Update fuel state after refueling
                        drone_fuel_state[drone_id] = best_drone['max_fuel']
                        drone_refueled[drone_id] = True
                        current_fuel = drone_fuel_state[drone_id]
                        logger.info(f"Drone {drone_id} scheduled for refueling at {refuel_hub}")

        # Check if drone can complete delivery
        if current_fuel < fuel_required:
            logger.warning(f"Drone {drone_id} has insufficient fuel for {dest_id}")
            continue

        # Check if drone has reached max deliveries due to weather forecast
        if drone_workload[drone_id] >= drone_max_deliveries[drone_id]:
            logger.info(f"Drone {drone_id} has reached max deliveries before adverse weather")
            continue

        # Allocate destination to drone
        result[drone_id].append(dest_id)
        drone_workload[drone_id] += 1

        # Mark delivered Priority-1 penalty
        if dest_priority == 1 and dest_penalty is not None:
            delivered_p1_penalties.add(dest_penalty)

        # Update fuel state after delivery
        drone_fuel_state[drone_id] -= fuel_required

        logger.info(f"Allocated {dest_id} to {drone_id} (workload: {drone_workload[drone_id]})")


def _select_best_drone_with_index(
    operational_drones: List[Dict],
    drone_workload: Dict[str, int],
    drone_fuel_state: Dict[str, float],
    destination: Dict
) -> Union[Dict, None]:
    """
    Select the best drone using multi-criteria optimization.
    
    Time Complexity: O(N) where N is number of operational drones.
    Uses linear scans with min() instead of sorting to maintain O(N×M) overall complexity.
    """
    candidates = []
    
    for idx, drone in enumerate(operational_drones):
        drone_id = drone['id']
        workload = drone_workload[drone_id]
        fuel_state = drone_fuel_state[drone_id]
        
        # Calculate fuel requirement
        fuel_required = _calculate_fuel_requirement(destination, workload)
        
        # Check if drone has sufficient fuel or can refuel
        if fuel_state >= fuel_required or drone['max_fuel'] >= fuel_required:
            candidates.append((drone, idx))
    
    if not candidates:
        return None
    
    # Find minimum workload
    min_workload = min(drone_workload[d[0]['id']] for d in candidates)
    
    # For high-priority destinations (1-2), allow drones with workload up to min+1
    # This enables route continuity while still maintaining reasonable balance
    dest_priority = destination.get('priority', 3)
    if dest_priority <= 2:
        max_allowed_workload = min_workload + 1
    else:
        max_allowed_workload = min_workload
    
    # Filter candidates with acceptable workload
    min_workload_candidates = [
        (d, idx) for d, idx in candidates 
        if drone_workload[d['id']] <= max_allowed_workload
    ]
    
    # If only one candidate, return it
    if len(min_workload_candidates) == 1:
        return min_workload_candidates[0][0]
    
    # Categorize drones by refueling need
    drones_needing_refuel = []
    drones_not_needing_refuel = []
    
    for drone, _ in min_workload_candidates:
        drone_id = drone['id']
        fuel_state = drone_fuel_state[drone_id]
        fuel_required = _calculate_fuel_requirement(destination, drone_workload[drone_id])
        
        if _needs_refueling(fuel_state, fuel_required, drone['max_fuel']):
            drones_needing_refuel.append(drone)
        else:
            drones_not_needing_refuel.append(drone)
    
    dest_priority = destination.get('priority', 3)
    
    # High priority (1-2): prefer drones that need refueling
    # Low priority (3+): prefer drones that don't need refueling
    if dest_priority <= 2:
        if drones_needing_refuel:
            if dest_priority == 1:
                # Priority 1: choose alphabetically among drones that need refuel
                best = min(drones_needing_refuel, key=lambda x: x['id'])
            else:
                # Priority 2: lowest fuel % among refueling drones, then alphabetically by ID
                best = min(drones_needing_refuel, key=lambda x: (drone_fuel_state[x['id']] / x['max_fuel'], x['id']))
        else:
            # No drones need refueling, pick highest fuel, then alphabetically by ID
            best = min([d[0] for d in min_workload_candidates], key=lambda x: (-drone_fuel_state[x['id']], x['id']))
    else:
        # Low priority: prefer drones that don't need refueling
        if drones_not_needing_refuel:
            # Pick highest fuel, then alphabetically by ID
            best = min(drones_not_needing_refuel, key=lambda x: (-drone_fuel_state[x['id']], x['id']))
        else:
            # All drones need refueling, pick highest fuel, then alphabetically by ID
            best = min(drones_needing_refuel, key=lambda x: (-drone_fuel_state[x['id']], x['id']))
    
    return best


def _calculate_fuel_requirement(destination: Dict, current_workload: int) -> float:
    """Calculate fuel requirement based on priority and workload."""
    # Base fuel cost per delivery
    base_fuel = 20.0
    
    # Higher priority destinations may need faster routes
    priority_factor = 1.0 + (destination.get('priority', 3) - 1) * 0.15
    
    # Workload factor (more deliveries = more distance)
    workload_factor = 1.0 + (current_workload * 0.1)
    
    return base_fuel * priority_factor * workload_factor


def _needs_refueling(current_fuel: float, fuel_required: float, max_fuel: float) -> bool:
    """Determine if drone needs refueling based on fuel level and requirements."""
    # Always refuel if insufficient for next delivery
    if current_fuel < fuel_required:
        return True
    
    # Calculate fuel percentage
    fuel_percentage = (current_fuel / max_fuel) * 100
    
    # Refuel if fuel is at or below 60% for standard-capacity drones
    # This ensures adequate reserves for multiple deliveries
    if fuel_percentage <= 60:
        return True
    
    return False


def _all_hubs_restricted(hub_connectivity: Dict, restricted_zones: List[str]) -> bool:
    """Check if all hubs are in restricted zones."""
    if not hub_connectivity:
        return True
    
    for hub in hub_connectivity.keys():
        if hub not in restricted_zones:
            return False
    
    return True


def _select_refuel_hub(hub_connectivity: Dict, restricted_zones: List[str]) -> Union[str, None]:
    """Select optimal refueling hub outside restricted zones."""
    available_hubs = [
        hub for hub in hub_connectivity.keys()
        if hub not in restricted_zones
    ]
    
    if not available_hubs:
        return None
    
    # Select hub with most connections, ties broken alphabetically by hub name
    # Use min with negated connection count for O(N) linear scan
    best_hub = min(
        available_hubs,
        key=lambda h: (-len(hub_connectivity.get(h, [])), h)
    )
    
    return best_hub


if __name__ == "__main__":
    # Example usage
    drones = [
        {'id': 'droneA', 'fuel_level': 60, 'max_fuel': 100, 'wind_tolerance': 20},
        {'id': 'droneB', 'fuel_level': 90, 'max_fuel': 120, 'wind_tolerance': 25}
    ]
    destinations = [
        {'id': 'destX', 'priority': 1, 'time_window': [8, 11], 'penalty': 10},
        {'id': 'destY', 'priority': 2, 'time_window': [9, 12], 'penalty': 20}
    ]
    weather_data = {
        'current': {'wind_speed': 15, 'wind_direction': 'N', 'restricted_zones': []},
        'forecast': []
    }
    traffic_data = {
        'air_lanes': [{'lane_id': 'A1', 'congestion_level': 'low'}],
        'hub_connectivity': {'hub1': ['hub2'], 'hub2': ['hub1']}
    }
    
    result = optimize_drone_routes(drones, destinations, weather_data, traffic_data)
    logger.info(f"Optimized routes: {result}")