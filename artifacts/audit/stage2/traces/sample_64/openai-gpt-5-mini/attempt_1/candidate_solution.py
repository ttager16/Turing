def optimize_city_layout(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Helper: compute axis-aligned bounding box for a zone
    def bbox(coords: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        return (min(xs), min(ys), max(xs), max(ys))

    # Helper: check bbox intersection (non-empty)
    def bbox_intersect(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)

    # Disjoint set (union-find) with path compression and union by rank
    class DSU:
        def __init__(self, n):
            self.parent = list(range(n))
            self.rank = [0]*n
        def find(self, x):
            p = self.parent
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x
        def union(self, x, y):
            rx = self.find(x)
            ry = self.find(y)
            if rx == ry:
                return False
            if self.rank[rx] < self.rank[ry]:
                self.parent[rx] = ry
            else:
                self.parent[ry] = rx
                if self.rank[rx] == self.rank[ry]:
                    self.rank[rx] += 1
            return True

    # Prepare zones sorted by id to ensure deterministic ordering where needed
    zones_sorted = sorted(zones, key=lambda z: z.get('id', 0))
    n = len(zones_sorted)
    id_to_index = {zones_sorted[i]['id']: i for i in range(n)}

    # Precompute bboxes
    bboxes = []
    for z in zones_sorted:
        coords = z.get('coordinates', [])
        if not coords:
            bboxes.append((0.0,0.0,0.0,0.0))
        else:
            bboxes.append(bbox(coords))

    dsu = DSU(n)

    # Global thresholds: can be configured here
    MAX_WATER_CAPACITY = 1000000  # default very large; per-zone max_water_capacity can restrict merges
    # Phase 1: raw adjacency pairs via bbox intersections
    adjacency_pairs = []
    # For n up to ~2000, O(n^2) acceptable
    for i in range(n):
        for j in range(i+1, n):
            if bbox_intersect(bboxes[i], bboxes[j]):
                adjacency_pairs.append((i, j))

    # Phase 2: resource compatibility checks for each adjacency pair
    for i, j in adjacency_pairs:
        zi = zones_sorted[i]
        zj = zones_sorted[j]
        ri = zi.get('resources', {}) or {}
        rj = zj.get('resources', {}) or {}

        compatible = True

        # Water compatibility: merged capacity must not exceed any provided max_water_capacity.
        # Default MAX_WATER_CAPACITY is large; if zones provide per-zone max_water_capacity, use the minimum of those as limit.
        wi = ri.get('water')
        wj = rj.get('water')
        cap_i = 0
        cap_j = 0
        # extract capacities if present
        if isinstance(wi, dict):
            cap_i = wi.get('capacity', 0) or 0
        if isinstance(wj, dict):
            cap_j = wj.get('capacity', 0) or 0
        merged_capacity = cap_i + cap_j

        # Determine any max constraints: check 'max_water_capacity' in zone resources dict or in water dict
        max_caps = []
        # look for resource-level max in each zone
        for z in (zi, zj):
            r = z.get('resources', {}) or {}
            # resource-level overall key
            if 'max_water_capacity' in r:
                try:
                    max_caps.append(float(r['max_water_capacity']))
                except Exception:
                    pass
            # water-specific
            w = r.get('water')
            if isinstance(w, dict) and 'max_water_capacity' in w:
                try:
                    max_caps.append(float(w['max_water_capacity']))
                except Exception:
                    pass
        # if any max_caps specified, merged_capacity must be <= min(max_caps)
        if max_caps:
            if merged_capacity > min(max_caps):
                compatible = False
        else:
            # otherwise compare to global MAX_WATER_CAPACITY
            if merged_capacity > MAX_WATER_CAPACITY:
                compatible = False

        # Roads: no upper bound unless 'max_density' specified in either zone resources
        if compatible:
            ri_roads = ri.get('roads')
            rj_roads = rj.get('roads')
            di = 0
            dj = 0
            if isinstance(ri_roads, dict):
                di = ri_roads.get('density', 0) or 0
            if isinstance(rj_roads, dict):
                dj = rj_roads.get('density', 0) or 0
            merged_density = di + dj
            # check any max_density present
            max_dens = []
            for z in (zi, zj):
                r = z.get('resources', {}) or {}
                if 'max_density' in r:
                    try:
                        max_dens.append(float(r['max_density']))
                    except Exception:
                        pass
                roads = r.get('roads')
                if isinstance(roads, dict) and 'max_density' in roads:
                    try:
                        max_dens.append(float(roads['max_density']))
                    except Exception:
                        pass
            if max_dens:
                # If merged density would exceed any provided max (use min), disallow
                if merged_density > min(max_dens):
                    compatible = False

        if compatible:
            dsu.union(i, j)

    # Phase 3: aggregate per-set geometry and resources
    groups = {}
    for idx in range(n):
        root = dsu.find(idx)
        groups.setdefault(root, []).append(idx)

    merged = []
    for root in sorted(groups.keys(), key=lambda r: min(zones_sorted[i]['id'] for i in groups[r])):
        members = groups[root]
        # Deterministic order: sort members by original zone id ascending
        members_sorted = sorted(members, key=lambda i: zones_sorted[i]['id'])
        ids = [zones_sorted[i]['id'] for i in members_sorted]
        count = len(members_sorted)
        new_id = min(ids) * 100 + count

        # type aggregation
        types = [zones_sorted[i].get('type') for i in members_sorted]
        if all(t == types[0] for t in types):
            new_type = types[0]
        else:
            new_type = 'mixed'

        # coordinates: deterministic concatenation in ascending zone id order
        new_coords = []
        for i in members_sorted:
            coords = zones_sorted[i].get('coordinates') or []
            new_coords.extend(coords)

        # resources aggregation
        agg_resources: Dict[str, Any] = {}
        # collect all resource keys across members
        resource_keys = []
        for i in members_sorted:
            r = zones_sorted[i].get('resources', {}) or {}
            for k in r.keys():
                if k not in resource_keys:
                    resource_keys.append(k)

        for rk in resource_keys:
            # special handling for 'water' and 'roads'
            if rk == 'water':
                total_capacity = 0
                routes = []
                for i in members_sorted:
                    r = zones_sorted[i].get('resources', {}) or {}
                    w = r.get('water')
                    if isinstance(w, dict):
                        total_capacity += w.get('capacity', 0) or 0
                        rt = w.get('routes')
                        if isinstance(rt, list):
                            routes.extend(rt)
                agg_resources['water'] = {'capacity': total_capacity, 'routes': routes}
                # Preserve any max_water_capacity if present? Aggregation rules don't require it.
            elif rk == 'roads':
                total_density = 0
                connections = []
                for i in members_sorted:
                    r = zones_sorted[i].get('resources', {}) or {}
                    rd = r.get('roads')
                    if isinstance(rd, dict):
                        total_density += rd.get('density', 0) or 0
                        conn = rd.get('connections')
                        if isinstance(conn, list):
                            connections.extend(conn)
                agg_resources['roads'] = {'density': total_density, 'connections': connections}
            else:
                # Conservative default: numeric -> sum, list -> concat, others -> list of values
                # Determine type by inspecting values in order
                values = []
                for i in members_sorted:
                    r = zones_sorted[i].get('resources', {}) or {}
                    if rk in r:
                        values.append(r[rk])
                # If all numeric (int/float), sum
                if values and all(isinstance(v, (int, float)) for v in values):
                    agg_resources[rk] = sum(v or 0 for v in values)
                # If any lists, concatenate preserving member order
                elif any(isinstance(v, list) for v in values):
                    concatenated = []
                    for v in values:
                        if isinstance(v, list):
                            concatenated.extend(v)
                        else:
                            concatenated.append(v)
                    agg_resources[rk] = concatenated
                else:
                    # fallback: collect into list
                    agg_resources[rk] = values

        merged.append({
            'id': new_id,
            'type': new_type,
            'coordinates': new_coords,
            'resources': agg_resources
        })

    # Sort output deterministically by id ascending
    merged_sorted = sorted(merged, key=lambda z: z['id'])
    return merged_sorted

# Notes where to integrate improvements:
# - A spatial index (e.g., R-tree) would replace the O(n^2) adjacency loop for scalability.
# - A proper polygon union routine (e.g., shapely) would be used to compute geometric unions rather than coordinate concatenation.