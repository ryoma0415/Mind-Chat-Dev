from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QObject, Signal, Slot

from ..llm_client import LocalLLM
from ..models import ChatMessage


class LLMWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, client: LocalLLM, messages: Iterable[ChatMessage], system_prompt: str | None) -> None:
        super().__init__()
        self._client = client
        self._messages = list(messages)
        self._system_prompt = system_prompt

    @Slot()
    def run(self) -> None:
        try:
            # GUI スレッドを塞がないよう別スレッドで推論を実行
            response = self._client.generate_reply(self._messages, self._system_prompt)
        except Exception as exc:  # pragma: no cover - runtime safety
            self.failed.emit(str(exc))
            return
        self.finished.emit(response)


class SpeechWorker(QObject):
    recognized = Signal(str)
    failed = Signal(str)

    def __init__(self, recognizer, pcm_bytes: bytes, sample_rate: int) -> None:
        super().__init__()
        self._recognizer = recognizer
        self._pcm_bytes = pcm_bytes
        self._sample_rate = sample_rate

    @Slot()
    def run(self) -> None:
        try:
            text = self._recognizer.recognize_pcm(self._pcm_bytes, self._sample_rate)
        except Exception as exc:  # pragma: no cover - runtime safety
            self.failed.emit(str(exc))
            return
        self.recognized.emit(text)
