"""GitHub repository sync module using PyGithub."""

import logging
from pathlib import Path
from typing import Optional

from github import Github, GithubException, InputGitAuthor

logger = logging.getLogger(__name__)


class GitHubSync:
    """Syncs local files to a GitHub repository."""

    def __init__(self, config: dict):
        self.token = config["token"]
        self.repo_name = config["repository"]
        self.branch = config.get("branch", "main")
        self.author_name = config.get("commit_author_name", "Drive Sync Bot")
        self.author_email = config.get("commit_author_email", "sync-bot@noreply.github.com")
        self._gh = Github(self.token)
        self._repo = None

    def connect(self) -> None:
        """Connect to the GitHub repository."""
        try:
            self._repo = self._gh.get_repo(self.repo_name)
            logger.info(f"Connected to GitHub repo: {self.repo_name}")
        except GithubException as e:
            raise ConnectionError(f"Failed to connect to repo '{self.repo_name}': {e}")

    def _get_file_sha(self, repo_path: str) -> Optional[str]:
        """Get the SHA of an existing file in the repo, or None if it doesn't exist."""
        try:
            contents = self._repo.get_contents(repo_path, ref=self.branch)
            return contents.sha
        except GithubException:
            return None

    def upload_file(self, local_path: Path, repo_path: str, commit_message: str) -> bool:
        """Upload or update a file in the GitHub repository.

        Returns True if the file was created or updated.
        """
        content = local_path.read_bytes()
        author = InputGitAuthor(self.author_name, self.author_email)
        sha = self._get_file_sha(repo_path)

        try:
            if sha:
                self._repo.update_file(
                    path=repo_path,
                    message=commit_message,
                    content=content,
                    sha=sha,
                    branch=self.branch,
                    author=author,
                )
                logger.info(f"Updated: {repo_path}")
            else:
                self._repo.create_file(
                    path=repo_path,
                    message=commit_message,
                    content=content,
                    branch=self.branch,
                    author=author,
                )
                logger.info(f"Created: {repo_path}")
            return True
        except GithubException as e:
            logger.error(f"Failed to upload {repo_path}: {e}")
            return False

    def sync_files(self, local_files: list[tuple[Path, str]]) -> int:
        """Sync a list of (local_path, repo_path) tuples.

        Returns the count of successfully synced files.
        """
        synced = 0
        for local_path, repo_path in local_files:
            message = f"sync: update {local_path.name} from Google Drive"
            if self.upload_file(local_path, repo_path, message):
                synced += 1
        return synced
