# API Walkthrough

REST API for damage claims automation system.

## Starting the Server

```bash
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Server runs on http://localhost:8000

Interactive docs: http://localhost:8000/docs
OpenAPI spec: http://localhost:8000/openapi.json

## Quick Test

```bash
# Health check
curl http://localhost:8000/health

# Submit a claim (minor damage - will auto-approve)
curl -X POST http://localhost:8000/claims/ \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "CLM-TEST-001",
    "vehicle_id": "VW-POLO-2023-001",
    "customer_id": "CUST-5678",
    "rental_agreement_id": "RNT-2026-001",
    "return_location": "Munich_Airport",
    "damage_type": "scratch",
    "severity": "minor",
    "location": "rear_bumper",
    "description": "Small scratch on rear bumper",
    "affected_parts": ["rear_bumper"],
    "photos": ["photo1.jpg"],
    "inspector_id": "INSP-001"
  }'
```

## Endpoints

### Claims

**Submit Claim**
```bash
POST /claims/
```
Processes claim through workflow: cost estimation, pattern recognition, validation, routing.
Returns auto-approve or sends to queue for human review.

**Get Claim Status**
```bash
GET /claims/{claim_id}
```
Returns workflow state, cost estimate, routing decision, flags.

### Approval Queue

**List Pending Approvals**
```bash
GET /queue/
```
Returns all claims awaiting human review, sorted by priority.

**Get Queue Item**
```bash
GET /queue/{queue_id}
```

**Approve Claim**
```bash
POST /queue/{queue_id}/approve
Body: {"reviewer_id": "REV-001", "notes": "Approved"}
```

**Reject Claim**
```bash
POST /queue/{queue_id}/reject
Body: {"reviewer_id": "REV-001", "reason": "Insufficient evidence"}
```

**Queue Statistics**
```bash
GET /queue/stats/summary
```
Returns pending, approved, rejected counts and average review time.

### Analytics

**Fleet Health**
```bash
GET /analytics/fleet-health
```
Returns:
- Total vehicles
- Average health score
- Vehicles needing attention
- Total damage cost YTD
- Health distribution (excellent/good/fair/poor)

**Location Risk Analysis**
```bash
GET /analytics/locations?limit=10
```
Damage statistics by return location, sorted by risk score.

**Pattern Summary**
```bash
GET /analytics/patterns?limit=20
```
Detected patterns across the fleet.

**Retirement Candidates**
```bash
GET /analytics/retirement-candidates?limit=10
```
Vehicles with high costs, low health, or high mileage.

**Cost Breakdown**
```bash
GET /analytics/cost-breakdown?period=ytd
```
Damage costs by vehicle category.

### Events

**Claim Events**
```bash
GET /events/{claim_id}?limit=100
```
Audit trail for a specific claim.

**Recent Events**
```bash
GET /events/recent/all?limit=50
```
Most recent events across all claims.

## Example Flow

1. Submit a high-cost claim (severe damage):
```bash
curl -X POST http://localhost:8000/claims/ \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "CLM-HIGH-COST",
    "vehicle_id": "BMW-X5-2020-006",
    "customer_id": "CUST-9999",
    "rental_agreement_id": "RNT-2026-9999",
    "return_location": "Frankfurt_Airport",
    "damage_type": "dent",
    "severity": "severe",
    "location": "driver_door",
    "description": "Large dent on driver door",
    "affected_parts": ["driver_door", "side_mirror"],
    "photos": ["photo1.jpg"],
    "inspector_id": "INSP-001"
  }'
```

2. Check queue for pending items:
```bash
curl http://localhost:8000/queue/ | jq '.[0]'
```

3. Get the queue_id and approve:
```bash
curl -X POST http://localhost:8000/queue/{queue_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer_id": "REVIEWER-001", "notes": "Approved after verification"}'
```

4. View claim events:
```bash
curl http://localhost:8000/events/CLM-HIGH-COST
```

## Valid Enum Values

**damage_type**: scratch, dent, bumper_crack, windshield_crack, interior_damage, mechanical, other

**severity**: minor, medium, severe, high

**location**: front_bumper, rear_bumper, driver_door, passenger_door, rear_quarter_panel, windshield, rear_seat, undercarriage, side_mirror, multiple

## Response Codes

- 200: Success
- 201: Created (claim submitted)
- 400: Bad Request (validation error)
- 404: Not Found
- 500: Internal Server Error

## Notes

- Auto-approve threshold: €500
- High-cost claims (>€500) require human approval
- Pattern flags trigger human review
- All timestamps in ISO 8601 format
- Costs in EUR
