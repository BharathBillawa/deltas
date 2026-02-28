"""
Event Logger - Simple event emission to database.

Provides event tracking for audit trail and observability.
"""

import logging
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from src.persistence.database import EventLogDB
from src.models.events import BaseEvent

logger = logging.getLogger(__name__)


class EventLogger:
    """
    Simple event logger for audit trail.

    Records all significant events in the damage claim workflow:
    - ClaimReceived: New claim entered system
    - CostEstimated: Cost calculation completed
    - PatternDetected: Pattern recognition found issues
    - ApprovalRequired: Claim needs human review
    - ClaimApproved/Rejected: Final decision made
    """

    def __init__(self, db_session: Session):
        """
        Initialize event logger.

        Args:
            db_session: Database session
        """
        self.db = db_session

    def emit_event(
        self,
        event_type: str,
        claim_id: str,
        data: Dict[str, Any],
        priority: str = "normal"
    ) -> str:
        """
        Emit an event to the event log.

        Args:
            event_type: Type of event (e.g., "ClaimReceived")
            claim_id: Associated claim ID
            data: Event data (will be stored as JSON)
            priority: Event priority (normal/high/critical)

        Returns:
            Event ID
        """
        event_id = str(uuid4())

        event_log = EventLogDB(
            event_id=event_id,
            claim_id=claim_id,
            event_type=event_type,
            payload=data,
            priority=priority,
            source_service="event_logger",
            timestamp=datetime.now()
        )

        self.db.add(event_log)
        self.db.commit()
        self.db.refresh(event_log)

        logger.debug(f"Event emitted: {event_type} for claim {claim_id}")

        return event_id

    def emit_claim_received(
        self,
        claim_id: str,
        vehicle_id: str,
        customer_id: str,
        damage_type: str
    ) -> str:
        """
        Emit ClaimReceived event.

        Args:
            claim_id: Claim identifier
            vehicle_id: Vehicle identifier
            customer_id: Customer identifier
            damage_type: Type of damage

        Returns:
            Event ID
        """
        return self.emit_event(
            event_type="ClaimReceived",
            claim_id=claim_id,
            data={
                "vehicle_id": vehicle_id,
                "customer_id": customer_id,
                "damage_type": damage_type
            }
        )

    def emit_cost_estimated(
        self,
        claim_id: str,
        estimated_cost_eur: float,
        labor_cost_eur: float,
        parts_cost_eur: float
    ) -> str:
        """
        Emit CostEstimated event.

        Args:
            claim_id: Claim identifier
            estimated_cost_eur: Total estimated cost
            labor_cost_eur: Labor cost
            parts_cost_eur: Parts cost

        Returns:
            Event ID
        """
        return self.emit_event(
            event_type="CostEstimated",
            claim_id=claim_id,
            data={
                "estimated_cost_eur": estimated_cost_eur,
                "labor_cost_eur": labor_cost_eur,
                "parts_cost_eur": parts_cost_eur
            }
        )

    def emit_pattern_detected(
        self,
        claim_id: str,
        pattern_type: str,
        severity: str,
        description: str
    ) -> str:
        """
        Emit PatternDetected event.

        Args:
            claim_id: Claim identifier
            pattern_type: Type of pattern detected
            severity: Pattern severity
            description: Pattern description

        Returns:
            Event ID
        """
        return self.emit_event(
            event_type="PatternDetected",
            claim_id=claim_id,
            data={
                "pattern_type": pattern_type,
                "severity": severity,
                "description": description
            },
            priority="high"
        )

    def emit_approval_required(
        self,
        claim_id: str,
        reason: str,
        flags: list
    ) -> str:
        """
        Emit ApprovalRequired event.

        Args:
            claim_id: Claim identifier
            reason: Reason for requiring approval
            flags: List of validation flags

        Returns:
            Event ID
        """
        return self.emit_event(
            event_type="ApprovalRequired",
            claim_id=claim_id,
            data={
                "reason": reason,
                "flags": flags
            },
            priority="high"
        )

    def emit_claim_approved(
        self,
        claim_id: str,
        reviewer_id: str,
        notes: str = None
    ) -> str:
        """
        Emit ClaimApproved event.

        Args:
            claim_id: Claim identifier
            reviewer_id: Reviewer identifier
            notes: Optional approval notes

        Returns:
            Event ID
        """
        return self.emit_event(
            event_type="ClaimApproved",
            claim_id=claim_id,
            data={
                "reviewer_id": reviewer_id,
                "notes": notes
            }
        )

    def emit_claim_rejected(
        self,
        claim_id: str,
        reviewer_id: str,
        reason: str
    ) -> str:
        """
        Emit ClaimRejected event.

        Args:
            claim_id: Claim identifier
            reviewer_id: Reviewer identifier
            reason: Rejection reason

        Returns:
            Event ID
        """
        return self.emit_event(
            event_type="ClaimRejected",
            claim_id=claim_id,
            data={
                "reviewer_id": reviewer_id,
                "reason": reason
            },
            priority="high"
        )

    def get_events_for_claim(self, claim_id: str) -> list:
        """
        Get all events for a specific claim.

        Args:
            claim_id: Claim identifier

        Returns:
            List of events ordered by timestamp
        """
        events = self.db.query(EventLogDB).filter(
            EventLogDB.claim_id == claim_id
        ).order_by(
            EventLogDB.timestamp.asc()
        ).all()

        return [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "priority": e.priority,
                "timestamp": e.timestamp.isoformat(),
                "data": e.payload or {}
            }
            for e in events
        ]

    def get_recent_events(self, limit: int = 50) -> list:
        """
        Get recent events across all claims.

        Args:
            limit: Max number of events to return

        Returns:
            List of recent events
        """
        events = self.db.query(EventLogDB).order_by(
            EventLogDB.timestamp.desc()
        ).limit(limit).all()

        return [
            {
                "event_id": e.event_id,
                "claim_id": e.claim_id,
                "event_type": e.event_type,
                "priority": e.priority,
                "timestamp": e.timestamp.isoformat(),
                "data": e.payload or {}
            }
            for e in events
        ]
