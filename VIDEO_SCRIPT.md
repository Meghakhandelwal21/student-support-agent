# Explanatory video walkthrough (target: 6–9 minutes)

## 1. Introduction (30 sec)
"This is my Intelligent Student Support Agent for Agentic AI Engineering Assignments 1 and 2. It uses fictional data. Assignment 1 demonstrates tools, policy retrieval, memory and tracing. Assignment 2 adds privacy, authorization, human approval and audit logs."

## 2. Architecture (60 sec)
Show README architecture. Explain Streamlit UI, agent orchestration, SQLite tools, policy retrieval, memory and audit records. Explain that the LLM is optional and the app can run in fallback mode.

## 3. Assignment 1 scenarios (2 min)
- Sign in as student001 and ask for fee status.
- Ask about the failed payment portal and open the trace to show the retrieved policy chunk.
- Create a support ticket.
- Save a harmless preference and explain that memories are scoped to the student.
- Ask a question the policy does not answer; show the uncertainty-aware response.

## 4. Assignment 2 security scenarios (2 min)
- Ask for student002's private fee record while signed in as student001; show access denied.
- Request a course change; show pending approval and that no record is changed automatically.
- Sign in as admin001 and reject the request; show audit evidence and the rejected status.
- Enter a password/OTP-like string; explain it is rejected from persistent memory.
- Show audit entries for allowed and blocked actions.

## 5. Evaluation and measurements (60–90 sec)
Run `pytest -q` and `python evaluate.py`. Open `evaluation_results.csv`. Explain task success, privacy tests, approval tests, latency, trace/evidence, and token counts. Token usage is blank when no API is configured. Do not invent metrics; report the values from your actual run. Compare against an Assignment 1 baseline if you recorded it.

## 6. Close (20 sec)
Summarize the key design decision: security is enforced in application/tool code, not trusted to an LLM prompt. Mention the demo limitations honestly.
