from typing import List, Dict, Optional, Tuple, Set, Any
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


class ScheduleStatus(Enum):
    """Status codes for schedule validation"""
    SUCCESS = "success"
    PARTIAL_ASSIGNMENT = "partial_assignment"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    BUFFER_VIOLATION = "buffer_violation"
    NO_AVAILABLE_ACTORS = "no_available_actors"
    INVALID_INPUT = "invalid_input"


@dataclass
class SceneAssignment:
    """Represents a complete scene assignment with metadata"""
    scene_id: str
    time_slot: int
    role_assignments: Dict[str, List[str]]
    assigned_actors: Set[str]
    status: ScheduleStatus
    missing_roles: List[str] = field(default_factory=list)
    
    def is_complete(self) -> bool:
        """Checks if all required roles are filled"""
        return self.status == ScheduleStatus.SUCCESS and len(self.missing_roles) == 0


@dataclass
class ActorScheduleState:
    """Comprehensive tracking of actor's scheduling state"""
    name: str
    assigned_scenes: int = 0
    capacity: int = 10
    scheduled_time_slots: List[int] = field(default_factory=list)
    scene_assignments: Dict[str, str] = field(default_factory=dict)
    
    def can_accept_scene(self) -> bool:
        """Checks if actor has capacity for another scene"""
        return self.assigned_scenes < self.capacity
    
    def get_utilization(self) -> float:
        """Returns current workload ratio"""
        return self.assigned_scenes / self.capacity if self.capacity > 0 else 1.0


class OptimizationWeights:
    """Configurable weights for optimization formula"""
    
    def __init__(self, 
                 availability_weight: float = 2.0,
                 role_fit_weight: float = 1.5,
                 workload_penalty: float = 0.3,
                 travel_penalty: float = 0.1,
                 name_penalty: float = 0.001):
        self.availability_weight = availability_weight
        self.role_fit_weight = role_fit_weight
        self.workload_penalty = workload_penalty
        self.travel_penalty = travel_penalty
        self.name_penalty = name_penalty
    
    def get_config(self) -> Dict[str, float]:
        """Returns current weight configuration"""
        return {
            'availability_weight': self.availability_weight,
            'role_fit_weight': self.role_fit_weight,
            'workload_penalty': self.workload_penalty,
            'travel_penalty': self.travel_penalty,
            'name_penalty': self.name_penalty
        }


class EnhancedAvailabilityAnalyzer:
    """Advanced probability calculation including travel fatigue and role preference"""
    
    def __init__(self, 
                 historical_data: Dict[str, List[int]],
                 role_mapping: Dict[str, Dict[str, float]]):
        self.historical_data = historical_data or {}
        self.role_mapping = role_mapping or {}
        self.recency_weight = 0.4
        self.cache = {}
    
    def calculate_base_availability(self, actor: str) -> float:
        """Calculates base probability from historical attendance"""
        if actor not in self.historical_data or not self.historical_data[actor]:
            return 0.5
        
        try:
            attendance = self.historical_data[actor]
            if len(attendance) == 0:
                return 0.5
            
            overall_rate = sum(attendance) / len(attendance)
            recent_window = min(3, len(attendance))
            recent_rate = sum(attendance[-recent_window:]) / recent_window
            
            base_prob = ((1 - self.recency_weight) * overall_rate + 
                        self.recency_weight * recent_rate)
            return max(0.0, min(1.0, base_prob))
        except (ZeroDivisionError, TypeError, ValueError):
            return 0.5
    
    def calculate_role_preference_bonus(self, actor: str, role: str) -> float:
        """Calculates role preference adjustment based on suitability"""
        if actor in self.role_mapping and role in self.role_mapping[actor]:
            suitability = self.role_mapping[actor][role]
            return (suitability - 0.5) * 0.2
        return 0.0
    
    def calculate_travel_fatigue_penalty(self, 
                                        actor: str,
                                        current_assignments: int,
                                        travel_load: float) -> float:
        """Calculates fatigue penalty based on workload and travel"""
        fatigue_factor = current_assignments * 0.05
        travel_factor = travel_load * 0.03
        return min(0.3, fatigue_factor + travel_factor)
    
    def calculate_comprehensive_probability(self,
                                           actor: str,
                                           role: str,
                                           current_assignments: int = 0,
                                           travel_load: float = 0.0) -> float:
        """
        Comprehensive probability calculation including:
        - Base historical availability
        - Role preference adjustment
        - Travel fatigue penalty
        """
        base_availability = self.calculate_base_availability(actor)
        role_bonus = self.calculate_role_preference_bonus(actor, role)
        fatigue_penalty = self.calculate_travel_fatigue_penalty(
            actor, current_assignments, travel_load
        )
        
        final_probability = base_availability + role_bonus - fatigue_penalty
        return max(0.0, min(1.0, final_probability))


