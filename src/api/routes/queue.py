"""
Approval Queue API endpoints.

Routes for managing human-in-the-loop approvals.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.graph.workflow import DamageClaimWorkflow
from src.persistence.database import get_db, ApprovalQueueDB
from src.services.approval_service import ApprovalService

router = APIRouter()


# Request/Response Models

class QueueItemResponse(BaseModel):
    """Response model for queue item."""
    queue_id: str
    claim_id: str
    vehicle_id: str
    customer_id: str
    damage_description: str
    estimated_cost_eur: float
    escalation_reason: str
    priority: int
    flags: list[str] = Field(default_factory=list)
    timestamp_added: str
    status: str = "pending_review"


class ApproveRequest(BaseModel):
    """Request model for approving a claim."""
    reviewer_id: str = Field(..., description="ID of the reviewer")
    notes: Optional[str] = Field(None, description="Optional approval notes")

    class Config:
        json_schema_extra = {
            "example": {
                "reviewer_id": "REVIEWER-001",
                "notes": "Approved after verification"
            }
        }


class RejectRequest(BaseModel):
    """Request model for rejecting a claim."""
    reviewer_id: str = Field(..., description="ID of the reviewer")
    reason: str = Field(..., description="Rejection reason (required)")

    class Config:
        json_schema_extra = {
            "example": {
                "reviewer_id": "REVIEWER-001",
                "reason": "Insufficient documentation"
            }
        }


class ApprovalResponse(BaseModel):
    """Response model for approval/rejection."""
    queue_id: str
    claim_id: str
    action: str
    reviewer_id: str
    workflow_complete: bool
    message: str


# Endpoints

@router.get("/", response_model=list[QueueItemResponse])
async def list_pending_approvals(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all claims pending human approval.

    Returns claims sorted by priority and timestamp.
    """
    try:
        workflow = DamageClaimWorkflow(use_checkpointer=True)
        pending = workflow.get_pending_approvals()

        # Limit results
        pending = pending[:limit]

        return [
            QueueItemResponse(
                queue_id=item["queue_id"],
                claim_id=item["claim_id"],
                vehicle_id=item["vehicle_id"],
                customer_id=item["customer_id"],
                damage_description=item["damage_description"],
                estimated_cost_eur=item["estimated_cost_eur"],
                escalation_reason=item["escalation_reason"],
                priority=item["priority"],
                flags=item.get("flags", []),
                timestamp_added=item.get("timestamp_added", ""),
                status="pending_review"
            )
            for item in pending
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending approvals: {str(e)}"
        )


@router.get("/{queue_id}", response_model=QueueItemResponse)
async def get_queue_item(
    queue_id: str,
    db: Session = Depends(get_db)
):
    """
    Get details for a specific queue item.
    """
    try:
        approval_service = ApprovalService(db)
        item = approval_service.get_by_id(queue_id)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue item {queue_id} not found"
            )

        return QueueItemResponse(
            queue_id=item["queue_id"],
            claim_id=item["claim_id"],
            vehicle_id=item["vehicle_id"],
            customer_id=item["customer_id"],
            damage_description=item["damage_description"],
            estimated_cost_eur=item["estimated_cost_eur"],
            escalation_reason=item["escalation_reason"],
            priority=item["priority"],
            flags=item.get("flags", []),
            timestamp_added=item.get("timestamp_added", ""),
            status=item.get("status", "pending_review")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch queue item: {str(e)}"
        )


@router.post("/{queue_id}/approve", response_model=ApprovalResponse)
async def approve_claim(
    queue_id: str,
    request: ApproveRequest,
    db: Session = Depends(get_db)
):
    """
    Approve a pending claim and resume workflow.

    This will:
    1. Update the approval queue status
    2. Resume the paused workflow
    3. Complete the claim processing
    """
    try:
        # Get queue item to find claim_id
        approval_service = ApprovalService(db)
        queue_item = approval_service.get_by_id(queue_id)

        if not queue_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue item {queue_id} not found"
            )

        claim_id = queue_item["claim_id"]

        # Check if already processed
        if queue_item.get("status") != "pending_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Queue item already processed: {queue_item.get('status')}"
            )

        # Resume workflow with approval
        workflow = DamageClaimWorkflow(use_checkpointer=True)

        if not workflow.is_awaiting_approval(claim_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Claim {claim_id} is not awaiting approval"
            )

        result = workflow.resume_after_approval(
            claim_id=claim_id,
            approved=True,
            reviewer_id=request.reviewer_id,
            notes=request.notes
        )

        return ApprovalResponse(
            queue_id=queue_id,
            claim_id=claim_id,
            action="approved",
            reviewer_id=request.reviewer_id,
            workflow_complete=result.workflow_complete,
            message=f"Claim {claim_id} approved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve claim: {str(e)}"
        )


@router.post("/{queue_id}/reject", response_model=ApprovalResponse)
async def reject_claim(
    queue_id: str,
    request: RejectRequest,
    db: Session = Depends(get_db)
):
    """
    Reject a pending claim.

    This will:
    1. Update the approval queue status
    2. Resume the workflow with rejection
    3. Log the rejection event
    """
    try:
        # Get queue item
        approval_service = ApprovalService(db)
        queue_item = approval_service.get_by_id(queue_id)

        if not queue_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue item {queue_id} not found"
            )

        claim_id = queue_item["claim_id"]

        # Check if already processed
        if queue_item.get("status") != "pending_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Queue item already processed: {queue_item.get('status')}"
            )

        # Resume workflow with rejection
        workflow = DamageClaimWorkflow(use_checkpointer=True)

        if not workflow.is_awaiting_approval(claim_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Claim {claim_id} is not awaiting approval"
            )

        result = workflow.resume_after_approval(
            claim_id=claim_id,
            approved=False,
            reviewer_id=request.reviewer_id,
            notes=request.reason
        )

        return ApprovalResponse(
            queue_id=queue_id,
            claim_id=claim_id,
            action="rejected",
            reviewer_id=request.reviewer_id,
            workflow_complete=result.workflow_complete,
            message=f"Claim {claim_id} rejected: {request.reason}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject claim: {str(e)}"
        )


@router.get("/stats/summary")
async def get_queue_stats(db: Session = Depends(get_db)):
    """
    Get approval queue statistics.

    Returns counts of pending, approved, rejected claims
    and average review time.
    """
    try:
        approval_service = ApprovalService(db)
        stats = approval_service.get_queue_stats()

        return {
            "pending": stats["pending"],
            "approved": stats["approved"],
            "rejected": stats["rejected"],
            "escalated": stats["escalated"],
            "total": stats["total"],
            "avg_hours_to_review": stats["avg_hours_to_review"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch queue stats: {str(e)}"
        )
