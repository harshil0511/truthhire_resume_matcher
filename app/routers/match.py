"""
Routes for resume/job-description matching.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.models import MatchRequest, MatchResponse
from app.services.groq_service import GroqServiceError, get_match_result

logger = logging.getLogger("truthhire.match_router")

router = APIRouter(tags=["matching"])


@router.post(
    "/test-match",
    response_model=MatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Score a resume against a job description",
)
async def test_match(payload: MatchRequest) -> MatchResponse:
    """
    Accepts a job description and a plain-text resume, sends them to Groq,
    and returns a structured match evaluation.

    - 400: empty/whitespace-only input (handled by the global validation
      exception handler in main.py).
    - 502: Groq call succeeded to reach the network but failed to produce
      a usable result (API error or unparsable output).
    - 500: any other unexpected server-side failure.
    """
    try:
        result = get_match_result(payload.job_description, payload.resume)
    except GroqServiceError as exc:
        # Log full details server-side only — never expose internal error to caller.
        logger.error("Groq service error while matching resume: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI model service failed to return a valid result. Please try again.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - guard against any unforeseen failure
        logger.exception("Unexpected error while matching resume to job description.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        ) from exc

    return MatchResponse(**result)
