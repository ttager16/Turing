from typing import List


def simulate_quantum_circuit(bitmask: str, gates: List[List], num_qubits: str) -> str:

    # --- helpers ---
    def get_bit(mask: int, i: int) -> int:
        return (mask >> i) & 1

    def bitmask_to_str(mask: int, q: int) -> str:
        return ''.join('1' if get_bit(mask, i) else '0' for i in range(q - 1, -1, -1))

    # --- Parse string inputs to integers ---
    try:
        bitmask_int = int(bitmask, 0)
    except Exception:
        return "ValueError: Invalid Input"
    
    try:
        num_qubits_int = int(num_qubits, 0)
    except Exception:
        return "ValueError: Invalid Input"

    # --- validate top-level args ---
    if not isinstance(num_qubits_int, int):
        return "ValueError: Invalid Input"
    if num_qubits_int <= 0:
        return "ValueError: Invalid Input"
    if not isinstance(bitmask_int, int):
        return "ValueError: Invalid Input"
    if bitmask_int < 0 or bitmask_int >= (1 << num_qubits_int):
        return "ValueError: Invalid Input"
    if not isinstance(gates, list):
        return "ValueError: Invalid Input"

    # Pre-validate every gate fully before executing anything
    valid_ops = {"MCX", "CNOT", "MEASURE", "REORDER", "TRACE"}
    for idx, g in enumerate(gates):
        if not (isinstance(g, list) and len(g) == 2):
            return "ValueError: Invalid Input"
        op, qlist = g
        if not isinstance(op, str):
            return "ValueError: Invalid Input"
        if op not in valid_ops:
            return "ValueError: Invalid Input"
        if not isinstance(qlist, list):
            return "ValueError: Invalid Input"

        # Per-op validation
        if op == "MCX":
            if len(qlist) < 1:
                return "ValueError: Invalid Input"
            for q in qlist:
                if not isinstance(q, int) or q < 0 or q >= num_qubits_int:
                    return "ValueError: Invalid Input"
        elif op == "CNOT":
            if len(qlist) != 2:
                return "ValueError: Invalid Input"
            a, b = qlist
            if not all(isinstance(x, int) for x in (a, b)):
                return "ValueError: Invalid Input"
            if a < 0 or a >= num_qubits_int or b < 0 or b >= num_qubits_int:
                return "ValueError: Invalid Input"
        elif op == "MEASURE":
            if len(qlist) != 1:
                return "ValueError: Invalid Input"
            q = qlist[0]
            if not isinstance(q, int) or q < 0 or q >= num_qubits_int:
                return "ValueError: Invalid Input"
        elif op == "REORDER":
            if len(qlist) != num_qubits_int:
                return "ValueError: Invalid Input"
            seen = [False] * num_qubits_int
            for q in qlist:
                if not isinstance(q, int) or q < 0 or q >= num_qubits_int:
                    return "ValueError: Invalid Input"
                if seen[q]:
                    return "ValueError: Invalid Input"
                seen[q] = True
            if not all(seen):
                return "ValueError: Invalid Input"
        elif op == "TRACE":
            if len(qlist) != 0:
                return "ValueError: Invalid Input"

    # --- all validation passed; execute gates sequentially ---
    initial_mask = bitmask_int
    current_mask = bitmask_int
    changed_qubits = set()
    trace_states: List[str] = []

    for op, qlist in gates:
        if op == "MCX":
            if len(qlist) == 1:
                controls = []
                target = qlist[0]
            else:
                controls = list(qlist[:-1])
                target = qlist[-1]
            # If all control bits are 1 (vacuously true for empty controls), flip target
            if all(get_bit(current_mask, c) == 1 for c in controls):
                before = get_bit(current_mask, target)
                current_mask ^= (1 << target)
                after = get_bit(current_mask, target)
                if before != after:
                    changed_qubits.add(target)

        elif op == "CNOT":
            control, target = qlist
            if get_bit(current_mask, control) == 1:
                before = get_bit(current_mask, target)
                current_mask ^= (1 << target)
                after = get_bit(current_mask, target)
                if before != after:
                    changed_qubits.add(target)

        elif op == "MEASURE":
            # Deterministic read in this classical model; no state change
            _ = get_bit(current_mask, qlist[0])

        elif op == "REORDER":
            perm = list(qlist)
            old_mask = current_mask
            new_mask = 0
            # semantics: new[i] = old[perm[i]]
            for i in range(num_qubits_int):
                src = perm[i]
                if get_bit(old_mask, src):
                    new_mask |= (1 << i)
            current_mask = new_mask
            # Record changed qubits where bit value at a given index flipped due to permutation
            for i in range(num_qubits_int):
                if get_bit(old_mask, i) != get_bit(current_mask, i):
                    changed_qubits.add(i)

        elif op == "TRACE":
            # Record current state (no modification); format as |bits>
            trace_states.append(f"|{bitmask_to_str(current_mask, num_qubits_int)}>")

    initial_bits = bitmask_to_str(initial_mask, num_qubits_int)
    final_bits = bitmask_to_str(current_mask, num_qubits_int)
    changed_list = sorted(changed_qubits)

    result = f"Resulting State: |{initial_bits}> -> |{final_bits}> | Changed qubits: {changed_list}"
    if trace_states:
        result += "\nTrace: [" + ", ".join(ts for ts in trace_states) + "]"
    return result