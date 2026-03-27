# main.py
from typing import Dict, List, Tuple, Any, Optional
import json
import re


class ConfigParser:
    """
    Multi-format configuration parser supporting JSON, YAML, and XML.
    Implements custom parsing without external libraries.
    """

    @staticmethod
    def detect_format(content: str) -> str:
        """Detect the format of configuration content."""
        content = content.strip()
        if content.startswith('{') or content.startswith('['):
            return 'json'
        elif content.startswith('<'):
            return 'xml'
        else:
            # Default to YAML for key: value patterns
            return 'yaml'

    @staticmethod
    def parse_json(content: str) -> Dict[str, Any]:
        """Parse JSON content into a structured dictionary."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def parse_yaml(content: str) -> Dict[str, Any]:
        """
        Parse YAML content using a custom lightweight parser.
        Handles basic YAML structures without external libraries.
        """
        result = {}
        lines = content.split('\n')
        stack = [(result, -1)]  # (current_dict, indent_level)

        for line in lines:
            if not line.strip() or line.strip().startswith('#'):
                continue

            # Calculate indentation
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()

            # Pop stack until we find the right parent
            while len(stack) > 1 and stack[-1][1] >= indent:
                stack.pop()

            current_dict = stack[-1][0]

            if ':' in stripped:
                key, sep, value = stripped.partition(':')
                key = key.strip()
                value = value.strip()

                if not value:
                    # This is a nested object
                    new_dict = {}
                    current_dict[key] = new_dict
                    stack.append((new_dict, indent))
                else:
                    # Parse the value
                    current_dict[key] = ConfigParser._parse_yaml_value(value)

        return result

    @staticmethod
    def _parse_yaml_value(value: str) -> Any:
        """Parse YAML value into appropriate Python type."""
        value = value.strip()
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        elif value.lower() == 'null':
            return None
        elif value.isdigit():
            return int(value)
        elif value.replace('.', '', 1).isdigit():
            return float(value)
        else:
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                return value[1:-1]
            return value

    @staticmethod
    def parse_xml(content: str) -> Dict[str, Any]:
        """
        Parse XML content into a structured dictionary.
        Custom lightweight XML parser without external libraries.
        """
        result = {}
        # Remove XML declaration if present
        content = re.sub(r'<\?xml.*?\?>', '', content)
        content = content.strip()

        def parse_element(text: str) -> Tuple[Optional[Dict], str]:
            """Parse a single XML element."""
            text = text.strip()
            if not text.startswith('<'):
                return None, text

            # Find the opening tag
            tag_end = text.find('>')
            if tag_end == -1:
                return None, text

            tag_content = text[1:tag_end]
            # Handle self-closing tags
            if tag_content.endswith('/'):
                tag_name = tag_content[:-1].strip().split()[0]
                attrs = ConfigParser._parse_xml_attributes(tag_content)
                return {tag_name: attrs if attrs else ''}, text[tag_end + 1:]

            tag_name = tag_content.split()[0]
            attrs = ConfigParser._parse_xml_attributes(tag_content)

            # Find the closing tag
            closing_tag = f'</{tag_name}>'
            closing_pos = text.find(closing_tag)
            if closing_pos == -1:
                return None, text

            # Extract content between tags
            inner_content = text[tag_end + 1:closing_pos].strip()
            remaining = text[closing_pos + len(closing_tag):]

            # Check if inner content has child elements
            if '<' in inner_content:
                children = {}
                temp_content = inner_content
                while temp_content.strip():
                    child, temp_content = parse_element(temp_content)
                    if child is None:
                        break
                    for k, v in child.items():
                        if k in children:
                            # Handle multiple children with same tag
                            if not isinstance(children[k], list):
                                children[k] = [children[k]]
                            children[k].append(v)
                        else:
                            children[k] = v

                if attrs:
                    children.update(attrs)
                return {tag_name: children if children else inner_content}, remaining
            else:
                # Leaf node with text content
                value = inner_content if inner_content else (attrs if attrs else '')
                return {tag_name: value}, remaining

        temp_content = content
        while temp_content.strip():
            element, temp_content = parse_element(temp_content)
            if element is None:
                break
            result.update(element)

        return result

    @staticmethod
    def _parse_xml_attributes(tag_content: str) -> Dict[str, str]:
        """Extract attributes from an XML tag."""
        attrs = {}
        # Simple attribute parsing
        attr_pattern = r'(\w+)=(["\'])([^"\']*)\2'
        matches = re.findall(attr_pattern, tag_content)
        for match in matches:
            attrs[match[0]] = match[2]
        return attrs

    @staticmethod
    def parse(content: str) -> Dict[str, Any]:
        """Auto-detect format and parse configuration content."""
        format_type = ConfigParser.detect_format(content)
        if format_type == 'json':
            return ConfigParser.parse_json(content)
        elif format_type == 'xml':
            return ConfigParser.parse_xml(content)
        else:
            return ConfigParser.parse_yaml(content)


class DependencyGraph:
    """
    Manages service dependency relationships and enables topological analysis.
    Supports dependency propagation for change impact assessment.
    """

    def __init__(self):
        self.graph = {}  # node -> list of nodes that depend on it
        self.reverse_graph = {}  # node -> list of nodes it depends on
        self.nodes = set()

    def add_dependency(self, dependent: str, dependency: str):
        """Add a dependency relationship: dependent depends on dependency."""
        self.nodes.add(dependent)
        self.nodes.add(dependency)

        if dependency not in self.graph:
            self.graph[dependency] = []
        self.graph[dependency].append(dependent)

        if dependent not in self.reverse_graph:
            self.reverse_graph[dependent] = []
        self.reverse_graph[dependent].append(dependency)

    def get_dependents(self, node: str) -> List[str]:
        """Get all nodes that depend on the given node."""
        return self.graph.get(node, [])

    def get_dependencies(self, node: str) -> List[str]:
        """Get all nodes that the given node depends on."""
        return self.reverse_graph.get(node, [])

    def get_transitive_dependents(self, node: str) -> List[str]:
        """Get all nodes transitively affected by changes to the given node."""
        visited = set()
        queue = [node]
        result = []

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current != node:
                result.append(current)

            # Sort dependents before adding to queue for deterministic order
            unvisited_dependents = sorted([
                dep for dep in self.get_dependents(current)
                if dep not in visited
            ])
            queue.extend(unvisited_dependents)

        return result

    def topological_sort(self) -> List[str]:
        """Return nodes in topological order (dependencies before dependents)."""
        # Sort nodes for deterministic iteration
        sorted_nodes = sorted(self.nodes)
        in_degree = {node: 0 for node in sorted_nodes}

        for node in sorted_nodes:
            for dependent in self.get_dependents(node):
                in_degree[dependent] += 1

        # Use sorted list for deterministic queue initialization
        queue = sorted([node for node in sorted_nodes if in_degree[node] == 0])
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Collect and sort dependents before adding to queue for determinism
            ready_dependents = []
            for dependent in self.get_dependents(node):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready_dependents.append(dependent)

            # Add in sorted order to maintain determinism
            queue.extend(sorted(ready_dependents))

        return result


class ConfigDiffer:
    """
    Core diffing engine that compares configurations and generates change reports.
    Handles multi-level nested structures and tracks change lineage.
    """

    def __init__(self):
        self.changes = []

    def flatten_config(self, config: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """
        Flatten nested configuration into dot-notation paths.
        Example: {"a": {"b": 1}} -> {"a.b": 1}
        """
        result = {}

        for key, value in config.items():
            new_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                result.update(self.flatten_config(value, new_key))
            elif isinstance(value, list):
                result[new_key] = str(value)
            else:
                result[new_key] = value

        return result

    def compare_configs(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compare two configuration dictionaries and return a list of changes.
        Each change includes the field path, old value, new value, and change type.
        """
        changes = []

        baseline_flat = self.flatten_config(baseline)
        current_flat = self.flatten_config(current)

        all_keys = set(baseline_flat.keys()) | set(current_flat.keys())

        for key in sorted(all_keys):
            old_value = baseline_flat.get(key)
            new_value = current_flat.get(key)

            if old_value is None and new_value is not None:
                changes.append({
                    'type': 'added',
                    'field': key,
                    'old_value': None,
                    'new_value': new_value
                })
            elif old_value is not None and new_value is None:
                changes.append({
                    'type': 'removed',
                    'field': key,
                    'old_value': old_value,
                    'new_value': None
                })
            elif old_value != new_value:
                changes.append({
                    'type': 'modified',
                    'field': key,
                    'old_value': old_value,
                    'new_value': new_value
                })

        return changes

    def compare_raw_lines(self, baseline: str, current: str) -> List[Dict[str, Any]]:
        """
        Compare raw configuration strings line by line.
        Returns line-level differences with line numbers.
        """
        baseline_lines = baseline.split('\n')
        current_lines = current.split('\n')

        changes = []

        # Use a simple LCS-based diff algorithm
        max_len = max(len(baseline_lines), len(current_lines))

        for i in range(max_len):
            baseline_line = baseline_lines[i] if i < len(baseline_lines) else None
            current_line = current_lines[i] if i < len(current_lines) else None

            if baseline_line != current_line:
                if baseline_line and current_line:
                    changes.append({
                        'type': 'modified',
                        'line_number': i + 1,
                        'old_line': baseline_line.strip(),
                        'new_line': current_line.strip()
                    })
                elif baseline_line and not current_line:
                    changes.append({
                        'type': 'removed',
                        'line_number': i + 1,
                        'old_line': baseline_line.strip(),
                        'new_line': None
                    })
                elif not baseline_line and current_line:
                    changes.append({
                        'type': 'added',
                        'line_number': i + 1,
                        'old_line': None,
                        'new_line': current_line.strip()
                    })

        return changes