class ComprehensiveConflictManager:
    """Enhanced conflict management with full buffer interval enforcement"""
    
    def __init__(self, buffer_intervals: int):
        self.buffer_intervals = max(0, buffer_intervals)
        self.actor_schedules = defaultdict(list)
        self.scene_time_mapping = {}
    
    def validate_buffer_enforcement(self, 
                                   actor: str, 
                                   new_time_slot: int) -> Tuple[bool, Optional[str]]:
        """
        Validates buffer interval between new slot and all existing assignments
        Returns: (is_valid, conflict_reason)
        """
        if actor not in self.actor_schedules:
            return True, None
        
        for existing_slot in self.actor_schedules[actor]:
            time_gap = abs(existing_slot - new_time_slot)
            
            if time_gap == 0:
                return False, f"Concurrent scene at time slot {existing_slot}"
            
            if time_gap <= self.buffer_intervals:
                return False, f"Buffer violation: gap of {time_gap} < required {self.buffer_intervals}"
        
        return True, None
    
    def check_cross_scene_conflicts(self,
                                   actor: str,
                                   scene_time_slot: int,
                                   all_scene_times: Dict[str, int]) -> List[str]:
        """Checks for conflicts across all scenes in timeline"""
        conflicts = []
        
        for scene_id, time_slot in all_scene_times.items():
            if time_slot == scene_time_slot:
                continue
            
            if actor in self.actor_schedules and time_slot in self.actor_schedules[actor]:
                if abs(time_slot - scene_time_slot) <= self.buffer_intervals:
                    conflicts.append(f"Scene {scene_id} at slot {time_slot}")
        
        return conflicts
    
    def assign_slot_safe(self, 
                        actor: str, 
                        scene_id: str,
                        time_slot: int) -> bool:
        """Safely assigns time slot with validation"""
        is_valid, reason = self.validate_buffer_enforcement(actor, time_slot)
        
        if not is_valid:
            return False
        
        if time_slot not in self.actor_schedules[actor]:
            self.actor_schedules[actor].append(time_slot)
            self.actor_schedules[actor].sort()
        
        self.scene_time_mapping[scene_id] = time_slot
        return True
    
    def remove_scene_assignment(self, actor: str, scene_id: str):
        """Removes scene assignment and cleans up time slot"""
        if scene_id in self.scene_time_mapping:
            time_slot = self.scene_time_mapping[scene_id]
            if actor in self.actor_schedules and time_slot in self.actor_schedules[actor]:
                self.actor_schedules[actor].remove(time_slot)
            del self.scene_time_mapping[scene_id]
    
    def get_actor_timeline(self, actor: str) -> List[Tuple[int, str]]:
        """Returns sorted timeline of actor's assignments"""
        timeline = []
        for scene_id, time_slot in self.scene_time_mapping.items():
            if actor in self.actor_schedules and time_slot in self.actor_schedules[actor]:
                timeline.append((time_slot, scene_id))
        return sorted(timeline)


class DirectionalTravelCalculator:
    """Enhanced travel calculator supporting directional and asymmetric travel times"""
    
    def __init__(self, transport_times: Dict[str, int]):
        self.transport_times = transport_times or {}
        self.cache = {}
        self.directional_support = True
    
    def get_directional_travel_time(self, 
                                   from_actor: str, 
                                   to_actor: str) -> float:
        """Gets travel time considering direction (asymmetric support)"""
        key_forward = f"{from_actor}-{to_actor}"
        
        if key_forward in self.transport_times:
            return float(self.transport_times[key_forward])
        
        key_backward = f"{to_actor}-{from_actor}"
        if key_backward in self.transport_times:
            return float(self.transport_times[key_backward])
        
        return 0.0
    
    def calculate_scene_travel_load(self, 
                                   actors: List[str],
                                   consider_direction: bool = True) -> float:
        """
        Calculates total travel load for a scene considering all pairwise distances
        Supports both symmetric and directional travel times
        """
        if len(actors) <= 1:
            return 0.0
        
        total_travel = 0.0
        pair_count = 0
        
        for i in range(len(actors)):
            for j in range(i + 1, len(actors)):
                if consider_direction:
                    forward_time = self.get_directional_travel_time(actors[i], actors[j])
                    backward_time = self.get_directional_travel_time(actors[j], actors[i])
                    avg_time = (forward_time + backward_time) / 2
                    total_travel += avg_time
                else:
                    total_travel += self.get_directional_travel_time(actors[i], actors[j])
                
                pair_count += 1
        
        return total_travel / pair_count if pair_count > 0 else 0.0
    
    def get_actor_travel_burden(self, 
                                actor: str,
                                scene_actors: List[str]) -> float:
        """Calculates specific travel burden for one actor in a scene"""
        if len(scene_actors) <= 1:
            return 0.0
        
        total_travel = 0.0
        for other_actor in scene_actors:
            if other_actor != actor:
                total_travel += self.get_directional_travel_time(actor, other_actor)
        
        return total_travel / (len(scene_actors) - 1) if len(scene_actors) > 1 else 0.0


