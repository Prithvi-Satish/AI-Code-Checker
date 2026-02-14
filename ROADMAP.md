# Agentic Code Reviewer — Roadmap & Run Checklist

## Critical fix applied: reviews not showing

**Cause:** `create_review()` was called with `commit_id=head_sha` (string). PyGithub expects `commit` (a **Commit object**). That raised a `TypeError` every time, so the review never posted and the exception was logged as "Failed to post review".

**Fix:** Get the commit with `repo.get_commit(head_sha)` and pass `commit=commit` to `create_review()`. After pulling this change and restarting the app, new PRs should show the review in the **Conversation** tab.

---

## Roadmap: get the project running

### Phase 1 — Local run (no GitHub)

| Step | Action | Check |
|------|--------|--------|
| 1.1 | `python -m venv .venv` then `pip install -r requirements.txt` | No errors |
| 1.2 | Create `.env` with `GOOGLE_API_KEY` (from [Google AI Studio](https://aistudio.google.com/apikey)) | — |
| 1.3 | `uvicorn app.main:app --reload --port 8000` | App starts |
| 1.4 | Open http://localhost:8000 | `{"service":"Agentic Code Reviewer","status":"ok"}` |
| 1.5 | Open http://localhost:8000/api/test-gemini | `{"gemini":"ok", "reply":"..."}` |

### Phase 2 — GitHub App and webhook

| Step | Action | Check |
|------|--------|--------|
| 2.1 | Create [GitHub App](https://github.com/settings/apps/new): Pull requests Read & write, Contents Read, Metadata Read; subscribe to **Pull request** | App created |
| 2.2 | Generate **Private key**, set **Webhook secret** (generate random string) | Key downloaded, secret copied |
| 2.3 | In `.env` set: `GITHUB_APP_ID`, `GITHUB_APP_WEBHOOK_SECRET`, `GITHUB_APP_PRIVATE_KEY` (full PEM; use `\n` for newlines if on one line) | No spaces around `=`, key starts with `-----BEGIN` |
| 2.4 | Run `ngrok http 8000`, copy HTTPS URL | e.g. `https://abc.ngrok-free.app` |
| 2.5 | In GitHub App → General → Webhook URL: `https://<ngrok>/api/webhooks/github` | Saved |
| 2.6 | Install app on repo: Settings → Installations → Configure → select repo | Repo selected |
| 2.7 | Restart uvicorn; check startup log: `Config: GITHUB_APP_ID=set, ... PRIVATE_KEY=set` | All "set" in log |

### Phase 3 — Trigger and verify review

| Step | Action | Check |
|------|--------|--------|
| 3.1 | In repo: create branch (e.g. `test-agent`), add/edit a file, push, open PR (base: main, compare: your branch) | PR created |
| 3.2 | In uvicorn terminal: `PR event: repo=... pr=... action=opened` | Webhook received |
| 3.3 | Then: `Posted review on ... PR #N (0 line comments)` or `(N line comments)` | No "Failed to post review" |
| 3.4 | On GitHub: open PR → **Conversation** tab | Review from app with body "No issues found" or "found the following issues" |
| 3.5 | **Files changed**: line comments if Critic found issues | Optional |

---

## Edge cases and behavior

| Area | Edge case | Handling |
|------|-----------|----------|
| **Webhook** | Duplicate delivery (retries) | `X-GitHub-Delivery` idempotency: skip if already seen. |
| **Webhook** | Missing `installation` or `pull_request` | Ignore event, return 200. |
| **Webhook** | Action not in `opened` / `synchronized` / `reopened` | Ignore, return 200. |
| **Payload** | `installation_id` as string (e.g. from some proxies) | `int(installation_id)` in `get_installation_token`. |
| **GitHub API** | `create_review` parameter | Must pass `commit` (Commit object), not `commit_id` (string). |
| **Diff** | No changed files or empty patch | Log "No changed files", return without posting review. |
| **Diff** | File >500 lines or >50KB patch | Include truncated placeholder in combined diff, skip full content. |
| **Diff** | Binary / no patch | Skipped in loop (`if not patch.strip(): continue`). |
| **Critic** | Gemini returns invalid JSON | `complete_json` strips markdown and retries parse; on failure returns `[]` (no issues). |
| **Critic** | Gemini timeout or rate limit | Exception logged "Critic (Gemini) failed"; no review posted. |
| **Rate limit** | Gemini 15 RPM | `throttle_gemini()` sleeps so requests are ≥4 s apart. |
| **Review** | No issues found | Still post review with body "No issues found" (body-only, `comments=[]`). |
| **Review** | Line number invalid for file | GitHub API may reject; exception logged "Failed to post review". |
| **Private key** | PEM in .env with literal `\n` | `config.py` does `_raw_key.replace("\\n", "\n")`. |
| **Fork PRs** | PR from fork | App can comment on main-repo PR; cannot push to fork (Fix-it would need to target main repo only). |

---

## If reviews still don’t appear

1. **Restart uvicorn** after code/config changes.
2. **Startup log:** Look for `PRIVATE_KEY=MISSING` or `GOOGLE_API_KEY=MISSING` and fix `.env`.
3. **On PR event:** Look for `Failed to post review` or `Failed to get installation token` and fix App ID / key / permissions.
4. **Recent Deliveries:** Response **200** = webhook reached app; then logs explain success or failure.
5. **GitHub App permissions:** Pull requests must be **Read and write** (not only Read).

---

## Next steps (from original spec)

- **Phase 2b:** Fixer agent + “Fix it” counter-PR (checkout branch, apply fixes, push, open PR).
- **Phase 3:** Deploy to Render (Docker + env secrets).
