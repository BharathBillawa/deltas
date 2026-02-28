# System Architecture

**Car Rental Damage Claims Automation - Production-Grade AI System**

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                              │
├─────────────────┬────────────────────┬──────────────────────────────┤
│   CLI Tool      │   REST API         │   Web Console (HTMX)        │
│   (Typer)       │   (FastAPI)        │   (Operators/Reviewers)     │
│                 │                    │   - Claims Dashboard         │
│ deltas process  │ POST /claims       │   - Approval Queue          │
│ deltas queue    │ GET /queue         │   - Analytics               │
│ deltas approve  │ GET /analytics     │   - Event Stream            │
└────────┬────────┴──────────┬─────────┴──────────────┬──────────────┘
         │                   │                        │
         └───────────────────┴────────────────────────┘
                             │
         ┌───────────────────▼────────────────────────────────────────┐
         │              ORCHESTRATION LAYER                           │
         │                                                             │
         │  ┌────────────────────────────────────────────────────┐   │
         │  │         LangGraph Workflow (StateGraph)            │   │
         │  │                                                    │   │
         │  │  Intake → Context → Cost → Validate → Route       │   │
         │  │    ↓        Enrich    Est.    Rules     Decision   │   │
         │  │  Events   Vehicle    Deprec.  Pattern   Approve/  │   │
         │  │           History    Apply    Detect    Review     │   │
         │  │                                                    │   │
         │  │  ┌──────────────────────────────────┐             │   │
         │  │  │   Human-in-the-Loop Checkpoint   │             │   │
         │  │  │   (Approval Queue - Persistent)  │             │   │
         │  │  └──────────────────────────────────┘             │   │
         │  └────────────────────────────────────────────────────┘   │
         │                             │                              │
         │                 ┌───────────▼──────────────┐               │
         │                 │      EVENT BUS           │               │
         │                 │   (Pub/Sub Pattern)      │               │
         │                 └───────────┬──────────────┘               │
         └─────────────────────────────┼───────────────────────────────┘
                                       │
         ┌─────────────────────────────▼───────────────────────────────┐
         │                    AGENT LAYER                               │
         │    (Deep Agents Patterns: Context Management, Sub-Agents)    │
         ├──────────────┬────────────────┬──────────────┬──────────────┤
         │ Intake Agent │ Cost Estimator │ Validator    │ Router       │
         │              │ Agent          │ Agent        │ Agent        │
         │ - Validate   │ - Base cost    │ - Rules      │ - Auto/      │
         │   claim      │ - Depreciation │ - Patterns   │   Review     │
         │ - Enrich     │ - Sub-agents   │ - Fraud      │ - Escalate   │
         │   context    │   for complex  │   scoring    │              │
         └──────────────┴────────────────┴──────────────┴──────────────┘
                                       │
         ┌─────────────────────────────▼───────────────────────────────┐
         │                    SERVICE LAYER                             │
         │             (Pure Business Logic - No LLM)                   │
         ├───────────────┬──────────────┬──────────────┬───────────────┤
         │ Pricing       │ Depreciation │ Pattern      │ Fleet         │
         │ Service       │ Service      │ Recognition  │ Analytics     │
         │               │              │ Service ⭐   │ Service       │
         │ - Load costs  │ - Age curves │ - Vehicle    │ - Health      │
         │ - Multipliers │ - Component  │   patterns   │   scoring     │
         │ - Market data │   factors    │ - Customer   │ - Retirement  │
         │               │ - Fair cost  │   risk       │   analysis    │
         │               │   calc       │ - Location   │ - Benchmarks  │
         │               │              │   correlation│               │
         └───────────────┴──────────────┴──────────────┴───────────────┘
                                       │
         ┌─────────────────────────────▼───────────────────────────────┐
         │                  PERSISTENCE LAYER                           │
         ├──────────────────┬───────────────────┬──────────────────────┤
         │  SQLite Database │  Repositories     │  Event Log           │
         │                  │                   │                      │
         │  - Vehicles      │  - VehicleRepo    │  - Audit Trail       │
         │  - Damages       │  - DamageRepo     │  - Event Stream      │
         │  - Claims        │  - ClaimRepo      │  - Analytics         │
         │  - Approval Queue│  - QueueRepo      │                      │
         │  - Customers     │  - CustomerRepo   │                      │
         └──────────────────┴───────────────────┴──────────────────────┘
                                       │
         ┌─────────────────────────────▼───────────────────────────────┐
         │                      DATA LAYER                              │
         │         (Validated German Market Data - GDV/Dekra)           │
         ├──────────────────────────────────────────────────────────────┤
         │  • 12 Vehicles with Complete Histories                       │
         │  • Validated Pricing (€202/hour labor - GDV 2024)            │
         │  • Depreciation Curves by Component                          │
         │  • 20+ Historical Damage Records with Patterns               │
         │  • Location Risk Profiles (Munich Airport, Berlin, etc.)     │
         └──────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Architecture

