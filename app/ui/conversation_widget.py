from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import ChatMessage, Conversation
from .media_display import MediaDisplayWidget


class ConversationWidget(QWidget):
    message_submitted = Signal(str)
    record_button_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_conversation: Conversation | None = None
        self._assistant_label = "Mind-Chat"
        self._is_busy = False
        self._is_recording = False

        self._welcome_label = QLabel(
            "こんにちは, 本日はどうされましたか？ 気楽に話していってくださいね。",
            self,
        )
        self._welcome_label.setWordWrap(True)

        self._transcript = QTextEdit(self)
        self._transcript.setReadOnly(True)
        self._transcript.setMinimumHeight(300)

        self._media_widget = MediaDisplayWidget(self)
        self._splitter = QSplitter(Qt.Vertical, self)
        # 上段: 動画・画像 / 下段: 応答ログ を切り替えできるレイアウト
        self._splitter.addWidget(self._media_widget)
        self._splitter.addWidget(self._transcript)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([240, 360])

        self._status_label = QLabel("", self)
        self._status_label.setObjectName("StatusLabel")
        self._status_label.setStyleSheet("color: #666666;")

        self._input = QPlainTextEdit(self)
        self._input.setPlaceholderText("お気持ちや状況を入力してください...")
        self._input.setFixedHeight(120)

        self._record_button = QPushButton("録音開始", self)
        self._record_button.clicked.connect(self._handle_record_button)
        self._record_button.setFixedWidth(110)

        self._send_button = QPushButton("送信", self)
        self._send_button.clicked.connect(self._handle_submit)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._record_button)
        input_row.addWidget(self._send_button)
        input_row.setSpacing(8)

        layout = QVBoxLayout()
        layout.addWidget(self._welcome_label)
        layout.addWidget(self._splitter, stretch=1)
        layout.addWidget(self._status_label)
        layout.addLayout(input_row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        self.setLayout(layout)
        self._refresh_controls()

    # Public API ---------------------------------------------------------
    def display_conversation(self, conversation: Conversation) -> None:
        self._current_conversation = conversation
        self._render_messages(conversation.messages)
        self._status_label.clear()

    def append_message(self, message: ChatMessage) -> None:
        # 新しいメッセージを末尾に追記し、常に最新までスクロールしておく
        self._transcript.moveCursor(QTextCursor.End)
        self._transcript.insertHtml(self._format_message(message))
        self._transcript.insertPlainText("\n")
        self._transcript.moveCursor(QTextCursor.End)

    def show_history(self, messages: Iterable[ChatMessage]) -> None:
        self._render_messages(messages)

    def set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        self._is_busy = is_busy
        self._refresh_controls()
        if status_text:
            self._status_label.setText(status_text)
        elif not is_busy and not self._is_recording:
            self._status_label.clear()

    def set_assistant_label(self, label: str) -> None:
        normalized = (label or "Mind-Chat").strip() or "Mind-Chat"
        if normalized == self._assistant_label:
            return
        self._assistant_label = normalized
        # ラベルが変化したときは既存履歴も更新して統一感を保つ
        if self._current_conversation:
            self._render_messages(self._current_conversation.messages)

    def set_media_content(self, media_type: str, media_path: Path | None) -> None:
        if media_type == "video":
            self._media_widget.display_video(media_path)
        elif media_type == "image":
            self._media_widget.display_image(media_path)
        else:
            self._media_widget.clear()

    def set_recording_state(self, is_recording: bool, status_text: str | None = None) -> None:
        self._is_recording = is_recording
        self._record_button.setText("録音停止" if is_recording else "録音開始")
        self._refresh_controls()
        if status_text is not None:
            self._status_label.setText(status_text)
        elif not self._is_busy and not self._is_recording:
            self._status_label.clear()

    def set_record_button_enabled(self, enabled: bool) -> None:
        # 録音中は停止操作を受け付けるためボタンを無効化しない
        if self._is_recording:
            self._record_button.setEnabled(True)
            return
        self._record_button.setEnabled(enabled)

    def set_status_text(self, text: str) -> None:
        self._status_label.setText(text)

    def append_text_to_input(self, text: str) -> None:
        if not text:
            return
        current = self._input.toPlainText()
        separator = "\n" if current and not current.endswith("\n") else ""
        new_text = f"{current}{separator}{text}"
        self._input.setPlainText(new_text)
        self._input.moveCursor(QTextCursor.End)
        self._input.setFocus()

    # Internal helpers ---------------------------------------------------
    def _handle_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        # テキスト入力を外部に通知することで MainWindow が LLM 呼び出しを開始する
        self.message_submitted.emit(text)

    def _handle_record_button(self) -> None:
        self.record_button_clicked.emit()

    def _render_messages(self, messages: Iterable[ChatMessage]) -> None:
        self._transcript.clear()
        for message in messages:
            self._transcript.insertHtml(self._format_message(message))
            self._transcript.insertPlainText("\n")
        self._transcript.moveCursor(QTextCursor.End)

    def _format_message(self, message: ChatMessage) -> str:
        role_label = "あなた" if message.role == "user" else self._assistant_label
        escaped = html.escape(message.content).replace("\n", "<br>")
        return f"<p><b>{role_label}</b><br>{escaped}</p>"

    def _refresh_controls(self) -> None:
        disable_send = self._is_busy or self._is_recording
        self._send_button.setDisabled(disable_send)
        self._input.setReadOnly(self._is_busy)
