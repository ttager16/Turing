# main.py
from typing import List, Dict, Any, Tuple
from collections import defaultdict

def optimize_supply_chain(resources: List[Dict[str, Any]],
                          demand_forecasts: List[Dict[str, Any]],
                          disruption_factors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute optimal transfer routes and updated inventories after disruptions.

    Deterministic Rules implemented (as per prompt):
    1) For each center, compute total severity = sum of severities of all disruptions that include that center,
       capped at 1.0. Effective inventory = floor(inventory * (1 - total_severity)).
    2) Aggregate total forecast per location (sum of all product forecasts at that location).
    3) Compute center-level surplus/deficit against the location's total forecast by distributing the
       location total forecast to centers in that location (ascending center_id), then compare to effective inventory:
         - surplus = max(0, effective_inventory - assigned_local_forecast)
         - deficit = max(0, assigned_local_forecast - effective_inventory)
       Note: demand is NOT “consumed” from inventory; it only guides transfers that minimize imbalance.
    4) Transfers are allowed only if sender and receiver are directly connected OR have a one-hop path through
       any common neighbor. We never use paths longer than one intermediate.
    5) Sender choice priority for each receiver deficit unit is:
         (a) higher sender surplus (desc),
         (b) smaller |sender.center_id - receiver.center_id|,
         (c) lower demand priority number (applied when assigning product IDs for the receiver’s location).
       We apply these deterministically with integer quantities.
    6) Capacity safety: receiver final inventory cannot exceed capacity. Sender cannot transfer more than its surplus.
    7) Output routes are aggregated by (from_location, to_location, product_id) with integer quantities.
       inventory_adjustments are the real inventories after transfers (original ± net shipped), then clamped to [0, capacity].
    Time complexity: O(N^2) where N = number of centers.
    """

    # --- Normalize & index centers ---
    centers: Dict[int, Dict[str, Any]] = {}
    loc_to_cids: Dict[str, List[int]] = defaultdict(list)
    neighbors: Dict[int, set] = {}
    for c in resources:
        cid = int(c["center_id"])
        inv = int(c["inventory"])
        cap = int(c["capacity"])
        loc = c["location"]
        neigh = set(int(x) for x in c.get("connected_centers", []))
        centers[cid] = {
            "center_id": cid,
            "location": loc,
            "inventory": inv,
            "capacity": cap,
            "neighbors": neigh
        }
        loc_to_cids[loc].append(cid)
        neighbors[cid] = neigh

    for loc in loc_to_cids:
        loc_to_cids[loc].sort()

    # --- Sum severities per center, capped at 1.0 ---
    total_sev: Dict[int, float] = defaultdict(float)
    for d in disruption_factors:
        sev = float(d.get("severity", 0.0))
        for cid in d.get("affected_centers", []):
            total_sev[int(cid)] += sev
    for cid in total_sev:
        if total_sev[cid] > 1.0:
            total_sev[cid] = 1.0

    # --- Effective inventory per center ---
    eff_inv: Dict[int, int] = {}
    for cid, info in centers.items():
        sev = total_sev.get(cid, 0.0)
        eff = int((info["inventory"]) * (1.0 - sev))
        if eff < 0:
            eff = 0
        eff_inv[cid] = eff

    # --- Total forecast per location + per-location product ordering (by priority then input order) ---
    total_forecast_by_loc: Dict[str, int] = defaultdict(int)
    products_by_loc: Dict[str, List[Tuple[int, str, int]]] = defaultdict(list)
    # store tuples: (priority, product_id, forecast)
    for i, d in enumerate(demand_forecasts):
        loc = d["location"]
        pr = int(d["priority"])
        fc = int(d["forecast"])
        pid = d["product_id"]
        total_forecast_by_loc[loc] += fc
        # keep stable order by (priority, original index)
        products_by_loc[loc].append((pr, pid, fc, i))
    for loc in products_by_loc:
        products_by_loc[loc].sort(key=lambda x: (x[0], x[3]))  # by priority, then input order

    # --- Distribute location total forecast to centers in that location (ascending center_id) deterministically ---
    assigned_local: Dict[int, int] = {cid: 0 for cid in centers}
    for loc, cids in loc_to_cids.items():
        remaining = total_forecast_by_loc.get(loc, 0)
        for cid in cids:
            if remaining <= 0:
                break
            # split greedily in center_id order; last center takes the remainder
            take = min(remaining, eff_inv[cid] + remaining)  # any upper bound; we just assign remaining across centers
            assigned_local[cid] += take
            remaining -= take
        # if remaining > 0 (no centers in that loc), it stays as unmet local demand at that location => deficits later

    # --- Compute surplus/deficit per center against assigned_local vs effective inventory ---
    surplus: Dict[int, int] = {}
    deficit: Dict[int, int] = {}
    for cid in centers:
        s = eff_inv[cid] - assigned_local[cid]
        if s > 0:
            surplus[cid] = s
            deficit[cid] = 0
        else:
            surplus[cid] = 0
            deficit[cid] = -s

    # --- Precompute one-hop reachability (direct or via one intermediate) ---
    def reachable_in_one_hop_or_less(a: int, b: int) -> bool:
        if a == b:
            return True
        if b in neighbors[a]:
            return True
        # one intermediate
        # small optimization: iterate smaller degree set first
        for mid in (neighbors[a] if len(neighbors[a]) < len(neighbors[b]) else neighbors[b]):
            if mid in neighbors[a] and b in neighbors[mid]:
                return True
        return False

    # --- Receiver ordering: handle locations with deficits first (sum of center deficits in that location) ---
    loc_deficit_order = []
    for loc, cids in loc_to_cids.items():
        total_def = sum(deficit[cid] for cid in cids)
        if total_def > 0:
            loc_deficit_order.append((loc, total_def))
    # stable order by larger total deficit first (to reduce global imbalance deterministically), then lex loc
    loc_deficit_order.sort(key=lambda x: (-x[1], x[0]))

    # --- Build structure for assigning product IDs at each destination location (priority then input order) ---
    # We'll keep a mutable pointer of remaining forecast by product for each location.
    prod_need_by_loc: Dict[str, List[List[Any]]] = {}
    for loc, plist in products_by_loc.items():
        # convert tuples to mutable [priority, product_id, remaining, original_index]
        prod_need_by_loc[loc] = [[p, pid, int(fc), idx] for (p, pid, fc, idx) in plist]

    routes_map: Dict[Tuple[str, str, str], int] = defaultdict(int)

    # --- Helper to allocate product IDs for a given location and quantity (lowest priority number first) ---
    def allocate_products_for_location(loc: str, qty: int) -> List[Tuple[str, int]]:
        out: List[Tuple[str, int]] = []
        if qty <= 0 or loc not in prod_need_by_loc:
            return out
        arr = prod_need_by_loc[loc]
        i = 0
        remaining = qty
        while remaining > 0 and i < len(arr):
            p, pid, need, _ = arr[i]
            if need <= 0:
                i += 1
                continue
            take = need if need <= remaining else remaining
            out.append((pid, take))
            need -= take
            remaining -= take
            arr[i][2] = need
            if need == 0:
                i += 1
        # If remaining > 0 (more sent than explicit product needs), we still account it under the last product in order
        # to keep totals consistent and deterministic (this can happen if deficits were computed from total forecast
        # but surplus exceeds sum of per-product needs due to integer/rounding or cross-center splits).
        if remaining > 0 and arr:
            # use the last product in priority order deterministically
            pid_last = arr[-1][1]
            out.append((pid_last, remaining))
            remaining = 0
        return out

    # --- Build a sorted list of sender candidates we will reuse per receiver ---
    def sender_order_for(receiver_cid: int) -> List[int]:
        # filter only reachable senders with positive surplus
        cand = []
        for scid, s in surplus.items():
            if s <= 0 or scid == receiver_cid:
                continue
            if reachable_in_one_hop_or_less(scid, receiver_cid):
                cand.append(scid)
        # sort by higher surplus desc, then smaller |id diff|, then lower sender id
        cand.sort(key=lambda sc: (-surplus[sc], abs(sc - receiver_cid), sc))
        return cand

    # --- Perform transfers: iterate locations with deficits, then centers in that location by ascending center_id ---
    for loc, _total_def in loc_deficit_order:
        for rcid in loc_to_cids.get(loc, []):
            need = deficit[rcid]
            if need <= 0:
                continue
            # receiver capacity headroom (based on REAL inventory; transfers change real inventory)
            real_recv_inv = centers[rcid]["inventory"]
            cap = centers[rcid]["capacity"]
            headroom = max(0, cap - real_recv_inv)
            if headroom <= 0:
                continue

            take_limit = min(need, headroom)
            if take_limit <= 0:
                continue

            # choose senders in deterministic order
            sorder = sender_order_for(rcid)
            remaining = take_limit
            for scid in sorder:
                if remaining <= 0:
                    break
                sendable = min(surplus[scid], remaining)
                # also can't send more than sender's real inventory
                sendable = min(sendable, centers[scid]["inventory"])
                if sendable <= 0:
                    continue

                # Split sendable into product-wise chunks per destination location
                chunks = allocate_products_for_location(loc, sendable)
                moved_total = 0
                for pid, q in chunks:
                    if q <= 0:
                        continue
                    # finalize move q units
                    centers[scid]["inventory"] -= q
                    centers[rcid]["inventory"] += q
                    moved_total += q
                    routes_map[(centers[scid]["location"], centers[rcid]["location"], pid)] += q

                # update bookkeeping after actual moved_total (not theoretical sendable)
                if moved_total > 0:
                    surplus[scid] -= moved_total
                    remaining -= moved_total
                    need -= moved_total
                    deficit[rcid] = need

    # --- Build output: aggregate routes and inventory adjustments (clamped to [0, capacity]) ---
    routes = []
    for (fr_loc, to_loc, pid), q in routes_map.items():
        if q > 0 and fr_loc != to_loc:
            routes.append({"from": fr_loc, "to": to_loc, "product_id": pid, "quantity": int(q)})
    routes.sort(key=lambda r: (r["from"], r["to"], r["product_id"]))

    inv_adj = []
    for cid in sorted(centers):
        inv = centers[cid]["inventory"]
        cap = centers[cid]["capacity"]
        # clamp for safety
        if inv < 0:
            inv = 0
        if inv > cap:
            inv = cap
        inv_adj.append({"center_id": cid, "new_inventory": int(inv)})

    return {"routes": routes, "inventory_adjustments": inv_adj}