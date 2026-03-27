from typing import List, Tuple


def can_secure_within_budget(
        standard_exploits: List[str],
        zero_day_threats: List[str],
        patches: List[Tuple[int, List[str]]],
        hardening_bonus: int,
        cost_threshold: int
) -> bool:
    """
    Determines if a valid set of patches can be deployed at or below a
    given cost threshold using a greedy heuristic approach.
    """
    # Edge case: no vulnerabilities to patch
    if not standard_exploits and not zero_day_threats:
        return cost_threshold >= 0

    standard_set = set(standard_exploits)
    zeroday_set = set(zero_day_threats)
    all_vulns = standard_set | zeroday_set

    # Check if all vulnerabilities can be covered
    coverable = set()
    for _, vulns in patches:
        coverable.update(vulns)
    if not all_vulns.issubset(coverable):
        return False

    # Initialize tracking structures
    selected_patches = []
    standard_covered = set()
    zeroday_count = {z: 0 for z in zeroday_set}
    available = list(range(len(patches)))

    # Phase 1: Greedily cover all vulnerabilities
    while len(standard_covered) < len(standard_set) or any(c == 0 for c in zeroday_count.values()):
        best_idx = None
        best_score = float('-inf')

        for idx in available:
            cost, vulns = patches[idx]

            # Skip patches that conflict with already covered standard exploits
            if any(v in standard_set and v in standard_covered for v in vulns):
                continue

            # Calculate new coverage provided by this patch
            new_standards = sum(1 for v in vulns if v in standard_set and v not in standard_covered)
            new_zerodays = sum(1 for v in vulns if v in zeroday_set and zeroday_count[v] == 0)

            # Skip if patch provides no new coverage
            if new_standards + new_zerodays == 0:
                continue

            # Calculate effective cost (accounting for bonuses from redundant zero-day coverage)
            extra_zerodays = sum(1 for v in vulns if v in zeroday_set and zeroday_count[v] > 0)
            effective_cost = cost - extra_zerodays * hardening_bonus

            # Score based on coverage efficiency (prioritize standard exploits)
            score = (new_standards * 2 + new_zerodays) / max(effective_cost, 1)

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            return False  # Cannot cover all vulnerabilities

        # Select the best patch
        selected_patches.append(best_idx)
        available.remove(best_idx)

        _, vulns = patches[best_idx]
        for v in vulns:
            if v in standard_set:
                standard_covered.add(v)
            if v in zeroday_set:
                zeroday_count[v] += 1

    # Phase 2: Add profitable patches for zero-day redundancy
    for idx in list(available):
        cost, vulns = patches[idx]

        # Skip if conflicts with standard exploits
        if any(v in standard_set and v in standard_covered for v in vulns):
            continue

        # Count zero-day threats covered by this patch
        zeroday_coverage = sum(1 for v in vulns if v in zeroday_set)

        # Add patch if bonus from redundancy exceeds or equals cost
        if zeroday_coverage > 0 and cost <= zeroday_coverage * hardening_bonus:
            selected_patches.append(idx)
            for v in vulns:
                if v in zeroday_set:
                    zeroday_count[v] += 1

    # Calculate final net cost
    total_cost = sum(patches[idx][0] for idx in selected_patches)
    total_bonus = sum(max(0, count - 1) for count in zeroday_count.values()) * hardening_bonus
    net_cost = total_cost - total_bonus

    return net_cost <= cost_threshold