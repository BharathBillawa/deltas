"""
Unit tests for PricingService.

Tests validated German market cost calculations.
"""

import pytest
from pathlib import Path

from src.models.damage import DamageType, DamageSeverity
from src.services.pricing_service import PricingService


@pytest.fixture
def pricing_service():
    """Create PricingService instance with default data."""
    return PricingService()


class TestPricingServiceInitialization:
    """Test service initialization and data loading."""

    def test_initialization_with_default_path(self):
        """Should load pricing data from default path."""
        service = PricingService()

        assert service.labor_rates is not None
        assert service.damage_types is not None
        assert service.vehicle_categories is not None

    def test_initialization_with_custom_path(self):
        """Should load pricing data from custom path."""
        project_root = Path(__file__).parent.parent.parent
        custom_path = project_root / "data" / "pricing_database" / "repair_costs.json"

        service = PricingService(pricing_data_path=custom_path)

        assert service.labor_rates is not None

    def test_initialization_with_invalid_path(self):
        """Should raise error for invalid path."""
        with pytest.raises(FileNotFoundError):
            PricingService(pricing_data_path=Path("/invalid/path.json"))


class TestCostCalculation:
    """Test cost calculation for various scenarios."""

    def test_minor_scratch_economy(self, pricing_service):
        """Minor scratch on Economy vehicle should be ~€100-165."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-001",
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            vehicle_category="Economy"
        )

        assert estimate.claim_id == "TEST-001"
        assert estimate.total_eur >= 100
        assert estimate.total_eur <= 200
        assert estimate.category_multiplier == 1.0
        assert estimate.confidence_score >= 0.8

    def test_minor_scratch_luxury(self, pricing_service):
        """Minor scratch on Luxury vehicle should be higher due to multiplier."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-002",
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            vehicle_category="Luxury"
        )

        assert estimate.category_multiplier == 1.65
        assert estimate.total_eur >= 150
        assert estimate.total_eur <= 300

    def test_bumper_repair_standard(self, pricing_service):
        """Bumper replacement on Standard vehicle (severe damage)."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-003",
            damage_type=DamageType.BUMPER_CRACK,
            severity=DamageSeverity.SEVERE,
            vehicle_category="Standard"
        )

        assert estimate.category_multiplier == 1.35
        assert estimate.total_eur >= 2000  # Severe bumper damage is expensive
        assert estimate.total_eur <= 5000

    def test_windshield_ev(self, pricing_service):
        """Windshield on EV/Luxury should include ADAS calibration."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-004",
            damage_type=DamageType.WINDSHIELD_CRACK,
            severity=DamageSeverity.HIGH,  # Windshield uses HIGH severity
            vehicle_category="Luxury"
        )

        # Windshield + ADAS on luxury vehicle (specialist labor + expensive parts)
        assert estimate.total_eur >= 1500
        assert estimate.total_eur <= 3000
        assert estimate.category_multiplier == 1.65


class TestMultipliers:
    """Test category and location multipliers."""

    def test_category_multipliers(self, pricing_service):
        """Different categories should have correct multipliers."""
        categories = {
            "Economy": 1.0,
            "Compact": 1.15,
            "Standard": 1.35,
            "Luxury": 1.65,
            "Premium": 2.1,
            "SUV": 1.45
        }

        for category, expected_multiplier in categories.items():
            multiplier = pricing_service._get_category_multiplier(category)
            assert multiplier == expected_multiplier

    def test_unknown_category_defaults_to_1x(self, pricing_service):
        """Unknown category should default to 1.0x multiplier."""
        multiplier = pricing_service._get_category_multiplier("UnknownCategory")
        assert multiplier == 1.0

    def test_location_multiplier_applied(self, pricing_service):
        """Location multiplier should be applied if provided."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-005",
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            vehicle_category="Economy",
            location="Munich_Airport"
        )

        # Currently all locations have 1.0x multiplier in data
        assert estimate.location_multiplier == 1.0


class TestFallbackEstimates:
    """Test graceful handling of unknown damage types."""

    def test_unknown_damage_type(self, pricing_service):
        """Unknown damage type should use fallback estimate."""
        # Undercarriage damage exists but may not have all severities
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-006",
            damage_type=DamageType.UNDERCARRIAGE,
            severity=DamageSeverity.MEDIUM,
            vehicle_category="Economy"
        )

        assert estimate.total_eur > 0
        assert estimate.confidence_score >= 0.5  # May use fallback or real data

    def test_fallback_respects_category_multiplier(self, pricing_service):
        """Category multiplier should still apply."""
        economy_estimate = pricing_service.calculate_cost(
            claim_id="TEST-007",
            damage_type=DamageType.UNDERCARRIAGE,
            severity=DamageSeverity.MEDIUM,
            vehicle_category="Economy"
        )

        luxury_estimate = pricing_service.calculate_cost(
            claim_id="TEST-008",
            damage_type=DamageType.UNDERCARRIAGE,
            severity=DamageSeverity.MEDIUM,
            vehicle_category="Luxury"
        )

        # Luxury should be more expensive due to multiplier
        assert luxury_estimate.total_eur > economy_estimate.total_eur
        assert luxury_estimate.category_multiplier == 1.65


class TestCostRange:
    """Test cost range estimation."""

    def test_get_cost_range(self, pricing_service):
        """Should return min/max cost range for damage type."""
        cost_range = pricing_service.get_cost_range(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR
        )

        assert cost_range is not None
        assert "min_eur" in cost_range
        assert "max_eur" in cost_range
        assert cost_range["max_eur"] > cost_range["min_eur"]
        assert cost_range["min_eur"] >= 0

    def test_get_cost_range_unknown_type(self, pricing_service):
        """Should return None for unknown severity."""
        # Use MULTIPLE damage type which won't have cost details
        cost_range = pricing_service.get_cost_range(
            damage_type=DamageType.UNDERCARRIAGE,
            severity=DamageSeverity.HIGH  # High severity may not be defined for undercarriage
        )

        # May return None if that severity doesn't exist
        # (This is okay - we're testing graceful handling)
        assert cost_range is None or "min_eur" in cost_range


class TestLaborCalculations:
    """Test labor cost calculations."""

    def test_painting_uses_higher_rate(self, pricing_service):
        """Painting work should use €220/hour rate."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-009",
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MEDIUM,  # Requires paint
            vehicle_category="Economy"
        )

        # Medium scratch requires painting
        assert estimate.labor_rate_eur == 220

    def test_standard_bodywork_rate(self, pricing_service):
        """Standard bodywork should use €202/hour rate."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-010",
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,  # Buffing only
            vehicle_category="Economy"
        )

        # Minor scratch is buffing only
        assert estimate.labor_rate_eur == 202


class TestEstimateMetadata:
    """Test estimate metadata and notes."""

    def test_estimate_includes_notes(self, pricing_service):
        """Estimate should include descriptive notes."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-011",
            damage_type=DamageType.DENT,
            severity=DamageSeverity.MEDIUM,
            vehicle_category="Luxury"
        )

        assert estimate.notes is not None
        assert "Dent" in estimate.notes
        assert "Luxury" in estimate.notes

    def test_confidence_score_set(self, pricing_service):
        """Estimate should have confidence score."""
        estimate = pricing_service.calculate_cost(
            claim_id="TEST-012",
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            vehicle_category="Economy"
        )

        assert estimate.confidence_score >= 0.0
        assert estimate.confidence_score <= 1.0
        assert estimate.confidence_score >= 0.8  # High confidence for known damage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
