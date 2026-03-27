from typing import Any, Callable, Dict, Iterable, List
import unicodedata

FNV_OFFSET_BASIS_64 = 0xCBF29CE484222325
FNV_PRIME_64 = 0x100000001B3


def fnv1a_64_bytes(data: bytes) -> int:
    """Deterministic 64-bit FNV-1a hash for bytes."""
    h = FNV_OFFSET_BASIS_64
    for b in data:
        h ^= b
        h = (h * FNV_PRIME_64) & 0xFFFFFFFFFFFFFFFF
    return h


def fnv1a_64_str(s: str) -> int:
    """Deterministic 64-bit FNV-1a hash for UTF-8 strings with NFC normalization."""
    normalized = unicodedata.normalize('NFC', s)
    return fnv1a_64_bytes(normalized.encode("utf-8"))


def hash_int64(x: int) -> int:
    """Deterministic 64-bit reduction for Python ints (mod 2^64)."""
    return x & 0xFFFFFFFFFFFFFFFF


def _type_tag(k: Any) -> int:
    """Assign a total-order tag for cross-type comparisons: int=0, str=1, bytes=2, else 9."""
    if isinstance(k, int):
        return 0
    if isinstance(k, str):
        return 1
    if isinstance(k, (bytes, bytearray)):
        return 2
    return 9


def _key_order_key(k: Any) -> List[Any]:
    """Produce a deterministic, totally-ordered sort key for supported key types."""
    tag = _type_tag(k)
    if tag == 0:
        return [tag, int(k)]
    if tag == 1:
        return [tag, k]
    if tag == 2:
        return [tag, bytes(k)]
    return [tag, repr(k)]


