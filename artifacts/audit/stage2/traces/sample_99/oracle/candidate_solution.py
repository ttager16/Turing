from typing import Dict, List


# System type constants
SYSTEM_TYPE_SERVER = 1
SYSTEM_TYPE_WORKSTATION = 2
SYSTEM_TYPE_DATABASE = 3
SYSTEM_TYPE_NETWORK_DEVICE = 4
SYSTEM_TYPE_SECURITY_APPLIANCE = 5

# Validation range constants
MAX_PATH_LENGTH = 50
MIN_SYSTEM_TYPE = 1
MAX_SYSTEM_TYPE = 5
MIN_PRIVILEGE_LEVEL = 1
MAX_PRIVILEGE_LEVEL = 4
MIN_SECURITY_LEVEL = 1
MAX_SECURITY_LEVEL = 5
MIN_TRUST_LEVEL = 1
MAX_TRUST_LEVEL = 10


def analyze_network_vulnerability(
    network: Dict[str, List[List[int]]],
    vulnerability_scores: Dict[str, float],
    system_types: Dict[str, int],
    privilege_levels: Dict[str, int],
    source_system: int,
    target_systems: List[int],
    vulnerability_threshold: float,
    max_path_length: int,
    threat_model: str,
    use_recursive: bool,
) -> Dict[str, List[List[int]]]:
    """
    Analyze network and return critical attack paths per target.
    
    This function serves as the main entry point and creates an analyzer instance.
    """
    analyzer = NetworkVulnerabilityAnalyzer(
        network, vulnerability_scores, system_types, privilege_levels, threat_model
    )
    return analyzer.analyze(
        source_system,
        target_systems,
        vulnerability_threshold,
        max_path_length,
        use_recursive,
    )


