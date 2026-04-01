"""
Orchestrator — central routing brain.

Routing logic:
  - No site record found         → Discovery Agent (new site)
  - Record found, dom_hash match → Static Worker directly
  - Record found, dom_hash diff  → Discovery Agent to regenerate script

After routing, attaches memory context (last script, healing history) to the job.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from app import confidence, memory, worker
from app.escalation import write_escalation_entry
from app.models import ScrapeEvent, SiteRecord
from app.schemas import ErrorPayload, ScrapeJob, ScrapeRequest, SuccessPayload
from config import settings

logger = logging.getLogger(__name__)


RouteDecision = Literal["discovery", "worker"]


def _compute_dom_hash(script_content: str) -> str:
    import hashlib
    return hashlib.md5(script_content.encode()).hexdigest()


def _script_path_for_site(domain_hash: str) -> Path:
    path = settings.scripts_dir / f"{domain_hash}.py"
    return path


def get_route(site: SiteRecord | None, job: ScrapeJob) -> RouteDecision:
    if site is None:
        return "discovery"
    script_path = _script_path_for_site(job.domain_hash)
    if not script_path.exists():
        return "discovery"
    return "worker"


def _build_job(request: ScrapeRequest, site: SiteRecord | None) -> ScrapeJob:
    d_hash = memory.domain_hash(request.competitor_url)
    job = ScrapeJob(
        job_id=str(uuid.uuid4()),
        competitor_url=request.competitor_url,
        product_name=request.product_name,
        requester_id=request.requester_id,
        domain_hash=d_hash,
    )
    if site:
        job.site_record_id = site.id
        job.last_script_content = site.script_content
        job.last_dom_hash = site.dom_hash
    return job


def _ensure_site_record(db: Session, request: ScrapeRequest) -> tuple[SiteRecord, bool]:
    d_hash = memory.domain_hash(request.competitor_url)
    site = memory.get_site_record(db, d_hash)
    created = False
    if site is None:
        site = memory.create_site_record(db, request.competitor_url, d_hash)
        created = True
    return site, created


def run(db: Session, request: ScrapeRequest) -> dict:
    site, _ = _ensure_site_record(db, request)
    job = _build_job(request, site)

    route = get_route(site, job)
    logger.info("job=%s route=%s url=%s", job.job_id, route, request.competitor_url)

    if route == "discovery":
        return {
            "job_id": job.job_id,
            "status": "PENDING_DISCOVERY",
            "message": (
                "No script found for this site. "
                "Run the Discovery Agent: "
                f"python -m app.discovery --url {request.competitor_url} --domain-hash {job.domain_hash}"
            ),
        }

    # --- Execute scrape ---
    event = memory.create_scrape_event(db, site.id)
    script_path = _script_path_for_site(job.domain_hash)

    result = worker.execute(script_path)

    if isinstance(result, ErrorPayload):
        return _handle_failure(db, site, event, result, job)

    return _handle_success(db, site, event, result, job)


def _handle_success(
    db: Session,
    site: SiteRecord,
    event: ScrapeEvent,
    payload: SuccessPayload,
    job: ScrapeJob,
) -> dict:
    conf = confidence.score(payload.data)

    if conf.routing == "reject":
        write_escalation_entry(
            job=job,
            reason="LOW_CONFIDENCE",
            confidence=conf,
            error_payload=None,
        )
        memory.complete_scrape_event(
            db, event,
            status="ESCALATED",
            confidence_score=conf.score,
        )
        return {
            "job_id": job.job_id,
            "status": "ESCALATED",
            "confidence_score": conf.score,
            "flags": conf.flags,
            "message": "Confidence too low — escalated for human review.",
        }

    status = "SUCCESS" if conf.routing == "accept" else "LOW_CONFIDENCE"
    memory.complete_scrape_event(
        db, event,
        status=status,
        confidence_score=conf.score,
    )
    memory.write_scrape_result(db, event.id, payload.data, conf)
    memory.update_site_record_after_success(
        db, site,
        dom_hash=_compute_dom_hash(payload.data.get("_raw_html", "")),
        script_content=site.script_content or "",
        fingerprint={"selectors_used": payload.selectors_used},
    )

    return {
        "job_id": job.job_id,
        "status": status,
        "confidence_score": conf.score,
        "flags": conf.flags,
        "data": payload.data,
    }


def _handle_failure(
    db: Session,
    site: SiteRecord,
    event: ScrapeEvent,
    payload: ErrorPayload,
    job: ScrapeJob,
) -> dict:
    logger.error("job=%s scrape_failed error_type=%s", job.job_id, payload.error_type)

    write_escalation_entry(
        job=job,
        reason="SCRAPE_FAILURE",
        confidence=None,
        error_payload=payload,
    )
    memory.complete_scrape_event(
        db, event,
        status="ESCALATED",
        error_type=payload.error_type,
        error_trace=payload.traceback,
    )

    return {
        "job_id": job.job_id,
        "status": "FAILED",
        "error_type": payload.error_type,
        "message": "Scrape failed — escalated for human review. See escalation log.",
    }