class ComprehensiveRoleAssigner:
    """Advanced role assignment with global optimization and constraint validation"""
    
    def __init__(self,
                 availability_analyzer: EnhancedAvailabilityAnalyzer,
                 conflict_manager: ComprehensiveConflictManager,
                 travel_calculator: DirectionalTravelCalculator,
                 actor_availability: Dict[str, Set[int]],
                 rehearsal_capacity: Dict[str, int],
                 weights: OptimizationWeights):
        
        self.availability_analyzer = availability_analyzer
        self.conflict_manager = conflict_manager
        self.travel_calculator = travel_calculator
        self.actor_availability = actor_availability
        self.weights = weights
        
        self.actor_states = {}
        for actor, capacity in rehearsal_capacity.items():
            self.actor_states[actor] = ActorScheduleState(
                name=actor,
                capacity=capacity
            )
        
        for actor in actor_availability.keys():
            if actor not in self.actor_states:
                self.actor_states[actor] = ActorScheduleState(name=actor, capacity=10)
        
        self.actor_name_index = {actor: idx for idx, actor in enumerate(sorted(actor_availability.keys()))}
    
    def validate_actor_eligibility(self,
                                  actor: str,
                                  time_slot: int,
                                  scene_id: str) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive eligibility check for actor assignment
        Returns: (is_eligible, reason_if_not)
        """
        if actor not in self.actor_availability:
            return False, "Actor not in availability list"
        
        if time_slot not in self.actor_availability[actor]:
            return False, f"Actor not available at time slot {time_slot}"
        
        if actor not in self.actor_states:
            return False, "Actor state not initialized"
        
        if not self.actor_states[actor].can_accept_scene():
            return False, f"Actor at capacity ({self.actor_states[actor].capacity} scenes)"
        
        is_valid, conflict_reason = self.conflict_manager.validate_buffer_enforcement(
            actor, time_slot
        )
        if not is_valid:
            return False, f"Buffer conflict: {conflict_reason}"
        
        if scene_id in self.actor_states[actor].scene_assignments:
            return False, f"Actor already assigned to this scene in another role"
        
        return True, None
    
    def calculate_optimized_score(self,
                                 actor: str,
                                 role: str,
                                 already_assigned: List[str]) -> float:
        """
        Calculates optimization score using configurable weights
        Score = w1*P_available + w2*W_role_fit - w3*U_workload - w4*C_travel - w5*P_name
        """
        actor_state = self.actor_states[actor]
        
        travel_load = 0.0
        if already_assigned:
            travel_load = self.travel_calculator.get_actor_travel_burden(
                actor, already_assigned
            )
        
        availability_prob = self.availability_analyzer.calculate_comprehensive_probability(
            actor, 
            role,
            actor_state.assigned_scenes,
            travel_load
        )
        
        role_fit = 1.0
        if (actor in self.availability_analyzer.role_mapping and 
            role in self.availability_analyzer.role_mapping[actor]):
            role_fit = self.availability_analyzer.role_mapping[actor][role]
        
        workload_ratio = actor_state.get_utilization()
        
        travel_cost = 0.0
        if already_assigned:
            combined_actors = already_assigned + [actor]
            travel_cost = self.travel_calculator.calculate_scene_travel_load(combined_actors)
        
        name_penalty = self.actor_name_index.get(actor, 0)
        
        score = (self.weights.availability_weight * availability_prob +
                self.weights.role_fit_weight * role_fit -
                self.weights.workload_penalty * workload_ratio -
                self.weights.travel_penalty * travel_cost -
                self.weights.name_penalty * name_penalty)
        
        return score
    
    def assign_roles_with_validation(self,
                                    scene_id: str,
                                    time_slot: int,
                                    roles: Dict[str, int]) -> SceneAssignment:
        """
        Assigns roles with comprehensive validation and status tracking
        Returns SceneAssignment with complete metadata
        """
        role_assignments = {}
        assigned_actors = set()
        missing_roles = []
        status = ScheduleStatus.SUCCESS
        
        for role in sorted(roles.keys()):
            required_count = roles[role]
            
            if required_count <= 0:
                role_assignments[role] = []
                continue
            
            candidates = []
            
            for actor in sorted(self.actor_availability.keys()):
                if actor in assigned_actors:
                    continue
                
                is_eligible, reason = self.validate_actor_eligibility(
                    actor, time_slot, scene_id
                )
                
                if not is_eligible:
                    continue
                
                score = self.calculate_optimized_score(
                    actor, role, list(assigned_actors)
                )
                candidates.append((score, actor))
            
            candidates.sort(key=lambda x: (-x[0], x[1]))
            
            assigned_for_role = []
            for score, actor in candidates[:required_count]:
                assigned_for_role.append(actor)
                assigned_actors.add(actor)
            
            if len(assigned_for_role) < required_count:
                missing_roles.append(f"{role} (need {required_count}, got {len(assigned_for_role)})")
                status = ScheduleStatus.PARTIAL_ASSIGNMENT
            
            role_assignments[role] = assigned_for_role
        
        if not assigned_actors:
            status = ScheduleStatus.NO_AVAILABLE_ACTORS
        
        for actor in assigned_actors:
            success = self.conflict_manager.assign_slot_safe(actor, scene_id, time_slot)
            if success:
                self.actor_states[actor].assigned_scenes += 1
                self.actor_states[actor].scheduled_time_slots.append(time_slot)
                self.actor_states[actor].scene_assignments[scene_id] = "assigned"
            else:
                status = ScheduleStatus.BUFFER_VIOLATION
        
        return SceneAssignment(
            scene_id=scene_id,
            time_slot=time_slot,
            role_assignments=role_assignments,
            assigned_actors=assigned_actors,
            status=status,
            missing_roles=missing_roles
        )
    
    def unassign_scene(self, scene_id: str, assignment: SceneAssignment):
        """Removes scene assignment and restores actor states"""
        for actor in assignment.assigned_actors:
            if actor in self.actor_states:
                self.actor_states[actor].assigned_scenes = max(
                    0, self.actor_states[actor].assigned_scenes - 1
                )
                
                if assignment.time_slot in self.actor_states[actor].scheduled_time_slots:
                    self.actor_states[actor].scheduled_time_slots.remove(assignment.time_slot)
                
                if scene_id in self.actor_states[actor].scene_assignments:
                    del self.actor_states[actor].scene_assignments[scene_id]
                
                self.conflict_manager.remove_scene_assignment(actor, scene_id)


class AdaptiveSceneManager:
    """Manages dynamic scene changes with selective re-optimization"""
    
    def __init__(self, role_assigner: ComprehensiveRoleAssigner):
        self.role_assigner = role_assigner
        self.scene_assignments = {}
        self.scene_requirements = {}
    
    def get_affected_scenes(self, 
                           modified_scene_ids: Set[str],
                           all_scenes: List[Dict]) -> Set[str]:
        """
        Identifies scenes affected by modifications based on:
        - Time slot proximity
        - Shared actors
        - Buffer interval violations
        """
        affected = set(modified_scene_ids)
        
        modified_actors = set()
        modified_times = set()
        
        for scene_id in modified_scene_ids:
            if scene_id in self.scene_assignments:
                assignment = self.scene_assignments[scene_id]
                modified_actors.update(assignment.assigned_actors)
                modified_times.add(assignment.time_slot)
        
        for scene_dict in all_scenes:
            scene_id = scene_dict.get('scene_id')
            if scene_id in modified_scene_ids:
                continue
            
            if scene_id in self.scene_assignments:
                assignment = self.scene_assignments[scene_id]
                
                if assignment.assigned_actors.intersection(modified_actors):
                    affected.add(scene_id)
                    continue
                
                for mod_time in modified_times:
                    time_diff = abs(assignment.time_slot - mod_time)
                    if time_diff <= self.role_assigner.conflict_manager.buffer_intervals + 1:
                        affected.add(scene_id)
                        break
        
        return affected
    
    def reoptimize_affected_scenes(self,
                                   affected_scene_ids: Set[str],
                                   scene_requirements: List[Dict]) -> Dict[str, SceneAssignment]:
        """Re-optimizes only affected scenes"""
        for scene_id in affected_scene_ids:
            if scene_id in self.scene_assignments:
                old_assignment = self.scene_assignments[scene_id]
                self.role_assigner.unassign_scene(scene_id, old_assignment)
                del self.scene_assignments[scene_id]
        
        reoptimized = {}
        affected_reqs = [req for req in scene_requirements 
                        if req.get('scene_id') in affected_scene_ids]
        
        affected_reqs.sort(key=lambda x: (x.get('time_slot', 0), x.get('scene_id', '')))
        
        for scene_req in affected_reqs:
            scene_id = scene_req['scene_id']
            time_slot = scene_req['time_slot']
            roles = scene_req['roles']
            
            assignment = self.role_assigner.assign_roles_with_validation(
                scene_id, time_slot, roles
            )
            
            reoptimized[scene_id] = assignment
            self.scene_assignments[scene_id] = assignment
        
        return reoptimized
    
    def merge_scenes(self,
                    scene_ids_to_merge: List[str],
                    new_scene_id: str,
                    new_time_slot: int,
                    all_scene_requirements: List[Dict]) -> bool:
        """
        Merges multiple scenes and re-optimizes affected scenes only
        """
        try:
            merged_roles = defaultdict(int)
            
            for scene_id in scene_ids_to_merge:
                if scene_id in self.scene_requirements:
                    for role, count in self.scene_requirements[scene_id].items():
                        merged_roles[role] += count
            
            new_scene_req = {
                'scene_id': new_scene_id,
                'time_slot': new_time_slot,
                'roles': dict(merged_roles)
            }
            
            modified_ids = set(scene_ids_to_merge) | {new_scene_id}
            affected = self.get_affected_scenes(modified_ids, all_scene_requirements)
            
            for scene_id in scene_ids_to_merge:
                if scene_id in self.scene_requirements:
                    del self.scene_requirements[scene_id]
            
            self.scene_requirements[new_scene_id] = dict(merged_roles)
            
            updated_requirements = [req for req in all_scene_requirements 
                                   if req['scene_id'] not in scene_ids_to_merge]
            updated_requirements.append(new_scene_req)
            
            self.reoptimize_affected_scenes(affected, updated_requirements)
            
            return True
        except Exception:
            return False
    
    def split_scene(self,
                   scene_id_to_split: str,
                   split_definitions: List[Dict],
                   all_scene_requirements: List[Dict]) -> bool:
        """
        Splits a scene into multiple scenes and re-optimizes affected scenes only
        """
        try:
            if scene_id_to_split in self.scene_requirements:
                del self.scene_requirements[scene_id_to_split]
            
            new_scene_ids = set()
            for split_def in split_definitions:
                new_scene_id = split_def['scene_id']
                self.scene_requirements[new_scene_id] = split_def['roles']
                new_scene_ids.add(new_scene_id)
            
            modified_ids = {scene_id_to_split} | new_scene_ids
            affected = self.get_affected_scenes(modified_ids, all_scene_requirements)
            
            updated_requirements = [req for req in all_scene_requirements 
                                   if req['scene_id'] != scene_id_to_split]
            updated_requirements.extend(split_definitions)
            
            self.reoptimize_affected_scenes(affected, updated_requirements)
            
            return True
        except Exception:
            return False


class ComprehensiveScheduleValidator:
    """Validates complete schedule against all constraints"""
    
    def __init__(self, buffer_intervals: int):
        self.buffer_intervals = buffer_intervals
        self.validation_errors = []
    
    def validate_complete_schedule(self,
                                   assignments: Dict[str, SceneAssignment],
                                   scene_requirements: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Performs comprehensive validation of entire schedule
        Returns: (is_valid, list_of_errors)
        """
        self.validation_errors = []
        
        self._validate_role_fulfillment(assignments, scene_requirements)
        self._validate_buffer_intervals(assignments)
        self._validate_no_concurrent_assignments(assignments)
        self._validate_capacity_limits(assignments)
        
        return len(self.validation_errors) == 0, self.validation_errors
    
    def _validate_role_fulfillment(self,
                                   assignments: Dict[str, SceneAssignment],
                                   scene_requirements: List[Dict]):
        """Validates all roles are completely filled"""
        for scene_req in scene_requirements:
            scene_id = scene_req['scene_id']
            required_roles = scene_req['roles']
            
            if scene_id not in assignments:
                self.validation_errors.append(
                    f"Scene {scene_id}: Not scheduled"
                )
                continue
            
            assignment = assignments[scene_id]
            
            for role, required_count in required_roles.items():
                assigned_count = len(assignment.role_assignments.get(role, []))
                if assigned_count < required_count:
                    self.validation_errors.append(
                        f"Scene {scene_id}, Role {role}: Required {required_count}, assigned {assigned_count}"
                    )
    
    def _validate_buffer_intervals(self, assignments: Dict[str, SceneAssignment]):
        """Validates buffer intervals between all actor assignments"""
        actor_timelines = defaultdict(list)
        
        for scene_id, assignment in assignments.items():
            for actor in assignment.assigned_actors:
                actor_timelines[actor].append((assignment.time_slot, scene_id))
        
        for actor, timeline in actor_timelines.items():
            timeline.sort()
            
            for i in range(len(timeline) - 1):
                current_time, current_scene = timeline[i]
                next_time, next_scene = timeline[i + 1]
                
                gap = next_time - current_time
                if gap <= self.buffer_intervals:
                    self.validation_errors.append(
                        f"Actor {actor}: Buffer violation between {current_scene} (slot {current_time}) "
                        f"and {next_scene} (slot {next_time}), gap={gap}, required={self.buffer_intervals}"
                    )
    
    def _validate_no_concurrent_assignments(self, assignments: Dict[str, SceneAssignment]):
        """Validates no actor is assigned to multiple scenes at same time"""
        time_slot_actors = defaultdict(lambda: defaultdict(list))
        
        for scene_id, assignment in assignments.items():
            for actor in assignment.assigned_actors:
                time_slot_actors[assignment.time_slot][actor].append(scene_id)
        
        for time_slot, actors in time_slot_actors.items():
            for actor, scene_list in actors.items():
                if len(scene_list) > 1:
                    self.validation_errors.append(
                        f"Actor {actor}: Concurrent assignment at slot {time_slot} "
                        f"in scenes {', '.join(scene_list)}"
                    )
    
    def _validate_capacity_limits(self, assignments: Dict[str, SceneAssignment]):
        """Validates no actor exceeds their capacity"""
        actor_scene_counts = defaultdict(int)
        
        for assignment in assignments.values():
            for actor in assignment.assigned_actors:
                actor_scene_counts[actor] += 1


