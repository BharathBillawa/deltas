# Product Requirements Document

**Project:** Car Rental Damage Claims Automation System
**Version:** 1.0
**Date:** 2026-02-28
**Purpose:** Explore AI-powered workflow automation for car rental operations

---

## Executive Summary

An intelligent damage claims processing system for car rental operations that automates routine claims while providing strategic fleet management insights through pattern recognition. The system reduces manual processing time by 70% and provides actionable intelligence for fleet optimization.

---

## Problem Statement

### Current Pain Points
1. **Manual Processing Overhead**: 15-30 minutes per claim, inconsistent estimates
2. **Reactive Management**: Damage patterns discovered too late
3. **Limited Intelligence**: No visibility into location risks, vehicle health trends
4. **Inconsistent Decisions**: No standardized criteria for repair vs retirement
5. **Poor Customer Experience**: Slow response times, opaque pricing

### Target Users
- **Vehicle Inspectors**: Need fast, consistent damage assessment and cost estimates
- **Operations Managers**: Need approval queue with context for edge cases
- **Fleet Managers**: Need strategic insights for vehicle rotation and retirement decisions
- **Finance Team**: Need cost tracking, trend analysis, and budget planning

---

## Solution Overview

### Core Capabilities
1. **Automated Cost Estimation** - Validated German market pricing (€202/hour labor - GDV 2024)
2. **Intelligent Routing** - Auto-approve vs human review with clear reasoning
3. **Pattern Recognition** - Detect vehicle/location/customer patterns proactively
4. **Fleet Intelligence** - Strategic recommendations for fleet optimization
5. **Human-in-the-Loop** - Persistent approval queue with full context

### Key Differentiators
- ✨ **Pattern Recognition as a Service** - Multi-stakeholder value (tactical + strategic + proactive)
- ✨ **Modern Document Processing** - Integration with Tensorlake for structured data extraction
- ✨ **LangGraph Workflow** - Production-grade orchestration with checkpoints
- ✨ **Validated Data** - Real German market costs, realistic vehicle histories

---

## User Stories

### Epic 1: Automated Claims Processing

**US-1.1: Quick Cost Estimation**
```
As a vehicle inspector
I want to submit a damage claim and get an instant cost estimate
So that I can quickly process customer returns

Acceptance Criteria:
- Submit claim with damage type, severity, location
- Receive cost estimate in < 5 seconds
- Estimate includes labor hours, parts, total cost
- Estimate accounts for vehicle category multiplier
- Estimate applies depreciation for vehicles 2+ years old
```

**US-1.2: Auto-Approval for Routine Claims**
```
As an operations manager
I want routine claims under €500 to be automatically approved
So that I can focus on complex cases

Acceptance Criteria:
- Claims under €500 with no red flags → auto-approved
- Invoice generated automatically
- Customer notification sent
- Claim logged with full audit trail
```

**US-1.3: Intelligent Escalation**
```
As an operations manager
I want to review only claims that truly need human judgment
So that I'm not overwhelmed with low-risk claims

Acceptance Criteria:
- High-cost claims (>€500) → human review
- Pattern-detected claims → human review with context
- Fraud-risk claims → human review with risk score
- Clear explanation WHY review is needed
```

### Epic 2: Pattern Recognition & Intelligence

**US-2.1: Vehicle Pattern Detection**
```
As a fleet manager
I want to be alerted when a vehicle has repeated damages
So that I can take preventive action (rotate vehicle, inspect, etc.)

Acceptance Criteria:
- Detect 3+ damages in 90 days → flag as frequent damage
- Detect damages always at same location → flag location correlation
- Show damage timeline with dates and costs
- Provide actionable recommendations (rotate, inspect, retire)
```

**US-2.2: Location Risk Analysis**
```
As an operations manager
I want to know which rental locations have high damage rates
So that I can improve parking guidance or adjust insurance

Acceptance Criteria:
- Track damage rate by location
- Identify most common damage types per location
- Show cost impact by location
- Provide recommendations for high-risk locations
```

