from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.core import APP_FULL_NAME, APP_SLUG, installation_dir, log_dir
from app.main_window import MainWindow
from app.styles import APP_STYLE


def configure_logging() -> None:
    path = log_dir() / "kliptora.log"
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )


def set_windows_identity() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_SLUG}.Desktop.2")
    except Exception:
        pass


def main() -> int:
    set_windows_identity()
    configure_logging()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_FULL_NAME)
    app.setOrganizationName("KliptoraTools")
    icon_path = installation_dir() / "assets" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
