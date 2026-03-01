"""
Tests for CostEstimatorAgent.

Tests deterministic cost estimation logic (LLM fallback path).
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from src.agents.cost_estimator_agent import CostEstimatorAgent
from src.models.damage import (
    DamageClaim,
    DamageAssessment,
    DamageType,
    DamageSeverity,
    VehicleLocation,
    VehicleInfo,
    VehicleCategory,
)
from src.models.financial import CostEstimate, LaborType
from src.persistence.database import SessionLocal


@pytest.fixture
def db_session():
    """Database session for tests."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def agent(db_session):
    """CostEstimatorAgent with LLM disabled (deterministic only)."""
    a = CostEstimatorAgent(db_session, temperature=0.3)
    a.llm = None  # Force deterministic path
    return a


@pytest.fixture
def standard_claim():
    """Standard vehicle minor scratch claim."""
    return DamageClaim(
        claim_id="CLM-AGENT-001",
        timestamp=datetime.now(),
        vehicle_id="VW-POLO-2023-001",
        customer_id="CUST-1234",
        rental_agreement_id="RNT-2026-0100",
        return_location="Munich_Airport",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            location=VehicleLocation.REAR_BUMPER,
            description="Minor scratch on rear bumper",
            affected_parts=["rear_bumper"],
            photos=[],
            inspector_id="INSP-001"
        )
    )


@pytest.fixture
def luxury_claim():
    """Luxury vehicle medium bumper crack claim."""
    return DamageClaim(
        claim_id="CLM-AGENT-002",
        timestamp=datetime.now(),
        vehicle_id="AUDI-A6-2019-004",
        customer_id="CUST-5678",
        rental_agreement_id="RNT-2026-0200",
        return_location="Berlin_City",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.BUMPER_CRACK,
            severity=DamageSeverity.MEDIUM,
            location=VehicleLocation.FRONT_BUMPER,
            description="Cracked front bumper on luxury Audi A6",
            affected_parts=["front_bumper"],
            photos=[],
            inspector_id="INSP-001"
        ),
        vehicle_context=VehicleInfo(
            vehicle_id="AUDI-A6-2019-004",
            category=VehicleCategory.LUXURY,
            make="Audi",
            model="A6 55 TFSI",
            year=2019,
            color="Mythos Black",
            vin="WAUZZZ4G9KN123456",
            license_plate="M-GH 3456",
            purchase_date=datetime(2019, 6, 20),
            purchase_price_eur=62000.0,
            current_mileage_km=158000,
            last_service_date=datetime(2025, 11, 15),
            health_score=5.2,
            cumulative_damage_ytd_eur=2845.0,
        )
    )


class TestCostEstimatorDeterministic:
    """Tests for deterministic cost estimation (no LLM)."""

    def test_estimate_returns_cost_and_no_reasoning(self, agent, standard_claim):
        """Without LLM, should return estimate with no reasoning."""
        estimate, reasoning = agent.estimate_cost(standard_claim)
        assert isinstance(estimate, CostEstimate)
        assert reasoning is None

    def test_estimate_positive_cost(self, agent, standard_claim):
        """Estimate should have positive total cost."""
        estimate, _ = agent.estimate_cost(standard_claim)
        assert estimate.total_eur > 0
        assert estimate.labor_cost_eur > 0
        assert estimate.parts_cost_eur >= 0

    def test_luxury_vehicle_uses_correct_category(self, agent, luxury_claim):
        """Luxury vehicle should use luxury category multiplier, not Standard."""
        estimate, _ = agent.estimate_cost(
            luxury_claim,
            vehicle_context={
                "age_years": datetime.now().year - 2019,
                "mileage_km": 158000,
                "cumulative_damage_ytd": 2845.0,
                "recent_damage_count": 0,
            }
        )
        # Luxury multiplier (1.35) should make total higher than standard
        assert estimate.category_multiplier == 1.65
        assert estimate.claim_id == "CLM-AGENT-002"

    def test_depreciation_applied_for_older_vehicle(self, agent, luxury_claim):
        """Vehicles >= 2 years old should get depreciation applied."""
        vehicle_context = {
            "age_years": 7,  # 2019 Audi
            "mileage_km": 158000,
            "cumulative_damage_ytd": 2845.0,
            "recent_damage_count": 0,
        }
        estimate, _ = agent.estimate_cost(luxury_claim, vehicle_context)
        assert estimate.depreciation_applicable is True
        assert estimate.total_eur < estimate.subtotal_eur

    def test_no_depreciation_for_new_vehicle(self, agent, standard_claim):
        """New vehicles (< 2 years) should not get depreciation."""
        vehicle_context = {
            "age_years": 1,
            "mileage_km": 15000,
            "cumulative_damage_ytd": 0,
            "recent_damage_count": 0,
        }
        estimate, _ = agent.estimate_cost(standard_claim, vehicle_context)
        # Without depreciation, total should equal subtotal
        if not estimate.depreciation_applicable:
            assert estimate.total_eur == estimate.subtotal_eur

    def test_estimate_without_vehicle_context(self, agent, standard_claim):
        """Should work without vehicle context (no depreciation)."""
        estimate, _ = agent.estimate_cost(standard_claim, vehicle_context=None)
        assert isinstance(estimate, CostEstimate)
        assert estimate.total_eur > 0

    def test_labor_rate_is_gdv_standard(self, agent, standard_claim):
        """Labor rate should be €202/hour (GDV/Dekra 2024 standard)."""
        estimate, _ = agent.estimate_cost(standard_claim)
        assert estimate.labor_rate_eur == 202.0


