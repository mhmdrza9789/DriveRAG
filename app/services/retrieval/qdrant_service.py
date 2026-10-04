from typing import Any

import logfire
from qdrant_client import QdrantClient

from app.config import settings
from app.services.retrieval.embedding import GeminiEmbeddingProvider


client = QdrantClient(
    url=settings.QDRANT_CLUSTER_ENDPOINT,
    api_key=settings.QDRANT_API_KEY,
)


def search_enterprise_knowledge(
    query: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """
    Search the enterprise knowledge base in Qdrant.

    Args:
        query: User's natural-language query.
        limit: Maximum number of results to return.

    Returns:
        A list of retrieved documents with their source and score.
    """
    if not query.strip():
        return []

    if limit <= 0:
        return []

    try:
        provider = GeminiEmbeddingProvider()
        query_vector = provider.embed_query(query)

        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        results: list[dict[str, Any]] = []

        for point in response.points:
            payload = point.payload or {}

            results.append(
                {
                    "content": payload.get("text", ""),
                    "source": payload.get("source", "Unknown"),
                    "score": point.score,
                }
            )

        logfire.info(
            "Qdrant search completed",
            query=query,
            result_count=len(results),
            collection_name=settings.QDRANT_COLLECTION,
        )

        return results

    except Exception:
        logfire.exception(
            "Qdrant search failed",
            query=query,
            collection_name=settings.QDRANT_COLLECTION,
        )
        return []
