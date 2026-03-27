from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any

def optimize_traffic_signals(
    graph: Dict[str, List[str]],
    traffic_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    
    def round_half_up(value):
        return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    def is_list_of_strings(value):
        return isinstance(value, list) and all(isinstance(item, str) for item in value)

    if not isinstance(graph, dict) or not graph:
        return {}
    for node, edges in graph.items():
        if not isinstance(node, str) or not node:
            return {}
        if not isinstance(edges, list) or not all(isinstance(e, str) for e in edges):
            return {}
    if not isinstance(traffic_data, list):
        return {}
    for record in traffic_data:
        if not isinstance(record, dict) or "intersection" not in record:
            return {}

    adjacency = {k: list(v) for k, v in graph.items()}
    for record in traffic_data:
        name = record.get("intersection")
        if isinstance(name, str) and name and name not in adjacency:
            adjacency[name] = []
    intersections = sorted(adjacency.keys())

    records_by_intersection = {}
    for idx, record in enumerate(traffic_data):
        name = record.get("intersection")
        if not isinstance(name, str) or not name:
            continue
        accidents = record.get("accidents", [])
        priority = record.get("priority_requests", [])
        if ("accidents" in record and not is_list_of_strings(accidents)) or \
           ("priority_requests" in record and not is_list_of_strings(priority)):
            continue
        has_density = "traffic_density" in record and record["traffic_density"] is not None
        density_valid = False
        density_value = None
        if has_density and not isinstance(record["traffic_density"], bool) and isinstance(record["traffic_density"], (int, float)):
            density_value = float(record["traffic_density"])
            if 0 <= density_value <= 1:
                density_valid = True
        records_by_intersection.setdefault(name, []).append({
            "index": idx,
            "accidents": accidents,
            "priority_requests": priority,
            "has_density": density_valid,
            "traffic_density": density_value if density_valid else None
        })

    best_density_record = {}
    for name, recs in records_by_intersection.items():
        best = None
        for r in recs:
            if not r["has_density"]:
                continue
            density = r["traffic_density"]
            has_emergency = "EMERGENCY" in r["priority_requests"]
            duration = 20 + round_half_up(70 * density)
            if has_emergency:
                duration += 10
            if density > 0.7 and "LANE_OUTAGE" in r["accidents"]:
                duration //= 2
            candidate = {"time": duration, "emergency": has_emergency, "index": r["index"], "density": density}
            if best is None:
                best = candidate
            else:
                if candidate["time"] < best["time"]:
                    best = candidate
                elif candidate["time"] == best["time"]:
                    if candidate["emergency"] and not best["emergency"]:
                        best = candidate
                    elif candidate["emergency"] == best["emergency"] and candidate["index"] >= best["index"]:
                        best = candidate
        if best is not None:
            best_density_record[name] = best

    preliminary_durations = {}
    for name, data in best_density_record.items():
        preliminary_durations[name] = float(data["time"])
    for name in intersections:
        if name not in preliminary_durations and len(adjacency.get(name, [])) == 0:
            preliminary_durations[name] = 45

    nodata_metadata = {}
    for name, recs in records_by_intersection.items():
        has_missing_density = any(not r["has_density"] for r in recs)
        if has_missing_density:
            has_emergency = any(("EMERGENCY" in r["priority_requests"]) for r in recs if not r["has_density"])
            last_index = max((r["index"] for r in recs if not r["has_density"]), default=-1)
            nodata_metadata[name] = {"has": True, "has_emergency": has_emergency, "last_index": last_index}

    nodata_duration = {}
    for name in intersections:
        neighbors = adjacency.get(name, [])
        known = [preliminary_durations[n] for n in neighbors if n in preliminary_durations]
        if known:
            nodata_duration[name] = round_half_up(sum(known) / len(known))
        else:
            nodata_duration[name] = 45

    preliminary_final = {}
    record_type = {}

    for name in intersections:
        density_record = best_density_record.get(name)
        nodata_info = nodata_metadata.get(name, {"has": False, "has_emergency": False, "last_index": -1})
        has_nodata = nodata_info["has"]
        nodata_time = nodata_duration[name]

        if density_record and has_nodata:
            if nodata_time < density_record["time"]:
                preliminary_final[name] = nodata_time
                record_type[name] = "nodata"
            elif nodata_time > density_record["time"]:
                preliminary_final[name] = density_record["time"]
                record_type[name] = "density"
            else:
                if nodata_info["has_emergency"] and not density_record["emergency"]:
                    preliminary_final[name] = nodata_time
                    record_type[name] = "nodata"
                elif density_record["emergency"] and not nodata_info["has_emergency"]:
                    preliminary_final[name] = density_record["time"]
                    record_type[name] = "density"
                else:
                    if nodata_info["last_index"] >= density_record["index"]:
                        preliminary_final[name] = nodata_time
                        record_type[name] = "nodata"
                    else:
                        preliminary_final[name] = density_record["time"]
                        record_type[name] = "density"
        elif density_record:
            preliminary_final[name] = density_record["time"]
            record_type[name] = "density"
        else:
            preliminary_final[name] = nodata_time
            record_type[name] = "nodata" if has_nodata else "none"

    if not preliminary_final:
        return {}
    total = sum(preliminary_final.values())
    scale_factor = (45 * len(preliminary_final) / total) if total != 0 else 1

    normalized_durations = {}
    for name in intersections:
        value = round_half_up(preliminary_final[name] * scale_factor)
        value = max(20, min(90, value))
        normalized_durations[name] = value

    results = {}
    for name in intersections:
        overflow = normalized_durations[name] < 30
        if not overflow and record_type.get(name) == "density":
            data = best_density_record[name]
            if data["density"] is not None and data["density"] > 0.75 and not data["emergency"]:
                overflow = True
        results[name] = {"signal_timing": normalized_durations[name], "overflow_indicator": overflow}

    return results


if __name__ == "__main__":
    graph = {
        "A": ["B", "C"],
        "B": ["A", "D"],
        "C": ["A", "F"],
        "D": ["B", "E"],
        "E": ["D", "F"],
        "F": ["C", "E"]
    }
    traffic_data = [
        {"intersection": "A", "traffic_density": 0.8, "accidents": [], "priority_requests": ["EMERGENCY"]},
        {"intersection": "B", "traffic_density": 0.75, "accidents": ["LANE_OUTAGE"], "priority_requests": []},
        {"intersection": "C", "traffic_density": 0.4, "accidents": [], "priority_requests": []},
        {"intersection": "E", "traffic_density": 0.65, "accidents": [], "priority_requests": []}
    ]
    print(optimize_traffic_signals(graph=graph, traffic_data=traffic_data))