from __future__ import annotations

from pathlib import Path
from typing import Iterable
import uuid

import logfire
from qdrant_client import models
from qdrant_client import QdrantClient

from app.config import settings
# from app.services.retrieval.qdrant_service import qdrant_client
from app.ingestion.chuncking.splitter import chunk_text
from app.services.retrieval.embedding import get_embedding_provider
from app.ingestion.persistence.local_disk import save_processed_locally
from app.ingestion.loaders.dispatcher import parse_file


NAMESPACE_INGESTION = uuid.UUID("12345678-1234-5678-1234-567812345678")
UPSERT_BATCH_SIZE = 5


def _batched(items: list[str], batch_size: int) -> Iterable[tuple[int, list[str]]]:
    for start in range(0, len(items), batch_size):
        yield start, items[start:start + batch_size]


class IngestionProcessor:
    def __init__(self) -> None:
        self.collection_name = settings.QDRANT_COLLECTION
        self.provider = get_embedding_provider()
        self.qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY
            )

    def ingest_directory(self, root: str | Path, source_type: str) -> None:
        root = Path(root)

        if not root.exists():
            raise FileNotFoundError(f"Directory not found: {root}")
        if not root.is_dir():
            raise ValueError(f"Path is not a directory: {root}")

        with logfire.span("Ingest Directory", root=str(root), source_type=source_type):
            for path in root.rglob("*"):
                if path.is_file():
                    self.ingest_file(path, source_type=source_type)

    def ingest_file(self, file_path: str | Path, source_type: str) -> None:
        path = Path(file_path)
        filename = path.name

        with logfire.span("Processing File", file=filename, source=source_type):
            try:
                print(f"\n=== START PROCESSING: {filename} ===", flush=True)

                full_text = parse_file(path)
                print(f"Extracted text length for {filename}: {len(full_text)}", flush=True)

                if not full_text or not full_text.strip():
                    logfire.warning(f"No text extracted from {filename} — skipping.")
                    return

                chunks = chunk_text(full_text)
                print(f"Chunks for {filename}: {len(chunks)}", flush=True)

                if not chunks:
                    logfire.warning(f"No valid chunks generated for {filename}.")
                    return

                processed_data = {
                    "filename": filename,
                    "source_type": source_type,
                    "chunks": chunks,
                }
                local_path = save_processed_locally(processed_data, source_type, filename)
                logfire.info(f"Saved processed data → {local_path}")

                self._index_chunks(
                    chunks=chunks,
                    filename=filename,
                    source_type=source_type,
                )
                print(f"✅ SUCCESS: {filename}")

            except ValueError as e:
                logfire.warning(f"Skipping file {filename}: {e}")
            except Exception as e:
                logfire.error(f"Failed to process {filename}: {e}")
                print(f"❌ FAILED: {filename} | Error: {e}", flush=True)
                return

    def _index_chunks(self, chunks: list[str], filename: str, source_type: str) -> None:
        with logfire.span("Vectorizing & Indexing", file=filename, total_chunks=len(chunks)):
            for start_index, chunk_batch in _batched(chunks, UPSERT_BATCH_SIZE):
                embeddings = self.provider.embed_documents(chunk_batch)

                points = []
                for offset, (chunk, vector) in enumerate(zip(chunk_batch, embeddings)):
                    absolute_index = start_index + offset
                    deterministic_id = str(
                        uuid.uuid5(NAMESPACE_INGESTION, f"{filename}_{absolute_index}")
                    )

                    points.append(
                        models.PointStruct(
                            id=deterministic_id,
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
                    f"Indexed batch for {filename}: "
                    f"chunks {start_index}..{start_index + len(points) - 1}"
                )
