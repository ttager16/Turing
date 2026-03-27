# Exemplar Set

Purpose: public note describing the chosen exemplar samples, the benchmark behavior each one is meant to illustrate, and where a reviewer should look if they want to validate the claim further.

These are not exhaustive case studies. They are the cleanest representative examples I selected for the final report.

Open these alongside:

- `outputs/dataset_analysis.xlsx`
- `outputs/workbook_field_guide.xlsx`
- `python main.py --manual-audit`

## 1. Benchmark Defect

### Sample 104

Claim:
- Sample `104` is the cleanest benchmark-defect exemplar in the dataset.

Why this is a good example:
- Stage 1 already treats the artifact as structurally weak: `Needs Fixing / Unusable / Unusable`.
- Stage 2 is the real smoking gun. The oracle probe fails outright (`OracleProbeStatus = error`, `OraclePassRate = 0.0`), but the model still posts a superficially high pass rate (`WinnerCombinedPassRate = 0.9286`). That is exactly the kind of pattern that should make a benchmark auditor distrust the artifact rather than praise the model or the sample.
- Stage 3 then does what it should do with that pattern: it escalates the sample as a critical benchmark-defect candidate.

What in the sample makes this plausible even before opening the code:
- The prompt is a sprawling “smart-city multi-level resource allocation” task with layered compatibility, merge/split operations, maintenance states, and a custom bipartite graph object. That is the kind of over-specified, heavily engineered task where oracle or grading mismatches are especially easy to hide.

Where to validate:
- `Stage1_Summary` and `Stage1_Detailed` for the structural failures
- `Stage2_Summary` for `OracleProbeStatus`, `OraclePassRate`, `FailureCategory`, and `BenchmarkQualitySignal`
- `Stage3_Detailed` for the critical benchmark-defect flag

## 2. Contradiction

### Sample 141

Claim:
- Sample `141` is the best contradiction exemplar: the static artifact looks bad, the dynamic behavior still produces strong model failure, and the two signals do not line up cleanly.

Why this is a good example:
- Stage 1 rates it `Unusable / Unusable / Unusable`.
- Stage 2 marks it `Suspicious (Needs Audit)` with a very low combined pass rate (`0.1765`), but the oracle is still mostly successful (`OraclePassRate = 0.9333`).
- Stage 3 explicitly calls this out as `high_static_low_dynamic` and also escalates it as a benchmark-defect candidate.

What in the sample makes the contradiction legible:
- The prompt is a highly specific “Martian rover” planning problem with two agents, terrain instability, a shared power budget, and mission sequencing. It is the sort of task where a benchmark can look rich and challenging while still being misaligned or brittle in how it is actually tested.
- The useful point here is not that the sample is merely hard. It is that “hard-looking”, “artifact-quality”, and “clean benchmark signal” are three different things.

Where to validate:
- `Stage1_Summary` for the total structural collapse
- `Stage2_Summary` for the low pass rate plus suspicious label
- `Stage3_Detailed` for `ContradictionCheck = high_static_low_dynamic`

## 3. Redundancy

### Samples 137 and 145

Claim:
- Samples `137` and `145` are the clearest redundancy pair in the final dataset slice.

Why this pair is a good example:
- Stage 3 marks them as a semantic-duplicate pair.
- They share the same function name, `optimize_delivery_route`.
- Their similarity is high in exactly the way that matters here: low-to-moderate lexical overlap but very high embedding similarity (`0.9198`), which is what you would expect when two prompts are paraphrased versions of the same underlying task.

What in the prompts makes that visible:
- Both are global-logistics / delivery-network routing tasks.
- Both ask for a route optimizer over a graph with layered operational constraints rather than a plain shortest-path problem.
- The wording differs, but the benchmark signal is basically the same: graph routing under extra constraints, with the model being asked to solve a very similar planning structure twice.

Why I like this pair:
- It is a cleaner redundancy story than a trivial duplicate or a title-only duplicate. It shows the failure mode that matters more in practice: duplicated capability coverage hiding behind paraphrase.