**US-2.3: Customer Risk Profiling**
```
As a risk analyst
I want to identify high-risk customers with repeated claims
So that I can apply appropriate insurance requirements

Acceptance Criteria:
- Track customer damage history
- Calculate damage rate (damages / total rentals)
- Flag customers with 2+ claims in 60 days
- Generate risk score (0-10)
- Recommend actions (higher deposit, investigation)
```

**US-2.4: Retirement Recommendations**
```
As a fleet manager
I want to know when vehicles should be retired vs repaired
So that I can optimize fleet costs and avoid throwing good money after bad

Acceptance Criteria:
- Flag vehicles with health score < 5
- Flag vehicles with cumulative damage > €2,500 YTD
- Flag vehicles with high mileage (>150k km) + high depreciation (>60%)
- Provide repair vs auction analysis
- Show estimated auction value and remaining rental revenue potential
```

### Epic 3: Approval Queue & Human-in-the-Loop

**US-3.1: Review Claims with Context**
```
As an operations manager
I want to review flagged claims with full context
So that I can make informed decisions quickly

Acceptance Criteria:
- See claim details (damage, cost, vehicle, customer)
- See WHY it was flagged (pattern, high cost, fraud risk)
- See vehicle damage history (last 12 months)
- See pattern analysis and recommendations
- Approve/reject with notes
```

**US-3.2: Priority Queue Management**
```
As an operations manager
I want high-priority claims at the top of my queue
So that I handle urgent issues first

Acceptance Criteria:
- Claims sorted by priority (1=highest, 5=lowest)
- High fraud risk → Priority 1
- Pattern detected → Priority 2
- High cost only → Priority 3
- Show time in queue (SLA tracking)
```

### Epic 4: Analytics & Reporting

**US-4.1: Fleet Health Dashboard**
```
As a fleet manager
I want a dashboard showing overall fleet health
So that I can identify trends and take proactive action

Acceptance Criteria:
- Show vehicle count by health score range
- Show total damage costs (YTD, by month)
- Show damage rate by category (Economy, Luxury, etc.)
- Show vehicles needing attention (health < 6)
- Show retirement candidates
```

**US-4.2: Location Performance**
```
As an operations manager
I want to see damage patterns by location
So that I can address location-specific issues

Acceptance Criteria:
- Show damage count and cost by location
- Show most common damage types per location
- Identify high-risk locations (damage rate > fleet average)
- Show trends over time
```

**US-4.3: Cost Analysis**
```
As a finance manager
I want to track damage costs and trends
So that I can plan budgets and identify cost drivers

Acceptance Criteria:
- Show total damage costs (by month, quarter, YTD)
- Show cost breakdown (labor, parts, categories)
- Show depreciation impact on costs
- Show cost per vehicle
- Export to CSV for further analysis
```

---

## System Assumptions

### What Exists (Assumed, Not Built)

1. **Computer Vision System** (Assumed to exist)
   - Detects damage from photos (scratches, dents, etc.)
   - Identifies damage location on vehicle
   - Determines severity (minor, medium, severe)
   - **For Demo**: We will mock this - inspector types damage details

2. **Tensorlake Integration** (Industry-standard document processing)
   - Modern car rental operations use document processing platforms
   - Extracts structured data from photos, PDFs, reports
   - **For Demo**: We will mock the interface - shows integration thinking
   - **Justification**: Demonstrates understanding of production integration patterns

3. **Customer Database** (Assumed to exist)
   - Customer rental history exists elsewhere
   - Customer profile data available
   - **For Demo**: We store minimal customer data (ID, rental count, damage history)

4. **Finance System** (Assumed to exist)
   - Invoicing system exists
   - Payment processing exists
   - **For Demo**: We generate invoice structure, assume it's sent to finance API

5. **Notification System** (Assumed to exist)
   - Email/SMS system exists
   - **For Demo**: We log notifications, don't actually send

### What We Build (In Scope)

1. ✅ **Core Services**
   - PricingService - Validated German market costs
   - DepreciationService - Age-based cost adjustment
   - PatternRecognitionService - Vehicle/customer/location pattern detection
   - FleetAnalyticsService - Aggregations for dashboards

