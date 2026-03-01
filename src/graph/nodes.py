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
from src.models.financial import CostEstimate, DepreciationComponent
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
from src.persistence.database import VehicleDB, CustomerDB

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
    Cost estimation node: Calculate repair costs with depreciation.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields with cost estimate
    """
    logger.info(f"Cost estimation node: Processing claim {state.claim.claim_id}")

    claim = state.claim
    updates: Dict[str, Any] = {}

    try:
        # Initialize pricing service
        pricing_service = PricingService()

        # Get vehicle category
        vehicle_category = "Standard"
        if claim.vehicle_context:
            vehicle_category = claim.vehicle_context.category.value

        # Calculate base cost
        cost_estimate = pricing_service.calculate_cost(
            claim_id=claim.claim_id,
            damage_type=claim.damage_assessment.damage_type,
            severity=claim.damage_assessment.severity,
            vehicle_category=vehicle_category,
            location=claim.return_location,
            damage_location=claim.damage_assessment.location.value
        )

        # Apply depreciation for older vehicles
        if claim.vehicle_context and claim.vehicle_context.year:
            depreciation_service = DepreciationService()

            # Check if depreciation should apply
            if depreciation_service.should_apply_depreciation(
                vehicle_year=claim.vehicle_context.year,
                component=depreciation_service.infer_component_from_location(
                    claim.damage_assessment.location.value
                ),
                min_age_years=2
            ):
                # Calculate depreciation
                component = depreciation_service.infer_component_from_location(
                    claim.damage_assessment.location.value
                )
                depreciation = depreciation_service.calculate(
                    vehicle_id=claim.vehicle_id,
                    vehicle_year=claim.vehicle_context.year,
                    original_cost_eur=cost_estimate.subtotal_eur,
                    component=component
                )

                # Update cost estimate with depreciation
                cost_estimate = CostEstimate(
                    claim_id=cost_estimate.claim_id,
                    labor_hours=cost_estimate.labor_hours,
                    labor_type=cost_estimate.labor_type,
                    labor_rate_eur=cost_estimate.labor_rate_eur,
                    labor_cost_eur=cost_estimate.labor_cost_eur,
                    parts_cost_eur=cost_estimate.parts_cost_eur,
                    category_multiplier=cost_estimate.category_multiplier,
                    location_multiplier=cost_estimate.location_multiplier,
                    subtotal_eur=cost_estimate.subtotal_eur,
                    depreciation_applicable=True,
                    depreciation_component=component,
                    depreciation_factor=depreciation.depreciation_factor,
                    depreciated_value_eur=depreciation.depreciated_value_eur,
                    total_eur=depreciation.depreciated_value_eur,
                    confidence_score=cost_estimate.confidence_score,
                    notes=f"{cost_estimate.notes}; Depreciation applied ({depreciation.depreciation_factor:.0%})"
                )

                logger.info(
                    f"Depreciation applied: €{cost_estimate.subtotal_eur:.2f} → "
                    f"€{cost_estimate.total_eur:.2f}"
                )

        updates["cost_estimate"] = cost_estimate

        # Emit CostEstimated event
        event_logger = EventLogger(db)
        event_logger.emit_cost_estimated(
            claim_id=claim.claim_id,
            estimated_cost_eur=cost_estimate.total_eur,
            labor_cost_eur=cost_estimate.labor_cost_eur,
            parts_cost_eur=cost_estimate.parts_cost_eur
        )

        logger.info(f"Cost estimate: €{cost_estimate.total_eur:.2f}")
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
    Validation node: Pattern recognition and business rules.

    Args:
        state: Current workflow state
        db: Database session

    Returns:
        Updated state fields with validation result
    """
    logger.info(f"Validation node: Processing claim {state.claim.claim_id}")

    claim = state.claim
    cost_estimate = state.cost_estimate
    updates: Dict[str, Any] = {}
    flags: list[ValidationFlag] = []
    patterns = []

    try:
        # Initialize pattern recognition
        pattern_service = PatternRecognitionService(db)
        event_logger = EventLogger(db)

        # Analyze vehicle patterns
        vehicle_patterns = pattern_service.analyze_vehicle_patterns(claim.vehicle_id)
        patterns.extend(vehicle_patterns)

        # Emit PatternDetected events
        for pattern in vehicle_patterns:
            event_logger.emit_pattern_detected(
                claim_id=claim.claim_id,
                pattern_type=pattern.pattern_type.value,
                severity=pattern.severity.value,
                description=pattern.details
            )

            # Add flag for each pattern
            flags.append(ValidationFlag(
                flag_type=f"pattern_{pattern.pattern_type.value}",
                severity=pattern.severity,
                description=pattern.details,
                recommended_action="Review vehicle damage history"
            ))

        # Analyze customer risk
        customer_risk = pattern_service.analyze_customer_risk(claim.customer_id)
        updates["customer_risk_profile"] = customer_risk

        if customer_risk.is_high_risk:
            flags.append(ValidationFlag(
                flag_type="high_risk_customer",
                severity=FlagSeverity.HIGH,
                description=f"Customer risk score: {customer_risk.risk_score}/10",
                details={"risk_factors": customer_risk.risk_factors},
                recommended_action=customer_risk.recommendation
            ))

        # Business rule: Cost threshold
        if cost_estimate and cost_estimate.total_eur > AUTO_APPROVE_THRESHOLD_EUR:
            flags.append(ValidationFlag(
                flag_type="high_cost",
                severity=FlagSeverity.WARNING,
                description=f"Cost €{cost_estimate.total_eur:.2f} exceeds auto-approve threshold €{AUTO_APPROVE_THRESHOLD_EUR}",
                recommended_action="Manual cost review required"
            ))

        # Business rule: Luxury vehicle
        if claim.vehicle_context and claim.vehicle_context.category in [
            VehicleCategory.LUXURY, VehicleCategory.PREMIUM
        ]:
            flags.append(ValidationFlag(
                flag_type="luxury_vehicle",
                severity=FlagSeverity.INFO,
                description=f"{claim.vehicle_context.category.value} vehicle requires additional scrutiny",
                recommended_action="Verify damage assessment accuracy"
            ))

        # Business rule: Low vehicle health
        if claim.vehicle_context and claim.vehicle_context.health_score < 5.0:
            flags.append(ValidationFlag(
                flag_type="low_vehicle_health",
                severity=FlagSeverity.WARNING,
                description=f"Vehicle health score: {claim.vehicle_context.health_score}/10",
                recommended_action="Consider retirement analysis"
            ))

        # Business rule: Depreciation applied
        if cost_estimate and cost_estimate.depreciation_applicable:
            flags.append(ValidationFlag(
                flag_type="depreciation_applied",
                severity=FlagSeverity.INFO,
                description=f"Depreciation factor: {cost_estimate.depreciation_factor:.0%}",
                recommended_action="Verify depreciation calculation"
            ))

        # Calculate overall risk score
        fraud_risk_score = customer_risk.risk_score if customer_risk else 0.0

        # Patterns increase fraud risk
        if len([p for p in patterns if p.severity in [FlagSeverity.HIGH, FlagSeverity.CRITICAL]]) > 0:
            fraud_risk_score = min(10.0, fraud_risk_score + 2.0)

        overall_risk_score = fraud_risk_score
        if flags:
            # Add 0.5 for each warning/high flag
            high_flags = len([f for f in flags if f.severity in [FlagSeverity.WARNING, FlagSeverity.HIGH]])
            overall_risk_score = min(10.0, overall_risk_score + high_flags * 0.5)

        # Determine routing decision
        can_auto_approve = True
        routing_decision = RoutingDecision.AUTO_APPROVE
        routing_reason = "All checks passed, within thresholds"
        escalation_reason = None

        # Check cost threshold
        if cost_estimate and cost_estimate.total_eur > AUTO_APPROVE_THRESHOLD_EUR:
            can_auto_approve = False
            routing_decision = RoutingDecision.HUMAN_REVIEW_REQUIRED
            routing_reason = f"Cost €{cost_estimate.total_eur:.2f} exceeds threshold"
            escalation_reason = EscalationReason.HIGH_COST

        # Check pattern flags
        elif len([p for p in patterns if p.impact_on_routing]) >= PATTERN_REVIEW_THRESHOLD:
            can_auto_approve = False
            routing_decision = RoutingDecision.HUMAN_REVIEW_REQUIRED
            routing_reason = f"Multiple patterns detected ({len(patterns)})"
            escalation_reason = EscalationReason.PATTERN_DETECTED

        # Check fraud risk
        elif fraud_risk_score >= FRAUD_RISK_THRESHOLD:
            can_auto_approve = False
            routing_decision = RoutingDecision.INVESTIGATION_REQUIRED
            routing_reason = f"High fraud risk score: {fraud_risk_score}/10"
            escalation_reason = EscalationReason.FRAUD_RISK

        # Check customer risk
        elif customer_risk and customer_risk.is_high_risk:
            can_auto_approve = False
            routing_decision = RoutingDecision.HUMAN_REVIEW_REQUIRED
            routing_reason = f"High-risk customer (score: {customer_risk.risk_score}/10)"
            escalation_reason = EscalationReason.FRAUD_RISK

        # Build validation result
        validation_result = ValidationResult(
            claim_id=claim.claim_id,
            is_valid=True,
            can_auto_approve=can_auto_approve,
            routing_decision=routing_decision,
            routing_reason=routing_reason,
            escalation_reason=escalation_reason,
            flags=flags,
            patterns_detected=[p for p in patterns],
            fraud_risk_score=fraud_risk_score,
            overall_risk_score=overall_risk_score,
            recommendations=[f.recommended_action for f in flags if f.recommended_action]
        )

        updates["validation_result"] = validation_result
        updates["next_step"] = "routing"

        logger.info(
            f"Validation complete: can_auto_approve={can_auto_approve}, "
            f"flags={len(flags)}, patterns={len(patterns)}"
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
            queue_id = _add_to_approval_queue(db, claim, validation_result, cost_estimate)
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
    cost_estimate
) -> Optional[str]:
    """
    Add claim to approval queue.

    Args:
        db: Database session
        claim: The damage claim
        validation_result: Validation result with flags
        cost_estimate: Cost estimate

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
            pattern_summary=pattern_summary
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