Where to validate:
- `Stage3_Detailed` for `RedundancyStatus`
- `outputs/dataset_analysis/duplicate_pairs.csv` for the pairwise similarity record

## 4. Saturated / Trivial

### Sample 11

Claim:
- Sample `11` is the cleanest saturated / low-information exemplar.

Why this is a good example:
- Stage 2 gives it `Low Efficacy` with a near-perfect combined pass rate (`0.9565`) and a failure category of `clean_pass`.
- Stage 3 then flags both threshold sensitivity and triviality.
- In other words, the sample is not failing because it is broken; it is failing because it contributes too little marginal difficulty.

What in the prompt makes that believable:
- The task is a station-placement / maximize-minimum-distance problem with connectivity constraints. That is a perfectly legitimate problem type, but in this specific formulation it appears to be yielding very little discriminative pressure on the evaluated model.
- This is exactly why triviality matters as a distinct category. A sample can be valid and still not pull its weight in a benchmark.

Where to validate:
- `Stage2_Summary` for `EfficacyLabel = Low Efficacy` and `WinnerCombinedPassRate = 0.9565`
- `Stage3_Detailed` for `TrivialityCheck = FLAG`

## 5. Strong Exemplar

### Sample 17

Claim:
- Sample `17` is the strongest positive exemplar in the current dataset: a sample that looks behaviorally informative without immediately looking broken or redundant.

Why this is a good example:
- Stage 1 rates it `Needs Fixing / Needs Fixing / Needs Fixing`, which is not perfect but is much cleaner than many other otherwise-interesting samples.
- Stage 2 gives it `High Efficacy` with `clean_evaluation`.
- Stage 3 explicitly surfaces it as an exemplar candidate without an elevated audit-warning story attached.
- Unlike the defect-oriented examples above, this one is not interesting because something went wrong. It is interesting because it appears to do what a benchmark item is supposed to do: produce meaningful model failure without triggering obvious trust alarms.

What in the prompt supports that read:
- It is a graph / algorithmic problem that still produces real model failure without immediately reading as a broken or redundant artifact.
- The dynamic profile is good for a positive example: the benchmark-quality signal is clean, and the model still fails enough tests for the sample to be informative.

Where to validate:
- `Stage1_Summary` for the comparatively cleaner artifact-quality profile
- `Stage2_Summary` for the clean high-efficacy profile
- `Stage3_Detailed` for `ExemplarCheck = FLAG`

## 6. Disagreement / Brittleness

### Sample 87

Claim:
- Sample `87` is the best disagreement / brittleness exemplar.

Why this is a good example:
- Stage 2 labels it `ambiguous_or_brittle` and marks it for audit even though the oracle is perfect (`OraclePassRate = 1.0`) and the overall pass rate is high (`0.9429`).
- The observed failures are tiny in count but messy in kind: one `format_mismatch`, one `incorrect_output`.
- Stage 3 then flags threshold sensitivity and escalates it as a benchmark-defect candidate.

What in the sample makes this plausible:
- The task is a Fenwick-tree / stock-analysis problem, which is a comparatively standard algorithm/data-structure task. That matters, because it helps show that brittleness is not only a problem of absurdly overengineered prompts. Even a fairly standard seeming sample can become caveated if the failure surface is brittle enough.

Why this is a useful exemplar:
- It sits exactly on the boundary where a benchmark team has to decide whether they are looking at a real miss, a brittle grader, or both. That is the kind of judgment call a dataset-governance process needs to surface.

Where to validate:
- `Stage2_Summary` for `BenchmarkQualitySignal = ambiguous_or_brittle`
- `Stage3_Detailed` for `ThresholdSensitivityCheck = FLAG` and `BenchmarkDefectCandidate = FLAG`

## Using The Web UI

The Stage 4 web UI exposes this same exemplar set directly:

```bash
python main.py --manual-audit
```

From the home page, open `Exemplar Set`, or jump directly to any dataset index if you want to inspect a sample outside the curated set.
