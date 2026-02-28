"""
Unit tests for EventLogger.

Tests event emission and retrieval.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base
from src.services.event_logger import EventLogger


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
def event_logger(db_session):
    """Create event logger."""
    return EventLogger(db_session)


class TestEmitEvent:
    """Test basic event emission."""

    def test_emit_event(self, event_logger):
        """Should emit event successfully."""
        event_id = event_logger.emit_event(
            event_type="TestEvent",
            claim_id="CLAIM-001",
            data={"test": "data"},
            
        )

        assert event_id is not None
        assert len(event_id) > 0

    def test_emit_multiple_events(self, event_logger):
        """Should emit multiple events."""
        event_id_1 = event_logger.emit_event(
            event_type="Event1",
            claim_id="CLAIM-001",
            data={"test": "1"}
        )

        event_id_2 = event_logger.emit_event(
            event_type="Event2",
            claim_id="CLAIM-001",
            data={"test": "2"}
        )

        assert event_id_1 != event_id_2


class TestSpecificEventTypes:
    """Test specific event type emitters."""

    def test_emit_claim_received(self, event_logger):
        """Should emit ClaimReceived event."""
        event_id = event_logger.emit_claim_received(
            claim_id="CLAIM-001",
            vehicle_id="VEH-001",
            customer_id="CUST-001",
            damage_type="scratch"
        )

        assert event_id is not None

        events = event_logger.get_events_for_claim("CLAIM-001")
        assert len(events) == 1
        assert events[0]["event_type"] == "ClaimReceived"

    def test_emit_cost_estimated(self, event_logger):
        """Should emit CostEstimated event."""
        event_id = event_logger.emit_cost_estimated(
            claim_id="CLAIM-002",
            estimated_cost_eur=500.0,
            labor_cost_eur=300.0,
            parts_cost_eur=200.0
        )

        assert event_id is not None

        events = event_logger.get_events_for_claim("CLAIM-002")
        assert events[0]["event_type"] == "CostEstimated"
        assert events[0]["data"]["estimated_cost_eur"] == 500.0

    def test_emit_pattern_detected(self, event_logger):
        """Should emit PatternDetected event."""
        event_id = event_logger.emit_pattern_detected(
            claim_id="CLAIM-003",
            pattern_type="frequent_damage",
            severity="high",
            description="3 damages in 90 days"
        )

        assert event_id is not None

        events = event_logger.get_events_for_claim("CLAIM-003")
        assert events[0]["event_type"] == "PatternDetected"
        assert events[0]["priority"] == "high"

    def test_emit_approval_required(self, event_logger):
        """Should emit ApprovalRequired event."""
        event_id = event_logger.emit_approval_required(
            claim_id="CLAIM-004",
            reason="Cost exceeds threshold",
            flags=["high_cost"]
        )

        assert event_id is not None

        events = event_logger.get_events_for_claim("CLAIM-004")
        assert events[0]["event_type"] == "ApprovalRequired"

    def test_emit_claim_approved(self, event_logger):
        """Should emit ClaimApproved event."""
        event_id = event_logger.emit_claim_approved(
            claim_id="CLAIM-005",
            reviewer_id="REV-001",
            notes="Approved"
        )

        assert event_id is not None

        events = event_logger.get_events_for_claim("CLAIM-005")
        assert events[0]["event_type"] == "ClaimApproved"

    def test_emit_claim_rejected(self, event_logger):
        """Should emit ClaimRejected event."""
        event_id = event_logger.emit_claim_rejected(
            claim_id="CLAIM-006",
            reviewer_id="REV-001",
            reason="Insufficient evidence"
        )

        assert event_id is not None

        events = event_logger.get_events_for_claim("CLAIM-006")
        assert events[0]["event_type"] == "ClaimRejected"


class TestGetEvents:
    """Test event retrieval."""

    def test_get_events_for_claim(self, event_logger):
        """Should retrieve all events for a claim."""
        event_logger.emit_claim_received(
            "CLAIM-007", "VEH-001", "CUST-001", "scratch"
        )
        event_logger.emit_cost_estimated(
            "CLAIM-007", 500.0, 300.0, 200.0
        )

        events = event_logger.get_events_for_claim("CLAIM-007")

        assert len(events) == 2
        assert events[0]["event_type"] == "ClaimReceived"
        assert events[1]["event_type"] == "CostEstimated"

    def test_get_events_for_nonexistent_claim(self, event_logger):
        """Should return empty list for nonexistent claim."""
        events = event_logger.get_events_for_claim("NONEXISTENT")
        assert len(events) == 0

    def test_get_recent_events(self, event_logger):
        """Should retrieve recent events across all claims."""
        for i in range(5):
            event_logger.emit_claim_received(
                f"CLAIM-{i}", f"VEH-{i}", f"CUST-{i}", "scratch"
            )

        events = event_logger.get_recent_events(limit=10)

        assert len(events) == 5
        # Should be in reverse chronological order (most recent first)
        assert events[0]["claim_id"] == "CLAIM-4"

    def test_get_recent_events_respects_limit(self, event_logger):
        """Should respect limit parameter."""
        for i in range(10):
            event_logger.emit_claim_received(
                f"CLAIM-{i}", f"VEH-{i}", f"CUST-{i}", "scratch"
            )

        events = event_logger.get_recent_events(limit=5)

        assert len(events) == 5


class TestEventOrdering:
    """Test event ordering."""

    def test_claim_events_ordered_chronologically(self, event_logger):
        """Events for a claim should be in chronological order."""
        event_logger.emit_claim_received("CLAIM-008", "VEH-001", "CUST-001", "scratch")
        event_logger.emit_cost_estimated("CLAIM-008", 500.0, 300.0, 200.0)
        event_logger.emit_approval_required("CLAIM-008", "High cost", ["high_cost"])
        event_logger.emit_claim_approved("CLAIM-008", "REV-001", "OK")

        events = event_logger.get_events_for_claim("CLAIM-008")

        assert len(events) == 4
        assert events[0]["event_type"] == "ClaimReceived"
        assert events[1]["event_type"] == "CostEstimated"
        assert events[2]["event_type"] == "ApprovalRequired"
        assert events[3]["event_type"] == "ClaimApproved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
