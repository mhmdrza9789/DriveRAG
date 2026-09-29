from __future__ import annotations

from pathlib import Path
from typing import Iterable
import uuid

import logfire
from qdrant_client import QdrantClient, models

from app.config import settings
from app.ingestion.chuncking.splitter import chunk_text
from app.ingestion.loaders.dispatcher import parse_file
from app.ingestion.persistence.local_disk import save_processed_locally
from app.services.retrieval.embedding import GeminiEmbeddingProvider


NAMESPACE_INGESTION = uuid.UUID("12345678-1234-5678-1234-567812345678")
UPSERT_BATCH_SIZE = 5


def _batched(
    items: list[str], batch_size: int
) -> Iterable[tuple[int, list[str]]]:
    for start in range(0, len(items), batch_size):
        yield start, items[start:start + batch_size]


class IngestionProcessor:
    def __init__(self) -> None:
        self.collection_name = settings.QDRANT_COLLECTION
        self.provider = GeminiEmbeddingProvider()
        self.qdrant_client = QdrantClient(
            url=settings.QDRANT_CLUSTER_ENDPOINT,
            api_key=settings.QDRANT_API_KEY,
        )
        self._checked_vector_size: int | None = None

    def ingest_directory(self, root: str | Path, source_type: str) -> None:
        root = Path(root)

        if not root.exists():
            raise FileNotFoundError(f"Directory not found: {root}")
        if not root.is_dir():
            raise ValueError(f"Path is not a directory: {root}")

        failed_files: list[Path] = []

        with logfire.span(
            "Ingest Directory", root=str(root), source_type=source_type
        ):
            for path in root.rglob("*"):
                if not path.is_file():
                    continue

                try:
                    self.ingest_file(path, source_type=source_type)
                except Exception as exc:
                    import traceback

                    print(f"\nFAILED: {path}", flush=True)
                    traceback.print_exc()
                    failed_files.append(path)


        if failed_files:
            raise RuntimeError(
                f"Ingestion failed for {len(failed_files)} file(s): "
                + ", ".join(str(path) for path in failed_files)
            )

    def ingest_file(self, file_path: str | Path, source_type: str) :
        path = Path(file_path)
        filename = path.name

        with logfire.span(
            "Processing File", file=filename, source=source_type
        ):
            try:
                full_text = parse_file(path)

                if not full_text or not full_text.strip():
                    logfire.warning(f"No text extracted from {filename}; skipping.")
                    return

                chunks = chunk_text(full_text)

                if not chunks:
                    logfire.warning(f"No valid chunks for {filename}; skipping.")
                    return

                processed_data = {
                    "filename": filename,
                    "source_type": source_type,
                    "chunks": chunks,
                }
                local_path = save_processed_locally(
                    processed_data, source_type, filename
                )
                logfire.info(f"Saved processed data to {local_path}")

                self._index_chunks(
                    chunks=chunks,
                    filename=filename,
                    source_type=source_type,
                )
                logfire.info(f"Successfully indexed {filename}")
                
            except Exception as exc:
                logfire.error(f"Failed to process {filename}: {exc}")
                raise

    def _ensure_collection(self, vector_size: int) -> None:
        if self._checked_vector_size == vector_size:
            return

        if not self.qdrant_client.collection_exists(
            collection_name=self.collection_name
        ):
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            logfire.info(
                f"Created collection {self.collection_name} "
                f"with vector size {vector_size}"
            )

        collection = self.qdrant_client.get_collection(
            collection_name=self.collection_name
        )
        vectors_config = collection.config.params.vectors

        if not isinstance(vectors_config, models.VectorParams):
            raise ValueError(
                f"Collection {self.collection_name} uses named vectors, "
                "but this processor sends unnamed vectors."
            )

        if vectors_config.size != vector_size:
            raise ValueError(
                f"Collection {self.collection_name} has vector size "
                f"{vectors_config.size}; embedding model returned {vector_size}."
            )

        self._checked_vector_size = vector_size

    def _index_chunks(
        self, chunks: list[str], filename: str, source_type: str
    ) -> None:
        with logfire.span(
            "Vectorizing & Indexing",
            file=filename,
            total_chunks=len(chunks),
        ):
            for start_index, chunk_batch in _batched(
                chunks, UPSERT_BATCH_SIZE
            ):
                embeddings = self.provider.embed_documents(chunk_batch)

                if len(embeddings) != len(chunk_batch):
                    raise ValueError(
                        f"Expected {len(chunk_batch)} embeddings, "
                        f"received {len(embeddings)}."
                    )

                vector_size = len(embeddings[0])
                if vector_size == 0 or any(
                    len(vector) != vector_size for vector in embeddings
                ):
                    raise ValueError("Empty or inconsistent embedding vectors.")

                self._ensure_collection(vector_size)

                points = []
                for offset, (chunk, vector) in enumerate(
                    zip(chunk_batch, embeddings)
                ):
                    absolute_index = start_index + offset
                    point_id = str(
                        uuid.uuid5(
                            NAMESPACE_INGESTION,
                            f"{source_type}/{filename}/{absolute_index}",
                        )
                    )

                    points.append(
                        models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                "text": chunk,
                                "source": filename,
                                "source_type": source_type,
                                "chunk_index": absolute_index,
                            },
                        )
                    )

                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )

                logfire.info(
                    f"Indexed {filename}: chunks "
                    f"{start_index}..{start_index + len(points) - 1}"
                )
