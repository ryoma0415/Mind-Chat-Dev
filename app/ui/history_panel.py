from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
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
    # 🗑️ 削除を要求するためのシグナルを追加
    delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conversations: list[Conversation] = []

        self._mode_label = QLabel("", self)
        self._mode_label.setObjectName("HistoryModeLabel")
        self._mode_label.setWordWrap(True)
        self._mode_label.setStyleSheet("font-weight: 600; font-size: 14px;")

        self._list = QListWidget(self)
        # クリックイベント中に会話ロードを行うため、selectionChanged で拾う
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        self._new_button = QPushButton("新しく対話を始める", self)
        self._new_button.clicked.connect(self.new_conversation_requested.emit)

        self._favorite_button = QPushButton("★ お気に入り切替", self)
        self._favorite_button.clicked.connect(self._on_favorite_clicked)
        self._favorite_button.setEnabled(False)

        # 🗑️ 削除ボタンの追加
        self._delete_button = QPushButton("🗑️ 履歴を削除", self)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._delete_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self._mode_label)
        layout.addWidget(self._new_button)
        layout.addWidget(self._favorite_button)
        # 🗑️ 削除ボタンをレイアウトに追加
        layout.addWidget(self._delete_button)
        layout.addWidget(self._list, stretch=1)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        self.setLayout(layout)

    def set_mode_label(self, label: str) -> None:
        self._mode_label.setText(label)

    def set_conversations(self, conversations: Iterable[Conversation]) -> None:
        selected_id = self.current_conversation_id
        self._conversations = list(conversations)
        # リストを再構築する間は選択シグナルを止めて無限ループを防ぐ
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
        # 🗑️ ボタンの状態を更新
        self._update_button_states()

    def select_conversation(self, conversation_id: str) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.data(Qt.UserRole) == conversation_id:
                self._list.blockSignals(True)
                self._list.setCurrentItem(item)
                self._list.blockSignals(False)
                self.conversation_selected.emit(conversation_id)
                # 🗑️ ボタンの状態を更新
                self._update_button_states()
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
        # 一覧表示では最終更新日時を添えることで状況を把握しやすくする
        return f"{star} {conversation.title}  ({timestamp})"

    def _on_selection_changed(self) -> None:
        conversation_id = self.current_conversation_id
        # 🗑️ ボタンの状態を更新
        self._update_button_states()
        if conversation_id:
            self.conversation_selected.emit(conversation_id)

    def _on_favorite_clicked(self) -> None:
        conversation_id = self.current_conversation_id
        if conversation_id:
            self.favorite_toggle_requested.emit(conversation_id)

    # 🗑️ 削除ボタンのクリックハンドラ
    def _on_delete_clicked(self) -> None:
        conversation_id = self.current_conversation_id
        if conversation_id:
            self.delete_requested.emit(conversation_id)

    # 🗑️ ボタンの状態をまとめて更新するメソッド
    def _update_button_states(self) -> None:
        is_selected = self.current_conversation_id is not None
        self._favorite_button.setEnabled(is_selected)
        self._delete_button.setEnabled(is_selected)