from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# Input Gateway
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    competitor_url: str
    product_name: str
    requester_id: str

    @field_validator("product_name")
    @classmethod
    def product_name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("product_name must be non-empty")
        return v.strip()


class ScrapeResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Internal job object passed between components
# ---------------------------------------------------------------------------

class ScrapeJob(BaseModel):
    job_id: str
    competitor_url: str
    product_name: str
    requester_id: str
    domain_hash: str
    site_record_id: Optional[int] = None
    last_script_content: Optional[str] = None
    last_dom_hash: Optional[str] = None
    healing_history: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Static Worker payloads
# ---------------------------------------------------------------------------

class SuccessPayload(BaseModel):
    data: dict[str, Any]
    confidence_raw: float
    selectors_used: list[str]
    duration_ms: int


class ErrorPayload(BaseModel):
    error_type: str
    traceback: str
    last_selector: str
    screenshot_b64: str
    html_snapshot: str


# ---------------------------------------------------------------------------
# Confidence Scorer output
# ---------------------------------------------------------------------------

class ConfidenceResult(BaseModel):
    score: float
    routing: Literal["accept", "flag", "reject"]
    flags: list[str] = []


# ---------------------------------------------------------------------------
# Site record (memory store read model)
# ---------------------------------------------------------------------------

class SiteRecordRead(BaseModel):
    id: int
    domain_hash: str
    url: str
    dom_hash: Optional[str]
    last_success_at: Optional[datetime]
    script_version: int
    script_content: Optional[str]
    site_fingerprint_json: Optional[dict[str, Any]]

    model_config = {"from_attributes": True}
