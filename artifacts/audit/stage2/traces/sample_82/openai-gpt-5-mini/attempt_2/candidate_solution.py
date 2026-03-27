def build_adaptive_sensor_list(
    data_stream: List[Dict[str, Any]],
    invalidations: List[int] = []
) -> Dict[str, Any]:
    lock = threading.Lock()
    # storage
    zones = {}  # zone -> {types: {type: {'values': [(idx,val,valid)], 'hot': (idx,val) or None}}}
    path_index = {}  # sensor key -> base type node id
    # process inserts
    with lock:
        for idx, ev in enumerate(data_stream):
            sensor = ev.get("sensor")
            val = float(ev.get("value"))
            if not sensor or "_" not in sensor:
                continue
            typ, zone = sensor.split("_", 1)
            zone_id = f"zone:{zone}"
            type_id = f"{zone_id}/type:{typ}"
            path_index[sensor] = type_id
            if zone not in zones:
                zones[zone] = {'types': {}}
            types = zones[zone]['types']
            if typ not in types:
                types[typ] = {'values': [], 'hot': None}
            entry = types[typ]
            entry['values'].append([idx, val, True])
            # promotion rule: when count reaches >=2, promote most recently inserted reading
            # count of valid readings (before invalidations) - but promotions happen online as events arrive
            valid_count = sum(1 for _i, _v, ok in entry['values'] if ok)
            if valid_count >= 2:
                # most recent inserted reading is last in list
                last_idx, last_val, last_ok = entry['values'][-1]
                entry['hot'] = (last_idx, last_val)
    # apply invalidations (partial rollback)
    inv_set = set(invalidations)
    with lock:
        for zone, zdata in zones.items():
            for typ, entry in zdata['types'].items():
                # mark invalids
                for rec in entry['values']:
                    if rec[0] in inv_set:
                        rec[2] = False
                # recompute hot: it's the latest valid reading if any and if count>=2 originally would have created hot
                # Rule: hot segment duplicates only the latest reading when event count reaches >=2.
                # After invalidation, hot should be latest valid or deleted.
                # Determine latest valid by max idx among valid recs
                valid_recs = [r for r in entry['values'] if r[2]]
                if valid_recs:
                    latest = max(valid_recs, key=lambda r: r[0])
                    # hot exists only if at any point there were >=2 valid insertions? The spec: hot deleted if none.
                    # We'll create hot if there is at least one valid and original promotion condition met:
                    # But sample shows hot exists after rollback if still has at least one valid and previous count>=2.
                    # Simpler: if there exists at least one valid and total historical valid count >=2 at some time.
                    # We don't track historical; but promotion is triggered when valid_count reached >=2 during insertion.
                    # We can infer: if entry ever had length >=2 (including invalidated ones) then hot was created.
                    if len(entry['values']) >= 2:
                        entry['hot'] = (latest[0], latest[1])
                    else:
                        entry['hot'] = None
                else:
                    entry['hot'] = None
    # build traversal order: root -> zones lex -> types lex -> hot immediately after base
    linked_order = ["root"]
    zone_names = sorted(zones.keys())
    for zn in zone_names:
        zid = f"zone:{zn}"
        linked_order.append(zid)
        type_names = sorted(zones[zn]['types'].keys())
        for tn in type_names:
            tid = f"{zid}/type:{tn}"
            linked_order.append(tid)
            if zones[zn]['types'][tn].get('hot') is not None:
                linked_order.append(f"{tid}*")
    # next pointers
    next_pointer_of = {}
    for i, node in enumerate(linked_order):
        next_pointer_of[node] = linked_order[i+1] if i+1 < len(linked_order) else None
    # segment_stats and leaf_values
    segment_stats = {}
    leaf_values = {}
    for zn in zone_names:
        zid = f"zone:{zn}"
        for tn in sorted(zones[zn]['types'].keys()):
            tid = f"{zid}/type:{tn}"
            entry = zones[zn]['types'][tn]
            vals = [r[1] for r in entry['values'] if r[2]]
            leaf_values[tid] = vals.copy()
            if vals:
                cnt = len(vals)
                s = sum(vals)
                mn = min(vals)
                mx = max(vals)
                avg = round(s / cnt + 1e-12, 3)
                segment_stats[tid] = {"count": cnt, "sum": s, "min": mn, "max": mx, "avg": float(f"{avg:.3f}")}
            # hot
            if entry.get('hot') is not None:
                hv = entry['hot'][1]
                segment_stats[f"{tid}*"] = {"latest_value": hv}
    # path_index should map each sensor key to its base type node id (only unique keys present)
    # Ensure path_index only contains unique sensor keys (latest mapping is fine)
    return {
        "linked_order": linked_order,
        "next_pointer_of": next_pointer_of,
        "segment_stats": segment_stats,
        "path_index": path_index,
        "leaf_values": leaf_values
    }