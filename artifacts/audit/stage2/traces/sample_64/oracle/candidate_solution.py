# main.py

from typing import List, Dict, Any, Tuple


class DSU:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            # path compression one-step
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> int:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return ra
        # union by rank
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return ra


def _bbox_of_coords(coords: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) for a list of (x,y) coordinates."""
    if not coords:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return (min(xs), min(ys), max(xs), max(ys))


def _bboxes_intersect(a: Tuple[float, float, float, float],
                      b: Tuple[float, float, float, float]) -> bool:
    """Axis-aligned bbox intersection (non-empty)."""
    a_minx, a_miny, a_maxx, a_maxy = a
    b_minx, b_miny, b_maxx, b_maxy = b
    # Intersection occurs when projections overlap
    return not (a_maxx < b_minx or b_maxx < a_minx or a_maxy < b_miny or b_maxy < a_miny)


def _aggregate_resource_dicts(list_of_res: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Conservative deterministic aggregation for a list of resource dicts.
    Numeric fields -> sum; list fields -> concatenation; nested dicts -> apply recursively.
    This function is used to produce aggregated summaries for a set of zones.
    """
    agg: Dict[str, Any] = {}
    for res in list_of_res:
        for k, v in res.items():
            if k not in agg:
                # initialize with a deep-ish copy (safe for basic types)
                if isinstance(v, (int, float)):
                    agg[k] = v
                elif isinstance(v, list):
                    agg[k] = list(v)
                elif isinstance(v, dict):
                    agg[k] = _aggregate_resource_dicts([v])
                else:
                    # other types: gather into a list
                    agg[k] = [v]
            else:
                # existing key: merge depending on type
                if isinstance(v, (int, float)) and isinstance(agg[k], (int, float)):
                    agg[k] = agg[k] + v
                elif isinstance(v, list) and isinstance(agg[k], list):
                    agg[k].extend(v)
                elif isinstance(v, dict) and isinstance(agg[k], dict):
                    # merge nested dicts
                    nested = _aggregate_resource_dicts([agg[k], v])
                    agg[k] = nested
                else:
                    # fallback: coerce to list and append
                    if not isinstance(agg[k], list):
                        agg[k] = [agg[k]]
                    agg[k].append(v)
    return agg


def _compatible_resources(resource_a: Dict[str, Any],
                          resource_b: Dict[str, Any]) -> bool:
    """
    Conservative compatibility check of two resource summaries.
    Rules:
      - water.capacity sum must be <= min(all max_water_capacity values present),
        if any such max is present in either resource dict under key 'max_water_capacity'
        (we check both dicts for 'max_water_capacity' numeric fields).
      - roads: if max_density provided by either, enforce sum(density) <= min(all max_density).
      - For other numeric limits, no general constraint is enforced.
    """
    # Water compatibility
    a_water = resource_a.get("water", {})
    b_water = resource_b.get("water", {})
    a_cap = a_water.get("capacity", 0) if isinstance(a_water, dict) else 0
    b_cap = b_water.get("capacity", 0) if isinstance(b_water, dict) else 0
    total_water = (a_cap or 0) + (b_cap or 0)

    # collect any max_water_capacity constraints present
    max_caps = []
    if isinstance(a_water, dict) and "max_water_capacity" in a_water:
        try:
            max_caps.append(float(a_water["max_water_capacity"]))
        except Exception:
            pass
    if isinstance(b_water, dict) and "max_water_capacity" in b_water:
        try:
            max_caps.append(float(b_water["max_water_capacity"]))
        except Exception:
            pass
    if max_caps:
        limit = min(max_caps)
        if total_water > limit:
            return False  # violates water capacity constraint

    # Roads compatibility: check densities vs potential max_density fields
    a_roads = resource_a.get("roads", {})
    b_roads = resource_b.get("roads", {})
    a_density = a_roads.get("density", 0) if isinstance(a_roads, dict) else 0
    b_density = b_roads.get("density", 0) if isinstance(b_roads, dict) else 0
    total_density = (a_density or 0) + (b_density or 0)
    max_densities = []
    if isinstance(a_roads, dict) and "max_density" in a_roads:
        try:
            max_densities.append(float(a_roads["max_density"]))
        except Exception:
            pass
    if isinstance(b_roads, dict) and "max_density" in b_roads:
        try:
            max_densities.append(float(b_roads["max_density"]))
        except Exception:
            pass
    if max_densities:
        dens_limit = min(max_densities)
        if total_density > dens_limit:
            return False

    # If both checks passed (or no constraints), declare compatible
    return True