### 1. Service Layer Design (Core Intelligence)

```
┌────────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER DETAIL                          │
└────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PRICING SERVICE                                                │
│  Purpose: Load and apply market-validated costs                 │
├─────────────────────────────────────────────────────────────────┤
│  Inputs:                                                        │
│    - damage_type: str                                           │
│    - severity: str                                              │
│    - vehicle_category: VehicleCategory                          │
│    - location: str                                              │
│                                                                 │
│  Processing:                                                    │
│    1. Load base cost from pricing_database/repair_costs.json   │
│    2. Apply category multiplier (Economy 1.0x → Premium 2.1x)  │
│    3. Apply location multiplier if needed                      │
│    4. Calculate labor hours × €202/hour (validated)            │
│    5. Add parts costs                                          │
│                                                                 │
│  Outputs:                                                       │
│    - base_cost_eur: float                                      │
│    - labor_hours: float                                        │
│    - labor_rate_eur: float (202 or 220 for painting)          │
│    - parts_cost_eur: float                                     │
│    - category_multiplier: float                                │
│                                                                 │
│  Data Source: data/pricing_database/repair_costs.json          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  DEPRECIATION SERVICE                                           │
│  Purpose: Calculate fair depreciated cost for older vehicles   │
├─────────────────────────────────────────────────────────────────┤
│  Inputs:                                                        │
│    - vehicle: VehicleInfo                                       │
│    - repair_cost_eur: float                                     │
│    - damage_component: DepreciationComponent (bumper/panel/etc)│
│                                                                 │
│  Processing:                                                    │
│    1. Calculate vehicle age (current_year - vehicle.year)      │
│    2. Load depreciation curve for component type              │
│    3. Get depreciation factor (e.g., 6-year bumper = 0.25)    │
│    4. Calculate depreciated value                             │
│    5. Company absorbs difference                              │
│                                                                 │
│  Business Logic:                                               │
│    - New vehicles (< 2 years): No depreciation                │
│    - Older vehicles: Apply age-based curves                   │
│    - Customer pays depreciated value                          │
│    - Transparent calculation for customer satisfaction        │
│                                                                 │
│  Outputs:                                                       │
│    - depreciation_factor: float (0.0-1.0)                      │
│    - depreciated_value_eur: float                              │
│    - savings_eur: float (absorbed by company)                  │
│    - calculation: DepreciationCalculation                      │
│                                                                 │
│  Data Source: depreciation_curves in repair_costs.json         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PATTERN RECOGNITION SERVICE ⭐ (BIGGEST DIFFERENTIATOR)       │
│  Purpose: Detect patterns and provide fleet intelligence       │
├─────────────────────────────────────────────────────────────────┤
│  Inputs:                                                        │
│    - claim: DamageClaim                                         │
│    - vehicle: VehicleInfo (with damage_history)                │
│    - customer_history: CustomerDB                              │
│                                                                 │
│  Pattern Detection:                                            │
│    1. VEHICLE PATTERNS                                         │
│       - Frequent damage (3+ in 90 days) ✓ Detected            │
│       - Location correlation (same location repeatedly)        │
│       - Damage type patterns (always same type)                │
│       - Maintenance correlation (poor maintenance + damage)    │
│                                                                 │
│    2. CUSTOMER PATTERNS                                        │
│       - High damage rate (> fleet average)                     │
│       - Frequent claims (2+ in 60 days) ✓ Detected            │
│       - Dispute patterns                                       │
│                                                                 │
│    3. FLEET-LEVEL INSIGHTS                                     │
│       - Location risk analysis (Munich Airport = 45% damages) │
│       - Age/damage correlation                                 │
│       - Category performance                                   │
│                                                                 │
│  Outputs (Multiple Stakeholders):                             │
│    1. TACTICAL (for current claim):                           │
│       - patterns_detected: List[PatternDetection]             │
│       - requires_escalation: bool                             │
│       - fraud_risk_score: float (0-10)                        │
│                                                                 │
│    2. STRATEGIC (for fleet management):                       │
│       - vehicle_health_alert: Optional[Alert]                 │
│       - retirement_recommendation: Optional[str]              │
│       - location_risk_update: Optional[dict]                  │
│                                                                 │
│    3. PROACTIVE (for operations):                             │
│       - maintenance_due_alerts: List[Alert]                   │
│       - rotation_recommendations: List[str]                   │
│                                                                 │
│  Events Emitted:                                               │
│    - PatternDetectedEvent                                      │
│    - FraudAlertEvent (if risk_score > 7)                      │
│    - RetirementAlertEvent (if health_score < 5)               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  FLEET ANALYTICS SERVICE                                        │
│  Purpose: Aggregate data for executive dashboards              │
├─────────────────────────────────────────────────────────────────┤
│  Inputs:                                                        │
│    - time_period: str (ytd, quarter, month)                    │
│    - filters: dict (location, category, etc.)                  │
│                                                                 │
│  Aggregations:                                                 │
│    1. Fleet Health Summary                                     │
│       - Total vehicles by health score range                   │
│       - Average health score by category                       │
│       - Vehicles needing attention                            │
│                                                                 │
│    2. Cost Analysis                                            │
│       - Total damage costs (YTD, by month)                     │
│       - Cost per vehicle                                       │
│       - Cost by location                                       │
│       - Depreciation impact on P&L                            │
│                                                                 │
│    3. Pattern Insights                                         │
│       - High-risk locations                                    │
│       - Seasonal patterns                                      │
│       - Category performance                                   │
│                                                                 │
│    4. Retirement Pipeline                                      │
│       - Vehicles approaching thresholds                        │
│       - Estimated auction values                               │
│       - Fleet optimization opportunities                       │
│                                                                 │
│  Outputs:                                                       │
│    - FleetHealthReport                                         │
│    - CostAnalysisReport                                        │
│    - PatternInsights                                           │
│    - RetirementPipeline                                        │
│                                                                 │
│  Use Cases:                                                     │
│    - Executive dashboards                                      │
│    - Budget planning                                           │
│    - Location risk assessment                                  │
│    - Fleet optimization                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Workflow Detail

```
┌────────────────────────────────────────────────────────────────────┐
│                   LANGGRAPH WORKFLOW DETAIL                        │
└────────────────────────────────────────────────────────────────────┘

                          ┌──────────────┐
                          │ Claim Input  │
                          │ (DamageClaim)│
                          └──────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │   INTAKE AGENT          │
                    │   (Validation)          │
                    ├─────────────────────────┤
                    │ • Validate completeness │
                    │ • Check data quality    │
                    │ • Emit ClaimReceived    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ CONTEXT ENRICHMENT      │
                    │ (Pattern from Deep      │
                    │  Agents)                │
                    ├─────────────────────────┤
                    │ • Load vehicle history  │
                    │ • Load customer history │
                    │ • Calculate baseline    │
                    │   risk score            │
                    │ • Enrich state with     │
                    │   full context          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ COST ESTIMATION AGENT   │
                    │ (with Sub-Agent Pattern)│
                    ├─────────────────────────┤
                    │ 1. Call PricingService  │
                    │ 2. Apply Depreciation   │
                    │    (DepreciationService)│
                    │ 3. Complex cases:       │
                    │    → Spawn sub-agent    │
                    │    → Specialist estimate│
                    │ 4. Emit CostEstimated   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ VALIDATION AGENT        │
                    │ (Business Rules)        │
                    ├─────────────────────────┤
                    │ • Apply business rules  │
                    │ • Pattern Recognition   │
                    │   Service ⭐            │
                    │ • Fraud scoring         │
                    │ • Check thresholds      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   ROUTING DECISION      │
                    │   (Router Agent)        │
                    ├─────────────────────────┤
                    │ Decision Logic:         │
                    │                         │
                    │ IF cost < €500 AND      │
                    │    no_patterns AND      │
                    │    fraud_score < 3      │
                    │ → AUTO_APPROVE          │
                    │                         │
                    │ ELSE IF patterns OR     │
                    │    fraud_score > 7      │
                    │ → HUMAN_REVIEW          │
                    │                         │
                    │ ELSE IF retirement      │
                    │ → ESCALATE_FLEET_MGT    │
                    └────────┬────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
     ┌──────────▼────────┐   ┌───────────▼───────────┐
     │  AUTO-APPROVE     │   │  HUMAN REVIEW         │
     │                   │   │  REQUIRED             │
     ├───────────────────┤   ├───────────────────────┤
     │ • Generate invoice│   │ • Add to approval     │
     │ • Notify customer │   │   queue (SQLite)      │
     │ • Close claim     │   │ • Emit                │
     │                   │   │   ApprovalRequired    │
     │                   │   │ • LangGraph INTERRUPT │
     │                   │   │   (checkpoint)        │
     └───────────────────┘   └───────────┬───────────┘
                                         │
                             ┌───────────▼───────────┐
                             │  APPROVAL QUEUE       │
                             │  (Persistent)         │
                             ├───────────────────────┤
                             │ • SQLite storage      │
                             │ • Full context saved  │
                             │ • Reviewer UI         │
                             │ • SLA tracking        │
                             └───────────┬───────────┘
                                         │
                                   Human Decision
                                         │
                             ┌───────────▼───────────┐
                             │  Resume Workflow      │
                             ├───────────────────────┤
                             │ IF approved:          │
                             │   → Generate invoice  │
                             │   → Notify customer   │
                             │                       │
                             │ IF rejected:          │
                             │   → Notify ops        │
                             │   → Investigation     │
                             └───────────────────────┘
