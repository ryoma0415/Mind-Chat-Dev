from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Centralized paths used across the application."""

    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = field(init=False)
    history_file: Path = field(init=False)
    model_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", self.root / "data")
        object.__setattr__(self, "history_file", self.data_dir / "history.json")
        object.__setattr__(self, "model_dir", self.root / "model")

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self.history_file.write_text("[]", encoding="utf-8")

    def resolve_model_path(self, default_filename: str) -> Path:
        override = os.getenv("MINDCHAT_MODEL_PATH")
        if override:
            return Path(override).expanduser().resolve()
        return (self.model_dir / default_filename).resolve()


@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration shared across the Mind-Chat app."""

    paths: AppPaths = field(default_factory=AppPaths)
    model_filename: str = "gemma-2-2b-it-japanese-it.gguf"
    system_prompt: str = (
        "あなたは丁寧で共感力のある悩み相談カウンセラーです。"
        "相手の気持ちを尊重し、安心して話してもらえるように、"
        "短すぎず長すぎない自然な日本語で、具体的な気づきや次の一歩を提案してください。"
        "アドバイスが難しい場合は、相手の気持ちを受け止める言葉を最優先にしてください。"
    )

    max_conversations: int = 60
    max_favorites: int = 50

    max_context_tokens: int = 4096
    max_response_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    gpu_layers: int = 0
    threads: int | None = None

    @property
    def model_path(self) -> Path:
        return self.paths.resolve_model_path(self.model_filename)
