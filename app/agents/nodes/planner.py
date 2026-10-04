# app/agents/nodes/planner.py

import logfire
from langchain_groq import ChatGroq

from app.agents.state import AgentState
from app.config import settings


MAX_HISTORY_MESSAGES = settings.MAX_HISTORY_MESSAGES
MAX_QUERY_LENGTH = settings.MAX_QUERY_LENGTH
CONVERSATIONAL = "CONVERSATIONAL"


llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.GROQ_MODEL,
    temperature=0,
)


def _get_message_content(message: dict) -> str:
    """Return the text content of a state message, if present."""
    content = message.get("content", "")
    return content.strip() if isinstance(content, str) else ""


def planner_node(state: AgentState) -> dict:
    """
    Decide whether the latest message needs document retrieval.

    Returns only updates to AgentState. The graph must route
    CONVERSATIONAL to a non-retrieval node.
    """
    messages = state.get("messages", [])

    if not messages:
        return {
            "current_query": CONVERSATIONAL,
            "status": "No user message provided",
            "plan": ["Intent: No input", "Retrieval: Skipped"],
        }

    latest_message = messages[-1]
    user_message = _get_message_content(latest_message)

    if latest_message.get("role") != "user" or not user_message:
        return {
            "current_query": CONVERSATIONAL,
            "status": "No valid latest user message",
            "plan": ["Intent: No valid user input", "Retrieval: Skipped"],
        }

    recent_history = messages[:-1][-MAX_HISTORY_MESSAGES:]

    history_lines = []
    for message in recent_history:
        content = _get_message_content(message)
        if not content:
            continue

        role = message.get("role")
        if role == "user":
            label = "User"
        elif role == "assistant":
            label = "Assistant"
        else:
            continue

        history_lines.append(f"{label}: {content}")

    history = "\n".join(history_lines) or "(No previous conversation)"

    prompt = f"""
You are the planner for a document-based question-answering assistant.

Decide whether the latest user message needs retrieval from the
assistant's document collection. Use the conversation history to resolve
references in follow-up questions.

CONVERSATION HISTORY:
{history}

LATEST USER MESSAGE:
{user_message}

Rules:
- If the message is a greeting, small talk, or can be answered using only
  the conversation history, output exactly: CONVERSATIONAL
- If answering requires information from the document collection, output
  a concise, standalone search query that includes the necessary context
  from the conversation history.
- Do not limit retrieval to specific topics.
- Do not answer the user's question.
- Do not add labels, quotes, explanations, or markdown.

Output exactly one line: CONVERSATIONAL or a search query.
""".strip()

    with logfire.span("Planner Decision"):
        try:
            raw_decision = llm.invoke(prompt).content
        except Exception:
            logfire.exception("Planner LLM request failed")
            raise

        if not isinstance(raw_decision, str):
            raise ValueError("Planner returned non-text output")

        decision = raw_decision.strip()

        # Accept minor formatting deviations without treating them as queries.
        normalized_decision = decision.strip(" \t\n\r`'\".!").upper()

        if normalized_decision == CONVERSATIONAL:
            logfire.info("Planner selected conversational route")
            return {
                "current_query": CONVERSATIONAL,
                "status": "Handling conversationally",
                "plan": ["Intent: Conversational", "Retrieval: Skipped"],
            }

        # A search query must be a single, non-empty line.
        if not decision or "\n" in decision or len(decision) > MAX_QUERY_LENGTH:
            raise ValueError("Planner returned an invalid search query")

        logfire.info("Planner selected retrieval route")

        return {
            "current_query": decision,
            "status": "Document retrieval needed",
            "plan": ["Intent: Retrieval", "Retrieval: Required"],
        }
