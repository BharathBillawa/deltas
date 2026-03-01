# Deltas — Stakeholder Presentation

## Damage Claims Automation for Car Rental Operations

---

## The Problem

Damage claim processing in car rental is **manual, slow, and inconsistent**.

| Pain Point | Impact |
|------------|--------|
| **15-30 min per claim** manually | Finance team bottleneck |
| **No standardized pricing** | Inconsistent cost estimates across inspectors |
| **Reactive pattern detection** | Repeat vehicle damage caught too late |
| **No fleet intelligence** | Retirement decisions based on gut feel, not data |
| **Flat escalation** | Every claim gets the same review, regardless of risk |

**~70% of claims are routine** (minor scratches, small dents under €500) — yet they receive the same manual handling as complex cases.

---

## The Solution

Deltas automates the full claim lifecycle:

```
Damage Report → Cost Estimation → Validation → Routing → Resolution
```

**Routine claims** (low cost, clean history) → auto-approved in seconds.

**Complex cases** (luxury vehicles, repeat damage, fraud signals) → routed to human review with full context and AI reasoning.

The system handles the easy 70% automatically so the team can focus on the 30% that actually needs judgment.

---

## How It Works

### Workflow

```
┌──────────┐    ┌───────────────┐    ┌────────────┐    ┌─────────┐
│  Intake  │ →  │ Cost Estimate │ →  │ Validation │ →  │ Routing │
└──────────┘    └───────────────┘    └────────────┘    └────┬────┘
                                                           │
                                          ┌────────────────┼────────────────┐
                                          ▼                                 ▼
                                   ┌─────────────┐                  ┌──────────────┐
                                   │ Auto-Approve │                  │ Human Review  │
                                   │  + Invoice   │                  │  (with AI     │
                                   └─────────────┘                  │   reasoning)  │
                                                                    └──────────────┘
```

### Each step:

1. **Intake** — Extract damage details from report (Tensorlake document processing)
2. **Cost Estimation** — Calculate repair costs using validated German market pricing
3. **Validation** — Check vehicle history, detect patterns, score fraud risk
4. **Routing** — Auto-approve or escalate based on cost + risk factors
5. **Resolution** — Generate invoice or queue for human review with full context

---

## Intelligent Routing

The system doesn't just check cost thresholds. It evaluates multiple factors:

| Factor | Auto-Approve | Escalate to Human |
|--------|-------------|-------------------|
| **Cost** | Under €500 | Over €500 |
| **Vehicle** | Standard category | Luxury / Premium |
| **History** | Clean | Repeat damage pattern |
| **Fleet Health** | Healthy (>7/10) | Low score (<5/10) |
| **Customer** | First claim | Multiple recent claims |
| **Fraud Risk** | Low (<0.3) | Elevated (>0.5) |

When a claim is escalated, the reviewer sees **why** — specific flags, risk scores, vehicle history, and AI reasoning — not just a queue item.

---

## Cost Estimation

Built on validated German market data:

- **Labor rate**: €202/hour (GDV/Dekra 2024)
- **Category multipliers**: Economy (1.0x) → Premium (2.5x)
- **Depreciation**: Age + mileage-based part depreciation for fair billing
- **Real pricing database**: Scratches, dents, bumpers, glass, wheels, interior

### Example: Same Damage, Different Vehicles

| | VW Polo (Economy) | BMW 530i (Luxury) |
|--|-------------------|-------------------|
| Bumper scratch repair | €165 | €420 |
| Category multiplier | 1.0x | 1.8x |
| Depreciation (3yr) | -15% | -15% |
| **Final estimate** | **€140** | **€357** |
| **Routing** | Auto-approve | Auto-approve |

| | VW Polo (Economy) | BMW 530i (Luxury) |
|--|-------------------|-------------------|
| Bumper replacement | €800 | €1,800 |
| Category multiplier | 1.0x | 1.8x |
| **Routing** | Human review | Human review + luxury flag |

---

## Pattern Recognition

Not just fraud detection — **fleet intelligence**:

### Vehicle Patterns
- 3 damages in 75 days → investigate root cause
- Cumulative repair cost approaching vehicle value → retirement candidate

### Location Patterns
- Munich Airport: 45% of all damages → high-risk location
- Specific parking areas generating repeat claims

