from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)

from ..config import AppConfig
from ..history import FavoriteLimitError, HistoryError, HistoryManager
from ..llm_client import LocalLLM
from ..models import ChatMessage, Conversation
from .conversation_widget import ConversationWidget
from .history_panel import HistoryPanel
from .workers import LLMWorker


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._config = config
        self._history = HistoryManager(config)
        self._llm_client: LocalLLM | None = None
        self._llm_error: str | None = None

        try:
            self._llm_client = LocalLLM(config)
        except Exception as exc:  # pragma: no cover - runtime feedback
            self._llm_error = str(exc)

        self._current_conversation_id: str | None = None
        self._worker_thread: QThread | None = None
        self._worker: LLMWorker | None = None

        self.setWindowTitle("Mind-Chat - ローカル悩み相談")
        self.resize(1100, 700)

        self._history_panel = HistoryPanel(self)
        self._conversation_widget = ConversationWidget(self)

        splitter = QSplitter(self)
        splitter.addWidget(self._history_panel)
        splitter.addWidget(self._conversation_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 820])

        self.setCentralWidget(splitter)

        self._history_panel.new_conversation_requested.connect(self._handle_new_conversation)
        self._history_panel.conversation_selected.connect(self._load_conversation)
        self._history_panel.favorite_toggle_requested.connect(self._toggle_favorite)
        self._conversation_widget.message_submitted.connect(self._handle_user_message)

        self._bootstrap_conversation()
        if self._llm_error:
            self._show_warning("LLMの初期化に失敗しました", self._llm_error)

    # UI event handlers --------------------------------------------------
    def _bootstrap_conversation(self) -> None:
        conversations = self._history.list_conversations()
        if conversations:
            self._current_conversation_id = conversations[0].conversation_id
        else:
            conversation = self._history.create_conversation()
            conversations = [conversation]
            self._current_conversation_id = conversation.conversation_id

        self._history_panel.set_conversations(conversations)
        if self._current_conversation_id:
            self._load_conversation(self._current_conversation_id)

    def _handle_new_conversation(self) -> None:
        conversation = self._history.create_conversation()
        self._current_conversation_id = conversation.conversation_id
        self._refresh_history_panel(select_id=conversation.conversation_id)

    def _load_conversation(self, conversation_id: str) -> None:
        try:
            conversation = self._history.get_conversation(conversation_id)
        except HistoryError as exc:
            self._show_warning("履歴の読み込みに失敗しました", str(exc))
            return
        self._current_conversation_id = conversation.conversation_id
        self._conversation_widget.display_conversation(conversation)

    def _toggle_favorite(self, conversation_id: str) -> None:
        try:
            conversation = self._history.toggle_favorite(conversation_id)
        except FavoriteLimitError as exc:
            self._show_warning("お気に入り制限", str(exc))
            return
        except HistoryError as exc:
            self._show_warning("お気に入りの更新に失敗しました", str(exc))
            return
        self._refresh_history_panel(select_id=conversation.conversation_id)

    def _handle_user_message(self, text: str) -> None:
        if not self._current_conversation_id:
            self._handle_new_conversation()
        if not self._current_conversation_id:
            return

        message = ChatMessage(role="user", content=text)
        conversation = self._history.append_message(self._current_conversation_id, message)
        self._conversation_widget.append_message(message)
        self._refresh_history_panel(select_id=conversation.conversation_id)
        self._conversation_widget.set_busy(True, "AIが考え中です...")
        self._request_llm_response(conversation)

    # LLM coordination ---------------------------------------------------
    def _request_llm_response(self, conversation: Conversation) -> None:
        if not self._llm_client:
            self._conversation_widget.set_busy(False)
            self._show_warning(
                "LLMが利用できません",
                self._llm_error or "必要なライブラリやモデルファイルを確認してください。",
            )
            return

        if self._worker_thread and self._worker_thread.isRunning():
            return

        self._worker = LLMWorker(self._llm_client, conversation.messages)
        self._worker_thread = QThread(self)

        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_llm_success)
        self._worker.failed.connect(self._handle_llm_failure)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.failed.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.failed.connect(self._cleanup_worker)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self._worker_thread.start()

    def _handle_llm_success(self, response: str) -> None:
        if not self._current_conversation_id:
            self._conversation_widget.set_busy(False)
            return
        assistant_message = ChatMessage(role="assistant", content=response)
        conversation = self._history.append_message(self._current_conversation_id, assistant_message)
        self._conversation_widget.append_message(assistant_message)
        self._conversation_widget.set_busy(False)
        self._refresh_history_panel(select_id=conversation.conversation_id)

    def _handle_llm_failure(self, error_message: str) -> None:
        self._conversation_widget.set_busy(False)
        if self._current_conversation_id:
            conversation = self._history.remove_trailing_user_message(self._current_conversation_id)
            self._conversation_widget.display_conversation(conversation)
            self._refresh_history_panel(select_id=conversation.conversation_id)
        self._show_warning("応答生成に失敗しました", error_message)

    def _cleanup_worker(self) -> None:
        self._worker = None
        self._worker_thread = None

    # Helpers ------------------------------------------------------------
    def _refresh_history_panel(self, select_id: Optional[str] = None) -> None:
        conversations = self._history.list_conversations()
        current_before = self._history_panel.current_conversation_id
        self._history_panel.set_conversations(conversations)
        target_id = select_id or current_before
        if target_id and self._history_panel.current_conversation_id != target_id:
            self._history_panel.select_conversation(target_id)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait()
        super().closeEvent(event)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
