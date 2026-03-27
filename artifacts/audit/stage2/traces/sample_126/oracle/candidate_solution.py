from typing import Dict, List, Union, Set, Tuple, Optional
import ast


class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}
        self.component_count = 0
    
    def make_set(self, node):
        if node not in self.parent:
            self.parent[node] = node
            self.rank[node] = 0
            self.component_count += 1
    
    def find(self, node):
        if node not in self.parent:
            return None
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]
    
    def union(self, node1, node2) -> bool:
        root1 = self.find(node1)
        root2 = self.find(node2)
        
        if root1 is None or root2 is None:
            return False
        
        if root1 == root2:
            return False
        
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1
        
        self.component_count -= 1
        return True
    
    def connected(self, node1, node2) -> bool:
        root1 = self.find(node1)
        root2 = self.find(node2)
        if root1 is None or root2 is None:
            return False
        return root1 == root2
    
    def is_fully_connected(self) -> bool:
        return self.component_count <= 1
    
    def copy(self):
        new_uf = UnionFind()
        new_uf.parent = self.parent.copy()
        new_uf.rank = self.rank.copy()
        new_uf.component_count = self.component_count
        return new_uf


class MultiLayerSpanningTree:
    def __init__(self, graph: Dict[str, int]):
        self.costs = {}
        self.mandatory = set()
        self.prohibited = set()
        self.spanning_tree = set()
        self.all_nodes = set()
        self.conduit_map = {}
        self.node_pair_to_conduits = {}
        
        if not graph:
            return
        
        for conduit_str, cost in graph.items():
            try:
                conduit = ast.literal_eval(conduit_str)
                if not isinstance(conduit, list) or len(conduit) != 3:
                    continue
                if not all(isinstance(x, int) for x in conduit):
                    continue
                if cost < 0:
                    continue
                
                conduit_tuple = self._normalize_conduit(conduit)
                self.costs[conduit_tuple] = cost
                self.conduit_map[conduit_tuple] = list(conduit_tuple)
                self.all_nodes.add(conduit_tuple[1])
                self.all_nodes.add(conduit_tuple[2])
                
                node_pair = self._get_node_pair(conduit_tuple)
                if node_pair not in self.node_pair_to_conduits:
                    self.node_pair_to_conduits[node_pair] = set()
                self.node_pair_to_conduits[node_pair].add(conduit_tuple)
            except (ValueError, SyntaxError):
                continue
        
        self._build_initial_tree()
    
    def _normalize_conduit(self, conduit) -> Tuple[int, int, int]:
        layer, n1, n2 = conduit[0], conduit[1], conduit[2]
        return (layer, min(n1, n2), max(n1, n2))
    
    def _get_node_pair(self, conduit) -> frozenset:
        return frozenset([conduit[1], conduit[2]])
    
    def _build_initial_tree(self):
        self.spanning_tree.clear()
        
        if not self.all_nodes:
            return
        
        uf = UnionFind()
        for node in self.all_nodes:
            uf.make_set(node)
        
        occupied_pairs = set()
        
        for conduit in self.mandatory:
            if conduit in self.costs:
                self.spanning_tree.add(conduit)
                uf.union(conduit[1], conduit[2])
                node_pair = self._get_node_pair(conduit)
                occupied_pairs.add(node_pair)
        
        available_conduits = []
        for conduit, cost in self.costs.items():
            if conduit not in self.prohibited and conduit not in self.mandatory:
                available_conduits.append((cost, conduit))
        
        available_conduits.sort()
        
        for cost, conduit in available_conduits:
            node_pair = self._get_node_pair(conduit)
            
            if node_pair in occupied_pairs:
                continue
            
            if not uf.connected(conduit[1], conduit[2]):
                uf.union(conduit[1], conduit[2])
                self.spanning_tree.add(conduit)
                occupied_pairs.add(node_pair)
                
                if uf.is_fully_connected():
                    break
        
        if not uf.is_fully_connected():
            self._force_connectivity(uf, occupied_pairs)
    
    def _force_connectivity(self, uf: UnionFind, occupied_pairs: set):
        max_iterations = len(self.costs)
        iteration = 0
        
        while not uf.is_fully_connected() and iteration < max_iterations:
            iteration += 1
            best_conduit = None
            best_cost = float('inf')
            
            for conduit, cost in self.costs.items():
                if conduit in self.prohibited:
                    continue
                if conduit in self.spanning_tree:
                    continue
                
                node_pair = self._get_node_pair(conduit)
                if node_pair in occupied_pairs:
                    continue
                
                if not uf.connected(conduit[1], conduit[2]):
                    if cost < best_cost:
                        best_cost = cost
                        best_conduit = conduit
            
            if best_conduit is None:
                for conduit, cost in self.costs.items():
                    if conduit in self.prohibited:
                        continue
                    if conduit in self.spanning_tree:
                        continue
                    
                    if not uf.connected(conduit[1], conduit[2]):
                        if cost < best_cost:
                            best_cost = cost
                            best_conduit = conduit
            
            if best_conduit is None:
                break
            
            uf.union(best_conduit[1], best_conduit[2])
            self.spanning_tree.add(best_conduit)
            node_pair = self._get_node_pair(best_conduit)
            occupied_pairs.add(node_pair)
    
    def _is_connected(self) -> bool:
        if not self.all_nodes:
            return True
        
        uf = UnionFind()
        for node in self.all_nodes:
            uf.make_set(node)
        
        for conduit in self.spanning_tree:
            uf.union(conduit[1], conduit[2])
        
        return uf.is_fully_connected()
    
    def _find_path(self, start: int, end: int, exclude_conduit=None) -> List[Tuple]:
        if start == end:
            return []
        
        graph = {}
        for node in self.all_nodes:
            graph[node] = []
        
        for conduit in self.spanning_tree:
            if exclude_conduit and conduit == exclude_conduit:
                continue
            graph[conduit[1]].append((conduit[2], conduit))
            graph[conduit[2]].append((conduit[1], conduit))
        
        visited = set()
        parent_map = {}
        queue = [start]
        visited.add(start)
        
        while queue:
            current = queue.pop(0)
            if current == end:
                path = []
                node = end
                while node != start:
                    prev_node, edge = parent_map[node]
                    path.append(edge)
                    node = prev_node
                return path[::-1]
            
            for neighbor, edge in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent_map[neighbor] = (current, edge)
                    queue.append(neighbor)
        
        return []
    
    def _find_replacement_conduit(self, uf: UnionFind, occupied_pairs: set) -> Optional[Tuple]:
        best_conduit = None
        best_cost = float('inf')
        
        for conduit, cost in self.costs.items():
            if conduit in self.prohibited:
                continue
            if conduit in self.spanning_tree:
                continue
            
            node_pair = self._get_node_pair(conduit)
            if node_pair in occupied_pairs:
                continue
            
            if not uf.connected(conduit[1], conduit[2]):
                if cost < best_cost:
                    best_cost = cost
                    best_conduit = conduit
        
        return best_conduit
    
    def _rebuild_tree_optimally(self):
        old_tree = self.spanning_tree.copy()
        self.spanning_tree.clear()
        
        uf = UnionFind()
        for node in self.all_nodes:
            uf.make_set(node)
        
        occupied_pairs = set()
        
        for conduit in self.mandatory:
            if conduit in self.costs:
                self.spanning_tree.add(conduit)
                uf.union(conduit[1], conduit[2])
                node_pair = self._get_node_pair(conduit)
                occupied_pairs.add(node_pair)
        
        available_conduits = []
        for conduit, cost in self.costs.items():
            if conduit not in self.prohibited and conduit not in self.mandatory:
                available_conduits.append((cost, conduit))
        
        available_conduits.sort()
        
        for cost, conduit in available_conduits:
            node_pair = self._get_node_pair(conduit)
            
            if node_pair in occupied_pairs:
                continue
            
            if not uf.connected(conduit[1], conduit[2]):
                uf.union(conduit[1], conduit[2])
                self.spanning_tree.add(conduit)
                occupied_pairs.add(node_pair)
                
                if uf.is_fully_connected():
                    break
        
        if not uf.is_fully_connected():
            self._force_connectivity(uf, occupied_pairs)
    
    def update_cost(self, conduit: List[int], new_cost: int):
        if not conduit or len(conduit) != 3:
            return
        if new_cost < 0:
            return
        
        conduit = self._normalize_conduit(conduit)
        
        if conduit not in self.costs:
            self.costs[conduit] = new_cost
            self.conduit_map[conduit] = list(conduit)
            self.all_nodes.add(conduit[1])
            self.all_nodes.add(conduit[2])
            
            node_pair = self._get_node_pair(conduit)
            if node_pair not in self.node_pair_to_conduits:
                self.node_pair_to_conduits[node_pair] = set()
            self.node_pair_to_conduits[node_pair].add(conduit)
            
            uf = UnionFind()
            for node in self.all_nodes:
                uf.make_set(node)
            for c in self.spanning_tree:
                uf.union(c[1], c[2])
            
            if conduit not in self.prohibited:
                occupied_pairs = {self._get_node_pair(c) for c in self.spanning_tree}
                
                if node_pair not in occupied_pairs and not uf.connected(conduit[1], conduit[2]):
                    self.spanning_tree.add(conduit)
                    return
        
        old_cost = self.costs.get(conduit, new_cost)
        self.costs[conduit] = new_cost
        
        if conduit in self.mandatory or conduit in self.prohibited:
            return
        
        if conduit in self.spanning_tree:
            if new_cost > old_cost:
                self._handle_cost_increase(conduit, new_cost)
        else:
            if new_cost < old_cost:
                self._handle_cost_decrease(conduit, new_cost)
    
    def _handle_cost_increase(self, conduit: Tuple, new_cost: int):
        if conduit in self.mandatory:
            return
        
        uf_test = UnionFind()
        for node in self.all_nodes:
            uf_test.make_set(node)
        
        for c in self.spanning_tree:
            if c != conduit:
                uf_test.union(c[1], c[2])
        
        if uf_test.is_fully_connected():
            self.spanning_tree.remove(conduit)
        else:
            path = self._find_path(conduit[1], conduit[2], exclude_conduit=conduit)
            if not path:
                return
            
            max_cost_conduit = None
            max_cost = -1
            
            for path_conduit in path:
                if path_conduit not in self.mandatory:
                    if self.costs[path_conduit] > max_cost:
                        max_cost = self.costs[path_conduit]
                        max_cost_conduit = path_conduit
            
            if max_cost_conduit and max_cost > new_cost:
                self.spanning_tree.remove(max_cost_conduit)
                if not self._is_connected():
                    self.spanning_tree.add(max_cost_conduit)
    
    def _handle_cost_decrease(self, conduit: Tuple, new_cost: int):
        if conduit in self.prohibited:
            return
        
        uf = UnionFind()
        for node in self.all_nodes:
            uf.make_set(node)
        for c in self.spanning_tree:
            uf.union(c[1], c[2])
        
        node_pair = self._get_node_pair(conduit)
        occupied_pairs = {self._get_node_pair(c) for c in self.spanning_tree}
        
        if node_pair in occupied_pairs:
            conflicting_conduit = None
            for c in self.spanning_tree:
                if self._get_node_pair(c) == node_pair:
                    conflicting_conduit = c
                    break
            
            if conflicting_conduit and conflicting_conduit not in self.mandatory:
                if new_cost < self.costs[conflicting_conduit]:
                    self.spanning_tree.remove(conflicting_conduit)
                    self.spanning_tree.add(conduit)
            return
        
        if not uf.connected(conduit[1], conduit[2]):
            self.spanning_tree.add(conduit)
        else:
            path = self._find_path(conduit[1], conduit[2])
            if not path:
                return
            
            max_cost_conduit = None
            max_cost = new_cost
            
            for path_conduit in path:
                if path_conduit not in self.mandatory:
                    if self.costs[path_conduit] > max_cost:
                        max_cost = self.costs[path_conduit]
                        max_cost_conduit = path_conduit
            
            if max_cost_conduit:
                self.spanning_tree.remove(max_cost_conduit)
                self.spanning_tree.add(conduit)
    
    def set_mandatory(self, conduit: List[int]):
        if not conduit or len(conduit) != 3:
            return
        
        conduit = self._normalize_conduit(conduit)
        
        if conduit in self.prohibited:
            self.prohibited.remove(conduit)
        
        self.mandatory.add(conduit)
        
        if conduit not in self.costs:
            self.costs[conduit] = 0
            self.conduit_map[conduit] = list(conduit)
            self.all_nodes.add(conduit[1])
            self.all_nodes.add(conduit[2])
            
            node_pair = self._get_node_pair(conduit)
            if node_pair not in self.node_pair_to_conduits:
                self.node_pair_to_conduits[node_pair] = set()
            self.node_pair_to_conduits[node_pair].add(conduit)
        
        node_pair = self._get_node_pair(conduit)
        
        conflicting_conduits = []
        for c in self.spanning_tree:
            if self._get_node_pair(c) == node_pair and c != conduit:
                conflicting_conduits.append(c)
        
        for c in conflicting_conduits:
            if c not in self.mandatory:
                self.spanning_tree.remove(c)
        
        if conduit not in self.spanning_tree:
            self.spanning_tree.add(conduit)
        
        if not self._is_connected():
            self._rebuild_tree_optimally()
    
    def set_prohibited(self, conduit: List[int]):
        if not conduit or len(conduit) != 3:
            return
        
        conduit = self._normalize_conduit(conduit)
        
        if conduit in self.mandatory:
            return
        
        self.prohibited.add(conduit)
        
        if conduit in self.spanning_tree:
            self.spanning_tree.remove(conduit)
            
            if not self._is_connected():
                uf = UnionFind()
                for node in self.all_nodes:
                    uf.make_set(node)
                for c in self.spanning_tree:
                    uf.union(c[1], c[2])
                
                occupied_pairs = {self._get_node_pair(c) for c in self.spanning_tree}
                replacement = self._find_replacement_conduit(uf, occupied_pairs)
                
                if replacement:
                    self.spanning_tree.add(replacement)
                else:
                    self._rebuild_tree_optimally()
    
    def get_spanning_tree(self) -> List[List[int]]:
        result = []
        seen_pairs = set()
        
        for conduit in self.spanning_tree:
            node_pair = self._get_node_pair(conduit)
            if node_pair not in seen_pairs:
                result.append(self.conduit_map[conduit])
                seen_pairs.add(node_pair)
        
        return result


