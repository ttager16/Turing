## main.py

from typing import List

def allocate_minimum_companies(demand: List[int], capacities: List[int]) -> int:
    """
    Allocates minimum delivery companies to cover all regions in implicit binary tree.
    """
    if not demand:
        return 0
    
    n = len(demand)
    if not capacities:
        return -1
    
    max_capacity = max(capacities)
    
    # Feasibility check
    for d in demand:
        if d > max_capacity:
            return -1
    
    memo = {}
    
    def solve(node):
        """Minimum paths to cover subtree rooted at node."""
        if node >= n:
            return 0
        
        if node in memo:
            return memo[node]
        
        def gen_paths(curr, acc_sum, path):
            """Generate all valid paths from curr node."""
            yield path[:]
            
            left = 2 * curr + 1
            right = 2 * curr + 2
            
            # Try left
            if left < n and acc_sum + demand[left] <= max_capacity:
                yield from gen_paths(left, acc_sum + demand[left], path + [left])
            
            # Try right
            if right < n and acc_sum + demand[right] <= max_capacity:
                yield from gen_paths(right, acc_sum + demand[right], path + [right])
        
        best = float('inf')
        
        for path in gen_paths(node, demand[node], [node]):
            covered = set(path)
            cost = 1
            
            for pnode in path:
                left = 2 * pnode + 1
                right = 2 * pnode + 2
                
                if left < n and left not in covered:
                    cost += solve(left)
                if right < n and right not in covered:
                    cost += solve(right)
            
            best = min(best, cost)
        
        memo[node] = best
        return best
    
    return solve(0)


## Entry point
if __name__ == "__main__":
    demand = [20, 30, 25, 15, 10]
    capacities = [50, 45, 40]
    result = allocate_minimum_companies(demand, capacities)
    print(result)