from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IntegrationConnect(BaseModel):
    credentials: dict[str, str] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
