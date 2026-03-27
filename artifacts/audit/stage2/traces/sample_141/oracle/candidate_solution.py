import heapq


def calculate_min_power(grid: list[list[int]], builder_pos: list[int], scout_pos: list[int],
                        unstable_cells: list[list[int]], target_pos: list[int]) -> float | None:
    """
    Calculates the minimum power for the Builder to reach and finalize a target site.

    This function uses Dijkstra's algorithm to find the lowest-power path in a complex
    state space. A state is defined by the positions of the Builder and Scout, the
    grid's elevation map, and the set of remaining unstable cells. The algorithm
    explores actions for each specialized rover (Build, Scan, Move) and finds the
    optimal sequence to complete the mission.
    """
    # --- Convert lists to tuples for hashability ---
    # The state includes positions, so they must be hashable tuples, not lists.
    builder_pos_tuple = tuple(builder_pos)
    scout_pos_tuple = tuple(scout_pos)
    # The set of unstable cells must also contain hashable tuples.
    unstable_cells_tuples = frozenset(tuple(cell) for cell in unstable_cells)
    target_pos_tuple = tuple(target_pos)

    # Helper to convert grid to a hashable tuple for use in dictionaries/sets
    def grid_to_tuple(g: list[list[int]]) -> tuple[tuple[int, ...], ...]:
        return tuple(tuple(row) for row in g)

    # Helper to get all 8 adjacent cells (including diagonals)
    def get_neighbors(pos: tuple[int, int]) -> list[tuple[int, int]]:
        r, c = pos
        neighbors = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < 5 and 0 <= nc < 5:
                    neighbors.append((nr, nc))
        return neighbors

    # Generates all valid subsequent states and their power costs from a given state
    def get_next_valid_states(state: tuple):
        b_pos, s_pos, grid_tuple, unstable_set = state
        current_grid = [list(row) for row in grid_tuple]

        # --- Builder Actions (Move-then-Build) ---
        for move_pos in get_neighbors(b_pos):
            # Check move validity
            if move_pos == s_pos or move_pos in unstable_set or current_grid[move_pos[0]][move_pos[1]] == 4:
                continue

            move_power = 1 + max(0, current_grid[move_pos[0]][move_pos[1]] - current_grid[b_pos[0]][b_pos[1]])

            # After moving, generate all possible build actions
            for build_pos in get_neighbors(move_pos):
                if build_pos in {move_pos, s_pos} or current_grid[build_pos[0]][build_pos[1]] >= 4:
                    continue

                new_grid = [row[:] for row in current_grid]
                new_grid[build_pos[0]][build_pos[1]] += 1

                new_state = (move_pos, s_pos, grid_to_tuple(new_grid), unstable_set)
                action_power = move_power + 2  # Build cost is 2
                yield new_state, action_power

        # --- Scout Actions (Scan or Move) ---
        # 1. Scan Action
        for scan_pos in get_neighbors(s_pos):
            if scan_pos in unstable_set:
                new_unstable = unstable_set - {scan_pos}
                new_state = (b_pos, s_pos, grid_tuple, frozenset(new_unstable))
                yield new_state, 3  # Scan cost is 3

        # 2. Move Action
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                # Check for 1 and 2-unit moves
                for dist in [1, 2]:
                    path_clear = True
                    end_r, end_c = s_pos[0] + dr * dist, s_pos[1] + dc * dist

                    if not (0 <= end_r < 5 and 0 <= end_c < 5):
                        continue

                    # Check all cells along the path
                    for i in range(1, dist + 1):
                        path_r, path_c = s_pos[0] + dr * i, s_pos[1] + dc * i
                        if (path_r, path_c) == b_pos or (path_r, path_c) in unstable_set or current_grid[path_r][
                            path_c] == 4:
                            path_clear = False
                            break

                    if path_clear:
                        move_power = (1 + max(0, current_grid[end_r][end_c] - current_grid[s_pos[0]][s_pos[1]])) * dist
                        new_state = (b_pos, (end_r, end_c), grid_tuple, unstable_set)
                        yield new_state, move_power

    # --- Main Dijkstra's Algorithm Logic ---
    final_power = float('inf')
    initial_state = (builder_pos_tuple, scout_pos_tuple, grid_to_tuple(grid), unstable_cells_tuples)

    pq = [(0, initial_state)]
    min_power_map = {initial_state: 0}

    while pq:
        power, current_state = heapq.heappop(pq)

        if power > min_power_map.get(current_state, float('inf')):
            continue

        b_pos, _, _, _ = current_state

        if b_pos == target_pos_tuple:
            final_power = float(power + 10)
            break

        for next_state, action_cost in get_next_valid_states(current_state):
            new_power = power + action_cost
            if new_power < min_power_map.get(next_state, float('inf')):
                min_power_map[next_state] = new_power
                heapq.heappush(pq, (new_power, next_state))

    return final_power