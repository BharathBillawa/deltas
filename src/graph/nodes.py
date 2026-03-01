"""
Workflow nodes for damage claim processing.

Each node handles a specific stage of the claim workflow:
- Intake: Validate and enrich claim with context
- Cost Estimation: Calculate repair costs with depreciation
- Validation: Pattern recognition and business rules
- Routing: Decision logic for auto-approve vs human review
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from src.models.state import DamageClaimState, WorkflowError
from src.models.damage import DamageClaim, VehicleInfo, VehicleCategory
from src.models.financial import CostEstimate
from src.models.routing import (
    ValidationResult,
    ValidationFlag,
    RoutingDecision,
    EscalationReason,
    FlagSeverity,
)
from src.services.pricing_service import PricingService
from src.services.depreciation_service import DepreciationService
from src.services.pattern_recognition_service import PatternRecognitionService
from src.services.event_logger import EventLogger
from src.services.tensorlake_service import TensorlakeService
from src.persistence.database import VehicleDB, CustomerDB
from src.agents.cost_estimator_agent import CostEstimatorAgent
from src.agents.validator_agent import ValidatorAgent

logger = logging.getLogger(__name__)

# Configuration thresholds
AUTO_APPROVE_THRESHOLD_EUR = 500.0
FRAUD_RISK_THRESHOLD = 7.0
PATTERN_REVIEW_THRESHOLD = 2  # Number of patterns that trigger review


def intake_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Intake node: Validate claim and enrich with vehicle/customer context.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields
    """
    logger.info(f"Intake node: Processing claim {state.claim.claim_id}")

    claim = state.claim
    updates: Dict[str, Any] = {
        "workflow_started_at": datetime.now().isoformat(),
    }

    try:
        # Load vehicle context from database
        vehicle = db.query(VehicleDB).filter(
            VehicleDB.vehicle_id == claim.vehicle_id
        ).first()

        if vehicle:
            # Build VehicleInfo from database record
            vehicle_info = VehicleInfo(
                vehicle_id=vehicle.vehicle_id,
                category=VehicleCategory(vehicle.category),
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                color=vehicle.color or "",
                vin=vehicle.vin,
                license_plate=vehicle.license_plate,
                purchase_date=vehicle.purchase_date,
                purchase_price_eur=vehicle.purchase_price_eur,
                current_mileage_km=vehicle.current_mileage_km,
                last_service_date=vehicle.last_service_date,
                health_score=vehicle.health_score or 5.0,
                cumulative_damage_ytd_eur=vehicle.cumulative_damage_ytd_eur or 0.0,
                depreciation_percent=vehicle.depreciation_percent,
            )

            # Update claim with vehicle context
            updated_claim = claim.model_copy(update={"vehicle_context": vehicle_info})
            updates["claim"] = updated_claim

            logger.info(f"Loaded vehicle context: {vehicle.make} {vehicle.model} ({vehicle.year})")
        else:
            logger.warning(f"Vehicle {claim.vehicle_id} not found in database")
            updates["errors"] = state.errors + [
                WorkflowError(
                    timestamp=datetime.now().isoformat(),
                    stage="intake",
                    error_type="vehicle_not_found",
                    message=f"Vehicle {claim.vehicle_id} not found",
                    recoverable=True
                )
            ]

        # Load customer risk profile
        customer = db.query(CustomerDB).filter(
            CustomerDB.customer_id == claim.customer_id
        ).first()

        if customer:
            logger.info(f"Loaded customer: {customer.customer_id} (risk score: {customer.risk_score})")
        else:
            logger.debug(f"Customer {claim.customer_id} not in database (new customer)")

        # Use Tensorlake to extract/validate damage assessment from photos
        current_claim = updates.get("claim", claim)
        if current_claim.damage_assessment and current_claim.damage_assessment.photos:
            try:
                tensorlake = TensorlakeService()
                logger.info(
                    f"Using Tensorlake to validate damage assessment for claim {claim.claim_id} "
                    f"({len(current_claim.damage_assessment.photos)} photos)"
                )
                # Extract assessment from photos for validation/enrichment
                extracted_assessment = tensorlake.extract_from_images(
                    image_paths=current_claim.damage_assessment.photos,
                    vehicle_id=claim.vehicle_id,
                    metadata={
                        "claim_id": claim.claim_id,
                        "return_location": claim.return_location
                    }
                )
                logger.info(
                    f"Tensorlake extraction: {extracted_assessment.damage_type.value} "
                    f"({extracted_assessment.severity.value}) at {extracted_assessment.location.value}"
                )
                # In production, you might merge/validate extracted vs submitted assessment
                # For now, we log the extraction to show Tensorlake integration
            except Exception as e:
                logger.warning(f"Tensorlake extraction failed: {e}")
                # Continue workflow - claim already has assessment

        # Emit ClaimReceived event
        event_logger = EventLogger(db)
        event_logger.emit_claim_received(
            claim_id=claim.claim_id,
            vehicle_id=claim.vehicle_id,
            customer_id=claim.customer_id,
            damage_type=claim.damage_assessment.damage_type.value
        )

        updates["next_step"] = "cost_estimation"

    except Exception as e:
        logger.error(f"Intake error: {e}")
        updates["errors"] = state.errors + [
            WorkflowError(
                timestamp=datetime.now().isoformat(),
                stage="intake",
                error_type="processing_error",
                message=str(e),
                recoverable=False
            )
        ]
        updates["next_step"] = "error"

    return updates


