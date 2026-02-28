"""
Pricing Service - Validated German market repair cost calculation.

Based on GDV/Dekra 2024 data:
- Standard bodywork: €202/hour
- Painting: €220/hour
- Vehicle category multipliers: Economy 1.0x → Premium 2.1x
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from src.models.damage import DamageSeverity, DamageType
from src.models.financial import CostEstimate, LaborType

logger = logging.getLogger(__name__)


class PricingService:
    """
    Calculate repair costs using validated German market data.

    Features:
    - Validated labor rates (GDV/Dekra 2024)
    - Vehicle category multipliers
    - Location-based multipliers (optional)
    - Graceful handling of unknown damage types
    """

    def __init__(self, pricing_data_path: Optional[Path] = None):
        """
        Initialize pricing service with repair cost data.

        Args:
            pricing_data_path: Path to repair_costs.json. If None, uses default.
        """
        if pricing_data_path is None:
            # Default path relative to project root
            project_root = Path(__file__).parent.parent.parent
            pricing_data_path = project_root / "data" / "pricing_database" / "repair_costs.json"

        self.pricing_data_path = pricing_data_path
        self._load_pricing_data()

    def _load_pricing_data(self) -> None:
        """Load repair costs from JSON file."""
        try:
            with open(self.pricing_data_path, "r") as f:
                data = json.load(f)

            self.labor_rates = data["labor_rates"]
            self.damage_types = data["damage_types"]
            self.vehicle_categories = data["vehicle_category_multipliers"]
            self.location_profiles = data.get("location_risk_profiles", {})

            logger.info(f"Loaded pricing data from {self.pricing_data_path}")

        except FileNotFoundError:
            logger.error(f"Pricing data not found at {self.pricing_data_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in pricing data: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required key in pricing data: {e}")
            raise

    def calculate_cost(
        self,
        claim_id: str,
        damage_type: DamageType,
        severity: DamageSeverity,
        vehicle_category: str,
        location: Optional[str] = None,
        damage_location: Optional[str] = None,
    ) -> CostEstimate:
        """
        Calculate repair cost estimate.

        Args:
            claim_id: Unique claim identifier
            damage_type: Type of damage (scratch, dent, etc.)
            severity: Severity level (minor, medium, severe)
            vehicle_category: Category (Economy, Compact, Standard, Luxury, Premium, SUV)
            location: Rental location (for risk-based multiplier, optional)
            damage_location: Where on vehicle (bumper, door, etc., optional)

        Returns:
            CostEstimate: Detailed cost breakdown

        Raises:
            ValueError: If damage type/severity combination not found in data
        """
        # Get damage details
        damage_key = damage_type.value
        severity_key = severity.value

        if damage_key not in self.damage_types:
            logger.warning(f"Unknown damage type: {damage_key}, using default")
            return self._create_fallback_estimate(claim_id, vehicle_category)

        damage_data = self.damage_types[damage_key]

        if severity_key not in damage_data:
            logger.warning(f"Unknown severity: {severity_key} for {damage_key}, using fallback")
            return self._create_fallback_estimate(claim_id, vehicle_category)

        severity_data = damage_data[severity_key]

        # Calculate labor
        labor_hours = (severity_data["labor_hours_min"] + severity_data["labor_hours_max"]) / 2
        labor_type_key = severity_data["labor_type"]
        labor_rate = self.labor_rates[labor_type_key]["rate_per_hour"]
        labor_cost = labor_hours * labor_rate

        # Calculate parts
        parts_cost = (severity_data["parts_cost_min"] + severity_data["parts_cost_max"]) / 2

        # Apply category multiplier
        category_multiplier = self._get_category_multiplier(vehicle_category)

        # Apply location multiplier (optional)
        location_multiplier = self._get_location_multiplier(location) if location else 1.0

        # Calculate subtotal
        base_cost = labor_cost + parts_cost
        subtotal = base_cost * category_multiplier * location_multiplier

        # Round to nearest euro
        subtotal = round(subtotal, 2)

        # Build estimate
        estimate = CostEstimate(
            claim_id=claim_id,
            labor_hours=labor_hours,
            labor_type=LaborType(labor_type_key),
            labor_rate_eur=labor_rate,
            labor_cost_eur=round(labor_cost, 2),
            parts_cost_eur=round(parts_cost, 2),
            category_multiplier=category_multiplier,
            location_multiplier=location_multiplier,
            subtotal_eur=subtotal,
            depreciation_applicable=False,  # Handled by DepreciationService
            total_eur=subtotal,
            confidence_score=0.85,
            notes=f"{damage_type.value.title()} ({severity.value}) on {vehicle_category} vehicle"
        )

        logger.info(
            f"Cost estimate: {damage_type.value}/{severity.value} on {vehicle_category} "
            f"= €{estimate.total_eur:.2f}"
        )

        return estimate

    def _get_category_multiplier(self, category: str) -> float:
        """
        Get vehicle category cost multiplier.

        Args:
            category: Vehicle category (Economy, Compact, etc.)

        Returns:
            Multiplier value (1.0 to 2.1)
        """
        if category not in self.vehicle_categories:
            logger.warning(f"Unknown vehicle category: {category}, using 1.0x multiplier")
            return 1.0

        return self.vehicle_categories[category]["multiplier"]

    def _get_location_multiplier(self, location: str) -> float:
        """
        Get location-based cost multiplier.

        Currently all locations have 1.0x multiplier in our data,
        but infrastructure supports location-based pricing.

        Args:
            location: Rental location key

        Returns:
            Multiplier value (defaults to 1.0)
        """
        if location not in self.location_profiles:
            logger.debug(f"Unknown location: {location}, using 1.0x multiplier")
            return 1.0

        return self.location_profiles[location].get("cost_multiplier", 1.0)

    def _create_fallback_estimate(self, claim_id: str, vehicle_category: str) -> CostEstimate:
        """
        Create fallback estimate for unknown damage types.

        Uses conservative defaults to ensure system doesn't fail.

        Args:
            claim_id: Claim identifier
            vehicle_category: Vehicle category

        Returns:
            CostEstimate: Conservative estimate (€300 base)
        """
        logger.warning(f"Using fallback estimate for claim {claim_id}")

        # Conservative defaults
        base_cost = 300.0
        category_multiplier = self._get_category_multiplier(vehicle_category)
        total = base_cost * category_multiplier

        return CostEstimate(
            claim_id=claim_id,
            labor_hours=1.5,
            labor_type=LaborType.STANDARD_BODYWORK,
            labor_rate_eur=202,
            labor_cost_eur=303,
            parts_cost_eur=0,
            category_multiplier=category_multiplier,
            location_multiplier=1.0,
            subtotal_eur=round(total, 2),
            depreciation_applicable=False,
            total_eur=round(total, 2),
            confidence_score=0.5,  # Low confidence for fallback
            notes="Conservative estimate - damage type details unclear"
        )

    def get_cost_range(
        self,
        damage_type: DamageType,
        severity: DamageSeverity
    ) -> Optional[Dict[str, float]]:
        """
        Get cost range for damage type/severity without full calculation.

        Useful for quick estimates or UIs showing ranges.

        Args:
            damage_type: Type of damage
            severity: Severity level

        Returns:
            Dict with min/max costs, or None if not found
        """
        damage_key = damage_type.value
        severity_key = severity.value

        if damage_key not in self.damage_types:
            return None

        damage_data = self.damage_types[damage_key]

        if severity_key not in damage_data:
            return None

        severity_data = damage_data[severity_key]

        # Calculate range
        labor_type_key = severity_data["labor_type"]
        labor_rate = self.labor_rates[labor_type_key]["rate_per_hour"]

        min_cost = (
            severity_data["labor_hours_min"] * labor_rate +
            severity_data["parts_cost_min"]
        )
        max_cost = (
            severity_data["labor_hours_max"] * labor_rate +
            severity_data["parts_cost_max"]
        )

        return {
            "min_eur": round(min_cost, 2),
            "max_eur": round(max_cost, 2),
            "labor_type": labor_type_key,
            "description": severity_data.get("description", "")
        }
