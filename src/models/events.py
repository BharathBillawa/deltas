"""
Event models for event-driven architecture.

All state changes emit events for loose coupling and audit trail.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events in the system."""
    # Claim lifecycle
    CLAIM_RECEIVED = "claim_received"
    CLAIM_VALIDATED = "claim_validated"
    COST_ESTIMATED = "cost_estimated"
    INVOICE_GENERATED = "invoice_generated"
    CLAIM_APPROVED = "claim_approved"
    CLAIM_REJECTED = "claim_rejected"

    # Routing & escalation
    APPROVAL_REQUIRED = "approval_required"
    CLAIM_ESCALATED = "claim_escalated"
    HUMAN_REVIEW_COMPLETED = "human_review_completed"

    # Pattern recognition
    PATTERN_DETECTED = "pattern_detected"
    FRAUD_ALERT = "fraud_alert"
    RETIREMENT_ALERT = "retirement_alert"

    # Notifications
    NOTIFICATION_SENT = "notification_sent"
    CUSTOMER_NOTIFIED = "customer_notified"

    # Errors
    VALIDATION_FAILED = "validation_failed"
    ESTIMATION_FAILED = "estimation_failed"
    SYSTEM_ERROR = "system_error"


class EventPriority(str, Enum):
    """Priority levels for events."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class BaseEvent(BaseModel):
    """
    Base event model for all system events.

    Events are immutable records of state changes.
    """
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    priority: EventPriority = Field(default=EventPriority.NORMAL)

    # Source
    source_service: str = Field(..., description="Service that emitted the event")
    source_agent: Optional[str] = Field(default=None, description="Agent that emitted the event")

    # Context
    claim_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    customer_id: Optional[str] = None

    # Payload
    payload: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    correlation_id: Optional[str] = Field(default=None, description="For tracing related events")
    tags: list[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_2026_001",
                "event_type": "claim_received",
                "source_service": "intake_agent",
                "claim_id": "CLM-2026-001",
                "timestamp": "2026-02-28T10:30:00Z"
            }
        }


class ClaimReceivedEvent(BaseEvent):
    """Event: New damage claim entered the system."""
    event_type: EventType = Field(default=EventType.CLAIM_RECEIVED, const=True)

    def __init__(self, **data):
        data["event_type"] = EventType.CLAIM_RECEIVED
        super().__init__(**data)


class CostEstimatedEvent(BaseEvent):
    """Event: Cost estimation completed for claim."""
    event_type: EventType = Field(default=EventType.COST_ESTIMATED, const=True)
    estimated_cost_eur: float = Field(..., ge=0)
    depreciation_applied: bool = Field(default=False)

    def __init__(self, **data):
        data["event_type"] = EventType.COST_ESTIMATED
        super().__init__(**data)


class ApprovalRequiredEvent(BaseEvent):
    """Event: Claim requires human approval."""
    event_type: EventType = Field(default=EventType.APPROVAL_REQUIRED, const=True)
    priority: EventPriority = Field(default=EventPriority.HIGH)
    escalation_reason: str
    queue_id: str

    def __init__(self, **data):
        data["event_type"] = EventType.APPROVAL_REQUIRED
        super().__init__(**data)


class PatternDetectedEvent(BaseEvent):
    """Event: Pattern detected in vehicle or customer history."""
    event_type: EventType = Field(default=EventType.PATTERN_DETECTED, const=True)
    priority: EventPriority = Field(default=EventPriority.HIGH)
    pattern_type: str
    pattern_details: str
    severity: str

    def __init__(self, **data):
        data["event_type"] = EventType.PATTERN_DETECTED
        super().__init__(**data)


class FraudAlertEvent(BaseEvent):
    """Event: Potential fraud detected."""
    event_type: EventType = Field(default=EventType.FRAUD_ALERT, const=True)
    priority: EventPriority = Field(default=EventPriority.CRITICAL)
    fraud_risk_score: float = Field(..., ge=0.0, le=10.0)
    risk_factors: list[str]

    def __init__(self, **data):
        data["event_type"] = EventType.FRAUD_ALERT
        super().__init__(**data)


class RetirementAlertEvent(BaseEvent):
    """Event: Vehicle retirement should be considered."""
    event_type: EventType = Field(default=EventType.RETIREMENT_ALERT, const=True)
    priority: EventPriority = Field(default=EventPriority.HIGH)
    recommendation: str
    net_benefit_auction_eur: float

    def __init__(self, **data):
        data["event_type"] = EventType.RETIREMENT_ALERT
        super().__init__(**data)


class NotificationSentEvent(BaseEvent):
    """Event: Notification sent to stakeholder."""
    event_type: EventType = Field(default=EventType.NOTIFICATION_SENT, const=True)
    recipient: str
    notification_type: str
    channel: str = Field(..., description="email, sms, webhook, etc.")

    def __init__(self, **data):
        data["event_type"] = EventType.NOTIFICATION_SENT
        super().__init__(**data)


class EventSubscription(BaseModel):
    """
    Event subscription configuration.

    Defines which events a service/component wants to receive.
    """
    subscriber_id: str
    event_types: list[EventType]
    filter_conditions: Optional[Dict[str, Any]] = Field(default=None)
    callback_url: Optional[str] = Field(default=None)
    active: bool = Field(default=True)


class EventLog(BaseModel):
    """
    Event log entry for audit trail.

    All events are persisted for compliance and debugging.
    """
    event: BaseEvent
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_duration_ms: Optional[float] = None
    subscribers_notified: int = Field(default=0)
    errors: list[str] = Field(default_factory=list)
