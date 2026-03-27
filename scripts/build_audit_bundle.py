from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "audit"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
STAGE1_SECTION_DIR = PROJECT_ROOT / "src" / "turing_takehome" / "stages" / "sample_requirements_analysis"


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return True


def copy_file_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def extract_stage1_prompts(target_dir: Path) -> list[dict[str, str]]:
    prompt_records: list[dict[str, str]] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(r"prompt\s*=\s*f?([\"']{3})(.*?)(?:\1)", re.DOTALL)
    for source_path in sorted(STAGE1_SECTION_DIR.glob("Section */*.py")):
        if source_path.name.startswith("section_"):
            continue
        text = source_path.read_text(encoding="utf-8")
        match = pattern.search(text)
        if not match:
            continue
        prompt_text = match.group(2).strip()
        target_path = target_dir / f"{source_path.stem}.txt"
        target_path.write_text(
            "\n".join(
                [
                    f"Source: {source_path.relative_to(PROJECT_ROOT)}",
                    "",
                    prompt_text,
                ]
            ),
            encoding="utf-8",
        )
        prompt_records.append(
            {
                "source": str(source_path.relative_to(PROJECT_ROOT)),
                "prompt_file": str(target_path.relative_to(PROJECT_ROOT)),
            }
        )
    return prompt_records


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    reset_dir(ARTIFACTS_DIR / "stage1")
    reset_dir(ARTIFACTS_DIR / "stage2")
    reset_dir(ARTIFACTS_DIR / "stage3")
    reset_dir(ARTIFACTS_DIR / "stage4")
    reset_dir(ARTIFACTS_DIR / "run_manifests")

    prompt_records = extract_stage1_prompts(ARTIFACTS_DIR / "stage1" / "prompts")
    write_text(
        ARTIFACTS_DIR / "stage1" / "traces" / "README.md",
        "\n".join(
            [
                "# Stage 1 Trace Notes",
                "",
                "Stage 1 preserves exact evaluator code and extracted prompt templates in this audit bundle.",
                "The canonical Stage 1 run did not persist per-call request and response traces the way Stage 2 does.",
                "This is intentional repository history rather than a missing file copy.",
            ]
        ),
    )
    write_text(
        ARTIFACTS_DIR / "stage1" / "prompts" / "manifest.json",
        json.dumps({"prompt_templates": prompt_records}, indent=2),
    )

    copy_tree_if_exists(
        OUTPUTS_DIR / "sample_efficacy_analysis" / "traces",
        ARTIFACTS_DIR / "stage2" / "traces",
    )
    for filename in [
        "run_manifest.json",
        "summary.md",
        "sample_results.csv",
        "sample_model_results.csv",
        "model_attempts.jsonl",
        "per_test_results.jsonl",
    ]:
        copy_file_if_exists(
            OUTPUTS_DIR / "sample_efficacy_analysis" / filename,
            ARTIFACTS_DIR / "stage2" / "artifacts" / filename,
        )

    copy_tree_if_exists(
        OUTPUTS_DIR / "dataset_analysis" / "stage3_auditor_traces",
        ARTIFACTS_DIR / "stage3" / "traces" / "stage3_auditor_traces",
    )
    copy_tree_if_exists(
        OUTPUTS_DIR / "dataset_analysis" / "embedding_traces",
        ARTIFACTS_DIR / "stage3" / "traces" / "embedding_traces",
    )
    for filename in [
        "run_manifest.json",
        "dataset_analysis.json",
        "dataset_analysis.xlsx",
        "dataset_summary.json",
        "summary.md",
        "audit_queues.json",
        "relationship_analysis.json",
    ]:
        copy_file_if_exists(
            OUTPUTS_DIR / "dataset_analysis" / filename,
            ARTIFACTS_DIR / "stage3" / "artifacts" / filename,
        )

    for filename in [
        "run_manifest.json",
        "review_packet.json",
        "review_template.csv",
        "manual_audit.json",
        "manual_audit.xlsx",
        "summary.md",
    ]:
        copy_file_if_exists(
            OUTPUTS_DIR / "manual_audit" / filename,
            ARTIFACTS_DIR / "stage4" / "artifacts" / filename,
        )

    copy_file_if_exists(PROJECT_ROOT / "RUN_MANIFEST.json", ARTIFACTS_DIR / "run_manifests" / "RUN_MANIFEST.json")
    copy_file_if_exists(
        OUTPUTS_DIR / "sample_efficacy_analysis" / "run_manifest.json",
        ARTIFACTS_DIR / "run_manifests" / "stage2_run_manifest.json",
    )
    copy_file_if_exists(
        OUTPUTS_DIR / "dataset_analysis" / "run_manifest.json",
        ARTIFACTS_DIR / "run_manifests" / "stage3_run_manifest.json",
    )
    copy_file_if_exists(
        OUTPUTS_DIR / "manual_audit" / "run_manifest.json",
        ARTIFACTS_DIR / "run_manifests" / "stage4_run_manifest.json",
    )

    write_text(
        ARTIFACTS_DIR / "bundle_manifest.json",
        json.dumps(
            {
                "stage1_prompt_templates": len(prompt_records),
                "stage2_traces_present": (ARTIFACTS_DIR / "stage2" / "traces").exists(),
                "stage3_stage3_auditor_traces_present": (ARTIFACTS_DIR / "stage3" / "traces" / "stage3_auditor_traces").exists(),
                "stage3_embedding_traces_present": (ARTIFACTS_DIR / "stage3" / "traces" / "embedding_traces").exists(),
                "stage4_review_packet_present": (ARTIFACTS_DIR / "stage4" / "artifacts" / "review_packet.json").exists(),
            },
            indent=2,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
