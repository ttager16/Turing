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

    # Compute total severity per center
    severity_map = defaultdict(float)
    for d in disruption_factors:
        sev = float(d.get('severity', 0.0))
        for c in d.get('affected_centers', []):
            severity_map[c] += sev
    for c in severity_map:
        if severity_map[c] > 1.0:
            severity_map[c] = 1.0

    # Effective inventory after disruptions (integer)
    effective_inv = {}
    for cid, info in centers.items():
        totsev = severity_map.get(cid, 0.0)
        eff = int(info['inventory'] * (1.0 - totsev))
        if eff < 0:
            eff = 0
        # Cap to capacity though disruption reduces only available, capacity still upper bound post transfers
        effective_inv[cid] = eff

    # Compute total forecast per location and also keep product-level forecasts per location and priority
    forecast_by_location = defaultdict(int)
    forecasts_by_location_product = defaultdict(list)  # location -> list of (product_id, forecast, priority)
    for f in demand_forecasts:
        loc = f['location']
        qty = int(f['forecast'])
        forecast_by_location[loc] += qty
        forecasts_by_location_product[loc].append({'product_id': f['product_id'], 'forecast': int(f['forecast']), 'priority': int(f.get('priority', 0))})

    # Map location to center_id(s). Assume one center per location usually, but support multiple.
    location_to_centers = defaultdict(list)
    for cid, info in centers.items():
        location_to_centers[info['location']].append(cid)

    # Compute surplus/deficit per center (aggregate across products)
    surplus_centers = {}  # cid -> surplus int
    deficit_centers = {}  # cid -> deficit int
    for cid, info in centers.items():
        loc = info['location']
        total_forecast = forecast_by_location.get(loc, 0)
        eff = effective_inv.get(cid, 0)
        diff = eff - total_forecast
        if diff > 0:
            surplus_centers[cid] = diff
        elif diff < 0:
            deficit_centers[cid] = -diff
        else:
            pass

    # Build adjacency for searching one-hop paths
    adjacency = {}
    for cid, info in centers.items():
        adjacency[cid] = set(info['connected'])

    # Helper to find possible senders for a receiver cid (direct or via one-hop)
    def possible_senders(receiver_cid):
        candidates = []
        # direct neighbors that have surplus
        for sender in adjacency.get(receiver_cid, []):
            if sender in surplus_centers and surplus_centers[sender] > 0:
                candidates.append( (sender, [sender, receiver_cid]) )
        # Also a sender could be the receiver itself? No.
        # one-hop via intermediate: sender -> inter -> receiver where inter is connected to both
        for inter in adjacency.get(receiver_cid, []):
            for sender in adjacency.get(inter, []):
                if sender == receiver_cid or sender == inter:
                    continue
                if sender in surplus_centers and surplus_centers[sender] > 0 and inter in adjacency.get(sender, []):
                    # ensure path sender - inter - receiver (connected)
                    candidates.append( (sender, [sender, inter, receiver_cid]) )
        # Deduplicate by sender keeping shortest path (min center_id distance if needed)
        best = {}
        for sender, path in candidates:
            dist = abs(sender - receiver_cid)
            if sender not in best or (len(path) < len(best[sender][1])) or (len(path)==len(best[sender][1]) and dist < best[sender][0]):
                best[sender] = (dist, path)
        result = [(s, best[s][1]) for s in best]
        return result  # list of (sender_cid, path)

    # Prepare product-level needs per center: for each center, a list of product demands sorted by priority ascending
    needs_by_center = {}
    for cid, info in centers.items():
        loc = info['location']
        prods = forecasts_by_location_product.get(loc, [])
        # copy to mutable dict of remaining per product
        prod_map = {}
        for p in prods:
            key = p['product_id']
            prod_map.setdefault(key, 0)
            prod_map[key] += int(p['forecast'])
        # Expand into list of items with priority: we need priority ordering
        items = []
        # determine priority per product by taking minimum priority among entries
        prio_map = {}
        for p in prods:
            key = p['product_id']
            prio_map[key] = min(prio_map.get(key, p['priority']), p['priority'])
        for pid, qty in prod_map.items():
            items.append({'product_id': pid, 'quantity': qty, 'priority': prio_map.get(pid, 0)})
        # sort by priority ascending, then product_id for determinism
        items.sort(key=lambda x: (x['priority'], str(x['product_id'])))
        if items:
            needs_by_center[cid] = items

    # Prepare routes list
    routes = []

    # Process deficits in deterministic order: centers with larger deficit first? Spec says when multiple candidate senders exist prioritize senders; for processing order choose increasing center_id to be deterministic.
    # We'll process deficits sorted by (deficit desc, center_id asc) to try to satisfy big needs first.
    deficit_list = sorted(deficit_centers.items(), key=lambda x: (-x[1], x[0]))

    for recv_cid, recv_deficit in deficit_list:
        if recv_deficit <= 0:
            continue
        # For its product-level needs
        needs = needs_by_center.get(recv_cid, [])
        # iterate through needs in priority order
        for need in needs:
            pid = need['product_id']
            want = need['quantity']
            if want <= 0:
                continue
            remaining_need = want
            # while still need and there exist senders
            while remaining_need > 0:
                senders = possible_senders(recv_cid)
                if not senders:
                    break
                # Filter senders with positive surplus
                filtered = []
                for s, path in senders:
                    avail = surplus_centers.get(s, 0)
                    if avail > 0:
                        filtered.append( (s, path, avail) )
                if not filtered:
                    break
                # Sort senders by: higher surplus, then smaller abs center_id difference
                filtered.sort(key=lambda x: (-x[2], abs(x[0]-recv_cid), x[0]))
                sender_cid, path, avail = filtered[0]
                # Determine transfer amount: min(avail, remaining_need, sender cannot cause receiver to exceed capacity)
                recv_capacity = centers[recv_cid]['capacity']
                # compute current receiver inventory = effective_inv + inbound already assigned to this receiver (sum of routes to this location)
                inbound_to_recv = 0
                for r in routes:
                    # map names to location; routes store from/to as location names
                    if r['to'] == centers[recv_cid]['location']:
                        inbound_to_recv += int(r['quantity'])
                current_recv_inv = effective_inv.get(recv_cid, 0) + inbound_to_recv
                max_recv_can_take = max(0, recv_capacity - current_recv_inv)
                transfer_qty = min(avail, remaining_need, max_recv_can_take)
                if transfer_qty <= 0:
                    # can't transfer due to capacity
                    break
                # perform transfer: record route using location names
                routes.append({
                    'from': centers[sender_cid]['location'],
                    'to': centers[recv_cid]['location'],
                    'product_id': pid,
                    'quantity': int(transfer_qty)
                })
                # update surplus and deficits and remaining_need
                surplus_centers[sender_cid] -= transfer_qty
                if surplus_centers[sender_cid] <= 0:
                    del surplus_centers[sender_cid]
                remaining_need -= transfer_qty
                deficit_centers[recv_cid] -= transfer_qty
                if deficit_centers[recv_cid] <= 0:
                    deficit_centers.pop(recv_cid, None)
                # Continue until filled or no senders

            # after attempting this product, reduce the need quantity to remaining_need
            need['quantity'] = remaining_need
            if remaining_need <= 0:
                # satisfied this product
                pass

    # After all transfers, compute new inventory per center: effective_inv + inbound - outbound, bounded 0..capacity
    inbound = defaultdict(int)
    outbound = defaultdict(int)
    # Map location to all center_ids (if multiple centers share location, distribute outbound/inbound proportionally? Problem assumes one-to-one; we'll attribute to centers by center_id with that location and use their IDs deterministically: if multiple, choose smallest center_id.)
    # Build location -> single representative center id (smallest id)
    loc_to_center = {}
    for cid, info in centers.items():
        loc = info['location']
        if loc not in loc_to_center or cid < loc_to_center[loc]:
            loc_to_center[loc] = cid

    for r in routes:
        from_loc = r['from']
        to_loc = r['to']
        qty = int(r['quantity'])
        from_cid = loc_to_center.get(from_loc)
        to_cid = loc_to_center.get(to_loc)
        if from_cid is not None:
            outbound[from_cid] += qty
        if to_cid is not None:
            inbound[to_cid] += qty

    inventory_adjustments = []
    for cid, info in centers.items():
        new_inv = effective_inv.get(cid, 0) + inbound.get(cid, 0) - outbound.get(cid, 0)
        if new_inv < 0:
            new_inv = 0
        if new_inv > info['capacity']:
            new_inv = info['capacity']
        inventory_adjustments.append({'center_id': cid, 'new_inventory': int(new_inv)})

    # Sort outputs deterministically
    routes.sort(key=lambda x: (x['from'], x['to'], x['product_id'], x['quantity']))
    inventory_adjustments.sort(key=lambda x: x['center_id'])

    return {'routes': routes, 'inventory_adjustments': inventory_adjustments}