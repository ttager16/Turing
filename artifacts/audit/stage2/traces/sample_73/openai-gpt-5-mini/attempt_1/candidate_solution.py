def fnv1a_64(data: bytes) -> int:
    h = 0xcbf29ce484222325
    fnv_prime = 0x100000001b3
    for b in data:
        h ^= b
        h = (h * fnv_prime) & 0xFFFFFFFFFFFFFFFF
    return h

def str_to_bytes_for_hash(s: str) -> bytes:
    return s.encode('utf-8')

def normalize_string_nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)

def default_key_validator(key: Any) -> None:
    if not isinstance(key, (int, str, bytes)):
        raise TypeError("Invalid operation: unsupported key type")

def detect_circular_ref(value: Any, roots: Tuple[int, ...]) -> None:
    # roots: ids of namespace tables to consider as forbidden in values
    seen = set()
    def _walk(v):
        vid = id(v)
        if vid in seen:
            return
        if vid in roots:
            raise ValueError("Invalid value: circular reference to table")
        seen.add(vid)
        if isinstance(v, dict):
            for k, vv in v.items():
                _walk(k); _walk(vv)
        elif isinstance(v, (list, tuple, set)):
            for vv in v:
                _walk(vv)
        # primitives ignored
    _walk(value)

class Entry:
    __slots__ = ('norm_key', 'orig_key', 'value', 'hash64', 'insert_idx')
    def __init__(self, norm_key, orig_key, value, hash64, insert_idx):
        self.norm_key = norm_key
        self.orig_key = orig_key
        self.value = value
        self.hash64 = hash64
        self.insert_idx = insert_idx

