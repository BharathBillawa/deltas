"""
LangGraph workflow for damage claim processing.

Orchestrates the claim processing pipeline:
intake → cost_estimation → validation → routing → [human_review | complete]

Features:
- Type-safe state management with Pydantic
- Human-in-the-loop interrupt for claims requiring review
- Event emission at each stage
- Graceful error handling with retry logic
"""

import logging
from datetime import datetime
from functools import partial
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.models.state import DamageClaimState
from src.models.damage import DamageClaim
from src.persistence.database import SessionLocal, ApprovalQueueDB
from src.graph.nodes import (
    intake_node,
    cost_estimation_node,
    validation_node,
    routing_node,
    human_review_node,
    complete_node,
    error_node,
)

logger = logging.getLogger(__name__)


def create_workflow(checkpointer: Optional[MemorySaver] = None) -> StateGraph:
    """
    Create the damage claim processing workflow.

    Args:
        checkpointer: Optional memory saver for state persistence

    Returns:
        Compiled LangGraph workflow
    """
    # Create graph with state type
    workflow = StateGraph(DamageClaimState)

    # Add nodes - wrap with database session
    def with_db_session(node_func, state: DamageClaimState) -> Dict[str, Any]:
        """Wrapper to provide database session to node functions."""
        db = SessionLocal()
        try:
            return node_func(state, db)
        finally:
            db.close()

    workflow.add_node("intake", partial(with_db_session, intake_node))
    workflow.add_node("cost_estimation", partial(with_db_session, cost_estimation_node))
    workflow.add_node("validation", partial(with_db_session, validation_node))
    workflow.add_node("routing", partial(with_db_session, routing_node))
    workflow.add_node("human_review", partial(with_db_session, human_review_node))
    workflow.add_node("complete", partial(with_db_session, complete_node))
    workflow.add_node("error", partial(with_db_session, error_node))

    # Define routing logic
    def route_next(state: DamageClaimState) -> str:
        """Route to next node based on state."""
        next_step = state.next_step

        if next_step == "cost_estimation":
            return "cost_estimation"
        elif next_step == "validation":
            return "validation"
        elif next_step == "routing":
            return "routing"
        elif next_step == "human_review":
            return "human_review"
        elif next_step == "complete":
            return "complete"
        elif next_step == "error":
            return "error"
        elif next_step == "awaiting_approval":
            return END  # Pause for human review
        elif next_step is None:
            return END
        else:
            logger.warning(f"Unknown next_step: {next_step}, defaulting to error")
            return "error"

    # Add edges
    workflow.add_edge(START, "intake")

    # Conditional edges based on next_step
    workflow.add_conditional_edges(
        "intake",
        route_next,
        {
            "cost_estimation": "cost_estimation",
            "error": "error",
        }
    )

    workflow.add_conditional_edges(
        "cost_estimation",
        route_next,
        {
            "validation": "validation",
            "error": "error",
        }
    )

    workflow.add_conditional_edges(
        "validation",
        route_next,
        {
            "routing": "routing",
            "error": "error",
        }
    )

    workflow.add_conditional_edges(
        "routing",
        route_next,
        {
            "human_review": "human_review",
            "complete": "complete",
            "error": "error",
        }
    )

    workflow.add_conditional_edges(
        "human_review",
        route_next,
        {
            "awaiting_approval": END,
            "complete": "complete",
        }
    )

    workflow.add_edge("complete", END)

    workflow.add_conditional_edges(
        "error",
        route_next,
        {
            "intake": "intake",  # Retry
            "human_review": "human_review",  # Escalate
        }
    )

    # Compile with optional checkpointer
    # Use interrupt_before to pause before human_review node
    if checkpointer:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_review"]
        )
    return workflow.compile()


