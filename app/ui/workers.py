from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QObject, Signal, Slot

from ..llm_client import LocalLLM
from ..models import ChatMessage


class LLMWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, client: LocalLLM, messages: Iterable[ChatMessage]) -> None:
        super().__init__()
        self._client = client
        self._messages = list(messages)

    @Slot()
    def run(self) -> None:
        try:
            response = self._client.generate_reply(self._messages)
        except Exception as exc:  # pragma: no cover - runtime safety
            self.failed.emit(str(exc))
            return
        self.finished.emit(response)