2. ✅ **LangGraph Workflow**
   - Intake → Context Enrichment → Cost Estimation → Validation → Routing
   - Human-in-the-loop checkpoint for approval queue
   - State management with full history

3. ✅ **Persistent Storage**
   - SQLite database (production: PostgreSQL)
   - Vehicle fleet with complete damage/service history
   - Claims processing and approval queue
   - Event log for audit trail

4. ✅ **User Interfaces**
   - REST API (FastAPI) - For integrations
   - CLI Tool (Typer) - For automation
   - Web Console (FastAPI + HTMX + Tailwind) - For operators

5. ✅ **Analytics Dashboard**
   - Fleet health overview
   - Location risk analysis
   - Cost trends
   - Retirement pipeline

---

## Success Criteria

### Functional Requirements

**Must Have (P0):**
- ✅ Process damage claim end-to-end (input → cost → routing → output)
- ✅ Auto-approve claims under €500 with no red flags
- ✅ Flag claims with patterns (3+ damages in 90 days)
- ✅ Persistent approval queue with context for human review
- ✅ Show cost estimate with depreciation applied
- ✅ Basic analytics dashboard (fleet health, location risks)

**Should Have (P1):**
- ✅ Pattern recognition recommendations (rotate vehicle, inspect, etc.)
- ✅ Customer risk scoring
- ✅ Retirement analysis (repair vs auction)
- ✅ Location risk profiling
- ✅ Event log for audit trail

**Nice to Have (P2):**
- ⚠️ Real-time event stream viewer
- ⚠️ Webhook integrations for external systems
- ⚠️ Advanced analytics (seasonal patterns, predictive alerts)
- ⚠️ Export reports to PDF/CSV

### Non-Functional Requirements

**Performance:**
- Cost estimation: < 2 seconds per claim
- Pattern detection: < 3 seconds per claim
- Dashboard load: < 1 second

**Data Quality:**
- Validated German market pricing (GDV/Dekra 2024)
- Realistic vehicle histories (12 vehicles with 20+ damages)
- Patterns emerge naturally from data

**Code Quality:**
- Type-safe (Pydantic V2)
- Tested (pytest - unit + integration)
- Documented (docstrings, architecture)
- Professional git history (clean commits)

**Usability:**
- Clear UI labels and explanations
- Actionable recommendations (not just alerts)
- Context for every decision (why flagged, why cost calculated)

---

## Technical Constraints

### Technology Stack (Fixed)
- **LangGraph**: Workflow orchestration (required to showcase skills)
- **Google Gemini**: LLM provider (user has API key)
- **SQLite**: Database for demo (production: PostgreSQL)
- **FastAPI**: REST API and web server
- **HTMX + Tailwind CSS**: Modern web UI
- **Pydantic V2**: Type safety

### Demo Scope Constraints
- **Time**: Weekend project (~12-16 hours)
- **Infrastructure**: Runs locally, no cloud deployment needed
- **Scale**: Demo data (12 vehicles, 50-100 claims)
- **Authentication**: Single-user mode (no auth required)

### Mocked Components
- ✅ Tensorlake API (interface designed, returns mock data)
- ✅ CV damage detection (assumed to exist, inspector types input)
- ✅ Email/SMS notifications (logged, not actually sent)
- ✅ Finance system API (invoice generated, not actually posted)

---

## Out of Scope (Future Enhancements)

### Phase 2 Enhancements
- Real Tensorlake API integration
- Real-time CV damage detection from photos
- Multi-user authentication and authorization
- Role-based access control (inspector, manager, fleet manager)
- Advanced fraud detection with ML models
- Seasonal pattern analysis
- Predictive maintenance alerts

### Integration Features
- Finance system integration (post invoices)
- CRM integration (customer data sync)
- Notification system integration (email/SMS)
- Webhook support for external systems
- Real-time event streaming (WebSocket)

### Advanced Analytics
- Executive dashboards with drill-down
- Predictive analytics (forecast damage costs)
- Benchmark against industry standards
- ROI calculator for preventive measures
- Cost optimization recommendations

