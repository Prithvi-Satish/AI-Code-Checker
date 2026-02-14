# Agentic Code Reviewer

GitHub App that reviews Pull Requests with **Gemini 1.5 Flash**, posts line-level comments, and can open a counter-PR with automated fixes.

## Quick start

1. **Create a virtual environment and install dependencies**

   ```bash
   cd "Github Agent"
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**

   The project uses a `.env` file in the repo root. A `.env` with `GOOGLE_API_KEY` is already present for local use. **Do not commit `.env`** (it is in `.gitignore`).

   For GitHub webhooks later, copy `.env.example` and add:
   - `GITHUB_APP_WEBHOOK_SECRET` (from your GitHub App settings)

3. **Run the app**

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Check Gemini**

   - Open [http://localhost:8000](http://localhost:8000) — should show `{"service": "Agentic Code Reviewer", "status": "ok"}`.
   - Open [http://localhost:8000/api/test-gemini](http://localhost:8000/api/test-gemini) — should show a short Gemini reply if the API key is valid.

5. **GitHub App + webhook (for live PR reviews)**

   - Create a [GitHub App](https://docs.github.com/en/apps/creating-apps): Repository permissions **Pull requests: Read & write**, **Contents: Read**, **Metadata: Read**. Subscribe to **Pull request** events. Generate a private key.
   - In `.env` set: `GITHUB_APP_ID`, `GITHUB_APP_WEBHOOK_SECRET`, `GITHUB_APP_PRIVATE_KEY` (paste the PEM; use `\n` for newlines if on one line).
   - Run [ngrok](https://ngrok.com/): `ngrok http 8000`. In the GitHub App, set the webhook URL to `https://<ngrok-host>/api/webhooks/github`.
   - Open or update a PR on a repo where the app is installed; the bot will fetch the diff, run the Critic (Gemini), and post a review with line-level comments.

## Project layout

- `app/main.py` — FastAPI app, webhook route, PR processing (fetch diff → Critic → post review).
- `app/config.py` — Loads `GOOGLE_API_KEY`, GitHub App env vars from `.env`.
- `app/webhooks/github.py` — Webhook signature verification and PR payload parsing.
- `app/github_client.py` — Installation token, fetch PR diff, post review comments.
- `app/agents/critic.py` — Critic agent: Gemini reviews diff and returns structured issues.
- `app/llm/gemini_client.py` — Gemini 1.5 Flash client with 15 RPM throttling.
- `app/llm/rate_limit.py` — Rate limiter for free-tier 15 requests/minute.

## Roadmap and troubleshooting

See **[ROADMAP.md](ROADMAP.md)** for a step-by-step run checklist, the fix for reviews not showing in the PR Conversation tab, and edge-case notes.

## Security

- Keep your **Gemini API key** and **GitHub App private key** only in `.env` or environment variables, never in code or in git.
- If the key in this repo was ever committed, rotate it in [Google AI Studio](https://aistudio.google.com/apikey) and update `.env`.

## Next steps (from spec)

- **Phase 2b:** Fixer agent + “Fix it” counter-PR (checkout branch, apply fixes, push, open PR).
- **Phase 3:** Deploy to Render (Docker + env secrets).
