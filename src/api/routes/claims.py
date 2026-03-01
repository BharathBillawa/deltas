"""
Claims API endpoints.

Routes for submitting and checking claim status.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.models.damage import DamageClaim, DamageAssessment, DamageType, DamageSeverity, VehicleLocation
from src.graph.workflow import get_workflow

router = APIRouter()


# Request/Response Models

class SubmitClaimRequest(BaseModel):
    """Request model for submitting a claim."""
    claim_id: str = Field(..., description="Unique claim identifier")
    vehicle_id: str = Field(..., description="Vehicle identifier")
    customer_id: str = Field(..., description="Customer identifier")
    rental_agreement_id: str = Field(..., description="Rental agreement ID")
    return_location: str = Field(..., description="Return location")
    damage_type: DamageType = Field(..., description="Type of damage")
    severity: DamageSeverity = Field(..., description="Damage severity")
    location: VehicleLocation = Field(..., description="Damage location on vehicle")
    description: str = Field(..., description="Damage description")
    affected_parts: list[str] = Field(..., description="List of affected parts")
    photos: list[str] = Field(default_factory=list, description="Photo URIs")
    inspector_id: Optional[str] = Field(None, description="Inspector ID")
    inspector_notes: Optional[str] = Field(None, description="Inspector notes")

    class Config:
        json_schema_extra = {
            "example": {
                "claim_id": "CLM-2026-999",
                "vehicle_id": "VW-POLO-2023-001",
                "customer_id": "CUST-5678",
                "rental_agreement_id": "RNT-2026-9999",
                "return_location": "Munich_Airport",
                "damage_type": "scratch",
                "severity": "minor",
                "location": "rear_bumper",
                "description": "Small scratch on rear bumper",
                "affected_parts": ["rear_bumper"],
                "photos": ["photo1.jpg"],
                "inspector_id": "INSP-001"
            }
        }


class ClaimStatusResponse(BaseModel):
    """Response model for claim status."""
    claim_id: str
    workflow_complete: bool
    requires_human_approval: bool
    approval_granted: Optional[bool] = None
    estimated_cost_eur: Optional[float] = None
    routing_decision: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    next_step: Optional[str] = None
    is_paused: bool = False
    message: Optional[str] = None


class ClaimSubmissionResponse(BaseModel):
    """Response model for claim submission."""
    claim_id: str
    status: str
    workflow_complete: bool
    requires_human_approval: bool
    approval_granted: Optional[bool] = None
    estimated_cost_eur: Optional[float] = None
    message: str


# Endpoints

@router.post("/", response_model=ClaimSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_claim(request: SubmitClaimRequest):
    """
    Submit a new damage claim for processing.

    The claim will be processed through the workflow:
    - Cost estimation
    - Pattern recognition
    - Validation
    - Routing (auto-approve or human review)

    Returns the initial processing result.
    """
    try:
        # Build DamageClaim from request
        damage_assessment = DamageAssessment(
            damage_type=request.damage_type,
            severity=request.severity,
            location=request.location,
            description=request.description,
            affected_parts=request.affected_parts,
            photos=request.photos,
            inspector_id=request.inspector_id or "API_SUBMISSION",
            inspector_notes=request.inspector_notes
        )

        claim = DamageClaim(
            claim_id=request.claim_id,
            timestamp=datetime.now(),
            vehicle_id=request.vehicle_id,
            customer_id=request.customer_id,
            rental_agreement_id=request.rental_agreement_id,
            return_location=request.return_location,
            damage_assessment=damage_assessment
        )

        # Process through workflow
        workflow = get_workflow()
        result = workflow.process_claim(claim)

        # Build response
        estimated_cost = result.cost_estimate.total_eur if result.cost_estimate else None

        if result.workflow_complete and result.approval_granted:
            message = f"Claim auto-approved. Estimated cost: €{estimated_cost:.2f}"
            status_str = "approved"
        elif result.requires_human_approval:
            message = "Claim requires human review. Check /queue for pending approvals."
            status_str = "pending_review"
        else:
            message = "Claim submitted and processing."
            status_str = "processing"

        return ClaimSubmissionResponse(
            claim_id=request.claim_id,
            status=status_str,
            workflow_complete=result.workflow_complete,
            requires_human_approval=result.requires_human_approval,
            approval_granted=result.approval_granted,
            estimated_cost_eur=estimated_cost,
            message=message
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process claim: {str(e)}"
        )


@router.get("/{claim_id}", response_model=ClaimStatusResponse)
async def get_claim_status(claim_id: str):
    """
    Get the current status of a claim.

    Returns workflow state, cost estimate, and routing decision.
    """
    try:
        workflow = get_workflow()
        workflow_status = workflow.get_status(claim_id)

        if not workflow_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found"
            )

        # Extract cost estimate
        estimated_cost = None
        if workflow_status.get("cost_estimate"):
            cost_est = workflow_status["cost_estimate"]
            estimated_cost = cost_est.get("total_eur") if isinstance(cost_est, dict) else cost_est.total_eur

        # Extract routing decision
        routing_decision = None
        if workflow_status.get("validation_result"):
            val_result = workflow_status["validation_result"]
            if isinstance(val_result, dict):
                routing_decision = val_result.get("routing_decision")
            else:
                routing_decision = val_result.routing_decision.value if val_result.routing_decision else None

        # Extract flags
        flags = []
        if workflow_status.get("validation_result"):
            val_result = workflow_status["validation_result"]
            if isinstance(val_result, dict):
                flags_data = val_result.get("flags", [])
                flags = [f.get("flag_type") if isinstance(f, dict) else f.flag_type for f in flags_data]
            else:
                flags = [f.flag_type for f in val_result.flags] if val_result.flags else []

        # Build message
        if workflow_status["workflow_complete"]:
            if workflow_status.get("approval_granted"):
                message = "Claim approved"
            elif workflow_status.get("approval_granted") is False:
                message = "Claim rejected"
            else:
                message = "Workflow complete"
        elif workflow_status["requires_human_approval"]:
            message = "Awaiting human review"
        else:
            message = "Processing"

        return ClaimStatusResponse(
            claim_id=claim_id,
            workflow_complete=workflow_status["workflow_complete"],
            requires_human_approval=workflow_status["requires_human_approval"],
            approval_granted=workflow_status.get("approval_granted"),
            estimated_cost_eur=estimated_cost,
            routing_decision=routing_decision,
            flags=flags[:5],  # Limit to 5 flags
            next_step=workflow_status.get("next_step"),
            is_paused=workflow_status.get("is_paused", False),
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get claim status: {str(e)}"
        )