class DamageClaimWorkflow:
    """
    High-level interface for damage claim processing workflow.

    Provides methods to:
    - Process new claims
    - Resume paused workflows after human approval
    - Check workflow status
    """

    def __init__(self, use_checkpointer: bool = True):
        """
        Initialize the workflow.

        Args:
            use_checkpointer: Whether to use memory checkpointer for state persistence
        """
        self.checkpointer = MemorySaver() if use_checkpointer else None
        self.workflow = create_workflow(self.checkpointer)

    def process_claim(
        self,
        claim: DamageClaim,
        thread_id: Optional[str] = None
    ) -> DamageClaimState:
        """
        Process a new damage claim through the workflow.

        Args:
            claim: The damage claim to process
            thread_id: Optional thread ID for checkpointing (defaults to claim_id)

        Returns:
            Final workflow state (may be interrupted if human review needed)
        """
        # Create initial state
        initial_state = DamageClaimState(claim=claim)

        # Use claim_id as thread_id if not provided
        config = {"configurable": {"thread_id": thread_id or claim.claim_id}}

        logger.info(f"Starting workflow for claim {claim.claim_id}")

        # Run workflow - may be interrupted for human review
        result_dict = self.workflow.invoke(initial_state, config)

        # LangGraph returns a dict, convert to state object
        if isinstance(result_dict, dict):
            # Merge with initial state and create new state
            result = initial_state.model_copy(update=result_dict)
        else:
            result = result_dict

        # Check if workflow was interrupted (requires human review)
        if self.checkpointer:
            state_snapshot = self.workflow.get_state(config)
            if state_snapshot and state_snapshot.next:
                # Workflow is paused at a node
                logger.info(
                    f"Workflow paused for claim {claim.claim_id} at: {state_snapshot.next}"
                )
                # Update result to reflect interrupted state
                result = result.model_copy(update={
                    "requires_human_approval": True,
                    "workflow_complete": False,
                })

        logger.info(
            f"Workflow {'paused' if result.requires_human_approval and not result.workflow_complete else 'complete'} "
            f"for {claim.claim_id}: complete={result.workflow_complete}, "
            f"requires_approval={result.requires_human_approval}"
        )

        return result

    def resume_after_approval(
        self,
        claim_id: str,
        approved: bool,
        reviewer_id: str,
        notes: Optional[str] = None
    ) -> DamageClaimState:
        """
        Resume workflow after human approval decision.

        Args:
            claim_id: The claim ID (used as thread_id)
            approved: Whether the claim was approved
            reviewer_id: ID of the reviewer
            notes: Optional reviewer notes

        Returns:
            Final workflow state
        """
        config = {"configurable": {"thread_id": claim_id}}

        # Get current state from checkpointer
        if not self.checkpointer:
            raise ValueError("Cannot resume without checkpointer")

        # Get current state
        state_snapshot = self.workflow.get_state(config)
        if not state_snapshot or not state_snapshot.values:
            raise ValueError(f"No workflow state found for claim {claim_id}")

        current_state = state_snapshot.values

        # Log the decision and update approval queue
        db = SessionLocal()
        try:
            from src.services.event_logger import EventLogger
            event_logger = EventLogger(db)

            if approved:
                event_logger.emit_claim_approved(
                    claim_id=claim_id,
                    reviewer_id=reviewer_id,
                    notes=notes
                )
            else:
                event_logger.emit_claim_rejected(
                    claim_id=claim_id,
                    reviewer_id=reviewer_id,
                    reason=notes or "Rejected without notes"
                )

            # Update approval queue status
            queue_item = db.query(ApprovalQueueDB).filter(
                ApprovalQueueDB.claim_id == claim_id,
                ApprovalQueueDB.status == "pending_review"
            ).first()

            if queue_item:
                queue_item.status = "approved" if approved else "rejected"
                queue_item.reviewer_id = reviewer_id
                queue_item.decision_notes = notes
                queue_item.decision_timestamp = datetime.now()
                queue_item.approved = approved
                db.commit()
                logger.info(
                    f"Updated approval queue: {queue_item.queue_id} -> "
                    f"{'approved' if approved else 'rejected'}"
                )

        finally:
            db.close()

        logger.info(
            f"Resuming workflow for {claim_id}: "
            f"approved={approved}, reviewer={reviewer_id}"
        )

        # Update state with approval decision and continue workflow
        state_update = {
            "approval_granted": approved,
            "workflow_complete": True,
            "workflow_completed_at": datetime.now().isoformat(),
            "next_step": "complete",
        }

        # Use update_state to modify the checkpointed state
        self.workflow.update_state(config, state_update)

        # Continue the workflow from where it was interrupted
        # Pass None to continue from current state
        result_dict = self.workflow.invoke(None, config)

        # Build final state
        if isinstance(result_dict, dict):
            # Get the claim from current state
            claim_data = current_state.get("claim", {})
            if isinstance(claim_data, dict):
                # Reconstruct claim from dict
                final_state = DamageClaimState(
                    claim=DamageClaim.model_validate(claim_data),
                    workflow_complete=True,
                    approval_granted=approved,
                    workflow_completed_at=datetime.now().isoformat(),
                    cost_estimate=current_state.get("cost_estimate"),
                    validation_result=current_state.get("validation_result"),
                )
            else:
                final_state = DamageClaimState(
                    claim=claim_data,
                    workflow_complete=True,
                    approval_granted=approved,
                    workflow_completed_at=datetime.now().isoformat(),
                )
        else:
            final_state = result_dict

        return final_state

    def get_status(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current workflow status for a claim.

        Args:
            claim_id: The claim ID

        Returns:
            Status dict or None if not found
        """
        if not self.checkpointer:
            return None

        config = {"configurable": {"thread_id": claim_id}}

        try:
            state = self.workflow.get_state(config)
            if state and state.values:
                # Check if workflow is paused
                is_paused = bool(state.next)
                paused_at = list(state.next) if state.next else None

                return {
                    "claim_id": claim_id,
                    "workflow_complete": state.values.get("workflow_complete", False),
                    "requires_human_approval": state.values.get("requires_human_approval", False),
                    "approval_granted": state.values.get("approval_granted"),
                    "next_step": state.values.get("next_step"),
                    "errors": state.values.get("errors", []),
                    "is_paused": is_paused,
                    "paused_at": paused_at,
                    "cost_estimate": state.values.get("cost_estimate"),
                    "validation_result": state.values.get("validation_result"),
                }
        except Exception as e:
            logger.error(f"Error getting status for {claim_id}: {e}")

        return None

    def is_awaiting_approval(self, claim_id: str) -> bool:
        """
        Check if a workflow is paused awaiting human approval.

        Args:
            claim_id: The claim ID

        Returns:
            True if workflow is paused at human_review
        """
        status = self.get_status(claim_id)
        if status:
            return status.get("is_paused", False) and status.get("requires_human_approval", False)
        return False

    def get_pending_approvals(self) -> list:
        """
        Get all claims pending human approval from the database.

        Returns:
            List of pending approval items
        """
        db = SessionLocal()
        try:
            pending = db.query(ApprovalQueueDB).filter(
                ApprovalQueueDB.status == "pending_review"
            ).order_by(
                ApprovalQueueDB.priority.asc(),
                ApprovalQueueDB.timestamp_added.asc()
            ).all()

            return [
                {
                    "queue_id": item.queue_id,
                    "claim_id": item.claim_id,
                    "vehicle_id": item.vehicle_id,
                    "customer_id": item.customer_id,
                    "damage_description": item.damage_description,
                    "estimated_cost_eur": item.estimated_cost_eur,
                    "escalation_reason": item.escalation_reason,
                    "priority": item.priority,
                    "flags": item.flags or [],
                    "timestamp_added": item.timestamp_added.isoformat() if item.timestamp_added else None,
                    "vehicle_health_score": item.vehicle_health_score,
                    "cumulative_damage_ytd_eur": item.cumulative_damage_ytd_eur,
                    "pattern_summary": item.pattern_summary,
                    "ai_cost_reasoning": item.ai_cost_reasoning,
                    "ai_validation_reasoning": item.ai_validation_reasoning,
                }
                for item in pending
            ]
        finally:
            db.close()


# Singleton workflow instance
_workflow_instance: Optional[DamageClaimWorkflow] = None


def get_workflow() -> DamageClaimWorkflow:
    """Get or create the singleton workflow instance."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = DamageClaimWorkflow()
    return _workflow_instance


def process_claim(claim: DamageClaim) -> DamageClaimState:
    """
    Convenience function to process a claim.

    Args:
        claim: The damage claim to process

    Returns:
        Final workflow state
    """
    workflow = get_workflow()
    return workflow.process_claim(claim)
