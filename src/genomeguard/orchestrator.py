"""Backward-compatible re-exports — prefer ``genomeguard.core``."""

from genomeguard.core import (
    WATCHER_DB_MISSING_MSG,
    configure_logging,
    process_single_change,
    run_daemon,
)

__all__ = [
    "WATCHER_DB_MISSING_MSG",
    "configure_logging",
    "process_single_change",
    "run_daemon",
]
