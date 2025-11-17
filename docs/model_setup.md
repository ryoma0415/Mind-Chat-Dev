# Gemma 2 2B Japanese IT (GGUF) 配置手順

Mind-Chat では llama.cpp 互換の GGUF モデルをローカルディスクから読み込みます。以下の手順で Gemma 2 2B Japanese IT の GGUF ファイルを取得し、`model/` フォルダに配置してください。

## 1. 前提条件
- Hugging Face など、配布元でライセンスに同意済みであること。
- Python 3.10 以上と `pip` が使える環境。
- `huggingface_hub` CLI を利用する場合はインターネット接続（モデル取得時のみ）。

## 2. モデル入手先を確認
1. Hugging Face で「Gemma 2 2B Japanese IT GGUF」などのキーワードで検索し、目的のモデル（例: `ORG/gemma-2-2b-japanese-it-gguf`）のページへ移動します。
2. モデルページ右側で利用規約とライセンスを確認し、必要に応じて「Access request」を承認します。
3. ダウンロード可能なファイル一覧から、使用したい精度（例: `Q4_K_M`, `Q5_K_S` 等）の `.gguf` ファイルを特定します。

> **注**: 公式配布元が更新される可能性があります。常に最新の案内に従い、利用規約を守ってください。

## 3. Hugging Face CLI でのダウンロード（推奨）
1. Hugging Face CLI をインストールし、ログインします。
   ```bash
   source .venv/bin/activate        # venv 使用時（任意）
   pip install --upgrade huggingface_hub
   huggingface-cli login            # アクセストークンを入力
   ```
2. Mind-Chat プロジェクトのルートで以下を実行し、`model/` に保存します。
   ```bash
   huggingface-cli download ORG/MODEL_NAME \
     --filename models/gemma-2-2b-japanese-it-q4_k_m.gguf \
     --local-dir ./model \
     --local-dir-use-symlinks False
   ```
   - `ORG/MODEL_NAME` と `--filename` の値は実際のリポジトリ／ファイル名に置き換えてください。
   - `--local-dir-use-symlinks False` を付けると物理コピーになります（PyInstaller などで同梱しやすくなります）。
3. ダウンロード後、ファイルを既定名 `gemma-2-2b-it-japanese-it.gguf` にリネームします。
   ```bash
   mv model/<取得したファイル名>.gguf model/gemma-2-2b-it-japanese-it.gguf
   ```

## 4. ブラウザ経由でのダウンロード（Windows 向け）
1. ブラウザで Hugging Face のモデルページを開き、ログインします。
2. `.gguf` ファイルをクリックしてダウンロードします（数百 MB〜数 GB あるため時間がかかります）。
3. ダウンロードしたファイルを Mind-Chat プロジェクトの `model/` フォルダにコピーし、名前を `gemma-2-2b-it-japanese-it.gguf` に変更します。

## 5. 環境変数で別名ファイルを指定する場合
- 既定名を変えたくない場合や複数精度を切り替えたい場合は、環境変数 `MINDCHAT_MODEL_PATH` にフルパスを設定してください。
  ```bash
  export MINDCHAT_MODEL_PATH="/home/ryoma/VSCode-Projects/Mind-Chat/model/gemma2-q5.gguf"
  python -m app.main
  ```

## 6. 配置確認
1. `model/` に目的の `.gguf` ファイルが存在するか確認します。
   ```bash
   ls -lh model
   ```
2. アプリを起動し、モデルファイル未検出エラーが出なければ配置完了です。
   ```bash
   python -m app.main
   ```

これで Mind-Chat がローカル LLM を正しく読み込めるようになります。PyInstaller で配布する際は、この `model/` ディレクトリをビルド成果物に含めてください。
