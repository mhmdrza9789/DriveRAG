from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# Find the project root from the location of this file:
# DriveRAG/app/ingestion/loaders/drive_sync.py -> DriveRAG/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_PATH = PROJECT_ROOT / ".env"
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"

load_dotenv(dotenv_path=ENV_PATH, override=True)


ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID")
LOCAL_ROOT = PROJECT_ROOT / os.getenv("DRIVE_LOCAL_ROOT", "DATA")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Native Google files must be exported to a downloadable format.
GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": (
        ".docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "application/vnd.google-apps.spreadsheet": (
        ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "application/vnd.google-apps.presentation": (
        ".pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "application/vnd.google-apps.drawing": (
        ".pdf",
        "application/pdf",
    ),
}


def get_drive_service():
    """Authenticate and create a read-only Google Drive client."""
    if not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"Google OAuth credentials not found: {CREDENTIALS_PATH}"
        )

    credentials = None

    if TOKEN_PATH.is_file():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_PATH),
            SCOPES,
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_PATH),
            SCOPES,
        )
        credentials = flow.run_local_server(port=0)

    # Save the token, including a refreshed token, for the next run.
    TOKEN_PATH.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    return build("drive", "v3", credentials=credentials)


def safe_name(name: str) -> str:
    """Make a Drive filename safe to use as a local filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip().strip(".")

    return name or "unnamed_file"


def list_children(service, folder_id: str) -> list[dict]:
    """List every non-trashed file and folder inside a Drive folder."""
    children = []
    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )

        children.extend(response.get("files", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return children


def download_file(
    service,
    file_id: str,
    mime_type: str,
    target_path: Path,
) -> None:
    """Download a regular file or export a native Google file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if mime_type in GOOGLE_EXPORTS:
        _, export_mime_type = GOOGLE_EXPORTS[mime_type]

        request = service.files().export_media(
            fileId=file_id,
            mimeType=export_mime_type,
        )
    else:
        request = service.files().get_media(fileId=file_id)

    # Download to a temporary file first, so an interrupted download
    # does not leave a partial file with the final filename.
    temporary_path = target_path.with_name(target_path.name + ".part")

    try:
        with temporary_path.open("wb") as output_file:
            downloader = MediaIoBaseDownload(
                output_file,
                request,
                chunksize=1024 * 1024,
            )

            completed = False

            while not completed:
                _, completed = downloader.next_chunk()

        temporary_path.replace(target_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def sync_folder(
    service,
    drive_folder_id: str,
    local_folder: Path,
) -> None:
    """Recursively copy a Drive folder into a local folder."""
    local_folder.mkdir(parents=True, exist_ok=True)

    for item in list_children(service, drive_folder_id):
        item_id = item["id"]
        item_name = safe_name(item["name"])
        mime_type = item["mimeType"]

        if mime_type == FOLDER_MIME_TYPE:
            subfolder = local_folder / item_name
            print(f"[DIR ] {subfolder}")

            sync_folder(
                service=service,
                drive_folder_id=item_id,
                local_folder=subfolder,
            )
            continue

        if mime_type in GOOGLE_EXPORTS:
            extension, _ = GOOGLE_EXPORTS[mime_type]

            if not item_name.lower().endswith(extension):
                item_name += extension

        target_path = local_folder / item_name
        print(f"[FILE] {target_path}")

        download_file(
            service=service,
            file_id=item_id,
            mime_type=mime_type,
            target_path=target_path,
        )


def main() -> None:
    if not ROOT_FOLDER_ID:
        raise RuntimeError(
            "GOOGLE_DRIVE_ROOT_FOLDER_ID is missing from .env"
        )

    service = get_drive_service()

    print(f"Drive folder ID: {ROOT_FOLDER_ID}")
    print(f"Local destination: {LOCAL_ROOT}")

    sync_folder(
        service=service,
        drive_folder_id=ROOT_FOLDER_ID,
        local_folder=LOCAL_ROOT,
    )

    print("Download completed.")


if __name__ == "__main__":
    main()
