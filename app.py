import streamlit as st
from db import init_db, authenticate, get_student_profile, get_pending_requests, approve_change, reject_change
from agent import run_agent
from db import get_recent_audit

st.set_page_config(page_title="Student Support Agent", page_icon="🎓", layout="wide")
init_db()

st.title("🎓 Intelligent Student Support Agent")
st.caption("Assignments 1 & 2 • Demo application using synthetic student records")

if "student" not in st.session_state:
    st.session_state.student = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "trace" not in st.session_state:
    st.session_state.trace = []

with st.sidebar:
    st.header("Demo sign-in")
    st.caption("Use one of the synthetic demo accounts.")
    demo_accounts = {
        "Aarav (student001)": ("student001", "Demo@123"),
        "Diya (student002)": ("student002", "Demo@123"),
        "Admin reviewer (admin001)": ("admin001", "Admin@123"),
    }
    chosen = st.selectbox("Account", list(demo_accounts.keys()))
    username, password = demo_accounts[chosen]
    if st.button("Sign in", use_container_width=True):
        user = authenticate(username, password)
        if user:
            st.session_state.student = user
            st.session_state.messages = []
            st.success(f"Signed in as {user['display_name']}")
            st.rerun()
        else:
            st.error("Sign-in failed.")
    if st.session_state.student:
        st.success(f"Signed in: {st.session_state.student['display_name']}")
        st.write(f"Role: `{st.session_state.student['role']}`")
        if st.button("Sign out", use_container_width=True):
            st.session_state.student = None
            st.session_state.messages = []
            st.rerun()
    st.divider()
    st.markdown("**Try these scenarios**")
    st.markdown("- What is my fee status?\n- What is my scholarship status?\n- Can you change my course?\n- Show student002's fee status.\n- The payment portal failed. Can I pay next working day?\n- Remember that my programme is PGDM.")

if not st.session_state.student:
    st.info("Sign in from the sidebar to begin. All accounts and records are fictional and intended for demonstration.")
    st.stop()

student = st.session_state.student
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Chat")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("evidence"):
                with st.expander("Retrieved evidence / trace"):
                    st.json(message["evidence"])
    prompt = st.chat_input("Ask about fees, scholarships, policies, or support...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Checking the right information and permissions..."):
                answer, trace = run_agent(prompt, student)
                st.markdown(answer)
                with st.expander("Retrieved evidence / trace"):
                    st.json(trace)
        st.session_state.messages.append({"role": "assistant", "content": answer, "evidence": trace})
        st.session_state.trace.append(trace)
        st.rerun()

with col2:
    st.subheader("Sensitive action approvals")
    pending = get_pending_requests()
    pending = [p for p in pending if student["role"] == "admin" or p["student_id"] == student["student_id"]]
    if not pending:
        st.caption("No pending requests.")
    for item in pending:
        st.warning(f"{item['student_id']}: {item['requested_change']}")
        st.caption(f"Request ID: {item['request_id']}")
        if student["role"] == "admin":
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Approve", key=f"approve_{item['request_id']}"):
                    approve_change(item["request_id"], student["username"])
                    st.success("Approved and executed.")
                    st.rerun()
            with c2:
                if st.button("Reject", key=f"reject_{item['request_id']}"):
                    reject_change(item["request_id"], student["username"])
                    st.info("Rejected; change not executed.")
                    st.rerun()
        else:
            st.caption("Only the admin reviewer can approve or reject this request.")

    st.divider()
    st.subheader("Recent audit events")
    st.caption("Audit entries are for demonstration; avoid using real student data.")
    st.dataframe(get_recent_audit(limit=10), use_container_width=True, hide_index=True)
