"""
Agentic Code Reviewer - FastAPI app.
Webhook endpoint + PR review (Critic agent) + optional test endpoints.
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, Request, Response, status

from app.agents.critic import review_diff
from app.config import GOOGLE_API_KEY, GITHUB_APP_WEBHOOK_SECRET
from app.github_client import fetch_pr_diff, post_review_comments
from app.llm.gemini_client import complete
from app.webhooks.github import parse_pr_payload, verify_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _log_startup_config() -> None:
    """Log config state at startup (no secrets)."""
    from app.config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_WEBHOOK_SECRET, GOOGLE_API_KEY
    logger.info(
        "Config: GITHUB_APP_ID=%s, WEBHOOK_SECRET=%s, PRIVATE_KEY=%s, GOOGLE_API_KEY=%s",
        "set" if GITHUB_APP_ID else "MISSING",
        "set" if GITHUB_APP_WEBHOOK_SECRET else "MISSING",
        "set" if (GITHUB_APP_PRIVATE_KEY and len(GITHUB_APP_PRIVATE_KEY) > 50) else "MISSING",
        "set" if GOOGLE_API_KEY else "MISSING",
    )


app = FastAPI(
    title="Agentic Code Reviewer",
    description="GitHub App that reviews PRs and suggests fixes via Gemini.",
)


@app.on_event("startup")
async def startup() -> None:
    _log_startup_config()

# In-memory set of processed delivery IDs (avoid duplicate work per process restart)
_seen_deliveries: set[str] = set()
_MAX_SEEN = 10_000


async def process_pr_async(context: dict[str, Any]) -> None:
    """Background task: fetch PR diff, run Critic, post review comments."""
    repo_full_name = context.get("repo_full_name")
    pr_number = context.get("pr_number")
    installation_id = context.get("installation_id")
    pr_title = context.get("pr_title")
    repo_name = context.get("repo_name")

    logger.info(
        "PR event: repo=%s pr=%s action=%s",
        repo_full_name,
        pr_number,
        context.get("action"),
    )

    if not installation_id or not repo_full_name or pr_number is None:
        logger.warning("Missing installation_id, repo_full_name, or pr_number; skipping")
        return

    # Run in thread pool so we don't block: GitHub + Gemini calls
    def _run() -> None:
        diff, head_sha, _files_info = fetch_pr_diff(installation_id, repo_full_name, pr_number)
        if not head_sha:
            logger.warning("Could not fetch PR diff for %s #%s", repo_full_name, pr_number)
            return
        if not diff or not diff.strip():
            logger.info("No changed files (or empty diff) for %s #%s", repo_full_name, pr_number)
            return

        return diff, head_sha

    try:
        result = await asyncio.to_thread(_run)
        if result is None:
            return
        diff, head_sha = result
    except Exception as e:
        logger.exception("Error fetching PR diff: %s", e)
        return

    # Critic: Gemini reviews the diff (rate-limited)
    try:
        issues = await review_diff(diff, repo_name=repo_name, pr_title=pr_title)
    except Exception as e:
        logger.exception("Critic (Gemini) failed: %s", e)
        return

    # Build comments for GitHub API: path, line, body (empty when no issues)
    comments = [
        {"path": i["path"], "line": i["line"], "body": i["body"]}
        for i in issues
    ]
    success = await asyncio.to_thread(
        post_review_comments,
        installation_id,
        repo_full_name,
        pr_number,
        head_sha,
        comments,
    )
    if success:
        if issues:
            logger.info("Posted %d comments on %s PR #%s", len(comments), repo_full_name, pr_number)
        else:
            logger.info("Posted 'No issues found' review on %s PR #%s", repo_full_name, pr_number)
    else:
        logger.warning("Failed to post review on %s PR #%s", repo_full_name, pr_number)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "Agentic Code Reviewer", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/test-gemini")
async def test_gemini() -> dict[str, str]:
    """Verify Gemini API key: ask a short question and return the reply."""
    if not GOOGLE_API_KEY:
        return {"error": "GOOGLE_API_KEY is not set in .env"}
    try:
        reply = await complete("Reply in one short sentence: what is 2+2?")
        return {"gemini": "ok", "reply": reply or "(empty)"}
    except Exception as e:
        logger.exception("Gemini test failed")
        return {"gemini": "error", "error": str(e)}


@app.post("/api/webhooks/github")
async def github_webhook(request: Request) -> Response:
    """Receive GitHub webhooks. Validate signature, then enqueue work."""
    body = await request.body()
    sig = request.headers.get("x-hub-signature-256")
    delivery = request.headers.get("x-github-delivery")
    event = request.headers.get("x-github-event")

    secret = GITHUB_APP_WEBHOOK_SECRET or ""
    if not secret:
        logger.warning("GITHUB_APP_WEBHOOK_SECRET not set - accepting any payload (dev only)")
    elif not verify_signature(body, sig, secret):
        logger.warning("Invalid webhook signature")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    if event != "pull_request":
        return Response(status_code=status.HTTP_200_OK)

    try:
        payload = json.loads(body)
    except Exception as e:
        logger.exception("Failed to parse webhook body: %s", e)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    context = parse_pr_payload(payload)
    if context is None:
        return Response(status_code=status.HTTP_200_OK)

    # Idempotency: skip if we already processed this delivery
    if delivery:
        if delivery in _seen_deliveries:
            logger.info("Duplicate delivery %s, skipping", delivery)
            return Response(status_code=status.HTTP_200_OK)
        _seen_deliveries.add(delivery)
        if len(_seen_deliveries) > _MAX_SEEN:
            _seen_deliveries.clear()

    # Return 200 immediately; process in background so GitHub doesn't timeout
    asyncio.create_task(process_pr_async(context))
    return Response(status_code=status.HTTP_200_OK)
