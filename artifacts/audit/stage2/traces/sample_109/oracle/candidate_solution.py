from typing import Dict, List
from collections import deque

def self_stabilizing_matching(graph: Dict[str, List], disruptions: List[List[str]]) -> Dict[str, str]:
    def is_integer(value):
        return isinstance(value, int) and not isinstance(value, bool)
    if not isinstance(graph, dict) or not isinstance(disruptions, list):
        return {}
    if len(graph) == 0 and len(disruptions) == 0:
        return {}

    all_services = []
    all_controls_set = set()
    min_cost_per_service_control = {}
    control_appearance_counts = {}

    for service_id, neighbor_list in graph.items():
        if not isinstance(service_id, str):
            return {}
        if not isinstance(neighbor_list, list):
            return {}

        all_services.append(service_id)
        min_cost_per_service_control[service_id] = {}
        control_appearance_counts[service_id] = {}

        for neighbor in neighbor_list:
            if isinstance(neighbor, str):
                control_id = neighbor
                if control_id == "":
                    return {}
                cost_value = 0
            elif isinstance(neighbor, list):
                if len(neighbor) != 2:
                    return {}
                control_id, cost_value = neighbor[0], neighbor[1]
                if not isinstance(control_id, str) or control_id == "":
                    return {}
                if not is_integer(cost_value):
                    return {}
            else:
                return {}

            prev_cost = min_cost_per_service_control[service_id].get(control_id)
            if prev_cost is None or cost_value < prev_cost:
                min_cost_per_service_control[service_id][control_id] = cost_value
            control_appearance_counts[service_id][control_id] = control_appearance_counts[service_id].get(control_id, 0) + 1
            all_controls_set.add(control_id)

    known_node_ids = set(all_services).union(all_controls_set)

    allowed_events = {"fail", "attack", "restore"}
    for item in disruptions:
        if not isinstance(item, list) or len(item) != 2:
            return {}
        event, node_id = item[0], item[1]
        if not isinstance(event, str) or event not in allowed_events:
            return {}
        if not isinstance(node_id, str) or node_id == "":
            return {}

    availability = {node: True for node in known_node_ids}
    for event, node_id in disruptions:
        if node_id in availability:
            if event in ("fail", "attack"):
                availability[node_id] = False
            elif event == "restore":
                availability[node_id] = True

    operational_services = sorted([s for s in all_services if availability.get(s, True)])
    operational_controls = sorted(c for c in all_controls_set if availability.get(c, True))
    if not operational_services or not operational_controls:
        return {}

    control_capacity = {c: 0 for c in operational_controls}
    for service_id in operational_services:
        for control_id, count in control_appearance_counts[service_id].items():
            if control_id in control_capacity:
                control_capacity[control_id] += count

    service_edges = {s: {} for s in operational_services}
    for service_id in operational_services:
        for control_id, cost_value in min_cost_per_service_control[service_id].items():
            if control_id in control_capacity and control_capacity[control_id] > 0:
                service_edges[service_id][control_id] = cost_value
    
    if not any(service_edges[s] for s in operational_services):
        return {}

    class MinCostMaxFlow:
        class Edge:
            def __init__(self, to_index, reverse_index, capacity, cost):
                self.to_index = to_index
                self.reverse_index = reverse_index
                self.capacity = capacity
                self.cost = cost

        def __init__(self, node_count):
            self.node_count = node_count
            self.graph = [[] for _ in range(node_count)]

        def add_edge(self, from_index, to_index, capacity, cost):
            forward = MinCostMaxFlow.Edge(to_index, len(self.graph[to_index]), capacity, cost)
            backward = MinCostMaxFlow.Edge(from_index, len(self.graph[from_index]), 0, -cost)
            self.graph[from_index].append(forward)
            self.graph[to_index].append(backward)

        def min_cost_max_flow(self, source_index, sink_index, limit = 10**18):
            flow = 0
            total_cost = 0
            n = self.node_count
            INF = 10**18

            while flow < limit:
                distance = [INF] * n
                in_queue = [False] * n
                parent_node = [-1] * n
                parent_edge = [-1] * n

                distance[source_index] = 0
                queue = deque([source_index])
                in_queue[source_index] = True

                while queue:
                    u = queue.popleft()
                    in_queue[u] = False
                    for ei, edge in enumerate(self.graph[u]):
                        if edge.capacity <= 0:
                            continue
                        v = edge.to_index
                        new_distance = distance[u] + edge.cost
                        if new_distance < distance[v]:
                            distance[v] = new_distance
                            parent_node[v] = u
                            parent_edge[v] = ei
                            if not in_queue[v]:
                                queue.append(v)
                                in_queue[v] = True

                if distance[sink_index] == INF:
                    break

                add_flow = limit - flow
                v = sink_index
                while v != source_index:
                    u = parent_node[v]
                    ei = parent_edge[v]
                    if u == -1:
                        add_flow = 0
                        break
                    add_flow = min(add_flow, self.graph[u][ei].capacity)
                    v = u
                if add_flow == 0:
                    break

                v = sink_index
                while v != source_index:
                    u = parent_node[v]
                    ei = parent_edge[v]
                    edge = self.graph[u][ei]
                    edge.capacity -= add_flow
                    self.graph[v][edge.reverse_index].capacity += add_flow
                    total_cost += add_flow * edge.cost
                    v = u
                flow += add_flow

            return flow, total_cost
        
    service_index = {_service: idx for idx, _service in enumerate(operational_services)}
    service_count = len(operational_services)

    service_weight = [service_count - i for i in range(service_count)]
    max_weight_sum = sum(service_weight)
    latency_scale = 1 + max_weight_sum

    control_index = {_control: idx for idx, _control in enumerate(operational_controls)}
    control_count = len(operational_controls)

    source_index = 0
    sink_index = 1 + service_count + control_count

    def build_network(allowed_services, fixed_pairs = None, apply_service_bias = True):
        mcmf = MinCostMaxFlow(sink_index + 1)

        for service_id in allowed_services:
            service_node_index = 1 + service_index[service_id]
            mcmf.add_edge(source_index, service_node_index, 1, 0)

        for service_id in allowed_services:
            service_node_index = 1 + service_index[service_id]
            forced_control = fixed_pairs.get(service_id) if fixed_pairs else None
            if forced_control is not None:
                if forced_control in service_edges[service_id]:
                    control_node_index = 1 + service_count + control_index[forced_control]
                    base_cost = service_edges[service_id][forced_control]
                    edge_cost = (
                        base_cost * latency_scale - service_weight[service_index[service_id]]
                        if apply_service_bias else base_cost
                    )
                    mcmf.add_edge(service_node_index, control_node_index, 1, edge_cost)
            else:
                for control_id, base_cost in service_edges[service_id].items():
                    control_node_index = 1 + service_count + control_index[control_id]
                    edge_cost = (
                        base_cost * latency_scale - service_weight[service_index[service_id]]
                        if apply_service_bias else base_cost
                    )
                    mcmf.add_edge(service_node_index, control_node_index, 1, edge_cost)

        for control_id in operational_controls:
            cap = control_capacity.get(control_id, 0)
            if cap > 0:
                control_node_index = 1 + service_count + control_index[control_id]
                mcmf.add_edge(control_node_index, sink_index, cap, 0)
        return mcmf

    mcmf_phase_one = build_network(operational_services, apply_service_bias=True)
    max_flow, _ = mcmf_phase_one.min_cost_max_flow(source_index, sink_index)
    if max_flow == 0:
        return {}

    chosen_pairs = {}
    for service_id in operational_services:
        service_node_index = 1 + service_index[service_id]
        for edge in mcmf_phase_one.graph[service_node_index]:
            if not (service_count + 1 <= edge.to_index <= service_count + control_count):
                continue
            control_node_offset = edge.to_index - (service_count + 1)
            control_id = operational_controls[control_node_offset]
            reverse_edge = mcmf_phase_one.graph[edge.to_index][edge.reverse_index]
            if reverse_edge.capacity > 0:
                chosen_pairs[service_id] = control_id
                break

    if not chosen_pairs:
        return {}
    matched_size = len(chosen_pairs)
    optimal_total_latency = sum(service_edges[svc_id][ctl_id] for svc_id, ctl_id in chosen_pairs.items())
    matched_services_sorted = sorted(chosen_pairs.keys())

    fixed_assignment = {}
    for service_id in matched_services_sorted:
        candidate_controls = sorted(service_edges[service_id].keys())
        selected_control = None
        for control_candidate in candidate_controls:
            tentative_assignment = fixed_assignment.copy()
            tentative_assignment[service_id] = control_candidate
            mcmf_phase_two = build_network(matched_services_sorted, fixed_pairs=tentative_assignment, apply_service_bias=False)
            flow_check, cost_check = mcmf_phase_two.min_cost_max_flow(source_index, sink_index)
            if flow_check == matched_size and cost_check == optimal_total_latency:
                selected_control = control_candidate
                fixed_assignment[service_id] = control_candidate
                break
        if selected_control is None:
            return {}

    result = {service_id: fixed_assignment[service_id] for service_id in matched_services_sorted}
    return result if result else {}

if __name__ == "__main__":
    graph = {
        "1": ["101", ["102", 1], "105"],
        "2": [["101", 1], "103"],
        "3": [["104", 2], ["105", 2]],
        "4": [["102", 1], ["104", 1]],
        "5": [["102", 1], "105", "105"]
    }

    disruptions = [
        ["fail", "101"],
        ["attack", "3"],
        ["attack", "5"]
    ]
    print(self_stabilizing_matching(graph, disruptions))