# Deltas

AI-powered damage claims automation for car rental operations.

Automates the full claim lifecycle — damage intake, cost estimation, validation, and routing — using a LangGraph workflow with human-in-the-loop approval for edge cases.

## Why

Damage claim processing in car rental is manual, inconsistent, and slow. Finance teams spend hours on routine claims that could be auto-approved, while genuinely complex cases (luxury vehicles, repeat offenders, fleet retirement decisions) get the same treatment.

Deltas uses deterministic business rules for the 70%+ of claims that are straightforward, and brings in LLM reasoning only for the ambiguous cases — cost edge cases near approval thresholds, pattern detection across vehicle history, multi-factor risk scoring.

## Architecture

```
intake → cost_estimation → validation → routing → [auto_complete | human_review]
```

**LangGraph** orchestrates the workflow with checkpoint-based state management. Each node delegates to pure Python services (testable without an LLM), wrapped by agents that add AI reasoning when deterministic rules aren't sufficient.

```
┌─────────────────────────────────────────────────┐
│                 LangGraph Workflow               │
│   intake → cost → validate → route → complete    │
├─────────────────────────────────────────────────┤
│               AI Agents (LLM layer)              │
│   CostEstimatorAgent    ValidatorAgent           │
├─────────────────────────────────────────────────┤
│            Services (deterministic)              │
│   Pricing · Depreciation · PatternRecognition    │
│   FleetAnalytics · Approval · EventLogger        │
│   TensorlakeService (document processing)        │
├─────────────────────────────────────────────────┤
│              Persistence (SQLAlchemy)             │
│   Approval queue · Event log · Claim history     │
└─────────────────────────────────────────────────┘
```

Key design decisions:
- **Services are pure Python** — no LLM dependency, fully unit-testable
- **Agents wrap services** — add LLM reasoning only at decision boundaries
- **Structured JSON output** — LLM returns `{"decision", "reasoning", "risk_level"}`, not free text
- **Human-in-the-loop** — LangGraph `interrupt_before` with persistent approval queue
- **Repository pattern** — SQLite now, PostgreSQL-ready

## Quick Start

```bash
git clone <repository-url> && cd deltas

# Install
uv sync            # or: pip install -e .

# Configure
cp .env.example .env
# Add your GOOGLE_API_KEY to .env

# Initialize database
python scripts/init_database.py

# Run tests
pytest
```

### CLI

```bash
# Process a claim from a scenario file
deltas process data/sample_scenarios/scenario_01_minor_scratch_auto_approve.json

# View approval queue
deltas queue

# Approve / reject
deltas approve CLM-001 --reviewer "john.doe"
deltas reject CLM-002 --reason "Insufficient documentation"

# Check claim status and event history
deltas status CLM-001
deltas events CLM-001

# Fleet-wide statistics
deltas stats
```

### Web Console

```bash
uvicorn src.api.main:app --reload
# http://localhost:8000
```

Dashboard, claim submission, approval queue, and analytics — built with HTMX + Tailwind CSS.

### REST API

Same server, JSON endpoints under `/api/`:

| Endpoint | Description |
|----------|-------------|
| `POST /api/claims/` | Submit a new claim |
| `GET /api/claims/{id}` | Claim status |
| `GET /api/queue/` | Approval queue |
| `POST /api/queue/{id}/approve` | Approve claim |
| `POST /api/queue/{id}/reject` | Reject claim |
| `GET /api/analytics/fleet-health` | Fleet health scores |
| `GET /api/analytics/patterns` | Damage pattern analysis |
| `GET /api/analytics/retirement-candidates` | Vehicles flagged for retirement |
| `GET /api/events/{claim_id}` | Event audit trail |

Interactive docs at `http://localhost:8000/docs`.

## Test Scenarios

Four scenarios in `data/sample_scenarios/` exercise the main routing paths:

| Scenario | What it tests |
|----------|---------------|
| `scenario_01` | Minor scratch, low cost → auto-approve |
| `scenario_02` | Luxury vehicle bumper damage → human review (cost > threshold) |
| `scenario_03` | Frequent damage, pattern detection → escalation |
| `scenario_04` | High cumulative cost, low fleet health → retirement recommendation |

## Project Structure

```
src/
├── models/        # Pydantic V2 models (damage, financial, routing, events, state)
├── agents/        # LLM-powered agents (base, cost_estimator, validator)
├── graph/         # LangGraph workflow definition and node implementations
├── services/      # Business logic (pricing, depreciation, patterns, fleet, approval)
├── persistence/   # SQLAlchemy models + repository pattern
├── api/           # FastAPI routes + Jinja2 templates
├── cli/           # Typer CLI (8 commands)
├── config/        # Pydantic Settings
└── utils/         # Shared utilities
data/
├── vehicle_fleet/      # 12 vehicles with damage + service history
├── pricing_database/   # German market repair costs (EUR)
├── sample_scenarios/   # Test claim scenarios
└── sample_damages/     # Damage record samples
tests/                  # 192 tests, 64% coverage
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
pytest                       # full suite
pytest tests/test_agents/    # agent tests only
pytest --cov=src             # with coverage

# Code quality
ruff check src/ tests/
black src/ tests/
mypy src/
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | LangGraph, LangChain |
| LLM | Google Gemini |
| Models | Pydantic V2 |
| Database | SQLAlchemy + SQLite |
| API | FastAPI, Uvicorn |
| Web UI | HTMX, Tailwind CSS, Jinja2 |
| CLI | Typer |
| Document Processing | Tensorlake SDK (mock) |
| Logging | structlog |
| Testing | pytest, pytest-cov |

## Domain Data

Pricing and thresholds use validated German market data:
- **Labor rate**: EUR 202/hour (GDV/Dekra 2024)
- **Auto-approve threshold**: EUR 500
- **Fraud rate baseline**: ~10% (Insurance Information Institute)
- **Depreciation**: Age + mileage-based part depreciation for fair customer billing

## License

MIT
