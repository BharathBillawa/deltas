"""
Unit tests for PatternRecognitionService.

Tests pattern detection and risk scoring.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, VehicleDB, DamageDB, CustomerDB
from src.services.pattern_recognition_service import PatternRecognitionService


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
def pattern_service(db_session):
    """Create pattern service."""
    return PatternRecognitionService(db_session)


class TestPatternRecognitionService:
    """Test pattern recognition functionality."""

    def test_no_patterns_for_clean_vehicle(self, pattern_service, db_session):
        """Clean vehicle should have no patterns."""
        vehicle = VehicleDB(
            vehicle_id="TEST-001",
            category="Economy",
            make="VW",
            model="Golf",
            year=2022,
            purchase_date=datetime(2022, 1, 1),
            purchase_price_eur=18000.0,
            current_mileage_km=50000
        )
        db_session.add(vehicle)
        db_session.commit()

        patterns = pattern_service.analyze_vehicle_patterns("TEST-001")
        assert len(patterns) == 0

    def test_frequent_damage_detection(self, pattern_service, db_session):
        """Should detect frequent damage pattern."""
        vehicle = VehicleDB(
            vehicle_id="TEST-002",
            category="Economy",
            make="VW",
            model="Golf",
            year=2022,
            purchase_date=datetime(2022, 1, 1),
            purchase_price_eur=18000.0,
            current_mileage_km=50000
        )
        db_session.add(vehicle)

        # Add 3 damages in 75 days
        for i in range(3):
            damage = DamageDB(
                vehicle_id="TEST-002",
                date=datetime.now() - timedelta(days=i*25),
                damage_type="scratch",
                severity="minor",
                location="bumper",
                description="Test damage",
                repair_cost_eur=150.0,
                status="repaired"
            )
            db_session.add(damage)
        db_session.commit()

        patterns = pattern_service.analyze_vehicle_patterns("TEST-002")
        assert len(patterns) >= 1
        assert any(p.pattern_type == "frequent_damage" for p in patterns)

    def test_customer_risk_new_customer(self, pattern_service, db_session):
        """New customer should have neutral risk profile."""
        customer = CustomerDB(
            customer_id="TEST-CUST-001",
            customer_name="Test User",
            total_rentals=1
        )
        db_session.add(customer)
        db_session.commit()

        profile = pattern_service.analyze_customer_risk("TEST-CUST-001")
        assert profile.risk_score == 0.0
        assert not profile.is_high_risk
        assert profile.damages_reported == 0

    def test_customer_risk_with_damages(self, pattern_service, db_session):
        """Customer with damages should have calculated risk."""
        customer = CustomerDB(
            customer_id="TEST-CUST-002",
            customer_name="Test User 2",
            total_rentals=20
        )
        db_session.add(customer)

        # Add 2 damages
        for i in range(2):
            damage = DamageDB(
                vehicle_id=f"VEH-{i}",
                date=datetime.now() - timedelta(days=i*100),
                damage_type="scratch",
                severity="minor",
                location="door",
                description="Customer damage",
                repair_cost_eur=300.0,
                rental_return_location="Munich_Airport",
                customer_id="TEST-CUST-002",
                status="repaired"
            )
            db_session.add(damage)
        db_session.commit()

        profile = pattern_service.analyze_customer_risk("TEST-CUST-002")
        assert profile.damages_reported == 2
        assert profile.risk_score > 0.0
        assert profile.total_rentals == 20

    def test_vehicle_health_score(self, pattern_service, db_session):
        """Should return vehicle health score."""
        vehicle = VehicleDB(
            vehicle_id="TEST-003",
            category="Standard",
            make="BMW",
            model="320i",
            year=2020,
            purchase_date=datetime(2020, 1, 1),
            purchase_price_eur=38000.0,
            current_mileage_km=125000,
            health_score=8.5
        )
        db_session.add(vehicle)
        db_session.commit()

        score, status = pattern_service.get_vehicle_health_score("TEST-003")
        assert score == 8.5
        assert status == "excellent"

    def test_unknown_vehicle(self, pattern_service):
        """Unknown vehicle should return empty patterns."""
        patterns = pattern_service.analyze_vehicle_patterns("UNKNOWN")
        assert len(patterns) == 0

    def test_unknown_customer(self, pattern_service):
        """Unknown customer should return neutral profile."""
        profile = pattern_service.analyze_customer_risk("UNKNOWN")
        assert profile.risk_score == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
