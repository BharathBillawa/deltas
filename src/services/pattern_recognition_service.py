"""
Pattern Recognition Service - Fleet intelligence and risk analysis.

THE DIFFERENTIATOR: Multi-stakeholder value beyond simple claims processing.
Provides tactical (fraud detection), operational (vehicle rotation), and strategic (retirement analysis) insights.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.models.routing import PatternDetection, CustomerRiskProfile
from src.persistence.database import VehicleDB, DamageDB, CustomerDB

logger = logging.getLogger(__name__)


class PatternRecognitionService:
    """
    Detect damage patterns and assess risk for vehicles and customers.

    Features:
    - Vehicle pattern detection (frequent damage, location correlation)
    - Customer risk scoring and profiling
    - Actionable recommendations for fleet management
    - Graceful handling of vehicles/customers with no history
    """

    def __init__(self, db_session: Session):
        """
        Initialize pattern recognition service.

        Args:
            db_session: Database session for querying vehicle/damage history
        """
        self.db = db_session

    def analyze_vehicle_patterns(self, vehicle_id: str) -> List[PatternDetection]:
        """
        Detect patterns in vehicle damage history.

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            List of detected patterns with severity and recommendations
        """
        patterns = []

        # Get vehicle from database
        vehicle = self.db.query(VehicleDB).filter(VehicleDB.vehicle_id == vehicle_id).first()

        if not vehicle:
            logger.warning(f"Vehicle {vehicle_id} not found")
            return patterns

        # Get damage history (last 12 months)
        twelve_months_ago = datetime.now() - timedelta(days=365)
        damages = (
            self.db.query(DamageDB)
            .filter(DamageDB.vehicle_id == vehicle_id)
            .filter(DamageDB.date >= twelve_months_ago)
            .order_by(DamageDB.date.desc())
            .all()
        )

        if not damages:
            logger.debug(f"No damage history for vehicle {vehicle_id}")
            return patterns

        # Pattern 1: Frequent damage (3+ in 90 days)
        frequent_pattern = self._detect_frequent_damage(damages)
        if frequent_pattern:
            patterns.append(frequent_pattern)

        # Pattern 2: Location correlation (same location repeatedly)
        location_pattern = self._detect_location_correlation(damages)
        if location_pattern:
            patterns.append(location_pattern)

        # Pattern 3: Damage type patterns (same type repeatedly)
        type_pattern = self._detect_damage_type_pattern(damages)
        if type_pattern:
            patterns.append(type_pattern)

        return patterns

    def _detect_frequent_damage(self, damages: List[DamageDB]) -> Optional[PatternDetection]:
        """Detect if vehicle has frequent damage (3+ in 90 days)."""
        if len(damages) < 3:
            return None

        ninety_days_ago = datetime.now() - timedelta(days=90)

        recent_damages = [d for d in damages if d.date >= ninety_days_ago]

        if len(recent_damages) >= 3:
            time_between = []
            for i in range(len(recent_damages) - 1):
                delta = (recent_damages[i].date - recent_damages[i+1].date).days
                time_between.append(delta)

            avg_days_between = sum(time_between) / len(time_between) if time_between else 0

            return PatternDetection(
                pattern_type="frequent_damage",
                severity="high",
                confidence=0.9,
                description=f"{len(recent_damages)} damages in last 90 days",
                evidence={
                    "damage_count": len(recent_damages),
                    "time_window_days": 90,
                    "avg_days_between_damages": round(avg_days_between, 1),
                    "damage_dates": [d.date.isoformat() for d in recent_damages[:5]]
                },
                recommendations=[
                    "Rotate vehicle out of high-risk location",
                    "Inspect vehicle for underlying issues",
                    "Consider customer behavior analysis"
                ]
            )

        return None

    def _detect_location_correlation(self, damages: List[DamageDB]) -> Optional[PatternDetection]:
        """Detect if damages occur repeatedly at same location."""
        if len(damages) < 2:
            return None

        # Count damages by rental location
        location_counts: Dict[str, int] = {}
        for damage in damages:
            if damage.rental_return_location:
                loc = damage.rental_return_location
                location_counts[loc] = location_counts.get(loc, 0) + 1

        if not location_counts:
            return None

        # Find most common location
        max_location = max(location_counts, key=location_counts.get)
        max_count = location_counts[max_location]

        # If 50%+ of damages at one location, flag it
        if max_count >= 2 and max_count / len(damages) >= 0.5:
            return PatternDetection(
                pattern_type="location_correlation",
                severity="medium",
                confidence=0.85,
                description=f"{max_count}/{len(damages)} damages at {max_location}",
                evidence={
                    "primary_location": max_location,
                    "damage_count_at_location": max_count,
                    "total_damages": len(damages),
                    "percentage": round(100 * max_count / len(damages), 1)
                },
                recommendations=[
                    f"Rotate vehicle away from {max_location}",
                    "Investigate location-specific risks",
                    "Review parking guidance for this location"
                ]
            )

        return None

    def _detect_damage_type_pattern(self, damages: List[DamageDB]) -> Optional[PatternDetection]:
        """Detect if same damage type occurs repeatedly."""
        if len(damages) < 3:
            return None

        # Count by damage type
        type_counts: Dict[str, int] = {}
        for damage in damages:
            dtype = damage.damage_type
            type_counts[dtype] = type_counts.get(dtype, 0) + 1

        # Find most common type
        max_type = max(type_counts, key=type_counts.get)
        max_count = type_counts[max_type]

        # If 60%+ same type, flag it
        if max_count >= 3 and max_count / len(damages) >= 0.6:
            return PatternDetection(
                pattern_type="damage_type_pattern",
                severity="low",
                confidence=0.75,
                description=f"Repeated {max_type} damage ({max_count} times)",
                evidence={
                    "damage_type": max_type,
                    "occurrence_count": max_count,
                    "total_damages": len(damages),
                    "percentage": round(100 * max_count / len(damages), 1)
                },
                recommendations=[
                    f"Review {max_type} vulnerability for this vehicle model",
                    "Check if specific customer behavior pattern exists"
                ]
            )

        return None

    def analyze_customer_risk(self, customer_id: str) -> CustomerRiskProfile:
        """
        Analyze customer damage history and calculate risk score.

        Args:
            customer_id: Customer identifier

        Returns:
            CustomerRiskProfile with risk score and recommendations
        """
        # Get customer from database
        customer = self.db.query(CustomerDB).filter(CustomerDB.customer_id == customer_id).first()

        if not customer:
            logger.warning(f"Customer {customer_id} not found, returning neutral profile")
            return self._create_neutral_risk_profile(customer_id)

        # Get all damages by this customer (last 12 months)
        twelve_months_ago = datetime.now() - timedelta(days=365)
        damages = (
            self.db.query(DamageDB)
            .filter(DamageDB.customer_id == customer_id)
            .filter(DamageDB.date >= twelve_months_ago)
            .all()
        )

        # Calculate metrics
        damage_count = len(damages)
        total_cost = sum(d.repair_cost_eur for d in damages if d.repair_cost_eur)

        # Get total rentals from customer record
        total_rentals = customer.total_rentals if hasattr(customer, 'total_rentals') else 1

        # Calculate damage rate
        damage_rate = (damage_count / total_rentals) * 100 if total_rentals > 0 else 0

        # Check for frequent claims (2+ in 60 days)
        sixty_days_ago = datetime.now() - timedelta(days=60)
        recent_damages = [d for d in damages if d.date >= sixty_days_ago]
        is_frequent_claimer = len(recent_damages) >= 2

        # Calculate risk score (0-10 scale)
        risk_score = self._calculate_risk_score(
            damage_count=damage_count,
            damage_rate=damage_rate,
            total_cost=total_cost,
            recent_damage_count=len(recent_damages)
        )

        # Identify risk factors
        risk_factors = []
        if damage_rate > 10:
            risk_factors.append(f"High damage rate: {damage_rate:.1f}%")
        if is_frequent_claimer:
            risk_factors.append(f"Frequent claimer: {len(recent_damages)} in 60 days")
        if total_cost > 1500:
            risk_factors.append(f"High total cost: €{total_cost:.0f}")
        if damage_count >= 3:
            risk_factors.append(f"Multiple incidents: {damage_count} damages")

        # Generate recommendations
        recommendations = self._generate_customer_recommendations(
            risk_score=risk_score,
            is_frequent_claimer=is_frequent_claimer,
            damage_rate=damage_rate
        )

        return CustomerRiskProfile(
            customer_id=customer_id,
            total_damages=damage_count,
            total_cost_eur=total_cost,
            damage_rate_percent=round(damage_rate, 2),
            is_frequent_claimer=is_frequent_claimer,
            risk_score=round(risk_score, 1),
            risk_factors=risk_factors,
            recommendations=recommendations,
            analysis_date=datetime.now()
        )

    def _calculate_risk_score(
        self,
        damage_count: int,
        damage_rate: float,
        total_cost: float,
        recent_damage_count: int
    ) -> float:
        """
        Calculate risk score (0-10) based on multiple factors.

        0-3: Low risk
        4-6: Medium risk
        7-10: High risk
        """
        score = 0.0

        # Damage count factor (0-3 points)
        if damage_count == 0:
            score += 0
        elif damage_count == 1:
            score += 1
        elif damage_count == 2:
            score += 2
        else:
            score += 3

        # Damage rate factor (0-3 points)
        if damage_rate < 5:
            score += 0
        elif damage_rate < 10:
            score += 1
        elif damage_rate < 20:
            score += 2
        else:
            score += 3

        # Cost factor (0-2 points)
        if total_cost < 500:
            score += 0
        elif total_cost < 1500:
            score += 1
        else:
            score += 2

        # Recent activity factor (0-2 points)
        if recent_damage_count >= 2:
            score += 2
        elif recent_damage_count == 1:
            score += 1

        return min(score, 10.0)

    def _generate_customer_recommendations(
        self,
        risk_score: float,
        is_frequent_claimer: bool,
        damage_rate: float
    ) -> List[str]:
        """Generate actionable recommendations based on risk profile."""
        recommendations = []

        if risk_score >= 7:
            recommendations.append("Require higher deposit for future rentals")
            recommendations.append("Flag account for fraud investigation")
        elif risk_score >= 4:
            recommendations.append("Monitor account for escalation")

        if is_frequent_claimer:
            recommendations.append("Review rental agreements and customer education")

        if damage_rate > 15:
            recommendations.append("Consider limiting vehicle categories available")

        if not recommendations:
            recommendations.append("Continue normal rental process")

        return recommendations

    def _create_neutral_risk_profile(self, customer_id: str) -> CustomerRiskProfile:
        """Create neutral profile for customers with no history."""
        return CustomerRiskProfile(
            customer_id=customer_id,
            total_damages=0,
            total_cost_eur=0.0,
            damage_rate_percent=0.0,
            is_frequent_claimer=False,
            risk_score=0.0,
            risk_factors=[],
            recommendations=["New customer - no history available"],
            analysis_date=datetime.now()
        )

    def get_vehicle_health_score(self, vehicle_id: str) -> Tuple[float, str]:
        """
        Calculate vehicle health score (0-10) based on damage history.

        Returns:
            Tuple of (score, status_label)
        """
        vehicle = self.db.query(VehicleDB).filter(VehicleDB.vehicle_id == vehicle_id).first()

        if not vehicle:
            return (5.0, "unknown")

        # Use pre-calculated health score if available
        if hasattr(vehicle, 'health_score') and vehicle.health_score:
            score = vehicle.health_score
        else:
            # Calculate from damage history
            damages = self.db.query(DamageDB).filter(
                DamageDB.vehicle_id == vehicle_id
            ).all()

            # Simple calculation: start at 10, deduct for damages
            score = 10.0
            score -= len(damages) * 0.5  # -0.5 per damage
            score = max(0.0, score)

        # Determine status label
        if score >= 8:
            status = "excellent"
        elif score >= 6:
            status = "good"
        elif score >= 4:
            status = "fair"
        else:
            status = "poor"

        return (score, status)
