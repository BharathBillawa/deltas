"""
Analytics API endpoints.

Routes for fleet health, patterns, and location analytics.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.persistence.database import get_db
from src.services.fleet_analytics_service import FleetAnalyticsService

router = APIRouter()


# Response Models

class FleetHealthResponse(BaseModel):
    """Response model for fleet health summary."""
    total_vehicles: int
    avg_health_score: float
    vehicles_needing_attention: int
    total_damage_cost_ytd: float
    avg_damage_cost_per_vehicle: float
    health_distribution: dict = Field(default_factory=dict)


class LocationRiskResponse(BaseModel):
    """Response model for location risk analysis."""
    location: str
    total_damages: int
    total_cost_eur: float
    avg_cost_per_damage: float
    risk_score: float
    recommendation: str


class PatternSummaryResponse(BaseModel):
    """Response model for pattern summary."""
    pattern_type: str
    count: int
    affected_vehicles: list[str]
    description: str


# Endpoints

@router.get("/fleet-health", response_model=FleetHealthResponse)
async def get_fleet_health(db: Session = Depends(get_db)):
    """
    Get fleet health summary.

    Returns overall fleet metrics including:
    - Total vehicles
    - Average health score
    - Vehicles needing attention
    - Total damage costs YTD
    """
    try:
        analytics_service = FleetAnalyticsService(db)
        health = analytics_service.get_fleet_health_summary()

        return FleetHealthResponse(
            total_vehicles=health["total_vehicles"],
            avg_health_score=health["avg_health_score"],
            vehicles_needing_attention=health["vehicles_needing_attention"],
            total_damage_cost_ytd=health["total_damage_cost_ytd"],
            avg_damage_cost_per_vehicle=health["avg_damage_cost_per_vehicle"],
            health_distribution=health.get("health_distribution", {})
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch fleet health: {str(e)}"
        )


@router.get("/locations", response_model=list[LocationRiskResponse])
async def get_location_risk_analysis(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get location risk analysis.

    Returns damage statistics by return location,
    sorted by risk score.
    """
    try:
        analytics_service = FleetAnalyticsService(db)
        locations = analytics_service.get_location_risk_analysis()

        # Limit and convert to response models
        return [
            LocationRiskResponse(
                location=loc["location"],
                total_damages=loc["total_damages"],
                total_cost_eur=loc["total_cost_eur"],
                avg_cost_per_damage=loc["avg_cost_per_damage"],
                risk_score=loc["risk_score"],
                recommendation=loc["recommendation"]
            )
            for loc in locations[:limit]
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch location analysis: {str(e)}"
        )


@router.get("/patterns", response_model=list[PatternSummaryResponse])
async def get_pattern_summary(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get summary of detected patterns across the fleet.

    Returns recent patterns detected by the pattern recognition service.
    """
    try:
        analytics_service = FleetAnalyticsService(db)
        patterns = analytics_service.get_pattern_summary()

        # Group patterns by type
        pattern_groups = {}
        for pattern in patterns:
            ptype = pattern["pattern_type"]
            if ptype not in pattern_groups:
                pattern_groups[ptype] = {
                    "pattern_type": ptype,
                    "count": 0,
                    "affected_vehicles": [],
                    "description": pattern.get("description", "")
                }
            pattern_groups[ptype]["count"] += 1
            if pattern["vehicle_id"] not in pattern_groups[ptype]["affected_vehicles"]:
                pattern_groups[ptype]["affected_vehicles"].append(pattern["vehicle_id"])

        # Convert to response models
        return [
            PatternSummaryResponse(
                pattern_type=data["pattern_type"],
                count=data["count"],
                affected_vehicles=data["affected_vehicles"][:5],  # Limit vehicles shown
                description=data["description"]
            )
            for data in list(pattern_groups.values())[:limit]
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch patterns: {str(e)}"
        )


@router.get("/retirement-candidates")
async def get_retirement_candidates(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get list of vehicles that are candidates for retirement.

    Returns vehicles with:
    - High cumulative damage costs
    - Low health scores
    - High mileage
    """
    try:
        analytics_service = FleetAnalyticsService(db)
        candidates = analytics_service.get_retirement_candidates()

        return {
            "count": len(candidates),
            "candidates": candidates[:limit]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch retirement candidates: {str(e)}"
        )


@router.get("/cost-breakdown")
async def get_cost_breakdown(
    period: str = "ytd",
    db: Session = Depends(get_db)
):
    """
    Get cost breakdown by category.

    Returns damage costs grouped by vehicle category.
    """
    try:
        analytics_service = FleetAnalyticsService(db)
        breakdown = analytics_service.get_cost_breakdown_by_category()

        return {
            "period": period,
            "breakdown": breakdown
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cost breakdown: {str(e)}"
        )