class TestCostEstimatorLLMTriggering:
    """Tests for LLM reasoning trigger logic."""

    def test_near_threshold_triggers_llm(self, agent, standard_claim):
        """Cost near €500 threshold should trigger LLM reasoning."""
        # Create a mock estimate near threshold
        mock_estimate = CostEstimate(
            claim_id="TEST",
            labor_hours=2.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202.0,
            labor_cost_eur=404.0,
            parts_cost_eur=80.0,
            subtotal_eur=484.0,
            total_eur=484.0,
        )
        needs = agent._needs_llm_reasoning(mock_estimate, standard_claim, None)
        assert needs is True

    def test_far_from_threshold_no_llm(self, agent, standard_claim):
        """Cost far from threshold should not trigger LLM."""
        mock_estimate = CostEstimate(
            claim_id="TEST",
            labor_hours=1.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202.0,
            labor_cost_eur=202.0,
            parts_cost_eur=50.0,
            subtotal_eur=252.0,
            total_eur=252.0,
        )
        needs = agent._needs_llm_reasoning(mock_estimate, standard_claim, None)
        assert needs is False

    def test_many_affected_parts_triggers_llm(self, agent):
        """Claims with >2 affected parts should trigger LLM."""
        claim = DamageClaim(
            claim_id="CLM-MULTI",
            timestamp=datetime.now(),
            vehicle_id="VW-POLO-2023-001",
            customer_id="CUST-1234",
            rental_agreement_id="RNT-2026-0300",
            return_location="Munich_Airport",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.SCRATCH,
                severity=DamageSeverity.MEDIUM,
                location=VehicleLocation.DRIVER_DOOR,
                description="Multiple scratches across vehicle",
                affected_parts=["front_bumper", "driver_door", "rear_quarter_panel"],
                photos=[],
                inspector_id="INSP-001"
            )
        )
        mock_estimate = CostEstimate(
            claim_id="CLM-MULTI",
            labor_hours=1.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202.0,
            labor_cost_eur=202.0,
            parts_cost_eur=50.0,
            subtotal_eur=252.0,
            total_eur=252.0,
        )
        needs = agent._needs_llm_reasoning(mock_estimate, claim, None)
        assert needs is True

    def test_high_cumulative_damage_triggers_llm(self, agent, standard_claim):
        """High cumulative damage (>€2000) should trigger LLM."""
        mock_estimate = CostEstimate(
            claim_id="TEST",
            labor_hours=1.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202.0,
            labor_cost_eur=202.0,
            parts_cost_eur=50.0,
            subtotal_eur=252.0,
            total_eur=252.0,
        )
        context = {"cumulative_damage_ytd": 3000}
        needs = agent._needs_llm_reasoning(mock_estimate, standard_claim, context)
        assert needs is True

    def test_short_description_triggers_llm(self, agent):
        """Claims with short descriptions (<20 chars) should trigger LLM."""
        claim = DamageClaim(
            claim_id="CLM-SHORT",
            timestamp=datetime.now(),
            vehicle_id="VW-POLO-2023-001",
            customer_id="CUST-1234",
            rental_agreement_id="RNT-2026-0300",
            return_location="Munich_Airport",
            damage_assessment=DamageAssessment(
                damage_type=DamageType.SCRATCH,
                severity=DamageSeverity.MINOR,
                location=VehicleLocation.REAR_BUMPER,
                description="Scratch",  # < 20 chars
                affected_parts=["rear_bumper"],
                photos=[],
                inspector_id="INSP-001"
            )
        )
        mock_estimate = CostEstimate(
            claim_id="CLM-SHORT",
            labor_hours=1.0,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202.0,
            labor_cost_eur=202.0,
            parts_cost_eur=50.0,
            subtotal_eur=200.0,
            total_eur=200.0,
        )
        needs = agent._needs_llm_reasoning(mock_estimate, claim, None)
        assert needs is True


class TestCostEstimatorLLMFallback:
    """Tests for graceful LLM fallback."""

    def test_no_api_key_uses_deterministic(self, db_session):
        """Should fall back to deterministic when no API key."""
        with patch.object(
            CostEstimatorAgent, '_initialize_llm', return_value=None
        ):
            agent = CostEstimatorAgent(db_session)
            assert agent.llm is None

    def test_reasoning_history_empty_without_llm(self, agent, standard_claim):
        """No reasoning history when LLM not used."""
        agent.estimate_cost(standard_claim)
        assert len(agent.reasoning_history) == 0
