def string_diff_algorithm(
    baseline_files: Dict[str, str],
    current_files: Dict[str, str],
    dependencies: List[List[str]]
) -> Dict[str, Any]:
    # Helper: detect format
    def detect_format(s: str) -> str:
        s_strip = s.lstrip()
        if not s_strip:
            return 'yaml'
        if s_strip[0] in ['{', '[']:
            return 'json'
        if s_strip[0] == '<':
            return 'xml'
        return 'yaml'

    # JSON parse with fallback
    def parse_json(s: str):
        try:
            return json.loads(s)
        except Exception:
            return {}

    # YAML parser: simple indentation-based mapping and lists
    def parse_yaml(s: str):
        lines = s.splitlines()
        root = {}
        stack: List[Tuple[dict, int]] = [(root, -1)]
        key_re = re.compile(r'^([^:]+):(?:\s*(.*))?$')
        list_item_re = re.compile(r'^\-\s*(.*)$')
        for raw in lines:
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip())
            line = raw.lstrip()
            # pop stack to appropriate indent
            while stack and indent <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0]
            # list item?
            mlist = list_item_re.match(line)
            if mlist:
                val_raw = mlist.group(1)
                # ensure parent is a list at special key '__list__'
                if '__list__' not in parent or not isinstance(parent['__list__'], list):
                    parent['__list__'] = []
                v = parse_yaml_value(val_raw)
                parent['__list__'].append(v)
                # if value is mapping indicator (ends with ':') create nested dict
                if val_raw.endswith(':'):
                    newd = {}
                    parent['__list__'][-1] = newd
                    stack.append((newd, indent))
                continue
            m = key_re.match(line)
            if m:
                key = m.group(1).strip()
                val_raw = m.group(2)
                if val_raw is None or val_raw == '':
                    # nested mapping
                    newd: dict = {}
                    parent[key] = newd
                    stack.append((newd, indent))
                else:
                    parent[key] = parse_yaml_value(val_raw)
        # convert any '__list__' holders in root to proper lists recursively
        def clean(node):
            if isinstance(node, dict):
                if '__list__' in node and len(node) == 1:
                    return [clean(i) for i in node['__list__']]
                return {k: clean(v) for k, v in node.items()}
            elif isinstance(node, list):
                return [clean(i) for i in node]
            else:
                return node
        return clean(root)

    def parse_yaml_value(val_raw: str):
        v = val_raw.strip()
        if v == 'null':
            return None
        if v == 'true':
            return True
        if v == 'false':
            return False
        # quoted
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        # numeric?
        if re.fullmatch(r'-?\d+', v):
            try:
                return int(v)
            except:
                pass
        if re.fullmatch(r'-?\d+\.\d+', v):
            try:
                return float(v)
            except:
                pass
        return v

    # XML parser: recursive
    def parse_xml(s: str):
        # remove xml declaration
        s2 = re.sub(r'<\?xml[^>]*\?>', '', s)
        s2 = s2.strip()
        pos = 0
        length = len(s2)

        attr_re = re.compile(r'(\w+)=(["\'])([^"\']*)\2')

        def parse_node():
            nonlocal pos
            # skip whitespace
            while pos < length and s2[pos].isspace():
                pos += 1
            if pos >= length or s2[pos] != '<':
                return None
            # parse tag
            end_tag = s2.find('>', pos)
            if end_tag == -1:
                return None
            tag_content = s2[pos+1:end_tag].strip()
            self_closing = tag_content.endswith('/')
            if self_closing:
                tag_content = tag_content[:-1].strip()
            parts = tag_content.split()
            tag = parts[0] if parts else ''
            attrs = {}
            for m in attr_re.finditer(tag_content):
                attrs[m.group(1)] = m.group(3)
            pos = end_tag + 1
            if self_closing:
                node = attrs.copy()
                # if no attrs, represent empty tag as empty string per constraints
                if not node:
                    return {tag: ''}
                return {tag: attrs if attrs else ''}
            # gather children/text until closing tag
            children = {}
            text_parts: List[str] = []
            while True:
                # find next '<'
                if pos >= length:
                    break
                if s2[pos] == '<':
                    if s2.startswith('</', pos):
                        # closing tag
                        close_end = s2.find('>', pos)
                        pos = close_end + 1 if close_end != -1 else length
                        break
                    elif s2.startswith('<?', pos):
                        # skip processing instruction
                        pi_end = s2.find('?>', pos)
                        pos = pi_end + 2 if pi_end != -1 else length
                        continue
                    else:
                        child = parse_node()
                        if child:
                            # merge child into children
                            for k, v in child.items():
                                if k in children:
                                    # make list
                                    if not isinstance(children[k], list):
                                        children[k] = [children[k]]
                                    children[k].append(v)
                                else:
                                    children[k] = v
                        continue
                else:
                    # text
                    nxt = s2.find('<', pos)
                    if nxt == -1:
                        txt = s2[pos:].strip()
                        pos = length
                    else:
                        txt = s2[pos:nxt]
                        pos = nxt
                    if txt.strip():
                        text_parts.append(txt.strip())
            # assemble node
            node_value: Any
            if children:
                # merge attrs into children
                merged = {}
                merged.update(children)
                merged.update(attrs)
                node_value = merged
            else:
                if text_parts:
                    node_value = ' '.join(text_parts)
                else:
                    node_value = ''
                # if attrs exist, include them
                if attrs:
                    merged = attrs.copy()
                    merged['_text'] = node_value
                    node_value = merged
            return {tag: node_value}

        result = {}
        items = []
        while pos < length:
            # skip whitespace
            while pos < length and s2[pos].isspace():
                pos += 1
            if pos >= length:
                break
            node = parse_node()
            if node:
                for k, v in node.items():
                    if k in result:
                        # ensure list
                        if not isinstance(result[k], list):
                            result[k] = [result[k]]
                        result[k].append(v)
                    else:
                        result[k] = v
        return result

    # Flatten dict to dot notation
    def flatten(obj, prefix=''):
        out = {}
        if isinstance(obj, dict):
            for k in sorted(obj.keys()):
                v = obj[k]
                new_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    sub = flatten(v, new_key)
                    out.update(sub)
                elif isinstance(v, list):
                    # convert list to string representation
                    out[new_key] = json.dumps(v, sort_keys=True)
                else:
                    out[new_key] = v
        elif isinstance(obj, list):
            out[prefix] = json.dumps(obj, sort_keys=True)
        else:
            out[prefix] = obj
        return out

    # Build dependency graphs
    graph: Dict[str, List[str]] = defaultdict(list)  # node -> dependents
    reverse_graph: Dict[str, List[str]] = defaultdict(list)  # node -> dependencies
    nodes_set = set()
    for dep_pair in dependencies:
        if len(dep_pair) != 2:
            continue
        dependent, dependency = dep_pair[0], dep_pair[1]
        graph[dependency].append(dependent)
        reverse_graph[dependent].append(dependency)
        nodes_set.add(dependent); nodes_set.add(dependency)
    # sort adjacency lists for determinism
    for k in list(graph.keys()):
        graph[k] = sorted(graph[k])
    for k in list(reverse_graph.keys()):
        reverse_graph[k] = sorted(reverse_graph[k])

    # All services
    all_services = sorted(set(list(baseline_files.keys()) + list(current_files.keys())))

    if not baseline_files and not current_files:
        return {
            "report": [],
            "summary": {
                "total_services": 0,
                "affected_services": 0,
                "total_changes": 0,
                "services_with_dependents": 0
            },
            "affected_services": [],
            "impact_analysis": {}
        }

    # parse all files
    parsed_baseline: Dict[str, Any] = {}
    parsed_current: Dict[str, Any] = {}
    for svc in all_services:
        b = baseline_files.get(svc, '')
        c = current_files.get(svc, '')
        # parse baseline
        fmt_b = detect_format(b)
        if fmt_b == 'json':
            parsed_baseline[svc] = parse_json(b)
        elif fmt_b == 'xml':
            parsed_baseline[svc] = parse_xml(b)
        else:
            parsed_baseline[svc] = parse_yaml(b)
        # parse current
        fmt_c = detect_format(c)
        if fmt_c == 'json':
            parsed_current[svc] = parse_json(c)
        elif fmt_c == 'xml':
            parsed_current[svc] = parse_xml(c)
        else:
            parsed_current[svc] = parse_yaml(c)

    # flatten
    flat_baseline: Dict[str, Any] = {}
    flat_current: Dict[str, Any] = {}
    for svc in all_services:
        flat_baseline[svc] = flatten(parsed_baseline.get(svc, {}))
        flat_current[svc] = flatten(parsed_current.get(svc, {}))

    # line-by-line compare
    line_changes_by_service: Dict[str, List[Tuple[int, str, str]]] = {}
    for svc in all_services:
        b_raw = baseline_files.get(svc, '') or ''
        c_raw = current_files.get(svc, '') or ''
        b_lines = b_raw.split('\n')
        c_lines = c_raw.split('\n')
        maxlen = max(len(b_lines), len(c_lines))
        changes = []
        for i in range(maxlen):
            bline = b_lines[i].strip() if i < len(b_lines) else ''
            cline = c_lines[i].strip() if i < len(c_lines) else ''
            # types per constraints: only include 'modified' (both truthy and different)
            if bline and cline and bline != cline:
                changes.append((i+1, bline, cline))
        if changes:
            line_changes_by_service[svc] = changes

    # structural changes
    structural_changes_by_service: Dict[str, List[Tuple[str, Optional[str], Optional[str], str]]] = {}
    # tuple: (field, old, new, change_type) change_type in {'modified','added','removed'}
    for svc in all_services:
        fb = flat_baseline.get(svc, {})
        fc = flat_current.get(svc, {})
        keys = sorted(set(list(fb.keys()) + list(fc.keys())))
        changes = []
        for k in keys:
            old = fb.get(k)
            new = fc.get(k)
            exists_old = k in fb
            exists_new = k in fc
            if not exists_old and exists_new:
                changes.append((k, None, normalize_value(new), 'added'))
            elif exists_old and not exists_new:
                changes.append((k, normalize_value(old), None, 'removed'))
            else:
                # both exist
                if not equal_values(old, new):
                    changes.append((k, normalize_value(old), normalize_value(new), 'modified'))
        if changes:
            structural_changes_by_service[svc] = changes

    # helper value normalization for reporting
    def normalize_value(v):
        if v is None:
            return 'None'
        if isinstance(v, bool):
            return 'True' if v else 'False'
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return v
        try:
            return str(v)
        except:
            return json.dumps(v, sort_keys=True)

    def equal_values(a, b):
        # treat None, '' etc as different; lists already serialized as JSON strings
        if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
            return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        return a == b

    # transitive dependents BFS
    def get_transitive_dependents(svc: str) -> List[str]:
        q = deque(sorted(graph.get(svc, [])))
        visited = set()
        result = []
        while q:
            node = q.popleft()
            if node in visited:
                continue
            visited.add(node)
            result.append(node)
            # add dependents of node in sorted order
            for dep in sorted(graph.get(node, [])):
                if dep not in visited:
                    q.append(dep)
        return result

    # topological sort per constraints (Kahn)
    # nodes are union of all_services and nodes_set
    topo_nodes = sorted(set(all_services) | nodes_set)
    indeg = {n: 0 for n in topo_nodes}
    for src, dests in graph.items():
        for d in dests:
            indeg[d] = indeg.get(d, 0) + 1
    q = deque(sorted([n for n in topo_nodes if indeg.get(n, 0) == 0]))
    topo_order = []
    while q:
        n = q.popleft()
        topo_order.append(n)
        for m in sorted(graph.get(n, [])):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    # add remaining nodes not in topo_order, sorted
    remaining = [n for n in topo_nodes if n not in topo_order]
    topo_order.extend(sorted(remaining))

    # Ensure report order: process services in topological order, then services not in dependency graph sorted
    processed = set()
    report: List[str] = []
    impacted_services_set = set()
    total_changes = 0
    services_with_dependents = 0

    # helper to build impact message
    def impact_msg(svc):
        deps = sorted(graph.get(svc, []))
        if deps:
            return f"re-check needed for {deps[0]}."
        return "no further dependents."

    # first line-level modified changes across services in topo order
    for svc in topo_order:
        if svc not in all_services:
            continue
        if svc in line_changes_by_service:
            for (num, old, new) in line_changes_by_service[svc]:
                msg = f"{svc}: Line {num} changed from '{old}' to '{new}'; {impact_msg(svc)}"
                report.append(msg)
                total_changes += 1
            impacted_services_set.add(svc)
        processed.add(svc)

    # then structural changes per service in same order
    for svc in topo_order:
        if svc not in all_services:
            continue
        if svc in structural_changes_by_service:
            for (field, old, new, ctype) in structural_changes_by_service[svc]:
                if ctype == 'modified':
                    msg = f"{svc}: '{field}' changed from '{old}' to '{new}'; {impact_msg(svc)}"
                elif ctype == 'added':
                    msg = f"{svc}: New field '{field}' = '{new}'; ensures forward compatibility."
                else:  # removed
                    msg = f"{svc}: Field '{field}' removed (was '{old}'); {impact_msg(svc)}"
                report.append(msg)
                total_changes += 1
            impacted_services_set.add(svc)
        processed.add(svc)

    # Services not in dependency graph but in all_services should be processed too (already in topo as union)
    # Impact analysis: for each changed service, compute transitive dependents
    impact_analysis: Dict[str, List[str]] = {}
    for svc in sorted(list(impacted_services_set)):
        trans = get_transitive_dependents(svc)
        if trans:
            impact_analysis[svc] = trans
    # services_with_dependents count: number of services that have dependents in graph
    services_with_dependents = sum(1 for s in all_services if graph.get(s))
    # affected_services sorted alphabetically per constraints
    affected_services = sorted(list(impacted_services_set))

    summary = {
        "total_services": len(set(all_services)),
        "affected_services": len(affected_services),
        "total_changes": total_changes,
        "services_with_dependents": services_with_dependents
    }

    return {
        "report": report,
        "summary": summary,
        "affected_services": affected_services,
        "impact_analysis": impact_analysis
    }