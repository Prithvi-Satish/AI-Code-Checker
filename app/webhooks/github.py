"""GitHub webhook signature verification and payload parsing."""
import hashlib
import hmac
import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_signature(payload_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify X-Hub-Signature-256 (HMAC-SHA256)."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_pr_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract PR-related fields. Returns None if not a pull_request event we handle."""
    if payload.get("installation") is None:
        return None
    if payload.get("pull_request") is None:
        return None
    action = payload.get("action")
    if action not in ("opened", "synchronized", "reopened"):
        return None

    pr = payload["pull_request"]
    repo = payload.get("repository", {})
    return {
        "action": action,
        "installation_id": payload["installation"]["id"],
        "repo_full_name": repo.get("full_name"),
        "repo_owner": repo.get("owner", {}).get("login"),
        "repo_name": repo.get("name"),
        "pr_number": pr.get("number"),
        "pr_head_sha": pr.get("head", {}).get("sha"),
        "pr_head_ref": pr.get("head", {}).get("ref"),
        "pr_base_ref": pr.get("base", {}).get("ref"),
        "pr_title": pr.get("title"),
        "pr_html_url": pr.get("html_url"),
    }
