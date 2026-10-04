import logfire

from app.agents.state import AgentState
from app.services.retrieval.qdrant_service import (
    search_enterprise_knowledge,
)
from app.services.retrieval.ranking_service import rerank_documents


def retrieve_node(state: AgentState) -> dict:
    """
    Performs vector search and semantic reranking for technical queries.
    """

    query = state["current_query"].strip()

    if not query:
        raise ValueError("Retrieval query cannot be empty.")

    with logfire.span("Knowledge Retrieval"):
        logfire.info(
            "Searching Qdrant for technical query",
            query_length=len(query),
        )

        raw_results = search_enterprise_knowledge(
            query,
            limit=15,
        )

        logfire.info(
            "Retrieved candidates from Vector DB",
            count=len(raw_results),
        )

        doc_contents = [
            doc["content"].strip()
            for doc in raw_results
            if isinstance(doc.get("content"), str)
            and doc["content"].strip()
        ]

        if not doc_contents:
            logfire.warning(
                "No valid document content found for retrieval query."
            )

            return {
                "documents": [],
                "status": "No relevant technical context found.",
                "plan": state["plan"] + [
                    "Context Retrieval: No Results"
                ],
            }

        with logfire.span("Semantic Reranking"):
            reranked_contents = rerank_documents(
                query,
                doc_contents,
                top_n=5,
            )

            logfire.info(
                "Reranking complete",
                kept_documents=len(reranked_contents),
            )

        formatted_docs = [
            f"CONTENT:\n{doc}"
            for doc in reranked_contents
        ]

    return {
        "documents": formatted_docs,
        "status": "Technical context retrieved.",
        "plan": state["plan"] + ["Context Retrieved"],
    }
