from typing import List, Dict, Tuple, Any

def match_nutrition_plan(
    user_profile: int,
    available_plans: List[Dict[str, Any]],
    profile_decoder: Dict[str, Any]
) -> Dict[str, Any]:
    
    if not available_plans:
        return {
            'matched_plan': '',
            'compatibility_score': 0.0,
            'required_modifications': [],
            'genetic_considerations': [],
            'dietary_restrictions_applied': [],
            'allergens_avoided': [],
            'alternative_plans': []
        }
    
    genetic_markers = profile_decoder.get('genetic_markers', {})
    dietary_preferences = profile_decoder.get('dietary_preferences', {})
    allergies = profile_decoder.get('allergies', {})
    
    user_genetic = user_profile & 0xFFFF
    user_dietary = (user_profile >> 16) & 0xFF
    user_allergies = (user_profile >> 24) & 0xFF
    
    active_genetic = []
    for bit_pos, marker_name in genetic_markers.items():
        bit_pos = int(bit_pos) if isinstance(bit_pos, str) else bit_pos
        if user_genetic & (1 << bit_pos):
            active_genetic.append(marker_name)
    
    active_dietary = []
    for bit_pos, pref_name in dietary_preferences.items():
        bit_pos = int(bit_pos) if isinstance(bit_pos, str) else bit_pos
        if user_dietary & (1 << (bit_pos - 16)):
            active_dietary.append(pref_name)
    
    active_allergies = []
    for bit_pos, allergen_name in allergies.items():
        bit_pos = int(bit_pos) if isinstance(bit_pos, str) else bit_pos
        if user_allergies & (1 << (bit_pos - 24)):
            active_allergies.append(allergen_name)
    
    plan_scores = []
    
    for plan in available_plans:
        plan_name = plan.get('plan_name', '')
        required_bits = plan.get('required_bits', 0)
        excluded_bits = plan.get('excluded_bits', 0)
        customizable = plan.get('customizable', False)
        
        required_genetic = required_bits & 0xFFFF
        required_dietary = (required_bits >> 16) & 0xFF
        required_allergies = (required_bits >> 24) & 0xFF
        
        excluded_genetic = excluded_bits & 0xFFFF
        excluded_dietary = (excluded_bits >> 16) & 0xFF
        excluded_allergies = (excluded_bits >> 24) & 0xFF
        
        is_compatible = True
        compatibility_parts = []
        conflicts = []
        
        if user_allergies & excluded_allergies:
            if not customizable:
                is_compatible = False
                continue
            else:
                conflicting_allergens = []
                for bit_pos, allergen_name in allergies.items():
                    bit_pos = int(bit_pos) if isinstance(bit_pos, str) else bit_pos
                    if (user_profile & (1 << bit_pos)) and (excluded_bits & (1 << bit_pos)):
                        conflicting_allergens.append(allergen_name)
                if conflicting_allergens:
                    conflicts.append(('allergy', conflicting_allergens))
        
        if user_dietary & excluded_dietary:
            if not customizable:
                is_compatible = False
                continue
            else:
                conflicting_dietary = []
                for bit_pos, pref_name in dietary_preferences.items():
                    bit_pos = int(bit_pos) if isinstance(bit_pos, str) else bit_pos
                    if (user_profile & (1 << bit_pos)) and (excluded_bits & (1 << bit_pos)):
                        conflicting_dietary.append(pref_name)
                if conflicting_dietary:
                    conflicts.append(('dietary', conflicting_dietary))
        
        if user_genetic & excluded_genetic:
            if not customizable:
                is_compatible = False
                continue
        
        genetic_match = 0
        genetic_total = 0
        for bit in range(16):
            if required_genetic & (1 << bit):
                genetic_total += 1
                if user_genetic & (1 << bit):
                    genetic_match += 1
        
        genetic_score = genetic_match / genetic_total if genetic_total > 0 else 1.0
        
        dietary_match = 0
        dietary_total = 0
        for bit in range(8):
            if required_dietary & (1 << bit):
                dietary_total += 1
                if user_dietary & (1 << bit):
                    dietary_match += 1
        
        dietary_score = dietary_match / dietary_total if dietary_total > 0 else 1.0
        
        allergy_conflicts = 0
        allergy_total = 0
        for bit in range(8):
            if excluded_allergies & (1 << bit):
                allergy_total += 1
                if user_allergies & (1 << bit):
                    allergy_conflicts += 1
        
        allergy_score = 1.0 - (allergy_conflicts / allergy_total) if allergy_total > 0 else 1.0
        
        if allergy_conflicts > 0 and not customizable:
            is_compatible = False
            continue
        
        overall_score = (genetic_score * 0.4 + dietary_score * 0.3 + allergy_score * 0.3)
        
        if conflicts:
            overall_score *= 0.9
        
        plan_scores.append({
            'plan_name': plan_name,
            'score': overall_score,
            'conflicts': conflicts,
            'customizable': customizable,
            'plan_data': plan
        })
    
    if not plan_scores:
        return {
            'matched_plan': '',
            'compatibility_score': 0.0,
            'required_modifications': [],
            'genetic_considerations': active_genetic,
            'dietary_restrictions_applied': active_dietary,
            'allergens_avoided': active_allergies,
            'alternative_plans': []
        }
    
    plan_scores.sort(key=lambda x: x['score'], reverse=True)
    
    best_plan = plan_scores[0]
    matched_plan_name = best_plan['plan_name']
    compatibility_score = best_plan['score']
    
    modifications = []
    for conflict_type, conflict_items in best_plan['conflicts']:
        if conflict_type == 'allergy':
            for allergen in conflict_items:
                modifications.append(f"Remove {allergen} ingredients and substitute with safe alternatives")
        elif conflict_type == 'dietary':
            for dietary in conflict_items:
                modifications.append(f"Adjust plan to accommodate {dietary} restriction")
    
    genetic_considerations = []
    plan_required = best_plan['plan_data'].get('required_bits', 0)
    plan_genetic_required = plan_required & 0xFFFF
    
    for bit_pos, marker_name in genetic_markers.items():
        bit_pos = int(bit_pos) if isinstance(bit_pos, str) else bit_pos
        if user_genetic & (1 << bit_pos) and plan_genetic_required & (1 << bit_pos):
            genetic_considerations.append(f"{marker_name} - plan optimized for this marker")
    
    alternatives = []
    if len(plan_scores) >= 4:
        for i in range(1, min(4, len(plan_scores))):
            alternatives.append({
                'plan_name': plan_scores[i]['plan_name'],
                'compatibility_score': round(plan_scores[i]['score'], 2)
            })
    
    return {
        'matched_plan': matched_plan_name,
        'compatibility_score': round(compatibility_score, 2),
        'required_modifications': modifications,
        'genetic_considerations': genetic_considerations,
        'dietary_restrictions_applied': active_dietary,
        'allergens_avoided': active_allergies,
        'alternative_plans': alternatives
    }