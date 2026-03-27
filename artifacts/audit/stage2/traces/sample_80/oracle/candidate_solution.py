from typing import List, Any
from collections import defaultdict
import re

def manage_device_logs(device_logs: List[List[Any]]) -> List[List[Any]]:
    """
    Manage device logs with multi-step reconciliation process.
    
    Rules (applied in order):
    1. Duplicate Entry: Remove logs with payload exactly equal to "duplicate_entry"
    2. Stale Data: Remove logs where newer_timestamp - timestamp > 1 for same device
    3. Reference Validation: REF_<device_id>_<timestamp> must reference existing valid logs
    4. Order Preservation: Maintain original order of valid logs
    
    Args:
        device_logs: List of logs [device_id, timestamp, payload]
    
    Returns:
        List of valid logs after applying all rules
    """
    if not device_logs:
        return []
    
    # Helper function to parse references
    def parse_references(payload: str) -> List[tuple]:
        """Extract references in format REF_<device_id>_<timestamp>"""
        # Pattern requires at least 10 digits for timestamp to avoid false matches
        pattern = r'REF_([a-zA-Z0-9_]+)_(\d{10,})'
        matches = re.findall(pattern, payload)
        return [(device_id, int(timestamp)) for device_id, timestamp in matches]
    
    def has_malformed_reference(payload: str) -> bool:
        """Check if payload has malformed REF_ patterns"""
        # Find all REF_ patterns
        potential_refs = re.findall(r'REF_[a-zA-Z0-9_]+(?:_\d*)?', payload)
        valid_refs = re.findall(r'REF_[a-zA-Z0-9_]+_\d{10,}', payload)
        
        # If there are REF_ patterns that don't match the valid format, it's malformed
        return len(potential_refs) > len(valid_refs)
    
    # Step 1: Remove explicit duplicates (payload == "duplicate_entry")
    logs_after_duplicate_removal = []
    for log in device_logs:
        if log[2] != "duplicate_entry":
            logs_after_duplicate_removal.append(log)
    
    # Step 2: Remove stale data (Δ_stale = 1)
    # Stale logs are removed regardless of whether they're referenced
    device_max_timestamp = defaultdict(lambda: float('-inf'))
    for log in logs_after_duplicate_removal:
        device_id = log[0]
        timestamp = log[1]
        device_max_timestamp[device_id] = max(device_max_timestamp[device_id], timestamp)
    
    logs_after_stale_removal = []
    for log in logs_after_duplicate_removal:
        device_id = log[0]
        timestamp = log[1]
        max_timestamp = device_max_timestamp[device_id]
        
        # A log is stale if: newer_timestamp - timestamp > Δ_stale (where Δ_stale = 1)
        if max_timestamp - timestamp > 1:
            continue  # Skip stale log
        
        logs_after_stale_removal.append(log)
    
    # Step 3: Iteratively validate references (cascade removal)
    current_logs = logs_after_stale_removal
    
    while True:
        # Build set of valid log keys
        valid_log_keys = set()
        for log in current_logs:
            device_id = log[0]
            timestamp = log[1]
            valid_log_keys.add((device_id, timestamp))
        
        # Validate references
        next_logs = []
        removed_any = False
        
        for log in current_logs:
            payload = log[2]
            
            # Check for malformed references first
            if has_malformed_reference(payload):
                removed_any = True
                continue
            
            references = parse_references(payload)
            
            # If log has references, validate them
            if references:
                all_refs_valid = True
                for ref_device_id, ref_timestamp in references:
                    if (ref_device_id, ref_timestamp) not in valid_log_keys:
                        all_refs_valid = False
                        break
                
                # Only keep log if all references are valid
                if all_refs_valid:
                    next_logs.append(log)
                else:
                    removed_any = True
            else:
                # No references, so it's valid
                next_logs.append(log)
        
        # If no logs were removed, we're done
        if not removed_any:
            break
        
        current_logs = next_logs
    
    return current_logs