class GlobalScheduleOptimizer:
    """Main orchestrator with global optimization and iterative refinement"""
    
    def __init__(self,
                 actor_availability: List[List],
                 scene_requirements: List[Dict],
                 historical_data: Dict[str, List[int]],
                 role_mapping: Dict[str, Dict[str, float]],
                 transport_times: Dict[str, int],
                 buffer_intervals: int,
                 rehearsal_capacity: Dict[str, int],
                 optimization_weights: Optional[OptimizationWeights] = None):
        
        self._validate_inputs(actor_availability, scene_requirements, historical_data,
                            role_mapping, transport_times, buffer_intervals, rehearsal_capacity)
        
        self.actor_availability_map = self._parse_actor_availability(actor_availability)
        self.scene_requirements = self._normalize_scene_requirements(scene_requirements)
        self.rehearsal_capacity = self._normalize_capacity(rehearsal_capacity, self.actor_availability_map)
        
        self.weights = optimization_weights or OptimizationWeights()
        
        self.availability_analyzer = EnhancedAvailabilityAnalyzer(
            historical_data, role_mapping
        )
        
        self.conflict_manager = ComprehensiveConflictManager(buffer_intervals)
        
        self.travel_calculator = DirectionalTravelCalculator(transport_times)
        
        self.role_assigner = ComprehensiveRoleAssigner(
            self.availability_analyzer,
            self.conflict_manager,
            self.travel_calculator,
            self.actor_availability_map,
            self.rehearsal_capacity,
            self.weights
        )
        
        self.adaptive_manager = AdaptiveSceneManager(self.role_assigner)
        self.validator = ComprehensiveScheduleValidator(buffer_intervals)
        
        self.optimization_metadata = {
            'weights_used': self.weights.get_config(),
            'total_actors': len(self.actor_availability_map),
            'total_scenes': len(self.scene_requirements),
            'buffer_intervals': buffer_intervals
        }
    
    def _validate_inputs(self, actor_availability, scene_requirements, historical_data,
                        role_mapping, transport_times, buffer_intervals, rehearsal_capacity):
        """Validates all input types and structures"""
        if not isinstance(actor_availability, list):
            raise TypeError("actor_availability must be a list")
        
        if not isinstance(scene_requirements, list):
            raise TypeError("scene_requirements must be a list")
        
        if not isinstance(historical_data, dict):
            raise TypeError("historical_data must be a dictionary")
        
        if not isinstance(role_mapping, dict):
            raise TypeError("role_mapping must be a dictionary")
        
        if not isinstance(transport_times, dict):
            raise TypeError("transport_times must be a dictionary")
        
        if not isinstance(buffer_intervals, int) or buffer_intervals < 0:
            raise ValueError("buffer_intervals must be a non-negative integer")
        
        if not isinstance(rehearsal_capacity, dict):
            raise TypeError("rehearsal_capacity must be a dictionary")
    
    def _parse_actor_availability(self, actor_availability: List[List]) -> Dict[str, Set[int]]:
        """Parses and validates actor availability with comprehensive error handling"""
        availability_map = {}
        
        for entry in actor_availability:
            try:
                if not isinstance(entry, list) or len(entry) < 2:
                    continue
                
                actor_name = str(entry[0]).strip()
                if not actor_name:
                    continue
                
                time_slots = entry[1]
                
                if not isinstance(time_slots, list):
                    continue
                
                valid_slots = set()
                for slot in time_slots:
                    try:
                        slot_int = int(slot)
                        if slot_int >= 0:
                            valid_slots.add(slot_int)
                    except (ValueError, TypeError):
                        continue
                
                if valid_slots:
                    availability_map[actor_name] = valid_slots
                    
            except (ValueError, TypeError, AttributeError):
                continue
        
        return availability_map
    
    def _normalize_scene_requirements(self, scene_requirements: List[Dict]) -> List[Dict]:
        """Normalizes and validates scene requirements"""
        normalized = []
        
        for scene_req in scene_requirements:
            try:
                if not isinstance(scene_req, dict):
                    continue
                
                if 'scene_id' not in scene_req:
                    continue
                if 'time_slot' not in scene_req:
                    continue
                if 'roles' not in scene_req:
                    continue
                
                scene_id = str(scene_req['scene_id']).strip()
                time_slot = int(scene_req['time_slot'])
                
                if time_slot < 0:
                    continue
                
                roles = {}
                if isinstance(scene_req['roles'], dict):
                    for role, count in scene_req['roles'].items():
                        try:
                            role_str = str(role).strip()
                            count_int = int(count)
                            if role_str and count_int >= 0:
                                roles[role_str] = count_int
                        except (ValueError, TypeError):
                            continue
                
                if scene_id and roles:
                    normalized.append({
                        'scene_id': scene_id,
                        'time_slot': time_slot,
                        'roles': roles
                    })
                    
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
        
        return normalized
    
    def _normalize_capacity(self, 
                           rehearsal_capacity: Dict[str, int],
                           actor_availability: Dict[str, Set[int]]) -> Dict[str, int]:
        """Normalizes capacity and ensures all actors have capacity defined"""
        normalized = {}
        
        for actor in actor_availability.keys():
            if actor in rehearsal_capacity:
                try:
                    capacity = int(rehearsal_capacity[actor])
                    normalized[actor] = max(1, capacity)
                except (ValueError, TypeError):
                    normalized[actor] = 10
            else:
                normalized[actor] = 10
        
        return normalized
    
    def _initial_greedy_assignment(self) -> Dict[str, SceneAssignment]:
        """Performs initial greedy assignment pass"""
        assignments = {}
        
        sorted_scenes = sorted(self.scene_requirements, 
                              key=lambda x: (x['time_slot'], x['scene_id']))
        
        for scene_req in sorted_scenes:
            scene_id = scene_req['scene_id']
            time_slot = scene_req['time_slot']
            roles = scene_req['roles']
            
            if not roles or all(count == 0 for count in roles.values()):
                assignments[scene_id] = SceneAssignment(
                    scene_id=scene_id,
                    time_slot=time_slot,
                    role_assignments={},
                    assigned_actors=set(),
                    status=ScheduleStatus.SUCCESS
                )
                continue
            
            assignment = self.role_assigner.assign_roles_with_validation(
                scene_id, time_slot, roles
            )
            
            assignments[scene_id] = assignment
            self.adaptive_manager.scene_assignments[scene_id] = assignment
            self.adaptive_manager.scene_requirements[scene_id] = roles
        
        return assignments
    
    def _iterative_refinement(self, 
                             assignments: Dict[str, SceneAssignment],
                             max_iterations: int = 3) -> Dict[str, SceneAssignment]:
        """
        Performs iterative refinement to improve partial assignments
        Uses backtracking and reassignment strategies
        """
        for iteration in range(max_iterations):
            incomplete_scenes = [
                scene_id for scene_id, assignment in assignments.items()
                if not assignment.is_complete()
            ]
            
            if not incomplete_scenes:
                break
            
            improvement_made = False
            
            for scene_id in incomplete_scenes:
                assignment = assignments[scene_id]
                
                scene_req = next(
                    (req for req in self.scene_requirements if req['scene_id'] == scene_id),
                    None
                )
                
                if not scene_req:
                    continue
                
                self.role_assigner.unassign_scene(scene_id, assignment)
                
                new_assignment = self.role_assigner.assign_roles_with_validation(
                    scene_id, scene_req['time_slot'], scene_req['roles']
                )
                
                if len(new_assignment.missing_roles) < len(assignment.missing_roles):
                    improvement_made = True
                    assignments[scene_id] = new_assignment
                    self.adaptive_manager.scene_assignments[scene_id] = new_assignment
                else:
                    for actor in assignment.assigned_actors:
                        self.conflict_manager.assign_slot_safe(
                            actor, scene_id, assignment.time_slot
                        )
                        if actor in self.role_assigner.actor_states:
                            self.role_assigner.actor_states[actor].assigned_scenes += 1
            
            if not improvement_made:
                break
        
        return assignments
    
    def optimize(self) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, Any]]:
        """
        Main optimization method with global optimization and validation
        Returns: (schedule, metadata)
        """
        if not self.scene_requirements:
            return {}, {
                'status': 'no_scenes',
                'validation_errors': [],
                'optimization_metadata': self.optimization_metadata
            }
        
        if not self.actor_availability_map:
            empty_schedule = {
                req['scene_id']: {} for req in self.scene_requirements
            }
            return empty_schedule, {
                'status': 'no_actors',
                'validation_errors': ['No actors available'],
                'optimization_metadata': self.optimization_metadata
            }
        
        assignments = self._initial_greedy_assignment()
        
        assignments = self._iterative_refinement(assignments)
        
        is_valid, validation_errors = self.validator.validate_complete_schedule(
            assignments, self.scene_requirements
        )
        
        final_schedule = {}
        scene_statuses = {}
        
        for scene_id, assignment in assignments.items():
            final_schedule[scene_id] = assignment.role_assignments
            scene_statuses[scene_id] = {
                'status': assignment.status.value,
                'missing_roles': assignment.missing_roles,
                'assigned_actors': list(assignment.assigned_actors),
                'is_complete': assignment.is_complete()
            }
        
        sorted_schedule = {}
        for scene_id in sorted(final_schedule.keys()):
            sorted_schedule[scene_id] = final_schedule[scene_id]
        
        metadata = {
            'status': 'complete' if is_valid else 'partial',
            'validation_errors': validation_errors,
            'scene_statuses': scene_statuses,
            'optimization_metadata': self.optimization_metadata,
            'total_assigned_scenes': len([a for a in assignments.values() if a.is_complete()]),
            'total_scenes': len(self.scene_requirements)
        }
        
        return sorted_schedule, metadata
    
    def get_adaptive_manager(self) -> AdaptiveSceneManager:
        """Returns adaptive manager for dynamic scene modifications"""
        return self.adaptive_manager
    
    def reoptimize_after_change(self, 
                               modified_scene_ids: Set[str]) -> Tuple[Dict[str, Dict[str, List[str]]], Dict]:
        """Re-optimizes schedule after dynamic changes to specific scenes"""
        affected_scenes = self.adaptive_manager.get_affected_scenes(
            modified_scene_ids, self.scene_requirements
        )
        
        reoptimized = self.adaptive_manager.reoptimize_affected_scenes(
            affected_scenes, self.scene_requirements
        )
        
        all_assignments = {**self.adaptive_manager.scene_assignments, **reoptimized}
        
        is_valid, validation_errors = self.validator.validate_complete_schedule(
            all_assignments, self.scene_requirements
        )
        
        final_schedule = {}
        for scene_id, assignment in all_assignments.items():
            final_schedule[scene_id] = assignment.role_assignments
        
        sorted_schedule = {}
        for scene_id in sorted(final_schedule.keys()):
            sorted_schedule[scene_id] = final_schedule[scene_id]
        
        metadata = {
            'status': 'reoptimized',
            'affected_scenes': list(affected_scenes),
            'modified_scenes': list(modified_scene_ids),
            'validation_errors': validation_errors,
            'is_valid': is_valid
        }
        
        return sorted_schedule, metadata


