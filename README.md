# TruthHire Resume Matcher

A standalone FastAPI service that scores a plain-text resume against a job
description using a Groq LLM, returning a structured JSON result:

```json
{
  "match_score": 78,
  "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
  "missing_skills": ["Kubernetes", "GraphQL"]
}
```

## Why the project looks the way it does

This is intentionally a small, focused service — no database, no auth, no
Docker. The task is stateless (score in, JSON out) and the spec explicitly
calls for keeping it lean, so none of that would add real value here; it
would just be surface area to review. What *does* matter for a service like
this:

- **Secrets never hardcoded.** The Groq API key is loaded from `.env` via
  `pydantic-settings` and is in `.gitignore`, so it can't accidentally end
  up in the repo.
- **Input validation at the boundary.** Empty/whitespace-only
  `job_description` or `resume` are rejected with an HTTP `400` (FastAPI's
  default `422` is remapped via a custom exception handler in `main.py`).
- **Defensive JSON extraction.** Even with Groq's JSON-object mode requested,
  the raw model output is *always* passed through
  `app/utils/json_extractor.py`, which strips markdown code fences
  (```` ```json ... ``` ````) and `<think>`/`<reasoning>` tags, then falls
  back to scanning for the first balanced `{...}` block if a direct parse
  fails. This is the part of the assignment most likely to break under
  real-world model output, so it's the most heavily tested piece.
- **Layered call strategy.** `groq_service.py` tries `json_object` mode
  first (most reliable for `openai/gpt-oss-20b`), then a plain call, then
  JSON-schema structured output — so the service degrades gracefully instead
  of hard-failing if a given model/SDK version doesn't support a given mode.

## Project structure

```
truthhire_resume_matcher/
├── .env                     # Local secrets (gitignored) — fill in your real key
├── .env.example             # Template for .env
├── .gitignore
├── requirements.txt
├── README.md
├── run.py                   # Convenience entry-point (wraps uvicorn)
└── app/
    ├── main.py               # FastAPI app, health check, error handlers
    ├── config.py             # pydantic-settings, loads .env
    ├── models.py             # Request/response Pydantic schemas
    ├── routers/
    │   └── match.py          # POST /test-match endpoint
    ├── services/
    │   └── groq_service.py   # Groq SDK wrapper + master system prompt
    └── utils/
        └── json_extractor.py # Defensive JSON extraction
```

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

2. Set your Groq API key:

   ```bash
   copy .env.example .env        # Windows
   # cp .env.example .env        # macOS / Linux
   # then edit .env and set GROQ_API_KEY=your_real_key
   ```

   Get a key at https://console.groq.com/keys

3. Run the server:

   ```bash
   # Option A — convenience script (recommended)
   python run.py

   # Option B — raw uvicorn command
   uvicorn app.main:app --reload
   ```

   The API will be available at `http://127.0.0.1:8000`, with interactive
   docs at `http://127.0.0.1:8000/docs`.

## Usage

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### Match a resume against a job description

```bash
curl -X POST http://127.0.0.1:8000/test-match \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Senior Backend Engineer. Requires 5+ years Python, FastAPI, PostgreSQL, Docker, and AWS. Experience with Kubernetes is a plus.",
    "resume": "Backend engineer with 4 years of experience building REST APIs in Python using FastAPI and Django. Managed PostgreSQL databases and deployed services with Docker on AWS EC2."
  }'
```

Example response:

```json
{
  "match_score": 74,
  "matched_skills": ["AWS", "Docker", "FastAPI", "PostgreSQL", "Python"],
  "missing_skills": ["Kubernetes"]
}
```

### Error cases

| Scenario | HTTP Status |
|---|---|
| Empty or whitespace-only `job_description` / `resume` | `400 Bad Request` |
| Groq API unreachable / all fallback strategies fail / unparsable output | `502 Bad Gateway` |
| Any other unexpected server failure | `500 Internal Server Error` |

## Notes on the model

Default model is `openai/gpt-oss-20b` (Groq-hosted), configurable via
`GROQ_MODEL` in `.env`. This model reliably supports `json_object` mode and
consistently returns clean JSON without extra prose. The service also falls
back through a plain call and finally a JSON-schema structured call, with the
defensive extractor as the last line of defence in every path.

Other available models you can swap in via `GROQ_MODEL`:
- `openai/gpt-oss-120b` — larger, more powerful variant
- `qwen/qwen3.8-27b` — Qwen 3 series on Groq
- `groq/compound` — Groq's compound agentic model
