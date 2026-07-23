from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BrandContext:
    workspace_name: str
    project_name: str
    brand_description: str
    brand_voice: str
    target_audience: str
    prohibited_words: tuple[str, ...]
    preferred_cta: str
    industry: str
    website_url: str


@dataclass(frozen=True)
class ContentContext:
    topic: str
    brief: str
    funnel_stage: str
    format_or_intent: str


def build_social_copy_prompt(brand: BrandContext, content: ContentContext) -> str:
    """Build a structured provider-neutral prompt with explicit JSON output rules."""
    payload = {"brand": asdict(brand), "content": asdict(content)}
    return (
        "You are the AXIS social copy assistant. Generate channel-specific copy "
        "for Facebook/Instagram, LinkedIn, YouTube, GBP, and Reddit. Return only "
        "valid JSON with keys facebook_instagram, linkedin, youtube, gbp, reddit. "
        "Respect channel length limits, avoid prohibited words, and do not invent "
        "claims. Keep Reddit natural and non-promotional.\n\n"
        f"Context:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