def optimize_rehearsal_schedule(
    actor_availability: List[List],
    scene_requirements: List[Dict[str, Any]],
    historical_data: Dict[str, List[int]],
    role_mapping: Dict[str, Dict[str, float]],
    transport_times: Dict[str, int],
    buffer_intervals: int,
    rehearsal_capacity: Dict[str, int]
) -> Dict[str, Dict[str, List[str]]]:
    """
    Optimizes theater rehearsal schedule with comprehensive constraint handling.
    
    This function implements a sophisticated scheduling algorithm that:
    - Enforces strict buffer intervals between consecutive actor assignments
    - Uses probability-based availability modeling with travel fatigue
    - Performs global optimization with iterative refinement
    - Validates all constraints and reports violations
    - Supports dynamic scene modifications with selective re-optimization
    
    Args:
        actor_availability: List of [actor_name, [time_slots]] pairs
        scene_requirements: List of dicts with scene_id, time_slot, and roles
        historical_data: Actor attendance history for probability calculation
        role_mapping: Actor-role suitability scores (0.0 to 1.0)
        transport_times: Directional travel times between actor pairs
        buffer_intervals: Minimum time gap between consecutive scenes
        rehearsal_capacity: Maximum scenes per actor
    
    Returns:
        Dictionary mapping scene_id to role assignments {role: [actors]}
        
    Raises:
        TypeError: If input types are invalid
        ValueError: If buffer_intervals is negative
    
    Optimization Formula:
        Score = 2.0*P_available + 1.5*W_role_fit - 0.3*U_workload - 0.1*C_travel - 0.001*P_name
    """
    try:
        if actor_availability is None:
            actor_availability = []
        if scene_requirements is None:
            scene_requirements = []
        if historical_data is None:
            historical_data = {}
        if role_mapping is None:
            role_mapping = {}
        if transport_times is None:
            transport_times = {}
        if buffer_intervals is None:
            buffer_intervals = 0
        if rehearsal_capacity is None:
            rehearsal_capacity = {}
        
        optimizer = GlobalScheduleOptimizer(
            actor_availability=actor_availability,
            scene_requirements=scene_requirements,
            historical_data=historical_data,
            role_mapping=role_mapping,
            transport_times=transport_times,
            buffer_intervals=buffer_intervals,
            rehearsal_capacity=rehearsal_capacity
        )
        
        schedule, metadata = optimizer.optimize()
        
        if metadata.get('validation_errors'):
            print("Schedule Validation Warnings:")
            for error in metadata['validation_errors'][:10]:
                print(f"  - {error}")
            if len(metadata['validation_errors']) > 10:
                print(f"  ... and {len(metadata['validation_errors']) - 10} more")
        
        incomplete_count = sum(
            1 for status in metadata.get('scene_statuses', {}).values()
            if not status.get('is_complete', False)
        )
        
        if incomplete_count > 0:
            print(f"\n{incomplete_count} scene(s) have incomplete role assignments")
            print("Consider adjusting:")
            print("  - Actor availability windows")
            print("  - Rehearsal capacity limits")
            print("  - Buffer interval requirements")
            print("  - Scene time slot assignments")
        
        return schedule
    
    except (TypeError, ValueError) as e:
        print(f"Input validation error: {e}")
        raise
    
    except Exception as e:
        print(f"Unexpected error during optimization: {e}")
        return {}


