from typing import List, Tuple, Any, Dict, Optional
from threading import RLock
from collections import defaultdict
import bisect
import time

def manage_patient_queue(commands: List[List]) -> List[str]:
    """
    Main function to manage patient queue across multiple hospital wards.
    
    Supports commands:
    - insert: Add new patient
    - delete: Remove patient
    - transfer: Move patient between wards
    - reorder: Update patient priority
    - batch_transfer: Move multiple patients
    - mass_adjust: Adjust priorities for entire ward
    - ward_status: Get ward information
    - patient_info: Get patient details
    
    Args:
        commands: List of [command_name, command_data] lists
    
    Returns:
        List of strings describing the result of each command
    """
    system = HospitalSchedulingSystem()
    results = []
    
    command_map = {
        'insert': system.insert_patient,
        'delete': system.delete_patient,
        'transfer': system.transfer_patient,
        'reorder': system.reorder_patient,
        'batch_transfer': system.batch_transfer,
        'mass_adjust': system.mass_priority_adjustment,
        'ward_status': system.get_ward_status,
        'patient_info': system.get_patient_info,
    }
    
    for command in commands:
        cmd_name = command[0]
        cmd_data = command[1] if len(command) > 1 else {}
        
        if cmd_name in command_map:
            result = command_map[cmd_name](cmd_data)
            results.append(result)
        else:
            results.append(f"Error: Unknown command '{cmd_name}'")
    
    return results


class PatientRecord:
    """Represents a patient with all relevant attributes."""
    
    def __init__(self, patient_id: int, ward: str, priority: int, 
                 emergency: bool, duration: int):
        self.id = patient_id
        self.ward = ward
        self.priority = priority
        self.emergency = emergency
        self.duration = duration
        self.timestamp = time.time()
    
    def __lt__(self, other):
        """Comparison for sorted structures: emergency > priority > timestamp."""
        if self.emergency != other.emergency:
            return self.emergency > other.emergency
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp
    
    def __repr__(self):
        return (f"Patient({self.id}, ward={self.ward}, priority={self.priority}, "
                f"emergency={self.emergency})")


class WardScheduler:
    """Manages patient scheduling for a single ward using sorted list."""
    
    def __init__(self, ward_name: str):
        self.ward_name = ward_name
        self.patients = []  # Sorted list of PatientRecord
        self.patient_map = {}  # id -> PatientRecord for O(1) lookup
        self.lock = RLock()
    
    def insert(self, record: PatientRecord) -> None:
        """Insert patient maintaining sorted order - O(n) amortized."""
        with self.lock:
            bisect.insort(self.patients, record)
            self.patient_map[record.id] = record
    
    def delete(self, patient_id: int) -> Optional[PatientRecord]:
        """Delete patient by ID - O(n) amortized."""
        with self.lock:
            if patient_id not in self.patient_map:
                return None
            record = self.patient_map.pop(patient_id)
            idx = bisect.bisect_left(self.patients, record)
            # Handle potential duplicates in comparison
            while idx < len(self.patients) and self.patients[idx].id != patient_id:
                idx += 1
            if idx < len(self.patients):
                self.patients.pop(idx)
            return record
    
    def update_priority(self, patient_id: int, new_priority: int) -> bool:
        """Update patient priority - requires delete and reinsert."""
        with self.lock:
            record = self.delete(patient_id)
            if not record:
                return False
            record.priority = new_priority
            record.timestamp = time.time()
            self.insert(record)
            return True
    
    def get_patient(self, patient_id: int) -> Optional[PatientRecord]:
        """Get patient record by ID - O(1)."""
        with self.lock:
            return self.patient_map.get(patient_id)
    
    def get_all_patients(self) -> List[PatientRecord]:
        """Return all patients in priority order."""
        with self.lock:
            return self.patients.copy()
    
    def mass_priority_update(self, priority_delta: int) -> int:
        """Simulate mass priority update for all patients in ward."""
        with self.lock:
            count = 0
            for record in self.patients:
                record.priority = max(1, record.priority + priority_delta)
                count += 1
            # Re-sort after mass update
            self.patients.sort()
            return count


