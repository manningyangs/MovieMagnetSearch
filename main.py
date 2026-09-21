"""电影磁力链接搜索工具 — 入口。"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from config import AppConfig
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("电影磁力链接搜索")
    config = AppConfig.load()
    win = MainWindow(config)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
