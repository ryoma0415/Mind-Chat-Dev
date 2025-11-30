from __future__ import annotations

import sys
import time
from array import array

from PySide6.QtCore import QIODevice, QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


class AudioRecorder(QObject):
    """
    Lightweight audio recorder using QtMultimedia.

    Captures raw PCM audio into memory and emits the byte stream when stopped.
    """

    audio_ready = Signal(object)  # emits tuple[bytes, int] = (pcm, sample_rate)
    recording_started = Signal()
    recording_stopped = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        parent=None,
        max_duration_ms: int = 120_000,
        silence_timeout_ms: int = 30_000,
        silence_threshold: int = 500,
    ) -> None:
        super().__init__(parent)
        self._audio_source: QAudioSource | None = None
        self._io_device: QIODevice | None = None
        self._buffer = bytearray()
        self._recording = False
        self._sample_rate = 16_000
        self._channels = 1
        self._bytes_per_sample = 2
        self._silence_threshold = silence_threshold
        self._silence_timeout_ms = silence_timeout_ms
        self._silence_detection_enabled = silence_timeout_ms > 0
        self._last_voice_time = time.monotonic()
        self._max_duration_ms = max_duration_ms

        self._max_timer = QTimer(self)
        self._max_timer.setSingleShot(True)
        self._max_timer.setInterval(max_duration_ms)
        self._max_timer.timeout.connect(self._handle_max_duration)

        self._silence_timer = QTimer(self)
        self._silence_timer.setInterval(1_000)
        self._silence_timer.timeout.connect(self._check_silence)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> bool:
        if self._recording:
            return False

        device = QMediaDevices.defaultAudioInput()
        if not device or device.isNull():
            self.error.emit("録音可能なマイクが見つかりません。")
            return False

        preferred = device.preferredFormat()
        target_format = QAudioFormat(preferred)
        target_format.setChannelCount(1)
        target_format.setSampleRate(16_000)
        target_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self._silence_detection_enabled = self._silence_timeout_ms > 0
        if not device.isFormatSupported(target_format):
            # Fallback to the preferred format if 16kHz/Int16 is not available
            target_format = preferred
            self._silence_detection_enabled = False

        self._sample_rate = target_format.sampleRate()
        self._channels = target_format.channelCount() or 1
        frame_bytes = target_format.bytesForFrames(1)
        self._bytes_per_sample = max(1, int(frame_bytes / max(1, self._channels)))

        self._buffer.clear()
        self._last_voice_time = time.monotonic()

        self._audio_source = QAudioSource(device, target_format, self)
        self._io_device = self._audio_source.start()
        if not self._io_device:
            self.error.emit("マイクの初期化に失敗しました。")
            self._cleanup()
            return False

        self._io_device.readyRead.connect(self._handle_ready_read)
        self._recording = True
        self._max_timer.start(self._max_duration_ms)
        if self._silence_detection_enabled:
            self._silence_timer.start()
        self.recording_started.emit()
        return True

    def stop(self, auto_reason: str | None = None) -> None:
        if not self._recording:
            return

        self._recording = False
        self._max_timer.stop()
        self._silence_timer.stop()

        if self._audio_source:
            self._audio_source.stop()

        if self._io_device:
            try:
                self._io_device.readyRead.disconnect(self._handle_ready_read)
            except (TypeError, RuntimeError):
                pass

        data = bytes(self._buffer)
        self._cleanup()

        reason = auto_reason or ""
        self.recording_stopped.emit(reason)
        if not data:
            self.error.emit("録音データが空でした。マイクの接続を確認してください。")
            return
        self.audio_ready.emit((data, self._sample_rate))

    # Internal helpers ---------------------------------------------------
    def _handle_ready_read(self) -> None:
        if not self._io_device or not self._recording:
            return

        while self._io_device.bytesAvailable() > 0:
            chunk = self._io_device.readAll()
            if not chunk:
                break
            raw = bytes(chunk)
            self._buffer.extend(raw)
            self._update_voice_activity(raw)

    def _handle_max_duration(self) -> None:
        self.stop("最大録音時間に達したため自動停止しました。")

    def _check_silence(self) -> None:
        if not self._silence_detection_enabled or not self._recording:
            return
        elapsed_ms = int((time.monotonic() - self._last_voice_time) * 1000)
        if elapsed_ms >= self._silence_timeout_ms:
            self.stop("無音状態が続いたため自動停止しました。")

    def _update_voice_activity(self, chunk: bytes) -> None:
        if not self._silence_detection_enabled:
            return
        if self._bytes_per_sample != 2:
            # Silence detection only supports 16-bit PCM
            self._last_voice_time = time.monotonic()
            return

        samples = array("h")
        samples.frombytes(chunk)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return
        threshold = self._silence_threshold
        if any(abs(sample) > threshold for sample in samples):
            self._last_voice_time = time.monotonic()

    def _cleanup(self) -> None:
        self._buffer.clear()
        self._audio_source = None
        self._io_device = None
