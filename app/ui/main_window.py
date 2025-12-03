from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, ConversationMode
from ..history import FavoriteLimitError, HistoryError, HistoryManager
from ..llm_client import LocalLLM
from ..models import ChatMessage, Conversation
from ..resources import resource_path
from ..speech_recognizer import SpeechRecognizer
from .conversation_widget import ConversationWidget
from .history_panel import HistoryPanel
from .audio_recorder import AudioRecorder
from .workers import LLMWorker, SpeechWorker


MEDIA_EXTENSIONS = {
    "video": (".mp4", ".mov", ".mkv", ".avi", ".webm"),
    "image": (".png", ".jpg", ".jpeg", ".bmp", ".gif"),
}

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._config = config
        self._modes = {mode.key: mode for mode in config.modes}
        if not self._modes:
            raise ValueError("会話モードが設定されていません。")
        if config.default_mode_key in self._modes:
            self._active_mode_key = config.default_mode_key
        else:
            self._active_mode_key = next(iter(self._modes))

        self._history_managers: dict[str, HistoryManager] = {
            key: HistoryManager(config, history_file=mode.history_path(config.paths))
            for key, mode in self._modes.items()
        }
        # モードごとに独立した履歴／選択状態を持たせて UI 切替時の混乱を避ける
        self._current_conversation_ids: dict[str, str | None] = {key: None for key in self._modes}
        self._media_cache: dict[str, Path | None] = {}
        self._llm_client: LocalLLM | None = None
        self._llm_error: str | None = None

        try:
            self._llm_client = LocalLLM(config)
        except Exception as exc:  # pragma: no cover - runtime feedback
            # モデルが無い環境でも起動だけはできるようにエラーメッセージを保持する
            self._llm_error = str(exc)

        self._worker_thread: QThread | None = None
        self._worker: LLMWorker | None = None
        self._speech_thread: QThread | None = None
        self._speech_worker: SpeechWorker | None = None
        self._speech_recognizer = SpeechRecognizer(config)
        self._audio_recorder = AudioRecorder(self)
        self._is_llm_busy = False
        self._is_recording = False

        self.resize(1100, 700)

        self._history_panel = HistoryPanel(self)
        self._history_panel.set_mode_label(self._active_mode.display_name)
        self._conversation_widget = ConversationWidget(self)
        self._apply_assistant_label()
        self._conversation_widget.record_button_clicked.connect(self._toggle_recording)
        self._update_media_display()

        self._mode_selector = QComboBox(self)
        for mode in self._modes.values():
            self._mode_selector.addItem(mode.display_name, mode.key)
        self._sync_mode_selector()
        self._mode_selector.currentIndexChanged.connect(self._handle_mode_change)

        header_label = QLabel("会話モード:", self)
        header_layout = QHBoxLayout()
        header_layout.addWidget(header_label)
        header_layout.addWidget(self._mode_selector)
        header_layout.addStretch()

        splitter = QSplitter(self)
        splitter.addWidget(self._history_panel)
        splitter.addWidget(self._conversation_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 820])

        container = QWidget(self)
        container_layout = QVBoxLayout(container)
        container_layout.addLayout(header_layout)
        container_layout.addWidget(splitter, stretch=1)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.setCentralWidget(container)

        self._history_panel.new_conversation_requested.connect(self._handle_new_conversation)
        self._history_panel.conversation_selected.connect(self._load_conversation)
        self._history_panel.favorite_toggle_requested.connect(self._toggle_favorite)
        self._conversation_widget.message_submitted.connect(self._handle_user_message)
        self._audio_recorder.recording_started.connect(self._handle_recording_started)
        self._audio_recorder.recording_stopped.connect(self._handle_recording_stopped)
        self._audio_recorder.audio_ready.connect(self._handle_audio_ready)
        self._audio_recorder.error.connect(self._handle_recording_error)

        self._apply_mode_theme(self._active_mode)
        self._refresh_interaction_locks()
        self._bootstrap_conversation()
        if self._llm_error:
            self._show_warning("LLMの初期化に失敗しました", self._llm_error)

    # UI event handlers --------------------------------------------------
    def _bootstrap_conversation(self) -> None:
        self._ensure_active_mode_ready()
        conversation_id = self._get_active_conversation_id()
        self._refresh_history_panel(select_id=conversation_id)
        # 最初の起動では履歴先頭または新規を読み込んで画面を埋める
        if conversation_id:
            self._load_conversation(conversation_id)

    def _handle_new_conversation(self) -> None:
        conversation = self._active_history.create_conversation()
        self._set_active_conversation_id(conversation.conversation_id)
        self._refresh_history_panel(select_id=conversation.conversation_id)
        self._conversation_widget.display_conversation(conversation)

    def _load_conversation(self, conversation_id: str) -> None:
        try:
            conversation = self._active_history.get_conversation(conversation_id)
        except HistoryError as exc:
            self._show_warning("履歴の読み込みに失敗しました", str(exc))
            # 現在の UI に前モードの内容が残らないように空の会話でリセットする
            fallback = self._active_history.create_conversation()
            self._set_active_conversation_id(fallback.conversation_id)
            self._refresh_history_panel(select_id=fallback.conversation_id)
            self._conversation_widget.display_conversation(fallback)
            return
        self._set_active_conversation_id(conversation.conversation_id)
        # 読み取ったメッセージをそのまま transcript に反映
        self._conversation_widget.display_conversation(conversation)

    def _toggle_favorite(self, conversation_id: str) -> None:
        try:
            conversation = self._active_history.toggle_favorite(conversation_id)
        except FavoriteLimitError as exc:
            self._show_warning("お気に入り制限", str(exc))
            return
        except HistoryError as exc:
            self._show_warning("お気に入りの更新に失敗しました", str(exc))
            return
        self._refresh_history_panel(select_id=conversation.conversation_id)

    def _handle_user_message(self, text: str) -> None:
        conversation_id = self._get_active_conversation_id()
        if not conversation_id:
            self._handle_new_conversation()
            conversation_id = self._get_active_conversation_id()
        if not conversation_id:
            return

        message = ChatMessage(role="user", content=text)
        conversation = self._active_history.append_message(conversation_id, message)
        self._conversation_widget.append_message(message)
        self._refresh_history_panel(select_id=conversation.conversation_id)
        # LLM レスポンスが返るまで UI 操作をロックする
        self._set_busy(True, "AIが考え中です...")
        self._request_llm_response(conversation)

    def _toggle_recording(self) -> None:
        if self._is_recording:
            self._audio_recorder.stop()
            return
        if self._is_llm_busy:
            self._show_warning("録音できません", "AI応答中は録音を開始できません。")
            return

        availability_error = self._speech_recognizer.availability_error()
        if availability_error:
            self._show_warning("音声認識が利用できません", availability_error)
            return

        self._conversation_widget.set_status_text("マイクを初期化しています...")
        self._audio_recorder.start()

    # LLM coordination ---------------------------------------------------
    def _request_llm_response(self, conversation: Conversation) -> None:
        if not self._llm_client:
            self._set_busy(False)
            self._show_warning(
                "LLMが利用できません",
                self._llm_error or "必要なライブラリやモデルファイルを確認してください。",
            )
            return

        if self._worker_thread and self._worker_thread.isRunning():
            # すでに別レスポンスを計算中ならキューを増やさずに無視
            return

        self._worker = LLMWorker(
            self._llm_client,
            conversation.messages,
            self._active_mode.system_prompt,
        )
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
        conversation_id = self._get_active_conversation_id()
        if not conversation_id:
            self._set_busy(False)
            return
        try:
            assistant_message = ChatMessage(role="assistant", content=response)
            conversation = self._active_history.append_message(conversation_id, assistant_message)
            self._set_active_conversation_id(conversation.conversation_id)
            # リサイズ等で transcript が崩れても履歴から再描画して確実に反映する
            self._conversation_widget.display_conversation(conversation)
            self._refresh_history_panel(select_id=conversation.conversation_id)
        except Exception as exc:  # pragma: no cover - UI robustness
            logger.exception("Failed to render assistant response", exc_info=exc)
            self._show_warning(
                "表示に失敗しました",
                "応答の生成は完了しましたが、保存または画面の更新に失敗しました。会話を開き直してください。",
            )
        finally:
            self._set_busy(False)

    def _handle_llm_failure(self, error_message: str) -> None:
        try:
            conversation_id = self._get_active_conversation_id()
            if conversation_id:
                conversation = self._active_history.remove_trailing_user_message(conversation_id)
                self._conversation_widget.display_conversation(conversation)
                self._refresh_history_panel(select_id=conversation.conversation_id)
        finally:
            self._set_busy(False)
        # エラー内容はダイアログで通知し、巻き戻したことが視覚的にわかるようにする
        self._show_warning("応答生成に失敗しました", error_message)

    def _cleanup_worker(self) -> None:
        self._worker = None
        self._worker_thread = None

    # Speech input coordination -----------------------------------------
    def _handle_recording_started(self) -> None:
        self._is_recording = True
        self._conversation_widget.set_recording_state(True, "録音中...（最大2分／無音30秒で自動停止）")
        self._refresh_interaction_locks()

    def _handle_recording_stopped(self, reason: str) -> None:
        self._is_recording = False
        self._conversation_widget.set_recording_state(False)
        if reason:
            self._conversation_widget.set_status_text(reason)
        elif not self._is_llm_busy:
            self._conversation_widget.set_status_text("")
        self._refresh_interaction_locks()

    def _handle_recording_error(self, message: str) -> None:
        self._is_recording = False
        self._conversation_widget.set_recording_state(False)
        self._conversation_widget.set_status_text(message)
        self._refresh_interaction_locks()
        self._show_warning("録音エラー", message)

    def _handle_audio_ready(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        pcm_bytes, sample_rate = payload
        try:
            pcm_bytes = bytes(pcm_bytes)  # type: ignore[arg-type]
            sample_rate_int = int(sample_rate)
        except Exception:
            return

        self._conversation_widget.set_status_text("音声を解析しています...")
        self._start_speech_worker(pcm_bytes, sample_rate_int)

    def _start_speech_worker(self, pcm_bytes: bytes, sample_rate: int) -> None:
        if self._speech_thread and self._speech_thread.isRunning():
            return

        self._speech_worker = SpeechWorker(self._speech_recognizer, pcm_bytes, sample_rate)
        self._speech_thread = QThread(self)

        self._speech_worker.moveToThread(self._speech_thread)
        self._speech_thread.started.connect(self._speech_worker.run)
        self._speech_worker.recognized.connect(self._handle_recognition_success)
        self._speech_worker.failed.connect(self._handle_recognition_failure)
        self._speech_worker.recognized.connect(self._speech_thread.quit)
        self._speech_worker.failed.connect(self._speech_thread.quit)
        self._speech_worker.recognized.connect(self._cleanup_speech_worker)
        self._speech_worker.failed.connect(self._cleanup_speech_worker)
        self._speech_worker.recognized.connect(self._speech_worker.deleteLater)
        self._speech_worker.failed.connect(self._speech_worker.deleteLater)
        self._speech_thread.finished.connect(self._speech_thread.deleteLater)

        # 音声解析中は誤操作防止のため録音ボタンを無効化
        self._conversation_widget.set_record_button_enabled(False)
        self._speech_thread.start()

    def _handle_recognition_success(self, text: str) -> None:
        self._conversation_widget.append_text_to_input(text)
        self._conversation_widget.set_status_text("音声入力のテキストを挿入しました。編集して送信できます。")

    def _handle_recognition_failure(self, error_message: str) -> None:
        self._conversation_widget.set_status_text("音声認識に失敗しました。もう一度お試しください。")
        self._show_warning("音声認識エラー", error_message)

    def _cleanup_speech_worker(self) -> None:
        self._speech_worker = None
        self._speech_thread = None
        self._refresh_interaction_locks()
        # 録音が終了していて LLM も空きならステータスを消しておく
        if not self._is_llm_busy and not self._is_recording:
            self._conversation_widget.set_status_text("")

    # Helpers ------------------------------------------------------------
    def _refresh_history_panel(self, select_id: Optional[str] = None) -> None:
        conversations = self._active_history.list_conversations()
        current_before = self._history_panel.current_conversation_id
        self._history_panel.set_conversations(conversations)
        target_id = select_id or current_before or self._get_active_conversation_id()
        if target_id and self._history_panel.current_conversation_id != target_id:
            self._history_panel.select_conversation(target_id)
        if target_id:
            # UI の選択と内部状態を揃えておかないと LLM 応答の紐付けがズレる
            self._set_active_conversation_id(target_id)

    def _set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        self._is_llm_busy = is_busy
        self._conversation_widget.set_busy(is_busy, status_text)
        self._refresh_interaction_locks()

    def _handle_mode_change(self, index: int) -> None:
        mode_key = self._mode_selector.itemData(index)
        if not mode_key or mode_key == self._active_mode_key:
            return
        self._active_mode_key = mode_key
        self._history_panel.set_mode_label(self._active_mode.display_name)
        self._apply_assistant_label()
        self._update_media_display()
        self._apply_mode_theme(self._active_mode)
        self._ensure_active_mode_ready()
        conversation_id = self._get_active_conversation_id()
        # モード固有の履歴に切り替え、必要なら該当の会話をロード
        self._refresh_history_panel(select_id=conversation_id)
        if conversation_id:
            self._load_conversation(conversation_id)

    def _ensure_active_mode_ready(self) -> None:
        if self._get_active_conversation_id():
            return
        conversations = self._active_history.list_conversations()
        if conversations:
            self._set_active_conversation_id(conversations[0].conversation_id)
        else:
            # 会話履歴が無い場合は即座に空の会話を作って表示可能にする
            conversation = self._active_history.create_conversation()
            self._set_active_conversation_id(conversation.conversation_id)

    def _sync_mode_selector(self) -> None:
        for index in range(self._mode_selector.count()):
            if self._mode_selector.itemData(index) == self._active_mode_key:
                self._mode_selector.blockSignals(True)
                self._mode_selector.setCurrentIndex(index)
                self._mode_selector.blockSignals(False)
                # UI からの signal を出さずに選択状態だけ合わせておく
                break

    def _get_active_conversation_id(self) -> str | None:
        return self._current_conversation_ids[self._active_mode_key]

    def _set_active_conversation_id(self, conversation_id: str | None) -> None:
        self._current_conversation_ids[self._active_mode_key] = conversation_id

    @property
    def _active_mode(self) -> ConversationMode:
        return self._modes[self._active_mode_key]

    @property
    def _active_history(self) -> HistoryManager:
        return self._history_managers[self._active_mode_key]

    def _refresh_interaction_locks(self) -> None:
        locked = self._is_llm_busy or self._is_recording
        self._history_panel.setDisabled(locked)
        self._mode_selector.setDisabled(locked)
        self._conversation_widget.set_record_button_enabled(
            not self._is_llm_busy and self._speech_worker is None
        )

    def _apply_mode_theme(self, mode: ConversationMode) -> None:
        theme = mode.theme
        stylesheet = f"""
        QWidget {{
            background-color: {theme.base_background};
            color: {theme.text};
        }}
        /* QTextEdit, QPlainTextEdit, QListWidget に統一して角丸と視覚的差別化を適用 */
        QTextEdit, QPlainTextEdit, QListWidget {{
            background-color: {theme.panel_background};
            /* 1px の薄いボーダーでパネルの分離効果を出す */
            border: 1px solid #d6d6d6; 
            border-radius: 8px; /* 角丸の適用 */
            padding: 4px; /* テキストとボーダーの間にゆとりを持たせる */
        }}
        /* QListWidget の選択アイテムにアクセントカラーを適用 */
        QListWidget::item:selected {{
            background-color: {theme.accent};
            color: {theme.accent_text}; 
            border-radius: 6px; 
        }}
        QListWidget::item:selected:!active {{
            background-color: {theme.accent}; 
        }}
        QPushButton {{
            background-color: {theme.accent};
            color: {theme.accent_text};
            border-radius: 4px;
            padding: 6px 12px;
        }}
        QPushButton:disabled {{
            background-color: #b4b4b4;
            color: #f2f2f2;
        }}
        QPushButton:hover:!disabled {{
            background-color: {theme.accent_hover};
        }}
        QLabel#StatusLabel {{
            color: {theme.subtle_text};
        }}
        """
        self.setStyleSheet(stylesheet)
        self.setWindowTitle(mode.window_title)

    def _apply_assistant_label(self) -> None:
        label = self._active_mode.assistant_label or self._active_mode.display_name
        self._conversation_widget.set_assistant_label(label)

    def _update_media_display(self) -> None:
        mode = self._active_mode
        media_path = self._resolve_media_path(mode)
        # モード選択に応じて表示するメディアを差し替える
        self._conversation_widget.set_media_content(mode.media_type, media_path)

    def _resolve_media_path(self, mode: ConversationMode) -> Path | None:
        # ファイル探索は重いためモードごとに結果をキャッシュ
        if mode.key in self._media_cache:
            return self._media_cache[mode.key]

        if not mode.media_subdir:
            self._media_cache[mode.key] = None
            return None

        base_dir = resource_path("screen_display", mode.media_subdir)
        if not base_dir.exists():
            logger.warning("Media directory not found: %s", base_dir)
            self._media_cache[mode.key] = None
            return None

        allowed = tuple(ext.lower() for ext in MEDIA_EXTENSIONS.get(mode.media_type, ()))
        for candidate in sorted(base_dir.iterdir()):
            if not candidate.is_file():
                continue
            if allowed and candidate.suffix.lower() not in allowed:
                continue
            # 最初に見つかった許可済みファイルのパスをキャッシュ
            self._media_cache[mode.key] = candidate
            return candidate

        logger.warning("No media files found for mode %s in %s", mode.key, base_dir)
        self._media_cache[mode.key] = None
        return None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker_thread and self._worker_thread.isRunning():
            # アプリ終了前にバックグラウンドの推論スレッドを安全に停止
            self._worker_thread.quit()
            self._worker_thread.wait()
        if self._speech_thread and self._speech_thread.isRunning():
            self._speech_thread.quit()
            self._speech_thread.wait()
        if self._audio_recorder.is_recording:
            self._audio_recorder.stop()
        super().closeEvent(event)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
