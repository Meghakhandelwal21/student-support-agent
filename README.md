# Intelligent Student Support Agent (Assignments 1 & 2)

A teaching/demo implementation of a chat-style Student Support Agent. It uses **fictional records only**. Assignment 2 extends the same Assignment 1 application with authorization, approval workflow, and auditability.

## Features mapped to the brief

### Assignment 1
- Chat UI using Streamlit.
- Student fee and scholarship tools plus support-ticket creation.
- Retrieval from a small student policy document; only matching sections are added to context.
- Student-scoped persistent memory for non-sensitive details.
- Context-aware responses; optional LLM API with a deterministic fallback.
- Per-run trace with tools, retrieved evidence, permission decisions, latency and token usage where provider usage is available.
- Evaluation script producing `evaluation_results.csv`.

### Assignment 2
- Demo login with hashed passwords and roles.
- Server-side checks in database tool functions: students can only read their own private records.
- Sensitive course/programme changes are staged as pending requests.
- Only the admin reviewer account can approve or reject a request.
- Rejected requests are not executed. In this demo, approval records the decision but does not modify an external institutional system.
- Audit records for record access, memory, tickets, approval and rejection.
- Password/OTP/token-like inputs are excluded from persistent memory.

## Demo accounts

These are fictional local demo credentials; change them before any deployment.

| Account | Username | Password |
|---|---|---|
| Aarav (student) | `student001` | `Demo@123` |
| Diya (student) | `student002` | `Demo@123` |
| Admin reviewer | `admin001` | `Admin@123` |

## Setup

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

The SQLite database is initialized automatically on first run. It contains synthetic demo data.

## Optional LLM setup

The application works without an API key using a deterministic fallback. To enable generated responses, copy `.env.example` to `.env`, fill in your provider settings, and load the variables into your shell before running Streamlit. Do not commit `.env`.

PowerShell example:
```powershell
$env:OPENAI_API_KEY="your-key"
$env:LLM_MODEL="gpt-4o-mini"
streamlit run app.py
```

For an OpenAI-compatible provider, set `OPENAI_BASE_URL` as well. Check the provider's current model name and endpoint documentation.

## Test and evaluate

```bash
pytest -q
python evaluate.py
```

Open `evaluation_results.csv` after running the evaluation. Do not claim benchmark results until you have actually run the tests and checked the output. Without a model API, token counts will be blank. Compare results with your Assignment 1 baseline by recording the same test set before adding security controls.

## Suggested demo scenarios

1. Sign in as `student001`; ask for your fee status. It should be allowed.
2. Ask for `student002`'s fee status. It should be blocked by application code.
3. Ask to change your course. It should create a pending request, not execute it.
4. Sign in as `admin001`; approve or reject the pending request. Rejection leaves the request unexecuted.
5. Ask about a failed fee-payment portal. The relevant handbook chunk should appear in the trace.
6. Enter an OTP/password-like statement. The app should warn you and not save it to memory.
7. Ask to create a support ticket.
8. Use the audit table to show allowed and blocked attempts.

## Architecture

`app.py` → identity/session → `agent.py` orchestration → `db.py` tools / `retrieval.py` policy retrieval / `security.py` secret detection → trace and audit.

Authorization is enforced in tool/database code and not just in the prompt. The LLM is not a security boundary.

## Important limitations (explain these honestly in the video)

- This is a local academic demo, not a production student information system.
- Demo passwords and records are synthetic. The simple sign-in is not a substitute for institutional SSO, MFA, secure session management, rate limiting, or a security review.
- Policy retrieval is lightweight keyword matching, not a semantic vector database. You can extend it if the course specifically expects embeddings.
- Sensitive change approval is recorded in the demo database; no external university record is changed.
- The optional LLM call is a single response-generation call after application-side routing, not a full model-native tool-calling loop. The routing/tool decisions are implemented in application code and can be discussed as a controlled orchestration design.
- Latency and token usage must be measured from your own runs. Token usage is shown only if the configured API provider returns usage data.

## Public GitHub checklist

- Include all source files, policy sample, README and requirements.
- Do not commit `.env`, API keys, database files or real student data.
- Run `pytest -q` and `python evaluate.py`.
- Add screenshots and your explanatory video link to the README after recording.
