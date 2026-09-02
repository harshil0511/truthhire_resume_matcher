"""
Defensive JSON extraction.

LLMs (even in "JSON mode") sometimes wrap their output in markdown code
fences, prepend reasoning/thinking tags, or add stray whitespace/text
around the actual JSON object. This module strips all of that and pulls
out a single, parseable JSON object no matter how it's dressed up.
"""

import json
import re
from typing import Any, Dict

# Matches <think>...</think>, <reasoning>...</reasoning>, <analysis>...</analysis>
# style tags some reasoning-capable models emit before the final answer.
_REASONING_TAG_RE = re.compile(
    r"<(think|reasoning|analysis|scratchpad)>.*?</\1>",
    flags=re.DOTALL | re.IGNORECASE,
)

# Matches ```json { ... } ``` or ``` { ... } ``` code fences.
_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    flags=re.DOTALL | re.IGNORECASE,
)


class JSONExtractionError(Exception):
    """Raised when a JSON object cannot be reliably extracted from model output."""


def _find_first_balanced_object(text: str) -> str:
    """Return the first balanced {...} substring in text, or raise."""
    start = text.find("{")
    if start == -1:
        raise JSONExtractionError("No opening brace found in model output.")

    depth = 0
    for i in range(start, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise JSONExtractionError("No balanced JSON object found in model output.")


def extract_json(raw_text: str) -> Dict[str, Any]:
    """
    Extract and parse a JSON object from raw LLM text output.

    Handles, in order:
      1. Empty/whitespace-only input -> error.
      2. <think>/<reasoning>/... tags -> stripped out entirely.
      3. Markdown code fences (```json ... ``` or ``` ... ```) -> unwrapped.
      4. Direct json.loads() on the cleaned text.
      5. Fallback: scan for the first balanced {...} block and parse that.

    Raises JSONExtractionError with a descriptive message if nothing usable
    is found.
    """
    if raw_text is None or not raw_text.strip():
        raise JSONExtractionError("Empty response received from model.")

    text = raw_text.strip()

    # 1. Strip reasoning/thinking tags some models emit before the answer.
    text = _REASONING_TAG_RE.sub("", text).strip()

    # 2. Unwrap markdown code fences if present.
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        # Handle a bare leading/trailing ``` without a captured group match
        # (e.g. malformed fences) by trimming backticks defensively.
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    # 3. Try a direct parse first (cheapest, most common success path).
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise JSONExtractionError("Parsed JSON was not an object.")
    except json.JSONDecodeError:
        pass

    # 4. Fallback: locate the first balanced {...} block anywhere in the text
    #    (covers cases with stray prose before/after the JSON).
    candidate = _find_first_balanced_object(text)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JSONExtractionError(f"Failed to parse extracted JSON candidate: {exc}") from exc

    if not isinstance(parsed, dict):
        raise JSONExtractionError("Extracted JSON candidate was not an object.")

    return parsed