class ComplianceReporter:
    """
    Generates comprehensive compliance reports with dependency impact analysis.
    Formats change information in human-readable format with cascading effects.
    """

    def __init__(self, dependency_graph: DependencyGraph):
        self.dependency_graph = dependency_graph

    def format_change_message(
        self,
        service: str,
        change: Dict[str, Any],
        line_change: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format a single change into a human-readable message."""
        change_type = change.get('type', 'unknown')

        if line_change:
            line_num = line_change.get('line_number', 'unknown')
            old_line = line_change.get('old_line', '')
            new_line = line_change.get('new_line', '')

            return f"{service}: Line {line_num} changed from '{old_line}' to '{new_line}'"

        field = change.get('field', 'unknown')
        old_value = change.get('old_value')
        new_value = change.get('new_value')

        if change_type == 'added':
            return f"{service}: New field '{field}' = '{new_value}'"
        elif change_type == 'removed':
            return f"{service}: Field '{field}' removed (was '{old_value}')"
        elif change_type == 'modified':
            return f"{service}: '{field}' changed from '{old_value}' to '{new_value}'"

        return f"{service}: Unknown change to '{field}'"

    def add_dependency_impact(self, message: str, service: str) -> str:
        """Add dependency impact information to a change message."""
        dependents = self.dependency_graph.get_dependents(service)

        if dependents:
            # Get immediate dependents
            immediate = dependents[0] if dependents else None
            if immediate:
                return f"{message}; re-check needed for {immediate}."

        return f"{message}; no further dependents."

    def generate_report(
        self,
        service_changes: Dict[str, Tuple[List[Dict], List[Dict]]]
    ) -> List[str]:
        """
        Generate a comprehensive compliance report.
        service_changes: Dict mapping service name to (structural_changes, line_changes)
        """
        report = []

        # Process services in topological order (dependencies first)
        service_order = self.dependency_graph.topological_sort()

        # Add services not in dependency graph
        all_services = set(service_changes.keys())
        for service in all_services:
            if service not in service_order:
                service_order.append(service)

        for service in service_order:
            if service not in service_changes:
                continue

            structural_changes, line_changes = service_changes[service]

            # Prioritize line changes with actual content modifications
            if line_changes:
                for line_change in line_changes:
                    if line_change.get('type') == 'modified':
                        message = self.format_change_message(service, {}, line_change)
                        message = self.add_dependency_impact(message, service)
                        report.append(message)

            # Add structural changes
            for change in structural_changes:
                message = self.format_change_message(service, change)

                # Add special notes for certain change types
                if change.get('type') == 'added':
                    message += "; ensures forward compatibility."
                else:
                    message = self.add_dependency_impact(message, service)

                report.append(message)

        return report


def string_diff_algorithm(
    baseline_files: Dict[str, str],
    current_files: Dict[str, str],
    dependencies: List[List[str]]
) -> Dict[str, Any]:
    """
    Main entry point for distributed configuration diffing system.

    Analyzes configuration changes across multiple services, considering their
    dependency relationships, and generates a comprehensive compliance report.

    Args:
        baseline_files: Dictionary mapping service identifiers to baseline configuration strings
        current_files: Dictionary mapping service identifiers to current configuration strings
        dependencies: List of [dependent, dependency] pairs defining service relationships

    Returns:
        Dictionary containing:
            - 'report': List of human-readable change messages
            - 'summary': Dictionary with statistics about changes
            - 'affected_services': List of services with changes
            - 'impact_analysis': Dictionary mapping services to their affected dependents
    """
    # Initialize components
    parser = ConfigParser()
    differ = ConfigDiffer()
    dep_graph = DependencyGraph()

    # Build dependency graph
    for dependent, dependency in dependencies:
        dep_graph.add_dependency(dependent, dependency)

    # Analyze changes for each service
    service_changes = {}
    affected_services = []
    total_changes = 0

    # Use sorted list instead of set to ensure deterministic iteration order
    all_services = sorted(set(baseline_files.keys()) | set(current_files.keys()))

    for service in all_services:
        baseline = baseline_files.get(service, "")
        current = current_files.get(service, "")

        if baseline == current:
            continue

        # Parse configurations
        baseline_parsed = parser.parse(baseline)
        current_parsed = parser.parse(current)

        # Perform structural comparison
        structural_changes = differ.compare_configs(baseline_parsed, current_parsed)

        # Perform line-by-line comparison
        line_changes = differ.compare_raw_lines(baseline, current)

        if structural_changes or line_changes:
            service_changes[service] = (structural_changes, line_changes)
            affected_services.append(service)
            total_changes += len(structural_changes) + len(line_changes)

    # Generate compliance report
    reporter = ComplianceReporter(dep_graph)
    report = reporter.generate_report(service_changes)

    # Build impact analysis
    impact_analysis = {}
    for service in affected_services:
        transitive_deps = dep_graph.get_transitive_dependents(service)
        if transitive_deps:
            impact_analysis[service] = transitive_deps

    # Compile summary statistics
    summary = {
        'total_services': len(all_services),
        'affected_services': len(affected_services),
        'total_changes': total_changes,
        'services_with_dependents': len(impact_analysis)
    }

    return {
        'report': report,
        'summary': summary,
        'affected_services': affected_services,
        'impact_analysis': impact_analysis
    }


# Example usage
if __name__ == "__main__":
    baseline_files = {
        "serviceA": "<service>\n  <host>10.0.0.1</host>\n  <port>8080</port>\n</service>",
        "serviceB": "{\n    \"apiVersion\": \"v1\",\n    \"endpoint\": \"/data\"\n}",
        "serviceC": "server:\n  address: 192.168.1.1\n  features:\n    caching: true\n"
    }

    current_files = {
        "serviceA": "<service>\n  <host>10.0.0.2</host>\n  <port>8080</port>\n</service>",
        "serviceB": "{\n    \"apiVersion\": \"v2\",\n    \"endpoint\": \"/data\",\n    \"extra\": \"param\"\n}",
        "serviceC": "server:\n  address: 192.168.1.1\n  features:\n    caching: false\n"
    }

    dependencies = [
        ["serviceA", "serviceB"],
        ["serviceB", "serviceC"]
    ]

    result = string_diff_algorithm(baseline_files, current_files, dependencies)
    print(result)