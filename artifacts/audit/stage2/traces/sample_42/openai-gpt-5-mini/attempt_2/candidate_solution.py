def solve_maze_path_to_exit(grid: List[List[str]]) -> List[Any]:
    # Validation basic types
    if not isinstance(grid, list) or not grid or not all(isinstance(r, list) for r in grid):
        raise ValueError("invalid input : wrong grid dimensions")
    H = len(grid)
    W = len(grid[0])
    if H < 3 or W < 3 or any(len(r) != W for r in grid):
        raise ValueError("invalid input : wrong grid dimensions")
    if H > 50 or W > 50:
        raise ValueError("invalid input : wrong grid dimensions")
    # single-element per cell check: each cell must be a string and not contain multiple top-level elements
    # Given cells are strings like ".", "#", "@", "<K0>" etc. We consider presence of multiple elements if contains more than one of '@' or angle brackets? Simpler: ensure it's a string and does not contain whitespace separating tokens.
    for r in grid:
        for c in r:
            if not isinstance(c, str):
                raise ValueError("invalid input : single cell cannot have multiple elements")
            # disallow spaces or multiple angle items separated (approx)
            if c.count('@') > 1:
                raise ValueError("invalid input : single cell cannot have multiple elements")
    # find start, DF, keys and doors
    start = None
    df_pos = None
    key_pattern = re.compile(r"^<K(\d+)>$")
    door_pattern = re.compile(r"^<D(\d+)>$")
    keys = {}
    doors = {}
    for i in range(H):
        for j in range(W):
            cell = grid[i][j]
            if cell == "@":
                if start is not None:
                    raise ValueError("invalid input : number of starting positions must exactly be one")
                start = (i, j)
            if cell == "<DF>":
                if df_pos is not None:
                    raise ValueError("invalid input : exactly one final door required")
                df_pos = (i, j)
            m = key_pattern.match(cell)
            if m:
                idx = int(m.group(1))
                keys[idx] = (i, j)
            m2 = door_pattern.match(cell)
            if m2:
                idx = int(m2.group(1))
                doors[idx] = (i, j)
    if start is None:
        raise ValueError("invalid input : number of starting positions must exactly be one")
    if df_pos is None:
        raise ValueError("invalid input : exactly one final door required")
    # key/door pair constraints: count unique pairs between 0 and 9 exclusive => 0..9? statement "between 0 and 10(exclusive)" means 0..9 allowed. So number of pairs must be <=9.
    if len(keys) != len(doors):
        raise ValueError("invalid input : unique door/key pair violated")
    if len(keys) > 9:
        raise ValueError("invalid input : violates key/door pair rule")
    # ensure every door has a key and vice versa; also ensure DF has corresponding KF present: they said includes DF as well (ie a key KF must also exist). So check for key index 'F'? But sample uses <KF> and <DF>. We must check existence of <KF>.
    # Look for literal "<KF>" and "<DF>"
    has_KF = False
    has_DF = False
    for i in range(H):
        for j in range(W):
            if grid[i][j] == "<KF>":
                has_KF = True
            if grid[i][j] == "<DF>":
                has_DF = True
    if has_DF and not has_KF:
        raise ValueError("invalid input : unique door/key pair violated")
    if has_KF and not has_DF:
        raise ValueError("invalid input : unique door/key pair violated")
    # Maze enclosed by walls: border cells must all be '#'
    for j in range(W):
        if grid[0][j] != "#" or grid[H-1][j] != "#":
            raise ValueError("invalid input : maze not enclosed by walls in all directions")
    for i in range(H):
        if grid[i][0] != "#" or grid[i][W-1] != "#":
            raise ValueError("invalid input : maze not enclosed by walls in all directions")
    # special door rule: each door <D#> must be between two walls on opposite sides (either up/down or left/right)
    for idx, (i,j) in doors.items():
        up = grid[i-1][j] == "#"
        down = grid[i+1][j] == "#"
        left = grid[i][j-1] == "#"
        right = grid[i][j+1] == "#"
        # must be either up and down both walls, or left and right both walls
        if not ((up and down) or (left and right)):
            raise ValueError("invalid input : special door rule violated")
    # BFS state: (i,j, keys_bitmask, picked_KF_flag maybe) But KF is just another key? It's literal <KF> not indexed. Represent KF as special bit at position 9 if exists.
    # Build mapping for numeric keys up to 9 -> bits 0..8, KF -> bit 9
    key_to_bit = {}
    for k in sorted(keys.keys()):
        if k < 0 or k > 8:
            raise ValueError("invalid input : violates key/door pair rule")
        key_to_bit[k] = 1 << k
    KF_bit = 0
    if has_KF:
        KF_bit = 1 << 9  # use bit 9
    # For doors D#, need mapping to bits. DF requires KF_bit.
    door_to_bit = {}
    for d in doors:
        if d < 0 or d > 8:
            raise ValueError("invalid input : violates key/door pair rule")
        door_to_bit[d] = 1 << d
    # BFS
    from collections import deque
    dq = deque()
    start_state = (start[0], start[1], 0)
    visited = set()
    visited.add(start_state)
    dq.append((start[0], start[1], 0, 0, None))  # i,j,keys,steps,prev pointer index
    # We'll store nodes in list to reconstruct path
    nodes = []
    nodes.append({'i':start[0],'j':start[1],'keys':0,'steps':0,'prev':None})
    found_idx = None
    # helper to check door passage: we can step on door even without key, but cannot pass through (i.e., move into door cell allowed but further movement across it? statement: "We cannot pass through a door unless we have its corresponding key. However, we can step on it even without a key." So moving into door cell is allowed, but moving out on opposite side? That implies door acts like a cell but blocks movement beyond that cell in direction through? Simpler interpretation: door occupies cell; stepping into it is allowed but you cannot move out of it unless you have key. This is weird. Sample shows stepping on <D0> with step number then passing through because had key. But they stepped onto D0 when had key. To satisfy, implement door as traversable cell but only if you have key OR you are moving into it (allowed) but cannot move out from it unless have key. Implement by allowing entering door cell always, but when expanding neighbors from a door cell, block moves that would go across door unless key present. We'll approximate: if current cell is a door and corresponding key not in keys, we do not expand neighbors (i.e., stuck). )
    def cell_is_door(i,j):
        m = door_pattern.match(grid[i][j])
        return m
    def cell_is_key(i,j):
        m = key_pattern.match(grid[i][j])
        return m
    # BFS loop
    while dq:
        i,j,keys_bit,steps,prev_idx = dq.popleft()
        curr_idx = len(nodes)
        nodes.append({'i':i,'j':j,'keys':keys_bit,'steps':steps,'prev':prev_idx})
        # check if at DF and has KF
        if (i,j) == df_pos:
            if has_KF:
                if keys_bit & KF_bit:
                    found_idx = curr_idx
                    break
            else:
                found_idx = curr_idx
                break
        # Determine if current cell is a door and block expansion if lacking key
        mdoor = cell_is_door(i,j)
        if mdoor:
            dnum = int(mdoor.group(1))
            required = door_to_bit.get(dnum, 0)
            if required and not (keys_bit & required):
                continue  # cannot move out
        # explore neighbors
        for di,dj in ((-1,0),(1,0),(0,-1),(0,1)):
            ni,nj = i+di, j+dj
            if not (0 <= ni < H and 0 <= nj < W):
                continue
            dest = grid[ni][nj]
            if dest == "#":
                continue
            new_keys = keys_bit
            mkey = cell_is_key(ni,nj)
            if mkey:
                knum = int(mkey.group(1))
                new_keys = new_keys | key_to_bit.get(knum,0)
            if dest == "<KF>":
                new_keys = new_keys | KF_bit
            # entering DF: require KF to finish; entering allowed even without KF? They said DF must be unlocked with KF. So we can step onto DF only if we have KF. We'll require KF to enter DF.
            if dest == "<DF>":
                if has_KF and not (new_keys & KF_bit):
                    continue
            # entering a door cell is allowed always (per statement)
            state = (ni,nj,new_keys)
            if state in visited:
                continue
            visited.add(state)
            dq.append((ni,nj,new_keys,steps+1,curr_idx))
    if found_idx is None:
        return [None, -1]
    # reconstruct path
    path_nodes = []
    idx = found_idx
    while idx is not None:
        n = nodes[idx]
        path_nodes.append(n)
        idx = n['prev']
    path_nodes.reverse()  # from start to end
    result_grid = copy.deepcopy(grid)
    for step, n in enumerate(path_nodes):
        i,j = n['i'], n['j']
        orig = result_grid[i][j]
        # append step number with comma, preserving existing
        result_grid[i][j] = f"{orig},{step}" if "," not in orig else f"{orig},{step}"
    min_steps = path_nodes[-1]['steps']
    return [result_grid, min_steps]