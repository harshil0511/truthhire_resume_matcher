"""
TruthHire Resume Matcher - FastAPI entrypoint.

Run with:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import match

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("truthhire.main")

app = FastAPI(
    title="TruthHire Resume Matcher",
    description=(
        "Standalone technical-screen API: scores a plain-text resume against "
        "a job description using a Groq LLM and returns a structured JSON result."
    ),
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Convert FastAPI's default 422 validation errors into 400 Bad Request,
    as required for empty/whitespace-only job_description or resume fields.
    """
    messages = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        messages.append(f"{loc}: {err.get('msg')}" if loc else err.get("msg"))

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": messages or "Invalid request payload."},
    )


@app.get("/", tags=["root"], summary="API Root")
async def root() -> dict:
    return {
        "message": "Welcome to the TruthHire Resume Matcher API.",
        "docs_url": "/docs",
        "health_url": "/health",
    }


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> dict:
    return {"status": "ok"}


app.include_router(match.router)
