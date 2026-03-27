def fft_integer_multiplication(poly1: List[int], poly2: List[int]) -> List[int]:
    # Handle empty as zero
    if not poly1: poly1 = [0]
    if not poly2: poly2 = [0]
    # Quick scalar cases
    if len(poly1) == 1:
        k = poly1[0]
        if k == 0: return [0]
        res = [k * c for c in poly2]
        # trim
        while len(res) > 1 and res[-1] == 0:
            res.pop()
        return res
    if len(poly2) == 1:
        k = poly2[0]
        if k == 0: return [0]
        res = [k * c for c in poly1]
        while len(res) > 1 and res[-1] == 0:
            res.pop()
        return res

    n1 = len(poly1)
    n2 = len(poly2)
    result_size = n1 + n2 - 1
    # compute size as power of two >= result_size
    n = 1
    while n < result_size:
        n <<= 1

    # prepare complex arrays
    fa = [complex(x, 0) for x in poly1] + [0] * (n - n1)
    fb = [complex(x, 0) for x in poly2] + [0] * (n - n2)

    # iterative in-place FFT
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
            invN = 1 / N
            for i in range(N):
                a[i] *= invN

    fft(fa, False)
    fft(fb, False)
    for i in range(n):
        fa[i] *= fb[i]
    fft(fa, True)

    # rounding with epsilon to avoid precision issues
    res = [0] * result_size
    for i in range(result_size):
        # Real part should be near integer
        val = fa[i].real
        # Round to nearest integer
        iv = int(round(val))
        res[i] = iv

    # Trim trailing zeros but ensure at least [0]
    while len(res) > 1 and res[-1] == 0:
        res.pop()
    if not res:
        return [0]
    return res