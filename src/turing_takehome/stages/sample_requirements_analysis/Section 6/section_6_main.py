"""Section 6 runner.

This script executes all per-column evaluators for Section 6. Each column
module owns its own verdict logic. This section runner only coordinates execution order
and aggregates subsection-level averages for the workbook's second tab.
"""

from pathlib import Path

from audit_core.section_runner import run_section


def run(contexts):
    return run_section("6", Path(__file__).parent, contexts)
