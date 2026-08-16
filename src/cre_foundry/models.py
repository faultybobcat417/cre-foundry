from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Business(BaseModel):
    business_id: str
    name: str
    address: str
    city: str
    industry: str
    employee_band: str | None = None


class EvidenceEvent(BaseModel):
    event_id: str
    source_id: str
    source_record_id: str
    observed_at: datetime
    event_date: date
    event_type: Literal["building_permit", "business_record", "expansion", "other"]
    account_name: str | None = None
    address: str | None = None
    city: str | None = None
    amount: float | None = Field(default=None, ge=0)
    description: str = ""
    attribution: str = ""

    @field_validator("source_id", "source_record_id", "event_id")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identifier cannot be empty")
        return value


class MatchResult(BaseModel):
    business_id: str | None
    confidence: float = Field(ge=0, le=1)
    method: str
    abstained: bool = False
    reason: str | None = None


class Signal(BaseModel):
    signal_id: str
    business_id: str
    event_id: str
    signal_type: str
    event_date: date
    recency_days: int = Field(ge=0)
    magnitude: float = Field(ge=0, le=1)
    corroboration: float = Field(ge=0, le=1)
    entity_confidence: float = Field(ge=0, le=1)
    evidence_summary: str


class RankedAccount(BaseModel):
    business: Business
    priority_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    component_scores: dict[str, float]
    signals: list[Signal]
    rationale: list[str]
