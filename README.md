# Deltas - AI-Powered Damage Claims Automation

> Production-grade automation system for car rental damage claim processing

## Overview

Deltas is an end-to-end AI-powered workflow system that automates damage claim processing for car rental operations. It combines LangGraph orchestration with event-driven architecture to handle damage assessment, cost estimation, invoice generation, and intelligent routing with human-in-the-loop approval.

**Key Features:**
- 🤖 **AI-Powered Workflow** - LangGraph agents with Deep Agents patterns
- 📊 **Event-Driven Architecture** - Decoupled, scalable, production-ready
- ✅ **Human-in-the-Loop** - Persistent approval queue for exception handling
- 🎯 **Intelligent Routing** - Auto-approve routine claims, escalate complex cases
- 📈 **Full Observability** - Event tracking, structured logging, metrics
- 🔧 **Multiple Interfaces** - CLI, REST API, Web Operations Console

## Architecture

### Hybrid Framework Approach
- **LangGraph** for workflow orchestration and state management
- **Deep Agents patterns** for agent implementation and context management
- **Event Bus** for loose coupling and extensibility
- **SQLite/PostgreSQL** for persistent approval queue

### Core Components
1. **Agents** - Intake, Cost Estimation, Invoice Generation, Validation, Routing, Notification
2. **Workflow** - LangGraph-based orchestration with checkpoints
3. **Services** - Event bus, pricing engine, finance system integration
4. **Persistence** - Approval queue, audit trail, claim history

## Quick Start

### Prerequisites
- Python 3.11+
- Google Gemini API key

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd deltas

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Usage

**CLI:**
```bash
# Process a damage claim
deltas process --claim-id ABC123

# List pending approvals
deltas queue list --status pending

# Approve a claim
deltas approve --claim-id ABC123
```

**API Server:**
```bash
# Start the API server
uvicorn src.api.main:app --reload

# API docs available at http://localhost:8000/docs
```

**Web Operations Console:**
```bash
# Start the web dashboard
uvicorn src.api.main:app --reload

# Dashboard available at http://localhost:8000
```

## Project Structure

```
deltas/
├── src/
│   ├── models/          # Pydantic data models
│   ├── agents/          # LangGraph agents
│   ├── graph/           # Workflow orchestration
│   ├── services/        # Event bus, external services
│   ├── persistence/     # Database, repositories
│   ├── api/             # FastAPI routes
│   ├── cli/             # CLI commands
│   └── utils/           # Utilities, logging
├── web/                 # Web UI (HTMX + Tailwind)
├── data/                # Sample data, scenarios
├── tests/               # Test suite
└── docs/                # Documentation
```

## Development

```bash
# Install development dependencies
uv sync --all-extras

# Run tests
pytest

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Technology Stack

**Core:**
- LangChain & LangGraph - Agent orchestration
- Google Gemini - LLM provider
- Pydantic - Data validation & type safety
- SQLAlchemy - Database ORM

**API & Web:**
- FastAPI - REST API framework
- HTMX + Tailwind CSS - Modern web UI
- Uvicorn - ASGI server

**CLI:**
- Typer - Command-line interface

**Testing:**
- Pytest - Test framework
- Coverage - Code coverage

## Documentation

- [Architecture Overview](docs/architecture/README.md)
- [API Documentation](http://localhost:8000/docs) (when running)
- [Deployment Guide](docs/architecture/deployment.md)

## Use Cases

This system is designed for car rental operations processing damage claims:
- Small to medium rental companies (1000-10000 claims/month)
- Enterprise fleet operators
- Insurance integration scenarios
- Multi-location rental networks

**Automation Benefits:**
- 70%+ reduction in processing time
- Consistent cost estimation
- Faster customer notifications
- Reduced finance team workload
- Comprehensive audit trail

## License

[Add your license here]

## Author

Built by BPOOJAR as a demonstration of production-grade AI automation engineering.
