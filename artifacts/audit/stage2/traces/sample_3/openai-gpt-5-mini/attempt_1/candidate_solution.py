def fft_multiply_large_integers(num1_str, num2_str, optimization_level):
    MOD = 998244353
    PRIMITIVE_ROOT = 3

    # --- Input validation ---
    def invalid(msg): 
        return {"error": msg}

    if num1_str is None or num2_str is None or num1_str == "" or num2_str == "":
        return invalid("Empty string provided")
    if optimization_level not in (1,2,3):
        return invalid("Invalid optimization level")
    if not (isinstance(num1_str, str) and isinstance(num2_str, str)):
        return invalid("Input is not valid")
    def valid_int_str(s):
        if s == "0":
            return True
        if not s.isdigit():
            return False
        if s[0] == '0':
            return False
        return True
    if not valid_int_str(num1_str) or not valid_int_str(num2_str):
        return invalid("Invalid integer string format")
    def valid_length(s):
        if s == "0":
            return True
        return 50 <= len(s) <= 200
    if not valid_length(num1_str) or not valid_length(num2_str):
        return invalid("Integer length out of range")

    # --- Base-10000 conversion ---
    def to_base10000(s):
        if s == "0":
            return [0]
        digits = []
        i = len(s)
        while i > 0:
            start = max(0, i-4)
            digits.append(int(s[start:i]))
            i -= 4
        return digits  # least significant first

    a = to_base10000(num1_str)
    b = to_base10000(num2_str)

    # --- helper: next power of two ---
    def next_pow2(x):
        p = 1
        while p < x:
            p <<= 1
        return p

    n = next_pow2(len(a) + len(b))
    # pad arrays
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))

    # --- modular utilities ---
    def mod_pow(base, exp, mod):
        return pow(base, exp, mod)
    # Validate modulus root calculation
    try:
        test_root = mod_pow(PRIMITIVE_ROOT, (MOD-1)//2, MOD)
    except Exception:
        return invalid("NTT modulus calculation failed")
    if test_root not in (MOD-1, 1):
        return invalid("NTT modulus calculation failed")

    # --- Bit-reversal permutation ---
    def bit_reverse(arr):
        n = len(arr)
        j = 0
        for i in range(1, n):
            bit = n >> 1
            while j & bit:
                j ^= bit
                bit >>= 1
            j ^= bit
            if i < j:
                arr[i], arr[j] = arr[j], arr[i]

    # --- NTT ---
    def ntt(a_arr, invert):
        n_local = len(a_arr)
        if optimization_level >= 2:
            bit_reverse(a_arr)
        else:
            # level 1: no bit reversal; implement simple Cooley-Tukey with explicit copies
            pass

        length = 2
        while length <= n_local:
            wlen = mod_pow(PRIMITIVE_ROOT, (MOD - 1) // length, MOD)
            if invert:
                wlen = mod_pow(wlen, MOD-2, MOD)
            half = length >> 1
            for i in range(0, n_local, length):
                w = 1
                # inner loop may be optimized at level 3
                if optimization_level == 3:
                    for j in range(half):
                        u = a_arr[i + j]
                        v = (a_arr[i + j + half] * w) % MOD
                        a_arr[i + j] = (u + v) % MOD
                        a_arr[i + j + half] = (u - v) % MOD
                        w = (w * wlen) % MOD
                else:
                    for j in range(half):
                        u = a_arr[i + j]
                        v = (a_arr[i + j + half] * w) % MOD
                        a_arr[i + j] = (u + v) % MOD
                        a_arr[i + j + half] = (u - v) % MOD
                        w = (w * wlen) % MOD
            length <<= 1
        if invert:
            inv_n = mod_pow(n_local, MOD-2, MOD)
            for i in range(n_local):
                a_arr[i] = (a_arr[i] * inv_n) % MOD

    # Prepare arrays for NTT: map base-10000 digits into field
    fa = [x % MOD for x in a]
    fb = [x % MOD for x in b]

    # Forward NTT
    ntt(fa, invert=False)
    ntt(fb, invert=False)

    # Pointwise multiplication
    for i in range(n):
        fa[i] = (fa[i] * fb[i]) % MOD

    # Inverse NTT
    ntt(fa, invert=True)

    # Extract integer coefficients (they may be modulo MOD)
    # Since original convolution coefficients are small (<10000*n), and MOD is big, we can take fa[i] as integers
    res = [int(fa[i]) for i in range(n)]

    # Carry propagation base 10000
    carry = 0
    for i in range(n):
        total = res[i] + carry
        digit = total % 10000
        carry = total // 10000
        res[i] = digit
    while carry > 0:
        res.append(carry % 10000)
        carry //= 10000

    # remove leading zeros
    while len(res) > 1 and res[-1] == 0:
        res.pop()

    # convert back to string
    if not res:
        return "0"
    parts = []
    for i in range(len(res)-1, -1, -1):
        if i == len(res)-1:
            parts.append(str(res[i]))
        else:
            parts.append("{:0>4}".format(res[i]))
    return "".join(parts)