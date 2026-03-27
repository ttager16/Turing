##  main.py
def circulant_decomposition(adj_matrix: list[list[int]]) -> list[list[list[int]]]:
    """
    Decomposes an adjacency matrix into a sum of circulant matrices.
    
    Args:
        adj_matrix: List[List[int]] - Square adjacency matrix
        
    Returns:
        List[List[List[int]]] - List of circulant matrices whose sum equals the input
    """
    if not adj_matrix or not adj_matrix[0]:
        return []
    
    n = len(adj_matrix)
    
    for row in adj_matrix:
        if len(row) != n:
            return []
    
    def create_circulant_from_pattern(n, pattern_offset, value):
        """
        Create a circulant matrix with a specific value at a specific diagonal pattern.
        pattern_offset determines which diagonal: (j - i) mod n = pattern_offset
        """
        circulant = [[0] * n for _ in range(n)]
        for i in range(n):
            j = (i + pattern_offset) % n
            circulant[i][j] = value
        return circulant
    
    def find_best_circulant(remaining):
        """
        Find the single-value circulant pattern that matches the most elements in remaining matrix.
        Optimized to O(n^2) by analyzing each diagonal pattern once.
        """
        best_circulant = None
        best_match_count = 0
        best_sum = 0
        
        # Iterate through each possible diagonal pattern (n patterns total)
        for pattern_offset in range(n):
            # Count frequency of values on this diagonal in remaining matrix
            value_count = {}
            value_sum = {}
            
            for i in range(n):
                j = (i + pattern_offset) % n
                val = remaining[i][j]
                if val > 0:
                    if val not in value_count:
                        value_count[val] = 0
                        value_sum[val] = 0
                    value_count[val] += 1
                    value_sum[val] += val
            
            # Find the best value for this pattern
            for value, count in value_count.items():
                total_sum = value_sum[value]
                
                if count > best_match_count or (count == best_match_count and total_sum > best_sum):
                    best_match_count = count
                    best_sum = total_sum
                    best_circulant = create_circulant_from_pattern(n, pattern_offset, value)
        
        return best_circulant
    
    def subtract_matrix(matrix1, matrix2):
        """Element-wise subtraction of matrix2 from matrix1."""
        result = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                result[i][j] = matrix1[i][j] - matrix2[i][j]
        return result
    
    def has_nonzero(matrix):
        """Check if matrix has any non-zero values."""
        for row in matrix:
            for val in row:
                if val != 0:
                    return True
        return False
    
    circulant_matrices = []
    remaining = [row[:] for row in adj_matrix]
    
    while has_nonzero(remaining):
        circulant = find_best_circulant(remaining)
        
        if circulant is None:
            break
        
        circulant_matrices.append(circulant)
        remaining = subtract_matrix(remaining, circulant)
    
    return circulant_matrices


if __name__ == "__main__":
    adj_matrix = [
        [5, 2, 0, 0],
        [0, 5, 2, 0],
        [0, 0, 5, 2],
        [2, 0, 0, 5]
    ]
    
    result = circulant_decomposition(adj_matrix)
    print(result)