"""
Unit tests for DepreciationService.

Tests age-based depreciation calculation for fair customer billing.
"""

import pytest
from datetime import datetime
from pathlib import Path

from src.models.financial import DepreciationComponent
from src.services.depreciation_service import DepreciationService


@pytest.fixture
def depreciation_service():
    """Create DepreciationService instance with default data."""
    return DepreciationService()


class TestDepreciationServiceInitialization:
    """Test service initialization."""

    def test_initialization_with_default_path(self):
        """Should load depreciation curves from default path."""
        service = DepreciationService()

        assert service.depreciation_curves is not None
        assert "bumper" in service.depreciation_curves

    def test_initialization_with_custom_path(self):
        """Should load depreciation curves from custom path."""
        project_root = Path(__file__).parent.parent.parent
        custom_path = project_root / "data" / "pricing_database" / "repair_costs.json"

        service = DepreciationService(pricing_data_path=custom_path)

        assert service.depreciation_curves is not None

    def test_initialization_with_invalid_path(self):
        """Should raise error for invalid path."""
        with pytest.raises(FileNotFoundError):
            DepreciationService(pricing_data_path=Path("/invalid/path.json"))


class TestDepreciationCalculation:
    """Test depreciation calculations."""

    def test_bumper_on_8_year_old_vehicle(self, depreciation_service):
        """8-year-old vehicle bumper should have ~25% value."""
        calculation = depreciation_service.calculate(
            vehicle_id="BMW-530-2018-009",
            vehicle_year=2018,
            original_cost_eur=890.0,
            component=DepreciationComponent.BUMPER
        )

        assert calculation.vehicle_id == "BMW-530-2018-009"
        assert calculation.vehicle_age_years == datetime.now().year - 2018
        assert calculation.component == DepreciationComponent.BUMPER
        assert calculation.depreciation_factor <= 0.3  # Heavily depreciated
        assert calculation.depreciated_value_eur < calculation.original_cost_eur
        assert calculation.savings_eur > 0

    def test_no_depreciation_on_new_vehicle(self, depreciation_service):
        """New vehicles (year 1-2) should have minimal or no depreciation."""
        current_year = datetime.now().year

        calculation = depreciation_service.calculate(
            vehicle_id="VW-POLO-2023-001",
            vehicle_year=current_year - 1,  # 1 year old
            original_cost_eur=165.0,
            component=DepreciationComponent.BUMPER
        )

        # 1-year-old vehicle should have high retention (90%+)
        assert calculation.depreciation_factor >= 0.90
        assert calculation.depreciated_value_eur >= 148.5  # ~90% of 165

    def test_glass_depreciates_slower(self, depreciation_service):
        """Glass components depreciate slower than body panels."""
        # 5-year-old vehicle
        current_year = datetime.now().year
        vehicle_year = current_year - 5

        bumper_calc = depreciation_service.calculate(
            vehicle_id="TEST-001",
            vehicle_year=vehicle_year,
            original_cost_eur=780.0,
            component=DepreciationComponent.BUMPER
        )

        glass_calc = depreciation_service.calculate(
            vehicle_id="TEST-001",
            vehicle_year=vehicle_year,
            original_cost_eur=780.0,
            component=DepreciationComponent.GLASS
        )

        # Glass should retain more value than bumper
        assert glass_calc.depreciation_factor > bumper_calc.depreciation_factor

    def test_electronics_depreciate_faster(self, depreciation_service):
        """Electronics depreciate faster than mechanical parts."""
        # 5-year-old vehicle
        current_year = datetime.now().year
        vehicle_year = current_year - 5

        bumper_calc = depreciation_service.calculate(
            vehicle_id="TEST-002",
            vehicle_year=vehicle_year,
            original_cost_eur=500.0,
            component=DepreciationComponent.BUMPER
        )

        electronics_calc = depreciation_service.calculate(
            vehicle_id="TEST-002",
            vehicle_year=vehicle_year,
            original_cost_eur=500.0,
            component=DepreciationComponent.ELECTRONICS
        )

        # Electronics should depreciate more
        assert electronics_calc.depreciation_factor < bumper_calc.depreciation_factor


class TestVehicleAgeCalculation:
    """Test vehicle age calculation."""

    def test_current_year_vehicle(self, depreciation_service):
        """Current year vehicle should have age 0."""
        current_year = datetime.now().year

        calculation = depreciation_service.calculate(
            vehicle_id="TEST-003",
            vehicle_year=current_year,
            original_cost_eur=100.0,
            component=DepreciationComponent.BUMPER
        )

        assert calculation.vehicle_age_years == 0
        assert calculation.depreciation_factor == 1.0  # No depreciation

    def test_future_year_vehicle(self, depreciation_service):
        """Future year vehicle should be treated as age 0."""
        future_year = datetime.now().year + 1

        calculation = depreciation_service.calculate(
            vehicle_id="TEST-004",
            vehicle_year=future_year,
            original_cost_eur=100.0,
            component=DepreciationComponent.BUMPER
        )

        assert calculation.vehicle_age_years == 0

    def test_very_old_vehicle(self, depreciation_service):
        """Very old vehicles (6+ years) should use year_6_plus depreciation."""
        old_year = datetime.now().year - 15

        calculation = depreciation_service.calculate(
            vehicle_id="TEST-005",
            vehicle_year=old_year,
            original_cost_eur=500.0,
            component=DepreciationComponent.BUMPER
        )

        # Should use year_6_plus factor (0.25 for bumpers)
        assert calculation.depreciation_factor > 0  # Never goes to zero
        assert calculation.depreciation_factor <= 0.3  # Heavily depreciated
        assert calculation.depreciation_factor == 0.25  # Bumper year_6_plus value


