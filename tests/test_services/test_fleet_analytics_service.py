"""
Unit tests for FleetAnalyticsService.

Tests aggregate fleet analytics and retirement analysis.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, VehicleDB, DamageDB
from src.services.fleet_analytics_service import FleetAnalyticsService


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
def analytics_service(db_session):
    """Create analytics service."""
    return FleetAnalyticsService(db_session)


@pytest.fixture
def sample_fleet(db_session):
    """Create sample fleet with varying health scores."""
    vehicles = [
        VehicleDB(
            vehicle_id="VEH-001",
            category="Economy",
            make="VW",
            model="Polo",
            year=2022,
            purchase_date=datetime(2022, 1, 1),
            purchase_price_eur=15000.0,
            current_mileage_km=30000,
            health_score=9.0,
            cumulative_damage_ytd_eur=100.0
        ),
        VehicleDB(
            vehicle_id="VEH-002",
            category="Standard",
            make="BMW",
            model="320i",
            year=2020,
            purchase_date=datetime(2020, 1, 1),
            purchase_price_eur=35000.0,
            current_mileage_km=80000,
            health_score=7.0,
            cumulative_damage_ytd_eur=800.0
        ),
        VehicleDB(
            vehicle_id="VEH-003",
            category="Luxury",
            make="Mercedes",
            model="E-Class",
            year=2018,
            purchase_date=datetime(2018, 1, 1),
            purchase_price_eur=50000.0,
            current_mileage_km=150000,
            health_score=4.0,
            cumulative_damage_ytd_eur=2800.0
        ),
        VehicleDB(
            vehicle_id="VEH-004",
            category="Economy",
            make="Ford",
            model="Fiesta",
            year=2023,
            purchase_date=datetime(2023, 1, 1),
            purchase_price_eur=16000.0,
            current_mileage_km=15000,
            health_score=5.5,
            cumulative_damage_ytd_eur=500.0
        )
    ]
    for v in vehicles:
        db_session.add(v)
    db_session.commit()
    return vehicles


class TestFleetHealthSummary:
    """Test fleet health summary."""

    def test_empty_fleet(self, analytics_service):
        """Empty fleet should return zeros."""
        summary = analytics_service.get_fleet_health_summary()

        assert summary["total_vehicles"] == 0
        assert summary["avg_health_score"] == 0.0
        assert len(summary["vehicles_needing_attention"]) == 0

    def test_fleet_health_distribution(self, analytics_service, sample_fleet):
        """Should categorize vehicles by health score."""
        summary = analytics_service.get_fleet_health_summary()

        assert summary["total_vehicles"] == 4
        assert summary["health_distribution"]["excellent"]["count"] == 1  # 9.0
        assert summary["health_distribution"]["good"]["count"] == 1  # 7.0
        assert summary["health_distribution"]["fair"]["count"] == 2  # 5.5, 4.0

    def test_vehicles_needing_attention(self, analytics_service, sample_fleet):
        """Should identify vehicles with health < 6."""
        summary = analytics_service.get_fleet_health_summary()

        needs_attention = summary["vehicles_needing_attention"]
        assert len(needs_attention) == 2  # VEH-003 (4.0), VEH-004 (5.5)

        vehicle_ids = [v["vehicle_id"] for v in needs_attention]
        assert "VEH-003" in vehicle_ids
        assert "VEH-004" in vehicle_ids


class TestLocationRiskAnalysis:
    """Test location risk analysis."""

    def test_no_damages(self, analytics_service):
        """No damages should return empty list."""
        locations = analytics_service.get_location_risk_analysis()
        assert len(locations) == 0

    def test_location_grouping(self, analytics_service, db_session):
        """Should group damages by location."""
        # Add damages at different locations
        for i in range(3):
            damage = DamageDB(
                vehicle_id="VEH-001",
                date=datetime.now() - timedelta(days=i*30),
                damage_type="scratch",
                severity="minor",
                location="bumper",
                description="Test damage",
                repair_cost_eur=200.0,
                rental_return_location="Munich_Airport",
                status="repaired"
            )
            db_session.add(damage)

        damage = DamageDB(
            vehicle_id="VEH-002",
            date=datetime.now(),
            damage_type="dent",
            severity="minor",
            location="door",
            description="Test damage",
            repair_cost_eur=300.0,
            rental_return_location="Berlin_Airport",
            status="repaired"
        )
        db_session.add(damage)
        db_session.commit()

        locations = analytics_service.get_location_risk_analysis()

        assert len(locations) == 2
        assert locations[0]["location"] == "Munich_Airport"  # Sorted by count
        assert locations[0]["damage_count"] == 3
        assert locations[1]["location"] == "Berlin_Airport"
        assert locations[1]["damage_count"] == 1


class TestCostAggregations:
    """Test cost aggregations."""

    def test_no_damages(self, analytics_service):
        """No damages should return zero costs."""
        costs = analytics_service.get_cost_aggregations()

        assert costs["total_cost_eur"] == 0.0
        assert costs["damage_count"] == 0
        assert costs["avg_cost_per_damage"] == 0.0

    def test_cost_calculation(self, analytics_service, db_session):
        """Should calculate total and average costs."""
        damages = [
            DamageDB(
                vehicle_id="VEH-001",
                date=datetime.now() - timedelta(days=30),
                damage_type="scratch",
                severity="minor",
                location="bumper",
                description="Test",
                repair_cost_eur=150.0,
                status="repaired"
            ),
            DamageDB(
                vehicle_id="VEH-002",
                date=datetime.now() - timedelta(days=60),
                damage_type="dent",
                severity="medium",
                location="door",
                description="Test",
                repair_cost_eur=450.0,
                status="repaired"
            )
        ]
        for d in damages:
            db_session.add(d)
        db_session.commit()

        costs = analytics_service.get_cost_aggregations()

        assert costs["total_cost_eur"] == 600.0
        assert costs["damage_count"] == 2
        assert costs["avg_cost_per_damage"] == 300.0


class TestRetirementCandidates:
    """Test retirement candidate identification."""

    def test_no_candidates(self, analytics_service, db_session):
        """Healthy vehicles should not be candidates."""
        vehicle = VehicleDB(
            vehicle_id="VEH-100",
            category="Economy",
            make="VW",
            model="Golf",
            year=2023,
            purchase_date=datetime(2023, 1, 1),
            purchase_price_eur=20000.0,
            current_mileage_km=10000,
            health_score=9.0,
            cumulative_damage_ytd_eur=100.0
        )
        db_session.add(vehicle)
        db_session.commit()

        candidates = analytics_service.get_retirement_candidates()
        assert len(candidates) == 0

    def test_low_health_candidate(self, analytics_service, db_session):
        """Low health should flag for retirement."""
        vehicle = VehicleDB(
            vehicle_id="VEH-101",
            category="Economy",
            make="VW",
            model="Golf",
            year=2020,
            purchase_date=datetime(2020, 1, 1),
            purchase_price_eur=20000.0,
            current_mileage_km=100000,
            health_score=3.5,
            cumulative_damage_ytd_eur=800.0
        )
        db_session.add(vehicle)
        db_session.commit()

        candidates = analytics_service.get_retirement_candidates()

        assert len(candidates) == 1
        assert candidates[0]["vehicle_id"] == "VEH-101"
        assert "Low health score" in candidates[0]["retirement_reasons"]

    def test_high_cost_candidate(self, analytics_service, db_session):
        """High cumulative cost should flag for retirement."""
        vehicle = VehicleDB(
            vehicle_id="VEH-102",
            category="Standard",
            make="BMW",
            model="320i",
            year=2021,
            purchase_date=datetime(2021, 1, 1),
            purchase_price_eur=35000.0,
            current_mileage_km=60000,
            health_score=6.5,
            cumulative_damage_ytd_eur=3000.0
        )
        db_session.add(vehicle)
        db_session.commit()

        candidates = analytics_service.get_retirement_candidates()

        assert len(candidates) == 1
        assert candidates[0]["vehicle_id"] == "VEH-102"
        assert "High cumulative damage cost" in candidates[0]["retirement_reasons"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
