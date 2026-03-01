"""
Validator Agent - LLM-powered validation with pattern reasoning.

Wraps PatternRecognitionService with LLM reasoning to handle
ambiguous patterns and fraud detection.
"""

import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.services.pattern_recognition_service import PatternRecognitionService
from src.models.damage import DamageClaim
from src.models.routing import ValidationResult, RoutingDecision, ValidationFlag, FlagSeverity

logger = logging.getLogger(__name__)


class ValidatorAgent(BaseAgent):
    """
    LLM-powered validation agent.

    Responsibilities:
    - Call PatternRecognitionService for pattern detection
    - Use LLM to reason about ambiguous patterns:
      * Is this fraud or bad luck?
      * Does location context explain pattern?
      * Is timing suspicious?
      * Customer history assessment
    - Provide explanation for validation decisions
    - Recommend routing with reasoning
    """

    def __init__(self, db_session: Session, temperature: float = 0.3):
        """
        Initialize validator agent.

        Args:
            db_session: Database session
            temperature: LLM temperature
        """
        super().__init__(temperature=temperature)
        self.pattern_service = PatternRecognitionService(db_session)
        self.db = db_session

    def validate_claim(
        self,
        claim: DamageClaim,
        cost_estimate_eur: float,
        fleet_context: Optional[Dict[str, Any]] = None
    ) -> tuple[ValidationResult, Optional[str]]:
        """
        Validate claim with LLM reasoning.

        Args:
            claim: Damage claim to validate
            cost_estimate_eur: Estimated repair cost
            fleet_context: Optional fleet analytics context

        Returns:
            Tuple of (ValidationResult, reasoning_explanation)
        """
        # Step 1: Get deterministic patterns from service
        patterns = self._detect_patterns(claim)

        # Step 2: Build initial validation result
        base_result = self._build_base_validation(claim, cost_estimate_eur, patterns)

        # Step 3: Check if LLM reasoning is needed
        needs_reasoning = self._needs_llm_reasoning(patterns, cost_estimate_eur)

        if not needs_reasoning or not self.llm:
            # Use deterministic result
            logger.info(f"Using deterministic validation: {base_result.routing_decision.value}")
            return base_result, None

        # Step 4: Get LLM reasoning
        reasoning = self._get_llm_reasoning(claim, patterns, cost_estimate_eur, fleet_context)

        # Step 5: Apply LLM reasoning to potentially adjust decision
        final_result, explanation = self._apply_llm_reasoning(
            base_result,
            reasoning,
            patterns
        )

        logger.info(f"Validation with LLM reasoning: {final_result.routing_decision.value}")
        return final_result, explanation

    def _detect_patterns(self, claim: DamageClaim) -> Dict[str, Any]:
        """Detect patterns using deterministic service."""
        # Analyze vehicle patterns
        vehicle_patterns = self.pattern_service.analyze_vehicle_patterns(claim.vehicle_id)

        # Build simplified pattern dict
        patterns = {
            "frequent_damage": len(vehicle_patterns) >= 3,
            "same_damage_type": any(p.pattern_type.value == "same_damage_type" for p in vehicle_patterns),
            "location_correlation": any(p.pattern_type.value == "location_correlation" for p in vehicle_patterns),
            "timing_pattern": "None",
            "fraud_risk_score": min(len(vehicle_patterns) * 0.3, 1.0)
        }

        return patterns

    def _build_base_validation(
        self,
        claim: DamageClaim,
        cost_estimate_eur: float,
        patterns: Dict[str, Any]
    ) -> ValidationResult:
        """Build initial validation result from deterministic checks."""

        flags: List[ValidationFlag] = []

        # Cost-based flags
        if cost_estimate_eur > 500:
            flags.append(ValidationFlag(
                flag_type="high_cost",
                description=f"Cost €{cost_estimate_eur:.2f} exceeds auto-approve threshold",
                severity=FlagSeverity.HIGH
            ))

        # Pattern-based flags
        if patterns.get("frequent_damage"):
            flags.append(ValidationFlag(
                flag_type="pattern_detected",
                description="Frequent damage pattern detected",
                severity=FlagSeverity.HIGH
            ))

        if patterns.get("same_damage_type"):
            flags.append(ValidationFlag(
                flag_type="pattern_detected",
                description="Repeated damage type detected",
                severity=FlagSeverity.WARNING
            ))

        # Determine routing
        if cost_estimate_eur > 500 or patterns.get("frequent_damage"):
            routing = RoutingDecision.HUMAN_REVIEW_REQUIRED
            can_auto_approve = False
            routing_reason = f"Requires human review: cost €{cost_estimate_eur:.2f}, patterns detected"
        else:
            routing = RoutingDecision.AUTO_APPROVE
            can_auto_approve = True
            routing_reason = f"Auto-approved: cost €{cost_estimate_eur:.2f} under threshold, no critical patterns"

        return ValidationResult(
            claim_id=claim.claim_id,
            is_valid=True,
            can_auto_approve=can_auto_approve,
            routing_decision=routing,
            routing_reason=routing_reason,
            fraud_risk_score=patterns.get("fraud_risk_score", 0.0) * 10,  # Scale to 0-10
            overall_risk_score=patterns.get("fraud_risk_score", 0.0) * 10,
            flags=flags
        )

    def _needs_llm_reasoning(
        self,
        patterns: Dict[str, Any],
        cost_estimate_eur: float
    ) -> bool:
        """
        Determine if LLM reasoning is needed.

        Triggers:
        - Any patterns detected
        - Cost near threshold
        - Moderate fraud risk (0.3-0.7)
        """
        # Patterns detected
        if patterns.get("frequent_damage") or patterns.get("location_correlation"):
            return True

        # Near threshold
        if 450 < cost_estimate_eur < 550:
            return True

        # Moderate fraud risk (ambiguous)
        fraud_risk = patterns.get("fraud_risk_score", 0.0)
        if 0.3 < fraud_risk < 0.7:
            return True

        return False

    def _get_llm_reasoning(
        self,
        claim: DamageClaim,
        patterns: Dict[str, Any],
        cost_estimate_eur: float,
        fleet_context: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Get LLM reasoning about validation decision."""

        system_prompt = """You are an expert fraud detection and claims validation specialist for a car rental company.

Your role is to analyze damage patterns and determine:
1. Whether detected patterns indicate fraud or are legitimate
2. How location/fleet context affects the assessment
3. Appropriate routing decision (auto-approve vs human review)
4. Risk level and mitigation recommendations

Consider both customer history and broader fleet trends. Be practical and business-focused."""

        human_prompt = """Analyze this damage claim for patterns and fraud risk:

CLAIM DETAILS:
- Vehicle ID: {vehicle_id}
- Customer ID: {customer_id}
- Damage Type: {damage_type}
- Location: {location}
- Return Location: {return_location}
- Estimated Cost: €{cost}

DETECTED PATTERNS:
- Frequent Damage: {frequent_damage}
- Same Damage Type: {same_damage_type}
- Location Correlation: {location_correlation}
- Timing Pattern: {timing_pattern}
- Fraud Risk Score: {fraud_risk}

FLEET CONTEXT:
- Location Damage Rate: {location_rate}
- Average Damage Cost: {avg_cost}
- Customer History: {customer_history}

AUTO-APPROVE THRESHOLD: €500

QUESTIONS:
1. Are these patterns indicative of fraud or legitimate circumstances?
2. How does the fleet/location context affect your assessment?
3. Should this be auto-approved or sent for human review?
4. What specific concerns or red flags should be noted?

Provide your analysis and recommendation in 3-4 sentences."""

        variables = {
            "vehicle_id": claim.vehicle_id,
            "customer_id": claim.customer_id,
            "damage_type": claim.damage_assessment.damage_type.value,
            "location": claim.damage_assessment.location.value,
            "return_location": claim.return_location,
            "cost": f"{cost_estimate_eur:.2f}",
            "frequent_damage": "Yes" if patterns.get("frequent_damage") else "No",
            "same_damage_type": "Yes" if patterns.get("same_damage_type") else "No",
            "location_correlation": "Yes" if patterns.get("location_correlation") else "No",
            "timing_pattern": patterns.get("timing_pattern", "None"),
            "fraud_risk": f"{patterns.get('fraud_risk_score', 0.0):.2f}",
            "location_rate": fleet_context.get("location_damage_rate", "Unknown") if fleet_context else "Unknown",
            "avg_cost": f"€{fleet_context.get('avg_damage_cost', 0):.0f}" if fleet_context else "Unknown",
            "customer_history": fleet_context.get("customer_history", "No prior data") if fleet_context else "No prior data",
        }

        prompt = self._create_prompt(system_prompt, human_prompt)
        return self._invoke_llm(prompt, variables)

    def _apply_llm_reasoning(
        self,
        base_result: ValidationResult,
        reasoning: Optional[str],
        patterns: Dict[str, Any]
    ) -> tuple[ValidationResult, Optional[str]]:
        """
        Apply LLM reasoning to potentially adjust validation decision.

        The LLM can upgrade or downgrade the routing decision based on context.
        """
        if not reasoning:
            return base_result, None

        # Parse reasoning for decision keywords
        reasoning_lower = reasoning.lower()

        # Check for override signals
        if "auto-approve" in reasoning_lower and "recommend" in reasoning_lower:
            # LLM recommends auto-approve despite flags
            if base_result.routing_decision == RoutingDecision.HUMAN_REVIEW_REQUIRED:
                logger.info("LLM recommends auto-approve, overriding base decision")
                # Create new ValidationResult with updated fields
                base_result = ValidationResult(
                    claim_id=base_result.claim_id,
                    is_valid=base_result.is_valid,
                    can_auto_approve=True,
                    routing_decision=RoutingDecision.AUTO_APPROVE,
                    routing_reason=f"{base_result.routing_reason} | LLM override: recommends auto-approval",
                    fraud_risk_score=base_result.fraud_risk_score,
                    overall_risk_score=base_result.overall_risk_score,
                    flags=base_result.flags
                )

        elif "human review" in reasoning_lower and "recommend" in reasoning_lower:
            # LLM recommends human review
            if base_result.routing_decision == RoutingDecision.AUTO_APPROVE:
                logger.info("LLM recommends human review, overriding base decision")
                # Create new ValidationResult with updated fields
                base_result = ValidationResult(
                    claim_id=base_result.claim_id,
                    is_valid=base_result.is_valid,
                    can_auto_approve=False,
                    routing_decision=RoutingDecision.HUMAN_REVIEW_REQUIRED,
                    routing_reason=f"{base_result.routing_reason} | LLM override: recommends human review",
                    fraud_risk_score=base_result.fraud_risk_score,
                    overall_risk_score=base_result.overall_risk_score,
                    flags=base_result.flags
                )

        explanation = f"AI Validation Analysis: {reasoning}"

        logger.info(f"LLM validation reasoning: {reasoning[:100]}...")

        return base_result, explanation
