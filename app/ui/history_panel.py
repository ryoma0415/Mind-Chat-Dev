from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Conversation


class HistoryPanel(QWidget):
    conversation_selected = Signal(str)
    new_conversation_requested = Signal()
    favorite_toggle_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conversations: list[Conversation] = []

        self._list = QListWidget(self)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        self._new_button = QPushButton("新しく対話を始める", self)
        self._new_button.clicked.connect(self.new_conversation_requested.emit)

        self._favorite_button = QPushButton("★ お気に入り切替", self)
        self._favorite_button.clicked.connect(self._on_favorite_clicked)
        self._favorite_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self._new_button)
        layout.addWidget(self._favorite_button)
        layout.addWidget(self._list, stretch=1)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        self.setLayout(layout)

    def set_conversations(self, conversations: Iterable[Conversation]) -> None:
        selected_id = self.current_conversation_id
        self._conversations = list(conversations)
        self._list.blockSignals(True)
        self._list.clear()
        for conversation in self._conversations:
            item = QListWidgetItem(self._format_title(conversation))
            item.setData(Qt.UserRole, conversation.conversation_id)
            self._list.addItem(item)
            if conversation.conversation_id == selected_id:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        if not self._list.currentItem() and self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._update_favorite_button_state()

    def select_conversation(self, conversation_id: str) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.data(Qt.UserRole) == conversation_id:
                self._list.blockSignals(True)
                self._list.setCurrentItem(item)
                self._list.blockSignals(False)
                self.conversation_selected.emit(conversation_id)
                self._update_favorite_button_state()
                return

    @property
    def current_conversation_id(self) -> str | None:
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _format_title(self, conversation: Conversation) -> str:
        from datetime import datetime

        star = "★" if conversation.is_favorite else "☆"
        try:
            dt = datetime.fromisoformat(conversation.updated_at)
            timestamp = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            timestamp = conversation.updated_at
        return f"{star} {conversation.title}  ({timestamp})"

    def _on_selection_changed(self) -> None:
        conversation_id = self.current_conversation_id
        self._update_favorite_button_state()
        if conversation_id:
            self.conversation_selected.emit(conversation_id)

    def _on_favorite_clicked(self) -> None:
        conversation_id = self.current_conversation_id
        if conversation_id:
            self.favorite_toggle_requested.emit(conversation_id)

    def _update_favorite_button_state(self) -> None:
        self._favorite_button.setEnabled(self.current_conversation_id is not None)
