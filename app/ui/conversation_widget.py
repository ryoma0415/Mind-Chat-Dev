from __future__ import annotations

import html
from typing import Iterable

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import ChatMessage, Conversation


class ConversationWidget(QWidget):
    message_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_conversation: Conversation | None = None

        self._welcome_label = QLabel(
            "こんにちは, 本日はどうされましたか？ 気楽に話していってくださいね。",
            self,
        )
        self._welcome_label.setWordWrap(True)

        self._transcript = QTextEdit(self)
        self._transcript.setReadOnly(True)
        self._transcript.setMinimumHeight(300)

        self._status_label = QLabel("", self)
        self._status_label.setStyleSheet("color: #666666;")

        self._input = QPlainTextEdit(self)
        self._input.setPlaceholderText("お気持ちや状況を入力してください...")
        self._input.setFixedHeight(120)

        self._send_button = QPushButton("送信", self)
        self._send_button.clicked.connect(self._handle_submit)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._send_button)
        input_row.setSpacing(8)

        layout = QVBoxLayout()
        layout.addWidget(self._welcome_label)
        layout.addWidget(self._transcript, stretch=1)
        layout.addWidget(self._status_label)
        layout.addLayout(input_row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        self.setLayout(layout)

    # Public API ---------------------------------------------------------
    def display_conversation(self, conversation: Conversation) -> None:
        self._current_conversation = conversation
        self._render_messages(conversation.messages)
        self._status_label.clear()

    def append_message(self, message: ChatMessage) -> None:
        self._transcript.moveCursor(QTextCursor.End)
        self._transcript.insertHtml(self._format_message(message))
        self._transcript.insertPlainText("\n")
        self._transcript.moveCursor(QTextCursor.End)

    def show_history(self, messages: Iterable[ChatMessage]) -> None:
        self._render_messages(messages)

    def set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        self._send_button.setDisabled(is_busy)
        if status_text:
            self._status_label.setText(status_text)
        elif not is_busy:
            self._status_label.clear()

    # Internal helpers ---------------------------------------------------
    def _handle_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.message_submitted.emit(text)

    def _render_messages(self, messages: Iterable[ChatMessage]) -> None:
        self._transcript.clear()
        for message in messages:
            self._transcript.insertHtml(self._format_message(message))
            self._transcript.insertPlainText("\n")
        self._transcript.moveCursor(QTextCursor.End)

    def _format_message(self, message: ChatMessage) -> str:
        role_label = "あなた" if message.role == "user" else "Mind-Chat"
        escaped = html.escape(message.content).replace("\n", "<br>")
        return f"<p><b>{role_label}</b><br>{escaped}</p>"
