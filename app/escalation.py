"""
Escalation logger — writes structured JSON Lines entries on failure.

Output:
  - escalation_logs/escalation.log  — append-only JSONL, one entry per failure
  - escalation_logs/screenshots/    — screenshot PNGs keyed by timestamp + domain_hash

Monitor in real time: tail -f escalation_logs/escalation.log | jq .
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import settings
from app.schemas import ConfidenceResult, ErrorPayload, ScrapeJob

logger = logging.getLogger(__name__)


def _ensure_dirs() -> None:
    settings.log_escalation_path.parent.mkdir(parents=True, exist_ok=True)
    settings.escalation_screenshots_dir.mkdir(parents=True, exist_ok=True)


def _save_screenshot(screenshot_b64: str, domain_hash: str, timestamp: str) -> Optional[str]:
    if not screenshot_b64:
        return None
    try:
        filename = f"{timestamp}_{domain_hash}.png"
        dest = settings.escalation_screenshots_dir / filename
        dest.write_bytes(base64.b64decode(screenshot_b64))
        return str(dest)
    except Exception as exc:
        logger.warning("Could not save screenshot: %s", exc)
        return None


def write_escalation_entry(
    job: ScrapeJob,
    reason: str,
    confidence: Optional[ConfidenceResult],
    error_payload: Optional[ErrorPayload],
) -> None:
    _ensure_dirs()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    screenshot_path: Optional[str] = None

    if error_payload and error_payload.screenshot_b64:
        screenshot_path = _save_screenshot(error_payload.screenshot_b64, job.domain_hash, ts)

    entry: dict = {
        "timestamp": ts,
        "job_id": job.job_id,
        "competitor_url": job.competitor_url,
        "product_name": job.product_name,
        "domain_hash": job.domain_hash,
        "reason": reason,
    }

    if confidence:
        entry["confidence_score"] = confidence.score
        entry["confidence_flags"] = confidence.flags

    if error_payload:
        entry["error_type"] = error_payload.error_type
        entry["traceback"] = error_payload.traceback
        entry["last_selector"] = error_payload.last_selector
        entry["html_snapshot_len"] = len(error_payload.html_snapshot)

    if screenshot_path:
        entry["screenshot_path"] = screenshot_path

    entry["resolution_status"] = "PENDING"

    line = json.dumps(entry, ensure_ascii=False)
    with settings.log_escalation_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    logger.warning("Escalation logged: job_id=%s reason=%s", job.job_id, reason)