class _NamespaceTable:
    """A single namespace table with separate chaining and deterministic iteration."""

    def __init__(
        self,
        mode: str,
        hash_fn: Callable[[Any], int] = None,
        normalize_key: Callable[[Any], Any] = None,
        key_validator: Callable[[Any], None] = None,
        initial_capacity: int = 8,
        load_factor: float = 0.75,
    ) -> None:
        if mode not in ("map", "set"):
            raise ValueError("mode must be 'map' or 'set'")
        self.mode = mode
        self.hash_fn = hash_fn
        self.normalize_key = normalize_key
        self.key_validator = key_validator
        self.load_factor = load_factor
        cap = max(2, initial_capacity)
        # Buckets: list of lists of entries
        # Entry list: [orig_key, value_or_None, h64, canonical_key]
        self.buckets: List[List[List[Any]]] = [[] for _ in range(cap)]
        self.size = 0
        self.insertion_order: List[Any] = []  # Track insertion order for stable output
        self.insertion_counter = 0  # Global counter for insertion order
        self.key_to_insertion_idx: Dict[Any, int] = {}  # Map keys to insertion indices

    def _get_hash(self, key: Any) -> int:
        """Return unsigned 64-bit deterministic hash for a canonical key."""
        if self.hash_fn:
            return self.hash_fn(key) & 0xFFFFFFFFFFFFFFFF
        if isinstance(key, int):
            return hash_int64(key)
        if isinstance(key, str):
            return fnv1a_64_str(key)
        if isinstance(key, (bytes, bytearray)):
            return fnv1a_64_bytes(bytes(key))
        raise TypeError(f"Unsupported key type: {type(key)}")

    def _get_canonical_key(self, key: Any) -> Any:
        """Apply normalization if provided; otherwise return key as-is."""
        if self.normalize_key:
            key = self.normalize_key(key)
        return key

    def _validate_key(self, key: Any) -> None:
        """Validate key type and custom rules."""
        if self.key_validator:
            self.key_validator(key)
        if not isinstance(key, (int, str, bytes, bytearray)):
            raise TypeError(f"Unsupported key type: {type(key)}")

        # If normalize_key is present, its output must be supported too
        canon = self._get_canonical_key(key)
        if not isinstance(canon, (int, str, bytes, bytearray)):
            raise TypeError(
                f"normalize_key must return int|str|bytes|bytearray, got {type(canon)}"
            )

    def _find_entry(self, key: Any) -> List[int]:
        """Find entry by key (using canonical equality). Return [bucket_index, entry_index] or [-1, -1]."""
        self._validate_key(key)
        canonical = self._get_canonical_key(key)
        h = self._get_hash(canonical)
        bucket_idx = h % len(self.buckets)

        for i, entry in enumerate(self.buckets[bucket_idx]):
            if entry[3] == canonical:
                return [bucket_idx, i]
        return [-1, -1]

    def _resize_if_needed(self) -> None:
        """Double capacity when load factor threshold exceeded; re-bucket deterministically."""
        if self.size >= len(self.buckets) * self.load_factor:
            old_buckets = self.buckets
            new_cap = len(self.buckets) * 2
            self.buckets = [[] for _ in range(new_cap)]
            self.size = 0

            # Rehash all entries using stored 64-bit hash (deterministic)
            for bucket in old_buckets:
                for entry in bucket:
                    _, _, h, _ = entry
                    new_bucket_idx = h % len(self.buckets)
                    self.buckets[new_bucket_idx].append(list(entry))  # Convert to list
                    self.size += 1

    def put(self, key: Any, value: Any) -> None:
        """Insert or overwrite a key-value pair (map mode only)."""
        if self.mode != "map":
            raise ValueError("put() only available for map mode")
        self._validate_key(key)
        canonical = self._get_canonical_key(key)
        h = self._get_hash(canonical)

        find_result = self._find_entry(key)
        bucket_idx, entry_idx = find_result[0], find_result[1]
        if entry_idx >= 0:
            orig_key = self.buckets[bucket_idx][entry_idx][0]
            self.buckets[bucket_idx][entry_idx] = [orig_key, value, h, canonical]
        else:
            bucket_idx = h % len(self.buckets)
            self.buckets[bucket_idx].append([key, value, h, canonical])
            self.insertion_order.append(key)
            self.key_to_insertion_idx[key] = len(self.insertion_order) - 1
            self.size += 1
            self._resize_if_needed()

    def get(self, key: Any) -> Any:
        """Retrieve value for key or raise KeyError (map mode only)."""
        if self.mode != "map":
            raise ValueError("get() only available for map mode")
        find_result = self._find_entry(key)
        bucket_idx, entry_idx = find_result[0], find_result[1]
        if entry_idx >= 0:
            return self.buckets[bucket_idx][entry_idx][1]
        raise KeyError(key)

    def update(self, key: Any, value: Any) -> None:
        """Update value for existing key; raise KeyError if missing (map mode only)."""
        if self.mode != "map":
            raise ValueError("update() only available for map mode")
        find_result = self._find_entry(key)
        bucket_idx, entry_idx = find_result[0], find_result[1]
        if entry_idx >= 0:
            canonical = self._get_canonical_key(key)
            h = self._get_hash(canonical)
            orig_key = self.buckets[bucket_idx][entry_idx][0]
            self.buckets[bucket_idx][entry_idx] = [orig_key, value, h, canonical]
            # Keep original key unchanged
        else:
            raise KeyError(key)

    def remove(self, key: Any) -> None:
        """Remove key-value pair; raise KeyError if missing (map mode only)."""
        if self.mode != "map":
            raise ValueError("remove() only available for map mode")
        find_result = self._find_entry(key)
        bucket_idx, entry_idx = find_result[0], find_result[1]
        if entry_idx >= 0:
            self.buckets[bucket_idx].pop(entry_idx)
            # Don't remove from insertion_order to preserve order for deleted keys
            self.size -= 1
        else:
            raise KeyError(key)

    def add(self, key: Any) -> None:
        """Add key to set (set mode only)."""
        if self.mode != "set":
            raise ValueError("add() only available for set mode")
        self._validate_key(key)
        canonical = self._get_canonical_key(key)
        h = self._get_hash(canonical)

        find_result = self._find_entry(key)
        bucket_idx, entry_idx = find_result[0], find_result[1]
        if entry_idx < 0:
            bucket_idx = h % len(self.buckets)
            self.buckets[bucket_idx].append([key, None, h, canonical])
            self.insertion_order.append(key)
            self.key_to_insertion_idx[key] = len(self.insertion_order) - 1
            self.size += 1
            self._resize_if_needed()

    def contains(self, key: Any) -> bool:
        """Check if key is in set (set mode only)."""
        if self.mode != "set":
            raise ValueError("contains() only available for set mode")
        find_result = self._find_entry(key)
        return find_result[1] >= 0

    def discard(self, key: Any) -> None:
        """Remove key from set; no error if missing (set mode only)."""
        if self.mode != "set":
            raise ValueError("discard() only available for set mode")
        find_result = self._find_entry(key)
        bucket_idx, entry_idx = find_result[0], find_result[1]
        if entry_idx >= 0:
            self.buckets[bucket_idx].pop(entry_idx)
            # Don't remove from insertion_order to preserve order for deleted keys (consistent with remove)
            self.size -= 1

    def get_size(self) -> int:
        """Return number of entries."""
        return self.size

    def bulk_load(self, entries: Iterable) -> None:
        """Bulk load entries deterministically."""
        for entry in entries:
            if self.mode == "map":
                if isinstance(entry, list) and len(entry) >= 2:
                    self.put(entry[0], entry[1])
            else:  # set
                self.add(entry)

    def snapshot(self) -> list:
        """Return deterministic snapshot with stable ordering."""
        entries = []
        for bucket_idx, bucket in enumerate(self.buckets):
            for entry in bucket:
                orig_key, value, h, canonical = entry[0], entry[1], entry[2], entry[3]
                entries.append([orig_key, value, h, canonical, bucket_idx])

        # Sort: bucket_idx (primary), hash, canonical key, insertion order
        def get_sort_key(e):
            orig_key, value, h, canonical, bucket_idx = e[0], e[1], e[2], e[3], e[4]
            # Use O(1) dictionary lookup instead of O(N) list.index()
            insertion_idx = self.key_to_insertion_idx.get(orig_key, len(self.key_to_insertion_idx))
            
            return [bucket_idx, h, _key_order_key(canonical), insertion_idx]
        
        entries.sort(key=get_sort_key)

        if self.mode == "map":
            return [[orig_key, value] for orig_key, value, _, _, _ in entries]
        else:
            return [orig_key for orig_key, _, _, _, _ in entries]


