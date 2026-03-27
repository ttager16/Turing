# Stage 3 Dataset Analysis

- Samples analyzed: 155
- Biggest structural risks: 9.0% of samples are already flagged as suspicious or broken.; 33 samples appear materially redundant or template-recycled.; 22 samples look strong statically but fail dynamically.; 32 samples show volatile repeated-attempt behavior.
- Strongest Stage 1 to Stage 2 signal: Stage1Section1Score
- Recommended next actions: Deduplicate or downweight near-identical prompt templates before using aggregate scores.; Prioritize manual review for samples failing Stage1Section1Score.; Treat unstable repeated-attempt samples as caveated benchmark signal, not clean difficulty evidence.; Use cross-model disagreement to triage ambiguous benchmark items before trusting aggregate conclusions.

## Audit Queues
### benchmark_defect_candidates
- Index 152 (146870): ambiguous_or_brittle [priority=critical, utility=caveated, redundancy=0.0]
- Index 0 (146030): oracle or benchmark artifact appears misaligned [priority=critical, utility=caveated, redundancy=0.0]
- Index 3 (146037): oracle or benchmark artifact appears misaligned [priority=critical, utility=caveated, redundancy=0.0]
- Index 92 (146553): oracle or benchmark artifact appears misaligned [priority=critical, utility=caveated, redundancy=0.0]
- Index 104 (146634): oracle or benchmark artifact appears misaligned [priority=critical, utility=caveated, redundancy=0.693]
### redundancy_candidates
- Index 137 (146753): semantic_duplicate vs 145 at 0.7206 [priority=medium, utility=usable, redundancy=0.7206]
- Index 145 (146781): semantic_duplicate vs 137 at 0.7206 [priority=critical, utility=contradictory, redundancy=0.7206]
- Index 72 (146436): near_duplicate vs 112 at 0.7192 [priority=medium, utility=usable, redundancy=0.7192]
- Index 112 (146676): near_duplicate vs 72 at 0.7192 [priority=medium, utility=usable, redundancy=0.7192]
- Index 38 (146223): semantic_duplicate vs 45 at 0.7184 [priority=medium, utility=usable, redundancy=0.7184]
### contradictory_candidates
- Index 154 (146942): high_static_low_dynamic [priority=critical, utility=caveated, redundancy=0.0]
- Index 152 (146870): high_static_low_dynamic [priority=critical, utility=caveated, redundancy=0.0]
- Index 145 (146781): high_static_low_dynamic [priority=critical, utility=contradictory, redundancy=0.7206]
- Index 141 (146768): high_static_low_dynamic [priority=critical, utility=caveated, redundancy=0.0]
- Index 136 (146756): high_static_low_dynamic [priority=critical, utility=contradictory, redundancy=0.0]
### trivial_candidates
- Index 13 (146119): near-saturated pass rate with otherwise clean Stage 1 signals [priority=high, utility=saturated, redundancy=0.0]
- Index 16 (146117): near-saturated pass rate with otherwise clean Stage 1 signals [priority=high, utility=saturated, redundancy=0.0]
- Index 108 (146639): near-saturated pass rate with otherwise clean Stage 1 signals [priority=high, utility=saturated, redundancy=0.0]
- Index 66 (146385): near-saturated pass rate with otherwise clean Stage 1 signals [priority=medium, utility=saturated, redundancy=0.0]
- Index 110 (146655): near-saturated pass rate with otherwise clean Stage 1 signals [priority=medium, utility=saturated, redundancy=0.693]
### exemplar_candidates
- Index 130 (146736): clean, interpretable, non-redundant evaluation candidate [priority=high, utility=strong, redundancy=0.0]
- Index 8 (146099): clean, interpretable, non-redundant evaluation candidate [priority=medium, utility=strong, redundancy=0.0]
- Index 62 (146376): clean, interpretable, non-redundant evaluation candidate [priority=medium, utility=strong, redundancy=0.0]
- Index 146 (146798): clean, interpretable, non-redundant evaluation candidate [priority=medium, utility=strong, redundancy=0.0]
- Index 4 (146048): clean, interpretable, non-redundant evaluation candidate [priority=normal, utility=strong, redundancy=0.0]

## Stage 1 to Stage 2 Relationships
- Stage1Section1Score: sample_count=155, pass_delta=0.3699, suspicious_lift=0.0597
- Stage1Score: sample_count=155, pass_delta=0.3187, suspicious_lift=-0.0633
- Stage1Section6Score: sample_count=155, pass_delta=0.1479, suspicious_lift=-0.1296
- Stage1Section2Score: sample_count=155, pass_delta=0.1068, suspicious_lift=-0.0949
- 1.2_practical_algorithmic_problem: sample_count=94, pass_delta=-0.2263, suspicious_lift=-0.0133
