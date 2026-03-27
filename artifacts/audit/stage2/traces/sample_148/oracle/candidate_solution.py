from typing import List, Dict, Any
import math


def analyze_mandelbrot_invariants(
    grid_resolution: int,
    transformation_codes: List[int]
) -> Dict[str, Any]:
    """
    Detect invariant point clusters under a sequence of coded transformations.

    Args:
        grid_resolution: Grid size N × N (N ≥ 1)
        transformation_codes: List of integers 0–4 selecting transformations

    Returns:
        Dictionary with invariant clusters and analysis summary
    """
    # Handle edge case: grid_resolution = 1
    if grid_resolution == 1:
        return {
            'invariant_subgraphs': [[[0.0, 0.0]]],
            'analysis_summary': {
                'total_points': 1,
                'num_layers': len(transformation_codes) + 1,
                'num_invariant_components': 1,
                'largest_component_size': 1,
                'detected_symmetries': ['point_symmetry_at_origin']
            }
        }
    
    # Normal case: grid_resolution > 1
    step = 4.0 / (grid_resolution - 1)
    grid_points = []
    for i in range(grid_resolution):
        for j in range(grid_resolution):
            x = i * step - 2.0
            y = j * step - 2.0
            grid_points.append(complex(x, y))
    
    point_to_id = {pt: idx for idx, pt in enumerate(grid_points)}
    grid_set = set(grid_points)
    
    transformations = {
        0: lambda z: z.conjugate(),
        1: lambda z: z * 1j,
        2: lambda z: z * 0.5,
        3: lambda z: complex(z.real, 0.0),
        4: lambda z: -z
    }
    
    def snap_to_grid(w):
        rx = round((w.real + 2.0) / step) * step - 2.0
        ry = round((w.imag + 2.0) / step) * step - 2.0
        
        if abs(rx) > 2.0 + 1e-9 or abs(ry) > 2.0 + 1e-9:
            return None
        
        snapped = complex(rx, ry)
        return snapped if snapped in grid_set else None
    
    parent = list(range(len(grid_points)))
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    for code in transformation_codes:
        if code not in transformations:
            continue
        
        T = transformations[code]
        for z in grid_points:
            try:
                w = T(z)
                if not (math.isfinite(w.real) and math.isfinite(w.imag)):
                    continue
                if abs(w.real) > 2.0 or abs(w.imag) > 2.0:
                    continue
                
                snapped = snap_to_grid(w)
                if snapped is not None and snapped in point_to_id:
                    z_id = point_to_id[z]
                    w_id = point_to_id[snapped]
                    union(z_id, w_id)
            except:
                continue
    
    clusters_dict = {}
    for idx, pt in enumerate(grid_points):
        root = find(idx)
        if root not in clusters_dict:
            clusters_dict[root] = []
        clusters_dict[root].append(pt)
    
    clusters = [[[pt.real, pt.imag] for pt in cluster_points] 
                for cluster_points in clusters_dict.values()]
    
    for cluster in clusters:
        cluster.sort()
    
    clusters.sort(key=lambda c: (-len(c), c[0] if c else [0, 0]))
    
    detected_symmetries = []
    
    origin_cluster = None
    for cluster in clusters:
        if [0.0, 0.0] in cluster:
            origin_cluster = cluster
            break
    
    if origin_cluster and len(origin_cluster) == 1:
        detected_symmetries.append('point_symmetry_at_origin')
    
    axis_points = {(0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0)}
    for cluster in clusters:
        cluster_set = {(pt[0], pt[1]) for pt in cluster}
        if len(axis_points & cluster_set) == 4:
            detected_symmetries.append('4-fold_rotational_symmetry_on_axes')
            break
    
    return {
        'invariant_subgraphs': clusters,
        'analysis_summary': {
            'total_points': len(grid_points),
            'num_layers': len(transformation_codes) + 1,
            'num_invariant_components': len(clusters),
            'largest_component_size': len(clusters[0]) if clusters else 0,
            'detected_symmetries': detected_symmetries
        }
    }