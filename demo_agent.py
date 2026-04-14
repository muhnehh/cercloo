#!/usr/bin/env python3
"""
Agentic demo entry point for Cercli.

This is the version to show in an agents interview or portfolio review.
It uses the agent loop instead of the older fixed demo flow.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agentic import CercliAgent


def main() -> None:
    agent = CercliAgent(
        data_dir="datasets",
        output_dir="outputs",
        jurisdiction="UAE",
        use_rag=True,
        confidence_threshold=0.8,
        max_iterations=2,
    )
    result = agent.run_agent()

    print("\nSUMMARY")
    print("-" * 80)
    evaluation = result.get("mapping_evaluation", {})
    compliance = result.get("compliance_report", {})

    print(f"Mappings evaluated: {evaluation.get('evaluated_columns', 0)}")
    print(f"Mapping accuracy: {evaluation.get('accuracy', 'n/a')}")
    print(f"Review required: {evaluation.get('review_required', False)}")
    print(f"Artifacts: {len(result.get('artifacts', {}))}")
    if compliance:
        print(f"Violations: {compliance.get('total_violations', 0)}")
    else:
        print("Violations: n/a")


if __name__ == "__main__":
    main()
