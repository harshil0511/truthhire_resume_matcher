"""
Groq SDK wrapper for resume/job-description matching.

Strategy:
  1. Try Groq structured outputs (JSON schema constrained) if the model
     supports it.
  2. Fall back to json_object mode if schema-constrained output fails
     (older/incompatible model or SDK version).
  3. Fall back to a plain call with no response_format constraint as a
     last resort.
  4. Regardless of which path succeeds, ALWAYS run the raw text through
     the defensive JSON extractor before trusting it -- structured output
     support varies across Groq models/SDK versions, and some models still
     wrap answers in markdown fences or reasoning tags even when asked
     not to.
"""

import logging
from typing import Any, Callable, Dict, Optional

# pyrefly: ignore [missing-import]
from groq import Groq

from app.config import settings
from app.utils.json_extractor import JSONExtractionError, extract_json

logger = logging.getLogger("truthhire.groq_service")


class GroqServiceError(Exception):
    """Raised for any failure calling Groq or interpreting its response."""


MASTER_SYSTEM_PROMPT = """You are an expert technical recruiter and resume analyst.
Your task is to compare a candidate's resume against a job description and produce a structured JSON evaluation.

RULES:
1. Identify skills that are EXPLICITLY mentioned in BOTH the resume and the job description. These go into "matched_skills".
2. Identify important skills REQUIRED by the job description that are NOT found in the resume. These go into "missing_skills".
3. Calculate a realistic match_score from 0 to 100 based on:
   - How many required skills are matched
   - Seniority level alignment
   - Years of experience relevance
   - Domain expertise overlap
4. NEVER invent skills. Only use skills that actually appear in the provided text.
5. Normalize skill names to standard industry terms (e.g., "ReactJS" -> "React", "k8s" -> "Kubernetes").
6. Be honest and objective. A weak candidate should get a low score.
7. Return ONLY a raw JSON object matching this exact schema. Do not wrap it in markdown code fences, do not include <think> or <reasoning> tags, and do not add any explanation before or after it.

SCHEMA:
{
  "match_score": <integer 0-100>,
  "matched_skills": [<string>, ...],
  "missing_skills": [<string>, ...]
}
"""

RESPONSE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "match_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "matched_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["match_score", "matched_skills", "missing_skills"],
    "additionalProperties": False,
}

_client: Optional[Groq] = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise GroqServiceError(
                "GROQ_API_KEY is not configured. Set it in your .env file."
            )
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _build_user_prompt(job_description: str, resume: str) -> str:
    return (
        "JOB DESCRIPTION:\n"
        f"{job_description.strip()}\n\n"
        "RESUME:\n"
        f"{resume.strip()}\n\n"
        "Return only the JSON object described in the system instructions."
    )


def _base_messages(user_prompt: str):
    return [
        {"role": "system", "content": MASTER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _call_structured(client: Groq, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=_base_messages(user_prompt),
        temperature=0.2,
        max_tokens=1024,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "resume_match_result",
                "schema": RESPONSE_JSON_SCHEMA,
            },
        },
        timeout=settings.request_timeout_seconds,
    )
    return response.choices[0].message.content or ""


def _call_json_object(client: Groq, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=_base_messages(user_prompt),
        temperature=0.2,
        max_tokens=1024,
        response_format={"type": "json_object"},
        timeout=settings.request_timeout_seconds,
    )
    return response.choices[0].message.content or ""


def _call_plain(client: Groq, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=_base_messages(user_prompt),
        temperature=0.2,
        max_tokens=1024,
        timeout=settings.request_timeout_seconds,
    )
    return response.choices[0].message.content or ""


# Ordered fallback chain: json_object first (most reliable for openai/gpt-oss-20b),
# plain text second, json_schema last (only some newer models support it).
_CALL_STRATEGIES: list[Callable[[Groq, str], str]] = [
    _call_json_object,
    _call_structured,
    _call_plain,
]


def _call_groq_with_fallback(client: Groq, user_prompt: str) -> str:
    last_error: Optional[Exception] = None

    for strategy in _CALL_STRATEGIES:
        try:
            content = strategy(client, user_prompt)
            if content and content.strip():
                return content
            last_error = GroqServiceError(f"{strategy.__name__} returned empty content.")
        except Exception as exc:  # noqa: BLE001 - deliberately broad, we fall back on anything
            logger.warning("Groq call strategy '%s' failed: %s", strategy.__name__, exc)
            last_error = exc

    raise GroqServiceError(f"All Groq call strategies failed. Last error: {last_error}")


def _validate_and_normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    if "match_score" not in data:
        raise GroqServiceError("Model response is missing required field 'match_score'.")

    try:
        score = int(round(float(data["match_score"])))
    except (TypeError, ValueError) as exc:
        raise GroqServiceError("Model response had a non-numeric 'match_score'.") from exc
    score = max(0, min(100, score))

    matched = data.get("matched_skills", [])
    missing = data.get("missing_skills", [])

    if not isinstance(matched, list):
        matched = []
    if not isinstance(missing, list):
        missing = []

    matched = sorted({str(s).strip() for s in matched if str(s).strip()})
    missing = sorted({str(s).strip() for s in missing if str(s).strip()})

    return {
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
    }


def get_match_result(job_description: str, resume: str) -> Dict[str, Any]:
    """
    Call Groq to compare a resume against a job description and return a
    normalized, schema-validated dict: {match_score, matched_skills, missing_skills}.

    Raises GroqServiceError on any failure (network, API, or unparsable output).
    """
    client = get_client()
    user_prompt = _build_user_prompt(job_description, resume)

    raw_content = _call_groq_with_fallback(client, user_prompt)

    try:
        parsed = extract_json(raw_content)
    except JSONExtractionError as exc:
        logger.error("Could not extract JSON from model output. Raw content: %r", raw_content)
        raise GroqServiceError(f"Model returned an unparsable response: {exc}") from exc

    return _validate_and_normalize(parsed)
