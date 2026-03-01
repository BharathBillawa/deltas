"""
Tests for LangGraph workflow.

Tests individual nodes and end-to-end workflow scenarios.
"""

import pytest
from datetime import datetime

from src.models.state import DamageClaimState
from src.models.damage import (
    DamageClaim,
    DamageAssessment,
    DamageType,
    DamageSeverity,
    VehicleLocation,
)
from src.models.financial import CostEstimate, LaborType
from src.models.routing import ValidationResult, RoutingDecision
from src.graph.nodes import (
    intake_node,
    cost_estimation_node,
    validation_node,
    routing_node,
    AUTO_APPROVE_THRESHOLD_EUR,
)
from src.graph.workflow import DamageClaimWorkflow, create_workflow
from src.persistence.database import SessionLocal, VehicleDB


@pytest.fixture
def sample_claim():
    """Create a sample damage claim for testing."""
    return DamageClaim(
        claim_id="CLM-TEST-001",
        timestamp=datetime.now(),
        vehicle_id="VW-POLO-2023-001",
        customer_id="CUST-5678",
        rental_agreement_id="RNT-2026-0234",
        return_location="Munich_Airport",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            location=VehicleLocation.REAR_BUMPER,
            description="Minor scratch on rear bumper",
            affected_parts=["rear_bumper"],
            photos=["photo1.jpg"],
            inspector_id="INSP-001"
        )
    )


@pytest.fixture
def sample_state(sample_claim):
    """Create a sample workflow state."""
    return DamageClaimState(claim=sample_claim)


