# Windows向けアプリケーション化ガイド

Mind-Chat を Windows でワンクリック実行できるようにするための PyInstaller によるパッケージング手順と、配布時の注意点をまとめます。Gemma 2 2B Japanese IT (約 1.6 GB) を含めた onedir ビルドを想定しています。

## 1. 前提条件
- Windows 10/11
- Python 3.10 以上
- Visual Studio Build Tools もしくは公式 CPython 配布に付属する MSVC ランタイム
- Mind-Chat リポジトリ直下に `data/`・`model/` ディレクトリが存在し、`model/` に GGUF ファイルが配置されていること

## 2. 仮想環境の作成と依存関係インストール
```powershell
cd C:\Users\<you>\VSCode-Projects\Mind-Chat
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller
```

## 3. ランチャースクリプト
PyInstaller はトップレベルスクリプトを実行するため、プロジェクトルートに `mindchat_launcher.py` を配置し、`from app.main import main` を呼び出す形にします。これにより相対インポート問題を回避します。

## 4. PyInstaller コマンド
```powershell
pyinstaller --noconfirm --clean --name MindChat --noconsole --onedir `
  --collect-all PySide6 `
  --collect-all llama_cpp `
  --add-data "data;data" `
  --add-data "model;model" `
  mindchat_launcher.py
```

### オプションの意味
- `--onedir`: DLL やモデルを含むフォルダ構成で出力（大容量モデル向け）
- `--collect-all PySide6` / `llama_cpp`: Qt プラグイン・llama-cpp バイナリを自動収集
- `--add-data`: 履歴・モデルディレクトリをそのまま同梱

ビルド完了後、実行可能ファイルは `dist/MindChat/MindChat.exe` に生成されます。

## 5. 動作確認
1. `dist/MindChat` フォルダへ移動し、`MindChat.exe` を起動
2. モデルが正しく読み込まれるか（未配置エラーが出ないか）確認
3. 会話を行い、`dist/MindChat/data/history.json` に履歴が保存されるか確認
4. DLL 欠損などがないかをクリーンな Windows 環境でもテスト

## 6. 配布方法
- 配布する際は `dist/MindChat` フォルダを丸ごと圧縮（ZIP など）し、受け取ったユーザーに解凍してもらいます。
- `.exe` 単体を取り出すと DLL/プラグインが見つからず起動できないため、必ずフォルダ構成のまま渡してください。
- ユーザーには「フォルダを解凍 → `MindChat.exe` をダブルクリック」と案内します。
- 追加の VC++ 再頒布可能パッケージが必要な場合は、Microsoft 公式サイトのインストーラを同梱（またはリンク提示）すると親切です。

## 7. よくあるトラブル
| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `attempted relative import with no known parent package` | PyInstaller が `app/main.py` を単体スクリプトとして実行 | `mindchat_launcher.py` 経由で `app.main` を呼び出す |
| モデル未検出エラー | `model/` が同梱されていない、もしくは展開先のパスが変わっている | `--add-data "model;model"` を再確認し、配布フォルダ内のファイル名が `AppConfig.model_filename` と一致しているか確認 |
| DLL が見つからない | Qt/llama-cpp の依存 DLL を収集できていない | `--collect-all` オプションの追加、足りない DLL を `--add-binary` で手動同梱 |

この手順で作成したフォルダを配布すれば、ユーザーは環境構築やモデルダウンロードを行わずにローカル悩み相談アプリを起動できます。
