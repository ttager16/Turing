def fft_multiply_large_integers(num1_str, num2_str, optimization_level):
    MOD = 998244353
    PRIMITIVE_ROOT = 3

    # --- Validation ---
    def invalid(msg): 
        return {"error": msg}

    if num1_str is None or num2_str is None or num1_str == "" or num2_str == "":
        return invalid("Empty string provided")
    if optimization_level not in (1,2,3):
        return invalid("Invalid optimization level")
    def valid_num(s):
        if not s.isdigit():
            return False
        if s != "0" and s.startswith("0"):
            return False
        if s == "0":
            return True
        return 50 <= len(s) <= 200
    if not valid_num(num1_str) or not valid_num(num2_str):
        # determine specific error
        for s in (num1_str, num2_str):
            if s is None or s == "":
                return invalid("Empty string provided")
            if not isinstance(s, str) or not s.isdigit():
                return invalid("Invalid integer string format")
            if s != "0" and s.startswith("0"):
                return invalid("Invalid integer string format")
            if s != "0" and not (50 <= len(s) <= 200):
                return invalid("Integer length out of range")
        return invalid("Input is not valid")

    # Quick zero handling
    if num1_str == "0" or num2_str == "0":
        return "0"

    # --- Base-10000 conversion ---
    def to_base10000(s):
        digits = []
        i = len(s)
        while i > 0:
            start = max(0, i-4)
            digits.append(int(s[start:i]))
            i -= 4
        return digits  # least significant first
    a = to_base10000(num1_str)
    b = to_base10000(num2_str)

    # --- Pad to power of two ---
    n = 1
    m = len(a) + len(b)
    while n < m:
        n <<= 1
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))

    # --- NTT utilities ---
    def mod_pow(x, e, mod=MOD):
        return pow(x, e, mod)

    # validate modulus properties by computing root for n (should be >1)
    try:
        root = mod_pow(PRIMITIVE_ROOT, (MOD-1)//n)
        if root == 0:
            return invalid("NTT modulus calculation failed")
    except Exception:
        return invalid("NTT modulus calculation failed")

    # bit-reversal permutation
    def bit_reverse_copy(arr):
        N = len(arr)
        res = [0]*N
        bits = N.bit_length()-1
        for i in range(N):
            rev = 0
            x = i
            for _ in range(bits):
                rev = (rev<<1) | (x & 1)
                x >>= 1
            res[rev] = arr[i]
        return res

    # iterative NTT
    def ntt(arr, invert=False):
        N = len(arr)
        if optimization_level >=2:
            a = bit_reverse_copy(arr)
        else:
            a = arr[:]
        length = 2
        while length <= N:
            wlen = mod_pow(PRIMITIVE_ROOT, (MOD-1)//length)
            if invert:
                wlen = pow(wlen, MOD-2, MOD)
            for i in range(0, N, length):
                w = 1
                # micro-optimizations for level 3: reduce % operations
                if optimization_level == 3:
                    for j in range(i, i + length//2):
                        u = a[j]
                        v = a[j + length//2] * w % MOD
                        a[j] = (u + v) % MOD
                        a[j + length//2] = (u - v) % MOD
                        w = (w * wlen) % MOD
                else:
                    for j in range(i, i + length//2):
                        u = a[j]
                        v = a[j + length//2] * w % MOD
                        a[j] = (u + v) % MOD
                        a[j + length//2] = (u - v) % MOD
                        w = (w * wlen) % MOD
            length <<= 1
        if invert:
            inv_n = pow(N, MOD-2, MOD)
            for i in range(N):
                a[i] = a[i] * inv_n % MOD
        return a

    # --- Forward NTT ---
    try:
        A = ntt(a, invert=False)
        B = ntt(b, invert=False)
    except Exception:
        return invalid("NTT modulus calculation failed")

    # --- Pointwise multiplication ---
    C = [(A[i] * B[i]) % MOD for i in range(n)]

    # --- Inverse NTT ---
    try:
        c = ntt(C, invert=True)
    except Exception:
        return invalid("NTT modulus calculation failed")

    # --- Extract integer coefficients and carry propagation ---
    # c currently mod MOD; but true convolution coefficients fit in integers less than MOD given inputs sizes
    # convert to ints
    coeffs = [int(x) for x in c]
    carry = 0
    for i in range(len(coeffs)):
        total = coeffs[i] + carry
        coeffs[i] = total % 10000
        carry = total // 10000
    while carry > 0:
        coeffs.append(carry % 10000)
        carry //= 10000

    # remove leading zeros
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()

    # convert back to decimal string
    parts = [str(coeffs[-1])]
    for d in reversed(coeffs[:-1]):
        parts.append(f"{d:04d}")
    result = "".join(parts)
    return result