def cost_estimation_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Cost estimation node: LLM-powered cost estimation with reasoning.

    Uses CostEstimatorAgent to wrap PricingService and DepreciationService
    with LLM reasoning for edge cases.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields with cost estimate and optional AI reasoning
    """
    logger.info(f"Cost estimation node (Agent): Processing claim {state.claim.claim_id}")

    claim = state.claim
    updates: Dict[str, Any] = {}

    try:
        # Build vehicle context for agent
        vehicle_context = None
        if claim.vehicle_context:
            vehicle_context = {
                "age_years": datetime.now().year - claim.vehicle_context.year,
                "mileage_km": claim.vehicle_context.current_mileage_km,
                "cumulative_damage_ytd": claim.vehicle_context.cumulative_damage_ytd_eur,
                "recent_damage_count": len(claim.vehicle_context.damage_history),
            }

        # Use agent for cost estimation
        agent = CostEstimatorAgent(db, temperature=0.3)
        cost_estimate, ai_reasoning = agent.estimate_cost(claim, vehicle_context)

        updates["cost_estimate"] = cost_estimate

        # Store AI reasoning if available
        if ai_reasoning:
            updates["ai_cost_reasoning"] = ai_reasoning
            logger.info(f"AI reasoning available for cost decision")

        # Emit CostEstimated event
        event_logger = EventLogger(db)
        event_logger.emit_cost_estimated(
            claim_id=claim.claim_id,
            estimated_cost_eur=cost_estimate.total_eur,
            labor_cost_eur=cost_estimate.labor_cost_eur,
            parts_cost_eur=cost_estimate.parts_cost_eur
        )

        logger.info(f"Cost estimate (Agent): €{cost_estimate.total_eur:.2f}")
        updates["next_step"] = "validation"

    except Exception as e:
        logger.error(f"Cost estimation error: {e}")
        updates["errors"] = state.errors + [
            WorkflowError(
                timestamp=datetime.now().isoformat(),
                stage="cost_estimation",
                error_type="estimation_error",
                message=str(e),
                recoverable=True
            )
        ]
        updates["next_step"] = "error"

    return updates


def validation_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Validation node: LLM-powered validation with pattern reasoning.

    Uses ValidatorAgent to wrap PatternRecognitionService with LLM reasoning
    for ambiguous patterns and fraud detection.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields with validation result and optional AI reasoning
    """
    logger.info(f"Validation node (Agent): Processing claim {state.claim.claim_id}")

    claim = state.claim
    cost_estimate = state.cost_estimate
    updates: Dict[str, Any] = {}

    try:
        # Build fleet context for agent (optional, enhances reasoning)
        fleet_context = {
            "location_damage_rate": "Medium",  # Would fetch from analytics in production
            "avg_damage_cost": 450.0,
            "customer_history": "No prior data"
        }

        # Use agent for validation
        agent = ValidatorAgent(db, temperature=0.3)
        validation_result, ai_reasoning = agent.validate_claim(
            claim,
            cost_estimate.total_eur if cost_estimate else 0.0,
            fleet_context
        )

        updates["validation_result"] = validation_result

        # Store AI reasoning if available
        if ai_reasoning:
            updates["ai_validation_reasoning"] = ai_reasoning
            logger.info(f"AI reasoning available for validation decision")

        # Emit events for patterns if detected
        if validation_result.flags:
            event_logger = EventLogger(db)
            for flag in validation_result.flags:
                if "pattern" in flag.flag_type.lower():
                    event_logger.emit_pattern_detected(
                        claim_id=claim.claim_id,
                        pattern_type=flag.flag_type,
                        severity=flag.severity,
                        description=flag.description
                    )

        updates["next_step"] = "routing"

        logger.info(
            f"Validation (Agent): {validation_result.routing_decision.value}, "
            f"flags={len(validation_result.flags)}"
        )

    except Exception as e:
        logger.error(f"Validation error: {e}")
        updates["errors"] = state.errors + [
            WorkflowError(
                timestamp=datetime.now().isoformat(),
                stage="validation",
                error_type="validation_error",
                message=str(e),
                recoverable=True
            )
        ]
        updates["next_step"] = "error"

    return updates


