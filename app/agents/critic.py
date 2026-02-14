"""Critic agent: analyze diff and return structured issues (Gemini 1.5 Flash)."""
import logging
from typing import Any

from app.llm.gemini_client import complete_json

logger = logging.getLogger(__name__)

CRITIC_SYSTEM = """You are a senior code reviewer. Analyze the following unified diff for:
1) Logic bugs
2) Security issues (SQL injection, XSS, hardcoded secrets, unsafe deserialization)
3) Style/maintainability (PEP8, clear naming, error handling)

For each issue output exactly:
- file: path as in the diff (e.g. src/auth/login.py)
- line: line number in the NEW file (right side of diff)
- end_line: optional, if the issue spans multiple lines
- severity: one of low, medium, high, critical
- category: one of logic, security, style
- message: short description of the issue
- snippet: the exact line(s) of code that have the issue

Respond with a single JSON object only. No markdown, no other text.
Schema: {"issues": [ {"file": "...", "line": N, "end_line": N or null, "severity": "...", "category": "...", "message": "...", "snippet": "..."} ]}
If there are no issues, respond: {"issues": []}"""


async def review_diff(diff: str, repo_name: str | None = None, pr_title: str | None = None) -> list[dict[str, Any]]:
    """
    Send the PR diff to Gemini and return a list of issues.
    Each issue has: file, line, end_line (optional), severity, category, message, snippet.
    """
    if not diff or not diff.strip():
        return []
    context = ""
    if repo_name:
        context += f"Repository: {repo_name}\n"
    if pr_title:
        context += f"PR title: {pr_title}\n"
    context += "\nDiff:\n" + diff
    out = await complete_json(context, system_instruction=CRITIC_SYSTEM)
    if not out or "issues" not in out:
        return []
    issues = out["issues"]
    if not isinstance(issues, list):
        return []
    # Normalize for GitHub API: path, line, body
    result = []
    for i in issues:
        if not isinstance(i, dict):
            continue
        file_path = i.get("file")
        line = i.get("line")
        if not file_path or line is None:
            continue
        severity = i.get("severity", "medium")
        category = i.get("category", "")
        message = i.get("message", "")
        snippet = (i.get("snippet") or "").strip()
        body = f"**[{severity}]** ({category})\n\n{message}"
        if snippet:
            body += f"\n\n```\n{snippet}\n```"
        result.append({
            "file": file_path,
            "path": file_path,
            "line": int(line) if isinstance(line, (int, float)) else line,
            "body": body,
            "message": message,
            "severity": severity,
            "category": category,
        })
    return result
