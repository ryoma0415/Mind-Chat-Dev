from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class AppPaths:
    """Centralized paths used across the application."""

    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = field(init=False)
    model_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        # アプリ初期化時に data / model ディレクトリを確実に作っておく
        object.__setattr__(self, "data_dir", self.root / "data")
        object.__setattr__(self, "model_dir", self.root / "model")

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def ensure_history_file(self, filename: str) -> Path:
        # 履歴ファイルが存在しなければ空配列を書き込んで初期化
        path = (self.data_dir / filename).resolve()
        if not path.exists():
            path.write_text("[]", encoding="utf-8")
        return path

    def resolve_model_path(self, default_filename: str) -> Path:
        # 環境変数でパスを上書きできるようにしつつ、デフォルトは model ディレクトリ配下を見る
        override = os.getenv("MINDCHAT_MODEL_PATH")
        if override:
            return Path(override).expanduser().resolve()
        return (self.model_dir / default_filename).resolve()


@dataclass(frozen=True)
class ModeTheme:
    """Represents a simple color palette per conversation mode."""

    base_background: str
    panel_background: str
    accent: str
    accent_hover: str
    accent_text: str
    text: str = "#1a1a1a"
    subtle_text: str = "#666666"


@dataclass(frozen=True)
class ConversationMode:
    key: str
    display_name: str
    history_filename: str
    window_title: str
    theme: ModeTheme
    system_prompt: str | None = None
    media_subdir: str | None = None
    media_type: Literal["video", "image", "none"] = "none"
    assistant_label: str | None = None

    def history_path(self, paths: AppPaths) -> Path:
        return paths.ensure_history_file(self.history_filename)


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
    default_mode_key: str = "plain_chat"
    modes: tuple[ConversationMode, ...] = field(init=False)

    @property
    def model_path(self) -> Path:
        return self.paths.resolve_model_path(self.model_filename)

    def __post_init__(self) -> None:
        # dataclass の初期化完了後にモード一覧を確定させる
        object.__setattr__(self, "modes", self._build_modes())

    def _build_modes(self) -> tuple[ConversationMode, ...]:
        # UI テーマやプロンプト設定をまとめたモード情報をここで定義する
        mind_theme = ModeTheme(
            base_background="#f1f7f3",
            panel_background="#ffffff",
            accent="#2f8f63",
            accent_hover="#267650",
            accent_text="#ffffff",
        )
        plain_theme = ModeTheme(
            base_background="#eef4fb",
            panel_background="#ffffff",
            accent="#256edc",
            accent_hover="#1d58b0",
            accent_text="#ffffff",
        )
        return (
            ConversationMode(
                key="mind_chat",
                display_name="Mind-Chat",
                history_filename="history_mindchat.json",
                window_title="Mind-Chat - カウンセリングモード",
                theme=mind_theme,
                system_prompt=self.system_prompt,
                media_subdir="Mind-Chat",
                media_type="video",
                assistant_label="Mind-Chat",
            ),
            ConversationMode(
                key="plain_chat",
                display_name="通常会話",
                history_filename="history_plain.json",
                window_title="Mind-Chat - 通常会話モード",
                theme=plain_theme,
                system_prompt=None,
                media_subdir="通常モード",
                media_type="image",
                assistant_label="Gemma2-2B-JPN-IT",
            ),
        )

    def get_mode(self, key: str) -> ConversationMode:
        for mode in self.modes:
            if mode.key == key:
                return mode
        raise KeyError(f"Unknown mode: {key}")

    @property
    def default_mode(self) -> ConversationMode:
        return self.get_mode(self.default_mode_key)
