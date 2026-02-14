"""GitHub API client: installation token, PR diff, post review comments."""
import logging
from typing import Any

from github import GithubIntegration, Github

from app.config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY

logger = logging.getLogger(__name__)

# Max patch size per file to send to LLM (lines)
MAX_PATCH_LINES = 500
MAX_PATCH_BYTES = 50_000


def _get_private_key() -> str:
    return GITHUB_APP_PRIVATE_KEY or ""


def get_installation_token(installation_id: int) -> str | None:
    """Return a short-lived installation access token for the GitHub App."""
    app_id = GITHUB_APP_ID
    key = _get_private_key()
    if not app_id or not key:
        logger.warning("GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY not set")
        return None
    try:
        integration = GithubIntegration(app_id, key)
        auth = integration.get_access_token(int(installation_id))
        return auth.token
    except Exception as e:
        logger.exception("Failed to get installation token: %s", e)
        return None


def fetch_pr_diff(installation_id: int, repo_full_name: str, pr_number: int) -> tuple[str, str | None, list[dict[str, Any]]]:
    """
    Fetch PR changed files and build a single diff string for the LLM.
    Returns (combined_diff, head_sha, files_info).
    files_info: list of {"filename": str, "patch": str, "line_offset": int} for mapping line numbers.
    """
    token = get_installation_token(installation_id)
    if not token:
        return "", None, []

    g = Github(token)
    try:
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        head_sha = pr.head.sha
        files = pr.get_files()
    except Exception as e:
        logger.exception("Failed to fetch PR: %s", e)
        return "", None, []

    combined_parts: list[str] = []
    files_info: list[dict[str, Any]] = []
    line_offset = 0

    for f in files:
        filename = f.filename
        patch = f.patch or ""
        if not patch.strip():
            continue
        # Skip binary or huge files
        lines = patch.count("\n") + 1
        if lines > MAX_PATCH_LINES or len(patch) > MAX_PATCH_BYTES:
            combined_parts.append(f"# File {filename} (truncated: {lines} lines)\n")
            files_info.append({"filename": filename, "patch": "", "line_offset": line_offset})
            line_offset += 1
            continue
        combined_parts.append(f"--- File: {filename}\n")
        combined_parts.append(patch)
        combined_parts.append("\n")
        files_info.append({"filename": filename, "patch": patch, "line_offset": line_offset})
        # Approximate: each file block adds header + patch lines
        line_offset += 1 + lines

    return "".join(combined_parts), head_sha, files_info


def post_review_comments(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    comments: list[dict[str, Any]],
) -> bool:
    """
    Post a PR review with line-level comments (or body-only when comments is empty).
    comments: list of {"path": str, "line": int, "body": str} (optional "start_line", "line" for multi-line).
    """
    token = get_installation_token(installation_id)
    if not token:
        return False
    g = Github(token)
    try:
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        # PyGithub create_review expects a Commit object, not a string
        commit = repo.get_commit(head_sha)
        # Build review comment payload: path, line, body (ReviewComment dicts)
        review_comments = []
        for c in comments:
            path = c.get("path") or c.get("file")
            line = c.get("line")
            body = c.get("body") or c.get("message")
            if not path or line is None or not body:
                continue
            review_comments.append({
                "path": path,
                "line": line,
                "body": body[:65535],  # GitHub limit
            })
        body_text = (
            "Agentic Code Reviewer (Gemini) found the following issues."
            if review_comments
            else "Agentic Code Reviewer (Gemini) reviewed this PR. No issues found."
        )
        pr.create_review(
            commit=commit,
            body=body_text,
            event="COMMENT",
            comments=review_comments,
        )
        logger.info("Posted review on %s PR #%s (%d line comments)", repo_full_name, pr_number, len(review_comments))
        return True
    except Exception as e:
        logger.exception("Failed to post review: %s", e)
        return False