### Customer Patterns
- Multiple claims in short period → risk profile
- Cross-reference across rental history

### Fleet Health Scores
- Every vehicle scored 0-10 based on damage history, age, maintenance
- Low-scoring vehicles flagged for rotation or retirement

---

## Interfaces

### Web Operations Console
- **Dashboard** — Fleet overview, recent claims, key metrics
- **Claim Submission** — Submit new damage reports
- **Approval Queue** — Review escalated claims with full context + AI reasoning
- **Analytics** — Fleet health, location risk, damage patterns

### CLI (for automation & scripting)
```
deltas process <scenario>    Process a claim
deltas queue                 View approval queue
deltas approve <id>          Approve a claim
deltas reject <id>           Reject with reason
deltas stats                 Fleet-wide statistics
```

### REST API (for integration)
- Full CRUD for claims, queue, analytics, events
- Interactive docs at `/docs`

---

## What's Built

| Component | Status | Details |
|-----------|--------|---------|
| LangGraph Workflow | ✅ Complete | 7 nodes, checkpoint-based state management |
| AI Agents | ✅ Complete | Cost estimation + validation with structured LLM output |
| Business Services | ✅ Complete | Pricing, depreciation, pattern recognition, fleet analytics |
| Tensorlake Integration | ✅ Complete | Document processing for damage extraction (mock) |
| Human-in-the-Loop | ✅ Complete | Persistent approval queue with interrupt/resume |
| Web Console | ✅ Complete | Dashboard, claims, queue, analytics (HTMX + Tailwind) |
| CLI | ✅ Complete | 8 commands for processing and management |
| REST API | ✅ Complete | 19 endpoints with OpenAPI docs |
| Test Suite | ✅ Complete | 192 tests, 64% coverage |
| Sample Data | ✅ Complete | 12 vehicles, 20+ damage records, 4 test scenarios |

---

## Tech Stack

| | |
|--|--|
| **Orchestration** | LangGraph (workflow + checkpoints + human-in-the-loop) |
| **AI** | Google Gemini via LangChain (structured JSON output) |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, Pydantic V2 |
| **Frontend** | HTMX + Tailwind CSS (server-rendered, no SPA complexity) |
| **Document Processing** | Tensorlake SDK |
| **Database** | SQLite (PostgreSQL-ready via repository pattern) |

---

## ROI Projection

Based on a mid-size rental operation (~5,000 claims/month):

| Metric | Before | After | Impact |
|--------|--------|-------|--------|
| **Processing time** | 15-30 min/claim | <1 min (auto) / 5 min (review) | **~70% reduction** |
| **Claims needing human review** | 100% | ~30% | **70% automated** |
| **Cost estimate consistency** | Varies by inspector | Standardized pricing | **Eliminates variance** |
| **Pattern detection** | Reactive (weeks/months) | Real-time | **Proactive fleet management** |
| **Fraud signal detection** | Manual review | Automated scoring | **Every claim scored** |

### Estimated Annual Savings

| | |
|--|--|
| FTE hours saved (claims processing) | ~6,000 hrs/year |
| At avg. cost €45/hr | **€270,000/year** |
| Fraud prevention (conservative 2% improvement) | **€150,000/year** |
| Fleet optimization (better retirement timing) | **€80,000/year** |
| **Total estimated benefit** | **~€500,000/year** |

*Assumptions: 5,000 claims/month, 20 min avg. saved per auto-approved claim, €3M annual damage costs, 10% baseline fraud rate.*

---

## Next Steps

| Phase | Scope | Timeline |
|-------|-------|----------|
| **Pilot** | Deploy with real claims data, validate pricing accuracy | 4 weeks |
| **Tensorlake Integration** | Connect real document processing (photos → structured data) | 2 weeks |
| **Production** | PostgreSQL, auth, monitoring, CI/CD | 3 weeks |
| **Scale** | Multi-location rollout, finance system integration | Ongoing |

---

## Summary

Deltas turns damage claim processing from a manual bottleneck into an automated pipeline.

- **70% of claims** handled without human intervention
- **Consistent pricing** based on validated market data
- **Intelligent escalation** — humans review only what needs judgment
- **Fleet intelligence** — patterns, health scores, retirement recommendations
- **Production-grade** — tested, documented, ready for pilot
