#!/usr/bin/env python
"""
Demo script for running the damage claim workflow.

Processes all test scenarios and shows the workflow results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.models.damage import (
    DamageClaim,
    DamageAssessment,
    DamageType,
    DamageSeverity,
    VehicleLocation,
)
from src.graph.workflow import DamageClaimWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_scenario(scenario_path: Path) -> DamageClaim:
    """Load a test scenario and convert to DamageClaim."""
    with open(scenario_path) as f:
        data = json.load(f)

    claim_data = data["damage_claim"]
    assessment = claim_data["damage_assessment"]

    return DamageClaim(
        claim_id=claim_data["claim_id"],
        timestamp=datetime.fromisoformat(claim_data["timestamp"].replace("Z", "+00:00")),
        vehicle_id=claim_data["vehicle_id"],
        customer_id=claim_data["customer_id"],
        rental_agreement_id=claim_data["rental_agreement_id"],
        return_location=claim_data["return_location"],
        damage_assessment=DamageAssessment(
            damage_type=DamageType(assessment["damage_type"]),
            severity=DamageSeverity(assessment["severity"]),
            location=VehicleLocation(assessment["location"]),
            description=assessment["description"],
            affected_parts=assessment["affected_parts"],
            photos=assessment["photos"],
            inspector_id=assessment["inspector_id"],
            inspector_notes=assessment.get("inspector_notes")
        )
    )


def print_result(scenario_name: str, result):
    """Print formatted workflow result."""
    print("\n" + "=" * 70)
    print(f"Scenario: {scenario_name}")
    print("=" * 70)

    print(f"\nClaim ID: {result.claim.claim_id}")
    print(f"Vehicle: {result.claim.vehicle_id}")
    print(f"Customer: {result.claim.customer_id}")
    print(f"Damage: {result.claim.damage_assessment.damage_type.value} ({result.claim.damage_assessment.severity.value})")

    if result.cost_estimate:
        print(f"\nCost Estimate: €{result.cost_estimate.total_eur:.2f}")
        if result.cost_estimate.depreciation_applicable:
            print(f"  - Depreciation applied: {result.cost_estimate.depreciation_factor:.0%}")
            print(f"  - Original cost: €{result.cost_estimate.subtotal_eur:.2f}")

    if result.validation_result:
        print(f"\nValidation:")
        print(f"  - Can auto-approve: {result.validation_result.can_auto_approve}")
        print(f"  - Decision: {result.validation_result.routing_decision.value}")
        print(f"  - Reason: {result.validation_result.routing_reason}")
        if result.validation_result.flags:
            print(f"  - Flags: {[f.flag_type for f in result.validation_result.flags]}")

    print(f"\nWorkflow Status:")
    print(f"  - Complete: {result.workflow_complete}")
    print(f"  - Requires approval: {result.requires_human_approval}")
    if result.approval_granted is not None:
        print(f"  - Approved: {result.approval_granted}")


def main():
    """Run workflow demo with all scenarios."""
    print("\n" + "=" * 70)
    print("DAMAGE CLAIM WORKFLOW DEMO")
    print("=" * 70)

    # Initialize workflow
    workflow = DamageClaimWorkflow(use_checkpointer=False)

    # Find scenarios
    scenarios_dir = Path(__file__).parent.parent / "data" / "sample_scenarios"
    scenarios = sorted(scenarios_dir.glob("*.json"))

    if not scenarios:
        print("No scenarios found!")
        return

    print(f"\nFound {len(scenarios)} scenarios to process\n")

    # Process each scenario
    results = []
    for scenario_path in scenarios:
        try:
            scenario_name = scenario_path.stem.replace("_", " ").title()
            print(f"\nProcessing: {scenario_name}...")

            claim = load_scenario(scenario_path)
            result = workflow.process_claim(claim)
            results.append((scenario_name, result))

            # Quick status
            if result.approval_granted:
                status = "AUTO-APPROVED"
            elif result.requires_human_approval:
                status = "NEEDS HUMAN REVIEW"
            else:
                status = "PROCESSING"
            print(f"  -> {status}")

        except Exception as e:
            # KeyError '__end__' means workflow paused at human_review
            if "'__end__'" in str(e):
                logger.warning(f"Workflow paused for human review: {scenario_path}")
                print(f"  -> PAUSED FOR HUMAN REVIEW (workflow interrupted)")
            else:
                logger.error(f"Error processing {scenario_path}: {e}")
                print(f"  -> ERROR: {e}")

    # Print detailed results
    print("\n\n" + "=" * 70)
    print("DETAILED RESULTS")
    print("=" * 70)

    for scenario_name, result in results:
        print_result(scenario_name, result)

    # Summary
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    auto_approved = sum(1 for _, r in results if r.approval_granted)
    needs_review = sum(1 for _, r in results if r.requires_human_approval and not r.approval_granted)

    print(f"\nTotal scenarios: {len(results)}")
    print(f"Auto-approved: {auto_approved}")
    print(f"Needs review: {needs_review}")


if __name__ == "__main__":
    main()
