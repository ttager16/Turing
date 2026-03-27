def optimize_supply_chain(resources: list, demand_forecasts: list, disruption_factors: list) -> dict:
    # Build center lookup
    centers = {}
    for r in resources:
        centers[r['center_id']] = {
            'center_id': r['center_id'],
            'location': r['location'],
            'inventory': int(r['inventory']),
            'capacity': int(r['capacity']),
            'connected': list(r.get('connected_centers', []))
        }
    # Map location to center_id (assume one center per location as sample implies)
    loc_to_center = {}
    for c in centers.values():
        loc_to_center[c['location']] = c['center_id']
    # Compute total severity per center
    severity = defaultdict(float)
    for d in disruption_factors:
        s = float(d.get('severity', 0.0))
        for cid in d.get('affected_centers', []):
            severity[cid] += s
    for cid in severity:
        if severity[cid] > 1.0:
            severity[cid] = 1.0
    # Effective inventory after disruption (integer)
    effective_inv = {}
    for cid, c in centers.items():
        eff = int(round(c['inventory'] * (1.0 - severity.get(cid, 0.0))))
        if eff < 0:
            eff = 0
        effective_inv[cid] = eff
    # Compute total forecast per location and preserve product-level forecasts per location
    loc_forecasts = defaultdict(int)
    loc_product_forecasts = defaultdict(list)  # location -> list of (priority, product_id, forecast)
    for f in demand_forecasts:
        loc = f['location']
        qty = int(f['forecast'])
        loc_forecasts[loc] += qty
        loc_product_forecasts[loc].append((int(f.get('priority', 0)), f['product_id'], qty))
    # Determine surplus and deficit per center (aggregated)
    surplus = {}
    deficit = {}
    for cid, c in centers.items():
        loc = c['location']
        total_forecast = loc_forecasts.get(loc, 0)
        inv = effective_inv.get(cid, 0)
        diff = inv - total_forecast
        if diff > 0:
            surplus[cid] = diff
        elif diff < 0:
            deficit[cid] = -diff
    # Precompute adjacency including one-hop via single intermediate
    adjacency = {}
    for cid, c in centers.items():
        direct = set(c['connected'])
        adjacency[cid] = {'direct': direct, 'onehop': {}}
    # For one-hop, build paths cid -> intermediate -> target
    for a in centers:
        for mid in adjacency[a]['direct']:
            if mid not in centers:
                continue
            for b in centers[mid]['connected']:
                if b == a: continue
                # allow if not directly connected already; still consider both
                # store path distance as abs diff of center_ids sum maybe
                adjacency[a]['onehop'][b] = mid
    # Prepare list of deficit centers with products sorted by priority
    # For each deficit center, expand product-level demands by priority ascending
    deficit_requests = []  # entries: (to_center_id, priority, product_id, qty)
    for loc, plist in loc_product_forecasts.items():
        to_cid = loc_to_center.get(loc)
        if to_cid is None: continue
        # sort by priority ascending (lower number = higher priority)
        plist_sorted = sorted(plist, key=lambda x: x[0])
        for prio, pid, qty in plist_sorted:
            # Only consider requests if center has aggregate deficit
            if to_cid in deficit:
                deficit_requests.append((to_cid, prio, pid, qty))
    # Deterministic processing: process deficit_requests in order of center id ascending then priority
    deficit_requests.sort(key=lambda x: (x[0], x[1], x[2]))
    routes = []
    # Helper to find candidate senders for a given receiver
    def candidate_senders(receiver):
        candidates = []
        for sid, s_amt in surplus.items():
            if s_amt <= 0:
                continue
            # direct?
            if receiver in adjacency[sid]['direct']:
                dist = abs(sid - receiver)
                hop = 0
                candidates.append((sid, s_amt, hop, dist, [sid, receiver]))
            # one-hop?
            mid = adjacency[sid]['onehop'].get(receiver)
            if mid is not None:
                dist = abs(sid - receiver)
                hop = 1
                candidates.append((sid, s_amt, hop, dist, [sid, mid, receiver]))
        # Sort by: higher surplus, smaller center_id diff (dist), (hop prefer 0? not specified so distance covers), then sender id
        candidates.sort(key=lambda x: (-x[1], x[3], x[0]))
        return candidates
    # Process each product request, allocate from candidates until fulfilled or no surplus
    for to_cid, prio, pid, req_qty in deficit_requests:
        remaining = req_qty
        # Also cap by aggregate deficit remaining
        agg_def = deficit.get(to_cid, 0)
        if agg_def <= 0:
            continue
        remaining = min(remaining, agg_def)
        # Find senders and allocate
        while remaining > 0:
            cand = candidate_senders(to_cid)
            if not cand:
                break
            sender_id, s_amt, hop, dist, path = cand[0]
            transfer = min(remaining, s_amt)
            if transfer <= 0:
                break
            # Ensure sender not exceeding capacity? transfers reduce sender inventory only, capacity applies at receiver end when adding
            # Also ensure receiver capacity not exceeded
            receiver_capacity = centers[to_cid]['capacity']
            receiver_current = effective_inv.get(to_cid, 0)
            # Sum incoming already planned to receiver
            incoming_planned = sum(r['quantity'] for r in routes if r['to'] == centers[to_cid]['location'])
            avail_space = receiver_capacity - (receiver_current + incoming_planned)
            if avail_space <= 0:
                break
            transfer = min(transfer, avail_space)
            if transfer <= 0:
                break
            # Make integer
            transfer = int(transfer)
            # Record route (from location name)
            routes.append({
                'from': centers[sender_id]['location'],
                'to': centers[to_cid]['location'],
                'product_id': pid,
                'quantity': transfer
            })
            # Update surplus and effective_inv and deficit
            surplus[sender_id] -= transfer
            effective_inv[sender_id] -= transfer
            if surplus[sender_id] <= 0:
                surplus.pop(sender_id, None)
            effective_inv[to_cid] = effective_inv.get(to_cid, 0) + transfer
            deficit[to_cid] -= transfer
            if deficit[to_cid] <= 0:
                deficit.pop(to_cid, None)
            remaining -= transfer
    # After processing, ensure no negative or over-capacity
    inventory_adjustments = []
    for cid in sorted(centers.keys()):
        new_inv = effective_inv.get(cid, 0)
        if new_inv < 0:
            new_inv = 0
        if new_inv > centers[cid]['capacity']:
            new_inv = centers[cid]['capacity']
        inventory_adjustments.append({'center_id': cid, 'new_inventory': int(new_inv)})
    return {'routes': routes, 'inventory_adjustments': inventory_adjustments}