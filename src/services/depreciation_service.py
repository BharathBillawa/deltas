"""
Depreciation Service - Fair cost adjustment based on vehicle age.

Applies age-based depreciation to repair parts for transparent customer billing.
Company absorbs the depreciation cost difference.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.models.financial import DepreciationCalculation, DepreciationComponent

logger = logging.getLogger(__name__)


class DepreciationService:
    """
    Calculate fair repair costs with age-based depreciation.

    Features:
    - Component-specific depreciation curves (bumper, panel, interior, glass, electronics)
    - Age-based factor calculation
    - Transparent cost breakdown (customer pays depreciated value, company absorbs difference)
    - Graceful handling of missing vehicle data
    """

    def __init__(self, pricing_data_path: Optional[Path] = None):
        """
        Initialize depreciation service.

        Args:
            pricing_data_path: Path to repair_costs.json. If None, uses default.
        """
        if pricing_data_path is None:
            # Default path relative to project root
            project_root = Path(__file__).parent.parent.parent
            pricing_data_path = project_root / "data" / "pricing_database" / "repair_costs.json"

        self.pricing_data_path = pricing_data_path
        self._load_depreciation_curves()

    def _load_depreciation_curves(self) -> None:
        """Load depreciation curves from JSON file."""
        try:
            with open(self.pricing_data_path, "r") as f:
                data = json.load(f)

            self.depreciation_curves = data["depreciation_curves"]

            logger.info(f"Loaded depreciation curves from {self.pricing_data_path}")

        except FileNotFoundError:
            logger.error(f"Pricing data not found at {self.pricing_data_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in pricing data: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing depreciation_curves in pricing data: {e}")
            raise

    def calculate(
        self,
        vehicle_id: str,
        vehicle_year: int,
        original_cost_eur: float,
        component: DepreciationComponent,
        damage_location: Optional[str] = None,
    ) -> DepreciationCalculation:
        """
        Calculate depreciation for repair component.

        Args:
            vehicle_id: Vehicle identifier
            vehicle_year: Year vehicle was manufactured
            original_cost_eur: Full repair cost before depreciation
            component: Component type (bumper, panel, interior, glass, electronics)
            damage_location: Location on vehicle (optional, for component inference)

        Returns:
            DepreciationCalculation: Transparent breakdown

        Raises:
            ValueError: If vehicle_year is invalid or component unknown
        """
        # Calculate vehicle age
        current_year = datetime.now().year
        vehicle_age_years = current_year - vehicle_year

        if vehicle_age_years < 0:
            logger.warning(f"Vehicle year {vehicle_year} is in the future, using age 0")
            vehicle_age_years = 0

        # Get depreciation factor
        depreciation_factor = self._get_depreciation_factor(component, vehicle_age_years)

        # Calculate depreciated value (what customer pays)
        depreciated_value = original_cost_eur * depreciation_factor

        # Calculate savings (what company absorbs)
        savings = original_cost_eur - depreciated_value

        # Build calculation
        calculation = DepreciationCalculation(
            vehicle_id=vehicle_id,
            vehicle_age_years=vehicle_age_years,
            component=component,
            original_cost_eur=round(original_cost_eur, 2),
            depreciation_factor=depreciation_factor,
            depreciated_value_eur=round(depreciated_value, 2),
            savings_eur=round(savings, 2),
            calculation_method="age_based_curve",
            notes=f"{component.value.title()} on {vehicle_age_years}-year-old vehicle"
        )

        logger.info(
            f"Depreciation: {component.value} age {vehicle_age_years}y "
            f"= €{original_cost_eur:.2f} → €{depreciated_value:.2f} "
            f"(company absorbs €{savings:.2f})"
        )

        return calculation

    def _get_depreciation_factor(
        self,
        component: DepreciationComponent,
        vehicle_age_years: int
    ) -> float:
        """
        Get depreciation factor for component and vehicle age.

        Args:
            component: Component type
            vehicle_age_years: Age of vehicle in years

        Returns:
            Depreciation factor (0.0 to 1.0)
        """
        component_key = component.value

        if component_key not in self.depreciation_curves:
            logger.warning(f"Unknown component: {component_key}, using 1.0 (no depreciation)")
            return 1.0

        curve = self.depreciation_curves[component_key]

        # Brand new vehicles (year 0) have no depreciation
        if vehicle_age_years == 0:
            return 1.0

        # For vehicles 6+ years old, use year_6_plus
        if vehicle_age_years >= 6:
            if "year_6_plus" in curve:
                return curve["year_6_plus"]

        # Try exact year first
        year_key = f"year_{vehicle_age_years}"

        if year_key in curve:
            return curve[year_key]

        # If not found, use closest available
        logger.warning(f"No factor for {year_key}, using closest available")

        # Find available years (excluding year_6_plus)
        available_years = []
        for k in curve.keys():
            if k.startswith("year_") and k != "year_6_plus":
                try:
                    year = int(k.split("_")[1])
                    available_years.append(year)
                except (ValueError, IndexError):
                    continue

        if not available_years:
            logger.error(f"No year data found for {component_key}, using 1.0")
            return 1.0

        available_years.sort()

        # Use closest year
        closest_year = min(available_years, key=lambda y: abs(y - vehicle_age_years))
        return curve[f"year_{closest_year}"]

    def should_apply_depreciation(
        self,
        vehicle_year: int,
        component: DepreciationComponent,
        min_age_years: int = 2
    ) -> bool:
        """
        Determine if depreciation should be applied.

        Typically only apply depreciation for vehicles 2+ years old.

        Args:
            vehicle_year: Year vehicle was manufactured
            component: Component type
            min_age_years: Minimum age before depreciation applies (default: 2)

        Returns:
            True if depreciation should be applied
        """
        current_year = datetime.now().year
        vehicle_age_years = current_year - vehicle_year

        return vehicle_age_years >= min_age_years

    def infer_component_from_location(self, damage_location: str) -> DepreciationComponent:
        """
        Infer depreciation component from damage location.

        Args:
            damage_location: Location on vehicle

        Returns:
            DepreciationComponent: Best guess component type
        """
        location_lower = damage_location.lower()

        # Mapping of keywords to components (order matters - check specific first)
        if "bumper" in location_lower:
            return DepreciationComponent.BUMPER
        elif any(word in location_lower for word in ["windshield", "window", "glass"]):
            return DepreciationComponent.GLASS
        elif any(word in location_lower for word in ["seat", "interior", "carpet", "upholstery"]):
            return DepreciationComponent.INTERIOR
        elif any(word in location_lower for word in ["sensor", "camera", "electronics", "adas"]):
            return DepreciationComponent.ELECTRONICS
        elif any(word in location_lower for word in ["door", "panel", "quarter", "fender"]):
            return DepreciationComponent.PANEL
        else:
            # Default to panel for unknown locations
            logger.debug(f"Could not infer component from '{damage_location}', using PANEL")
            return DepreciationComponent.PANEL

    def get_depreciation_curve(self, component: DepreciationComponent) -> Dict[str, float]:
        """
        Get full depreciation curve for component.

        Useful for visualizations or analysis.

        Args:
            component: Component type

        Returns:
            Dict mapping year keys to depreciation factors
        """
        component_key = component.value

        if component_key not in self.depreciation_curves:
            logger.warning(f"Unknown component: {component_key}")
            return {}

        return self.depreciation_curves[component_key].copy()