class NamespaceTable:
    def __init__(self, name: str, cfg: Dict[str, Any]):
        self.name = name
        mode = cfg.get('mode')
        if mode not in ('map', 'set'):
            raise ValueError("Invalid configuration: mode must be 'map' or 'set'")
        self.mode = mode
        self.hash_fn: Optional[Callable[[Any], int]] = cfg.get('hash_fn')
        self.key_validator: Optional[Callable[[Any], None]] = cfg.get('key_validator')
        self.value_validator: Optional[Callable[[Any], None]] = cfg.get('value_validator')
        nk = cfg.get('normalize_key', 'nfc')
        if nk not in ('none', 'nfc', 'case_insensitive'):
            raise ValueError("Invalid configuration: normalize_key must be 'none', 'nfc', or 'case_insensitive'")
        self.normalize_mode = nk
        self.capacity = 8  # start small but >= power of two
        self.buckets: List[List[Entry]] = [[] for _ in range(self.capacity)]
        self.size = 0
        self.insert_counter = 0
        # for circular detection: mark this table id
        self._id_marker = id(self)
    def _apply_key_validator(self, key: Any) -> None:
        if self.key_validator:
            self.key_validator(key)
        else:
            default_key_validator(key)
    def _normalize_key(self, key: Any):
        if isinstance(key, str):
            s = normalize_string_nfc(key)
            if self.normalize_mode == 'case_insensitive':
                s = s.lower()
            # if normalize_mode == 'none' we still apply NFC per spec default applied to strings regardless
            return s
        return key
    def _hash_key(self, key: Any) -> int:
        if self.hash_fn:
            return self.hash_fn(key) & 0xFFFFFFFFFFFFFFFF
        if isinstance(key, int):
            return key & 0xFFFFFFFFFFFFFFFF
        if isinstance(key, str):
            b = str_to_bytes_for_hash(key)
            return fnv1a_64(b)
        if isinstance(key, bytes):
            return fnv1a_64(key)
        raise TypeError("Invalid operation: unsupported key type")
    def _bucket_index(self, hash64: int) -> int:
        return hash64 & (self.capacity - 1)
    def _find_entry(self, norm_key, hash64) -> Optional[Entry]:
        idx = self._bucket_index(hash64)
        bucket = self.buckets[idx]
        for e in bucket:
            if e.hash64 == hash64 and e.norm_key == norm_key:
                return e
        return None
    def _maybe_resize(self):
        if self.size <= 0:
            return
        if self.size / self.capacity > 0.75:
            old_buckets = self.buckets
            old_capacity = self.capacity
            self.capacity *= 2
            self.buckets = [[] for _ in range(self.capacity)]
            # reinsert preserving stable order per bucket and entry ordering
            for b in old_buckets:
                for e in b:
                    idx = self._bucket_index(e.hash64)
                    self.buckets[idx].append(e)
    def put(self, key: Any, value: Any):
        if self.mode != 'map':
            raise ValueError("Invalid operation: put not supported for set namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        # circular detection: value must not reference this table
        detect_circular_ref(value, (self._id_marker,))
        if self.value_validator:
            self.value_validator(value)
        existing = self._find_entry(norm, h)
        if existing:
            # idempotent update: replace value
            existing.value = value
            return
        ent = Entry(norm, key, value, h, self.insert_counter)
        self.insert_counter += 1
        idx = self._bucket_index(h)
        self.buckets[idx].append(ent)
        self.size += 1
        self._maybe_resize()
    def get(self, key: Any):
        if self.mode != 'map':
            raise ValueError("Invalid operation: get not supported for set namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        e = self._find_entry(norm, h)
        if e:
            return e.value
        return None
    def remove(self, key: Any):
        if self.mode != 'map':
            raise ValueError("Invalid operation: remove not supported for set namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        idx = self._bucket_index(h)
        bucket = self.buckets[idx]
        for i, e in enumerate(bucket):
            if e.hash64 == h and e.norm_key == norm:
                bucket.pop(i)
                self.size -= 1
                return
    def update(self, key: Any, func: Callable[[Any], Any]):
        if self.mode != 'map':
            raise ValueError("Invalid operation: update not supported for set namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        e = self._find_entry(norm, h)
        if not e:
            raise KeyError("Invalid operation: key not found")
        new_val = func(e.value)
        detect_circular_ref(new_val, (self._id_marker,))
        if self.value_validator:
            self.value_validator(new_val)
        e.value = new_val
    def add(self, key: Any):
        if self.mode != 'set':
            raise ValueError("Invalid operation: add not supported for map namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        existing = self._find_entry(norm, h)
        if existing:
            return
        ent = Entry(norm, key, None, h, self.insert_counter)
        self.insert_counter += 1
        idx = self._bucket_index(h)
        self.buckets[idx].append(ent)
        self.size += 1
        self._maybe_resize()
    def contains(self, key: Any) -> bool:
        if self.mode != 'set':
            raise ValueError("Invalid operation: contains not supported for map namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        return self._find_entry(norm, h) is not None
    def discard(self, key: Any):
        if self.mode != 'set':
            raise ValueError("Invalid operation: discard not supported for map namespace")
        self._apply_key_validator(key)
        norm = self._normalize_key(key)
        h = self._hash_key(norm)
        idx = self._bucket_index(h)
        bucket = self.buckets[idx]
        for i, e in enumerate(bucket):
            if e.hash64 == h and e.norm_key == norm:
                bucket.pop(i)
                self.size -= 1
                return
    def bulk_load(self, entries: List[Any]):
        if self.mode == 'map':
            for pair in entries:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError("Invalid operation: bulk_load entries for map must be [key, value] pairs")
                self.put(pair[0], pair[1])
        else:
            for k in entries:
                self.add(k)
    def snapshot_entries(self) -> List[Any]:
        out = []
        # ordering: by bucket index (0..capacity-1), then by 64-bit hash value, then by canonical key, then insertion idx
        for bucket_idx in range(self.capacity):
            bucket = self.buckets[bucket_idx]
            # sort bucket deterministically per rules
            def sort_key(e: Entry):
                # canonical key: for deterministic ordering use repr of normalized key for cross-type stability
                canon = e.norm_key
                # For bytes, ensure stable representation
                if isinstance(canon, bytes):
                    canon_repr = ('bytes', canonical_bytes_repr(canon))
                elif isinstance(canon, str):
                    canon_repr = ('str', canon)
                else:
                    canon_repr = ('int', canon)
                return (e.hash64, canon_repr, e.insert_idx)
            sorted_bucket = sorted(bucket, key=sort_key)
            for e in sorted_bucket:
                if self.mode == 'map':
                    out.append([e.orig_key, e.value])
                else:
                    out.append(e.orig_key)
        return out

def canonical_bytes_repr(b: bytes) -> str:
    # deterministic hex
    return ''.join(f'{x:02x}' for x in b)

def execute_hash_table_commands(
    config: Dict[str, Dict[str, Any]],
    commands: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute a sequence of deterministic hash table commands and return
    the final snapshot across all namespaces.
    """
    # initialize namespaces
    namespaces: Dict[str, NamespaceTable] = {}
    for ns_name, cfg in config.items():
        if not isinstance(ns_name, str):
            raise TypeError("Invalid configuration: namespace names must be strings")
        namespaces[ns_name] = NamespaceTable(ns_name, cfg or {})
    # process commands
    last_snapshot: Optional[Dict[str, Any]] = None
    for cmd in commands:
        if not isinstance(cmd, dict):
            raise TypeError("Invalid operation: command must be a dict")
        op = cmd.get('op')
        if op is None:
            raise ValueError("Invalid operation: missing 'op'")
        if op == 'snapshot':
            # build snapshot at this point (but final return only returns final snapshot after all commands)
            snap = {}
            for ns_name in sorted(namespaces.keys()):
                ns = namespaces[ns_name]
                snap[ns_name] = ns.snapshot_entries()
            last_snapshot = snap
            continue
        ns_name = cmd.get('ns')
        if ns_name not in namespaces:
            raise KeyError(f"Invalid operation: unknown namespace '{ns_name}'")
        ns = namespaces[ns_name]
        if op == 'put':
            if 'key' not in cmd or 'value' not in cmd:
                raise ValueError("Invalid operation: put requires 'key' and 'value'")
            ns.put(cmd['key'], cmd['value'])
        elif op == 'get':
            if 'key' not in cmd:
                raise ValueError("Invalid operation: get requires 'key'")
            _ = ns.get(cmd['key'])
        elif op == 'remove':
            if 'key' not in cmd:
                raise ValueError("Invalid operation: remove requires 'key'")
            ns.remove(cmd['key'])
        elif op == 'update':
            if 'key' not in cmd or 'func' not in cmd:
                raise ValueError("Invalid operation: update requires 'key' and 'func'")
            func = cmd['func']
            if not callable(func):
                raise TypeError("Invalid operation: update 'func' must be callable")
            ns.update(cmd['key'], func)
        elif op == 'add':
            if 'key' not in cmd:
                raise ValueError("Invalid operation: add requires 'key'")
            ns.add(cmd['key'])
        elif op == 'contains':
            if 'key' not in cmd:
                raise ValueError("Invalid operation: contains requires 'key'")
            _ = ns.contains(cmd['key'])
        elif op == 'discard':
            if 'key' not in cmd:
                raise ValueError("Invalid operation: discard requires 'key'")
            ns.discard(cmd['key'])
        elif op == 'bulk_load':
            entries = cmd.get('entries')
            if entries is None:
                raise ValueError("Invalid operation: bulk_load requires 'entries'")
            ns.bulk_load(entries)
        elif op == 'size':
            # return size maybe ignored; validate existence
            _ = ns.size
        else:
            raise ValueError(f"Invalid operation: unknown op '{op}'")
    # final snapshot: if last_snapshot set from explicit snapshot, return final state after all commands (per spec final snapshot)
    final_snap = {}
    for ns_name in sorted(namespaces.keys()):
        ns = namespaces[ns_name]
        final_snap[ns_name] = ns.snapshot_entries()
    return final_snap