"""
Damage assessment and vehicle data models.

Based on realistic car rental damage scenarios with validated German market data.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DamageType(str, Enum):
    """Types of vehicle damage."""
    SCRATCH = "scratch"
    DENT = "dent"
    BUMPER_CRACK = "bumper_crack"
    WINDSHIELD_CRACK = "windshield_crack"
    INTERIOR_STAIN = "interior_stain"
    MIRROR_DAMAGE = "mirror_damage"
    UNDERCARRIAGE = "undercarriage"
    MULTIPLE = "multiple"


class DamageSeverity(str, Enum):
    """Severity levels for damage assessment."""
    MINOR = "minor"
    MEDIUM = "medium"
    SEVERE = "severe"
    HIGH = "high"  # Used for windshield and critical damage


class VehicleLocation(str, Enum):
    """Vehicle body locations."""
    FRONT_BUMPER = "front_bumper"
    REAR_BUMPER = "rear_bumper"
    DRIVER_DOOR = "driver_door"
    PASSENGER_DOOR = "passenger_door"
    REAR_QUARTER_PANEL = "rear_quarter_panel"
    WINDSHIELD = "windshield"
    REAR_SEAT = "rear_seat"
    UNDERCARRIAGE = "undercarriage"
    SIDE_MIRROR = "side_mirror"
    MULTIPLE = "multiple"


class VehicleCategory(str, Enum):
    """Vehicle rental categories."""
    ECONOMY = "Economy"
    COMPACT = "Compact"
    STANDARD = "Standard"
    LUXURY = "Luxury"
    PREMIUM = "Premium"
    SUV = "SUV"


class DamageStatus(str, Enum):
    """Status of damage claim processing."""
    PENDING_REVIEW = "pending_review"
    AUTO_APPROVED = "auto_approved"
    REPAIRED = "repaired"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class DamageAssessment(BaseModel):
    """
    Damage assessment from vehicle inspector.

    This is the input to the system after CV damage detection.
    """
    damage_type: DamageType
    severity: DamageSeverity
    location: VehicleLocation
    description: str = Field(..., description="Human-readable damage description")
    affected_parts: List[str] = Field(default_factory=list)
    photos: List[str] = Field(default_factory=list, description="Photo filenames or URLs")
    inspector_id: str
    inspector_notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "damage_type": "scratch",
                "severity": "minor",
                "location": "rear_bumper",
                "description": "10cm scratch from parking lot incident",
                "affected_parts": ["rear_bumper"],
                "photos": ["damage_001_overview.jpg"],
                "inspector_id": "INSP-042",
                "inspector_notes": "Clean scratch, buffing should be sufficient"
            }
        }


class ServiceRecord(BaseModel):
    """Vehicle service/maintenance record."""
    date: datetime
    type: str = Field(..., description="Service type (oil_change, tire_rotation, etc.)")
    cost_eur: float
    mileage_km: int
    notes: Optional[str] = None


class HistoricalDamage(BaseModel):
    """Past damage record for pattern analysis."""
    date: datetime
    damage_type: DamageType
    severity: DamageSeverity
    location: VehicleLocation
    description: str
    repair_cost_eur: float
    labor_hours: float
    labor_rate_eur: float
    parts_cost_eur: float
    rental_return_location: str
    customer_id: str
    status: DamageStatus
    insurance_claim: bool = False
    flags: List[str] = Field(default_factory=list)


class RentalHistorySummary(BaseModel):
    """Summary of vehicle rental history."""
    total_rentals: int
    rentals_with_damage: int
    damage_rate_percent: float
    avg_rental_days: float


class VehicleInfo(BaseModel):
    """
    Complete vehicle information including history.

    Used for context enrichment and pattern recognition.
    """
    vehicle_id: str
    category: VehicleCategory
    make: str
    model: str
    year: int
    color: str
    vin: str
    license_plate: str
    purchase_date: datetime
    purchase_price_eur: float
    current_mileage_km: int
    last_service_date: Optional[datetime] = None

    # History for pattern recognition
    service_history: List[ServiceRecord] = Field(default_factory=list)
    damage_history: List[HistoricalDamage] = Field(default_factory=list)
    rental_history_summary: Optional[RentalHistorySummary] = None

    # Health metrics
    health_score: float = Field(ge=0.0, le=10.0, description="Vehicle health score 0-10")
    cumulative_damage_ytd_eur: float = Field(default=0.0)
    depreciation_percent: Optional[float] = Field(default=None, ge=0, le=100)

    # Flags and notes
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "vehicle_id": "VW-POLO-2023-001",
                "category": "Economy",
                "make": "Volkswagen",
                "model": "Polo",
                "year": 2023,
                "health_score": 9.2
            }
        }


class DamageClaim(BaseModel):
    """
    Complete damage claim submission.

    This is the main input to the workflow.
    """
    claim_id: str
    timestamp: datetime
    vehicle_id: str
    customer_id: str
    rental_agreement_id: str
    return_location: str
    damage_assessment: DamageAssessment

    # Context (enriched by system)
    vehicle_context: Optional[VehicleInfo] = None

    class Config:
        json_schema_extra = {
            "example": {
                "claim_id": "CLM-2026-001",
                "timestamp": "2026-02-28T10:30:00Z",
                "vehicle_id": "VW-POLO-2023-001",
                "customer_id": "CUST-5678",
                "rental_agreement_id": "RNT-2026-0234",
                "return_location": "Munich_Airport"
            }
        }
