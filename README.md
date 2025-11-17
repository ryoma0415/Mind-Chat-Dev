# Mind-Chat

ローカルで動作する悩み相談カウンセラーアプリです。Gemma 2 2B Japanese IT (GGUF) を llama.cpp 互換ランタイムで扱い、完全ローカルで対話履歴とお気に入りを管理します。UI は PySide6 を用いたデスクトップアプリで、Linux/Windows いずれのプラットフォームでも同じコードで動作する構成になっています。

## 主な機能
- 起動直後に「こんにちは, 本日はどうされましたか？ 気楽に話していってくださいね。」と表示し、ユーザー入力を受付
- llama-cpp-python を用いたローカル LLM (Gemma 2 2B Japanese IT, GGUF) での返答生成
- JSON ベースの完全ローカル履歴管理（最大 60 件／お気に入りは最大 50 件、溢れた場合は非お気に入りから自動削除）
- 履歴一覧・お気に入りトグル・再開・新規開始ボタンを備えたデスクトップ UI
- 履歴／モデルディレクトリの固定パス化と PyInstaller 想定のシンプルな構成

## ディレクトリ構成
```
Mind-Chat/
├── mindchat_launcher.py   # PyInstaller 用のランチャー
├── app/
│   ├── __init__.py
│   ├── config.py          # パス／LLM設定
│   ├── history.py         # JSON 永続化と制約ロジック
│   ├── llm_client.py      # llama.cpp ラッパー
│   ├── main.py            # アプリエントリーポイント
│   ├── models.py          # データモデル
│   └── ui/
│       ├── __init__.py
│       ├── conversation_widget.py
│       ├── history_panel.py
│       ├── main_window.py
│       └── workers.py
├── data/                  # 履歴 (conversations.json) が保存される
├── model/                 # Gemma GGUF を配置する
├── requirements.txt
└── README.md
```

## セットアップ
1. Python 3.10+ を用意します。
2. 依存ライブラリをインストールします。
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. `model/` ディレクトリに Gemma 2 2B Japanese IT の GGUF ファイルを配置します。  
   既定ファイル名は `gemma-2-2b-it-japanese-it.gguf` です。別名を使う場合は環境変数 `MINDCHAT_MODEL_PATH` でフルパスを指定してください。  
   取得手順の詳細は `docs/model_setup.md` を参照してください。

## 実行方法
```bash
python -m app.main
```
起動すると履歴ペインと対話ペインが表示されます。右側で入力・送信するとローカル LLM が応答し、左側で履歴の再開やお気に入り指定が可能です。

## 履歴管理仕様
- 履歴は `data/history.json` に JSON 形式で保存され、完全ローカルに保持されます。
- 全体で 60 会話まで保持し、上限超過時は「お気に入りではない最古の会話」から順に削除されます。
- お気に入りは最大 50 件。上限到達時はエラーダイアログで通知され、新規お気に入り登録は拒否されます。

## モデル／ビルドに関する注意
- llama-cpp-python は CPU/GPU 構成を自動検出し、`AppConfig` でスレッド数や GPU レイヤ数を調整できます。
- PyInstaller 等でバンドルする際は `model/` ディレクトリを同梱し、`python -m app.main` と同じエントリポイントを指定してください。
- ネットワークアクセスは一切不要で、UI からも外部通信は行っていません。

### Windows向けアプリ配布
- `pyinstaller --onedir` を使って `dist/MindChat` フォルダを作成し、そのフォルダ全体を配布します。ユーザーはフォルダを解凍し `MindChat.exe` をダブルクリックするだけで起動できます。
- 詳しい手順や注意点は `docs/windows_packaging.md` を参照してください。

## 次のステップ例
1. テスト用モック LLM を用意して CI でも UI 以外を検証できるようにする。
2. OpenCL/CUDA など GPU 最適化オプションを `AppConfig` から切り替えられるようにする。
3. PyInstaller 用の spec ファイルや自動ビルドスクリプトを追加し、Windows 向け配布を容易にする。
4. LangChain 連携・キャラクター UI・音声 I/O などの将来的な拡張については `docs/future_expansion.md` に検討内容をまとめています。
