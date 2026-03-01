# Deltas — Stakeholder Presentation

## AI-Powered Finance Process Automation: Damage Claims

---

## The Problem

Damage claims are a **core finance process** in car rental — high volume, manual, and directly impacting revenue recovery.

| Pain Point | Impact |
|------------|--------|
| **15-30 min per claim** manually | Finance team bottleneck, poor time-to-value |
| **No standardized pricing** | Inconsistent cost estimates, revenue leakage |
| **100% manual review** | No distinction between routine and complex claims |
| **Reactive pattern detection** | Fraud and fleet issues caught weeks too late |
| **No system integration** | Data lives in spreadsheets, emails, paper forms |

**~70% of claims are routine** — minor scratches, small dents under €500. They don't need human judgment, yet they consume the same processing time as complex cases.

---

## The Solution

An **AI agent-based workflow** that automates end-to-end damage claim processing within the finance organization.

```
Document Intake → Cost Estimation → Validation → Routing → Resolution
    (OCR/AI)        (AI Agent)       (AI Agent)    (Rules)    (Auto/Human)
```

**Routine claims** → auto-approved in seconds, invoice generated.

**Complex cases** → escalated to human review with full context, AI reasoning, and recommended action.

The system automates the 70% that's predictable, so the finance team focuses on the 30% that needs judgment.

---

## AI Agents & Workflow Orchestration

### Agent-Based Architecture

Each workflow step is powered by an **AI agent** that combines deterministic business rules with LLM reasoning:

```
┌─────────────────────────────────────────────────────┐
│              LangGraph Workflow Engine                │
│                                                      │
│   ┌─────────┐   ┌──────────────┐   ┌────────────┐  │
│   │ Intake  │ → │ Cost Agent   │ → │ Validator  │  │
│   │ Agent   │   │              │   │ Agent      │  │
│   └─────────┘   └──────────────┘   └────────────┘  │
│        │               │                  │          │
│   Tensorlake      Pricing +          Pattern +       │
│   (doc extract)   Depreciation       Fraud           │
│                   Services           Detection       │
│                                                      │
│                    ┌──────────┐                       │
│                    │ Routing  │                       │
│                    └────┬─────┘                       │
│              ┌──────────┴──────────┐                 │
│              ▼                     ▼                  │
│     ┌──────────────┐     ┌────────────────┐         │
│     │ Auto-Approve │     │ Human Review   │         │
│     │ + Invoice    │     │ (with context) │         │
│     └──────────────┘     └────────────────┘         │
└─────────────────────────────────────────────────────┘
```

### How Agents Work

Each agent follows the same pattern — **deterministic first, LLM only when needed**:

1. **Run business rules** (pricing tables, thresholds, pattern checks)
2. **Check if case is ambiguous** (cost near threshold, conflicting signals)
3. **If ambiguous → invoke LLM** with structured JSON output for reasoning
4. **Return decision + explanation** for audit trail

This keeps the system fast, predictable, and testable — while still leveraging AI for edge cases.

---

## Exception Handling & Escalation

The system doesn't just auto-approve or reject. It implements **multi-factor escalation logic**:

| Factor | Auto-Approve | Escalate to Human Review |
|--------|-------------|--------------------------|
| **Cost** | Under €500 | Over €500 |
| **Vehicle** | Standard category | Luxury / Premium |
| **History** | Clean record | Repeat damage pattern |
| **Fleet Health** | Healthy (>7/10) | Low score (<5/10) |
| **Customer** | First claim | Multiple recent claims |
| **Fraud Score** | Low (<0.3) | Elevated (>0.5) |

### Human-in-the-Loop

When a claim is escalated, the reviewer receives:

- **Why it was escalated** — specific flags and scores, not just "needs review"
- **AI reasoning** — what the agent's analysis found
- **Vehicle history** — all prior damages, cumulative costs, service gaps
- **Recommended action** — approve, reject, or investigate further

The workflow **pauses and persists state** (LangGraph checkpointing). The reviewer approves or rejects via web console, CLI, or API. The workflow **resumes from where it stopped** — no re-processing.

---

## Cost Estimation

Built on **validated German market data** (GDV/Dekra 2024):

- **Labor rate**: €202/hour
- **Category multipliers**: Economy (1.0x) → Premium (2.5x)
- **Depreciation**: Age + mileage-based part depreciation
- **Real pricing database**: Scratches, dents, bumpers, glass, wheels, interior

### Example: Same Damage, Different Routing

| | VW Polo (Economy) | BMW 530i (Luxury) |
|--|-------------------|-------------------|
| Bumper scratch repair | €165 | €420 |
| After depreciation (3yr) | **€140** | **€357** |
| **Routing** | Auto-approve | Auto-approve |

| | VW Polo (Economy) | BMW 530i (Luxury) |
|--|-------------------|-------------------|
| Bumper replacement | €800 | €1,800 |
| **Routing** | Human review | Human review + luxury flag |

---

## Pattern Recognition & Fleet Intelligence

Beyond individual claims — the system builds **strategic intelligence**:

| Pattern Type | What it Detects | Action |
|-------------|-----------------|--------|
| **Vehicle** | 3 damages in 75 days | Flag for inspection, rotate to low-risk location |
| **Location** | Munich Airport: 45% of damages | Identify high-risk areas, adjust processes |
| **Customer** | Multiple claims in short period | Risk profile, potential fraud signal |
| **Fleet Health** | Vehicle score dropping below 5/10 | Retirement candidate, cost-benefit analysis |
| **Cumulative Cost** | Repair costs approaching vehicle value | Retire vs. continue decision support |