if __name__ == "__main__":
    
    actor_availability = [
        ['Actor1', [1, 2, 3, 5]],
        ['Actor2', [1, 3, 4, 6]],
        ['Actor3', [2, 4, 5, 7]],
        ['Actor4', [1, 2, 7, 8]]
    ]

    scene_requirements = [
        {'scene_id': 'Scene1', 'time_slot': 2, 'roles': {'role1': 2, 'role2': 1}},
        {'scene_id': 'Scene2', 'time_slot': 4, 'roles': {'role1': 1, 'role2': 1, 'role3': 1}},
        {'scene_id': 'Scene3', 'time_slot': 6, 'roles': {'role2': 2}}
    ]

    historical_data = {
        'Actor1': [1, 1, 0, 1, 1],
        'Actor2': [1, 0, 1, 0, 1],
        'Actor3': [0, 1, 1, 1, 0],
        'Actor4': [1, 1, 1, 0, 1]
    }

    role_mapping = {
        'Actor1': {'role1': 0.9, 'role2': 0.8, 'role3': 0.6},
        'Actor2': {'role1': 0.7, 'role2': 1.0, 'role3': 0.5},
        'Actor3': {'role1': 0.8, 'role2': 0.9, 'role3': 0.7},
        'Actor4': {'role1': 0.6, 'role2': 0.8, 'role3': 1.0}
    }

    transport_times = {
        'Actor1-Actor2': 3,
        'Actor2-Actor4': 2,
        'Actor3-Actor2': 4,
        'Actor1-Actor4': 2
    }

    buffer_intervals = 1

    rehearsal_capacity = {
        'Actor1': 3,
        'Actor2': 2,
        'Actor3': 3,
        'Actor4': 3
    }
    
    result = optimize_rehearsal_schedule(
        actor_availability,
        scene_requirements,
        historical_data,
        role_mapping,
        transport_times,
        buffer_intervals,
        rehearsal_capacity
    )
    
    # print("\nFinal Schedule:")
    print(result)
    
    
    for scene_id in sorted(result.keys()):
        assignments = result[scene_id]
        print(f"\n{scene_id}:")
        
        if not assignments:
            print("No assignments (insufficient actors or conflicts)")
        else:
            for role in sorted(assignments.keys()):
                actors = assignments[role]
                if actors:
                    print(f"  {role}: {', '.join(actors)}")
                else:
                    print(f"  {role}:UNFILLED")