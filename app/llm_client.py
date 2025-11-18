from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Iterable, List

from .config import AppConfig
from .models import ChatMessage

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover - handled at runtime
    Llama = None


class LocalLLM:
    """
    Thin wrapper around llama.cpp that exposes a chat-friendly interface.
    """

    def __init__(self, config: AppConfig):
        if Llama is None:  # pragma: no cover - import guard
            raise RuntimeError(
                "llama-cpp-python が見つかりません。`pip install -r requirements.txt` を実行してください。"
            )

        self._config = config
        self._model_path = config.model_path

        self._llama: Llama | None = None
        # llama.cpp の推論はスレッド非安全なため排他制御を入れておく
        self._lock = threading.Lock()

    def generate_reply(self, history: Iterable[ChatMessage], system_prompt: str | None) -> str:
        llama = self._ensure_model()
        chat_messages = self._build_prompt(history, system_prompt)
        with self._lock:
            completion = llama.create_chat_completion(
                messages=chat_messages,
                max_tokens=self._config.max_response_tokens,
                temperature=self._config.temperature,
                top_p=self._config.top_p,
            )
        content = completion["choices"][0]["message"]["content"]
        return content.strip()

    # Internal helpers ---------------------------------------------------
    def _ensure_model(self) -> Llama:
        if self._llama is not None:
            return self._llama

        with self._lock:
            if self._llama is not None:
                return self._llama

            if not self._model_path.exists():
                raise FileNotFoundError(
                    f"モデルファイルが見つかりません: {self._model_path}. "
                    "model フォルダに Gemma 2 2B Japanese IT の GGUF ファイルを置いてください。"
                )

            # スレッド数は環境に応じて自動調整しつつ llama.cpp を初期化
            threads = self._config.threads or max(1, os.cpu_count() or 1)
            self._llama = Llama(
                model_path=str(self._model_path),
                n_ctx=self._config.max_context_tokens,
                n_batch=512,
                n_threads=threads,
                n_gpu_layers=self._config.gpu_layers,
                verbose=False,
            )
        return self._llama

    def _build_prompt(self, history: Iterable[ChatMessage], system_prompt: str | None) -> List[dict]:
        """
        Gemma 2 2B Japanese IT の chat template は system ロールをサポートしないため、
        最初の user メッセージにシステムプロンプトを結合して渡す。
        システムプロンプトを利用しないモードでは history だけをそのまま渡す。
        """
        messages = self._normalize_messages(list(history))
        chat_messages: List[dict] = []

        if system_prompt:
            if not messages:
                chat_messages.append({"role": "user", "content": system_prompt})
                return chat_messages

            first = messages[0]
            start_index = 0
            if first.role == "user":
                combined = f"{system_prompt}\n\n{first.content}".strip()
                chat_messages.append({"role": "user", "content": combined})
                start_index = 1
            else:
                chat_messages.append({"role": "user", "content": system_prompt})

            for message in messages[start_index:]:
                chat_messages.append(
                    {
                        "role": message.role,
                        "content": message.content,
                    }
                )
            return chat_messages

        if not messages:
            return chat_messages

        for message in messages:
            chat_messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )
        return chat_messages

    def _normalize_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        if not messages:
            return []

        normalized: List[ChatMessage] = []
        for message in messages:
            clone = ChatMessage(role=message.role, content=message.content, created_at=message.created_at)
            if not normalized:
                normalized.append(clone)
                continue
            last = normalized[-1]
            if last.role == clone.role:
                # 同じロールが連続した場合は 1 つに畳み込んでコンテキスト長を節約
                last.content = f"{last.content}\n\n{clone.content}"
            else:
                normalized.append(clone)
        return normalized
