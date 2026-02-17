"""Main pipeline orchestrator: Drive → local staging → GitHub."""

import logging
import shutil
from pathlib import Path
from typing import Dict, List

from .drive_watcher import DriveWatcher
from .github_sync import GitHubSync

logger = logging.getLogger(__name__)


class SyncPipeline:
    """Orchestrates the Drive-to-GitHub synchronization pipeline."""

    def __init__(self, config: dict):
        self.staging_dir = Path(config["sync"]["staging_dir"])
        self.target_path = config["sync"].get("target_path", "synced").strip("/")
        self.preserve_structure = config["sync"].get("preserve_structure", True)
        self.include_ext = set(config["sync"].get("include_extensions", []))
        self.exclude_ext = set(config["sync"].get("exclude_extensions", []))

        self.watcher = DriveWatcher(config["google_drive"])
        self.syncer = GitHubSync(config["github"])

    def setup(self) -> None:
        """Authenticate and connect to all services."""
        self.watcher.authenticate()
        self.syncer.connect()
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Pipeline setup complete")

    def _should_sync(self, file_name: str) -> bool:
        """Check whether a file should be synced based on extension filters."""
        suffix = Path(file_name).suffix.lower()
        if self.exclude_ext and suffix in self.exclude_ext:
            return False
        if self.include_ext and suffix not in self.include_ext:
            return False
        return True

    def _build_repo_path(self, file_name: str) -> str:
        """Build the target path within the GitHub repo."""
        if self.target_path:
            return f"{self.target_path}/{file_name}"
        return file_name

    def _process_changes(self, changed_files: List[Dict]) -> None:
        """Download changed Drive files and push them to GitHub."""
        to_sync: list[tuple[Path, str]] = []

        for file_meta in changed_files:
            file_name = file_meta.get("name", "")
            if not self._should_sync(file_name):
                logger.debug(f"Skipping excluded file: {file_name}")
                continue

            local_path = self.watcher.download_file(file_meta, self.staging_dir)
            if local_path is None:
                continue

            repo_path = self._build_repo_path(local_path.name)
            to_sync.append((local_path, repo_path))

        if to_sync:
            synced = self.syncer.sync_files(to_sync)
            logger.info(f"Synced {synced}/{len(to_sync)} file(s) to GitHub")
        else:
            logger.info("No eligible files to sync")

        self._cleanup_staging()

    def _cleanup_staging(self) -> None:
        """Remove all files from the local staging directory."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
            self.staging_dir.mkdir(parents=True, exist_ok=True)

    def run_once(self) -> None:
        """Perform a single sync of all files currently in the Drive folder."""
        logger.info("Running one-shot sync of Drive folder")
        all_files = self.watcher.list_folder_files()
        self._process_changes(all_files)

    def run(self) -> None:
        """Start the continuous polling loop."""
        logger.info("Starting Drive→GitHub sync pipeline")
        self.watcher.watch(self._process_changes)
