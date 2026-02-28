"""
Financial models for cost estimation, depreciation, and invoicing.

Based on validated German market data (GDV/Dekra 2024).
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class LaborType(str, Enum):
    """Types of labor for cost calculation."""
    STANDARD_BODYWORK = "standard_bodywork"  # €202/hour (GDV validated)
    PAINTING = "painting"  # €220/hour (GDV validated)
    SPECIALIST_REPAIR = "specialist_repair"  # €245/hour (ADAS, luxury)
    INTERIOR_CLEANING = "interior_cleaning"  # €85/hour


class DepreciationComponent(str, Enum):
    """Component types for depreciation calculation."""
    BUMPER = "bumper"
    PANEL = "panel"
    INTERIOR = "interior"
    GLASS = "glass"
    ELECTRONICS = "electronics"


class CostEstimate(BaseModel):
    """
    Detailed cost breakdown for damage repair.

    Includes validated German market labor rates and depreciation.
    """
    claim_id: str

    # Labor costs
    labor_hours: float = Field(gt=0, description="Estimated repair hours")
    labor_type: LaborType
    labor_rate_eur: float = Field(gt=0, description="Hourly labor rate")
    labor_cost_eur: float = Field(ge=0)

    # Parts costs
    parts_cost_eur: float = Field(ge=0)

    # Multipliers
    category_multiplier: float = Field(default=1.0, ge=1.0, le=3.0)
    location_multiplier: float = Field(default=1.0, ge=1.0, le=1.5)

    # Subtotal before depreciation
    subtotal_eur: float = Field(ge=0)

    # Depreciation
    depreciation_applicable: bool = Field(default=False)
    depreciation_component: Optional[DepreciationComponent] = None
    depreciation_factor: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    depreciated_value_eur: Optional[float] = Field(default=None, ge=0)

    # Final cost
    total_eur: float = Field(ge=0, description="Final cost to customer")

    # Metadata
    estimation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    estimation_method: str = Field(default="automated")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "claim_id": "CLM-2026-001",
                "labor_hours": 0.8,
                "labor_type": "standard_bodywork",
                "labor_rate_eur": 202,
                "labor_cost_eur": 161.60,
                "parts_cost_eur": 3,
                "category_multiplier": 1.0,
                "subtotal_eur": 164.60,
                "depreciation_applicable": False,
                "total_eur": 165
            }
        }


class DepreciationCalculation(BaseModel):
    """Depreciation calculation details for transparency."""
    vehicle_id: str
    vehicle_age_years: int
    component: DepreciationComponent
    original_cost_eur: float
    depreciation_factor: float = Field(ge=0.0, le=1.0)
    depreciated_value_eur: float
    savings_eur: float = Field(ge=0, description="Amount absorbed by company")
    calculation_method: str = Field(default="age_based_curve")
    notes: Optional[str] = None


class InvoiceLineItem(BaseModel):
    """Single line item on repair invoice."""
    description: str
    quantity: float = Field(default=1.0, gt=0)
    unit_price_eur: float = Field(ge=0)
    total_eur: float = Field(ge=0)
    category: str = Field(default="repair")  # repair, parts, labor, etc.


class Invoice(BaseModel):
    """
    Professional repair invoice for customer billing.

    Generated after cost estimation and approval.
    """
    invoice_id: str
    claim_id: str
    invoice_date: datetime = Field(default_factory=datetime.utcnow)

    # Customer details
    customer_id: str
    customer_name: Optional[str] = None
    rental_agreement_id: str

    # Vehicle details
    vehicle_id: str
    vehicle_description: str

    # Damage details
    damage_description: str
    damage_location: str

    # Line items
    line_items: List[InvoiceLineItem]

    # Totals
    subtotal_eur: float = Field(ge=0)
    tax_rate_percent: float = Field(default=19.0)  # German VAT
    tax_amount_eur: float = Field(ge=0)
    total_eur: float = Field(ge=0)

    # Payment terms
    due_date: datetime
    payment_status: str = Field(default="pending")

    # Notes
    depreciation_applied: bool = Field(default=False)
    depreciation_notes: Optional[str] = None
    additional_notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_id": "INV-2026-001",
                "claim_id": "CLM-2026-001",
                "customer_id": "CUST-5678",
                "vehicle_id": "VW-POLO-2023-001",
                "damage_description": "Minor scratch repair",
                "total_eur": 196.35
            }
        }


class RetirementAnalysis(BaseModel):
    """
    Strategic analysis for repair vs auction decision.

    Part of fleet intelligence - not just tactical claims processing.
    """
    vehicle_id: str
    analysis_date: datetime = Field(default_factory=datetime.utcnow)

    # Current damage
    current_damage_repair_cost_eur: float

    # Vehicle condition
    cumulative_damage_cost_eur: float
    percentage_of_market_value: float
    health_score: float = Field(ge=0.0, le=10.0)
    mileage_km: int
    age_years: int

    # Financial analysis
    estimated_auction_value_eur: float
    estimated_remaining_rental_life_months: int
    estimated_monthly_revenue_eur: float
    total_potential_revenue_eur: float
    repair_plus_service_cost_eur: float

    # Decision support
    net_benefit_keep_eur: float
    net_benefit_auction_eur: float
    recommendation: str
    risk_factors: List[str] = Field(default_factory=list)

    # Confidence
    confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {
                "vehicle_id": "BMW-530-2018-009",
                "current_damage_repair_cost_eur": 890,
                "cumulative_damage_cost_eur": 3785,
                "recommendation": "Consider auction - high mileage, poor health",
                "net_benefit_auction_eur": 15000
            }
        }
