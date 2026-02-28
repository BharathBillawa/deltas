"""
Database persistence layer.

SQLite for demo (production-ready for PostgreSQL migration).
"""

from src.persistence.database import (
    Base,
    SessionLocal,
    engine,
    get_db,
    init_db,
    ApprovalQueueDB,
    ClaimDB,
    CustomerDB,
    DamageDB,
    EventLogDB,
    VehicleDB,
)
from src.persistence.repositories import (
    ApprovalQueueRepository,
    ClaimRepository,
    CustomerRepository,
    DamageRepository,
    EventLogRepository,
    VehicleRepository,
)

__all__ = [
    # Database
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    "init_db",
    # DB Models
    "ApprovalQueueDB",
    "ClaimDB",
    "CustomerDB",
    "DamageDB",
    "EventLogDB",
    "VehicleDB",
    # Repositories
    "ApprovalQueueRepository",
    "ClaimRepository",
    "CustomerRepository",
    "DamageRepository",
    "EventLogRepository",
    "VehicleRepository",
]
