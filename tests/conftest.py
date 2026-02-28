"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_claim_data():
    """Sample damage claim data for testing."""
    return {
        "claim_id": "TEST-001",
        "vehicle_id": "VW-GOLF-2024",
        "damage_type": "scratch",
        "severity": "minor",
        "location": "rear_bumper",
        "estimated_cost": 180.0,
    }
