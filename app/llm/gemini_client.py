"""Gemini 1.5 Flash client with 15 RPM throttling and optional JSON parsing."""
import asyncio
import json
import logging
import re
from typing import Any

from app.config import GOOGLE_API_KEY
from app.llm.rate_limit import throttle_gemini

logger = logging.getLogger(__name__)

# Lazy init to avoid import-time API key requirement
_model = None


def _get_model():
    global _model
    if _model is None:
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set")
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


async def complete(prompt: str, system_instruction: str | None = None) -> str:
    """Call Gemini 1.5 Flash. Throttles to 15 RPM. Returns response text."""
    await throttle_gemini()
    model = _get_model()
    contents = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
    response = await asyncio.to_thread(lambda: model.generate_content(contents))
    if not response or not response.text:
        return ""
    return response.text.strip()


async def complete_json(
    prompt: str,
    system_instruction: str | None = None,
) -> dict[str, Any] | None:
    """Call Gemini and parse response as JSON. Strips markdown code blocks if present."""
    text = await complete(prompt, system_instruction=system_instruction)
    if not text:
        return None
    # Try raw parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip ```json ... ``` or ``` ... ```
    stripped = re.sub(r"^```(?:json)?\s*", "", text)
    stripped = re.sub(r"\s*```\s*$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        logger.warning("Gemini response was not valid JSON: %s", e)
        return None
