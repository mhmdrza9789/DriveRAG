from pathlib import Path

import logfire

from app.config import settings, PROJECT_DATA
from app.ingestion.processor import IngestionProcessor
from qdrant_client import QdrantClient


def ingest_data(
    reset_collection: bool,
    collection_name: str,
    data_dir: str | Path,
) -> None:
    """
    در صورت فعال بودن reset_collection، collection را حذف می‌کند.
    سپس ابتدا true_data و بعد noisy_data را ingest می‌کند.
    """

    logfire.configure()

    data_dir = Path(data_dir).expanduser().resolve()
    true_dir = data_dir / "true_data"
    noisy_dir = data_dir / "noisy_data"

    if not collection_name.strip():
        raise ValueError("collection_name cannot be empty.")

    for directory in (true_dir, noisy_dir):
        if not directory.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")

    qdrant_client = QdrantClient(
        url=settings.QDRANT_CLUSTER_ENDPOINT,
        api_key=settings.QDRANT_API_KEY,
    )

    with logfire.span(
        "Ingest DATA into Qdrant",
        collection_name=collection_name,
        reset_collection=reset_collection,
        data_dir=str(data_dir),
    ):
        if reset_collection:
            with logfire.span(
                "Reset Qdrant collection",
                collection_name=collection_name,
            ):
                if qdrant_client.collection_exists(
                    collection_name=collection_name
                ):
                    qdrant_client.delete_collection(
                        collection_name=collection_name
                    )

                    logfire.info(
                        "Qdrant collection deleted",
                        collection_name=collection_name,
                    )
                else:
                    logfire.info(
                        "Qdrant collection does not exist; nothing to delete",
                        collection_name=collection_name,
                    )

        ingest = IngestionProcessor()

        for directory, source_type in (
            (true_dir, "true_data"),
            (noisy_dir, "noisy_data"),
        ):
            with logfire.span(
                "Ingest directory",
                directory=str(directory),
                source_type=source_type,
                collection_name=collection_name,
            ):
                ingest.ingest_directory(
                    directory,
                    source_type=source_type,
                )

        logfire.info(
            "DATA ingestion completed",
            collection_name=collection_name,
        )


if __name__ == "__main__":
    ingest_data(
        reset_collection = True,
        collection_name = settings.QDRANT_COLLECTION,
        data_dir = PROJECT_DATA,
    )
