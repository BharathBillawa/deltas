"""
Approval Service - Human-in-the-loop persistence.

Manages approval queue for claims requiring human review.
Provides CRUD operations with SQLite persistence.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict
from uuid import uuid4

from sqlalchemy.orm import Session

from src.persistence.database import ApprovalQueueDB
from src.models.routing import ValidationResult
from src.models.damage import DamageClaim

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Manage approval queue for claims requiring human review.

    Features:
    - Add claims to queue with validation results
    - Retrieve pending approvals (sorted by priority)
    - Approve/reject with reviewer notes
    - Handle duplicate submissions
    - Comprehensive error handling
    """

    def __init__(self, db_session: Session):
        """
        Initialize approval service.

        Args:
            db_session: Database session
        """
        self.db = db_session

    def add_to_queue(
        self,
        claim: DamageClaim,
        validation_result: ValidationResult,
        priority: int = 3
    ) -> str:
        """
        Add claim to approval queue.

        Args:
            claim: Damage claim to queue
            validation_result: Validation result with flags
            priority: Queue priority (1=highest, 5=lowest)

        Returns:
            Queue ID for tracking

        Raises:
            ValueError: If claim already in queue
        """
        # Check for duplicate
        existing = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.claim_id == claim.claim_id,
            ApprovalQueueDB.status == "pending_review"
        ).first()

        if existing:
            logger.warning(f"Claim {claim.claim_id} already in queue: {existing.queue_id}")
            raise ValueError(f"Claim {claim.claim_id} already pending review")

        # Create queue entry
        queue_id = str(uuid4())

        # Build damage description from assessment
        damage_desc = f"{claim.damage_assessment.severity.value} {claim.damage_assessment.damage_type.value} at {claim.damage_assessment.location}"

        queue_entry = ApprovalQueueDB(
            queue_id=queue_id,
            claim_id=claim.claim_id,
            vehicle_id=claim.vehicle_info.vehicle_id,
            customer_id=getattr(claim, 'customer_id', 'UNKNOWN'),
            damage_description=damage_desc,
            estimated_cost_eur=validation_result.estimated_cost_eur,
            flags=validation_result.flags,
            routing_decision="requires_human_review",
            escalation_reason=validation_result.requires_review_reason or "Manual review required",
            priority=priority,
            status="pending_review"
        )

        self.db.add(queue_entry)
        self.db.commit()
        self.db.refresh(queue_entry)

        logger.info(f"Added claim {claim.claim_id} to queue: {queue_id}")

        return queue_id

    def get_pending_approvals(self, limit: int = 50) -> List[Dict]:
        """
        Get all pending approvals sorted by priority and age.

        Args:
            limit: Max number to return (default: 50)

        Returns:
            List of pending approval items with metadata
        """
        pending = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status == "pending_review"
        ).order_by(
            ApprovalQueueDB.priority.asc(),  # 1=highest priority first
            ApprovalQueueDB.timestamp_added.asc()  # Oldest first within priority
        ).limit(limit).all()

        result = []
        for item in pending:
            # Calculate time in queue
            time_in_queue = datetime.now() - item.timestamp_added
            hours_in_queue = time_in_queue.total_seconds() / 3600

            result.append({
                "queue_id": item.queue_id,
                "claim_id": item.claim_id,
                "vehicle_id": item.vehicle_id,
                "customer_id": item.customer_id,
                "damage_description": item.damage_description,
                "estimated_cost_eur": item.estimated_cost_eur,
                "flags": item.flags or [],
                "escalation_reason": item.escalation_reason,
                "priority": item.priority,
                "timestamp_added": item.timestamp_added.isoformat(),
                "hours_in_queue": round(hours_in_queue, 1)
            })

        return result

    def get_by_id(self, queue_id: str) -> Optional[Dict]:
        """
        Get approval item by queue ID.

        Args:
            queue_id: Queue identifier

        Returns:
            Approval item details or None if not found
        """
        item = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.queue_id == queue_id
        ).first()

        if not item:
            logger.warning(f"Queue item not found: {queue_id}")
            return None

        # Calculate time metrics
        time_in_queue = datetime.now() - item.timestamp_added
        hours_in_queue = time_in_queue.total_seconds() / 3600

        return {
            "queue_id": item.queue_id,
            "claim_id": item.claim_id,
            "vehicle_id": item.vehicle_id,
            "customer_id": item.customer_id,
            "damage_description": item.damage_description,
            "estimated_cost_eur": item.estimated_cost_eur,
            "flags": item.flags or [],
            "escalation_reason": item.escalation_reason,
            "priority": item.priority,
            "status": item.status,
            "timestamp_added": item.timestamp_added.isoformat(),
            "decision_timestamp": item.decision_timestamp.isoformat() if item.decision_timestamp else None,
            "reviewer_id": item.reviewer_id,
            "decision_notes": item.decision_notes,
            "approved": item.approved,
            "hours_in_queue": round(hours_in_queue, 1)
        }

    def approve(
        self,
        queue_id: str,
        reviewer_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Approve a queued claim.

        Args:
            queue_id: Queue identifier
            reviewer_id: ID of approving reviewer
            notes: Optional reviewer notes

        Returns:
            True if approved, False if not found or invalid state

        Raises:
            ValueError: If already reviewed
        """
        item = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.queue_id == queue_id
        ).first()

        if not item:
            logger.error(f"Queue item not found: {queue_id}")
            return False

        if item.status != "pending_review":
            raise ValueError(f"Item {queue_id} already reviewed: {item.status}")

        # Update status
        item.status = "approved"
        item.decision_timestamp = datetime.now()
        item.reviewer_id = reviewer_id
        item.decision_notes = notes
        item.approved = True
        item.updated_at = datetime.now()

        self.db.commit()

        logger.info(f"Approved queue item {queue_id} by {reviewer_id}")
        return True

    def reject(
        self,
        queue_id: str,
        reviewer_id: str,
        notes: str
    ) -> bool:
        """
        Reject a queued claim.

        Args:
            queue_id: Queue identifier
            reviewer_id: ID of rejecting reviewer
            notes: Rejection reason (required)

        Returns:
            True if rejected, False if not found or invalid state

        Raises:
            ValueError: If already reviewed or missing notes
        """
        if not notes:
            raise ValueError("Rejection notes are required")

        item = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.queue_id == queue_id
        ).first()

        if not item:
            logger.error(f"Queue item not found: {queue_id}")
            return False

        if item.status != "pending_review":
            raise ValueError(f"Item {queue_id} already reviewed: {item.status}")

        # Update status
        item.status = "rejected"
        item.decision_timestamp = datetime.now()
        item.reviewer_id = reviewer_id
        item.decision_notes = notes
        item.approved = False
        item.updated_at = datetime.now()

        self.db.commit()

        logger.info(f"Rejected queue item {queue_id} by {reviewer_id}: {notes}")
        return True

    def escalate(
        self,
        queue_id: str,
        reviewer_id: str,
        notes: str
    ) -> bool:
        """
        Escalate a queued claim to higher authority.

        Args:
            queue_id: Queue identifier
            reviewer_id: ID of escalating reviewer
            notes: Escalation reason (required)

        Returns:
            True if escalated, False if not found or invalid state
        """
        if not notes:
            raise ValueError("Escalation notes are required")

        item = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.queue_id == queue_id
        ).first()

        if not item:
            logger.error(f"Queue item not found: {queue_id}")
            return False

        if item.status != "pending_review":
            raise ValueError(f"Item {queue_id} already processed: {item.status}")

        # Update status and priority
        item.status = "escalated"
        item.priority = 1  # Highest priority
        item.decision_timestamp = datetime.now()
        item.reviewer_id = reviewer_id
        item.decision_notes = notes
        item.updated_at = datetime.now()

        self.db.commit()

        logger.info(f"Escalated queue item {queue_id} by {reviewer_id}: {notes}")
        return True

    def get_queue_stats(self) -> Dict:
        """
        Get approval queue statistics.

        Returns:
            Dict with queue metrics
        """
        pending_count = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status == "pending_review"
        ).count()

        approved_count = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status == "approved"
        ).count()

        rejected_count = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status == "rejected"
        ).count()

        escalated_count = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status == "escalated"
        ).count()

        # Calculate average time in queue for completed items
        completed = self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status.in_(["approved", "rejected"]),
            ApprovalQueueDB.decision_timestamp.isnot(None)
        ).all()

        avg_hours_to_review = 0.0
        if completed:
            total_hours = sum(
                (item.decision_timestamp - item.timestamp_added).total_seconds() / 3600
                for item in completed
            )
            avg_hours_to_review = total_hours / len(completed)

        return {
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
            "escalated": escalated_count,
            "total": pending_count + approved_count + rejected_count + escalated_count,
            "avg_hours_to_review": round(avg_hours_to_review, 1)
        }