def routing_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Routing node: Final decision for auto-approve vs human review.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields with final routing decision
    """
    logger.info(f"Routing node: Processing claim {state.claim.claim_id}")

    validation_result = state.validation_result
    cost_estimate = state.cost_estimate
    claim = state.claim
    updates: Dict[str, Any] = {}

    try:
        event_logger = EventLogger(db)

        if validation_result and validation_result.can_auto_approve:
            # Auto-approve the claim
            updates["workflow_complete"] = True
            updates["requires_human_approval"] = False
            updates["approval_granted"] = True
            updates["workflow_completed_at"] = datetime.now().isoformat()
            updates["next_step"] = "complete"

            # Emit ClaimApproved event
            event_logger.emit_claim_approved(
                claim_id=state.claim.claim_id,
                reviewer_id="AUTO_SYSTEM",
                notes="Auto-approved: All checks passed"
            )

            logger.info(f"Claim {state.claim.claim_id} auto-approved")

        else:
            # Requires human review - add to approval queue BEFORE pausing
            updates["requires_human_approval"] = True
            updates["workflow_complete"] = False
            updates["next_step"] = "human_review"

            # Add to approval queue
            queue_id = _add_to_approval_queue(
                db, claim, validation_result, cost_estimate,
                state.ai_cost_reasoning, state.ai_validation_reasoning
            )
            if queue_id:
                updates["queue_id"] = queue_id

            # Emit ApprovalRequired event
            flags_summary = [f.flag_type for f in validation_result.flags] if validation_result else []
            event_logger.emit_approval_required(
                claim_id=state.claim.claim_id,
                reason=validation_result.routing_reason if validation_result else "Manual review required",
                flags=flags_summary
            )

            logger.info(
                f"Claim {state.claim.claim_id} requires human review: "
                f"{validation_result.routing_reason if validation_result else 'Unknown'}"
            )

    except Exception as e:
        logger.error(f"Routing error: {e}")
        updates["errors"] = state.errors + [
            WorkflowError(
                timestamp=datetime.now().isoformat(),
                stage="routing",
                error_type="routing_error",
                message=str(e),
                recoverable=True
            )
        ]
        updates["next_step"] = "error"

    return updates


def _add_to_approval_queue(
    db: Session,
    claim: DamageClaim,
    validation_result,
    cost_estimate,
    ai_cost_reasoning: Optional[str] = None,
    ai_validation_reasoning: Optional[str] = None
) -> Optional[str]:
    """
    Add claim to approval queue.

    Args:
        db: Database session
        claim: The damage claim
        validation_result: Validation result with flags
        cost_estimate: Cost estimate
        ai_cost_reasoning: Optional LLM reasoning for cost
        ai_validation_reasoning: Optional LLM reasoning for validation

    Returns:
        Queue ID if added, None if already exists or error
    """
    from src.persistence.database import ApprovalQueueDB
    from uuid import uuid4

    try:
        # Check if already in queue
        existing = db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.claim_id == claim.claim_id,
            ApprovalQueueDB.status == "pending_review"
        ).first()

        if existing:
            logger.info(f"Claim {claim.claim_id} already in queue: {existing.queue_id}")
            return existing.queue_id

        # Create queue entry
        queue_id = str(uuid4())

        # Build damage description
        damage_desc = (
            f"{claim.damage_assessment.severity.value} "
            f"{claim.damage_assessment.damage_type.value} at "
            f"{claim.damage_assessment.location.value}"
        )

        # Get estimated cost
        estimated_cost = cost_estimate.total_eur if cost_estimate else 0.0

        # Get escalation reason
        escalation_reason = "Manual review required"
        if validation_result and validation_result.escalation_reason:
            escalation_reason = validation_result.escalation_reason.value
        elif validation_result:
            escalation_reason = validation_result.routing_reason

        # Get flags as strings
        flags_list = []
        if validation_result and validation_result.flags:
            flags_list = [f.flag_type for f in validation_result.flags]

        # Get vehicle context
        vehicle_id = claim.vehicle_id
        vehicle_health = None
        cumulative_damage = None
        if claim.vehicle_context:
            vehicle_health = claim.vehicle_context.health_score
            cumulative_damage = claim.vehicle_context.cumulative_damage_ytd_eur

        # Calculate priority based on cost and flags
        priority = 3  # Default
        if estimated_cost > 1000:
            priority = 2
        if estimated_cost > 2000 or "fraud_risk" in flags_list:
            priority = 1

        # Pattern summary
        pattern_summary = None
        if validation_result and validation_result.patterns_detected:
            patterns = [p.pattern_type.value for p in validation_result.patterns_detected]
            pattern_summary = f"Patterns: {', '.join(patterns)}"

        queue_entry = ApprovalQueueDB(
            queue_id=queue_id,
            claim_id=claim.claim_id,
            vehicle_id=vehicle_id,
            customer_id=claim.customer_id,
            damage_description=damage_desc,
            estimated_cost_eur=estimated_cost,
            flags=flags_list,
            routing_decision=validation_result.routing_decision.value if validation_result else "human_review_required",
            escalation_reason=escalation_reason,
            priority=priority,
            status="pending_review",
            vehicle_health_score=vehicle_health,
            cumulative_damage_ytd_eur=cumulative_damage,
            pattern_summary=pattern_summary,
            ai_cost_reasoning=ai_cost_reasoning,
            ai_validation_reasoning=ai_validation_reasoning
        )

        db.add(queue_entry)
        db.commit()

        logger.info(f"Added claim {claim.claim_id} to approval queue: {queue_id}")
        return queue_id

    except Exception as e:
        logger.error(f"Error adding to approval queue: {e}")
        db.rollback()
        return None


def human_review_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Human review node: Workflow pauses here for human approval.

    The claim has already been added to the approval queue in routing_node.
    This node marks the pause point for the workflow interrupt.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields
    """
    logger.info(f"Human review node: Claim {state.claim.claim_id} awaiting approval")

    # Workflow pauses here - claim already in approval queue
    return {
        "next_step": "awaiting_approval"
    }


