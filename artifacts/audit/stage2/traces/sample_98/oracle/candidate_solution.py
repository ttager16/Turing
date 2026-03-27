from typing import List
from array import array

def max_synergy_path(matrix: List[List[int]], water_costs: List[List[int]], budget: int) -> int:
    if not matrix or not matrix[0] or not water_costs or not water_costs[0]:
        return 0

    rows, cols = len(matrix), len(matrix[0])
    if len(water_costs) != rows or len(water_costs[0]) != cols:
        return 0

    # Fixed neighbor order: Right, Left, Down, Up
    NEIGHBORS = ((0, 1), (0, -1), (1, 0), (-1, 0))

    # Rolling-hash constants (unsigned 64-bit wraparound)
    BASE1 = 911382323
    BASE2 = 972663749
    MASK = (1 << 64) - 1

    def idx(r: int, c: int) -> int:
        return r * cols + c

    N = rows * cols

    # Per-cell best state stored in fixed-size parallel arrays
    L = array('I', [0]) * N               # length
    C = array('I', [0]) * N               # total cost
    SF = array('I', [0]) * N              # starting fertility
    SR = array('I', [0]) * N              # starting row
    SC = array('I', [0]) * N              # starting col
    H1 = array('Q', [0]) * N              # hash1
    H2 = array('Q', [0]) * N              # hash2
    LR = array('I', [0]) * N              # ending row (current cell)
    LC = array('I', [0]) * N              # ending col (current cell)

    # Dominance comparison: does candidate strictly dominate existing?
    def dominates(eL: int, eC: int, eSF: int, eSR: int, eSC: int,
                  eH1: int, eH2: int, eLR: int, eLC: int,
                  cL: int, cC: int, cSF: int, cSR: int, cSC: int,
                  cH1: int, cH2: int, cLR: int, cLC: int) -> bool:
        if cL > eL:
            return True
        if cL < eL:
            return False
        if cC < eC:
            return True
        if cC > eC:
            return False
        if cSF < eSF:
            return True
        if cSF > eSF:
            return False
        if cSR < eSR:
            return True
        if cSR > eSR:
            return False
        if cSC < eSC:
            return True
        if cSC > eSC:
            return False
        if cH1 < eH1:
            return True
        if cH1 > eH1:
            return False
        if cH2 < eH2:
            return True
        if cH2 > eH2:
            return False
        if cLR < eLR:
            return True
        if cLR > eLR:
            return False
        if cLC < eLC:
            return True
        return False

    # Build buckets for fertility values [0..max] with row-major insertion
    max_fert = 0
    for r in range(rows):
        for c in range(cols):
            if matrix[r][c] > max_fert:
                max_fert = matrix[r][c]
    buckets = [[] for _ in range(max_fert + 1)]
    for r in range(rows):
        for c in range(cols):
            buckets[matrix[r][c]].append((r, c))  # row-major order by construction

    # Process cells in nondecreasing fertility
    for fert in range(len(buckets)):
        for r, c in buckets[fert]:
            i = idx(r, c)

            # Base state from starting at (r,c)
            base_cost = water_costs[r][c]
            if base_cost <= budget:
                bL = 1
                bC = base_cost
                bSF = matrix[r][c]
                bSR, bSC = r, c
                # append current cell id (i) to rolling hashes
                bH1 = ((0 * BASE1) + (i + 1)) & MASK
                bH2 = ((0 * BASE2) + (i + 1)) & MASK
                bLR, bLC = r, c

                if L[i] == 0 or dominates(L[i], C[i], SF[i], SR[i], SC[i], H1[i], H2[i], LR[i], LC[i],
                                          bL, bC, bSF, bSR, bSC, bH1, bH2, bLR, bLC):
                    L[i] = bL; C[i] = bC; SF[i] = bSF; SR[i] = bSR; SC[i] = bSC
                    H1[i] = bH1; H2[i] = bH2; LR[i] = bLR; LC[i] = bLC

            # Propagate to strictly higher-fertility neighbors from the best state at i
            if L[i] == 0:
                continue

            srcL, srcC = L[i], C[i]
            srcSF, srcSR, srcSC = SF[i], SR[i], SC[i]
            srcH1, srcH2 = H1[i], H2[i]

            for dr, dc in NEIGHBORS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and matrix[nr][nc] > fert:
                    j = idx(nr, nc)
                    add_cost = water_costs[nr][nc]
                    cand_cost = srcC + add_cost
                    if cand_cost > budget:
                        continue
                    cand_len = srcL + 1
                    cand_h1 = ((srcH1 * BASE1) + (j + 1)) & MASK
                    cand_h2 = ((srcH2 * BASE2) + (j + 1)) & MASK
                    cand_lr, cand_lc = nr, nc

                    if L[j] == 0 or dominates(L[j], C[j], SF[j], SR[j], SC[j], H1[j], H2[j], LR[j], LC[j],
                                              cand_len, cand_cost, srcSF, srcSR, srcSC,
                                              cand_h1, cand_h2, cand_lr, cand_lc):
                        L[j] = cand_len; C[j] = cand_cost; SF[j] = srcSF; SR[j] = srcSR; SC[j] = srcSC
                        H1[j] = cand_h1; H2[j] = cand_h2; LR[j] = cand_lr; LC[j] = cand_lc

    # Select the global best using the same dominance rules
    best_idx = -1
    for i in range(N):
        if L[i] == 0:
            continue
        if best_idx == -1 or dominates(L[best_idx], C[best_idx], SF[best_idx], SR[best_idx], SC[best_idx],
                                       H1[best_idx], H2[best_idx], LR[best_idx], LC[best_idx],
                                       L[i], C[i], SF[i], SR[i], SC[i], H1[i], H2[i], LR[i], LC[i]):
            best_idx = i

    return int(0 if best_idx == -1 else L[best_idx])

if __name__ == "__main__":
    fertility_matrix = [
        [1,  2,  5,  9],
        [2, 10, 15,  1],
        [1,  6,  7, 11],
        [4,  3,  2, 12]
    ]

    water_costs_matrix = [
        [1, 2, 3, 4],
        [2, 4, 5, 1],
        [1, 6, 4, 5],
        [2, 1, 3, 2]
    ]

    budget = 12

    print(max_synergy_path(fertility_matrix, water_costs_matrix, budget))