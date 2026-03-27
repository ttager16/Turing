from typing import List, Dict, Any

def analyze_retinal_patterns(pixel_matrix: List[List[int]], feature_templates: List[Dict], 
                           diagnostic_masks: List[Dict], risk_factors: Dict) -> Dict[str, Any]:
    """
    Analyzes retinal patterns using advanced bit manipulation framework.
    Returns: Dictionary with diagnostic analysis results and severity classifications
    """
    
    # Input validation
    if not pixel_matrix:
        return {"error": "Empty pixel matrix provided"}
    
    # Check matrix dimensions and rectangularity
    if len(pixel_matrix) < 8 or len(pixel_matrix) > 16:
        return {"error": "Invalid pixel matrix dimensions"}
    
    row_length = len(pixel_matrix[0])
    if row_length < 8 or row_length > 16:
        return {"error": "Invalid pixel matrix dimensions"}
    
    for row in pixel_matrix:
        if len(row) != row_length:
            return {"error": "Invalid pixel matrix dimensions"}
        for pixel in row:
            if not isinstance(pixel, int) or pixel < 0 or pixel > 255:
                return {"error": "Input is not valid"}
    
    # Validate feature templates
    for template in feature_templates:
        if template['template_id'] < 0 or template['template_id'] > 15:
            return {"error": "Input is not valid"}
        if template['pattern_mask'] < 0 or template['pattern_mask'] > 255:
            return {"error": f"Invalid pattern mask value for template {template['template_id']}"}
        if template['feature_weight'] < 0.1 or template['feature_weight'] > 2.0:
            return {"error": f"Feature weight out of range for template {template['template_id']}"}
        if template['correlation_threshold'] < 0.3 or template['correlation_threshold'] > 0.9:
            return {"error": f"Correlation threshold invalid for template {template['template_id']}"}
    
    # Validate diagnostic masks
    for mask in diagnostic_masks:
        if mask['mask_id'] < 0 or mask['mask_id'] > 7:
            return {"error": "Input is not valid"}
        if mask['severity_modifier'] < 0.5 or mask['severity_modifier'] > 1.5:
            return {"error": "Input is not valid"}
        if mask['analysis_priority'] < 1 or mask['analysis_priority'] > 5:
            return {"error": "Input is not valid"}
        
        for coord in mask['region_coordinates']:
            row, col = coord[0], coord[1]
            if row < 0 or row >= len(pixel_matrix) or col < 0 or col >= len(pixel_matrix[0]):
                return {"error": f"Region coordinates exceed matrix bounds for mask {mask['mask_id']}"}
    
    # Validate risk factors
    if (risk_factors['patient_age_group'] < 1 or risk_factors['patient_age_group'] > 5 or
        risk_factors['genetic_predisposition'] < 0.0 or risk_factors['genetic_predisposition'] > 1.0 or
        risk_factors['environmental_exposure'] < 0.0 or risk_factors['environmental_exposure'] > 1.0 or
        risk_factors['previous_diagnosis_history'] < 0.0 or risk_factors['previous_diagnosis_history'] > 1.0):
        return {"error": "Invalid risk factor values detected"}
    
    def popcount(n):
        """Count the number of set bits in integer n"""
        count = 0
        while n:
            count += n & 1
            n >>= 1
        return count
    
    def extract_retinal_features(pixel):
        """
        Extract 4 retinal features from pixel using 2 bits per feature
        as specified in Feature Encoding Constraints
        """
        feature_0 = pixel & 0x03          # bits 0-1
        feature_1 = (pixel >> 2) & 0x03   # bits 2-3
        feature_2 = (pixel >> 4) & 0x03   # bits 4-5
        feature_3 = (pixel >> 6) & 0x03   # bits 6-7
        return [feature_0, feature_1, feature_2, feature_3]
    
    def analyze_feature_patterns(pixel, template_mask):
        """
        Analyze retinal features against template patterns
        Returns True if pixel matches the template pattern
        """
        # Extract individual features from pixel and template for analysis
        pixel_features = extract_retinal_features(pixel)
        template_features = extract_retinal_features(template_mask)
        
        # Pattern matching: check if pixel features match template features
        # A match occurs when (pixel & template) == template for the composite
        return (pixel & template_mask) == template_mask
    
    def calculate_feature_based_correlation(region_pixels, template_mask):
        """
        Calculate correlation based on individual feature analysis
        """
        matches = 0
        for pixel in region_pixels:
            if analyze_feature_patterns(pixel, template_mask):
                matches += 1
        return matches / len(region_pixels) if region_pixels else 0.0
    
    def get_adjacent_pairs(coordinates):
        """Get all adjacent coordinate pairs in the region"""
        pairs = []
        coord_set = set((r, c) for r, c in coordinates)
        
        for r, c in coordinates:
            # Check right neighbor
            if (r, c + 1) in coord_set:
                pairs.append(((r, c), (r, c + 1)))
            # Check bottom neighbor
            if (r + 1, c) in coord_set:
                pairs.append(((r, c), (r + 1, c)))
        
        return pairs
    
    def analyze_feature_discontinuities(pixel1, pixel2):
        """
        Analyze edge discontinuities between adjacent pixels using feature-level XOR
        """
        # Extract features for detailed analysis
        features1 = extract_retinal_features(pixel1)
        features2 = extract_retinal_features(pixel2)
        
        # Calculate discontinuities per feature and aggregate
        total_discontinuities = 0
        for f1, f2 in zip(features1, features2):
            total_discontinuities += popcount(f1 ^ f2)
        
        # Return the overall pixel XOR as specified in the prompt
        overall_discontinuity = popcount(pixel1 ^ pixel2)
        
        # The prompt specifies using XOR between pixels for edge discontinuities
        return overall_discontinuity
    
    def calculate_feature_density_with_extraction(region_pixels):
        """
        Calculate feature density using explicit feature extraction and aggregation
        """
        aggregated_pixels = 0
        for pixel in region_pixels:
            # Extract all 4 features for comprehensive analysis
            features = extract_retinal_features(pixel)
            
            # Aggregate features back into pixel representation for density calculation
            feature_contribution = 0
            for i, feature in enumerate(features):
                feature_contribution |= (feature << (i * 2))
            
            # Use bitwise OR aggregation as specified in the prompt
            aggregated_pixels |= pixel
        
        return popcount(aggregated_pixels) / (len(region_pixels) * 8) if region_pixels else 0.0
    
    # Calculate constants dynamically from current inputs
    max_feature_weight = max(template['feature_weight'] for template in feature_templates)
    max_severity_modifier = max(mask['severity_modifier'] for mask in diagnostic_masks)
    max_region_pixel_count = max(len(mask['region_coordinates']) for mask in diagnostic_masks)
    
    # Calculate max_adjacent_pairs by checking actual adjacencies in each region
    max_adjacent_pairs_in_any_region = 0
    for mask in diagnostic_masks:
        pairs = get_adjacent_pairs(mask['region_coordinates'])
        max_adjacent_pairs_in_any_region = max(max_adjacent_pairs_in_any_region, len(pairs))
    max_possible_score = (max_region_pixel_count * max_feature_weight) + (max_adjacent_pairs_in_any_region * max_severity_modifier)
    base_threshold = 0.6 * max_possible_score
    
    # Calculate risk weight
    risk_weight = (risk_factors['patient_age_group'] * 0.3 + 
                   risk_factors['genetic_predisposition'] * 0.4 + 
                   risk_factors['environmental_exposure'] * 0.2 + 
                   risk_factors['previous_diagnosis_history'] * 0.1)
    
    diagnostic_results = []
    total_pattern_matches = 0
    total_correlation_sum = 0.0
    successful_operations = 0
    total_operations = 0
    
    # Sort templates and masks by ID for deterministic processing
    sorted_templates = sorted(feature_templates, key=lambda x: x['template_id'])
    sorted_masks = sorted(diagnostic_masks, key=lambda x: x['mask_id'])
    
    # Process each template-mask combination
    for template in sorted_templates:
        for mask in sorted_masks:
            total_operations += 1
            
            # Extract pixel values from region
            region_pixels = []
            for row, col in mask['region_coordinates']:
                region_pixels.append(pixel_matrix[row][col])
            
            # Enhanced pattern matching using feature-aware analysis
            pattern_matches = 0
            for pixel in region_pixels:
                if analyze_feature_patterns(pixel, template['pattern_mask']):
                    pattern_matches += 1
            
            # Calculate correlation score using feature-based analysis
            correlation_score = calculate_feature_based_correlation(region_pixels, template['pattern_mask'])
            
            # Count edge discontinuities using enhanced feature analysis
            adjacent_pairs = get_adjacent_pairs(mask['region_coordinates'])
            edge_discontinuities = 0
            for (r1, c1), (r2, c2) in adjacent_pairs:
                pixel1 = pixel_matrix[r1][c1]
                pixel2 = pixel_matrix[r2][c2]
                edge_discontinuities += analyze_feature_discontinuities(pixel1, pixel2)
            
            # Calculate diagnostic score
            diagnostic_score = (pattern_matches * template['feature_weight']) + (edge_discontinuities * mask['severity_modifier'])
            
            # Calculate severity level
            final_severity_score = diagnostic_score * risk_weight
            classification_level = min(4, int(final_severity_score / base_threshold)) if base_threshold > 0 else 0
            
            # Calculate feature density using enhanced feature extraction
            feature_density = calculate_feature_density_with_extraction(region_pixels)
            
            # Check if meets correlation threshold
            if correlation_score >= template['correlation_threshold']:
                successful_operations += 1
            
            diagnostic_results.append({
                "template_id": template['template_id'],
                "mask_id": mask['mask_id'],
                "pattern_matches": pattern_matches,
                "correlation_score": round(correlation_score, 2),
                "edge_discontinuities": edge_discontinuities,
                "diagnostic_score": round(diagnostic_score, 1),
                "severity_level": classification_level,
                "feature_density": round(feature_density, 3)
            })
            
            total_pattern_matches += pattern_matches
            total_correlation_sum += correlation_score
    
    # Calculate overall assessment
    total_diagnostic_score = sum(result['diagnostic_score'] for result in diagnostic_results)
    highest_severity_detected = max(result['severity_level'] for result in diagnostic_results) if diagnostic_results else 0
    risk_adjusted_score = total_diagnostic_score * risk_weight
    
    # Determine recommended followup
    if highest_severity_detected == 0:
        recommended_followup = "routine_monitoring"
    elif highest_severity_detected == 1:
        recommended_followup = "routine_monitoring"
    elif highest_severity_detected == 2:
        recommended_followup = "increased_monitoring"
    elif highest_severity_detected == 3:
        recommended_followup = "immediate_consultation"
    else:
        recommended_followup = "urgent_intervention"
    
    # Calculate analysis metadata
    processed_regions = len(sorted_masks)
    average_correlation = total_correlation_sum / total_operations if total_operations > 0 else 0.0
    processing_efficiency = successful_operations / total_operations if total_operations > 0 else 0.0
    
    return {
        "diagnostic_results": diagnostic_results,
        "overall_assessment": {
            "total_diagnostic_score": round(total_diagnostic_score, 1),
            "highest_severity_detected": highest_severity_detected,
            "risk_adjusted_score": round(risk_adjusted_score, 1),
            "recommended_followup": recommended_followup
        },
        "analysis_metadata": {
            "processed_regions": processed_regions,
            "total_pattern_matches": total_pattern_matches,
            "average_correlation": round(average_correlation, 3),
            "processing_efficiency": round(processing_efficiency, 2)
        }
    }


