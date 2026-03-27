from collections import deque
import re
from typing import List, Optional, Any

def solve_maze_path_to_exit(grid: List[List[str]]) -> List[Any]:
    """
    Solves a maze grid to find the shortest path from a starting point '@'
    to a final door '<DF>', collecting keys '<K...>' to open corresponding
    doors '<D...>'.

    Args:
        grid: A 2D list of strings representing the maze layout.

    Returns:
        A list containing two elements:
        - The annotated grid with the path traced by step numbers (or None if no path exists).
        - The minimum number of steps to reach the exit (or -1 if no path exists).
    """
    key_re = re.compile(r"^<K(F|\d+)>$")
    door_re = re.compile(r"^<D(F|\d+)>$")
    
    def parse_key_id(s: str) -> Optional[str]:
        m = key_re.match(s)
        return m.group(1) if m else None

    def parse_door_id(s: str) -> Optional[str]:
        m = door_re.match(s)
        return m.group(1) if m else None

    def is_wall(s: str) -> bool:
        return s == '#'

    def is_start(s: str) -> bool:
        return s == '@'

    if not isinstance(grid, list) or not grid or not all(isinstance(row, list) for row in grid):
        raise ValueError("invalid input : wrong grid dimensions")

    R = len(grid)
    C = len(grid[0]) if R > 0 else 0
    if R < 3 or R > 50 or C < 3 or C > 50:
        raise ValueError("invalid input : wrong grid dimensions")
    if any(len(row) != C for row in grid):
        raise ValueError("invalid input : wrong grid dimensions")

    if any(cell != '#' for cell in grid[0]) or any(cell != '#' for cell in grid[-1]):
        raise ValueError("invalid input : maze not enclosed by walls in all directions")
    for r in range(R):
        if grid[r][0] != '#' or grid[r][-1] != '#':
            raise ValueError("invalid input : maze not enclosed by walls in all directions")

    start_pos = None
    df_pos = None
    keys_present = set()
    doors_present = set()
    allowed_tokens = {'#', '.', '@'}

    for r in range(R):
        for c in range(C):
            s = grid[r][c]
            if s in allowed_tokens:
                pass
            elif parse_key_id(s) is not None:
                keys_present.add(parse_key_id(s))
            elif parse_door_id(s) is not None:
                doors_present.add(parse_door_id(s))
            else:
                raise ValueError("invalid input : single cell cannot have multiple elements")
            
            if is_start(s):
                if start_pos is not None:
                    raise ValueError("invalid input : number of starting positions must exactly be one")
                start_pos = (r, c)
            if s == "<DF>":
                if df_pos is not None:
                    raise ValueError("invalid input : exactly one final door required")
                df_pos = (r, c)

    if start_pos is None:
        raise ValueError("invalid input : number of starting positions must exactly be one")
    if df_pos is None:
        raise ValueError("invalid input : exactly one final door required")

    if 'F' not in doors_present or 'F' not in keys_present:
        raise ValueError("invalid input : unique door/key pair violated")
    
    if doors_present != keys_present:
        raise ValueError("invalid input : unique door/key pair violated")

    if not (1 <= len(keys_present) <= 9):
        raise ValueError("invalid input : violates key/door pair rule")

    for r in range(1, R - 1):
        for c in range(1, C - 1):
            s = grid[r][c]
            did = parse_door_id(s)
            if did is not None and did != 'F':
                up = grid[r - 1][c]
                down = grid[r + 1][c]
                left = grid[r][c - 1]
                right = grid[r][c + 1]
                has_vert_walls = is_wall(up) and is_wall(down)
                has_horz_walls = is_wall(left) and is_wall(right)
                if not (has_vert_walls or has_horz_walls):
                    raise ValueError("invalid input : special door rule violated")

    key_ids_sorted = sorted(keys_present, key=lambda x: (x != 'F', int(x) if x.isdigit() else float('inf')))
    key_to_bit = {kid: i for i, kid in enumerate(key_ids_sorted)}
    final_bit = key_to_bit['F']

    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def has_key(mask: int, kid: str) -> bool:
        return (mask & (1 << key_to_bit[kid])) != 0

    start_state = (start_pos[0], start_pos[1], 0)
    visited = {start_state}
    parent = {}
    dist = {start_state: 0}
    q = deque([start_state])

    goal_state = None

    while q:
        r, c, mask = q.popleft()
        steps = dist[(r, c, mask)]

        if (r, c) == df_pos and (mask & (1 << final_bit)):
            goal_state = (r, c, mask)
            break

        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            
            if not (0 <= nr < R and 0 <= nc < C):
                continue
            
            ns = grid[nr][nc]
            if is_wall(ns):
                continue

            ndid = parse_door_id(ns)
            if ndid is not None and ndid != 'F':
                if not has_key(mask, ndid):
                    continue

            nkid = parse_key_id(ns)
            new_mask = mask
            if nkid is not None:
                new_mask = mask | (1 << key_to_bit[nkid])

            next_state = (nr, nc, new_mask)
            
            if next_state in visited:
                continue
            
            visited.add(next_state)
            parent[next_state] = (r, c, mask)
            dist[next_state] = steps + 1
            q.append(next_state)

    if goal_state is None:
        return [None, -1]

    path_states = []
    cur = goal_state
    while True:
        path_states.append(cur)
        if cur == start_state:
            break
        cur = parent[cur]
    path_states.reverse()

    annotated = [row[:] for row in grid]
    for step_idx, (r, c, _) in enumerate(path_states):
        annotated[r][c] = f"{annotated[r][c]},{step_idx}"

    min_steps = len(path_states) - 1
    return [annotated, min_steps]

def main():
    """
    Defines a sample puzzle and runs the maze solver, printing the result.
    """
    PUZZLE = [
        ["#", "#", "#", "#", "#"],
        ["#", "<KF>", "<DF>", "@", "#"],
        ["#", "#", "#", "#", "#"]
    ]
    result = solve_maze_path_to_exit(PUZZLE)
    print(result)

if __name__ == "__main__":
    main()