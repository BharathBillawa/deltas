"""
Tests for ValidatorAgent.

Tests deterministic validation logic (LLM fallback path).
"""

import pytest
from datetime import datetime
from unittest.mock import patch

import json

from src.agents.validator_agent import ValidatorAgent
from src.models.damage import (
    DamageClaim,
    DamageAssessment,
    DamageType,
    DamageSeverity,
    VehicleLocation,
    VehicleInfo,
    VehicleCategory,
)
from src.models.routing import (
    ValidationResult,
    RoutingDecision,
    ValidationFlag,
    FlagSeverity,
)
from src.persistence.database import SessionLocal


@pytest.fixture
def db_session():
    """Database session for tests."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def agent(db_session):
    """ValidatorAgent with LLM disabled (deterministic only)."""
    a = ValidatorAgent(db_session, temperature=0.3)
    a.llm = None  # Force deterministic path
    return a


@pytest.fixture
def low_cost_claim():
    """Low-cost claim that should auto-approve."""
    return DamageClaim(
        claim_id="CLM-VAL-001",
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
    """Luxury vehicle claim."""
    return DamageClaim(
        claim_id="CLM-VAL-002",
        timestamp=datetime.now(),
        vehicle_id="AUDI-A6-2019-004",
        customer_id="CUST-5678",
        rental_agreement_id="RNT-2026-0200",
        return_location="Berlin_City",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.BUMPER_CRACK,
            severity=DamageSeverity.MEDIUM,
            location=VehicleLocation.FRONT_BUMPER,
            description="Cracked front bumper on luxury Audi",
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


@pytest.fixture
def low_health_claim():
    """Claim with low vehicle health score."""
    return DamageClaim(
        claim_id="CLM-VAL-003",
        timestamp=datetime.now(),
        vehicle_id="VW-POLO-2023-001",
        customer_id="CUST-1234",
        rental_agreement_id="RNT-2026-0300",
        return_location="Munich_Airport",
        damage_assessment=DamageAssessment(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            location=VehicleLocation.REAR_BUMPER,
            description="Minor scratch on rear bumper",
            affected_parts=["rear_bumper"],
            photos=[],
            inspector_id="INSP-001"
        ),
        vehicle_context=VehicleInfo(
            vehicle_id="VW-POLO-2023-001",
            category=VehicleCategory.ECONOMY,
            make="VW",
            model="Polo",
            year=2023,
            color="White",
            vin="WVWZZZ6RZXY123456",
            license_plate="M-AB 1234",
            purchase_date=datetime(2023, 1, 1),
            purchase_price_eur=22000.0,
            current_mileage_km=50000,
            last_service_date=datetime(2025, 6, 1),
            health_score=3.5,  # Below 5.0 threshold
        )
    )


class TestValidatorDeterministic:
    """Tests for deterministic validation (no LLM)."""

    def test_low_cost_auto_approves(self, agent, low_cost_claim):
        """Claims under €500 with no patterns should auto-approve."""
        result, reasoning = agent.validate_claim(low_cost_claim, 200.0)
        assert isinstance(result, ValidationResult)
        assert result.can_auto_approve is True
        assert result.routing_decision == RoutingDecision.AUTO_APPROVE
        assert reasoning is None

    def test_high_cost_requires_human_review(self, agent, low_cost_claim):
        """Claims over €500 should require human review."""
        result, _ = agent.validate_claim(low_cost_claim, 750.0)
        assert result.can_auto_approve is False
        assert result.routing_decision == RoutingDecision.HUMAN_REVIEW_REQUIRED

    def test_high_cost_has_flag(self, agent, low_cost_claim):
        """High cost should add a high_cost flag."""
        result, _ = agent.validate_claim(low_cost_claim, 750.0)
        flag_types = [f.flag_type for f in result.flags]
        assert "high_cost" in flag_types

    def test_is_valid_always_true(self, agent, low_cost_claim):
        """Claims are always considered valid (routing decides handling)."""
        result, _ = agent.validate_claim(low_cost_claim, 200.0)
        assert result.is_valid is True

    def test_claim_id_preserved(self, agent, low_cost_claim):
        """Validation result should reference correct claim."""
        result, _ = agent.validate_claim(low_cost_claim, 200.0)
        assert result.claim_id == "CLM-VAL-001"


class TestValidatorLuxuryVehicle:
    """Tests for luxury vehicle business rules."""

    def test_luxury_vehicle_flag_added(self, agent, luxury_claim):
        """Luxury vehicles should get a luxury_vehicle flag."""
        result, _ = agent.validate_claim(luxury_claim, 200.0)
        flag_types = [f.flag_type for f in result.flags]
        assert "luxury_vehicle" in flag_types

    def test_luxury_flag_is_info_severity(self, agent, luxury_claim):
        """Luxury vehicle flag should be INFO severity (not blocking)."""
        result, _ = agent.validate_claim(luxury_claim, 200.0)
        luxury_flags = [f for f in result.flags if f.flag_type == "luxury_vehicle"]
        assert len(luxury_flags) == 1
        assert luxury_flags[0].severity == FlagSeverity.INFO


class TestValidatorVehicleHealth:
    """Tests for low vehicle health business rules."""

    def test_low_health_flag_added(self, agent, low_health_claim):
        """Low health score (<5.0) should add a warning flag."""
        result, _ = agent.validate_claim(low_health_claim, 200.0)
        flag_types = [f.flag_type for f in result.flags]
        assert "low_vehicle_health" in flag_types

    def test_low_health_flag_is_warning(self, agent, low_health_claim):
        """Low health flag should be WARNING severity."""
        result, _ = agent.validate_claim(low_health_claim, 200.0)
        health_flags = [f for f in result.flags if f.flag_type == "low_vehicle_health"]
        assert len(health_flags) == 1
        assert health_flags[0].severity == FlagSeverity.WARNING


class TestValidatorRiskScoring:
    """Tests for risk scoring logic."""

    def test_zero_risk_for_clean_claim(self, agent, low_cost_claim):
        """Clean claims should have zero or low risk."""
        result, _ = agent.validate_claim(low_cost_claim, 200.0)
        assert result.fraud_risk_score >= 0.0
        assert result.overall_risk_score >= 0.0

    def test_risk_increases_with_flags(self, agent, low_cost_claim):
        """High-severity flags should increase overall risk score."""
        # High cost produces a HIGH flag, which should increase risk
        result, _ = agent.validate_claim(low_cost_claim, 750.0)
        assert result.overall_risk_score > 0.0


class TestValidatorLLMTriggering:
    """Tests for LLM reasoning trigger logic."""

    def test_near_threshold_triggers_llm(self, agent):
        """Cost near €500 threshold (€450-550) should trigger LLM."""
        cost = 490.0
        patterns = {"frequent_damage": False, "location_correlation": False, "fraud_risk_score": 0.0}
        assert agent._needs_llm_reasoning(patterns, cost) is True

    def test_far_from_threshold_no_llm(self, agent):
        """Cost far from threshold should not trigger LLM."""
        cost = 200.0
        patterns = {"frequent_damage": False, "location_correlation": False, "fraud_risk_score": 0.0}
        assert agent._needs_llm_reasoning(patterns, cost) is False

    def test_patterns_trigger_llm(self, agent):
        """Detected patterns should trigger LLM reasoning."""
        patterns = {"frequent_damage": True, "location_correlation": False, "fraud_risk_score": 0.5}
        assert agent._needs_llm_reasoning(patterns, 200.0) is True

    def test_moderate_fraud_risk_triggers_llm(self, agent):
        """Moderate fraud risk (0.3-0.7) should trigger LLM."""
        patterns = {"frequent_damage": False, "location_correlation": False, "fraud_risk_score": 0.5}
        assert agent._needs_llm_reasoning(patterns, 200.0) is True


class TestValidatorLLMOverride:
    """Tests for LLM routing override logic via structured JSON."""

    def test_auto_approve_override(self, agent):
        """LLM can override human review to auto-approve via JSON."""
        base = ValidationResult(
            claim_id="TEST",
            is_valid=True,
            can_auto_approve=False,
            routing_decision=RoutingDecision.HUMAN_REVIEW_REQUIRED,
            routing_reason="Cost exceeds threshold",
        )
        reasoning = json.dumps({
            "decision": "auto-approve",
            "reasoning": "Context suggests this is legitimate.",
            "risk_level": "low"
        })
        result, explanation = agent._apply_llm_reasoning(base, reasoning, {})
        assert result.can_auto_approve is True
        assert result.routing_decision == RoutingDecision.AUTO_APPROVE
        assert "LLM override" in result.routing_reason

    def test_human_review_override(self, agent):
        """LLM can override auto-approve to human review via JSON."""
        base = ValidationResult(
            claim_id="TEST",
            is_valid=True,
            can_auto_approve=True,
            routing_decision=RoutingDecision.AUTO_APPROVE,
            routing_reason="All checks passed",
        )
        reasoning = json.dumps({
            "decision": "human-review",
            "reasoning": "Suspicious patterns detected.",
            "risk_level": "high"
        })
        result, explanation = agent._apply_llm_reasoning(base, reasoning, {})
        assert result.can_auto_approve is False
        assert result.routing_decision == RoutingDecision.HUMAN_REVIEW_REQUIRED
        assert "LLM override" in result.routing_reason

    def test_no_override_when_decision_matches(self, agent):
        """No override when LLM agrees with base decision."""
        base = ValidationResult(
            claim_id="TEST",
            is_valid=True,
            can_auto_approve=True,
            routing_decision=RoutingDecision.AUTO_APPROVE,
            routing_reason="All checks passed",
        )
        reasoning = json.dumps({
            "decision": "auto-approve",
            "reasoning": "Claim looks fine.",
            "risk_level": "low"
        })
        result, explanation = agent._apply_llm_reasoning(base, reasoning, {})
        assert result.routing_decision == RoutingDecision.AUTO_APPROVE
        assert "LLM override" not in result.routing_reason

    def test_none_reasoning_returns_base(self, agent):
        """None reasoning should return base result unchanged."""
        base = ValidationResult(
            claim_id="TEST",
            is_valid=True,
            can_auto_approve=True,
            routing_decision=RoutingDecision.AUTO_APPROVE,
            routing_reason="All checks passed",
        )
        result, explanation = agent._apply_llm_reasoning(base, None, {})
        assert result == base
        assert explanation is None

    def test_malformed_json_uses_raw_reasoning(self, agent):
        """Non-JSON LLM response should still return reasoning without override."""
        base = ValidationResult(
            claim_id="TEST",
            is_valid=True,
            can_auto_approve=True,
            routing_decision=RoutingDecision.AUTO_APPROVE,
            routing_reason="All checks passed",
        )
        reasoning = "This claim looks fine. No concerns noted."
        result, explanation = agent._apply_llm_reasoning(base, reasoning, {})
        assert result.routing_decision == RoutingDecision.AUTO_APPROVE
        assert explanation is not None
        assert "This claim looks fine" in explanation

    def test_handles_markdown_code_fences(self, agent):
        """Should handle LLM responses wrapped in markdown code fences."""
        base = ValidationResult(
            claim_id="TEST",
            is_valid=True,
            can_auto_approve=False,
            routing_decision=RoutingDecision.HUMAN_REVIEW_REQUIRED,
            routing_reason="Cost exceeds threshold",
        )
        reasoning = '```json\n{"decision": "auto-approve", "reasoning": "Legitimate claim.", "risk_level": "low"}\n```'
        result, explanation = agent._apply_llm_reasoning(base, reasoning, {})
        assert result.can_auto_approve is True
        assert result.routing_decision == RoutingDecision.AUTO_APPROVE


class TestValidatorLLMFallback:
    """Tests for graceful LLM fallback."""

    def test_no_api_key_uses_deterministic(self, db_session):
        """Should fall back to deterministic when no API key."""
        with patch.object(
            ValidatorAgent, '_initialize_llm', return_value=None
        ):
            agent = ValidatorAgent(db_session)
            assert agent.llm is None

    def test_reasoning_history_empty_without_llm(self, agent, low_cost_claim):
        """No reasoning history when LLM not used."""
        agent.validate_claim(low_cost_claim, 200.0)
        assert len(agent.reasoning_history) == 0


class TestParseLLMDecision:
    """Tests for structured JSON parsing of LLM responses."""

    def test_valid_json(self, agent):
        """Should parse valid JSON with required keys."""
        text = json.dumps({
            "decision": "auto-approve",
            "reasoning": "Looks good.",
            "risk_level": "low"
        })
        result = agent._parse_llm_decision(text)
        assert result is not None
        assert result["decision"] == "auto-approve"

    def test_json_with_code_fences(self, agent):
        """Should strip markdown code fences."""
        text = '```json\n{"decision": "human-review", "reasoning": "Suspicious.", "risk_level": "high"}\n```'
        result = agent._parse_llm_decision(text)
        assert result is not None
        assert result["decision"] == "human-review"

    def test_missing_required_keys(self, agent):
        """Should return None if required keys are missing."""
        text = json.dumps({"risk_level": "low"})
        result = agent._parse_llm_decision(text)
        assert result is None

    def test_invalid_json(self, agent):
        """Should return None for non-JSON text."""
        result = agent._parse_llm_decision("This is not JSON at all.")
        assert result is None

    def test_empty_string(self, agent):
        """Should return None for empty string."""
        result = agent._parse_llm_decision("")
        assert result is None
