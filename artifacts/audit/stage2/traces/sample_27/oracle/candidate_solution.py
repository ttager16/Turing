# main.py
from collections import defaultdict
from itertools import combinations, product
import copy
from typing import List, Dict, Any, Tuple


class BattlefieldSimulator:
    """Main simulator class implementing the battlefield strategy optimization."""

    def __init__(self, units: List[Dict[str, Any]], terrain_graph: Dict[str, Any], scenarios: List[Dict[str, str]]) -> None:
        """Initialize the battlefield simulator with units, terrain, and scenarios.

        Args:
            units: List of unit dictionaries with type, synergy, base_cost, and power.
            terrain_graph: Dictionary containing nodes, edges, and resources.
            scenarios: List of scenario dictionaries with enemy_strat and terrain_change.
        """
        self.units = units or []
        self.terrain_graph = terrain_graph or {}
        self.scenarios = scenarios or []
        self.unit_types = [unit['type'] for unit in self.units]
        self.sectors = self.terrain_graph.get('nodes', [])
        self.synergy_matrix = self._build_synergy_matrix()

    def _build_synergy_matrix(self) -> defaultdict:
        """Build synergy matrix mapping unit type pairs to compatibility scores.

        Returns:
            Nested defaultdict with synergy multipliers (1.2 for compatible pairs).
        """
        synergy_matrix = defaultdict(lambda: defaultdict(float))
        for unit in self.units:
            for synergy_unit in unit['synergy']:
                synergy_matrix[unit['type']][synergy_unit] = 1.2
                synergy_matrix[synergy_unit][unit['type']] = 1.2
        return synergy_matrix

    def _calculate_synergy_score(self, allocations: List[Dict[str, Any]]) -> float:
        """Calculate synergy bonus for unit pairs in the same sector.

        Args:
            allocations: List of allocation dicts with unit, sector, and count.

        Returns:
            Total synergy score from all compatible unit pairs.
        """
        synergy_score = 0
        sector_units = defaultdict(list)

        # Group units by sector
        for allocation in allocations:
            sector = allocation['sector']
            unit_type = allocation['unit']
            count = allocation['count']
            unit_data = next(u for u in self.units if u['type'] == unit_type)
            for _ in range(count):
                sector_units[sector].append(unit_data)

        # Calculate synergy for each sector
        for sector, units_in_sector in sector_units.items():
            if len(units_in_sector) <= 1:
                continue
            for unit1, unit2 in combinations(units_in_sector, 2):
                synergy = self.synergy_matrix[unit1['type']][unit2['type']]
                if synergy > 1.0:
                    synergy_score += unit1['power'] * unit2['power'] * 0.2

        return synergy_score

    def _apply_terrain_change(self, terrain_change: str, edge_capacities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply terrain change multipliers to edge capacities.

        Args:
            terrain_change: Type of terrain change (forest_to_desert, desert_to_mountain, mountain_to_forest).
            edge_capacities: List of edge dictionaries with capacity values.

        Returns:
            Deep copy of edge_capacities with adjusted capacity values.
        """
        adjusted_capacities = copy.deepcopy(edge_capacities)

        if terrain_change == 'forest_to_desert':
            for edge in adjusted_capacities:
                edge['capacity'] = int(edge['capacity'] * 0.8)
        elif terrain_change == 'desert_to_mountain':
            for edge in adjusted_capacities:
                edge['capacity'] = int(edge['capacity'] * 0.6)
        elif terrain_change == 'mountain_to_forest':
            for edge in adjusted_capacities:
                edge['capacity'] = int(edge['capacity'] * 1.1)

        return adjusted_capacities

    def _apply_enemy_strategy(self, enemy_strat: str, edge_capacities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply enemy strategy multipliers to edge capacities.

        Args:
            enemy_strat: Enemy strategy type (aggressive, flanking, turtling).
            edge_capacities: List of edge dictionaries with capacity values.

        Returns:
            Deep copy of edge_capacities with adjusted capacity values.
        """
        adjusted_capacities = copy.deepcopy(edge_capacities)

        if enemy_strat == 'aggressive':
            for edge in adjusted_capacities:
                edge['capacity'] = int(edge['capacity'] * 0.7)
        elif enemy_strat == 'flanking':
            for edge in adjusted_capacities:
                edge['capacity'] = int(edge['capacity'] * 0.9)
        # turtling has no effect (multiplier = 1.0)

        return adjusted_capacities

    def _calculate_optimal_flows(self, edge_capacities: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate optimal resource flows proportionally by edge capacity.

        Args:
            edge_capacities: List of edge dictionaries with from, to, and capacity.

        Returns:
            Dictionary mapping edge keys (from->to) to flow values.
        """
        if not self.sectors or not edge_capacities:
            return {}

        # Calculate total resources available
        total_resources = sum(self.terrain_graph['resources'].values())
        if total_resources == 0:
            return {f"{edge['from']}->{edge['to']}": 0 for edge in edge_capacities}

        # Calculate total adjusted capacity
        total_capacity = sum(edge['capacity'] for edge in edge_capacities)
        if total_capacity == 0:
            return {f"{edge['from']}->{edge['to']}": 0 for edge in edge_capacities}

        # Distribute flow proportionally based on capacity
        result_flows = {}
        flow_to_distribute = min(total_resources, total_capacity)

        for edge in edge_capacities:
            key = f"{edge['from']}->{edge['to']}"
            # Proportional flow based on capacity
            proportional_flow = int((edge['capacity'] / total_capacity) * flow_to_distribute)
            result_flows[key] = min(proportional_flow, edge['capacity'])

        return result_flows

    def _calculate_resource_efficiency(self, allocations: List[Dict[str, Any]]) -> float:
        """Calculate resource efficiency as total power divided by total cost.

        Args:
            allocations: List of allocation dicts with unit, sector, and count.

        Returns:
            Efficiency ratio (power/cost), or 0 if cost is zero.
        """
        total_power = 0
        total_cost = 0

        for allocation in allocations:
            unit_type = allocation['unit']
            count = allocation['count']
            unit_data = next(u for u in self.units if u['type'] == unit_type)
            total_power += unit_data['power'] * count
            total_cost += unit_data['base_cost'] * count

        if total_cost == 0:
            return 0
        return total_power / total_cost

    def _calculate_flow_efficiency(self, flows: Dict[str, int], max_possible_flow: int) -> float:
        """Calculate flow efficiency as actual flow divided by maximum possible.

        Args:
            flows: Dictionary of edge flows.
            max_possible_flow: Maximum theoretical flow capacity.

        Returns:
            Efficiency ratio (actual/max), or 0 if max is zero.
        """
        if max_possible_flow == 0:
            return 0
        total_flow = sum(flows.values())
        return total_flow / max_possible_flow

    def _calculate_scenario_score(self, allocations: List[Dict[str, Any]], scenario: Dict[str, str]) -> Tuple[int, Dict[str, int]]:
        """Calculate score for allocations under a specific scenario.

        Args:
            allocations: List of allocation dicts with unit, sector, and count.
            scenario: Scenario dict with enemy_strat and terrain_change.

        Returns:
            Tuple of (final_score, flows_dict).
        """
        # Apply terrain and enemy effects
        edge_capacities = self.terrain_graph['edges'].copy()
        edge_capacities = self._apply_terrain_change(scenario['terrain_change'], edge_capacities)
        edge_capacities = self._apply_enemy_strategy(scenario['enemy_strat'], edge_capacities)

        # Calculate optimal flows using proper min-cost max-flow
        flows = self._calculate_optimal_flows(edge_capacities)

        # Calculate components
        total_power = sum(allocation['count'] * next(u for u in self.units if u['type'] == allocation['unit'])['power']
                          for allocation in allocations)
        resource_efficiency = self._calculate_resource_efficiency(allocations)
        max_possible_flow = sum(edge['capacity'] for edge in self.terrain_graph['edges'])  # Use original capacities
        flow_efficiency = self._calculate_flow_efficiency(flows, max_possible_flow)

        # Apply scoring formula from requirements
        base_score = (total_power * resource_efficiency * flow_efficiency) / 100
        synergy_bonus = self._calculate_synergy_score(allocations) * 2

        # Calculate penalties as specified in requirements
        terrain_penalty = 0
        enemy_penalty = 0

        if scenario['terrain_change'] == 'forest_to_desert':
            terrain_penalty = 20  # 20% reduction
        elif scenario['terrain_change'] == 'desert_to_mountain':
            terrain_penalty = 40  # 40% reduction
        elif scenario['terrain_change'] == 'mountain_to_forest':
            terrain_penalty = -10  # 10% increase (bonus)

        if scenario['enemy_strat'] == 'aggressive':
            enemy_penalty = 30  # 30% reduction
        elif scenario['enemy_strat'] == 'flanking':
            enemy_penalty = 10  # 10% reduction

        final_score = max(0, min(1000, base_score + synergy_bonus - terrain_penalty - enemy_penalty))
        return int(final_score), flows

    def _generate_configurations(self) -> List[Dict[str, Any]]:
        """Generate candidate deployment configurations with various unit combinations.

        Returns:
            List of configuration dicts with allocations and flows.
        """
        configurations = []
        max_units_per_sector = 10

        # Generate single unit type configurations
        for sector in self.sectors:
            for unit_type in self.unit_types:
                for count in range(1, max_units_per_sector + 1):
                    config = {
                        'allocations': [{'unit': unit_type, 'sector': sector, 'count': count}],
                        'flows': {}
                    }
                    configurations.append(config)

        # Generate two unit type configurations (different sectors)
        for sector1, sector2 in combinations(self.sectors, 2):
            for unit_type1, unit_type2 in product(self.unit_types, repeat=2):
                for count1 in range(1, max_units_per_sector + 1):
                    for count2 in range(1, max_units_per_sector + 1):
                        config = {
                            'allocations': [
                                {'unit': unit_type1, 'sector': sector1, 'count': count1},
                                {'unit': unit_type2, 'sector': sector2, 'count': count2}
                            ],
                            'flows': {}
                        }
                        configurations.append(config)

        # Generate same-sector synergy configurations
        for sector in self.sectors:
            for unit_type1, unit_type2 in combinations(self.unit_types, 2):
                if self.synergy_matrix[unit_type1][unit_type2] > 1.0:
                    for count1 in range(1, max_units_per_sector + 1):
                        for count2 in range(1, max_units_per_sector + 1):
                            config = {
                                'allocations': [
                                    {'unit': unit_type1, 'sector': sector, 'count': count1},
                                    {'unit': unit_type2, 'sector': sector, 'count': count2}
                                ],
                                'flows': {}
                            }
                            configurations.append(config)

        # Limit configurations for performance (keep top configurations by raw power + synergy)
        config_scores = []
        for config in configurations:
            total_power = sum(allocation['count'] * next(u for u in self.units if u['type'] == allocation['unit'])['power']
                              for allocation in config['allocations'])
            synergy_score = self._calculate_synergy_score(config['allocations'])
            config_scores.append((total_power + synergy_score, config))

        # Sort by score and take top configurations
        config_scores.sort(key=lambda x: x[0], reverse=True)
        top_configs = [config for _, config in config_scores[:100]]  # Limit for performance

        return top_configs

    def simulate_optimal_strategy(self) -> List[Dict[str, Any]]:
        """Run simulation and return top 10 configurations by average score.

        Returns:
            List of result dicts with configuration and score, sorted by score descending.
        """
        if not self.units or not self.scenarios:
            return []

        configurations = self._generate_configurations()
        results = []

        for config in configurations:
            total_score = 0
            scenario_count = 0
            avg_flows = defaultdict(int)

            # Evaluate against all scenarios
            for scenario in self.scenarios:
                scenario_score, flows = self._calculate_scenario_score(config['allocations'], scenario)
                total_score += scenario_score
                scenario_count += 1

                # Average the flows across scenarios
                for key, value in flows.items():
                    avg_flows[key] += value

            if scenario_count > 0:
                final_score = total_score // scenario_count
                # Average the flows
                for key in avg_flows:
                    avg_flows[key] = avg_flows[key] // scenario_count

            results.append({
                    'configuration': {
                        'allocations': config['allocations'],
                        'flows': dict(avg_flows)
                    },
                    'score': final_score
                })

        # Sort by score (highest first) and return top 10
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:10]


def simulate_optimal_strategy(units: List[Dict[str, Any]], terrain_graph: Dict[str, Any], scenarios: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Computes optimal unit deployment and resource flow configurations.

    Args:
        units: List of unit dictionaries with type, synergy, base_cost, and power.
        terrain_graph: Dictionary containing nodes, edges, and resources.
        scenarios: List of scenario dictionaries with enemy_strat and terrain_change.

    Returns:
        List of top 10 configurations with allocations, flows, and scores.
    """
    simulator = BattlefieldSimulator(units, terrain_graph, scenarios)
    return simulator.simulate_optimal_strategy()


# Example usage
if __name__ == '__main__':
    units = [
        {'type': 'infantry', 'synergy': ['engineer'], 'base_cost': 10, 'power': 5},
        {'type': 'engineer', 'synergy': ['infantry'], 'base_cost': 8, 'power': 3},
        {'type': 'tank', 'synergy': [], 'base_cost': 50, 'power': 20}
    ]

    terrain_graph = {
        'nodes': ['sector_A', 'sector_B', 'sector_C'],
        'edges': [
            {'from': 'sector_A', 'to': 'sector_B', 'capacity': 40},
            {'from': 'sector_B', 'to': 'sector_C', 'capacity': 30},
            {'from': 'sector_A', 'to': 'sector_C', 'capacity': 10}
        ],
        'resources': {'sector_A': 50, 'sector_B': 70, 'sector_C': 30}
    }

    scenarios = [
        {'enemy_strat': 'aggressive', 'terrain_change': 'forest_to_desert'},
        {'enemy_strat': 'flanking', 'terrain_change': 'desert_to_mountain'}
    ]

    result = simulate_optimal_strategy(units, terrain_graph, scenarios)
    print(result)