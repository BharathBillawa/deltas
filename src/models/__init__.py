"""
Data models for car rental damage claims automation.

All models use Pydantic V2 for type safety, validation, and serialization.
Based on realistic German market data with validated costs (GDV/Dekra 2024).
"""

# Damage and vehicle models
from src.models.damage import (
    DamageAssessment,
    DamageClaim,
    DamageSeverity,
    DamageStatus,
    DamageType,
    HistoricalDamage,
    RentalHistorySummary,
    ServiceRecord,
    VehicleCategory,
    VehicleInfo,
    VehicleLocation,
)

# Financial models
from src.models.financial import (
    CostEstimate,
    DepreciationCalculation,
    DepreciationComponent,
    Invoice,
    InvoiceLineItem,
    LaborType,
    RetirementAnalysis,
)

# Routing and validation models
from src.models.routing import (
    ApprovalDecision,
    ApprovalQueueItem,
    CustomerRiskProfile,
    EscalationReason,
    FlagSeverity,
    PatternDetection,
    PatternType,
    RoutingDecision,
    ValidationFlag,
    ValidationResult,
)

# Event models
from src.models.events import (
    ApprovalRequiredEvent,
    BaseEvent,
    ClaimReceivedEvent,
    CostEstimatedEvent,
    EventLog,
    EventPriority,
    EventSubscription,
    EventType,
    FraudAlertEvent,
    NotificationSentEvent,
    PatternDetectedEvent,
    RetirementAlertEvent,
)

# State model for LangGraph
from src.models.state import (
    DamageClaimState,
    Notification,
    StateAnnotation,
    WorkflowError,
)

__all__ = [
    # Damage models
    "DamageAssessment",
    "DamageClaim",
    "DamageSeverity",
    "DamageStatus",
    "DamageType",
    "HistoricalDamage",
    "RentalHistorySummary",
    "ServiceRecord",
    "VehicleCategory",
    "VehicleInfo",
    "VehicleLocation",
    # Financial models
    "CostEstimate",
    "DepreciationCalculation",
    "DepreciationComponent",
    "Invoice",
    "InvoiceLineItem",
    "LaborType",
    "RetirementAnalysis",
    # Routing models
    "ApprovalDecision",
    "ApprovalQueueItem",
    "CustomerRiskProfile",
    "EscalationReason",
    "FlagSeverity",
    "PatternDetection",
    "PatternType",
    "RoutingDecision",
    "ValidationFlag",
    "ValidationResult",
    # Event models
    "ApprovalRequiredEvent",
    "BaseEvent",
    "ClaimReceivedEvent",
    "CostEstimatedEvent",
    "EventLog",
    "EventPriority",
    "EventSubscription",
    "EventType",
    "FraudAlertEvent",
    "NotificationSentEvent",
    "PatternDetectedEvent",
    "RetirementAlertEvent",
    # State models
    "DamageClaimState",
    "Notification",
    "StateAnnotation",
    "WorkflowError",
]
