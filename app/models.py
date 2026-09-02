"""
Request/response schemas for the matching API.
"""

from typing import List

from pydantic import BaseModel, Field, field_validator


class MatchRequest(BaseModel):
    """Incoming payload for POST /test-match."""

    job_description: str = Field(
        ...,
        min_length=1,
        description="Full plain-text job description.",
        examples=["Senior Backend Engineer with 5+ years Python, FastAPI, PostgreSQL..."],
    )
    resume: str = Field(
        ...,
        min_length=1,
        description="Full plain-text resume content.",
        examples=["John Doe - Backend Engineer with 4 years experience in Django, REST APIs..."],
    )

    @field_validator("job_description", "resume")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if value is None or not value.strip():
            raise ValueError("must not be empty or whitespace-only")
        return value


class MatchResponse(BaseModel):
    """Structured result returned to the caller."""

    match_score: int = Field(..., ge=0, le=100)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
