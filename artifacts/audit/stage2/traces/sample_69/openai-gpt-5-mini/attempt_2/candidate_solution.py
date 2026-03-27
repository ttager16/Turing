def _round_half_up(n: float) -> int:
    return int(Decimal(n).quantize(0, ROUND_HALF_UP))

def optimize_traffic_signals(
    graph: Dict[str, List[str]],
    traffic_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    # Validation
    if not isinstance(graph, dict) or len(graph) == 0:
        return {}
    for k, v in graph.items():
        if not isinstance(k, str) or k == "":
            return {}
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return {}
    if not isinstance(traffic_data, list):
        return {}
    for rec in traffic_data:
        if not isinstance(rec, dict) or "intersection" not in rec:
            return {}

    # Copy graph and ensure intersections from traffic_data exist
    G = {k: list(v) for k, v in graph.items()}
    # Prepare processed records per intersection following rules
    per_inter_records = {}  # intersection -> selected record dict with metadata
    # Helper to validate a record; returns normalized record or None
    def validate_record(rec):
        inter = rec.get("intersection")
        if not isinstance(inter, str) or inter == "":
            return None
        # traffic_density optional
        td = rec.get("traffic_density", None)
        if td is not None:
            if not (isinstance(td, (int, float))):
                return None
            tdf = float(td)
            if not (0.0 <= tdf <= 1.0):
                return None
        else:
            tdf = None
        acc = rec.get("accidents", [])
        if acc is None:
            acc = []
        if not isinstance(acc, list) or not all(isinstance(x, str) for x in acc):
            return None
        pr = rec.get("priority_requests", [])
        if pr is None:
            pr = []
        if not isinstance(pr, list) or not all(isinstance(x, str) for x in pr):
            return None
        return {"intersection": inter, "traffic_density": tdf, "accidents": list(acc), "priority_requests": list(pr)}

    # Iterate traffic_data in order, selecting per rules (keep lowest preliminary later)
    # But preliminary depends on traffic_density and lists; compute preliminary per record now
    def preliminary_from_record(rec):
        # rec is validated normalized record
        base = 20
        td = rec["traffic_density"]
        if td is None:
            return None  # indicates no direct data
        total = base + 70 * td
        total = float(Decimal(total).quantize(Decimal('0.0000001')))  # keep float
        if "EMERGENCY" in rec["priority_requests"]:
            total += 10
        # rounding half-up of the addition 70*td is applied by rounding the added term per instruction:
        # The instruction: Add "70 × traffic_density", rounded half-up. So we should round that component.
        add = _round_half_up(70 * td)
        total = 20 + add
        if "EMERGENCY" in rec["priority_requests"]:
            total += 10
        if td > 0.7 and "LANE_OUTAGE" in rec["accidents"]:
            total = total // 2
        return float(total)

    # Process records
    for raw in traffic_data:
        rec = validate_record(raw)
        if rec is None:
            continue
        inter = rec["intersection"]
        if inter not in G:
            G[inter] = []
        prelim = preliminary_from_record(rec)
        # For selection among multiple records: keep one with lowest preliminary value.
        # If ties, prefer one containing EMERGENCY, if still tied, use last record.
        existing = per_inter_records.get(inter)
        if existing is None:
            per_inter_records[inter] = {"rec": rec, "prelim": prelim}
        else:
            ex_pre = existing["prelim"]
            # None prelim means no traffic_density; per rules, such records count as "without traffic data"
            # and selection rule applies comparing preliminary; treat None as special: a record with real prelim is considered lower? 
            # The spec: "If multiple records exist for the same intersection, compute each record’s preliminary timing and keep the one with the lowest value."
            # Records without traffic_density don't have preliminary; treat them as not comparable: ignore them unless all are without data.
            if ex_pre is None and prelim is None:
                # tie: prefer one with EMERGENCY, then last -> so current overrides if has EMERGENCY or if previous lacks it; else override due to last
                ex_em = "EMERGENCY" in existing["rec"]["priority_requests"]
                cur_em = "EMERGENCY" in rec["priority_requests"]
                if cur_em and not ex_em:
                    per_inter_records[inter] = {"rec": rec, "prelim": prelim}
                elif cur_em == ex_em:
                    per_inter_records[inter] = {"rec": rec, "prelim": prelim}
            elif ex_pre is None and prelim is not None:
                # current has prelim numeric, previous didn't -> choose the numeric (has a concrete value)
                per_inter_records[inter] = {"rec": rec, "prelim": prelim}
            elif ex_pre is not None and prelim is None:
                # keep existing
                continue
            else:
                # both numeric: choose lower; if tie prefer EMERGENCY; if still tie keep last (current)
                if prelim < ex_pre:
                    per_inter_records[inter] = {"rec": rec, "prelim": prelim}
                elif prelim == ex_pre:
                    ex_em = "EMERGENCY" in existing["rec"]["priority_requests"]
                    cur_em = "EMERGENCY" in rec["priority_requests"]
                    if cur_em and not ex_em:
                        per_inter_records[inter] = {"rec": rec, "prelim": prelim}
                    else:
                        # if tie and either both have same EMERGENCY status, prefer last => current
                        per_inter_records[inter] = {"rec": rec, "prelim": prelim}

    # Now compute preliminary durations per intersection:
    prelim_map = {}  # intersection -> preliminary float (before normalization)
    # First set for those with selected records having traffic_density defined
    for inter, data in per_inter_records.items():
        rec = data["rec"]
        prelim = data["prelim"]
        if prelim is not None:
            prelim_map[inter] = float(prelim)
    # We'll need to compute for intersections with no traffic data using neighbor-average rule (half-up average of already-computed outgoing neighbors). 
    # Iteratively fill until no change or all assigned. Start by adding intersections from G keys union traffic_data intersections
    all_keys = set(G.keys()) | set(per_inter_records.keys())
    # Ensure keys for any traffic_data entries that had only invalid records? They were ignored. But spec said intersections mentioned in traffic_data but not present in graph are added; we did that when validated records.
    # For intersections that had selected record but traffic_density None, they count as "without traffic data".
    # Initialize set of unassigned
    assigned = set(prelim_map.keys())
    unassigned = set(all_keys) - assigned
    # For those unassigned that had selected record but no traffic_density, they still treated as without traffic data.
    # Iteratively compute neighbor averages using outgoing neighbors' already-computed preliminary durations
    changed = True
    while changed:
        changed = False
        to_remove = set()
        for inter in list(unassigned):
            outs = G.get(inter, [])
            # only consider outgoing neighbors that already have preliminary in prelim_map
            neigh_values = [prelim_map[n] for n in outs if n in prelim_map]
            if neigh_values:
                avg = sum(neigh_values) / len(neigh_values)
                val = float(_round_half_up(avg))
                prelim_map[inter] = float(val)
                to_remove.add(inter)
                changed = True
        unassigned -= to_remove
    # For any remaining unassigned, set to 45
    for inter in list(unassigned):
        prelim_map[inter] = 45.0

    # Now ensure all keys present
    for inter in all_keys:
        if inter not in prelim_map:
            prelim_map[inter] = 45.0

    # Normalization: scale all durations so their mean (before rounding) equals 45
    values = list(prelim_map.values())
    if len(values) == 0:
        return {}
    current_mean = sum(values) / len(values)
    if current_mean == 0:
        scale = 1.0
    else:
        scale = 45.0 / current_mean
    scaled = {}
    for k, v in prelim_map.items():
        scaled_val = v * scale
        scaled[k] = scaled_val

    # Then round half-up and clamp 20-90
    final = {}
    for k, v in scaled.items():
        rv = _round_half_up(v)
        if rv < 20:
            rv = 20
        if rv > 90:
            rv = 90
        final[k] = rv

    # Determine overflow per rules
    result = {}
    # Need traffic_density per intersection if available
    traffic_density_map = {}
    for inter, data in per_inter_records.items():
        td = data["rec"]["traffic_density"]
        traffic_density_map[inter] = td  # may be None

    for inter in sorted(final.keys()):
        timing = final[inter]
        td = traffic_density_map.get(inter, None)
        overflow = False
        if timing < 30:
            overflow = True
        else:
            if td is not None:
                if td > 0.75:
                    # need to check EMERGENCY presence in selected record
                    rec = per_inter_records.get(inter, {}).get("rec")
                    has_em = False
                    if rec:
                        has_em = "EMERGENCY" in rec.get("priority_requests", [])
                    if not has_em:
                        overflow = True
        result[inter] = {"signal_timing": timing, "overflow_indicator": overflow}
    return result