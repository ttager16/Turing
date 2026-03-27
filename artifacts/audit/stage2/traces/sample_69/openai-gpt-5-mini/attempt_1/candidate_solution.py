def _round_half_up(n: float) -> int:
    return int(Decimal(n).quantize(0, rounding=ROUND_HALF_UP))

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

    # Prepare combined node set
    nodes = dict(graph)  # copy
    # ensure outgoing lists are copies
    for k in list(nodes.keys()):
        nodes[k] = list(nodes[k])

    # Parse traffic_data, validate records, group by intersection keeping preliminary rules
    # For each record compute preliminary duration per rule, but we need neighbor-average fallback for missing data.
    # First, separate records: valid records with fields (but traffic_density optional)
    records_by_node = {}
    for rec in traffic_data:
        if not isinstance(rec, dict):
            continue
        inter = rec.get("intersection")
        if not isinstance(inter, str) or inter == "":
            continue
        # normalize fields
        td = rec.get("traffic_density", None)
        if td is not None:
            try:
                td = float(td)
            except Exception:
                td = None
        acc = rec.get("accidents", [])
        pr = rec.get("priority_requests", [])
        if acc is None:
            acc = []
        if pr is None:
            pr = []
        if not isinstance(acc, list) or not all(isinstance(x, str) for x in acc):
            acc = None  # mark malformed
        if not isinstance(pr, list) or not all(isinstance(x, str) for x in pr):
            pr = None
        # validate traffic_density range
        if td is not None and not (0.0 <= td <= 1.0):
            td = None  # treat as missing per instructions (malformed record ignored? spec: malformed records ignored, but here we can ignore only this record if any field wrong)
        # If accidents/pr wrong types, treat record as malformed => skip record
        if acc is None or pr is None:
            continue
        # Record considered valid (with possibly missing traffic_density)
        records_by_node.setdefault(inter, []).append({
            "traffic_density": td,
            "accidents": list(acc),
            "priority_requests": list(pr),
            "raw": rec
        })
        if inter not in nodes:
            nodes[inter] = []

    # We'll compute preliminary durations for nodes that have at least one record with traffic_density present.
    prelim = {}  # node -> chosen preliminary duration (float)
    # For nodes with multiple records: compute each record's preliminary timing and keep lowest; tie-break EMERGENCY present; then last record.
    for node, recs in records_by_node.items():
        # If any rec has traffic_density is None, that rec is treated as "no traffic data" and should not produce preliminary duration; spec says missing traffic_density -> no traffic data (neighbor-average rule)
        rec_prelims = []
        for rec in recs:
            td = rec["traffic_density"]
            if td is None:
                rec_prelims.append(None)
                continue
            total = 20.0
            total += 70.0 * td
            if any(r == "EMERGENCY" for r in rec["priority_requests"]):
                total += 10.0
            # If traffic_density > 0.7 and LANE_OUTAGE reported, halve total using floor division after emergency bonus
            if td > 0.7 and any(a == "LANE_OUTAGE" for a in rec["accidents"]):
                # halve using floor division (integer division). It says halve the total (after emergency bonus) using floor division.
                total = math.floor(total / 2)
            rec_prelims.append(total)
        # Choose per rules: keep record with lowest value among those that produced a value; if tied, prefer one containing EMERGENCY; if still tied, use last record.
        candidates = []
        for idx, val in enumerate(rec_prelims):
            if val is not None:
                candidates.append((val, idx, recs[idx]))
        if candidates:
            # find min value
            minval = min(c[0] for c in candidates)
            tied = [c for c in candidates if c[0] == minval]
            if len(tied) == 1:
                chosen = tied[0]
            else:
                # prefer one containing EMERGENCY
                with_em = [t for t in tied if any(r == "EMERGENCY" for r in t[2]["priority_requests"])]
                if with_em:
                    # if multiple, choose last among them
                    chosen = with_em[-1]
                else:
                    chosen = tied[-1]
            prelim[node] = float(chosen[0])

    # For nodes that exist but have no traffic data or whose records lacked traffic_density, use neighbor-average rule.
    # We may need iterative computation because neighbor averages depend on outgoing neighbors' preliminary durations.
    # Approach: initialize known set = prelim keys. For others that have at least one record but no td -> they count as "without traffic data". For nodes with no records also are without data.
    all_nodes = set(nodes.keys())
    known = set(prelim.keys())
    unknown = all_nodes - known

    # For unknown nodes, we need average of already-computed outgoing neighbors (half-up). If none known or no outgoing edges, use 45s.
    # Since neighbor dependencies could chain, iterate until no change by computing those with any outgoing neighbor known.
    prelim_values = dict(prelim)
    changed = True
    while changed:
        changed = False
        for node in list(unknown):
            outs = nodes.get(node, [])
            # compute average of already-computed outgoing neighbors
            vals = [prelim_values[nbr] for nbr in outs if nbr in prelim_values]
            if vals:
                avg = sum(vals) / len(vals)
                val = float(_round_half_up(avg))
                prelim_values[node] = float(val)
                known.add(node)
                unknown.remove(node)
                changed = True
        # stop if no progress
    # Any remaining unknown nodes -> set to 45
    for node in list(unknown):
        prelim_values[node] = 45.0

    # Now union of graph keys and traffic-data intersections already accounted in nodes/all_nodes
    final_nodes = sorted(all_nodes)

    # Normalization: scale all durations so their mean (before rounding) equals 45 s.
    durations = [prelim_values[n] for n in final_nodes]
    if len(durations) == 0:
        return {}
    current_mean = sum(durations) / len(durations)
    if current_mean == 0:
        scale = 1.0
    else:
        scale = 45.0 / current_mean
    scaled = [d * scale for d in durations]

    # Round half-up and clamp 20-90
    final_vals = {}
    for node, val in zip(final_nodes, scaled):
        r = _round_half_up(val)
        if r < 20:
            r = 20
        if r > 90:
            r = 90
        final_vals[node] = r

    # Determine overflow indicator per node:
    result = {}
    # We need traffic_density presence per node and whether EMERGENCY present
    # For nodes with multiple records, traffic_density may be missing in some; spec: "Intersections lacking traffic data consider only the first condition." I interpret lacking traffic data means no record with traffic_density.
    td_info = {}
    emergency_info = {}
    for node in final_nodes:
        recs = records_by_node.get(node, [])
        has_td = False
        max_td = None
        has_em = False
        for rec in recs:
            td = rec["traffic_density"]
            if td is not None:
                has_td = True
                max_td = td  # last seen with td; but spec doesn't prescribe aggregation; we just need whether >0.75
            if any(r == "EMERGENCY" for r in rec["priority_requests"]):
                has_em = True
        td_info[node] = max_td if has_td else None
        emergency_info[node] = has_em

    for node in final_nodes:
        timing = final_vals[node]
        overflow = False
        if timing < 30:
            overflow = True
        td = td_info.get(node)
        if td is not None:
            if td > 0.75 and not emergency_info.get(node, False):
                overflow = True
        result[node] = {"signal_timing": timing, "overflow_indicator": bool(overflow)}
    return result