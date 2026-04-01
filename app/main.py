"""
Input Gateway — FastAPI application entry point.

Endpoints:
  POST /scrape         — submit a new scrape job
  GET  /health         — liveness check
  GET  /jobs/{job_id}  — look up a past scrape event (basic)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app import orchestrator
from app.database import engine, get_db
from app.models import Base, ScrapeEvent
from app.schemas import ScrapeRequest, ScrapeResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (idempotent; Alembic handles migrations)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured.")
    yield


app = FastAPI(
    title="Autonomous Competitor Intelligence System",
    version="0.1.0",
    description="Self-healing LLM-powered competitor scraping pipeline.",
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.post("/scrape", response_model=ScrapeResponse, status_code=status.HTTP_202_ACCEPTED, tags=["scrape"])
def submit_scrape(request: ScrapeRequest, db: Session = Depends(get_db)):
    """
    Submit a scrape job for a competitor URL.

    - If the site has no script yet, returns PENDING_DISCOVERY with CLI instructions.
    - If a script exists, runs it immediately and returns the result.
    """
    try:
        result = orchestrator.run(db, request)
    except Exception as exc:
        logger.exception("Unhandled error in orchestrator")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ScrapeResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=result.get("message") or _summarise(result),
    )


@app.get("/jobs/{job_id}", tags=["scrape"])
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Look up a scrape event by job_id (UUID stored in message, not DB PK)."""
    # The job_id in the response is a UUID generated per request; for a full
    # implementation this would be persisted. For the prototype we return a
    # 404 to signal the endpoint exists but persistence isn't wired yet.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Job lookup by UUID not yet implemented. Query scrape_events table directly.",
    )


def _summarise(result: dict) -> str:
    if result.get("data"):
        score = result.get("confidence_score", "?")
        return f"Scrape complete. Confidence: {score}"
    return result.get("error_type", "See escalation log.")
