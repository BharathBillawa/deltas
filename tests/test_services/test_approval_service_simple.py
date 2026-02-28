"""
Simplified unit tests for ApprovalService.

Tests core approval queue functionality without complex Pydantic fixtures.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, ApprovalQueueDB
from src.services.approval_service import ApprovalService


@pytest.fixture
def db_session():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def approval_service(db_session):
    """Create approval service."""
    return ApprovalService(db_session)


def create_queue_item(db_session, claim_id="CLAIM-001", status="pending_review", priority=3):
    """Helper to create queue item directly in DB."""
    from uuid import uuid4

    item = ApprovalQueueDB(
        queue_id=str(uuid4()),
        claim_id=claim_id,
        vehicle_id="VEH-001",
        customer_id="CUST-001",
        damage_description="Minor scratch at door",
        estimated_cost_eur=300.0,
        flags=["test_flag"],
        routing_decision="requires_human_review",
        escalation_reason="Test reason",
        priority=priority,
        status=status
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item.queue_id


class TestGetPendingApprovals:
    """Test retrieving pending approvals."""

    def test_empty_queue(self, approval_service):
        """Empty queue should return empty list."""
        pending = approval_service.get_pending_approvals()
        assert len(pending) == 0

    def test_get_pending_items(self, approval_service, db_session):
        """Should retrieve pending items."""
        queue_id = create_queue_item(db_session)
        pending = approval_service.get_pending_approvals()

        assert len(pending) == 1
        assert pending[0]["queue_id"] == queue_id
        assert pending[0]["claim_id"] == "CLAIM-001"

    def test_priority_sorting(self, approval_service, db_session):
        """Should sort by priority (1=highest first)."""
        # Add items with different priorities (1=highest, 5=lowest)
        create_queue_item(db_session, "CLAIM-1", priority=5)  # lowest
        create_queue_item(db_session, "CLAIM-2", priority=2)  # high
        create_queue_item(db_session, "CLAIM-3", priority=1)  # critical/highest
        create_queue_item(db_session, "CLAIM-4", priority=3)  # medium

        pending = approval_service.get_pending_approvals()

        # Should be ordered: 1 (highest), 2, 3, 5
        assert pending[0]["priority"] == 1
        assert pending[1]["priority"] == 2
        assert pending[2]["priority"] == 3
        assert pending[3]["priority"] == 5

    def test_excludes_non_pending(self, approval_service, db_session):
        """Should only return pending items."""
        create_queue_item(db_session, "CLAIM-1", status="pending_review")
        create_queue_item(db_session, "CLAIM-2", status="approved")
        create_queue_item(db_session, "CLAIM-3", status="rejected")

        pending = approval_service.get_pending_approvals()

        assert len(pending) == 1
        assert pending[0]["claim_id"] == "CLAIM-1"


class TestGetById:
    """Test retrieving specific queue items."""

    def test_get_existing_item(self, approval_service, db_session):
        """Should retrieve item by ID."""
        queue_id = create_queue_item(db_session)
        item = approval_service.get_by_id(queue_id)

        assert item is not None
        assert item["queue_id"] == queue_id
        assert item["claim_id"] == "CLAIM-001"

    def test_get_nonexistent_item(self, approval_service):
        """Should return None for invalid ID."""
        item = approval_service.get_by_id("INVALID-ID")
        assert item is None


class TestApprove:
    """Test claim approval."""

    def test_approve_item(self, approval_service, db_session):
        """Should approve item successfully."""
        queue_id = create_queue_item(db_session)

        result = approval_service.approve(queue_id, "reviewer-001", "Approved")

        assert result is True

        item = approval_service.get_by_id(queue_id)
        assert item["status"] == "approved"
        assert item["reviewer_id"] == "reviewer-001"
        assert item["decision_notes"] == "Approved"
        assert item["approved"] is True

    def test_approve_invalid_id(self, approval_service):
        """Should return False for invalid ID."""
        result = approval_service.approve("INVALID-ID", "reviewer-001")
        assert result is False

    def test_approve_already_reviewed(self, approval_service, db_session):
        """Should raise error if already reviewed."""
        queue_id = create_queue_item(db_session)
        approval_service.approve(queue_id, "reviewer-001")

        with pytest.raises(ValueError, match="already reviewed"):
            approval_service.approve(queue_id, "reviewer-002")


class TestReject:
    """Test claim rejection."""

    def test_reject_item(self, approval_service, db_session):
        """Should reject item successfully."""
        queue_id = create_queue_item(db_session)

        result = approval_service.reject(queue_id, "reviewer-001", "Insufficient evidence")

        assert result is True

        item = approval_service.get_by_id(queue_id)
        assert item["status"] == "rejected"
        assert item["decision_notes"] == "Insufficient evidence"
        assert item["approved"] is False

    def test_reject_requires_notes(self, approval_service, db_session):
        """Should require rejection notes."""
        queue_id = create_queue_item(db_session)

        with pytest.raises(ValueError, match="required"):
            approval_service.reject(queue_id, "reviewer-001", "")


class TestEscalate:
    """Test claim escalation."""

    def test_escalate_item(self, approval_service, db_session):
        """Should escalate item successfully."""
        queue_id = create_queue_item(db_session)

        result = approval_service.escalate(queue_id, "reviewer-001", "Complex case")

        assert result is True

        item = approval_service.get_by_id(queue_id)
        assert item["status"] == "escalated"
        assert item["priority"] == 1  # Highest priority
        assert item["decision_notes"] == "Complex case"


class TestQueueStats:
    """Test queue statistics."""

    def test_empty_stats(self, approval_service):
        """Empty queue should return zeros."""
        stats = approval_service.get_queue_stats()

        assert stats["pending"] == 0
        assert stats["approved"] == 0
        assert stats["rejected"] == 0
        assert stats["escalated"] == 0
        assert stats["total"] == 0

    def test_stats_with_items(self, approval_service, db_session):
        """Should calculate stats correctly."""
        # Create items with different statuses
        q1 = create_queue_item(db_session, "CLAIM-1", status="pending_review")
        q2 = create_queue_item(db_session, "CLAIM-2", status="pending_review")
        q3 = create_queue_item(db_session, "CLAIM-3", status="pending_review")

        # Process some
        approval_service.approve(q1, "reviewer-001")
        approval_service.reject(q2, "reviewer-001", "Invalid")

        stats = approval_service.get_queue_stats()

        assert stats["pending"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["total"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
