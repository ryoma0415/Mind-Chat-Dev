from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import QLabel, QStackedLayout, QSizePolicy, QWidget


logger = logging.getLogger(__name__)


class MediaDisplayWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None
        self._current_pixmap: QPixmap | None = None
        self._video_sink: QVideoSink | None = None
        self._current_video_image: QImage | None = None

        self._stack = QStackedLayout(self)

        self._placeholder = QLabel("メディアが読み込まれていません", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setObjectName("MediaPlaceholderLabel")

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._video_label = QLabel(self)
        self._video_label.setAlignment(Qt.AlignCenter)
        self._video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._image_label)
        self._stack.addWidget(self._video_label)
        self._stack.setCurrentWidget(self._placeholder)

        self.setMinimumHeight(200)

    def display_image(self, path: Path | None) -> None:
        self._stop_video()
        self._current_pixmap = None
        if not path or not path.exists():
            if path:
                logger.warning("Image not found: %s", path)
            self._image_label.clear()
            self._stack.setCurrentWidget(self._placeholder)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            logger.warning("Failed to load image: %s", path)
            self._stack.setCurrentWidget(self._placeholder)
            return

        self._current_pixmap = pixmap
        # ラベルサイズにフィットするようにスケールを適用
        self._apply_pixmap()
        self._stack.setCurrentWidget(self._image_label)

    def display_video(self, path: Path | None) -> None:
        self._current_pixmap = None
        if not path or not path.exists():
            if path:
                logger.warning("Video not found: %s", path)
            self._stop_video()
            self._stack.setCurrentWidget(self._placeholder)
            return

        player = self._ensure_player()
        self._current_video_image = None
        self._video_label.clear()
        player.setVideoSink(self._video_sink)
        # PySide6 の QMediaPlayer には URL を渡す必要がある
        player.setSource(QUrl.fromLocalFile(str(path)))
        player.play()
        self._stack.setCurrentWidget(self._video_label)

    def clear(self) -> None:
        self._stop_video()
        self._current_pixmap = None
        self._image_label.clear()
        self._stack.setCurrentWidget(self._placeholder)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_pixmap()
        self._apply_video_frame()

    def _apply_pixmap(self) -> None:
        if not self._current_pixmap:
            return
        scaled = self._current_pixmap.scaled(
            self._image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    def _apply_video_frame(self) -> None:
        if not self._current_video_image:
            return
        pixmap = QPixmap.fromImage(self._current_video_image)
        scaled = pixmap.scaled(
            self._video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._video_label.setPixmap(scaled)

    def _ensure_player(self) -> QMediaPlayer:
        if self._player is not None:
            return self._player

        self._player = QMediaPlayer(self)
        loops_value = getattr(QMediaPlayer, "Infinite", None)
        if loops_value is None and hasattr(QMediaPlayer, "Loops"):
            loops_value = getattr(QMediaPlayer.Loops, "Infinite", None)
        if loops_value is not None:
            self._player.setLoops(loops_value)
        self._video_sink = QVideoSink(self)
        self._video_sink.videoFrameChanged.connect(self._handle_video_frame)
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.0)
        # カウンセリング中は映像のみ再生したいので音声はミュート
        self._player.setAudioOutput(self._audio_output)
        return self._player

    def _stop_video(self) -> None:
        if self._player:
            self._player.stop()
            self._player.setVideoSink(None)
        self._current_video_image = None
        self._video_label.clear()

    def _handle_video_frame(self, frame: QVideoFrame) -> None:
        image = frame.toImage()
        if image.isNull():
            return
        self._current_video_image = image
        self._apply_video_frame()