def dynamic_mst(
    graph: Dict[str, int],
    updates: List[List[Union[List[int], Union[int, str]]]]
) -> List[List[int]]:
    if not graph:
        return []
    
    try:
        mst = MultiLayerSpanningTree(graph)
    except Exception:
        return []
    
    if not updates:
        return mst.get_spanning_tree()
    
    for update in updates:
        try:
            if not update or len(update) < 2:
                continue
            
            conduit = update[0]
            value = update[1]
            
            if not conduit or len(conduit) != 3:
                continue
            
            if not all(isinstance(x, int) for x in conduit):
                continue
            
            if isinstance(value, int):
                mst.update_cost(conduit, value)
            elif isinstance(value, str):
                if value == "MANDATORY":
                    mst.set_mandatory(conduit)
                elif value == "PROHIBITED":
                    mst.set_prohibited(conduit)
        except Exception:
            continue
    
    return mst.get_spanning_tree()


if __name__ == "__main__":

    graph = {
        "[0, 1, 2]": 4,
        "[0, 2, 3]": 7,
        "[1, 1, 2]": 3,
        "[1, 2, 3]": 5,
        "[2, 3, 4]": 2
    }
    
    updates = [
        [[1, 1, 2], 1],
        [[2, 3, 4], "MANDATORY"]
    ]

    result = dynamic_mst(graph, updates)
    print(f"Final spanning subgraph: {result}")