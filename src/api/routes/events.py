"""
Events API endpoints.

Routes for viewing event audit trails.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.persistence.database import get_db
from src.services.event_logger import EventLogger

router = APIRouter()


# Response Models

class EventResponse(BaseModel):
    """Response model for an event."""
    event_id: str
    event_type: str
    timestamp: str
    priority: str
    data: dict = Field(default_factory=dict)


# Endpoints

@router.get("/{claim_id}", response_model=list[EventResponse])
async def get_claim_events(
    claim_id: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all events for a specific claim.

    Returns the complete audit trail for a claim,
    ordered chronologically.
    """
    try:
        event_logger = EventLogger(db)
        events = event_logger.get_events_for_claim(claim_id)

        if not events:
            return []  # Return empty list instead of 404

        # Limit results
        events = events[:limit]

        return [
            EventResponse(
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=event["timestamp"],
                priority=event.get("priority", "normal"),
                data=event.get("data", {})
            )
            for event in events
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch events: {str(e)}"
        )


@router.get("/recent/all", response_model=list[EventResponse])
async def get_recent_events(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get recent events across all claims.

    Returns the most recent events system-wide,
    ordered by timestamp (newest first).
    """
    try:
        event_logger = EventLogger(db)
        events = event_logger.get_recent_events(limit=limit)

        return [
            EventResponse(
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=event["timestamp"],
                priority=event.get("priority", "normal"),
                data=event.get("data", {})
            )
            for event in events
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent events: {str(e)}"
        )
