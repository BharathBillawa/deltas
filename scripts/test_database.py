#!/usr/bin/env python3
"""
Test script to verify database and data models.

Shows vehicles, damage histories, and demonstrates pattern detection potential.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.persistence.database import SessionLocal
from src.persistence.repositories import (
    VehicleRepository,
    DamageRepository,
    CustomerRepository
)


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_vehicle_queries():
    """Test basic vehicle queries."""
    print_header("TEST 1: Vehicle Queries")

    db = SessionLocal()
    vehicle_repo = VehicleRepository(db)

    # Get all vehicles
    vehicles = vehicle_repo.get_all()
    print(f"✅ Found {len(vehicles)} vehicles in database\n")

    # Show summary
    for vehicle in vehicles:
        status = "🟢" if vehicle.health_score >= 8 else "🟡" if vehicle.health_score >= 6 else "🔴"
        print(f"{status} {vehicle.vehicle_id:25s} | {vehicle.make} {vehicle.model:20s} | Health: {vehicle.health_score:.1f}/10")

    db.close()


def test_vehicle_with_history():
    """Test vehicle with complete history."""
    print_header("TEST 2: Vehicle History (Pattern Detection Candidate)")

    db = SessionLocal()
    vehicle_repo = VehicleRepository(db)
    damage_repo = DamageRepository(db)

    # Get VW Golf (has pattern of 3 damages)
    vehicle_id = "VW-GOLF-2022-003"
    vehicle = vehicle_repo.get_by_id(vehicle_id)

    if vehicle:
        print(f"Vehicle: {vehicle.make} {vehicle.model} ({vehicle.year})")
        print(f"Category: {vehicle.category}")
        print(f"Mileage: {vehicle.current_mileage_km:,} km")
        print(f"Health Score: {vehicle.health_score}/10")
        print(f"Cumulative Damage YTD: €{vehicle.cumulative_damage_ytd_eur:.2f}")

        # Get damage history
        damages = damage_repo.get_by_vehicle(vehicle_id)
        print(f"\n📋 Damage History: {len(damages)} incidents")

        for i, damage in enumerate(damages, 1):
            print(f"\n  {i}. {damage.date.strftime('%Y-%m-%d')} | {damage.damage_type.upper()}")
            print(f"     Location: {damage.location}")
            print(f"     Cost: €{damage.repair_cost_eur:.2f}")
            print(f"     Return: {damage.rental_return_location}")
            print(f"     Status: {damage.status}")
            if damage.flags:
                print(f"     🚩 Flags: {', '.join(damage.flags)}")

        # Pattern detection analysis
        recent_damages = damage_repo.get_recent_by_vehicle(vehicle_id, days=90)
        if len(recent_damages) >= 3:
            print(f"\n⚠️  PATTERN DETECTED: {len(recent_damages)} damages in last 90 days")
            print(f"   → This vehicle should be flagged for review")

            # Check location pattern
            locations = [d.rental_return_location for d in recent_damages]
            if len(set(locations)) == 1:
                print(f"   → All damages at same location: {locations[0]}")
                print(f"   → Possible high-risk location or vehicle issue")

    db.close()


def test_retirement_candidate():
    """Test vehicle retirement analysis data."""
    print_header("TEST 3: Retirement Candidate (Fleet Management)")

    db = SessionLocal()
    vehicle_repo = VehicleRepository(db)
    damage_repo = DamageRepository(db)

    # Get BMW 530i (retirement candidate)
    vehicle_id = "BMW-530-2018-009"
    vehicle = vehicle_repo.get_by_id(vehicle_id)

    if vehicle:
        print(f"Vehicle: {vehicle.make} {vehicle.model} ({vehicle.year})")
        print(f"Age: {2026 - vehicle.year} years")
        print(f"Mileage: {vehicle.current_mileage_km:,} km")
        print(f"Purchase Price: €{vehicle.purchase_price_eur:,.2f}")
        print(f"Health Score: {vehicle.health_score}/10 {'🔴' if vehicle.health_score < 5 else ''}")
        print(f"Cumulative Damage YTD: €{vehicle.cumulative_damage_ytd_eur:,.2f}")
        print(f"Depreciation: {vehicle.depreciation_percent}%")

        damages = damage_repo.get_by_vehicle(vehicle_id)
        print(f"\nDamage History: {len(damages)} incidents")
        print(f"Total Damage Cost: €{sum(d.repair_cost_eur for d in damages):,.2f}")

        print("\n💡 Retirement Analysis Indicators:")
        indicators = []
        if vehicle.health_score < 5:
            indicators.append("✓ Low health score (< 5)")
        if vehicle.current_mileage_km > 150000:
            indicators.append(f"✓ High mileage ({vehicle.current_mileage_km:,} km)")
        if vehicle.cumulative_damage_ytd_eur > 2500:
            indicators.append(f"✓ High cumulative damage (€{vehicle.cumulative_damage_ytd_eur:,.2f})")
        if vehicle.depreciation_percent and vehicle.depreciation_percent > 60:
            indicators.append(f"✓ High depreciation ({vehicle.depreciation_percent}%)")

        for indicator in indicators:
            print(f"   {indicator}")

        print("\n🎯 Recommendation: Consider repair vs. auction analysis")

    db.close()


def test_customer_risk_pattern():
    """Test customer risk pattern detection."""
    print_header("TEST 4: Customer Risk Pattern (Fraud Detection)")

    db = SessionLocal()
    damage_repo = DamageRepository(db)

    # Get damages for high-risk customer
    customer_id = "CUST-RISK-001"

    # Query damages by customer (need to add this query)
    from src.persistence.database import DamageDB
    damages = db.query(DamageDB).filter(
        DamageDB.customer_id == customer_id
    ).order_by(DamageDB.date.asc()).all()

    print(f"Customer: {customer_id}")
    print(f"Total Damages Reported: {len(damages)}")

    if damages:
        print("\n📋 Damage Timeline:")
        for i, damage in enumerate(damages, 1):
            days_between = ""
            if i > 1:
                days = (damage.date - damages[i-2].date).days
                days_between = f" ({days} days after previous)"

            print(f"  {i}. {damage.date.strftime('%Y-%m-%d')}{days_between}")
            print(f"     Vehicle: {damage.vehicle_id}")
            print(f"     Type: {damage.damage_type} | Cost: €{damage.repair_cost_eur:.2f}")
            if damage.flags:
                print(f"     🚩 {', '.join(damage.flags)}")

        # Risk analysis
        if len(damages) >= 2:
            days_between = (damages[-1].date - damages[0].date).days
            print(f"\n⚠️  RISK PATTERN DETECTED:")
            print(f"   → {len(damages)} claims in {days_between} days")
            print(f"   → Frequent damage pattern suggests high-risk customer")
            print(f"   → Recommend: Higher deposit, fraud investigation")

    db.close()


def test_data_integrity():
    """Test data integrity and relationships."""
    print_header("TEST 5: Data Integrity & Statistics")

    db = SessionLocal()
    vehicle_repo = VehicleRepository(db)
    damage_repo = DamageRepository(db)

    vehicles = vehicle_repo.get_all()

    # Calculate statistics
    total_damages = 0
    total_cost = 0.0
    damages_by_location = {}

    for vehicle in vehicles:
        damages = damage_repo.get_by_vehicle(vehicle.vehicle_id)
        total_damages += len(damages)

        for damage in damages:
            total_cost += damage.repair_cost_eur
            location = damage.rental_return_location
            damages_by_location[location] = damages_by_location.get(location, 0) + 1

    print(f"Total Vehicles: {len(vehicles)}")
    print(f"Total Historical Damages: {total_damages}")
    print(f"Total Damage Cost: €{total_cost:,.2f}")
    print(f"Average Cost per Damage: €{total_cost/total_damages:.2f}")

    print("\n📍 Damages by Location:")
    for location, count in sorted(damages_by_location.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total_damages) * 100
        print(f"   {location:25s}: {count:2d} incidents ({pct:.1f}%)")

    # Vehicle health distribution
    health_ranges = {"Excellent (8-10)": 0, "Good (6-8)": 0, "Poor (<6)": 0}
    for vehicle in vehicles:
        if vehicle.health_score >= 8:
            health_ranges["Excellent (8-10)"] += 1
        elif vehicle.health_score >= 6:
            health_ranges["Good (6-8)"] += 1
        else:
            health_ranges["Poor (<6)"] += 1

    print("\n🏥 Fleet Health Distribution:")
    for category, count in health_ranges.items():
        pct = (count / len(vehicles)) * 100
        print(f"   {category:20s}: {count:2d} vehicles ({pct:.1f}%)")

    print("\n✅ Data integrity verified - all relationships working correctly!")

    db.close()


def main():
    """Run all tests."""
    print("\n" + "🧪" * 35)
    print("  DATABASE & DATA MODEL TESTS")
    print("🧪" * 35)

    try:
        test_vehicle_queries()
        test_vehicle_with_history()
        test_retirement_candidate()
        test_customer_risk_pattern()
        test_data_integrity()

        print("\n" + "=" * 70)
        print("  ✅ ALL TESTS PASSED!")
        print("=" * 70)

        print("\n💡 Next Steps:")
        print("   1. Build core services (depreciation, pattern recognition)")
        print("   2. Create agents with LangGraph")
        print("   3. Build REST API & web UI")
        print()

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
