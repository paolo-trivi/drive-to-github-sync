# Drive to GitHub Sync

A Python pipeline that watches a Google Drive folder and automatically syncs changed files to a GitHub repository.

## How it works

```
Google Drive folder  →  (polling)  →  local staging  →  GitHub repo
```

1. **DriveWatcher** polls a Drive folder for changes using the Drive API v3 change-tracking endpoint.
2. Changed files are downloaded to a local staging directory.
3. **GitHubSync** uploads each file to the configured GitHub repository via the GitHub API.

## Setup

### 1. Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Drive API**.
3. Create an **OAuth 2.0 Client ID** (Desktop app) and download `credentials.json`.

### 2. GitHub token

Create a [personal access token](https://github.com/settings/tokens) with **repo** scope.

### 3. Configuration

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your folder ID, token, and repo name
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

## Usage

**Continuous polling** (default):
```bash
python main.py --config config.yaml
```

**One-shot sync** (sync all current files then exit):
```bash
python main.py --config config.yaml --once
```

## Project structure

```
.
├── main.py                  # Entry point
├── config.yaml.example      # Example configuration
├── requirements.txt
└── src/
    ├── drive_watcher.py     # Google Drive API polling & download
    ├── github_sync.py       # GitHub file upload via PyGithub
    └── pipeline.py          # Orchestrates watcher → staging → GitHub
```