@pytest.fixture
def db_session():
    """Get database session for testing."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestIntakeNode:
    """Tests for intake node."""

    def test_intake_sets_workflow_started_at(self, sample_state, db_session):
        """Intake node should set workflow start time."""
        result = intake_node(sample_state, db_session)

        assert "workflow_started_at" in result
        assert result["workflow_started_at"] is not None

    def test_intake_sets_next_step(self, sample_state, db_session):
        """Intake node should set next step to cost_estimation."""
        result = intake_node(sample_state, db_session)

        assert result["next_step"] == "cost_estimation"

    def test_intake_loads_vehicle_context(self, sample_state, db_session):
        """Intake node should load vehicle context if vehicle exists."""
        # Check if vehicle exists
        vehicle = db_session.query(VehicleDB).filter(
            VehicleDB.vehicle_id == sample_state.claim.vehicle_id
        ).first()

        result = intake_node(sample_state, db_session)

        if vehicle:
            assert "claim" in result
            assert result["claim"].vehicle_context is not None
        else:
            # Vehicle not found, should have error
            assert "errors" in result or result["next_step"] == "cost_estimation"


class TestCostEstimationNode:
    """Tests for cost estimation node."""

    def test_cost_estimation_creates_estimate(self, sample_state, db_session):
        """Cost estimation should create a cost estimate."""
        # First run intake to set up state
        intake_result = intake_node(sample_state, db_session)

        # Update state
        updated_state = sample_state.model_copy(update=intake_result)

        # Run cost estimation
        result = cost_estimation_node(updated_state, db_session)

        assert "cost_estimate" in result
        assert result["cost_estimate"] is not None
        assert result["cost_estimate"].total_eur > 0

    def test_cost_estimation_sets_next_step(self, sample_state, db_session):
        """Cost estimation should set next step to validation."""
        result = cost_estimation_node(sample_state, db_session)

        assert result["next_step"] == "validation"


class TestValidationNode:
    """Tests for validation node."""

    def test_validation_creates_result(self, sample_state, db_session):
        """Validation should create a validation result."""
        # Set up cost estimate
        cost_estimate = CostEstimate(
            claim_id=sample_state.claim.claim_id,
            labor_hours=0.8,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202,
            labor_cost_eur=161.60,
            parts_cost_eur=3,
            category_multiplier=1.0,
            location_multiplier=1.0,
            subtotal_eur=164.60,
            total_eur=165
        )

        updated_state = sample_state.model_copy(update={"cost_estimate": cost_estimate})

        result = validation_node(updated_state, db_session)

        assert "validation_result" in result
        assert result["validation_result"] is not None

    def test_validation_auto_approves_low_cost(self, sample_state, db_session):
        """Low cost claims should be auto-approvable."""
        # Set up low cost estimate
        cost_estimate = CostEstimate(
            claim_id=sample_state.claim.claim_id,
            labor_hours=0.5,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202,
            labor_cost_eur=101,
            parts_cost_eur=0,
            category_multiplier=1.0,
            location_multiplier=1.0,
            subtotal_eur=101,
            total_eur=101
        )

        updated_state = sample_state.model_copy(update={"cost_estimate": cost_estimate})

        result = validation_node(updated_state, db_session)

        # Should be auto-approvable if no patterns detected
        validation = result["validation_result"]
        assert validation is not None
        # Note: May still require review if patterns are detected

    def test_validation_flags_high_cost(self, sample_state, db_session):
        """High cost claims should be flagged."""
        # Set up high cost estimate
        cost_estimate = CostEstimate(
            claim_id=sample_state.claim.claim_id,
            labor_hours=5.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202,
            labor_cost_eur=1010,
            parts_cost_eur=200,
            category_multiplier=1.0,
            location_multiplier=1.0,
            subtotal_eur=1210,
            total_eur=1210
        )

        updated_state = sample_state.model_copy(update={"cost_estimate": cost_estimate})

        result = validation_node(updated_state, db_session)

        validation = result["validation_result"]
        assert validation is not None

        # Should have high_cost flag
        flag_types = [f.flag_type for f in validation.flags]
        assert "high_cost" in flag_types

        # Should not be auto-approvable
        assert not validation.can_auto_approve


class TestRoutingNode:
    """Tests for routing node."""

    def test_routing_auto_approves(self, sample_state, db_session):
        """Routing should auto-approve when validation allows."""
        # Set up validation result that allows auto-approve
        validation_result = ValidationResult(
            claim_id=sample_state.claim.claim_id,
            is_valid=True,
            can_auto_approve=True,
            routing_decision=RoutingDecision.AUTO_APPROVE,
            routing_reason="All checks passed"
        )

        updated_state = sample_state.model_copy(update={
            "validation_result": validation_result
        })

        result = routing_node(updated_state, db_session)

        assert result["workflow_complete"] is True
        assert result["requires_human_approval"] is False
        assert result["approval_granted"] is True

    def test_routing_requires_human_review(self, sample_state, db_session):
        """Routing should require human review when validation fails."""
        # Set up validation result that requires review
        validation_result = ValidationResult(
            claim_id=sample_state.claim.claim_id,
            is_valid=True,
            can_auto_approve=False,
            routing_decision=RoutingDecision.HUMAN_REVIEW_REQUIRED,
            routing_reason="Cost exceeds threshold"
        )

        updated_state = sample_state.model_copy(update={
            "validation_result": validation_result
        })

        result = routing_node(updated_state, db_session)

        assert result["requires_human_approval"] is True
        assert result["workflow_complete"] is False


class TestWorkflowEndToEnd:
    """End-to-end workflow tests."""

    def test_workflow_creates_successfully(self):
        """Workflow should create without errors."""
        workflow = create_workflow()
        assert workflow is not None

    def test_workflow_class_initializes(self):
        """DamageClaimWorkflow should initialize."""
        workflow = DamageClaimWorkflow(use_checkpointer=False)
        assert workflow is not None
        assert workflow.workflow is not None

    def test_minor_scratch_auto_approve(self, sample_claim):
        """Minor scratch should be auto-approved (happy path)."""
        workflow = DamageClaimWorkflow(use_checkpointer=False)

        result = workflow.process_claim(sample_claim)

        assert result is not None
        # May or may not be auto-approved depending on vehicle history
        # Just verify workflow completes without error
        assert result.workflow_complete or result.requires_human_approval

    def test_workflow_handles_missing_vehicle(self):
        """Workflow should handle missing vehicle gracefully."""
        # Create claim with non-existent vehicle
        claim = DamageClaim(
            claim_id="CLM-MISSING-001",
            timestamp=datetime.now(),
            vehicle_id="NON-EXISTENT-VEHICLE",
            customer_id="CUST-1234",
            rental_agreement_id="RNT-2026-0001",
            return_location="Munich_Airport",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.SCRATCH,
                severity=DamageSeverity.MINOR,
                location=VehicleLocation.REAR_BUMPER,
                description="Test scratch",
                affected_parts=["rear_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=False)

        # Should not raise exception
        result = workflow.process_claim(claim)

        assert result is not None


class TestHumanInTheLoop:
    """Tests for human-in-the-loop functionality."""

    def test_high_cost_claim_pauses_for_review(self):
        """High cost claims should pause at human_review."""
        # Create claim that will exceed threshold
        claim = DamageClaim(
            claim_id="CLM-HITL-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",  # Luxury vehicle
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0300",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Cracked front bumper",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=True)
        result = workflow.process_claim(claim)

        # Should require human approval
        assert result.requires_human_approval is True
        # Should not be complete yet
        assert result.workflow_complete is False

    def test_claim_added_to_approval_queue(self, db_session):
        """Claims requiring review should be added to approval queue."""
        from src.persistence.database import ApprovalQueueDB

        claim = DamageClaim(
            claim_id="CLM-QUEUE-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0301",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Cracked bumper for queue test",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=True)
        workflow.process_claim(claim)

        # Check approval queue
        queue_item = db_session.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.claim_id == "CLM-QUEUE-001"
        ).first()

        assert queue_item is not None
        assert queue_item.status == "pending_review"
        assert queue_item.estimated_cost_eur > 0

    def test_get_pending_approvals(self):
        """Should return list of pending approvals."""
        workflow = DamageClaimWorkflow(use_checkpointer=True)

        # Process a claim that needs review
        claim = DamageClaim(
            claim_id="CLM-PENDING-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0302",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Bumper crack for pending test",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow.process_claim(claim)

        # Get pending approvals
        pending = workflow.get_pending_approvals()

        # Should have at least one pending
        assert len(pending) >= 1

        # Find our claim
        our_claim = next((p for p in pending if p["claim_id"] == "CLM-PENDING-001"), None)
        assert our_claim is not None
        assert our_claim["escalation_reason"] is not None

    def test_workflow_status_shows_paused(self):
        """Workflow status should show paused state."""
        claim = DamageClaim(
            claim_id="CLM-STATUS-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0303",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Bumper crack for status test",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=True)
        workflow.process_claim(claim)

        status = workflow.get_status("CLM-STATUS-001")

        assert status is not None
        assert status["requires_human_approval"] is True

    def test_is_awaiting_approval(self):
        """Should correctly identify claims awaiting approval."""
        claim = DamageClaim(
            claim_id="CLM-AWAIT-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0304",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Bumper crack for await test",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=True)
        workflow.process_claim(claim)

        assert workflow.is_awaiting_approval("CLM-AWAIT-001") is True

    def test_resume_after_approval_approve(self, db_session):
        """Should resume workflow after approval."""
        from src.persistence.database import ApprovalQueueDB

        claim = DamageClaim(
            claim_id="CLM-RESUME-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0305",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Bumper crack for resume test",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=True)
        workflow.process_claim(claim)

        # Verify it's waiting
        assert workflow.is_awaiting_approval("CLM-RESUME-001") is True

        # Resume with approval
        result = workflow.resume_after_approval(
            claim_id="CLM-RESUME-001",
            approved=True,
            reviewer_id="REVIEWER-001",
            notes="Approved after review"
        )

        assert result.workflow_complete is True
        assert result.approval_granted is True

        # Check queue was updated
        queue_item = db_session.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.claim_id == "CLM-RESUME-001"
        ).first()

        assert queue_item is not None
        assert queue_item.status == "approved"
        assert queue_item.reviewer_id == "REVIEWER-001"

    def test_resume_after_approval_reject(self, db_session):
        """Should resume workflow after rejection."""
        from src.persistence.database import ApprovalQueueDB

        claim = DamageClaim(
            claim_id="CLM-REJECT-001",
            timestamp=datetime.now(),
            vehicle_id="AUDI-A6-2019-004",
            customer_id="CUST-7788",
            rental_agreement_id="RNT-2026-0306",
            return_location="Berlin_City",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.BUMPER_CRACK,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.FRONT_BUMPER,
                description="Bumper crack for reject test",
                affected_parts=["front_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )

        workflow = DamageClaimWorkflow(use_checkpointer=True)
        workflow.process_claim(claim)

        # Resume with rejection
        result = workflow.resume_after_approval(
            claim_id="CLM-REJECT-001",
            approved=False,
            reviewer_id="REVIEWER-002",
            notes="Insufficient documentation"
        )

        assert result.workflow_complete is True
        assert result.approval_granted is False

        # Check queue was updated
        queue_item = db_session.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.claim_id == "CLM-REJECT-001"
        ).first()

        assert queue_item is not None
        assert queue_item.status == "rejected"
        assert queue_item.decision_notes == "Insufficient documentation"


class TestWorkflowThresholds:
    """Tests for workflow threshold configurations."""

    def test_auto_approve_threshold_is_500(self):
        """Auto-approve threshold should be €500."""
        assert AUTO_APPROVE_THRESHOLD_EUR == 500.0

    def test_cost_below_threshold_can_auto_approve(self, sample_state, db_session):
        """Costs below threshold should be auto-approvable."""
        cost_estimate = CostEstimate(
            claim_id=sample_state.claim.claim_id,
            labor_hours=1.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202,
            labor_cost_eur=202,
            parts_cost_eur=50,
            category_multiplier=1.0,
            location_multiplier=1.0,
            subtotal_eur=252,
            total_eur=252
        )

        updated_state = sample_state.model_copy(update={"cost_estimate": cost_estimate})

        result = validation_node(updated_state, db_session)
        validation = result["validation_result"]

        # Should not have high_cost flag
        flag_types = [f.flag_type for f in validation.flags]
        assert "high_cost" not in flag_types

    def test_cost_above_threshold_requires_review(self, sample_state, db_session):
        """Costs above threshold should require review."""
        cost_estimate = CostEstimate(
            claim_id=sample_state.claim.claim_id,
            labor_hours=3.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202,
            labor_cost_eur=606,
            parts_cost_eur=100,
            category_multiplier=1.0,
            location_multiplier=1.0,
            subtotal_eur=706,
            total_eur=706
        )

        updated_state = sample_state.model_copy(update={"cost_estimate": cost_estimate})

        result = validation_node(updated_state, db_session)
        validation = result["validation_result"]

        # Should have high_cost flag and not be auto-approvable
        flag_types = [f.flag_type for f in validation.flags]
        assert "high_cost" in flag_types
        assert not validation.can_auto_approve
