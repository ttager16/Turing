def fft_integer_multiplication(poly1: List[int], poly2: List[int]) -> List[int]:
    # Treat empty as [0]
    if not poly1:
        poly1 = [0]
    if not poly2:
        poly2 = [0]
    # Quick cases
    if poly1 == [0] or poly2 == [0]:
        return [0]
    if len(poly1) == 1:
        val = poly1[0]
        return [val * c for c in poly2] if not poly2 == [0] else [0]
    if len(poly2) == 1:
        val = poly2[0]
        return [val * c for c in poly1] if not poly1 == [0] else [0]

    n1 = len(poly1)
    n2 = len(poly2)
    n = 1
    while n < n1 + n2 - 1:
        n <<= 1

    # prepare complex arrays
    fa = [complex(x, 0) for x in poly1] + [0j] * (n - n1)
    fb = [complex(x, 0) for x in poly2] + [0j] * (n - n2)

    # iterative FFT
    def fft(a, invert):
        N = len(a)
        j = 0
        for i in range(1, N):
            bit = N >> 1
            while j & bit:
                j ^= bit
                bit >>= 1
            j ^= bit
            if i < j:
                a[i], a[j] = a[j], a[i]
        length = 2
        while length <= N:
            ang = 2 * math.pi / length * (-1 if invert else 1)
            wlen = complex(math.cos(ang), math.sin(ang))
            for i in range(0, N, length):
                w = 1+0j
                half = length >> 1
                for j in range(i, i + half):
                    u = a[j]
                    v = a[j + half] * w
                    a[j] = u + v
                    a[j + half] = u - v
                    w *= wlen
            length <<= 1
        if invert:
            invN = 1.0 / N
            for i in range(N):
                a[i] *= invN

    fft(fa, False)
    fft(fb, False)
    for i in range(n):
        fa[i] *= fb[i]
    fft(fa, True)

    # Round to nearest integer with tolerance
    result = [0] * (n1 + n2 - 1)
    for i in range(len(result)):
        # real part should be near integer
        val = fa[i].real
        # Round with tolerance to avoid -0.0 etc.
        rounded = int(round(val))
        # Correct possible tiny residuals crossing rounding boundary:
        if abs(val - rounded) > 0.5:
            # fallback: use math.floor/ceil based on sign
            rounded = int(math.floor(val + 0.5))
        result[i] = rounded

    # Trim trailing zeros but preserve single zero
    i = len(result) - 1
    while i > 0 and result[i] == 0:
        i -= 1
    result = result[:i+1]
    if not result:
        return [0]
    return result