```

---

## Event-Driven Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                    EVENT-DRIVEN ARCHITECTURE                       │
└────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │   EVENT BUS         │
                    │   (In-memory/Redis) │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐    ┌───────▼────────┐    ┌───────▼────────┐
│ Event Listeners│    │ Event Listeners│    │ Event Listeners│
│                │    │                │    │                │
│ • Audit Log    │    │ • Analytics    │    │ • Webhooks     │
│   Writer       │    │   Aggregator   │    │   (External)   │
│                │    │                │    │                │
│ • Notification │    │ • Dashboard    │    │ • Finance      │
│   Service      │    │   Updates      │    │   System       │
│                │    │                │    │                │
│ • Metrics      │    │ • Alert        │    │ • Tensorlake   │
│   Collector    │    │   Manager      │    │   (Future)     │
└────────────────┘    └────────────────┘    └────────────────┘

Events Published:
┌─────────────────────────────────────────────────────────────┐
│ ClaimReceived        → Audit, Analytics                     │
│ CostEstimated        → Finance System, Dashboard            │
│ PatternDetected      → Operations Team, Fleet Management    │
│ FraudAlert           → Risk Team, Investigation Queue       │
│ RetirementAlert      → Fleet Management, Finance            │
│ ApprovalRequired     → Approval Queue, SLA Tracking         │
│ ClaimApproved        → Customer Notification, Finance       │
│ NotificationSent     → Audit Log                            │
└─────────────────────────────────────────────────────────────┘

Benefits:
✓ Loose coupling - Services don't depend on each other directly
✓ Easy extensibility - Add new listeners without touching core code
✓ Audit trail - Every state change is recorded
✓ Analytics ready - Events feed dashboards in real-time
✓ Production pattern - Standard for scalable systems
```

