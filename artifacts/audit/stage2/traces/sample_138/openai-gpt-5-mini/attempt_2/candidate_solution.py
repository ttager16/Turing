from typing import List, Tuple, Dict, Optional
import itertools
import copy

def process_network_operations(n: int, operations: list[list[str]]) -> list[int]:
    # Edge key as ordered tuple
    def edge_key(u: int, v: int) -> Tuple[int,int]:
        return (u,v) if u<=v else (v,u)
    # State snapshot
    class State:
        def __init__(self, edges: Dict[Tuple[int,int], Tuple[int,int]], valid: bool):
            # edges: map (u,v)->(cost,priority)
            self.edges = edges
            self.valid = valid
    states: List[State] = []
    # initial state: empty, valid
    states.append(State(edges={}, valid=True))
    results: List[int] = []
    op_index = 0  # 1-based index notion: after k-th operation -> states[k]
    for op in operations:
        op_index += 1
        cur = states[-1]
        # Work on a copy for next state unless rollback
        if op[0] == "ADD":
            # ["ADD", u, v, c, p]
            try:
                u = int(op[1]); v = int(op[2]); c = int(op[3]); p = int(op[4])
            except:
                # malformed -> invalid
                new = State(edges=copy.deepcopy(cur.edges), valid=False)
                states.append(new)
                continue
            if u==v:
                # self-loop invalidates
                new = State(edges=copy.deepcopy(cur.edges), valid=False)
                states.append(new)
                continue
            new_edges = copy.deepcopy(cur.edges)
            new_edges[edge_key(u,v)] = (c,p)
            new = State(edges=new_edges, valid=True)
            states.append(new)
        elif op[0] == "REMOVE":
            # ["REMOVE", u, v]
            try:
                u = int(op[1]); v = int(op[2])
            except:
                new = State(edges=copy.deepcopy(cur.edges), valid=False)
                states.append(new)
                continue
            key = edge_key(u,v)
            if key in cur.edges:
                new_edges = copy.deepcopy(cur.edges)
                del new_edges[key]
                new = State(edges=new_edges, valid=True)
                states.append(new)
            else:
                # becomes invalid until next successful modification
                new = State(edges=copy.deepcopy(cur.edges), valid=False)
                states.append(new)
        elif op[0] == "ROLLBACK":
            # ["ROLLBACK", k]
            try:
                k = int(op[1])
            except:
                # invalid
                new = State(edges=copy.deepcopy(cur.edges), valid=False)
                states.append(new)
                continue
            # restore to state immediately after k-th operation -> states[k]
            if 0 <= k <= len(operations):
                # but our states list length equals processed ops so far +1; valid k if 0<=k<=processed ops
                if 0 <= k < len(states):
                    # copy that state
                    ref = states[k]
                    new = State(edges=copy.deepcopy(ref.edges), valid=ref.valid)
                    states.append(new)
                else:
                    # invalid k
                    new = State(edges=copy.deepcopy(cur.edges), valid=False)
                    states.append(new)
            else:
                new = State(edges=copy.deepcopy(cur.edges), valid=False)
                states.append(new)
        elif op[0] == "QUERY":
            # state doesn't change, just append same state to history
            # compute answer based on cur
            # We'll append a copy state to states to represent after this op
            # compute result first
            if not cur.valid:
                results.append(-1)
            else:
                edges = cur.edges
                m = len(edges)
                if m == 0:
                    results.append(0)
                else:
                    # Build list of edges with indices
                    items = list(edges.items())  # [((u,v),(cost,pri)), ...]
                    if m <= 20:
                        # exact via brute force over subsets of edges to select monitored set that includes all priority edges
                        # assign indices
                        edge_list = []
                        for (uv,(cost,pri)) in items:
                            u,v = uv
                            edge_list.append( (uv[0],uv[1],cost,pri) )
                        idx_map = { (e[0],e[1]):i for i,e in enumerate(edge_list) }
                        # Precompute adjacency: each selected edge covers itself and edges sharing an endpoint
                        covers = []
                        for i,e in enumerate(edge_list):
                            u,v,c,p = e
                            cover = 0
                            for j,f in enumerate(edge_list):
                                x,y,_,_ = f
                                if i==j or u==x or u==y or v==x or v==y:
                                    cover |= (1<<j)
                            covers.append(cover)
                        full_mask = (1<<m)-1
                        # required mask for priority edges must be selected themselves
                        required_sel_mask = 0
                        for i,e in enumerate(edge_list):
                            if e[3]==1:
                                required_sel_mask |= (1<<i)
                        best = None
                        # iterate subsets that include required_sel_mask
                        # iterate over superset: iterate s from 0..2^m-1 where (s & required_sel_mask)==required_sel_mask
                        # optimize by iterating s' over remaining bits
                        rem_bits = [i for i in range(m) if not (required_sel_mask>>i &1)]
                        R = len(rem_bits)
                        for sfix in range(1<<R):
                            s = required_sel_mask
                            for j in range(R):
                                if (sfix>>j)&1:
                                    s |= (1<<rem_bits[j])
                            # check coverage
                            cov = 0
                            cost = 0
                            for i in range(m):
                                if (s>>i)&1:
                                    cov |= covers[i]
                                    cost += edge_list[i][2]
                            if cov == full_mask:
                                if best is None or cost < best:
                                    best = cost
                        if best is None:
                            results.append(-1)
                        else:
                            results.append(best)
                    else:
                        # heuristic deterministic: select all priority edges, then greedily add edges with best cost per uncovered edges covered
                        edge_list = []
                        for (uv,(cost,pri)) in items:
                            u,v = uv
                            edge_list.append( {'uv':uv,'u':u,'v':v,'cost':cost,'pri':pri} )
                        m = len(edge_list)
                        # map endpoints to edges
                        adj = {}
                        for i,e in enumerate(edge_list):
                            adj.setdefault(e['u'],[]).append(i)
                            adj.setdefault(e['v'],[]).append(i)
                        uncovered = set(range(m))
                        selected = set(i for i,e in enumerate(edge_list) if e['pri']==1)
                        # mark covered by initial selection
                        for i in list(selected):
                            e = edge_list[i]
                            for j in adj.get(e['u'],[]):
                                if j in uncovered:
                                    uncovered.discard(j)
                            for j in adj.get(e['v'],[]):
                                if j in uncovered:
                                    uncovered.discard(j)
                        # Greedy until uncovered empty
                        while uncovered:
                            # for each edge not yet selected, compute newly covered count
                            best_i = None
                            best_ratio = None
                            best_newcov = 0
                            for i,e in enumerate(edge_list):
                                if i in selected:
                                    continue
                                newcov = 0
                                # edges covered if select i
                                for j in adj.get(e['u'],[]):
                                    if j in uncovered:
                                        newcov += 1
                                for j in adj.get(e['v'],[]):
                                    if j in uncovered and j not in adj.get(e['u'],[]):
                                        newcov += 1
                                if newcov==0:
                                    continue
                                ratio = e['cost'] / newcov
                                # deterministic tie-break: lower cost, then smaller uv tuple
                                key = (ratio, e['cost'], e['uv'])
                                if best_i is None or key < best_ratio:
                                    best_i = i
                                    best_ratio = key
                                    best_newcov = newcov
                            if best_i is None:
                                # cannot cover remaining edges
                                selected = None
                                break
                            selected.add(best_i)
                            e = edge_list[best_i]
                            for j in adj.get(e['u'],[]):
                                if j in uncovered:
                                    uncovered.discard(j)
                            for j in adj.get(e['v'],[]):
                                if j in uncovered:
                                    uncovered.discard(j)
                        if selected is None:
                            results.append(-1)
                        else:
                            total = sum(edge_list[i]['cost'] for i in selected)
                            results.append(total)
            # append copy of current state to states to represent no-change after query
            states.append(State(edges=copy.deepcopy(cur.edges), valid=cur.valid))
        else:
            # unknown op -> state becomes invalid
            new = State(edges=copy.deepcopy(cur.edges), valid=False)
            states.append(new)
    return results