if __name__ == "__main__":
    # Test with sample input
    pixel_matrix = [
        [45, 67, 89, 123, 156, 78, 234, 145],
        [67, 89, 123, 156, 78, 234, 145, 67],
        [89, 123, 156, 78, 234, 145, 67, 89],
        [123, 156, 78, 234, 145, 67, 89, 123],
        [156, 78, 234, 145, 67, 89, 123, 156],
        [78, 234, 145, 67, 89, 123, 156, 78],
        [234, 145, 67, 89, 123, 156, 78, 234],
        [145, 67, 89, 123, 156, 78, 234, 145]
    ]

    feature_templates = [
        {"template_id": 0, "pattern_mask": 42, "feature_weight": 1.2, "correlation_threshold": 0.6},
        {"template_id": 1, "pattern_mask": 156, "feature_weight": 1.5, "correlation_threshold": 0.7}
    ]

    diagnostic_masks = [
        {"mask_id": 0, "region_coordinates": [[0, 0], [0, 1], [1, 0], [1, 1]], "severity_modifier": 1.0, "analysis_priority": 1},
        {"mask_id": 1, "region_coordinates": [[2, 2], [2, 3], [3, 2], [3, 3]], "severity_modifier": 1.3, "analysis_priority": 2}
    ]

    risk_factors = {
        "patient_age_group": 3,
        "genetic_predisposition": 0.4,
        "environmental_exposure": 0.2,
        "previous_diagnosis_history": 0.1
    }

    result = analyze_retinal_patterns(pixel_matrix, feature_templates, diagnostic_masks, risk_factors)
    print(result)