---

## Data Flow Example: Pattern Detection Scenario

```
┌────────────────────────────────────────────────────────────────────┐
│  SCENARIO: VW Golf - 3rd scratch in 75 days at Munich Airport     │
└────────────────────────────────────────────────────────────────────┘

1. CLAIM INPUT
   ├─ Vehicle: VW-GOLF-2022-003
   ├─ Damage: Scratch (minor) on front bumper
   ├─ Location: Munich_Airport
   └─ Customer: CUST-5566

2. CONTEXT ENRICHMENT
   ├─ Load vehicle from DB
   │  ├─ Previous damages: 2 (last: 23 days ago)
   │  ├─ Both at Munich_Airport
   │  └─ Health score: 6.8/10
   └─ Enrich state with full history

3. COST ESTIMATION
   ├─ PricingService.estimate()
   │  ├─ Base: €202/hr × 1.0hr = €202
   │  ├─ Parts: €8
   │  ├─ Category multiplier: 1.15 (Compact)
   │  └─ Total: €210
   └─ Depreciation: Not applicable (4-year vehicle)

4. PATTERN RECOGNITION SERVICE ⭐
   ├─ analyze_vehicle_patterns()
   │  ├─ Query recent damages (90 days)
   │  ├─ Found: 3 damages in 75 days
   │  ├─ Location: All at Munich_Airport
   │  └─ Pattern: FREQUENT_DAMAGE + LOCATION_CORRELATION
   │
   ├─ calculate_risk_scores()
   │  ├─ Fraud risk: 3.5/10 (moderate)
   │  └─ Overall risk: 6.2/10 (elevated)
   │
   └─ generate_recommendations()
      ├─ "Rotate vehicle out of Munich Airport fleet"
      ├─ "Inspect for pre-existing cosmetic issues"
      └─ "Review parking guidance at location"

5. VALIDATION
   ├─ Cost check: €210 < €500 (passes threshold)
   ├─ Pattern check: Frequent damage detected (FAIL)
   └─ Decision: Requires human review

6. ROUTING DECISION
   ├─ Route to: HUMAN_REVIEW_REQUIRED
   ├─ Reason: "Pattern detected: 3 damages in 75 days"
   └─ Escalation: pattern_detected

7. APPROVAL QUEUE
   ├─ Create queue item
   ├─ Priority: 2 (high due to pattern)
   ├─ Context for reviewer:
   │  ├─ Cost: €210 (low)
   │  ├─ Pattern summary: "3rd scratch in 75 days, same location"
   │  ├─ Recommendations: [rotate vehicle, inspect, review location]
   │  └─ Vehicle health: 6.8/10
   └─ Wait for human decision

8. EVENTS EMITTED
   ├─ ClaimReceived
   ├─ CostEstimated (€210)
   ├─ PatternDetected (FREQUENT_DAMAGE, LOCATION_CORRELATION)
   └─ ApprovalRequired

9. STAKEHOLDER VALUE
   ├─ Finance: Low cost claim, but pattern indicates risk
   ├─ Operations: Munich Airport flagged as high-risk location
   ├─ Fleet Management: Vehicle rotation recommendation
   └─ Customer Service: Fair handling, not auto-rejected

KEY INSIGHT: Cost is low (€210) but PATTERN MATTERS MORE
→ This is what makes the system intelligent, not just faster
```

