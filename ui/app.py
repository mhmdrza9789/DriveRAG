import os
import uuid

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv



# Load .env from the project root
env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)
load_dotenv(dotenv_path=env_path)


# Page configuration
st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
)


# Logfire configuration
try:
    token = os.getenv("LOGFIRE_TOKEN")

    if token:
        logfire.configure(token=token)
        LOGFIRE_STATUS = "Connected & Tracing"
    else:
        LOGFIRE_STATUS = "Not configured"

except Exception as e:
    print(f"Logfire Init Error in UI: {e}")
    LOGFIRE_STATUS = f"Standby (Error: {e})"


AI_AVATAR = "🤖"
USER_AVATAR = "👤"


# Session management
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

    logfire.info(
        "New user session created",
        session_id=st.session_state.session_id,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []


# Sidebar
with st.sidebar:
    st.title("🧠 Agent OS")
    st.markdown("---")

    st.success(f"Logfire: {LOGFIRE_STATUS}")
    st.info(f"Memory ID: {st.session_state.session_id[:8]}")

    if st.button(
        "🗑️ Clear History & Memory",
        width="stretch",
        type="primary",
    ):
        logfire.info(
            "Starting a new conversation",
            previous_session_id=st.session_state.session_id,
        )

        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()


# Main chat
st.title("🤖 Enterprise Agentic Assistant")


# Display messages from the current Streamlit session
for message in st.session_state.messages:
    avatar = (
        AI_AVATAR
        if message["role"] == "assistant"
        else USER_AVATAR
    )

    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# New message
if prompt := st.chat_input("Ask about your documentation..."):
    session_id = st.session_state.session_id

    with logfire.span(
        "User Chat Interaction",
        user_query=prompt,
        session_id=session_id,
    ):
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )

        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=AI_AVATAR):
            try:
                with st.status(
                    "🔍 Agent is thinking...",
                    expanded=True,
                ) as status:
                    with logfire.span("Calling RAG Backend"):
                        base_url = os.getenv(
                            "BACKEND_URL",
                            "http://localhost:8000",
                        )
                        url = f"{base_url.rstrip('/')}/query"

                        payload = {
                            "q": prompt,
                            "thread_id": session_id,
                        }

                        response = requests.post(
                            url,
                            json=payload,
                            timeout=60,
                        )
                        response.raise_for_status()
                        data = response.json()

                    for step in data.get("thought_process", []):
                        st.write(f"⚙️ {step}")

                    status.update(
                        label="✅ Answer Synthesized",
                        state="complete",
                        expanded=False,
                    )

                # IMPORTANT:
                # This is inside the assistant chat message,
                # but outside the st.status block.
                full_answer = data.get("answer")

                if not isinstance(full_answer, str) or not full_answer.strip():
                    st.error("Backend returned an empty answer.")
                    logfire.error(
                        "Backend returned an empty answer",
                        session_id=session_id,
                    )
                else:
                    # Display directly for now; no typing animation.
                    st.markdown(full_answer)

                    sources = data.get("sources", [])

                    if sources:
                        with st.expander("📄 View Retrieved Context (Sources)"):
                            for index, source in enumerate(sources):
                                source_text = str(source)
                                preview = (
                                    source_text[:100].replace("\n", " ") + "..."
                                )

                                with st.expander(
                                    f"Chunk {index + 1}: {preview}"
                                ):
                                    st.info(source_text)

                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_answer}
                    )

                    logfire.info(
                        "Chat cycle completed successfully",
                        session_id=session_id,
                    )

            except requests.RequestException as e:
                logfire.error(
                    "UI-Backend connection failed",
                    error=str(e),
                    session_id=session_id,
                )
                st.error(f"Backend request failed: {e}")

            except ValueError as e:
                logfire.error(
                    "Backend returned invalid JSON",
                    error=str(e),
                    session_id=session_id,
                )
                st.error(f"Backend returned invalid JSON: {e}")
