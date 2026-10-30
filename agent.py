import os
import re
import time
from db import (
    get_fee_status, get_scholarship_status, create_support_ticket,
    request_sensitive_change, save_memory, get_memories, add_audit
)
from retrieval import retrieve_policy
from security import contains_sensitive_secret

SYSTEM_PROMPT = """You are a careful Student Support Agent for a fictional institution.
Use only supplied tool results and retrieved policy evidence for institution-specific claims.
Never invent fee, scholarship, or policy facts. If evidence is insufficient, say so.
Never ask for or store passwords, OTPs, access tokens, or payment-card details.
A student can access only their own private record. Sensitive changes must be staged for approval.
Keep answers concise and explain next steps.
"""

def _safe_text(text):
    # Mask common secret-like values before any persistent logging or memory handling.
    text = re.sub(r'(?i)\b(password|otp|token)\s*[:=]\s*\S+', r'\1=[REDACTED]', text)
    return text

def run_agent(question, student):
    start = time.perf_counter()
    trace = {
        "user": student["username"],
        "student_id": student["student_id"],
        "tools": [],
        "retrieved_evidence": [],
        "permission_decisions": [],
        "approval_status": "not_required",
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }
    if contains_sensitive_secret(question):
        answer = ("For your safety, please do not share passwords, OTPs, or access tokens in chat. "
                  "I will not save that sensitive content to long-term memory. How else can I help?")
        add_audit(student["username"], "sensitive_input", "blocked_from_memory", "blocked", "secret-like content detected")
        trace["permission_decisions"].append("Sensitive content excluded from persistent memory")
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return answer, trace

    lower = question.lower()
    context = []
    requested_student = student["student_id"]
    # If a prompt explicitly names another demo student ID, pass that target to the tool.
    # The tool performs the actual authorization check; this parser is not the security boundary.
    mentioned_id = re.search(r"\bstudent\d{3}\b", lower)
    if mentioned_id:
        requested_student = mentioned_id.group(0)

    if any(k in lower for k in ["fee", "fees", "payment", "paid", "dues"]):
        result = get_fee_status(requested_student, requester=student)
        trace["tools"].append("get_fee_status")
        trace["permission_decisions"].append(result.get("permission", "allowed"))
        if result.get("allowed"):
            context.append(f"Fee tool result: {result['data']}")
        else:
            answer = result["message"]
            trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            return answer, trace

    if "scholarship" in lower or "stipend" in lower:
        result = get_scholarship_status(requested_student, requester=student)
        trace["tools"].append("get_scholarship_status")
        trace["permission_decisions"].append(result.get("permission", "allowed"))
        if result.get("allowed"):
            context.append(f"Scholarship tool result: {result['data']}")
        else:
            answer = result["message"]
            trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            return answer, trace

    if any(k in lower for k in ["change my course", "change course", "update my record", "change my programme", "change my program"]):
        requested = question.strip()
        result = request_sensitive_change(student, requested)
        trace["tools"].append("request_sensitive_change")
        trace["approval_status"] = "pending" if result.get("allowed") else "blocked"
        trace["permission_decisions"].append(result.get("permission", "allowed"))
        add_audit(student["username"], "sensitive_change", requested, "approval_required" if result.get("allowed") else "blocked", result.get("message", ""))
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result["message"], trace

    if any(k in lower for k in ["support ticket", "raise a ticket", "create a ticket", "support request"]):
        result = create_support_ticket(student, question)
        trace["tools"].append("create_support_ticket")
        trace["permission_decisions"].append(result.get("permission", "allowed"))
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result["message"], trace

    policy = retrieve_policy(question)
    if policy:
        trace["retrieved_evidence"] = [{"source": p["source"], "chunk_id": p["chunk_id"], "text": p["text"]} for p in policy]
        context.extend(["Policy evidence: " + p["text"] for p in policy])

    memories = get_memories(student["student_id"])
    if memories and any(k in lower for k in ["remember", "programme", "program", "earlier", "before", "my preference"]):
        context.append("Relevant saved memory: " + "; ".join(m["memory_text"] for m in memories))

    if "remember that" in lower or "remember my" in lower:
        memory_text = question.split("remember", 1)[-1].strip(" :")
        if not contains_sensitive_secret(memory_text):
            save_memory(student["student_id"], _safe_text(memory_text))
            add_audit(student["username"], "save_memory", _safe_text(memory_text), "allowed", "non-sensitive memory saved")
            answer = "I’ve saved that non-sensitive detail for future sessions."
        else:
            answer = "I can’t save sensitive information such as passwords or OTPs."
        trace["tools"].append("save_memory")
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return answer, trace

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL") or None
            )
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {question}\n\nRelevant context only:\n" + ("\n".join(context) if context else "No relevant policy, record, or memory evidence found.")}
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
            )
            answer = response.choices[0].message.content or "I couldn't produce a response. Please try again."
            usage = response.usage
            if usage:
                trace["input_tokens"] = getattr(usage, "prompt_tokens", None)
                trace["output_tokens"] = getattr(usage, "completion_tokens", None)
            trace["model"] = model
        except Exception as exc:
            answer = _fallback_answer(question, context)
            trace["llm_error"] = type(exc).__name__
    else:
        answer = _fallback_answer(question, context)

    trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
    add_audit(student["username"], "chat_query", _safe_text(question), "allowed", "answered with available context")
    return answer, trace

def _fallback_answer(question, context):
    if context:
        return "Here is the relevant information I found:\n\n" + "\n\n".join(context) + "\n\nIf you need a definitive decision, please confirm with the student administration office."
    return ("I couldn't find enough verified information in the available student record or policy document to answer that confidently. "
            "Please contact the student administration office for confirmation.")