---

## Data Requirements

### Vehicle Fleet Data (✅ Already Created)
- 12 realistic vehicles (economy → luxury)
- Complete damage history (20+ incidents with patterns)
- Service history records
- Health scores and depreciation data
- Validated costs based on GDV/Dekra 2024 data

### Test Scenarios (✅ Already Created)
1. **Auto-approve**: Simple scratch, low cost, clean history
2. **Pattern detection**: VW Golf - 3 scratches in 75 days
3. **Retirement analysis**: BMW 530i - high mileage, high damage
4. **Customer risk**: CUST-RISK-001 - 2 claims in 45 days

### Location Data
- Munich Airport (high risk - 45% of damages)
- Berlin City (medium risk - 30% of damages)
- Frankfurt Suburban (low risk - 25% of damages)

---

## Acceptance Criteria for Demo

### Minimum Viable Demo (MVP)

**Scenario 1: Auto-Approve Flow**
```
1. Submit simple scratch claim (VW Polo, €165)
2. System calculates cost in < 2 seconds
3. System auto-approves (< €500, no flags)
4. Invoice generated
5. Status: APPROVED
✅ Pass: Complete flow works end-to-end
```

**Scenario 2: Pattern Detection Flow**
```
1. Submit 3rd scratch claim for VW Golf
2. System detects pattern (3 damages in 75 days)
3. System flags for human review
4. Approval queue shows context + recommendations
5. Manager reviews and approves
6. Workflow continues to completion
✅ Pass: Pattern detection works, human-in-the-loop works
```

**Scenario 3: Analytics Dashboard**
```
1. Open dashboard
2. See 12 vehicles with health scores
3. See Munich Airport as high-risk (45% damages)
4. See BMW 530i as retirement candidate
5. See VW Golf as needing rotation
✅ Pass: Analytics show actionable insights
```

### Demo Presentation Flow

**5-minute demo walkthrough:**
1. Show vehicle fleet data (realistic, validated)
2. Submit simple claim → auto-approved (30 seconds)
3. Submit pattern claim → flagged with context (30 seconds)
4. Show approval queue with recommendations (1 minute)
5. Show analytics dashboard (fleet health, location risks, retirement candidates) (1 minute)
6. Explain architecture (LangGraph, services, integration patterns) (2 minutes)

**Key talking points:**
- "Used validated German market data (€202/hour - GDV 2024)"
- "Pattern recognition provides multi-stakeholder value"
- "Modern integration patterns with document processing platforms"
- "Production-grade LangGraph workflow with human-in-the-loop"
- "70% automation rate while providing strategic intelligence"

---

## Risk Mitigation

### Technical Risks
- **Risk**: LangGraph complexity delays progress
  - **Mitigation**: Start with simple workflow, add complexity iteratively

- **Risk**: Pattern recognition logic too complex
  - **Mitigation**: Start with simple rules (3+ in 90 days), expand if time

- **Risk**: UI takes too long to build
  - **Mitigation**: Build CLI first, add simple web UI later

### Scope Risks
- **Risk**: Trying to build too much
  - **Mitigation**: This requirements doc defines clear MVP and nice-to-haves

- **Risk**: Getting stuck on mocked integrations
  - **Mitigation**: Mock interfaces clearly defined, don't over-engineer

---

## Appendix: Validated Data Sources

### German Market Costs (✅ Validated)
- **Source**: German Insurance Association (GDV) via Dekra, 2024
- **Labor rate**: €202/hour (mechanical/electrical/bodywork)
- **Painting rate**: €220/hour
- **Reference**: https://www.meinbavaria.de/car-repair-costs-in-germany-hit-record-highs/

### Fraud Statistics (✅ Validated)
- **Source**: Insurance Information Institute (III)
- **Fraud rate**: 10% of all insurance losses
- **Cross-validated**: 9-12% internationally (New Zealand, UK)

### Fleet Benchmarks (⚠️ Partial)
- **Sources identified**: Fleet Response, LeasePlan, NETS benchmark reports
- **Status**: Documents exist, good enough for demo estimates