class AnthroHashTable:
    """Deterministic, namespaced hash-table system (Map/Set) with JSON-safe snapshot."""

    def __init__(self, config: Dict[str, Dict[str, Any]] = None):
        self.namespaces: Dict[str, _NamespaceTable] = {}
        if config:
            for ns_name, ns_config in config.items():
                # Support JSON-friendly normalize modes
                norm = ns_config.get("normalize_key")
                if isinstance(norm, str):
                    if norm == "case_insensitive":
                        def _nk(x):
                            return unicodedata.normalize('NFC', x).lower() if isinstance(x, str) else x
                        norm_func = _nk
                    elif norm == "nfc":
                        def _nk(x):
                            return unicodedata.normalize('NFC', x) if isinstance(x, str) else x
                        norm_func = _nk
                    elif norm == "none":
                        norm_func = None
                    else:
                        norm_func = None
                else:
                    norm_func = ns_config.get("normalize_key")

                self.namespaces[ns_name] = _NamespaceTable(
                    mode=ns_config.get("mode", "map"),
                    hash_fn=ns_config.get("hash_fn"),
                    normalize_key=norm_func,
                    key_validator=ns_config.get("key_validator"),
                )

    def _get_namespace(self, ns: str) -> _NamespaceTable:
        if ns not in self.namespaces:
            raise ValueError(f"Invalid operation: Namespace '{ns}' not found")
        return self.namespaces[ns]

    def put(self, ns: str, key: Any, value: Any) -> None:
        """Insert or overwrite in a map namespace."""
        if self._has_circular_reference(value, set()):
            raise ValueError("Invalid value: circular reference to table")
        self._get_namespace(ns).put(key, value)

    def get(self, ns: str, key: Any) -> Any:
        """Get from a map namespace."""
        return self._get_namespace(ns).get(key)

    def update(self, ns: str, key: Any, value: Any) -> None:
        """Update existing key in a map namespace."""
        if self._has_circular_reference(value, set()):
            raise ValueError("Invalid value: circular reference to table")
        self._get_namespace(ns).update(key, value)

    def _has_circular_reference(self, obj: Any, visited: set) -> bool:
        """Check for circular references that point to this hash table instance."""
        if id(obj) in visited:
            return True
        visited.add(id(obj))

        if isinstance(obj, dict):
            if obj is self:
                return True
            return any(self._has_circular_reference(v, visited) for v in obj.values())
        elif isinstance(obj, list):
            return any(self._has_circular_reference(item, visited) for item in obj)
        return False

    def remove(self, ns: str, key: Any) -> None:
        """Remove from a map namespace."""
        self._get_namespace(ns).remove(key)

    def add(self, ns: str, key: Any) -> None:
        """Add to a set namespace."""
        self._get_namespace(ns).add(key)

    def contains(self, ns: str, key: Any) -> bool:
        """Check membership in a set namespace."""
        return self._get_namespace(ns).contains(key)

    def discard(self, ns: str, key: Any) -> None:
        """Discard from a set namespace."""
        self._get_namespace(ns).discard(key)

    def keys(self, ns: str) -> Iterable[Any]:
        """Deterministic keys iteration for a namespace."""
        return self._get_namespace(ns).keys()

    def values(self, ns: str) -> Iterable[Any]:
        """Deterministic values iteration for a map namespace."""
        return self._get_namespace(ns).values()

    def items(self, ns: str) -> Iterable[List[Any]]:
        """Deterministic items iteration for a map namespace."""
        return self._get_namespace(ns).items()

    def size(self, ns: str = None) -> int:
        """Total size or per-namespace size."""
        if ns is None:
            return sum(table.get_size() for table in self.namespaces.values())
        return self._get_namespace(ns).get_size()

    def bulk_load(self, ns: str, entries: Iterable) -> None:
        """Bulk load into a namespace with deterministic semantics."""
        for entry in entries:
            if isinstance(entry, list) and len(entry) >= 2:
                value = entry[1]
                if self._has_circular_reference(value, set()):
                    raise ValueError("Invalid value: circular reference to table")

        self._get_namespace(ns).bulk_load(entries)

    def snapshot(self) -> Dict[str, Any]:
        """Return deterministic snapshot with stable structure per Constraint 10."""
        result: Dict[str, Any] = {}
        for ns_name in sorted(self.namespaces.keys()):  # Constraint 11: lexicographic namespace order
            table = self.namespaces[ns_name]
            ns_data = []
            for item in table.snapshot():
                if isinstance(item, list):
                    # Map mode: [key, value] - return as list [key, value]
                    ns_data.append(item)
                else:
                    # Set mode: key only - return as list item
                    ns_data.append(item)
            result[ns_name] = ns_data
        return result


