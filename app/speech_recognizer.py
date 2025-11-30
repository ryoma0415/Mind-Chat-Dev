from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .config import AppConfig

try:
    import vosk  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    vosk = None


class SpeechRecognitionError(Exception):
    """Raised when speech recognition cannot proceed."""


class SpeechRecognizer:
    """
    Thin wrapper around an offline speech recognition engine (Vosk).

    The recognizer is lazily initialized to avoid blocking the UI at startup.
    """

    def __init__(self, config: AppConfig):
        model_override = os.getenv("MINDCHAT_SPEECH_MODEL_PATH")
        default_model_dir = config.paths.model_dir / "vosk-model-small-ja-0.22"
        self._model_path = Path(model_override).expanduser().resolve() if model_override else default_model_dir
        self._model: object | None = None
        self._lock = threading.Lock()

    def availability_error(self) -> str | None:
        """
        Return None if the recognizer is ready to use, otherwise a human friendly error message.
        """

        if vosk is None:
            return "音声認識ライブラリ(vosk)が見つかりません。`pip install vosk` を実行してください。"
        if not self._model_path.exists():
            return f"音声認識モデルが見つかりません: {self._model_path}"
        return None

    def recognize_pcm(self, pcm_bytes: bytes, sample_rate: int) -> str:
        """
        Convert raw PCM audio into text using Vosk.
        """

        if not pcm_bytes:
            raise SpeechRecognitionError("音声が検出できませんでした。録音を確認してください。")

        model = self._ensure_model()
        recognizer = vosk.KaldiRecognizer(model, sample_rate)  # type: ignore[arg-type]
        recognizer.AcceptWaveform(pcm_bytes)
        result = json.loads(recognizer.FinalResult())
        text = result.get("text", "").strip()
        if not text:
            raise SpeechRecognitionError("音声をテキストに変換できませんでした。もう一度お試しください。")
        return text

    # Internal helpers ---------------------------------------------------
    def _ensure_model(self):
        error = self.availability_error()
        if error:
            raise SpeechRecognitionError(error)

        with self._lock:
            if self._model is not None:
                return self._model
            # Lazy load the Vosk model (can take a few seconds)
            self._model = vosk.Model(str(self._model_path))  # type: ignore[call-arg]
            return self._model
