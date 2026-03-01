"""
Fleet Analytics Service - Aggregate insights for dashboards.

Provides high-level fleet health metrics, location analysis, and retirement candidates.
Separate from PatternRecognitionService (which focuses on individual vehicles/customers).
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.persistence.database import VehicleDB, DamageDB, ApprovalQueueDB

logger = logging.getLogger(__name__)


class FleetAnalyticsService:
    """
    Aggregate analytics for fleet management dashboards.

    Features:
    - Fleet health summary (vehicle counts by health score)
    - Location risk analysis (damage rates by location)
    - Cost aggregations
    - Retirement candidates list
    """

    def __init__(self, db_session: Session):
        """
        Initialize fleet analytics service.

        Args:
            db_session: Database session
        """
        self.db = db_session

    def get_fleet_health_summary(self) -> Dict:
        """
        Get aggregate fleet health metrics.

        Returns:
            Dict with fleet health breakdown
        """
        vehicles = self.db.query(VehicleDB).all()

        if not vehicles:
            return {
                "total_vehicles": 0,
                "health_distribution": {},
                "avg_health_score": 0.0,
                "vehicles_needing_attention": 0,
                "total_damage_cost_ytd": 0.0,
                "avg_damage_cost_per_vehicle": 0.0
            }

        # Categorize by health score
        excellent = sum(1 for v in vehicles if v.health_score >= 8)
        good = sum(1 for v in vehicles if 6 <= v.health_score < 8)
        fair = sum(1 for v in vehicles if 4 <= v.health_score < 6)
        poor = sum(1 for v in vehicles if v.health_score < 4)

        total = len(vehicles)
        avg_score = sum(v.health_score for v in vehicles) / total

        # Financial metrics
        total_damage_cost = sum(v.cumulative_damage_ytd_eur for v in vehicles)
        avg_damage_cost = total_damage_cost / total

        # Vehicles needing attention (health < 6)
        needs_attention_count = sum(1 for v in vehicles if v.health_score < 6)

        return {
            "total_vehicles": total,
            "health_distribution": {
                "excellent": {"count": excellent, "percent": round(100 * excellent / total, 1)},
                "good": {"count": good, "percent": round(100 * good / total, 1)},
                "fair": {"count": fair, "percent": round(100 * fair / total, 1)},
                "poor": {"count": poor, "percent": round(100 * poor / total, 1)}
            },
            "avg_health_score": round(avg_score, 2),
            "vehicles_needing_attention": needs_attention_count,
            "total_damage_cost_ytd": round(total_damage_cost, 2),
            "avg_damage_cost_per_vehicle": round(avg_damage_cost, 2)
        }

    def get_location_risk_analysis(self) -> List[Dict]:
        """
        Analyze damage rates by rental return location.

        Returns:
            List of location risk profiles
        """
        # Get all damages from last 12 months
        twelve_months_ago = datetime.now() - timedelta(days=365)
        damages = self.db.query(DamageDB).filter(
            DamageDB.date >= twelve_months_ago
        ).all()

        if not damages:
            return []

        # Group by location
        location_stats: Dict[str, Dict] = {}

        for damage in damages:
            if not damage.rental_return_location:
                continue

            loc = damage.rental_return_location

            if loc not in location_stats:
                location_stats[loc] = {
                    "location": loc,
                    "damage_count": 0,
                    "total_cost_eur": 0.0,
                    "avg_cost_eur": 0.0,
                    "damage_types": {}
                }

            location_stats[loc]["damage_count"] += 1
            location_stats[loc]["total_cost_eur"] += damage.repair_cost_eur or 0

            # Track damage types
            dtype = damage.damage_type
            if dtype not in location_stats[loc]["damage_types"]:
                location_stats[loc]["damage_types"][dtype] = 0
            location_stats[loc]["damage_types"][dtype] += 1

        # Calculate averages and identify high-risk
        total_damages = len(damages)
        avg_damages_per_location = total_damages / len(location_stats) if location_stats else 0

        result = []
        for loc, stats in location_stats.items():
            avg_cost = stats["total_cost_eur"] / stats["damage_count"] if stats["damage_count"] > 0 else 0

            # Determine risk level
            damage_rate_vs_avg = stats["damage_count"] / avg_damages_per_location if avg_damages_per_location > 0 else 1.0

            if damage_rate_vs_avg >= 1.5:
                risk_level = "high"
            elif damage_rate_vs_avg >= 1.2:
                risk_level = "medium"
            else:
                risk_level = "low"

            # Most common damage type
            most_common_type = max(stats["damage_types"], key=stats["damage_types"].get) if stats["damage_types"] else "unknown"

            # Convert risk level to numeric score
            risk_scores = {"low": 3.0, "medium": 6.0, "high": 9.0}
            risk_score = risk_scores.get(risk_level, 5.0)

            # Generate recommendation
            if risk_level == "high":
                recommendation = f"High damage rate at {loc}. Review parking/vehicle check procedures."
            elif risk_level == "medium":
                recommendation = f"Monitor {loc} for trends. Most common: {most_common_type}."
            else:
                recommendation = f"Low risk location. Standard monitoring sufficient."

            result.append({
                "location": loc,
                "total_damages": stats["damage_count"],
                "total_cost_eur": round(stats["total_cost_eur"], 2),
                "avg_cost_per_damage": round(avg_cost, 2),
                "risk_score": risk_score,
                "recommendation": recommendation
            })

        # Sort by damage count descending
        result.sort(key=lambda x: x["total_damages"], reverse=True)

        return result

    def get_cost_aggregations(
        self,
        time_period_days: int = 365,
        group_by_category: bool = True
    ) -> Dict:
        """
        Get cost aggregations for reporting.

        Args:
            time_period_days: Days to look back (default: 365)
            group_by_category: Group by vehicle category (default: True)

        Returns:
            Dict with cost breakdowns
        """
        start_date = datetime.now() - timedelta(days=time_period_days)

        damages = self.db.query(DamageDB).filter(
            DamageDB.date >= start_date
        ).all()

        if not damages:
            return {
                "total_cost_eur": 0.0,
                "damage_count": 0,
                "avg_cost_per_damage": 0.0,
                "by_category": {}
            }

        total_cost = sum(d.repair_cost_eur for d in damages if d.repair_cost_eur)
        damage_count = len(damages)

        result = {
            "total_cost_eur": round(total_cost, 2),
            "damage_count": damage_count,
            "avg_cost_per_damage": round(total_cost / damage_count if damage_count > 0 else 0, 2),
            "time_period_days": time_period_days
        }

        if group_by_category:
            # Get vehicle categories for damages
            category_costs: Dict[str, float] = {}
            category_counts: Dict[str, int] = {}

            for damage in damages:
                vehicle = self.db.query(VehicleDB).filter(
                    VehicleDB.vehicle_id == damage.vehicle_id
                ).first()

                if vehicle:
                    cat = vehicle.category
                    category_costs[cat] = category_costs.get(cat, 0) + (damage.repair_cost_eur or 0)
                    category_counts[cat] = category_counts.get(cat, 0) + 1

            result["by_category"] = {
                cat: {
                    "total_cost_eur": round(cost, 2),
                    "damage_count": category_counts[cat],
                    "avg_cost_eur": round(cost / category_counts[cat] if category_counts[cat] > 0 else 0, 2)
                }
                for cat, cost in category_costs.items()
            }

        return result

    def get_retirement_candidates(
        self,
        health_score_threshold: float = 5.0,
        cumulative_cost_threshold: float = 2500.0
    ) -> List[Dict]:
        """
        Get list of vehicles that may need retirement.

        Args:
            health_score_threshold: Max health score for consideration (default: 5.0)
            cumulative_cost_threshold: Min cumulative damage cost (default: €2500)

        Returns:
            List of retirement candidates with analysis
        """
        vehicles = self.db.query(VehicleDB).all()

        candidates = []

        for vehicle in vehicles:
            # Check if meets retirement criteria
            low_health = vehicle.health_score < health_score_threshold
            high_cost = vehicle.cumulative_damage_ytd_eur >= cumulative_cost_threshold

            if low_health or high_cost:
                # Calculate vehicle age
                age_years = datetime.now().year - vehicle.year

                # Get recent damage count
                recent_damages = self.db.query(DamageDB).filter(
                    DamageDB.vehicle_id == vehicle.vehicle_id,
                    DamageDB.date >= datetime.now() - timedelta(days=180)
                ).count()

                candidates.append({
                    "vehicle_id": vehicle.vehicle_id,
                    "make_model": f"{vehicle.make} {vehicle.model}",
                    "year": vehicle.year,
                    "age_years": age_years,
                    "category": vehicle.category,
                    "health_score": vehicle.health_score,
                    "cumulative_damage_ytd_eur": vehicle.cumulative_damage_ytd_eur,
                    "current_mileage_km": vehicle.current_mileage_km,
                    "recent_damages_6mo": recent_damages,
                    "retirement_reasons": self._get_retirement_reasons(
                        low_health, high_cost, age_years, vehicle.current_mileage_km
                    )
                })

        # Sort by health score (lowest first)
        candidates.sort(key=lambda x: x["health_score"])

        return candidates

    def _get_retirement_reasons(
        self,
        low_health: bool,
        high_cost: bool,
        age_years: int,
        mileage_km: int
    ) -> List[str]:
        """Generate human-readable retirement reasons."""
        reasons = []

        if low_health:
            reasons.append("Low health score")
        if high_cost:
            reasons.append("High cumulative damage cost")
        if age_years >= 7:
            reasons.append(f"Vehicle age: {age_years} years")
        if mileage_km >= 150000:
            reasons.append(f"High mileage: {mileage_km:,} km")

        return reasons if reasons else ["Review recommended"]

    def get_pattern_summary(self) -> List[Dict]:
        """
        Get summary of detected patterns across the fleet.

        Returns patterns from approval queue where patterns were detected.
        """
        # Get claims with pattern_summary data
        queue_items = (
            self.db.query(ApprovalQueueDB)
            .filter(ApprovalQueueDB.pattern_summary.isnot(None))
            .all()
        )

        patterns = []
        for item in queue_items:
            if item.pattern_summary:
                # Parse pattern summary (stored as text)
                patterns.append({
                    "pattern_type": "damage_pattern",
                    "vehicle_id": item.vehicle_id,
                    "description": item.pattern_summary[:200]  # Truncate for display
                })

        return patterns

    def get_cost_breakdown_by_category(self) -> List[Dict]:
        """
        Get cost breakdown by vehicle category.

        Returns total damage costs grouped by category.
        """
        # Aggregate by category
        results = (
            self.db.query(
                VehicleDB.category,
                func.sum(VehicleDB.cumulative_damage_ytd_eur).label("total_cost"),
                func.count(VehicleDB.vehicle_id).label("vehicle_count")
            )
            .group_by(VehicleDB.category)
            .all()
        )

        breakdown = []
        for category, total_cost, vehicle_count in results:
            avg_cost = total_cost / vehicle_count if vehicle_count > 0 else 0
            breakdown.append({
                "category": category,
                "total_cost_eur": round(total_cost, 2),
                "vehicle_count": vehicle_count,
                "avg_cost_per_vehicle": round(avg_cost, 2)
            })

        # Sort by total cost descending
        breakdown.sort(key=lambda x: x["total_cost_eur"], reverse=True)

        return breakdown
