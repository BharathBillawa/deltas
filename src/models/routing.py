"""
Routing, validation, and decision models.

Determines claim flow: auto-approve, human review, or escalation.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class RoutingDecision(str, Enum):
    """Possible routing outcomes for claims."""
    AUTO_APPROVE = "auto_approve"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    ESCALATE_TO_FINANCE = "escalate_to_finance"
    ESCALATE_TO_FLEET_MANAGEMENT = "escalate_to_fleet_management"
    REJECT = "reject"
    INVESTIGATION_REQUIRED = "investigation_required"


class EscalationReason(str, Enum):
    """Reasons for escalating to human review."""
    HIGH_COST = "high_cost"
    PATTERN_DETECTED = "pattern_detected"
    FRAUD_RISK = "fraud_risk"
    CUSTOMER_DISPUTE = "customer_dispute"
    AMBIGUOUS_DAMAGE = "ambiguous_damage"
    RETIREMENT_DECISION_NEEDED = "retirement_decision_needed"
    VIP_CUSTOMER = "vip_customer"
    INSURANCE_COVERAGE = "insurance_coverage"
    MULTIPLE_DAMAGES = "multiple_damages"
    COMPLEX_REPAIR = "complex_repair"


class PatternType(str, Enum):
    """Types of patterns detected in vehicle/customer history."""
    FREQUENT_DAMAGE = "frequent_damage"
    LOCATION_CORRELATION = "location_correlation"
    CUSTOMER_PATTERN = "customer_pattern"
    SAME_DAMAGE_TYPE = "same_damage_type"
    SEASONAL_PATTERN = "seasonal_pattern"
    MAINTENANCE_CORRELATION = "maintenance_correlation"


class FlagSeverity(str, Enum):
    """Severity of validation flags."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationFlag(BaseModel):
    """Individual validation flag or concern."""
    flag_type: str = Field(..., description="Type of flag (e.g., 'high_cost', 'pattern_detected')")
    severity: FlagSeverity
    description: str
    details: Optional[dict] = None
    recommended_action: Optional[str] = None


class PatternDetection(BaseModel):
    """Pattern detected in vehicle or customer history."""
    pattern_type: PatternType
    details: str
    threshold_exceeded: bool = Field(default=False)
    threshold_config: Optional[str] = None
    severity: FlagSeverity
    impact_on_routing: bool = Field(default=False, description="Whether this affects routing decision")


class ValidationResult(BaseModel):
    """
    Result of business rules validation.

    Determines if claim requires human review or can be auto-approved.
    """
    claim_id: str
    validation_timestamp: datetime = Field(default_factory=datetime.now)

    # Overall result
    is_valid: bool = Field(default=True)
    can_auto_approve: bool
    routing_decision: RoutingDecision

    # Reasons and explanations
    routing_reason: str = Field(..., description="Human-readable explanation of routing decision")
    escalation_reason: Optional[EscalationReason] = None
    escalation_stakeholder: Optional[str] = None

    # Flags and patterns
    flags: List[ValidationFlag] = Field(default_factory=list)
    patterns_detected: List[PatternDetection] = Field(default_factory=list)

    # Risk scoring
    fraud_risk_score: float = Field(default=0.0, ge=0.0, le=10.0)
    overall_risk_score: float = Field(default=0.0, ge=0.0, le=10.0)

    # Recommendations
    recommendations: List[str] = Field(default_factory=list)

    # Confidence
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "claim_id": "CLM-2026-001",
                "is_valid": True,
                "can_auto_approve": True,
                "routing_decision": "auto_approve",
                "routing_reason": "Cost under €500 threshold, clean history",
                "fraud_risk_score": 1.2,
                "overall_risk_score": 2.5
            }
        }


    )


class ApprovalQueueItem(BaseModel):
    """
    Item in human approval queue.

    Represents a claim awaiting human review with full context.
    """
    queue_id: str
    claim_id: str
    timestamp_added: datetime = Field(default_factory=datetime.now)

    # Claim summary
    vehicle_id: str
    customer_id: str
    damage_description: str
    estimated_cost_eur: float

    # Why it needs review
    routing_decision: RoutingDecision
    escalation_reason: EscalationReason
    flags: List[str] = Field(default_factory=list)

    # Context for reviewer
    vehicle_health_score: Optional[float] = None
    cumulative_damage_ytd_eur: Optional[float] = None
    pattern_summary: Optional[str] = None

    # AI reasoning (if agents were used)
    ai_cost_reasoning: Optional[str] = Field(
        default=None,
        description="LLM reasoning for cost estimation"
    )
    ai_validation_reasoning: Optional[str] = Field(
        default=None,
        description="LLM reasoning for validation decision"
    )

    # Queue management
    assigned_to: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5, description="1=highest, 5=lowest")
    status: str = Field(default="pending_review")
    sla_deadline: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queue_id": "Q-2026-001",
                "claim_id": "CLM-2026-002",
                "vehicle_id": "AUDI-A6-2019-004",
                "damage_description": "Cracked front bumper",
                "estimated_cost_eur": 965,
                "escalation_reason": "high_cost",
                "priority": 2
            }
        }


    )


class ApprovalDecision(BaseModel):
    """Human reviewer's decision on a claim."""
    queue_id: str
    claim_id: str
    reviewer_id: str
    decision_timestamp: datetime = Field(default_factory=datetime.now)

    # Decision
    approved: bool
    decision_notes: Optional[str] = None
    adjusted_cost_eur: Optional[float] = Field(default=None, description="If reviewer adjusted cost")

    # Next actions
    requires_further_review: bool = Field(default=False)
    escalate_to: Optional[str] = None
    follow_up_actions: List[str] = Field(default_factory=list)


class CustomerRiskProfile(BaseModel):
    """Customer risk assessment for fraud detection."""
    customer_id: str
    risk_score: float = Field(ge=0.0, le=10.0)

    # History
    total_rentals: int
    damages_reported: int
    damage_rate_percent: float
    disputed_claims: int

    # Risk factors
    is_high_risk: bool = Field(default=False)
    risk_factors: List[str] = Field(default_factory=list)

    # Recommendation
    recommendation: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "CUST-RISK-001",
                "risk_score": 7.8,
                "total_rentals": 12,
                "damages_reported": 4,
                "damage_rate_percent": 33.3,
                "is_high_risk": True,
                "recommendation": "Higher deposit, premium insurance required"
            }
        }


    )
