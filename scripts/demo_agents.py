"""
Demo script for LLM agents.

Shows CostEstimatorAgent and ValidatorAgent in action with AI reasoning.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime

from src.models.damage import DamageClaim, DamageAssessment, DamageType, DamageSeverity, VehicleLocation
from src.agents.cost_estimator_agent import CostEstimatorAgent
from src.agents.validator_agent import ValidatorAgent
from src.persistence.database import get_db
from src.config.settings import settings


def demo_cost_estimator():
    """Demo cost estimator agent with edge cases."""
    print("\n" + "="*70)
    print("COST ESTIMATOR AGENT DEMO")
    print("="*70)

    # Test case 1: Borderline cost near threshold
    print("\n\n📋 Test Case 1: Borderline Cost (€480)")
    print("-" * 70)

    claim1 = DamageClaim(
        claim_id="CLM-AGENT-TEST-001",
        timestamp=datetime.now(),
        vehicle_id="BMW-X5-2020-006",
        customer_id="CUST-5678",
        rental_agreement_id="RNT-2026-001",
        return_location="Munich_Airport",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MEDIUM,
            location=VehicleLocation.DRIVER_DOOR,
            description="Medium scratch on driver door, customer has 2 prior claims in 6 months",
            affected_parts=["driver_door"],
            photos=["photo1.jpg"],
            inspector_id="INSP-DEMO",
            inspector_notes="Customer seems nervous"
        )
    )

    vehicle_context1 = {
        "age_years": 4,
        "mileage_km": 85000,
        "cumulative_damage_ytd": 1800,
        "recent_damage_count": 2
    }

    db = next(get_db())
    agent = CostEstimatorAgent(db, temperature=0.3)

    print(f"\nProcessing claim: {claim1.claim_id}")
    print(f"Vehicle: {claim1.vehicle_id}")
    print(f"Damage: {claim1.damage_assessment.damage_type.value} ({claim1.damage_assessment.severity.value})")
    print(f"Vehicle context: €{vehicle_context1['cumulative_damage_ytd']} YTD, {vehicle_context1['recent_damage_count']} recent claims")

    cost_estimate, ai_reasoning = agent.estimate_cost(claim1, vehicle_context1)

    print(f"\n💰 COST ESTIMATE: €{cost_estimate.total_eur:.2f}")
    print(f"   - Labor: €{cost_estimate.labor_cost_eur:.2f}")
    print(f"   - Parts: €{cost_estimate.parts_cost_eur:.2f}")

    if ai_reasoning:
        print(f"\n🤖 AI REASONING:")
        print(f"   {ai_reasoning}")
    else:
        print(f"\n✓ Deterministic result (no edge case detected)")


def demo_validator():
    """Demo validator agent with pattern analysis."""
    print("\n\n" + "="*70)
    print("VALIDATOR AGENT DEMO")
    print("="*70)

    # Test case: Ambiguous pattern
    print("\n\n📋 Test Case 2: Pattern Detection - Same Location")
    print("-" * 70)

    claim2 = DamageClaim(
        claim_id="CLM-AGENT-TEST-002",
        timestamp=datetime.now(),
        vehicle_id="VW-GOLF-2022-003",
        customer_id="CUST-7777",
        rental_agreement_id="RNT-2026-002",
        return_location="Munich_Airport",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MEDIUM,
            location=VehicleLocation.REAR_BUMPER,
            description="Scratch on rear bumper, third claim from Munich Airport this quarter",
            affected_parts=["rear_bumper"],
            photos=["photo2.jpg"],
            inspector_id="INSP-DEMO",
            inspector_notes="All damages at same location"
        )
    )

    fleet_context = {
        "location_damage_rate": "High - Munich Airport has 2x average damage rate",
        "avg_damage_cost": 450.0,
        "customer_history": "3 claims in 90 days, all at Munich Airport"
    }

    db = next(get_db())
    agent = ValidatorAgent(db, temperature=0.3)

    print(f"\nProcessing claim: {claim2.claim_id}")
    print(f"Vehicle: {claim2.vehicle_id}")
    print(f"Location: {claim2.return_location}")
    print(f"Pattern: 3 claims in 90 days at same location")

    validation_result, ai_reasoning = agent.validate_claim(claim2, 420.0, fleet_context)

    print(f"\n⚖️  VALIDATION RESULT:")
    print(f"   - Decision: {validation_result.routing_decision.value}")
    print(f"   - Fraud Risk: {validation_result.fraud_risk_score:.2f}/10")
    print(f"   - Flags: {len(validation_result.flags)}")

    for flag in validation_result.flags:
        print(f"     • {flag.flag_type}: {flag.description}")

    if ai_reasoning:
        print(f"\n🤖 AI REASONING:")
        print(f"   {ai_reasoning}")
    else:
        print(f"\n✓ Deterministic result (no ambiguity detected)")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("LLM AGENTS DEMONSTRATION")
    print("="*70)
    print("\nShowing how agents add AI reasoning to edge cases...")

    # Check API key status
    if settings.google_api_key:
        print("✓ GOOGLE_API_KEY configured - AI reasoning ENABLED")
        print("  Model: gemini-3-flash-preview")
    else:
        print("⚠ GOOGLE_API_KEY not configured - falling back to deterministic logic")

    try:
        demo_cost_estimator()
        demo_validator()

        print("\n\n" + "="*70)
        print("DEMO COMPLETE")
        print("="*70)
        print("\nKey Points:")
        print("  • Agents wrap deterministic services with LLM reasoning")
        print("  • LLM activates only for edge cases (near thresholds, ambiguous patterns)")
        print("  • Fallback to deterministic if LLM unavailable")
        print("  • Transparent reasoning for human reviewers")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
