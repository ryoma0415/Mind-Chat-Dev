# Mind-Chat

Mind-Chat は Gemma 2 2B Japanese IT (GGUF) をローカル実行し、完全オフラインで悩み相談や通常会話を楽しめるデスクトップアプリです。UI は PySide6 製で Windows / Linux を共通コードでサポートし、履歴やお気に入りもローカル JSON で永続化します。

## 主な特徴
- **完全ローカル推論**: `llama-cpp-python` で GGUF モデルを直接ロードし、ネットワーク接続不要で応答生成。
- **2 種類の会話モード**: Mind-Chat (カウンセリング) と 通常会話 を切り替え。モードごとに履歴・お気に入りを独立管理し、配色・ウィンドウタイトル・アシスタント名を自動切替。
- **メディア表示エリア**: モードに応じて `screen_display/` 内の動画または静止画をチャット画面上部に表示。Mind-Chat では動画をループ再生、通常会話では静止画をフィット表示。
- **履歴管理**: モードごとに最大 60 会話、お気に入り最大 50 件。超過時は非お気に入りを自動削除。履歴から再開・お気に入りトグル・再生成などの操作が可能。
- **PyInstaller 配布を想定**: ランチャースクリプトと `resource_path` ヘルパーを用意し、`screen_display/` や `model/` を含めた onedir 配布が容易。

## ディレクトリ構成
```
Mind-Chat/
├── app/
│   ├── __init__.py
│   ├── config.py             # パス、LLM、モード定義
│   ├── history.py            # 履歴とお気に入り管理ロジック
│   ├── llm_client.py         # llama.cpp ラッパー
│   ├── main.py               # アプリエントリーポイント
│   ├── models.py             # Conversation / ChatMessage モデル
│   ├── resources.py          # PyInstaller 対応のリソース解決
│   └── ui/
│       ├── conversation_widget.py
│       ├── history_panel.py
│       ├── main_window.py
│       ├── media_display.py  # 画像・動画表示ウィジェット
│       └── workers.py
├── data/                     # 履歴 JSON (history_mindchat.json 等)
├── model/                    # GGUF モデル配置ディレクトリ
├── screen_display/           # モード別の動画・画像リソース
├── mindchat_launcher.py      # PyInstaller 用ランチャー
├── requirements.txt
└── README.md
```

## 動作要件
- Python 3.10 以上
- `pip install -r requirements.txt` で導入するライブラリ
  - `llama-cpp-python>=0.2.84`
  - `PySide6>=6.7.0`
- **Linux のみ**: QtMultimedia が PulseAudio を利用するため `libpulse0` (および `libpulse-mainloop-glib0`) を apt 等で事前にインストールしてください。
- Gemma 2 2B Japanese IT (GGUF) のモデルファイル

## セットアップ手順
```bash
git clone <this-repo>
cd Mind-Chat
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## モデルファイルの準備
1. `model/` 配下に Gemma 2 2B Japanese IT の GGUF を配置します。デフォルトファイル名は `gemma-2-2b-it-japanese-it.gguf` です。
2. 別ファイル名や別ディレクトリを使う場合は環境変数 `MINDCHAT_MODEL_PATH` にフルパスを指定してください。

## メディアアセット
- `screen_display/Mind-Chat/` に動画 (`.mp4`/`.mov`/`.mkv` など) を置くと Mind-Chat モードでループ再生されます。複数ある場合はファイル名の昇順で最初の 1 つを選択。
- `screen_display/通常モード/` に画像 (`.png`/`.jpg`/`.gif` 等) を置くと通常会話モードで表示されます。
- PyInstaller で配布する場合は上記ディレクトリを `collect_data_files` 等で忘れずに同梱してください。

## アプリの実行
```bash
python -m app.main
```
- 起動直後は **通常会話モード** で開始します（メディアは静止画表示、アシスタント名は「Gemma2-2B-JPN-IT」）。
- 左ペインの履歴から会話を選択／お気に入り切替／新規作成が可能。右ペインで入力するとローカル LLM が応答します。
- モード切替ドロップダウンを操作すると、履歴・テーマカラー・メディア表示・アシスタント名が切り替わります。

## 会話管理仕様
- 履歴はモードごとに JSON (`data/history_mindchat.json`, `data/history_plain.json`) へ保存。
- 最大 60 会話まで保持し、超過時は「お気に入りではない最古の会話」から自動削除。
- お気に入りは各モード最大 50 件。上限を超える登録はエラーで拒否。
- 会話タイトルは最初のユーザーメッセージから自動生成されます。

## 設定と拡張ポイント
- `app/config.py` の `AppConfig` でスレッド数、GPU レイヤ数、温度、トークン長などを変更可能。
- `ConversationMode` でメディアフォルダ・アシスタント表示名・システムプロンプトなどをモードごとに指定できます。
- `app/resources.py` の `resource_path()` は PyInstaller の `_MEIPASS` に対応済み。独自リソースを追加する際もこのヘルパーを利用してください。

## PyInstaller での配布手順の例
```bash
pyinstaller --onedir --name MindChat \
  --add-data "screen_display:screen_display" \
  --add-data "model:model" \
  mindchat_launcher.py
```
- `--add-data` の区切りは Windows では `;`、Linux では `:` になる点に注意。
- 生成された `dist/MindChat/` フォルダごと配布すれば、ユーザーは `MindChat.exe` を実行するだけで利用できます。

## トラブルシューティング
- **`ImportError: libpulse.so.0`**: Linux で PulseAudio ライブラリが不足しています。`sudo apt install libpulse0 libpulse-mainloop-glib0` を実行してください。
- **モデルファイルが見つからないエラー**: `model/` に GGUF が存在するか、`MINDCHAT_MODEL_PATH` の値を再確認してください。
- **動画/画像が表示されない**: `screen_display/<モード名>/` に対応拡張子のファイルがあるか確認してください。存在しない場合はプレースホルダーが表示されます。

## 参考・今後の拡張
- テスト用のモック LLM、GPU 切替 UI、PyInstaller spec の追加などの TODO は `app/config.py` やコメントを参照して進めてください。
- LangChain 連携や音声 I/O などのアイデアを追加する場合は、`resource_path()` を活用してリソース管理を一本化すると保守が容易になります。

ローカルで安全に動作するカウンセリングアプリとして、Mind-Chat をぜひ活用してください。