def complete_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Complete node: Finalize the workflow.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields marking completion
    """
    logger.info(f"Complete node: Finalizing claim {state.claim.claim_id}")

    # Calculate processing time
    processing_time = None
    if state.workflow_started_at:
        start_time = datetime.fromisoformat(state.workflow_started_at)
        processing_time = (datetime.now() - start_time).total_seconds()

    return {
        "workflow_complete": True,
        "workflow_completed_at": datetime.now().isoformat(),
        "processing_time_seconds": processing_time,
        "next_step": None
    }


def error_node(state: DamageClaimState, db: Session) -> Dict[str, Any]:
    """
    Error node: Handle workflow errors.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields for error handling
    """
    logger.error(f"Error node: Claim {state.claim.claim_id} encountered errors")

    # Log errors
    for error in state.errors:
        logger.error(f"  - {error.stage}: {error.error_type} - {error.message}")

    # Check if retry is possible
    recoverable_errors = [e for e in state.errors if e.recoverable]

    if recoverable_errors and state.retry_count < 3:
        return {
            "requires_retry": True,
            "retry_count": state.retry_count + 1,
            "next_step": "intake"  # Restart from intake
        }

    return {
        "workflow_complete": True,
        "requires_human_approval": True,  # Escalate to human
        "next_step": "human_review"
    }
