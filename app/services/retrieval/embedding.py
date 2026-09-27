from __future__ import annotations

import logging
import random
import time
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider:
    def __init__(self):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION

        self._client = GoogleGenerativeAIEmbeddings(
            model=self.model_name,
            google_api_key=settings.GEMINI_API_KEY,
        )

    def _retry(self, fn, *args, **kwargs):
        max_retries = 5

        for attempt in range(max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                message = str(exc).lower()
                retryable = (
                    "429",
                    "timeout",
                    "deadline",
                    "503",
                    "504",
                    "exhausted",
                )

                if not any(code in message for code in retryable):
                    raise

                if attempt == max_retries:
                    raise

                wait = (2**attempt) + random.random()
                logger.warning(
                    "Embedding request failed; retrying in %.1f seconds (%d/%d): %s",
                    wait,
                    attempt + 1,
                    max_retries,
                    exc,
                )
                time.sleep(wait)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        batch_size = 2
        all_vectors: List[List[float]] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors = self._retry(self._client.embed_documents, batch)
            all_vectors.extend(vectors)

            if start + batch_size < len(texts):
                time.sleep(2)

        return all_vectors

    def embed_query(self, text: str) -> List[float]:
        return self._retry(self._client.embed_query, text)
