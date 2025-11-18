from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .config import AppConfig
from .ui import MainWindow


def main() -> None:
    # Qt アプリのエントリポイント。設定→メインウィンドウを生成して実行する。
    app = QApplication(sys.argv)
    config = AppConfig()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