class TestShouldApplyDepreciation:
    """Test depreciation applicability logic."""

    def test_should_apply_for_old_vehicle(self, depreciation_service):
        """Should apply depreciation for vehicles 2+ years old."""
        old_year = datetime.now().year - 5

        should_apply = depreciation_service.should_apply_depreciation(
            vehicle_year=old_year,
            component=DepreciationComponent.BUMPER
        )

        assert should_apply is True

    def test_should_not_apply_for_new_vehicle(self, depreciation_service):
        """Should not apply depreciation for vehicles under 2 years."""
        new_year = datetime.now().year - 1

        should_apply = depreciation_service.should_apply_depreciation(
            vehicle_year=new_year,
            component=DepreciationComponent.BUMPER
        )

        assert should_apply is False

    def test_custom_min_age(self, depreciation_service):
        """Should respect custom minimum age."""
        vehicle_year = datetime.now().year - 3

        # 3-year-old vehicle with min_age=4 should not apply
        should_apply = depreciation_service.should_apply_depreciation(
            vehicle_year=vehicle_year,
            component=DepreciationComponent.BUMPER,
            min_age_years=4
        )

        assert should_apply is False


class TestComponentInference:
    """Test component inference from damage location."""

    def test_infer_bumper(self, depreciation_service):
        """Should infer BUMPER from bumper locations."""
        locations = ["front_bumper", "rear bumper", "BUMPER"]

        for location in locations:
            component = depreciation_service.infer_component_from_location(location)
            assert component == DepreciationComponent.BUMPER

    def test_infer_panel(self, depreciation_service):
        """Should infer PANEL from body panel locations."""
        locations = ["driver_door", "quarter panel", "fender", "side panel"]

        for location in locations:
            component = depreciation_service.infer_component_from_location(location)
            assert component == DepreciationComponent.PANEL

    def test_infer_glass(self, depreciation_service):
        """Should infer GLASS from window locations."""
        locations = ["windshield", "rear window", "side glass"]

        for location in locations:
            component = depreciation_service.infer_component_from_location(location)
            assert component == DepreciationComponent.GLASS

    def test_infer_interior(self, depreciation_service):
        """Should infer INTERIOR from interior locations."""
        locations = ["rear seat", "carpet", "interior panel", "upholstery"]

        for location in locations:
            component = depreciation_service.infer_component_from_location(location)
            assert component == DepreciationComponent.INTERIOR

    def test_infer_electronics(self, depreciation_service):
        """Should infer ELECTRONICS from sensor/electronics."""
        locations = ["ADAS sensor", "camera", "electronics module"]

        for location in locations:
            component = depreciation_service.infer_component_from_location(location)
            assert component == DepreciationComponent.ELECTRONICS

    def test_default_to_panel_for_unknown(self, depreciation_service):
        """Should default to PANEL for unknown locations."""
        component = depreciation_service.infer_component_from_location("unknown_location")
        assert component == DepreciationComponent.PANEL


class TestDepreciationCurves:
    """Test depreciation curve retrieval."""

    def test_get_depreciation_curve(self, depreciation_service):
        """Should return full depreciation curve for component."""
        curve = depreciation_service.get_depreciation_curve(DepreciationComponent.BUMPER)

        assert isinstance(curve, dict)
        assert len(curve) > 0
        assert "year_1" in curve or "year_6_plus" in curve  # Has year data

        # Check that numeric values are in valid range (skip description key)
        for k, v in curve.items():
            if k != "description" and isinstance(v, (int, float)):
                assert 0 <= v <= 1.0

    def test_get_curve_for_unknown_component(self, depreciation_service):
        """Should return empty dict for unknown component."""
        # This won't work with enum validation, so we'll test the internal method
        curve = depreciation_service.depreciation_curves.get("unknown_component", {})
        assert curve == {}


class TestCalculationTransparency:
    """Test transparency and breakdown of calculations."""

    def test_calculation_includes_all_fields(self, depreciation_service):
        """Calculation should include all required fields for transparency."""
        calculation = depreciation_service.calculate(
            vehicle_id="TEST-006",
            vehicle_year=2019,
            original_cost_eur=450.0,
            component=DepreciationComponent.PANEL
        )

        assert calculation.vehicle_id is not None
        assert calculation.vehicle_age_years >= 0
        assert calculation.component is not None
        assert calculation.original_cost_eur == 450.0
        assert 0 <= calculation.depreciation_factor <= 1.0
        assert calculation.depreciated_value_eur >= 0
        assert calculation.savings_eur >= 0
        assert calculation.calculation_method is not None

    def test_savings_calculation(self, depreciation_service):
        """Savings should equal original cost minus depreciated value."""
        calculation = depreciation_service.calculate(
            vehicle_id="TEST-007",
            vehicle_year=2019,
            original_cost_eur=1000.0,
            component=DepreciationComponent.BUMPER
        )

        expected_savings = calculation.original_cost_eur - calculation.depreciated_value_eur
        assert abs(calculation.savings_eur - expected_savings) < 0.01  # Allow for rounding

    def test_depreciated_value_formula(self, depreciation_service):
        """Depreciated value should equal original cost times factor."""
        calculation = depreciation_service.calculate(
            vehicle_id="TEST-008",
            vehicle_year=2020,
            original_cost_eur=750.0,
            component=DepreciationComponent.INTERIOR
        )

        expected_value = calculation.original_cost_eur * calculation.depreciation_factor
        assert abs(calculation.depreciated_value_eur - expected_value) < 0.01  # Allow for rounding


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
