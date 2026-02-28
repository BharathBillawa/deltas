#!/usr/bin/env python3
"""
Initialize database and load sample data.

Loads the 12 realistic vehicles from fleet_data.json into the database.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.persistence.database import init_db, SessionLocal
from src.persistence.repositories import VehicleRepository, DamageRepository, CustomerRepository


def load_fleet_data():
    """Load vehicle fleet data from JSON."""
    data_path = Path(__file__).parent.parent / "data" / "vehicle_fleet" / "fleet_data.json"
    with open(data_path, "r") as f:
        return json.load(f)


def parse_datetime(date_str: str) -> datetime:
    """Parse datetime string to datetime object."""
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def load_vehicles(db_session):
    """Load vehicles into database."""
    fleet_data = load_fleet_data()
    vehicle_repo = VehicleRepository(db_session)
    damage_repo = DamageRepository(db_session)
    customer_repo = CustomerRepository(db_session)

    print(f"Loading {len(fleet_data['vehicles'])} vehicles...")

    for vehicle_data in fleet_data["vehicles"]:
        vehicle_id = vehicle_data["vehicle_id"]
        print(f"  Loading {vehicle_id}...")

        # Parse dates
        purchase_date = parse_datetime(vehicle_data["purchase_date"])
        last_service_date = parse_datetime(vehicle_data["last_service_date"]) if vehicle_data.get("last_service_date") else None

        # Parse service history
        service_history = []
        for service in vehicle_data.get("service_history", []):
            service_history.append({
                "date": parse_datetime(service["date"]).isoformat(),
                "type": service["type"],
                "cost_eur": service["cost_eur"],
                "mileage_km": service["mileage_km"]
            })

        # Create vehicle from Pydantic model
        from src.models import VehicleInfo, VehicleCategory

        vehicle = VehicleInfo(
            vehicle_id=vehicle_id,
            category=VehicleCategory(vehicle_data["category"]),
            make=vehicle_data["make"],
            model=vehicle_data["model"],
            year=vehicle_data["year"],
            color=vehicle_data["color"],
            vin=vehicle_data["vin"],
            license_plate=vehicle_data["license_plate"],
            purchase_date=purchase_date,
            purchase_price_eur=vehicle_data["purchase_price_eur"],
            current_mileage_km=vehicle_data["current_mileage_km"],
            last_service_date=last_service_date,
            health_score=vehicle_data["health_score"],
            cumulative_damage_ytd_eur=vehicle_data.get("cumulative_damage_ytd_eur", 0.0),
            depreciation_percent=vehicle_data.get("depreciation_percent"),
            notes=vehicle_data.get("notes")
        )

        # Add service history and rental summary
        vehicle.service_history = [
            type("ServiceRecord", (), {
                "model_dump": lambda self=s: s,
                "date": s["date"],
                "type": s["type"],
                "cost_eur": s["cost_eur"],
                "mileage_km": s["mileage_km"]
            })() for s in service_history
        ]

        if vehicle_data.get("rental_history_summary"):
            from src.models import RentalHistorySummary
            vehicle.rental_history_summary = RentalHistorySummary(
                **vehicle_data["rental_history_summary"]
            )

        # Create vehicle in database
        vehicle_repo.create(vehicle)

        # Load damage history
        for damage in vehicle_data.get("damage_history", []):
            damage_dict = {
                "vehicle_id": vehicle_id,
                "date": parse_datetime(damage["date"]),
                "damage_type": damage["damage_type"],
                "severity": damage["severity"],
                "location": damage["location"],
                "description": damage["description"],
                "repair_cost_eur": damage["repair_cost_eur"],
                "labor_hours": damage["labor_hours"],
                "labor_rate_eur": damage["labor_rate_eur"],
                "parts_cost_eur": damage["parts_cost_eur"],
                "rental_return_location": damage["rental_return_location"],
                "customer_id": damage["customer_id"],
                "status": damage["status"],
                "insurance_claim": damage.get("insurance_claim", False),
                "flags": damage.get("flags", [])
            }
            damage_repo.create(damage_dict)

            # Update customer records
            customer_id = damage["customer_id"]
            customer_repo.create_or_update(
                customer_id=customer_id,
                customer_type="regular",
                total_rentals=1,  # Simplified for demo
                damages_reported=1
            )

    print(f"✅ Loaded {len(fleet_data['vehicles'])} vehicles successfully!")


def main():
    """Initialize database and load data."""
    print("=== Initializing Database ===\n")

    # Create tables
    print("Creating database tables...")
    init_db()
    print("✅ Tables created!\n")

    # Load data
    print("Loading sample data...")
    db = SessionLocal()
    try:
        load_vehicles(db)
        print("\n✅ Database initialized successfully!")
        print(f"\nDatabase location: deltas.db")
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
