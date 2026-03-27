from decimal import Decimal, ROUND_HALF_UP
import math
from functools import cmp_to_key
from heapq import heappush, heappop


def sort_investment_portfolios(portfolios: list[dict]) -> list[dict]:
    """
    Sort and rank investment portfolios by their risk-return ratio and references.

    portfolios: list of portfolio dictionaries with fields (name, risk, return, references, sub_portfolios)
    returns: ranked list of portfolios with added _score and _rank, or [] if validation fails.
    """

    TOLERANCE = 1e-12
    REFERENCE_WEIGHT = 0.1

    
    def is_number(value):
        return isinstance(value, (int, float)) and math.isfinite(value)

    def is_alpha_name(value):
        return isinstance(value, str) and len(value) > 0 and value.isalpha()

    def round_to_10(x):
        d = Decimal(str(x))
        return float(d.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP))

    if not isinstance(portfolios, list):
        return []
    if len(portfolios) == 0:
        return []

    required_keys = ("name", "risk", "return", "references", "sub_portfolios")
    node_by_name = {}
    parent_child_edges = []

    def validate_and_register(node, parent_name=None):
        if not isinstance(node, dict):
            raise ValueError
        if set(node.keys()) != set(required_keys):
            raise ValueError

        name = node["name"]
        risk = node["risk"]
        ret = node["return"]
        references = node["references"]
        sub_portfolios = node["sub_portfolios"]

        if not is_alpha_name(name):
            raise ValueError
        if not is_number(risk) or not is_number(ret):
            raise ValueError
        if risk <= 0:
            raise ValueError
        if not isinstance(references, list) or not isinstance(sub_portfolios, list):
            raise ValueError
        for ref in references:
            if not is_alpha_name(ref):
                raise ValueError
        if name in references:
            raise ValueError
        if name in node_by_name:
            raise ValueError

        node_by_name[name] = {
            "name": name,
            "risk": risk,
            "return": ret,
            "references": list(references),
            "sub_portfolios": list(sub_portfolios),
        }

        if parent_name is not None:
            parent_child_edges.append((parent_name, name))

        for child in sub_portfolios:
            validate_and_register(child, parent_name=name)

    try:
        for top in portfolios:
            validate_and_register(top, parent_name=None)
    except Exception:
        return []

    sorted_names = sorted(node_by_name.keys())
    reference_adjacency = {n: [] for n in sorted_names}
    combined_adjacency = {n: [] for n in sorted_names}

    for name in sorted_names:
        seen = set()
        for ref in node_by_name[name]["references"]:
            if ref in node_by_name and ref not in seen:
                seen.add(ref)
        refs_sorted = sorted(seen)
        reference_adjacency[name] = refs_sorted
        combined_adjacency[name].extend(refs_sorted)

    hierarchy_map = {n: set() for n in sorted_names}
    for parent, child in parent_child_edges:
        hierarchy_map[parent].add(child)
    for name in sorted_names:
        children_sorted = sorted(hierarchy_map[name])
        combined_adjacency[name].extend(children_sorted)
        combined_adjacency[name] = sorted(set(combined_adjacency[name]))

    base_score = {}
    for name in sorted_names:
        value = node_by_name[name]["return"] / node_by_name[name]["risk"]
        if not math.isfinite(value):
            return []
        base_score[name] = value

    index_counter = 0
    index_map = {}
    lowlink_map = {}
    on_stack = {}
    stack = []
    components = []

    def strong_connect(vertex):
        nonlocal index_counter
        index_map[vertex] = index_counter
        lowlink_map[vertex] = index_counter
        index_counter += 1
        stack.append(vertex)
        on_stack[vertex] = True

        for neighbor in combined_adjacency[vertex]:
            if neighbor not in index_map:
                strong_connect(neighbor)
                lowlink_map[vertex] = min(lowlink_map[vertex], lowlink_map[neighbor])
            elif on_stack.get(neighbor, False):
                lowlink_map[vertex] = min(lowlink_map[vertex], index_map[neighbor])

        if lowlink_map[vertex] == index_map[vertex]:
            comp = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                comp.append(w)
                if w == vertex:
                    break
            components.append(sorted(comp))

    for name in sorted_names:
        if name not in index_map:
            strong_connect(name)

    group_of = {}
    members_by_group = {}
    group_is_cycle = {}
    fixed_group_score = {}

    for comp in components:
        group_id = comp[0]
        for member in comp:
            group_of[member] = group_id
        members_by_group[group_id] = comp
        is_cycle = len(comp) > 1
        group_is_cycle[group_id] = is_cycle
        if is_cycle:
            fixed_group_score[group_id] = sum(base_score[m] for m in comp) / len(comp)

    groups_sorted = sorted(members_by_group.keys())
    dag_adjacency = {g: [] for g in groups_sorted}
    indegree = {g: 0 for g in groups_sorted}

    for name in sorted_names:
        src_group = group_of[name]
        for ref in reference_adjacency[name]:
            dst_group = group_of[ref]
            if src_group != dst_group:
                dag_adjacency[dst_group].append(src_group)

    for g in groups_sorted:
        dag_adjacency[g] = sorted(set(dag_adjacency[g]))
    indegree = {g: 0 for g in groups_sorted}
    for g in groups_sorted:
        for h in dag_adjacency[g]:
            indegree[h] += 1

    heap = []
    for g in groups_sorted:
        if indegree[g] == 0:
            heappush(heap, g)

    topo_groups = []
    while heap:
        g = heappop(heap)
        topo_groups.append(g)
        for h in dag_adjacency[g]:
            indegree[h] -= 1
            if indegree[h] == 0:
                heappush(heap, h)

    if len(topo_groups) != len(groups_sorted):
        return []

    group_score = {}
    for g in groups_sorted:
        if group_is_cycle[g]:
            group_score[g] = fixed_group_score[g]

    for g in topo_groups:
        if group_is_cycle[g]:
            continue
        member = members_by_group[g][0]
        base = base_score[member]
        ref_names = reference_adjacency[member]
        if not ref_names:
            avg_ref = 0.0
        else:
            ref_scores = [group_score[group_of[r]] for r in ref_names]
            avg_ref = sum(ref_scores) / len(ref_scores)
        value = base + REFERENCE_WEIGHT * avg_ref
        if not math.isfinite(value):
            return []
        group_score[g] = value

    final_score = {}
    for g in groups_sorted:
        s = group_score[g]
        for n in members_by_group[g]:
            final_score[n] = s

    top_names = [p["name"] for p in portfolios]

    def compare_names(a, b):
        sa = final_score[a]
        sb = final_score[b]
        diff = sa - sb
        if abs(diff) <= TOLERANCE:
            if a < b:
                return -1
            if a > b:
                return 1
            return 0
        return -1 if sa > sb else 1

    sorted_top_names = sorted(top_names, key=cmp_to_key(compare_names))

    def clone_with_rounding(node):
        rounded = {
            "name": node["name"],
            "risk": round_to_10(node["risk"]) if isinstance(node["risk"], float) else node["risk"],
            "return": round_to_10(node["return"]) if isinstance(node["return"], float) else node["return"],
            "references": list(node["references"]),
            "sub_portfolios": [],
        }
        for child in node["sub_portfolios"]:
            rounded["sub_portfolios"].append(clone_with_rounding(child))
        return rounded

    node_lookup = {p["name"]: p for p in portfolios}
    result = []
    rank_counter = 1
    for name in sorted_top_names:
        node = node_lookup[name]
        ranked_portfolio = clone_with_rounding(node)
        ranked_portfolio["_score"] = round_to_10(final_score[name])
        ranked_portfolio["_rank"] = rank_counter
        rank_counter += 1
        result.append(ranked_portfolio)

    return result

if __name__ == "__main__":
    portfolios = [
        {
            'name': 'A',
            'risk': 0.2,
            'return': 6.0,
            'references': ['B'],
            'sub_portfolios': []
        },
        {
            'name': 'B',
            'risk': 0.3,
            'return': 7.0,
            'references': ['A'],
            'sub_portfolios': []
        }
    ]
    result = sort_investment_portfolios(portfolios)
    print(result)