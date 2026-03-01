"""
Database setup and SQLAlchemy models for persistence.

Uses SQLite for demo (production-ready for PostgreSQL migration).
"""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from src.config.settings import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# === Vehicle Tables ===

class VehicleDB(Base):
    """Vehicle master data."""
    __tablename__ = "vehicles"

    vehicle_id = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    color = Column(String)
    vin = Column(String, unique=True, index=True)
    license_plate = Column(String, unique=True, index=True)

    purchase_date = Column(DateTime, nullable=False)
    purchase_price_eur = Column(Float, nullable=False)
    current_mileage_km = Column(Integer, nullable=False)
    last_service_date = Column(DateTime)

    # Health metrics
    health_score = Column(Float, default=10.0)
    cumulative_damage_ytd_eur = Column(Float, default=0.0)
    depreciation_percent = Column(Float)

    # JSON fields for history (flexible schema)
    service_history = Column(JSON, default=list)
    rental_history_summary = Column(JSON)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    damages = relationship("DamageDB", back_populates="vehicle")
    claims = relationship("ClaimDB", back_populates="vehicle")


class DamageDB(Base):
    """Historical damage records for pattern analysis."""
    __tablename__ = "damages"

    damage_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=False, index=True)

    date = Column(DateTime, nullable=False, index=True)
    damage_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    location = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    repair_cost_eur = Column(Float, nullable=False)
    labor_hours = Column(Float)
    labor_rate_eur = Column(Float)
    parts_cost_eur = Column(Float)

    rental_return_location = Column(String)
    customer_id = Column(String, index=True)
    status = Column(String, nullable=False)
    insurance_claim = Column(Boolean, default=False)

    flags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    vehicle = relationship("VehicleDB", back_populates="damages")


# === Claims Processing Tables ===

class ClaimDB(Base):
    """Damage claims being processed."""
    __tablename__ = "claims"

    claim_id = Column(String, primary_key=True, index=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    rental_agreement_id = Column(String, nullable=False)

    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    return_location = Column(String, nullable=False)

    # Damage assessment (JSON for flexibility)
    damage_assessment = Column(JSON, nullable=False)

    # Processing results (JSON)
    cost_estimate = Column(JSON)
    validation_result = Column(JSON)
    invoice = Column(JSON)
    retirement_analysis = Column(JSON)

    # Status
    status = Column(String, default="pending", index=True)
    workflow_complete = Column(Boolean, default=False)
    requires_human_approval = Column(Boolean, default=False)
    approval_granted = Column(Boolean)

    # Metadata
    workflow_started_at = Column(DateTime)
    workflow_completed_at = Column(DateTime)
    processing_time_seconds = Column(Float)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    vehicle = relationship("VehicleDB", back_populates="claims")
    approval_queue_item = relationship("ApprovalQueueDB", back_populates="claim", uselist=False)


# === Approval Queue Table ===

class ApprovalQueueDB(Base):
    """Human-in-the-loop approval queue."""
    __tablename__ = "approval_queue"

    queue_id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, ForeignKey("claims.claim_id"), nullable=False, unique=True, index=True)

    # Claim summary
    vehicle_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    damage_description = Column(Text, nullable=False)
    estimated_cost_eur = Column(Float, nullable=False)

    # Escalation details
    routing_decision = Column(String, nullable=False)
    escalation_reason = Column(String, nullable=False)
    flags = Column(JSON, default=list)

    # Context for reviewer
    vehicle_health_score = Column(Float)
    cumulative_damage_ytd_eur = Column(Float)
    pattern_summary = Column(Text)

    # Queue management
    assigned_to = Column(String)
    priority = Column(Integer, default=3)  # 1=highest, 5=lowest
    status = Column(String, default="pending_review", index=True)
    sla_deadline = Column(DateTime)

    # Approval decision
    reviewer_id = Column(String)
    approved = Column(Boolean)
    decision_notes = Column(Text)
    decision_timestamp = Column(DateTime)

    timestamp_added = Column(DateTime, default=datetime.now, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    claim = relationship("ClaimDB", back_populates="approval_queue_item")


# === Customer Table ===

class CustomerDB(Base):
    """Customer rental history and risk profiles."""
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True, index=True)
    customer_name = Column(String)
    customer_type = Column(String, default="regular")  # regular, vip, corporate
    vip_status = Column(Boolean, default=False)

    # Rental history
    total_rentals = Column(Integer, default=0)
    damages_reported = Column(Integer, default=0)
    damage_rate_percent = Column(Float, default=0.0)
    disputed_claims = Column(Integer, default=0)

    # Risk scoring
    risk_score = Column(Float, default=0.0)
    is_high_risk = Column(Boolean, default=False)
    risk_factors = Column(JSON, default=list)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# === Event Log Table ===

class EventLogDB(Base):
    """Audit trail of all events."""
    __tablename__ = "event_logs"

    event_id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now, index=True)
    priority = Column(String, default="normal")

    source_service = Column(String, nullable=False)
    source_agent = Column(String)

    claim_id = Column(String, index=True)
    vehicle_id = Column(String, index=True)
    customer_id = Column(String, index=True)

    payload = Column(JSON, default=dict)
    correlation_id = Column(String, index=True)
    tags = Column(JSON, default=list)

    processed_at = Column(DateTime, default=datetime.now)
    processing_duration_ms = Column(Float)
    subscribers_notified = Column(Integer, default=0)
    errors = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.now)


# === Database initialization ===

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency for FastAPI routes.

    Yields database session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create tables on import if they don't exist
if __name__ == "__main__":
    print("Creating database tables...")
    init_db()
    print("Database tables created successfully!")