def build_anthro_hash_table(config: Dict[str, Dict[str, Any]] = None):
    """
    Initialize and return a deterministic, namespaced hash-table system.

    Args:
        config: Per-namespace configuration

    Returns:
        AnthroHashTable object
    """
    return AnthroHashTable(config or {})


def execute_hash_table_commands(
    config: Dict[str, Dict[str, Any]],
    commands: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute a sequence of deterministic hash table commands and return
    the final snapshot across all namespaces.
    """
    # Create table
    h = AnthroHashTable(config)

    # Execute commands
    for cmd in commands:
        op = cmd.get("op")
        ns = cmd.get("ns")

        if op == "put":
            h.put(ns, cmd.get("key"), cmd.get("value"))
        elif op == "get":
            h.get(ns, cmd.get("key"))
        elif op == "update":
            h.update(ns, cmd.get("key"), cmd.get("value"))
        elif op == "remove":
            h.remove(ns, cmd.get("key"))
        elif op == "add":
            h.add(ns, cmd.get("key"))
        elif op == "contains":
            h.contains(ns, cmd.get("key"))
        elif op == "discard":
            h.discard(ns, cmd.get("key"))
        elif op == "keys":
            h.keys(ns)
        elif op == "values":
            h.values(ns)
        elif op == "items":
            h.items(ns)
        elif op == "size":
            h.size(ns)
        elif op == "bulk_load":
            # entries: for map [[k,v], ...]; for set [k1, k2, ...]
            h.bulk_load(ns, cmd.get("entries"))
        elif op == "snapshot":
            return h.snapshot()

    # If no snapshot command, return current state
    return h.snapshot()


if __name__ == "__main__":
    # Demo usage
    result = execute_hash_table_commands(
        config={
            "artifacts": {"mode": "map"},
            "linguistics": {"mode": "set", "normalize_key": "case_insensitive"},
            "genetics": {"mode": "map"}
        },
        commands=[
            {"op": "put", "ns": "artifacts", "key": 101, "value": {"name": "Vessel-A", "era": "Late Formative"}},
            {"op": "put", "ns": "artifacts", "key": "AX-42", "value": {"name": "Obsidian Blade"}},
            {"op": "add", "ns": "linguistics", "key": "nahuatl"},
            {"op": "add", "ns": "linguistics", "key": "QUECHUA"},
            {"op": "put", "ns": "genetics", "key": "Haplogroup B2", "value": {"freq": 0.27}},
            {"op": "snapshot"}
        ]
    )
    print("Snapshot:", result)