---

## Technology Stack Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY CHOICES                       │
├─────────────────────────────────────────────────────────────┤
│ Orchestration:  LangGraph (workflow control)               │
│ Agent Patterns: Deep Agents patterns (context, sub-agents) │
│ LLM:            Google Gemini (via langchain-google-genai)  │
│ Data Models:    Pydantic V2 (type safety)                  │
│ Database:       SQLite → PostgreSQL ready                  │
│ ORM:            SQLAlchemy                                  │
│ API:            FastAPI (REST)                             │
│ CLI:            Typer                                       │
│ UI:             HTMX + Tailwind CSS                        │
│ Testing:        Pytest                                      │
│ Code Quality:   Black, Ruff, MyPy                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Hybrid Architecture (LangGraph + Deep Agents Patterns)
**Why**: Different layers benefit from different tools
- LangGraph: Precise workflow control, checkpoints, interrupts
- Deep Agents: Context management, sub-agent patterns, smart prompts

### 2. Service Layer Separate from Agents
**Why**: Pure business logic can be tested without LLM calls
- Services: Deterministic calculations (pricing, depreciation)
- Agents: LLM-powered reasoning (interpretation, edge cases)

### 3. Pattern Recognition as Service
**Why**: Multi-stakeholder value, not just tactical
- Tactical: Flag current claim for review
- Strategic: Fleet management intelligence
- Proactive: Predictive maintenance alerts

### 4. Event-Driven Architecture
**Why**: Loose coupling, easy extensibility
- Add analytics without touching core code
- Audit trail built-in
- Real-time dashboards

### 5. Persistent Approval Queue (SQLite)
**Why**: Production-grade human-in-the-loop
- Claims can wait hours/days
- Full context preserved
- SLA tracking

---

## Next Steps

After reviewing and refining this architecture:

1. **Build Core Services** (Option A)
   - Start with PricingService
   - Add DepreciationService
   - Build PatternRecognitionService ⭐

2. **Create First Agent**
   - Cost Estimation Agent
   - Uses services we build
   - Tests LLM integration

3. **Add Tests**
   - Service layer unit tests
   - Integration tests with database
   - E2E scenario tests
