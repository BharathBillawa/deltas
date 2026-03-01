"""
Cost Estimator Agent - LLM-powered cost estimation with reasoning.

Wraps PricingService and DepreciationService with LLM reasoning
to handle edge cases and ambiguous situations.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.services.pricing_service import PricingService
from src.services.depreciation_service import DepreciationService
from src.models.damage import DamageClaim
from src.models.financial import CostEstimate

logger = logging.getLogger(__name__)


class CostEstimatorAgent(BaseAgent):
    """
    LLM-powered cost estimation agent.

    Responsibilities:
    - Call PricingService for base cost calculation
    - Call DepreciationService for part depreciation
    - Use LLM to reason about edge cases:
      * Borderline costs near approval thresholds
      * Complex multi-part damage
      * Missing or ambiguous information
      * Unusual damage patterns
    - Provide explanation for cost decisions
    """

    def __init__(self, db_session: Session, temperature: float = 0.3):
        """
        Initialize cost estimator agent.

        Args:
            db_session: Database session for service access
            temperature: LLM temperature
        """
        super().__init__(temperature=temperature)
        self.pricing_service = PricingService()
        self.depreciation_service = DepreciationService()
        self.db = db_session

    def estimate_cost(
        self,
        claim: DamageClaim,
        vehicle_context: Optional[Dict[str, Any]] = None
    ) -> tuple[CostEstimate, Optional[str]]:
        """
        Estimate repair cost with LLM reasoning.

        Args:
            claim: Damage claim to estimate
            vehicle_context: Optional vehicle history/context

        Returns:
            Tuple of (CostEstimate, reasoning_explanation)
        """
        # Step 1: Get deterministic cost from services
        base_estimate = self._get_base_estimate(claim, vehicle_context)

        # Step 2: Check if LLM reasoning is needed
        needs_reasoning = self._needs_llm_reasoning(base_estimate, claim, vehicle_context)

        if not needs_reasoning or not self.llm:
            # Use deterministic result
            logger.info(f"Using deterministic cost estimate: €{base_estimate.total_eur}")
            return base_estimate, None

        # Step 3: Get LLM reasoning
        reasoning = self._get_llm_reasoning(claim, base_estimate, vehicle_context)

        # Step 4: Attach LLM reasoning to the estimate
        final_estimate, explanation = self._build_reasoning_explanation(
            base_estimate,
            reasoning,
            claim
        )

        logger.info(f"Cost estimate with LLM reasoning: €{final_estimate.total_eur}")
        return final_estimate, explanation

    def _get_base_estimate(
        self,
        claim: DamageClaim,
        vehicle_context: Optional[Dict[str, Any]]
    ) -> CostEstimate:
        """Get base cost estimate from deterministic services."""
        # Get vehicle category from claim context (critical for correct pricing)
        vehicle_category = "Standard"
        if claim.vehicle_context:
            vehicle_category = claim.vehicle_context.category.value

        # Calculate base cost
        cost_estimate = self.pricing_service.calculate_cost(
            claim_id=claim.claim_id,
            damage_type=claim.damage_assessment.damage_type,
            severity=claim.damage_assessment.severity,
            vehicle_category=vehicle_category,
            location=claim.return_location,
            damage_location=claim.damage_assessment.location.value
        )

        # Apply depreciation if vehicle context available
        # Note: Simplified - in production would check if depreciation should apply
        if vehicle_context and "age_years" in vehicle_context and vehicle_context["age_years"] >= 2:
            component = self.depreciation_service.infer_component_from_location(
                claim.damage_assessment.location.value
            )

            depreciation_calc = self.depreciation_service.calculate(
                vehicle_id=claim.vehicle_id,
                vehicle_year=datetime.now().year - vehicle_context["age_years"],
                original_cost_eur=cost_estimate.subtotal_eur,
                component=component
            )

            # Update cost estimate with depreciation
            cost_estimate.depreciation_applicable = True
            cost_estimate.depreciation_component = component
            cost_estimate.depreciation_factor = depreciation_calc.depreciation_factor
            cost_estimate.depreciated_value_eur = depreciation_calc.depreciated_value_eur
            cost_estimate.total_eur = depreciation_calc.depreciated_value_eur

        return cost_estimate

    def _needs_llm_reasoning(
        self,
        estimate: CostEstimate,
        claim: DamageClaim,
        vehicle_context: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Determine if LLM reasoning is needed.

        Triggers:
        - Cost near approval threshold (€450-550)
        - Multiple affected parts
        - High cumulative vehicle damage
        - Missing information
        """
        AUTO_APPROVE_THRESHOLD = 500.0

        # Near threshold (+/- €50)
        if abs(estimate.total_eur - AUTO_APPROVE_THRESHOLD) < 50:
            return True

        # Multiple parts
        if len(claim.damage_assessment.affected_parts) > 2:
            return True

        # High cumulative damage
        if vehicle_context and vehicle_context.get("cumulative_damage_ytd", 0) > 2000:
            return True

        # Missing critical info
        if not claim.damage_assessment.description or len(claim.damage_assessment.description) < 20:
            return True

        return False

    def _get_llm_reasoning(
        self,
        claim: DamageClaim,
        estimate: CostEstimate,
        vehicle_context: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Get LLM reasoning about cost estimate."""

        system_prompt = """You are an expert automotive damage cost estimator for a car rental company.

Your role is to analyze repair cost estimates and provide reasoning about:
1. Whether the estimate seems accurate given the damage description
2. Any concerns or flags that should be raised
3. Recommendations for approval routing (auto-approve vs human review)
4. Risk factors based on vehicle history

Be concise but thorough. Focus on practical business decisions."""

        human_prompt = """Analyze this damage claim and cost estimate:

CLAIM DETAILS:
- Vehicle ID: {vehicle_id}
- Damage Type: {damage_type}
- Severity: {severity}
- Location: {location}
- Description: {description}
- Affected Parts: {affected_parts}

COST ESTIMATE:
- Labor Cost: €{labor_cost}
- Parts Cost: €{parts_cost}
- Total: €{total_cost}

VEHICLE CONTEXT:
- Cumulative Damage YTD: €{cumulative_damage}
- Vehicle Age: {vehicle_age} years
- Recent Damage Count: {recent_damage_count}

AUTO-APPROVE THRESHOLD: €500

QUESTIONS:
1. Is this cost estimate reasonable for the described damage?
2. Should this be auto-approved or sent for human review?
3. What risk factors or concerns should be noted?

Provide your analysis and recommendation in 3-4 sentences."""

        variables = {
            "vehicle_id": claim.vehicle_id,
            "damage_type": claim.damage_assessment.damage_type.value,
            "severity": claim.damage_assessment.severity.value,
            "location": claim.damage_assessment.location.value,
            "description": claim.damage_assessment.description or "No description provided",
            "affected_parts": ", ".join(claim.damage_assessment.affected_parts),
            "labor_cost": f"{estimate.labor_cost_eur:.2f}",
            "parts_cost": f"{estimate.parts_cost_eur:.2f}",
            "total_cost": f"{estimate.total_eur:.2f}",
            "cumulative_damage": f"{vehicle_context.get('cumulative_damage_ytd', 0):.0f}" if vehicle_context else "0",
            "vehicle_age": f"{vehicle_context.get('age_years', 0)}" if vehicle_context else "Unknown",
            "recent_damage_count": f"{vehicle_context.get('recent_damage_count', 0)}" if vehicle_context else "0",
        }

        prompt = self._create_prompt(system_prompt, human_prompt)
        return self._invoke_llm(prompt, variables)

    def _build_reasoning_explanation(
        self,
        base_estimate: CostEstimate,
        reasoning: Optional[str],
        claim: DamageClaim
    ) -> tuple[CostEstimate, Optional[str]]:
        """
        Build reasoning explanation to attach to the estimate.

        The deterministic estimate is preserved; reasoning provides
        transparency for reviewers on why the estimate was flagged.
        """
        if not reasoning:
            return base_estimate, None

        # Keep base estimate, but return reasoning for transparency
        explanation = f"AI Analysis: {reasoning}"

        logger.info(f"LLM reasoning for claim {claim.claim_id}: {reasoning[:100]}...")

        return base_estimate, explanation
