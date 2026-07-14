from __future__ import annotations

import logging
from typing import List

from engine.models import LogEntry


class ImportLogger:
    """In-memory logger plus stdlib logging bridge for UI and diagnostics."""

    def __init__(self, name: str = "importer") -> None:
        self._logger = logging.getLogger(name)
        self._entries: List[LogEntry] = []

    def info(self, message: str) -> None:
        self._logger.info(message)
        self._entries.append(LogEntry(level="INFO", message=message))

    def warning(self, message: str) -> None:
        self._logger.warning(message)
        self._entries.append(LogEntry(level="WARNING", message=message))

    def error(self, message: str) -> None:
        self._logger.error(message)
        self._entries.append(LogEntry(level="ERROR", message=message))

    @property
    def entries(self) -> list[LogEntry]:
        return list(self._entries)
