"""
Web UI routes.

Serves HTML pages with HTMX interactions.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.persistence.database import get_db
from src.services.approval_service import ApprovalService
from src.services.event_logger import EventLogger
from src.services.fleet_analytics_service import FleetAnalyticsService

router = APIRouter()

# Setup Jinja2 templates
templates = Jinja2Templates(directory="src/api/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard page with overview stats."""

    # Get queue stats
    approval_service = ApprovalService(db)
    stats = approval_service.get_queue_stats()

    # Get fleet health
    analytics_service = FleetAnalyticsService(db)
    fleet = analytics_service.get_fleet_health_summary()

    # Get recent events
    event_logger = EventLogger(db)
    recent_events = event_logger.get_recent_events(limit=10)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "fleet": fleet,
            "recent_events": recent_events
        }
    )


@router.get("/submit", response_class=HTMLResponse)
async def submit_claim_page(request: Request):
    """Submit new claim page."""
    return templates.TemplateResponse(
        "submit.html",
        {"request": request}
    )


@router.get("/queue", response_class=HTMLResponse)
async def approval_queue_page(request: Request):
    """Approval queue page."""
    # Get pending approvals from workflow
    from src.graph.workflow import DamageClaimWorkflow
    workflow = DamageClaimWorkflow(use_checkpointer=True)
    pending = workflow.get_pending_approvals()

    return templates.TemplateResponse(
        "queue.html",
        {
            "request": request,
            "pending": pending
        }
    )


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, db: Session = Depends(get_db)):
    """Analytics page with fleet insights."""
    analytics_service = FleetAnalyticsService(db)

    # Get all analytics data
    fleet_health = analytics_service.get_fleet_health_summary()
    locations = analytics_service.get_location_risk_analysis()
    patterns = analytics_service.get_pattern_summary()
    retirement_candidates = analytics_service.get_retirement_candidates()
    cost_breakdown = analytics_service.get_cost_breakdown_by_category()

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "fleet_health": fleet_health,
            "locations": locations[:5],  # Top 5 locations
            "patterns": patterns,
            "retirement_candidates": retirement_candidates[:5],
            "cost_breakdown": cost_breakdown
        }
    )