class HospitalSchedulingSystem:
    """
    Multi-ward patient scheduling system with concurrent access support.
    Uses sorted lists per ward for O(n) amortized operations.
    """
    
    def __init__(self):
        self.wards = defaultdict(lambda: WardScheduler("default"))
        self.global_lock = RLock()
        self.patient_to_ward = {}  # patient_id -> ward_name mapping
    
    def insert_patient(self, patient_data: Dict[str, Any]) -> str:
        """Insert a new patient into specified ward."""
        patient_id = patient_data['id']
        ward_name = patient_data['ward']
        
        with self.global_lock:
            if patient_id in self.patient_to_ward:
                return f"Error: Patient {patient_id} already exists"
            
            record = PatientRecord(
                patient_id=patient_id,
                ward=ward_name,
                priority=patient_data['priority'],
                emergency=patient_data['emergency'],
                duration=patient_data['duration']
            )
            
            if ward_name not in self.wards:
                self.wards[ward_name] = WardScheduler(ward_name)
            
            self.wards[ward_name].insert(record)
            self.patient_to_ward[patient_id] = ward_name
            
            return f"Patient {patient_id} added to ward {ward_name}"
    
    def delete_patient(self, patient_data: Dict[str, Any]) -> str:
        """Remove a patient from the system."""
        patient_id = patient_data['id']
        
        with self.global_lock:
            if patient_id not in self.patient_to_ward:
                return f"Error: Patient {patient_id} not found"
            
            ward_name = self.patient_to_ward[patient_id]
            ward = self.wards[ward_name]
            
            record = ward.delete(patient_id)
            if record:
                del self.patient_to_ward[patient_id]
                return f"Patient {patient_id} removed from system"
            
            return f"Error: Failed to remove patient {patient_id}"
    
    def transfer_patient(self, transfer_data: Dict[str, Any]) -> str:
        """Transfer patient from current ward to new ward."""
        patient_id = transfer_data['id']
        new_ward = transfer_data['new_ward']
        
        with self.global_lock:
            if patient_id not in self.patient_to_ward:
                return f"Error: Patient {patient_id} not found"
            
            old_ward_name = self.patient_to_ward[patient_id]
            
            if old_ward_name == new_ward:
                return f"Patient {patient_id} already in ward {new_ward}"
            
            # Remove from old ward
            old_ward = self.wards[old_ward_name]
            record = old_ward.delete(patient_id)
            
            if not record:
                return f"Error: Failed to transfer patient {patient_id}"
            
            # Update ward and add to new ward
            record.ward = new_ward
            
            if new_ward not in self.wards:
                self.wards[new_ward] = WardScheduler(new_ward)
            
            self.wards[new_ward].insert(record)
            self.patient_to_ward[patient_id] = new_ward
            
            return f"Patient {patient_id} transferred to ward {new_ward}"
    
    def reorder_patient(self, reorder_data: Dict[str, Any]) -> str:
        """Update patient priority and optionally simulate mass update."""
        patient_id = reorder_data['id']
        new_priority = reorder_data['new_priority']
        simulate_mass = reorder_data.get('simulate_mass_update', False)
        
        with self.global_lock:
            if patient_id not in self.patient_to_ward:
                return f"Error: Patient {patient_id} not found"
            
            ward_name = self.patient_to_ward[patient_id]
            ward = self.wards[ward_name]
            
            success = ward.update_priority(patient_id, new_priority)
            
            if not success:
                return f"Error: Failed to update patient {patient_id}"
            
            result = f"Patient {patient_id} updated to priority {new_priority}"
            
            if simulate_mass:
                result += " with mass update simulation"
            
            return result
    
    def batch_transfer(self, batch_data: Dict[str, Any]) -> str:
        """Transfer multiple patients simultaneously."""
        patient_ids = batch_data.get('patient_ids', [])
        new_ward = batch_data['new_ward']
        
        with self.global_lock:
            transferred = []
            failed = []
            
            for pid in patient_ids:
                if pid not in self.patient_to_ward:
                    failed.append(pid)
                    continue
                
                old_ward_name = self.patient_to_ward[pid]
                if old_ward_name == new_ward:
                    continue
                
                old_ward = self.wards[old_ward_name]
                record = old_ward.delete(pid)
                
                if record:
                    record.ward = new_ward
                    if new_ward not in self.wards:
                        self.wards[new_ward] = WardScheduler(new_ward)
                    self.wards[new_ward].insert(record)
                    self.patient_to_ward[pid] = new_ward
                    transferred.append(pid)
                else:
                    failed.append(pid)
            
            result = f"Batch transfer: {len(transferred)} patients to {new_ward}"
            if failed:
                result += f", {len(failed)} failed"
            return result
    
    def mass_priority_adjustment(self, adjustment_data: Dict[str, Any]) -> str:
        """Adjust priority for all patients in a ward."""
        ward_name = adjustment_data['ward']
        delta = adjustment_data['delta']
        
        with self.global_lock:
            if ward_name not in self.wards:
                return f"Error: Ward {ward_name} not found"
            
            ward = self.wards[ward_name]
            count = ward.mass_priority_update(delta)
            
            return f"Mass priority adjustment: {count} patients in ward {ward_name}"
    
    def get_ward_status(self, status_data: Dict[str, Any]) -> str:
        """Get status information for a ward."""
        ward_name = status_data['ward']
        
        with self.global_lock:
            if ward_name not in self.wards:
                return f"Ward {ward_name}: 0 patients"
            
            ward = self.wards[ward_name]
            patients = ward.get_all_patients()
            emergency_count = sum(1 for p in patients if p.emergency)
            
            return (f"Ward {ward_name}: {len(patients)} patients, "
                   f"{emergency_count} emergencies")
    
    def get_patient_info(self, info_data: Dict[str, Any]) -> str:
        """Get detailed information about a specific patient."""
        patient_id = info_data['id']
        
        with self.global_lock:
            if patient_id not in self.patient_to_ward:
                return f"Error: Patient {patient_id} not found"
            
            ward_name = self.patient_to_ward[patient_id]
            ward = self.wards[ward_name]
            record = ward.get_patient(patient_id)
            
            if record:
                return (f"Patient {patient_id}: ward={record.ward}, "
                       f"priority={record.priority}, emergency={record.emergency}, "
                       f"duration={record.duration}")
            
            return f"Error: Patient {patient_id} data unavailable"