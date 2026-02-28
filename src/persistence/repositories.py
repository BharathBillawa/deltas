"""
Repository layer for database operations.

Provides clean interface for data access, hiding SQLAlchemy details.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models import VehicleInfo, DamageClaim, ApprovalQueueItem
from src.persistence.database import (
    VehicleDB,
    DamageDB,
    ClaimDB,
    ApprovalQueueDB,
    CustomerDB,
    EventLogDB,
)


class VehicleRepository:
    """Repository for vehicle operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, vehicle_id: str) -> Optional[VehicleDB]:
        """Get vehicle by ID."""
        return self.db.query(VehicleDB).filter(VehicleDB.vehicle_id == vehicle_id).first()

    def get_all(self) -> List[VehicleDB]:
        """Get all vehicles."""
        return self.db.query(VehicleDB).all()

    def create(self, vehicle: VehicleInfo) -> VehicleDB:
        """Create new vehicle record."""
        db_vehicle = VehicleDB(
            vehicle_id=vehicle.vehicle_id,
            category=vehicle.category.value,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            color=vehicle.color,
            vin=vehicle.vin,
            license_plate=vehicle.license_plate,
            purchase_date=vehicle.purchase_date,
            purchase_price_eur=vehicle.purchase_price_eur,
            current_mileage_km=vehicle.current_mileage_km,
            last_service_date=vehicle.last_service_date,
            health_score=vehicle.health_score,
            cumulative_damage_ytd_eur=vehicle.cumulative_damage_ytd_eur,
            depreciation_percent=vehicle.depreciation_percent,
            service_history=[s.model_dump() for s in vehicle.service_history],
            rental_history_summary=vehicle.rental_history_summary.model_dump() if vehicle.rental_history_summary else None,
            notes=vehicle.notes,
        )
        self.db.add(db_vehicle)
        self.db.commit()
        self.db.refresh(db_vehicle)
        return db_vehicle

    def update_health_score(self, vehicle_id: str, health_score: float):
        """Update vehicle health score."""
        vehicle = self.get_by_id(vehicle_id)
        if vehicle:
            vehicle.health_score = health_score
            vehicle.updated_at = datetime.utcnow()
            self.db.commit()

    def add_cumulative_damage(self, vehicle_id: str, damage_cost_eur: float):
        """Add to cumulative damage cost."""
        vehicle = self.get_by_id(vehicle_id)
        if vehicle:
            vehicle.cumulative_damage_ytd_eur += damage_cost_eur
            vehicle.updated_at = datetime.utcnow()
            self.db.commit()


class DamageRepository:
    """Repository for damage history operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_vehicle(self, vehicle_id: str) -> List[DamageDB]:
        """Get all damages for a vehicle."""
        return self.db.query(DamageDB).filter(
            DamageDB.vehicle_id == vehicle_id
        ).order_by(DamageDB.date.desc()).all()

    def get_recent_by_vehicle(self, vehicle_id: str, days: int = 90) -> List[DamageDB]:
        """Get recent damages for a vehicle (last N days)."""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(DamageDB).filter(
            DamageDB.vehicle_id == vehicle_id,
            DamageDB.date >= cutoff_date
        ).order_by(DamageDB.date.desc()).all()

    def create(self, damage: dict) -> DamageDB:
        """Create new damage record."""
        db_damage = DamageDB(**damage)
        self.db.add(db_damage)
        self.db.commit()
        self.db.refresh(db_damage)
        return db_damage


class ClaimRepository:
    """Repository for claim operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, claim_id: str) -> Optional[ClaimDB]:
        """Get claim by ID."""
        return self.db.query(ClaimDB).filter(ClaimDB.claim_id == claim_id).first()

    def get_all(self, status: Optional[str] = None) -> List[ClaimDB]:
        """Get all claims, optionally filtered by status."""
        query = self.db.query(ClaimDB)
        if status:
            query = query.filter(ClaimDB.status == status)
        return query.order_by(ClaimDB.timestamp.desc()).all()

    def create(self, claim: DamageClaim) -> ClaimDB:
        """Create new claim record."""
        db_claim = ClaimDB(
            claim_id=claim.claim_id,
            vehicle_id=claim.vehicle_id,
            customer_id=claim.customer_id,
            rental_agreement_id=claim.rental_agreement_id,
            timestamp=claim.timestamp,
            return_location=claim.return_location,
            damage_assessment=claim.damage_assessment.model_dump(),
            workflow_started_at=datetime.utcnow(),
        )
        self.db.add(db_claim)
        self.db.commit()
        self.db.refresh(db_claim)
        return db_claim

    def update_status(self, claim_id: str, status: str):
        """Update claim status."""
        claim = self.get_by_id(claim_id)
        if claim:
            claim.status = status
            claim.updated_at = datetime.utcnow()
            self.db.commit()

    def update_cost_estimate(self, claim_id: str, cost_estimate: dict):
        """Update cost estimate for claim."""
        claim = self.get_by_id(claim_id)
        if claim:
            claim.cost_estimate = cost_estimate
            claim.updated_at = datetime.utcnow()
            self.db.commit()

    def update_validation_result(self, claim_id: str, validation_result: dict):
        """Update validation result for claim."""
        claim = self.get_by_id(claim_id)
        if claim:
            claim.validation_result = validation_result
            claim.requires_human_approval = validation_result.get("requires_human_review", False)
            claim.updated_at = datetime.utcnow()
            self.db.commit()

    def mark_complete(self, claim_id: str):
        """Mark claim as complete."""
        claim = self.get_by_id(claim_id)
        if claim:
            claim.workflow_complete = True
            claim.workflow_completed_at = datetime.utcnow()
            if claim.workflow_started_at:
                delta = claim.workflow_completed_at - claim.workflow_started_at
                claim.processing_time_seconds = delta.total_seconds()
            claim.updated_at = datetime.utcnow()
            self.db.commit()


