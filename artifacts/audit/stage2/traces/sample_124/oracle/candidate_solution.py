import math
import random
import time
from typing import List, Set, FrozenSet


def design_metro_system(
        demand_matrix: List[List[int]],
        cost_matrix: List[List[int]],
        budget: int,
        max_avg_time: float
) -> bool:
    """
    Designs a metro system using Simulated Annealing to find a near-optimal network.

    This function first generates a good initial solution using a greedy heuristic.
    It then uses Simulated Annealing to iteratively improve this solution by
    exploring neighboring network configurations (swapping, adding, or removing
    tunnels). This allows the algorithm to escape local optima and find a more
    globally optimal solution that minimizes the average travel time while
    respecting the budget.

    Args:
        demand_matrix: A 2D list where demand_matrix[i][j] is the number of
                       passengers traveling from station i to j.
        cost_matrix: A 2D list where cost_matrix[i][j] is the cost to build a
                     direct tunnel between station i and j.
        budget: The maximum total cost for construction.
        max_avg_time: The maximum allowable average travel time.

    Returns:
        True if a qualifying network design is found, False otherwise.
    """
    start_time = time.time()
    N = len(demand_matrix)
    if N <= 1:
        return True

    # --- Helper function for performance evaluation (the "energy" function) ---
    def _evaluate_network(edges: Set[FrozenSet[int]]):
        # Floyd-Warshall for shortest paths
        dist = [[math.inf] * N for _ in range(N)]
        for i in range(N):
            dist[i][i] = 0
        for edge in edges:
            u, v = tuple(edge)
            dist[u][v] = dist[v][u] = 1

        for k in range(N):
            for i in range(N):
                for j in range(N):
                    if dist[i][k] + dist[k][j] < dist[i][j]:
                        dist[i][j] = dist[i][k] + dist[k][j]

        # Calculate average travel time
        total_weighted_time = 0
        total_passengers = 0
        for i in range(N):
            for j in range(N):
                passengers = demand_matrix[i][j]
                if passengers == 0:
                    continue
                total_passengers += passengers
                travel_time = dist[i][j]

                if travel_time == math.inf:
                    return math.inf  # Incomplete network is infinitely bad
                total_weighted_time += passengers * travel_time

        if total_passengers == 0:
            return 0.0
        return total_weighted_time / total_passengers

    # --- 1. Create a pool of all possible tunnels ---
    all_tunnels = []
    for i in range(N):
        for j in range(i + 1, N):
            all_tunnels.append({
                'edge': frozenset((i, j)),
                'cost': cost_matrix[i][j],
                'demand': demand_matrix[i][j] + demand_matrix[j][i]
            })
    all_tunnels_set = {t['edge'] for t in all_tunnels}

    # --- 2. Greedy Initialization for a strong starting point ---
    sorted_tunnels = sorted(all_tunnels, key=lambda x: (x['cost'], -x['demand']))

    current_edges = set()
    current_cost = 0
    for tunnel in sorted_tunnels:
        if current_cost + tunnel['cost'] <= budget:
            current_edges.add(tunnel['edge'])
            current_cost += tunnel['cost']

    best_edges = current_edges
    best_avg_time = _evaluate_network(best_edges)
    current_avg_time = best_avg_time

    # --- 3. Simulated Annealing ---
    T = 1.0  # Initial temperature
    T_min = 0.0001  # Minimum temperature to stop
    alpha = 0.99  # Cooling rate

    while T > T_min and time.time() - start_time < 0.9:
        # Generate a neighbor solution by making a small random change
        new_edges = set(current_edges)

        # Randomly choose a move: swap, add, or remove a tunnel
        move = random.random()

        if move < 0.7 and len(new_edges) > 0:  # Try to swap
            edge_to_remove = random.choice(list(new_edges))
            new_edges.remove(edge_to_remove)

            removed_cost = cost_matrix[list(edge_to_remove)[0]][list(edge_to_remove)[1]]
            cost_without_removed = current_cost - removed_cost

            unbuilt_edges = list(all_tunnels_set - new_edges)
            random.shuffle(unbuilt_edges)

            # Find a new edge to add that fits the budget
            for edge_to_add in unbuilt_edges:
                add_cost = cost_matrix[list(edge_to_add)[0]][list(edge_to_add)[1]]
                if cost_without_removed + add_cost <= budget:
                    new_edges.add(edge_to_add)
                    break
        elif move < 0.85:  # Try to add
            unbuilt_edges = list(all_tunnels_set - new_edges)
            if not unbuilt_edges: continue
            edge_to_add = random.choice(unbuilt_edges)
            add_cost = cost_matrix[list(edge_to_add)[0]][list(edge_to_add)[1]]
            if current_cost + add_cost <= budget:
                new_edges.add(edge_to_add)
        else:  # Try to remove
            if not new_edges: continue
            new_edges.remove(random.choice(list(new_edges)))

        # Evaluate the new solution
        new_avg_time = _evaluate_network(new_edges)

        # Decide whether to accept the new solution
        delta_energy = new_avg_time - current_avg_time
        if delta_energy < 0 or random.random() < math.exp(-delta_energy / T):
            current_edges = new_edges
            current_avg_time = new_avg_time
            current_cost = sum(cost_matrix[list(e)[0]][list(e)[1]] for e in current_edges)

            if current_avg_time < best_avg_time:
                best_avg_time = current_avg_time
                best_edges = current_edges

        T *= alpha  # Cool down
    return best_avg_time <= max_avg_time