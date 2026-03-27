from typing import List
from collections import deque

def maxProductKIncreasing(nums: List[int], K: int, D: int) -> int:
    n = len(nums)
    if K < 1 or K > n:
        return 0
    delta = 1 if D <= 0 else D
    adj = [[] for _ in range(n)]
    for i in range(n):
        vi = nums[i]
        for j in range(i + 1, n):
            if nums[j] - vi >= delta:
                adj[i].append(j)
    matchR = [-1] * n
    matchL = [-1] * n
    INF = 10**9
    def bfs() -> bool:
        q = deque()
        dist = [INF] * n
        for l in range(n):
            if matchL[l] == -1:
                dist[l] = 0
                q.append(l)
        found_augmenting = False
        while q:
            l = q.popleft()
            for r in adj[l]:
                ml = matchR[r]
                if ml != -1:
                    if dist[ml] == INF:
                        dist[ml] = dist[l] + 1
                        q.append(ml)
                else:
                    found_augmenting = True
        bfs.dist = dist
        return found_augmenting
    def dfs(l: int, seenR: List[bool]) -> bool:
        for r in adj[l]:
            if seenR[r]:
                continue
            seenR[r] = True
            ml = matchR[r]
            if ml == -1 or (bfs.dist[ml] == bfs.dist[l] + 1 and dfs(ml, seenR)):
                matchL[l] = r
                matchR[r] = l
                return True
        bfs.dist[l] = INF
        return False
    matching_size = 0
    while bfs():
        seenR = [False] * n
        for l in range(n):
            if matchL[l] == -1:
                if dfs(l, seenR):
                    matching_size += 1
    min_chains = n - matching_size
    if K < min_chains or K > n:
        return 0
    base = n // K
    r = n % K
    product = pow(base, K - r) * pow(base + 1, r)
    return product