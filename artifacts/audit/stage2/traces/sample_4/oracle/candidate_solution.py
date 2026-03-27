from typing import List
import cmath


def fft(coeffs: List[complex], inverse: bool = False) -> List[complex]:
    n = len(coeffs)
    
    if n <= 1:
        return coeffs.copy()
    
    if n & (n - 1) != 0:
        raise ValueError(f"FFT size must be power of 2, got {n}")
    
    result = coeffs.copy()
    
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        
        if i < j:
            result[i], result[j] = result[j], result[i]
    
    length = 2
    while length <= n:
        angle = 2 * cmath.pi / length * (-1 if inverse else 1)
        wlen = cmath.exp(1j * angle)
        
        for i in range(0, n, length):
            w = 1 + 0j
            for j in range(length // 2):
                u = result[i + j]
                v = result[i + j + length // 2] * w
                result[i + j] = u + v
                result[i + j + length // 2] = u - v
                w *= wlen
        
        length *= 2
    
    if inverse:
        result = [c / n for c in result]
    
    return result


def next_power_of_2(n: int) -> int:
    if n <= 0:
        return 1
    return 1 << (n - 1).bit_length()


def validate_polynomial(poly: List[int]) -> List[int]:
    if poly is None or len(poly) == 0:
        return [0]
    
    if not isinstance(poly, list):
        raise TypeError(f"Expected list, got {type(poly).__name__}")
    
    validated = []
    for i, coeff in enumerate(poly):
        if not isinstance(coeff, (int, float)):
            try:
                coeff = int(coeff)
            except (ValueError, TypeError):
                raise TypeError(f"Invalid coefficient at index {i}: {type(coeff).__name__}")
        
        if isinstance(coeff, float):
            coeff = int(round(coeff))
        
        if coeff < -1000000 or coeff > 1000000:
            raise ValueError(f"Coefficient at index {i} is out of range [-10^6, 10^6]: {coeff}")
        
        validated.append(coeff)
    
    if all(c == 0 for c in validated):
        return [0]
    
    return validated


def trim_trailing_zeros(poly: List[int]) -> List[int]:
    last_nonzero = -1
    for i in range(len(poly) - 1, -1, -1):
        if poly[i] != 0:
            last_nonzero = i
            break
    
    if last_nonzero == -1:
        return [0]
    
    return poly[:last_nonzero + 1]


def direct_multiply(poly1: List[int], poly2: List[int]) -> List[int]:
    if not poly1 or not poly2:
        return [0]
    
    result = [0] * (len(poly1) + len(poly2) - 1)
    
    for i in range(len(poly1)):
        for j in range(len(poly2)):
            result[i + j] += poly1[i] * poly2[j]
    
    return trim_trailing_zeros(result)


def fft_multiply(poly1: List[int], poly2: List[int]) -> List[int]:
    n1, n2 = len(poly1), len(poly2)
    result_size = n1 + n2 - 1
    fft_size = next_power_of_2(result_size)
    
    buffer1 = [complex(poly1[i], 0) if i < n1 else 0j for i in range(fft_size)]
    buffer2 = [complex(poly2[i], 0) if i < n2 else 0j for i in range(fft_size)]
    
    fft1 = fft(buffer1, inverse=False)
    fft2 = fft(buffer2, inverse=False)
    
    product = [fft1[i] * fft2[i] for i in range(fft_size)]
    
    result_complex = fft(product, inverse=True)
    
    result = []
    for i in range(result_size):
        real_part = result_complex[i].real
        rounded = int(round(real_part))
        
        if abs(real_part) < 1e-9:
            rounded = 0
        result.append(rounded)
    
    return result


def fft_integer_multiplication(poly1: List[int], poly2: List[int]) -> List[int]:
    poly1 = validate_polynomial(poly1)
    poly2 = validate_polynomial(poly2)
    
    if poly1 == [0] or poly2 == [0]:
        return [0]
    
    if len(poly1) == 1:
        result = [poly1[0] * c for c in poly2]
        return trim_trailing_zeros(result)
    
    if len(poly2) == 1:
        result = [poly2[0] * c for c in poly1]
        return trim_trailing_zeros(result)
    
    if len(poly1) > 100000 or len(poly2) > 100000:
        raise ValueError(f"Polynomial exceeds size limit: poly1={len(poly1)}, poly2={len(poly2)}, max=100000")
    
    if len(poly1) + len(poly2) <= 20:
        return direct_multiply(poly1, poly2)
    
    result = fft_multiply(poly1, poly2)
    
    return trim_trailing_zeros(result)


if __name__ == "__main__":
    poly1 = [2, 0, 1, 3]
    poly2 = [4, 5, 0, 1]
    result = fft_integer_multiplication(poly1, poly2)
    print(result)