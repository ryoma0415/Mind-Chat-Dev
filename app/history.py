from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import AppConfig
from .models import ChatMessage, Conversation


class HistoryError(Exception):
    """Base class for history related issues."""


class FavoriteLimitError(HistoryError):
    """Raised when the favorite limit would be exceeded."""


class ConversationNotFoundError(HistoryError):
    """Raised when a conversation id cannot be located."""


class HistoryManager:
    """
    Manages persistence and business rules around conversation history.
    """

    def __init__(self, config: AppConfig, history_file: Path | None = None):
        self._config = config
        default_path = config.default_mode.history_path(config.paths)
        self._path: Path = history_file or default_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 異常終了しても壊れないよう初期状態の JSON を用意する
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")
        self._conversations: list[Conversation] = []
        self._load_from_disk()

    # Public API ---------------------------------------------------------
    def list_conversations(self) -> List[Conversation]:
        return list(self._conversations)

    def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self._find_conversation(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def upsert_conversation(self, conversation: Conversation) -> None:
        existing = self._find_conversation(conversation.conversation_id)
        if existing:
            index = self._conversations.index(existing)
            self._conversations[index] = conversation
        else:
            self._conversations.insert(0, conversation)
        self._persist()

    def create_conversation(self) -> Conversation:
        conversation = Conversation()
        self._conversations.insert(0, conversation)
        # 件数上限を超えないよう新規作成直後に整理する
        self._enforce_limits()
        self._persist()
        return conversation

    def append_message(self, conversation_id: str, message: ChatMessage) -> Conversation:
        conversation = self.get_conversation(conversation_id)
        conversation.append_message(message)
        self._promote_to_top(conversation)
        self._persist()
        return conversation

    def remove_trailing_user_message(self, conversation_id: str) -> Conversation:
        conversation = self.get_conversation(conversation_id)
        if conversation.messages and conversation.messages[-1].role == "user":
            # LLM 応答に失敗した場合は最後のユーザ発話を巻き戻す
            conversation.messages.pop()
            conversation.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            self._persist()
        return conversation

    def toggle_favorite(self, conversation_id: str) -> Conversation:
        conversation = self.get_conversation(conversation_id)
        target_state = not conversation.is_favorite
        if target_state and self.favorite_count >= self._config.max_favorites:
            raise FavoriteLimitError(
                f"お気に入りは最大{self._config.max_favorites}件までです。"
            )
        conversation.is_favorite = target_state
        conversation.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._promote_to_top(conversation)
        self._enforce_limits()
        self._persist()
        return conversation

    def delete_conversation(self, conversation_id: str) -> None:
        conversation = self.get_conversation(conversation_id)
        self._conversations.remove(conversation)
        self._persist()

    @property
    def favorite_count(self) -> int:
        return sum(1 for c in self._conversations if c.is_favorite)

    # Internal helpers ---------------------------------------------------
    def _load_from_disk(self) -> None:
        if not self._path.exists():
            self._conversations = []
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # ファイル破損時は安全に空の状態で立ち上げる
            payload = []

        conversations = [Conversation.from_dict(item) for item in payload]
        conversations.sort(key=self._timestamp_key, reverse=True)
        self._conversations = conversations

    def _persist(self) -> None:
        payload = [conversation.to_dict() for conversation in self._conversations]
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_conversation(self, conversation_id: str) -> Optional[Conversation]:
        for conversation in self._conversations:
            if conversation.conversation_id == conversation_id:
                return conversation
        return None

    def _promote_to_top(self, conversation: Conversation) -> None:
        if self._conversations and self._conversations[0] is conversation:
            return
        try:
            self._conversations.remove(conversation)
        except ValueError:
            pass
        # アクティブな会話をリストの先頭へ押し上げる
        self._conversations.insert(0, conversation)

    def _enforce_limits(self) -> None:
        while len(self._conversations) > self._config.max_conversations:
            oldest = self._oldest_non_favorite()
            if not oldest:
                break
            self._conversations.remove(oldest)

    def _oldest_non_favorite(self) -> Optional[Conversation]:
        candidates = [c for c in self._conversations if not c.is_favorite]
        if not candidates:
            return None
        return min(candidates, key=self._timestamp_key)

    @staticmethod
    def _timestamp_key(conversation: Conversation) -> datetime:
        return HistoryManager._parse_iso(conversation.updated_at)

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.fromtimestamp(0, tz=timezone.utc)
