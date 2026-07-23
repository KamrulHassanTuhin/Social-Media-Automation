from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ContentCreate(BaseModel):
    project_id: str = Field(min_length=1)
    topic: str = Field(min_length=3, max_length=300)
    brief_status: str = "NOT_STARTED"


class ContentSummary(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    topic: str
    brief_status: str
    automation_status: str
    publisher_id: str | None
    live_url: str | None
    has_media: bool
    copies: dict[str, str]
    updated_at: datetime


class GenerateRequest(BaseModel):
    channels: list[str] = Field(default_factory=lambda: ["FACEBOOK_INSTAGRAM", "LINKEDIN", "YOUTUBE", "GBP", "REDDIT"])
    provider: str = "OPENAI"
    force_regenerate: bool = False


class ActionResponse(BaseModel):
    job_id: str | None = None
    content_id: str
    status: str


class CopyUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=40000)


class ApprovalAction(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class ScheduleRequest(BaseModel):
    scheduled_for: datetime
