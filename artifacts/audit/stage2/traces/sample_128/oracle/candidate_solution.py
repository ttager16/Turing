from typing import Any, Dict, List


def determine_tree_centers(trees: List[Dict[str, Any]]) -> List[int]:

    n = len(trees)


    def int_keyed(d: Dict[Any, Any]) -> Dict[int, Any]:
        return {int(k): v for k, v in d.items()}

    parent = list(range(n))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    class ComponentData:
        __slots__ = ("adj", "T", "C", "active")
        def __init__(self):
            self.adj: Dict[int, Dict[int, int]] = {}
            self.T: Dict[int, int] = {}
            self.C: Dict[int, int] = {}
            self.active: Dict[int, bool] = {}

    comps: Dict[int, ComponentData] = {}

    for idx, district in enumerate(trees):
        comp = ComponentData()

        nodes = [int(x) for x in district["nodes"]]
        for node in nodes:
            comp.adj[node] = {}

        for u, v, w in district["edges"]:
            u = int(u); v = int(v)
            comp.adj.setdefault(u, {})[v] = w
            comp.adj.setdefault(v, {})[u] = w

        comp.T.update(int_keyed(district["node_weights"]))
        comp.C.update(int_keyed(district["capacity"]))

        for node in nodes:
            comp.active[node] = True

        comps[idx] = comp

    def merge_components(src_root: int, tgt_root: int, node_src: int, node_tgt: int, w: int) -> None:
        node_src = int(node_src)
        node_tgt = int(node_tgt)

        if src_root == tgt_root:
            comp_tgt = comps[tgt_root]
            comp_tgt.adj.setdefault(node_src, {})
            comp_tgt.adj.setdefault(node_tgt, {})
            comp_tgt.adj[node_src][node_tgt] = w
            comp_tgt.adj[node_tgt][node_src] = w
            return

        comp_src = comps[src_root]
        comp_tgt = comps[tgt_root]

        for node, nbrs in comp_src.adj.items():
            if node not in comp_tgt.adj:
                comp_tgt.adj[node] = {}
            for nbr, wt in nbrs.items():
                if nbr not in comp_tgt.adj:
                    comp_tgt.adj[nbr] = {}
                comp_tgt.adj[node][nbr] = wt
                comp_tgt.adj[nbr][node] = wt

        comp_tgt.T.update(comp_src.T)
        comp_tgt.C.update(comp_src.C)
        comp_tgt.active.update(comp_src.active)

        comp_tgt.adj.setdefault(node_src, {})
        comp_tgt.adj.setdefault(node_tgt, {})
        comp_tgt.adj[node_src][node_tgt] = w
        comp_tgt.adj[node_tgt][node_src] = w

        parent[src_root] = tgt_root
        del comps[src_root]

    for idx in range(n):
        events = trees[idx].get("events", [])
        for event in events:
            etype = event[0]
            if etype == "deactivate_node":
                node_id = int(event[1])
                root = find(idx)
                comps[root].active[node_id] = False
            elif etype == "activate_node":
                node_id = int(event[1])
                root = find(idx)
                comps[root].active[node_id] = True
            elif etype == "update_road":
                u, v, new_w = int(event[1]), int(event[2]), event[3]
                root = find(idx)
                comp = comps[root]
                comp.adj.setdefault(u, {})
                comp.adj.setdefault(v, {})
                comp.adj[u][v] = new_w
                comp.adj[v][u] = new_w
            elif etype == "merge":
                target_idx, node_this, node_other, connecting_w = event[1], event[2], event[3], event[4]
                src_root = find(idx)
                tgt_root = find(int(target_idx))
                merge_components(src_root, tgt_root, node_this, node_other, connecting_w)
            else:
                continue

    def build_active_adj(comp: ComponentData) -> Dict[int, Dict[int, int]]:
        active_adj: Dict[int, Dict[int, int]] = {}
        for u, nbrs in comp.adj.items():
            if not comp.active.get(u, False):
                continue
            au = active_adj.setdefault(u, {})
            for v, wt in nbrs.items():
                if comp.active.get(v, False):
                    au[v] = wt
        return active_adj

    def find_active_components(active_adj: Dict[int, Dict[int, int]], active_nodes: List[int]) -> List[List[int]]:
        comps_list: List[List[int]] = []
        seen = set()
        for s in active_nodes:
            if s in seen:
                continue
            stack = [s]
            seen.add(s)
            comp_nodes = []
            while stack:
                u = stack.pop()
                comp_nodes.append(u)
                for v in active_adj.get(u, {}):
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            comps_list.append(comp_nodes)
        return comps_list

    def best_hub_connected(comp: ComponentData, component_nodes: List[int], active_adj: Dict[int, Dict[int, int]]) -> int:
        root = component_nodes[0]
        stack = [root]
        parent_node: Dict[int, int] = {root: None}
        order: List[int] = []
        visited = {root}

        while stack:
            u = stack.pop()
            order.append(u)
            for v, w in active_adj.get(u, {}).items():
                if v not in visited:
                    visited.add(v)
                    parent_node[v] = u
                    stack.append(v)

        edge_w: Dict[tuple, int] = {}
        for u in component_nodes:
            for v, w in active_adj.get(u, {}).items():
                edge_w[(u, v)] = w

        sub_weight = {u: comp.T.get(u, 0) for u in component_nodes}
        sub_cost = {u: 0 for u in component_nodes}

        for u in reversed(order):
            for v in active_adj.get(u, {}):
                if parent_node.get(v) == u:
                    w = edge_w[(u, v)]
                    sub_weight[u] += sub_weight[v]
                    sub_cost[u] += sub_cost[v] + sub_weight[v] * w

        total_weight = sub_weight[root]

        D = {root: sub_cost[root]}
        for u in order:
            for v in active_adj.get(u, {}):
                if parent_node.get(v) == u:
                    w = edge_w[(u, v)]
                    D[v] = D[u] - sub_weight[v] * w + (total_weight - sub_weight[v]) * w

        best_node = None
        best_num = None
        best_den = None

        for h in component_nodes:
            num = D[h]
            den = comp.C.get(h, 0)
            if den <= 0:
                continue
            if best_node is None:
                best_node, best_num, best_den = h, num, den
            else:
                left = num * best_den
                right = best_num * den
                if left < right or (left == right and h < best_node):
                    best_node, best_num, best_den = h, num, den

        if best_node is not None:
            return best_node
        return min(component_nodes)

    best_hub_for_root: Dict[int, int] = {}

    for root_idx, comp in comps.items():
        active_nodes = [u for u, on in comp.active.items() if on]
        if not active_nodes:
            best_hub_for_root[root_idx] = -1
            continue

        active_adj = build_active_adj(comp)
        components = find_active_components(active_adj, active_nodes)

        if len(components) == 1:
            best_hub_for_root[root_idx] = best_hub_connected(comp, components[0], active_adj)
        else:
            def comp_key(nodes_list: List[int]):
                size = len(nodes_list)
                tot_traffic = sum(comp.T.get(x, 0) for x in nodes_list)
                min_id = min(nodes_list)
                return (size, tot_traffic, -min_id)

            chosen = max(components, key=comp_key)
            best_hub_for_root[root_idx] = best_hub_connected(comp, chosen, active_adj)

    result: List[int] = []
    for i in range(n):
        r = find(i)
        if r != i:
            result.append(-1)
        else:
            result.append(best_hub_for_root.get(i, -1))
    return result