def optimize_city_layout(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge zones deterministically based on bbox overlap and resource compatibility.

    Returns a list of merged zone dicts following aggregation rules.
    """
    if zones is None:
        return []

    n = len(zones)
    if n == 0:
        return []

    # Preprocess zones: stable order by input index; also map index -> zone
    indexed = list(enumerate(zones))

    # Compute bounding boxes and normalized resources for each zone
    bboxes = []
    resources = []
    ids = []
    types = []
    coords = []
    for idx, z in indexed:
        zid = int(z.get("id", idx))
        ids.append(zid)
        types.append(str(z.get("type", "unknown")))
        c = z.get("coordinates", []) or []
        coords.append(list(c))
        bbox = _bbox_of_coords(c)
        bboxes.append(bbox)
        res = z.get("resources", {}) or {}
        resources.append(res)

    # Build adjacency candidate pairs using an O(n^2) check with deterministic ordering.
    # For modest n (<=2000) this is acceptable. We sort by minx to allow early pruning.
    indexed_b = list(enumerate(bboxes))
    # pair list as tuples (i, j) with i<j, sorted deterministically by (min(ids[i], ids[j]), max(...))
    candidate_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if _bboxes_intersect(bboxes[i], bboxes[j]):
                candidate_pairs.append((i, j))
    # Sort candidate pairs deterministically by zone id (not by index) then by indices
    candidate_pairs.sort(key=lambda ij: (min(ids[ij[0]], ids[ij[1]]),
                                         max(ids[ij[0]], ids[ij[1]]),
                                         ij[0], ij[1]))

    # Initialize DSU
    dsu = DSU(n)

    # Maintain aggregated resource summaries per DSU root (initially per zone)
    agg_resources: List[Dict[str, Any]] = [None] * n
    member_ids: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        agg_resources[i] = _aggregate_resource_dicts([resources[i]])
        member_ids[i] = [i]

    # Iteratively union compatible sets until no more unions occur
    changed = True
    # To ensure termination and determinism, we repeatedly scan candidate_pairs in the same order
    # and attempt unions; stop when a pass yields no unions.
    while changed:
        changed = False
        for (i, j) in candidate_pairs:
            ri = dsu.find(i)
            rj = dsu.find(j)
            if ri == rj:
                continue
            # evaluate compatibility between aggregated resources of ri and rj
            if _compatible_resources(agg_resources[ri], agg_resources[rj]):
                # perform union and update aggregated data
                new_root = dsu.union(ri, rj)
                # determine other root
                other = ri if new_root == rj else rj
                # Merge member ids deterministically by original zone id ordering
                combined_members = member_ids[new_root] + member_ids[other]
                # We want deterministic ordering by original zone id (ids list)
                combined_members = sorted(set(combined_members), key=lambda idx: ids[idx])
                member_ids[new_root] = combined_members
                member_ids[other] = []  # cleared; optional
                # Update aggregated resources
                agg_resources[new_root] = _aggregate_resource_dicts(
                    [agg_resources[new_root], agg_resources[other]]
                )
                agg_resources[other] = {}  # cleared
                changed = True
                # Note: continue scanning pairs to allow further transitive merges

    # After unions stabilized, collect final sets
    root_to_members: Dict[int, List[int]] = {}
    for i in range(n):
        ri = dsu.find(i)
        root_to_members.setdefault(ri, [])
        root_to_members[ri].append(i)

    # Build merged zone dicts deterministically: for each set, sort members by original zone id
    merged_zones: List[Dict[str, Any]] = []
    for root in sorted(root_to_members.keys(), key=lambda r: min(ids[idx] for idx in root_to_members[r])):
        members = root_to_members[root]
        # sort members by original zone id for deterministic aggregation
        members_sorted = sorted(members, key=lambda idx: ids[idx])
        constituent_ids = [ids[idx] for idx in members_sorted]
        count = len(constituent_ids)
        new_id = int(min(constituent_ids)) * 100 + count
        # type determination
        set_types = [types[idx] for idx in members_sorted]
        merged_type = set_types[0] if all(t == set_types[0] for t in set_types) else "mixed"
        # coordinates: concatenate in ascending zone id order
        merged_coords: List[Tuple[float, float]] = []
        for idx in members_sorted:
            merged_coords.extend(coords[idx])
        # resources: aggregate with deterministic rules
        res_list = [resources[idx] for idx in members_sorted]
        merged_resources = _aggregate_resource_dicts(res_list)

        merged_zone = {
            "id": new_id,
            "type": merged_type,
            "coordinates": merged_coords,
            "resources": merged_resources
        }
        merged_zones.append(merged_zone)

    # Sort final list by merged id for determinism
    merged_zones.sort(key=lambda z: z["id"])
    return merged_zones