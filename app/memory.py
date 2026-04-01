"""
Memory Store access layer.
All DB reads/writes for site_records, scrape_events, healing_history, and scrape_results.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import HealingHistory, ScrapeEvent, ScrapeResult, SiteRecord
from app.schemas import ConfidenceResult, SiteRecordRead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def domain_hash(url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc or url
    return hashlib.sha256(domain.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# site_records
# ---------------------------------------------------------------------------

def get_site_record(db: Session, d_hash: str) -> Optional[SiteRecord]:
    return db.query(SiteRecord).filter(SiteRecord.domain_hash == d_hash).first()


def create_site_record(db: Session, url: str, d_hash: str) -> SiteRecord:
    record = SiteRecord(domain_hash=d_hash, url=url)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_site_record_after_success(
    db: Session,
    site: SiteRecord,
    dom_hash: str,
    script_content: str,
    fingerprint: dict,
) -> SiteRecord:
    site.dom_hash = dom_hash
    site.last_success_at = datetime.utcnow()
    site.script_version = (site.script_version or 0) + 1
    site.script_content = script_content
    site.site_fingerprint_json = fingerprint
    site.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(site)
    return site


def update_site_script(db: Session, site: SiteRecord, script_content: str) -> SiteRecord:
    site.script_content = script_content
    site.script_version = (site.script_version or 0) + 1
    site.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(site)
    return site


# ---------------------------------------------------------------------------
# scrape_events
# ---------------------------------------------------------------------------

def create_scrape_event(db: Session, site_id: int) -> ScrapeEvent:
    event = ScrapeEvent(site_id=site_id, status="IN_PROGRESS")
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def complete_scrape_event(
    db: Session,
    event: ScrapeEvent,
    status: str,
    confidence_score: Optional[float] = None,
    error_type: Optional[str] = None,
    error_trace: Optional[str] = None,
    healing_tier_used: Optional[int] = None,
) -> ScrapeEvent:
    event.completed_at = datetime.utcnow()
    event.status = status
    event.confidence_score = confidence_score
    event.error_type = error_type
    event.error_trace = error_trace
    event.healing_tier_used = healing_tier_used
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# scrape_results
# ---------------------------------------------------------------------------

def write_scrape_result(
    db: Session,
    event_id: int,
    data: dict,
    confidence: ConfidenceResult,
) -> ScrapeResult:
    result = ScrapeResult(
        event_id=event_id,
        data=data,
        confidence_score=confidence.score,
        confidence_flags=confidence.flags if confidence.flags else None,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


# ---------------------------------------------------------------------------
# healing_history
# ---------------------------------------------------------------------------

def record_healing_attempt(
    db: Session,
    site_id: int,
    event_id: int,
    tier: int,
    old_selector: Optional[str],
    new_selector: Optional[str],
    prompt_used: Optional[str],
    success: bool,
) -> HealingHistory:
    entry = HealingHistory(
        site_id=site_id,
        event_id=event_id,
        tier=tier,
        old_selector=old_selector,
        new_selector=new_selector,
        prompt_used=prompt_used,
        success=success,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_healing_history_for_site(db: Session, site_id: int, limit: int = 20) -> list[HealingHistory]:
    return (
        db.query(HealingHistory)
        .filter(HealingHistory.site_id == site_id, HealingHistory.success == True)  # noqa: E712
        .order_by(HealingHistory.applied_at.desc())
        .limit(limit)
        .all()
    )