This turns damage data from a cost center into **fleet management intelligence**.

---

## System Integration

### Three interfaces — same backend, different use cases:

| Interface | Users | Use Case |
|-----------|-------|----------|
| **Web Console** | Operations managers, finance team | Daily workflow — review queue, analytics, dashboards |
| **REST API** | Other systems, automation tools | Integration with finance systems, ERPs, notification services |
| **CLI** | Engineers, batch processing | Scripting, testing, bulk operations |

### API Design

19 RESTful endpoints with OpenAPI documentation:

```
POST   /api/claims/              Submit a new claim
GET    /api/claims/{id}          Claim status
GET    /api/queue/               Approval queue
POST   /api/queue/{id}/approve   Approve claim
POST   /api/queue/{id}/reject    Reject claim
GET    /api/analytics/fleet-health    Fleet scores
GET    /api/analytics/patterns        Damage patterns
GET    /api/events/{claim_id}         Audit trail
```

Ready for integration with existing systems — finance APIs, RPA tools, data pipelines.

---

## What's Built (MVP Status)

| Component | Status | Details |
|-----------|--------|---------|
| LangGraph Workflow | ✅ | 7 nodes, checkpoint-based state, error handling |
| AI Agents | ✅ | Cost estimation + validation, structured JSON LLM output |
| Tensorlake Integration | ✅ | Document extraction interface designed against their SDK |
| Business Services | ✅ | Pricing, depreciation, pattern recognition, fleet analytics |
| Human-in-the-Loop | ✅ | Persistent queue, interrupt/resume, reviewer context |
| Exception Handling | ✅ | Multi-factor escalation, fraud scoring, error recovery |
| Web Console | ✅ | Dashboard, claims, queue, analytics |
| REST API | ✅ | 19 endpoints, OpenAPI docs |
| CLI | ✅ | 8 commands |
| Test Suite | ✅ | 192 tests, 64% coverage |
| Sample Data | ✅ | 12 vehicles, 20+ damage records, 5 test scenarios |

**Time-to-value**: MVP built and tested. Ready for pilot with real data.

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Agent Orchestration** | LangGraph | Workflow checkpoints, human-in-the-loop, state management |
| **LLM** | Google Gemini via LangChain | Structured output, function calling, cost-effective |
| **Document Processing** | Tensorlake SDK | Built for fleet/automotive doc extraction, VPC-deployable |
| **Backend** | Python 3.11, FastAPI | Industry standard, easy to maintain |
| **Data Validation** | Pydantic V2 | Type-safe models across entire pipeline |
| **Database** | SQLAlchemy + SQLite | Repository pattern — PostgreSQL-ready, no code changes |
| **Web UI** | HTMX + Tailwind CSS | Server-rendered, fast iteration, no SPA overhead |
| **API Integration** | REST + OpenAPI | Standard interface for RPA tools, ERPs, other systems |

---

## ROI Projection

Based on a mid-size rental operation (~5,000 claims/month):

| Metric | Before | After | Impact |
|--------|--------|-------|--------|
| **Processing time** | 15-30 min/claim | <1 min (auto) / 5 min (review) | **~70% reduction** |
| **Claims requiring manual review** | 100% | ~30% | **70% fully automated** |
| **Cost estimate consistency** | Varies by person | Standardized, auditable | **Eliminates variance** |
| **Pattern detection** | Reactive (weeks) | Real-time | **Proactive management** |
| **Fraud signal coverage** | Sampled manually | Every claim scored | **100% coverage** |

### Estimated Annual Savings

| | |
|--|--|
| FTE hours saved (claims processing) | ~6,000 hrs/year |
| At avg. cost €45/hr | **€270,000/year** |
| Fraud prevention (conservative 2% improvement) | **€150,000/year** |
| Fleet optimization (better retirement timing) | **€80,000/year** |
| **Total estimated benefit** | **~€500,000/year** |

*Assumptions: 5,000 claims/month, 20 min avg. saved per auto-approved claim, €3M annual damage costs.*

---

## Rollout Path

| Phase | Scope | Timeline |
|-------|-------|----------|
| **MVP** ✅ | Agent workflow, HITL, web console, API, tests | Done |
| **Pilot** | Real claims data, validate pricing accuracy, user feedback | 4 weeks |
| **Tensorlake** | Swap mock for live Tensorlake API | 2 weeks |
| **Production** | PostgreSQL, auth, monitoring, CI/CD, finance system integration | 4 weeks |
| **Scale** | Multi-location rollout, additional finance process automation | Ongoing |

Designed for **iterative rollout** — each phase delivers value independently.

---

## Summary

| | |
|--|--|
| **What** | AI agent-based automation for damage claim processing |
| **How** | LangGraph workflow + AI agents + human-in-the-loop |
| **Impact** | 70% of claims automated, consistent pricing, real-time fraud detection |
| **Intelligence** | Pattern recognition turns cost data into fleet management insights |
| **Integration** | REST API ready for finance systems, RPA tools, data pipelines |
| **Status** | MVP complete — 192 tests passing, ready for pilot |
