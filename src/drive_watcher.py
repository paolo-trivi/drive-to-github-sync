"""Google Drive folder watcher using the Drive API v3."""

import io
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class DriveWatcher:
    """Watches a Google Drive folder and downloads changed files."""

    def __init__(self, config: dict):
        self.credentials_file = config["credentials_file"]
        self.token_file = config["token_file"]
        self.folder_id = config["folder_id"]
        self.poll_interval = config.get("poll_interval", 60)
        self._service = None
        self._page_token: Optional[str] = None

    def authenticate(self) -> None:
        """Authenticate with Google Drive API."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_file, "w") as f:
                f.write(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        logger.info("Authenticated with Google Drive API")

    def _get_start_page_token(self) -> str:
        """Get the current start page token for change tracking."""
        response = self._service.changes().getStartPageToken().execute()
        return response["startPageToken"]

    def list_folder_files(self) -> List[Dict]:
        """List all files in the watched folder recursively."""
        files = []
        page_token = None

        while True:
            query = f"'{self.folder_id}' in parents and trashed = false"
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents)",
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files

    def get_changes(self) -> List[Dict]:
        """Get list of changed files since last poll."""
        if self._page_token is None:
            self._page_token = self._get_start_page_token()
            logger.info(f"Initialized change tracking at page token: {self._page_token}")
            return []

        changes = []
        page_token = self._page_token

        while page_token:
            response = (
                self._service.changes()
                .list(
                    pageToken=page_token,
                    spaces="drive",
                    fields="nextPageToken, newStartPageToken, changes(fileId, file(id, name, mimeType, modifiedTime, parents, trashed))",
                )
                .execute()
            )

            for change in response.get("changes", []):
                file_meta = change.get("file", {})
                if not file_meta.get("trashed", False):
                    if self._is_in_watched_folder(file_meta):
                        changes.append(file_meta)

            if "newStartPageToken" in response:
                self._page_token = response["newStartPageToken"]
            page_token = response.get("nextPageToken")

        return changes

    def _is_in_watched_folder(self, file_meta: Dict) -> bool:
        """Check if a file belongs to the watched folder."""
        parents = file_meta.get("parents", [])
        return self.folder_id in parents

    def download_file(self, file_meta: Dict, dest_dir: Path) -> Optional[Path]:
        """Download a Drive file to the local staging directory."""
        mime_type = file_meta.get("mimeType", "")
        file_id = file_meta["id"]
        file_name = file_meta["name"]

        # Handle Google Workspace documents by exporting them
        export_map = {
            "application/vnd.google-apps.document": ("text/plain", ".txt"),
            "application/vnd.google-apps.spreadsheet": (
                "text/csv",
                ".csv",
            ),
            "application/vnd.google-apps.presentation": ("text/plain", ".txt"),
        }

        dest_dir.mkdir(parents=True, exist_ok=True)

        if mime_type in export_map:
            export_mime, ext = export_map[mime_type]
            if not file_name.endswith(ext):
                file_name += ext
            request = self._service.files().export_media(
                fileId=file_id, mimeType=export_mime
            )
        elif mime_type.startswith("application/vnd.google-apps"):
            logger.warning(f"Skipping unsupported Google Workspace type: {mime_type}")
            return None
        else:
            request = self._service.files().get_media(fileId=file_id)

        dest_path = dest_dir / file_name
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        dest_path.write_bytes(buffer.getvalue())
        logger.info(f"Downloaded: {file_name} → {dest_path}")
        return dest_path

    def watch(self, callback) -> None:
        """Start polling loop. Calls callback(changed_files) on each change."""
        logger.info(
            f"Watching Drive folder {self.folder_id} every {self.poll_interval}s"
        )
        # Initialize page token
        self._page_token = self._get_start_page_token()

        while True:
            try:
                changes = self.get_changes()
                if changes:
                    logger.info(f"Detected {len(changes)} changed file(s)")
                    callback(changes)
            except Exception as e:
                logger.error(f"Error polling Drive changes: {e}")
            time.sleep(self.poll_interval)