class NetworkVulnerabilityAnalyzer:
    """Analyzer for finding critical attack paths in network systems."""

    def __init__(
        self,
        network: Dict[str, List[List[int]]],
        vulnerability_scores: Dict[str, float],
        system_types: Dict[str, int],
        privilege_levels: Dict[str, int],
        threat_model: str,
    ):
        """Initialize the analyzer with network configuration."""
        self.network = network
        self.vulnerability_scores = vulnerability_scores
        self.system_types = system_types
        self.privilege_levels = privilege_levels
        self.threat_model = threat_model
        self.coefficient = self._get_threat_coefficient(threat_model)

    def _get_threat_coefficient(self, model: str) -> float:
        """Get the coefficient for the threat model."""
        if model == "insider":
            return 1.5
        if model == "external":
            return 0.8
        return 2.0

    def _allowed_type(self, dst_type: int, src_type: int) -> bool:
        """Check if system type transition is allowed."""
        if src_type == SYSTEM_TYPE_SERVER:
            return True
        if src_type == SYSTEM_TYPE_WORKSTATION:
            return dst_type in (SYSTEM_TYPE_SERVER, SYSTEM_TYPE_DATABASE)
        if src_type == SYSTEM_TYPE_DATABASE:
            return dst_type in (SYSTEM_TYPE_SERVER, SYSTEM_TYPE_WORKSTATION)
        if src_type == SYSTEM_TYPE_NETWORK_DEVICE:
            return True
        if src_type == SYSTEM_TYPE_SECURITY_APPLIANCE:
            return dst_type in (SYSTEM_TYPE_SERVER, SYSTEM_TYPE_NETWORK_DEVICE)
        return False

    def _allowed_privilege(self, dst_priv: int, src_priv: int) -> bool:
        """Check if privilege level transition is allowed."""
        return dst_priv <= src_priv or dst_priv == src_priv + 1

    def _calculate_edge_score(
        self, dst: str, sec_level: int, trust_level: int
    ) -> float:
        """Calculate vulnerability score for an edge."""
        base = self.vulnerability_scores[dst]
        return base * (sec_level / float(trust_level)) * self.coefficient

    def _validate_attribute_in_dict(
        self, attr_dict: Dict[str, int], attr_name: str, min_val: int, max_val: int
    ) -> Dict[str, str]:
        """Validate all values in an attribute dictionary are within range."""
        for _, val in attr_dict.items():
            if val < min_val or val > max_val:
                return {"error": f"Invalid {attr_name}"}
        return {}

    def _validate_connected_systems(
        self, attr_dict: Dict[str, object], attr_name: str
    ) -> Dict[str, str]:
        """Validate all connected systems exist in the attribute dictionary."""
        for _, neighbors in self.network.items():
            for edge in neighbors:
                if len(edge) < 3:
                    continue
                v = str(edge[0])
                if v not in attr_dict:
                    return {"error": f"Connected system not found in {attr_name}"}
        return {}

    def _validate_targets_in_dict(
        self, target_systems: List[int], attr_dict: Dict[str, object], attr_name: str
    ) -> Dict[str, str]:
        """Validate all target systems exist in the attribute dictionary."""
        for t in target_systems:
            if str(t) not in attr_dict:
                return {"error": f"Target system not found in {attr_name}"}
        return {}

    def _validate_inputs(
        self,
        source_system: int,
        target_systems: List[int],
        vulnerability_threshold: float,
        max_path_length: int,
    ) -> Dict[str, str]:
        """Validate all input parameters."""
        # Basic validations
        if str(source_system) not in self.network:
            return {"error": "Source system not found in network"}
        if self.threat_model not in ["insider", "external", "apt"]:
            return {"error": "Invalid threat model"}
        if max_path_length < 1 or max_path_length > MAX_PATH_LENGTH:
            return {"error": "Invalid max_path_length"}
        if vulnerability_threshold < 0:
            return {"error": "Invalid vulnerability_threshold"}

        # System type and privilege level ranges
        error = self._validate_attribute_in_dict(
            self.system_types, "system_type", MIN_SYSTEM_TYPE, MAX_SYSTEM_TYPE
        )
        if error:
            return error
        error = self._validate_attribute_in_dict(
            self.privilege_levels, "privilege_level", MIN_PRIVILEGE_LEVEL, MAX_PRIVILEGE_LEVEL
        )
        if error:
            return error

        # Source presence in attribute dicts
        if str(source_system) not in self.vulnerability_scores:
            return {"error": "Source system not found in vulnerability_scores"}
        if str(source_system) not in self.system_types:
            return {"error": "Source system not found in system_types"}
        if str(source_system) not in self.privilege_levels:
            return {"error": "Source system not found in privilege_levels"}

        # Validate all targets exist in network first
        for t in target_systems:
            if str(t) not in self.network:
                return {"error": "Target system not found in network"}

        # Validate edge ranges
        for _, neighbors in self.network.items():
            for edge in neighbors:
                if len(edge) < 3:
                    continue
                sec = edge[1]
                tr = edge[2]
                if sec < MIN_SECURITY_LEVEL or sec > MAX_SECURITY_LEVEL:
                    return {"error": "Invalid connection_security_level"}
                if tr < MIN_TRUST_LEVEL or tr > MAX_TRUST_LEVEL:
                    return {"error": "Invalid trust_level"}

        # Validate connected systems (before targets as per spec)
        error = self._validate_connected_systems(
            self.vulnerability_scores, "vulnerability_scores"
        )
        if error:
            return error
        error = self._validate_targets_in_dict(
            target_systems, self.vulnerability_scores, "vulnerability_scores"
        )
        if error:
            return error

        error = self._validate_connected_systems(self.system_types, "system_types")
        if error:
            return error
        error = self._validate_targets_in_dict(
            target_systems, self.system_types, "system_types"
        )
        if error:
            return error

        error = self._validate_connected_systems(
            self.privilege_levels, "privilege_levels"
        )
        if error:
            return error
        error = self._validate_targets_in_dict(
            target_systems, self.privilege_levels, "privilege_levels"
        )
        if error:
            return error

        return {}

    def _dfs_recursive(
        self,
        u: int,
        path: List[int],
        score: float,
        targets_set: set,
        vulnerability_threshold: float,
        max_path_length: int,
        results_paths: Dict[int, List[Dict[str, object]]],
    ) -> None:
        """Recursive DFS to find attack paths."""
        if u in targets_set and score >= vulnerability_threshold:
            results_paths[u].append({"path": list(path), "score": score})

        if len(path) >= max_path_length:
            return

        for edge in self.network.get(str(u), []):
            if len(edge) < 3:
                continue
            v = edge[0]
            sec = edge[1]
            tr = edge[2]

            # Avoid cycles
            if v in path:
                continue

            # Type and privilege checks
            if not self._allowed_type(
                self.system_types[str(v)], self.system_types[str(u)]
            ):
                continue
            if not self._allowed_privilege(
                self.privilege_levels[str(v)], self.privilege_levels[str(u)]
            ):
                continue

            next_score = score + self._calculate_edge_score(str(v), sec, tr)
            path.append(v)
            self._dfs_recursive(
                v,
                path,
                next_score,
                targets_set,
                vulnerability_threshold,
                max_path_length,
                results_paths,
            )
            path.pop()

    def _dfs_iterative(
        self,
        source_system: int,
        targets_set: set,
        vulnerability_threshold: float,
        max_path_length: int,
        results_paths: Dict[int, List[Dict[str, object]]],
    ) -> None:
        """Iterative DFS using explicit stack to find attack paths."""
        path: List[int] = [source_system]
        cum_scores: List[float] = [0.0]
        stack: List[Dict[str, int]] = [{"node": source_system, "idx": 0}]

        while len(stack) > 0:
            top = stack[-1]
            u = top["node"]
            idx = top["idx"]
            neighbors = self.network.get(str(u), [])

            if (
                u in targets_set
                and idx == 0
                and cum_scores[-1] >= vulnerability_threshold
            ):
                results_paths[u].append(
                    {"path": list(path), "score": cum_scores[-1]}
                )

            if len(path) >= max_path_length or idx >= len(neighbors):
                stack.pop()
                if len(path) > 1:
                    path.pop()
                    cum_scores.pop()
                continue

            # Advance to next neighbor
            edge = neighbors[idx]
            top["idx"] = idx + 1
            if len(edge) < 3:
                continue
            v = edge[0]
            sec = edge[1]
            tr = edge[2]

            # Skip invalid moves
            if v in path:
                continue
            if not self._allowed_type(
                self.system_types[str(v)], self.system_types[str(u)]
            ):
                continue
            if not self._allowed_privilege(
                self.privilege_levels[str(v)], self.privilege_levels[str(u)]
            ):
                continue

            next_score = cum_scores[-1] + self._calculate_edge_score(str(v), sec, tr)
            path.append(v)
            cum_scores.append(next_score)
            stack.append({"node": v, "idx": 0})

    def analyze(
        self,
        source_system: int,
        target_systems: List[int],
        vulnerability_threshold: float,
        max_path_length: int,
        use_recursive: bool,
    ) -> Dict[str, List[List[int]]]:
        """Analyze network and return critical attack paths per target."""
        # Input validation
        error = self._validate_inputs(
            source_system, target_systems, vulnerability_threshold, max_path_length
        )
        if error:
            return error

        targets_set = set(target_systems)
        results_paths: Dict[int, List[Dict[str, object]]] = {
            t: [] for t in targets_set
        }

        # Execute DFS based on mode
        if use_recursive:
            self._dfs_recursive(
                source_system,
                [source_system],
                0.0,
                targets_set,
                vulnerability_threshold,
                max_path_length,
                results_paths,
            )
        else:
            self._dfs_iterative(
                source_system,
                targets_set,
                vulnerability_threshold,
                max_path_length,
                results_paths,
            )

        # Format and sort results
        final_out: Dict[str, List[List[int]]] = {}

        for t in targets_set:
            items = results_paths.get(t, [])

            # Filter by threshold and length
            filtered: List[Dict[str, object]] = []
            for it in items:
                p: List[int] = it["path"]
                s: float = it["score"]
                if s >= vulnerability_threshold and len(p) <= max_path_length:
                    filtered.append({"path": p, "score": s})

            filtered.sort(key=lambda itm: itm["path"])  # secondary key first
            filtered.sort(key=lambda itm: itm["score"], reverse=True)

            only_paths: List[List[int]] = [itm["path"] for itm in filtered]
            final_out[str(t)] = only_paths

        # Ensure all requested targets appear, even if no paths found
        for t in target_systems:
            key = str(t)
            if key not in final_out:
                final_out[key] = []

        return final_out


if __name__ == "__main__":
    network = {
        '0': [[1, 2, 5], [2, 3, 4]],
        '1': [[3, 1, 8], [4, 4, 3]],
        '2': [[4, 2, 6]],
        '3': [[4, 3, 7]],
        '4': []
    }
    vulnerability_scores = {'0': 2.5, '1': 4.0, '2': 3.2, '3': 5.1, '4': 1.8}
    system_types = {'0': 1, '1': 2, '2': 1, '3': 3, '4': 1}
    privilege_levels = {'0': 2, '1': 1, '2': 2, '3': 3, '4': 2}
    source_system = 0
    target_systems = [4]
    vulnerability_threshold = 3.0
    max_path_length = 5
    threat_model = "insider"
    use_recursive = True

    print(analyze_network_vulnerability(network, vulnerability_scores, system_types, privilege_levels, source_system, target_systems, vulnerability_threshold, max_path_length, threat_model, use_recursive))