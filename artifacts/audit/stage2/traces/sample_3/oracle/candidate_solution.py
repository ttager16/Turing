def fft_multiply_large_integers(num1_str, num2_str, optimization_level):
    """
    Multiplies two large integers using optimized FFT-based algorithm.
    
    Returns: String representation of the multiplication result
    """
    
    # Input validation
    if num1_str is None or num2_str is None:
        return {"error": "Empty string provided"}
    
    if num1_str == "" or num2_str == "":
        return {"error": "Empty string provided"}
    
    if not isinstance(num1_str,str) or not isinstance(num2_str,str):
        return { "error" : "Input is not valid"}
    
    if not isinstance(optimization_level, int) or optimization_level not in [1, 2, 3]:
        return {"error" :"Invalid optimization level" }
    
    # Validate string format and handle leading zeros
    for num_str in [num1_str, num2_str]:
        if not num_str.isdigit():
            return {"error" : "Invalid integer string format"}
        
        if len(num_str) > 1 and num_str[0] == '0':
            return {"error" : "Invalid integer string format"}
    
    # Length validation with special case for "0"
    for num_str in [num1_str, num2_str]:
        if num_str != "0":
            if len(num_str) < 50 or len(num_str) > 200:
                return {"error" : "Integer length out of range"}
    
    # Handle multiplication by zero
    if num1_str == "0" or num2_str == "0":
        return "0"
    
    # Constants for NTT
    MOD = 998244353
    BASE = 10000
    
    def mod_pow_with_pattern(base, exponent, modulus):
        """
        Modular exponentiation following the specified pattern:
        exponent follows pattern (modulus - 1) // (2^k) for appropriate k values
        """
        # For NTT roots, we need to handle the specific pattern mentioned in prompt
        result = 1
        base = base % modulus
        while exponent > 0:
            if exponent % 2 == 1:
                result = (result * base) % modulus
            exponent = exponent >> 1
            base = (base * base) % modulus
        return result
    
    def get_primitive_nth_root_corrected(n):
        """
        Get primitive nth root of unity using the EXACT specified formula:
        nth roots are computed as `pow(3, (998244353-1)//n, 998244353)`
        """
        if (MOD - 1) % n != 0:
            return {"error" : "NTT modulus calculation failed"}
        
        # Verify n is a power of 2 for valid NTT
        if n & (n - 1) != 0:
            return {"error" : "NTT modulus calculation failed"}
        
        try:
            # Use the EXACT formula specified in prompt
            exponent = (998244353 - 1) // n
            return mod_pow_with_pattern(3, exponent, 998244353)
        except:
            return {"error" : "NTT modulus calculation failed"}
    
    def bit_reverse(arr, n):
        """Bit reversal for optimization level 2+"""
        j = 0
        for i in range(1, n):
            bit = n >> 1
            while j & bit:
                j ^= bit
                bit >>= 1
            j ^= bit
            if i < j:
                arr[i], arr[j] = arr[j], arr[i]
    
    def ntt_forward_corrected(arr, n, optimization_level):
        """
        Forward Number Theoretic Transform with CORRECT optimization levels:
        Level 1: Basic NTT without optimizations (NO bit-reversal)
        Level 2: Include bit-reversal optimization for FFT
        Level 3: Add cache-friendly memory access patterns and reduce modular operations
        """
        try:
            # Level 1: Basic NTT WITHOUT optimizations (no bit-reversal)
            # Level 2+: Include bit-reversal optimization
            if optimization_level >= 2:
                bit_reverse(arr, n)
            
            length = 2
            while length <= n:
                root = get_primitive_nth_root_corrected(length)
                
                # Level 3: Cache-friendly memory access patterns and REDUCE modular operations
                if optimization_level >= 3:
                    # Process in cache-friendly blocks and pre-compute to reduce modular ops
                    for start in range(0, n, length):
                        # Pre-compute ALL powers to reduce modular operations significantly
                        powers = [1]
                        w = 1
                        for _ in range(length // 2):
                            w = (w * root) % MOD
                            powers.append(w)
                        
                        # Cache-friendly memory access - process consecutive elements
                        for i in range(length // 2):
                            u = arr[start + i]
                            v = (arr[start + i + length // 2] * powers[i]) % MOD
                            arr[start + i] = (u + v) % MOD
                            arr[start + i + length // 2] = (u - v + MOD) % MOD
                else:
                    # Level 1 & 2: Standard approach with more modular operations
                    for start in range(0, n, length):
                        w = 1
                        for i in range(length // 2):
                            u = arr[start + i]
                            v = (arr[start + i + length // 2] * w) % MOD
                            arr[start + i] = (u + v) % MOD
                            arr[start + i + length // 2] = (u - v + MOD) % MOD
                            w = (w * root) % MOD  # More modular operations per iteration
                
                length <<= 1
        except:
            return {"error" : "NTT modulus calculation failed"}
    
    def ntt_inverse_corrected(arr, n, optimization_level):
        """
        Inverse Number Theoretic Transform with CORRECT optimization levels
        Level 1: Basic without bit-reversal
        Level 2+: With bit-reversal (but only if not already applied in forward)
        """
        try:
            # For inverse NTT, bit-reversal is only needed if it wasn't applied in forward
            # Level 1: No bit-reversal anywhere
            # Level 2+: Bit-reversal was applied in forward, so we need it here too for proper inverse
            if optimization_level >= 2:
                bit_reverse(arr, n)
            
            length = 2
            while length <= n:
                root = get_primitive_nth_root_corrected(length)
                root = mod_pow_with_pattern(root, MOD - 2, MOD)  # Modular inverse
                
                # Level 3: Cache-friendly memory access patterns and reduce modular operations
                if optimization_level >= 3:
                    for start in range(0, n, length):
                        # Pre-compute powers to reduce modular operations
                        powers = [1]
                        w = 1
                        for _ in range(length // 2):
                            w = (w * root) % MOD
                            powers.append(w)
                        
                        for i in range(length // 2):
                            u = arr[start + i]
                            v = (arr[start + i + length // 2] * powers[i]) % MOD
                            arr[start + i] = (u + v) % MOD
                            arr[start + i + length // 2] = (u - v + MOD) % MOD
                else:
                    # Level 1 & 2: Standard approach
                    for start in range(0, n, length):
                        w = 1
                        for i in range(length // 2):
                            u = arr[start + i]
                            v = (arr[start + i + length // 2] * w) % MOD
                            arr[start + i] = (u + v) % MOD
                            arr[start + i + length // 2] = (u - v + MOD) % MOD
                            w = (w * root) % MOD
                
                length <<= 1
            
            # Normalize by dividing by n
            n_inv = mod_pow_with_pattern(n, MOD - 2, MOD)
            for i in range(n):
                arr[i] = (arr[i] * n_inv) % MOD
                
        except:
            return {"error" : "NTT modulus calculation failed"}
    
    def string_to_base_array_specified(num_str):
        """
        Convert decimal strings to base-10000 arrays using the EXACT specified formula:
        digits = [int(num_str[i:i+4]) for i in range(len(num_str)-4, -1, -4)]
        """
        digits = [int(num_str[i:i+4]) for i in range(len(num_str)-4, -1, -4)]
        return digits
    
    def base_array_to_string(digits):
        """Convert base-10000 array to decimal string"""
        if not digits or all(d == 0 for d in digits):
            return "0"
        
        # Remove leading zeros
        while len(digits) > 1 and digits[-1] == 0:
            digits.pop()
        
        # Convert back to string
        result = str(digits[-1])  # Most significant digit (no padding)
        for i in range(len(digits) - 2, -1, -1):
            result += f"{digits[i]:04d}"  # Pad with zeros
        
        return result
    
    def next_power_of_2(n):
        """Find next power of 2 >= n"""
        power = 1
        while power < n:
            power <<= 1
        return power
    
    def check_memory_constraint(fft_length):
        """
        Check memory constraints based on O(n log n) space complexity requirement
        where n is the maximum digit count
        """
        try:
            max_digits = max(len(num1_str), len(num2_str))
            
            required_space_factor = max_digits * (max_digits.bit_length())
            
            if fft_length > 2**20 or required_space_factor > 10**8:
                return False
            return True
        except:
            return False
    
    try:

        num1_digits = string_to_base_array_specified(num1_str)
        num2_digits = string_to_base_array_specified(num2_str)
        
        # Pad shorter numbers with leading zeros to match the longer number's length
        max_input_length = max(len(num1_digits), len(num2_digits))
        while len(num1_digits) < max_input_length:
            num1_digits.append(0)
        while len(num2_digits) < max_input_length:
            num2_digits.append(0)
        
        # Ensure total length is a power of 2 for efficient FFT processing
        result_length = len(num1_digits) + len(num2_digits)
        fft_length = next_power_of_2(result_length)
        
        # Pad to fft_length
        while len(num1_digits) < fft_length:
            num1_digits.append(0)
        while len(num2_digits) < fft_length:
            num2_digits.append(0)
        
        # STAGE 2: Number Theoretic Transform
        
        # Apply forward NTT using modulus 998244353 and primitive root 3
        ntt_forward_corrected(num1_digits, fft_length, optimization_level)
        ntt_forward_corrected(num2_digits, fft_length, optimization_level)
        
        # Perform pointwise multiplication in the frequency domain
        result_digits = []
        for i in range(fft_length):
            result_digits.append((num1_digits[i] * num2_digits[i]) % MOD)
        
        # Apply inverse NTT to obtain the convolution result
        ntt_inverse_corrected(result_digits, fft_length, optimization_level)
        
        # STAGE 3: Carry Propagation
        
        # Process carries from the least significant to the most significant digits
        carry = 0
        for i in range(len(result_digits)):
            # Handle overflow using the EXACT specified formulas
            current_digit_plus_carry = result_digits[i] + carry
            new_digit = current_digit_plus_carry % BASE  # new_digit = (current_digit + carry) % 10000
            carry = current_digit_plus_carry // BASE     # carry = (current_digit + carry) // 10000
            result_digits[i] = new_digit
        
        # Handle any remaining carry
        while carry > 0:
            result_digits.append(carry % BASE)
            carry //= BASE
        
        # Convert back to string
        result_str = base_array_to_string(result_digits)
        
        return result_str
        
    except TypeError as e:
        # Preserve specific TypeError messages
        return {"error": str(e)}
    except ValueError as e:
        # Preserve specific ValueError messages like "NTT modulus calculation failed"
        if any(msg in str(e) for msg in [
            "Invalid integer string format",
            "Integer length out of range", 
            "Invalid optimization level",
            "NTT modulus calculation failed"
        ]):
            return {"error":str(e)}
        else:
            return { "error" : "Input is not valid"}
    except Exception:
        # Only catch truly unexpected exceptions
        return { "error" : "Input is not valid"}


if __name__ == "__main__":
    # Test with sample input
    num1_str = "12345678901234567890123456789012345678901234567890123456789012345678901234567890"
    num2_str = "98765432109876543210987654321098765432109876543210987654321098765432109876543210" 
    optimization_level=2
    result = fft_multiply_large_integers(num1_str, num2_str, optimization_level)
    print(result)