class ApprovalQueueRepository:
    """Repository for approval queue operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, queue_id: str) -> Optional[ApprovalQueueDB]:
        """Get queue item by ID."""
        return self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.queue_id == queue_id
        ).first()

    def get_pending(self) -> List[ApprovalQueueDB]:
        """Get all pending approval items."""
        return self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.status == "pending_review"
        ).order_by(
            ApprovalQueueDB.priority.asc(),
            ApprovalQueueDB.timestamp_added.asc()
        ).all()

    def get_by_claim_id(self, claim_id: str) -> Optional[ApprovalQueueDB]:
        """Get queue item by claim ID."""
        return self.db.query(ApprovalQueueDB).filter(
            ApprovalQueueDB.claim_id == claim_id
        ).first()

    def create(self, queue_item: ApprovalQueueItem) -> ApprovalQueueDB:
        """Create new queue item."""
        db_item = ApprovalQueueDB(
            queue_id=queue_item.queue_id,
            claim_id=queue_item.claim_id,
            vehicle_id=queue_item.vehicle_id,
            customer_id=queue_item.customer_id,
            damage_description=queue_item.damage_description,
            estimated_cost_eur=queue_item.estimated_cost_eur,
            routing_decision=queue_item.routing_decision.value,
            escalation_reason=queue_item.escalation_reason.value,
            flags=queue_item.flags,
            vehicle_health_score=queue_item.vehicle_health_score,
            cumulative_damage_ytd_eur=queue_item.cumulative_damage_ytd_eur,
            pattern_summary=queue_item.pattern_summary,
            assigned_to=queue_item.assigned_to,
            priority=queue_item.priority,
            status=queue_item.status,
            sla_deadline=queue_item.sla_deadline,
        )
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return db_item

    def update_decision(self, queue_id: str, approved: bool, reviewer_id: str, notes: Optional[str] = None):
        """Record approval decision."""
        item = self.get_by_id(queue_id)
        if item:
            item.approved = approved
            item.reviewer_id = reviewer_id
            item.decision_notes = notes
            item.decision_timestamp = datetime.utcnow()
            item.status = "approved" if approved else "rejected"
            item.updated_at = datetime.utcnow()
            self.db.commit()


class CustomerRepository:
    """Repository for customer operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, customer_id: str) -> Optional[CustomerDB]:
        """Get customer by ID."""
        return self.db.query(CustomerDB).filter(
            CustomerDB.customer_id == customer_id
        ).first()

    def create_or_update(self, customer_id: str, **kwargs) -> CustomerDB:
        """Create new customer or update existing."""
        customer = self.get_by_id(customer_id)
        if customer:
            for key, value in kwargs.items():
                setattr(customer, key, value)
            customer.updated_at = datetime.utcnow()
        else:
            customer = CustomerDB(customer_id=customer_id, **kwargs)
            self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer


class EventLogRepository:
    """Repository for event log operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, event: dict) -> EventLogDB:
        """Create new event log entry."""
        db_event = EventLogDB(**event)
        self.db.add(db_event)
        self.db.commit()
        self.db.refresh(db_event)
        return db_event

    def get_by_claim_id(self, claim_id: str) -> List[EventLogDB]:
        """Get all events for a claim."""
        return self.db.query(EventLogDB).filter(
            EventLogDB.claim_id == claim_id
        ).order_by(EventLogDB.timestamp.asc()).all()

    def get_recent(self, limit: int = 100) -> List[EventLogDB]:
        """Get recent events."""
        return self.db.query(EventLogDB).order_by(
            EventLogDB.timestamp.desc()
        ).limit(limit).all()
