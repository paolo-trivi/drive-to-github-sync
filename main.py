#!/usr/bin/env python3
"""Entry point for the Drive-to-GitHub sync pipeline."""

import argparse
import logging
import sys
from pathlib import Path

import yaml

from src.pipeline import SyncPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync files from Google Drive to a GitHub repository."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single sync then exit (instead of continuous polling)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.config.exists():
        logger.error(
            f"Config file not found: {args.config}. "
            "Copy config.yaml.example to config.yaml and fill in your values."
        )
        sys.exit(1)

    config = load_config(args.config)
    pipeline = SyncPipeline(config)

    try:
        pipeline.setup()
        if args.once:
            pipeline.run_once()
        else:
            pipeline.run()
    except KeyboardInterrupt:
        logger.info("Sync pipeline stopped by user")
    except Exception as e:
        logger.exception(f"Pipeline error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
