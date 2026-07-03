from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QTimer, QUrl, QPoint, QRectF
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap, QPainter, QColor, QLinearGradient, QPen, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedLayout,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .core import (
    APP_FULL_NAME,
    APP_NAME,
    APP_ORGANIZATION,
    APP_SLUG,
    AUDIO_BITRATES,
    AUDIO_FORMATS,
    BROWSERS,
    SOURCE_MODES,
    VIDEO_CONTAINERS,
    VIDEO_QUALITIES,
    DownloadJob,
    activate_tool_paths,
    app_data_dir,
    bundled_resource,
    classify_url,
    find_deno,
    find_ffmpeg,
    human_duration,
    plugin_dir,
    sanitize_diagnostic_text,
    installation_dir,
    split_urls,
    update_config_path,
)
from .security import create_pin_record, protect_secret, unprotect_secret, verify_pin
from .updates import (
    PackageBuildWorker,
    build_update_package,
    PublishReleaseWorker,
    RepositoryTestWorker,
    UpdateCheckWorker,
    UpdateDownloadWorker,
)
from .version import APP_VERSION
from .workers import (
    AnalyzeWorker,
    DenoInstallWorker,
    DownloadWorker,
    EngineUpdateWorker,
    FfmpegInstallWorker,
)


class RoundedProgressBar(QWidget):
    """Tam kapsül biçimli, pürüzsüz boyanan indirme ilerleme çubuğu."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self._format = "%p%"
        self.setMinimumHeight(28)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(minimum + 1, maximum)
        self.update()

    def setValue(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, int(value)))
        self.update()

    def value(self) -> int:
        return self._value

    def setFormat(self, value: str) -> None:
        self._format = value
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        outer_radius = outer.height() / 2.0
        painter.setPen(QPen(QColor(79, 101, 173, 220), 1.0))
        painter.setBrush(QColor(5, 12, 29, 245))
        painter.drawRoundedRect(outer, outer_radius, outer_radius)

        inner = outer.adjusted(4.0, 4.0, -4.0, -4.0)
        span = max(1, self._maximum - self._minimum)
        ratio = (self._value - self._minimum) / span
        if ratio > 0:
            fill_width = inner.width() * max(0.0, min(1.0, ratio))
            fill = QRectF(inner.left(), inner.top(), fill_width, inner.height())
            fill_radius = min(inner.height() / 2.0, max(1.0, fill.width() / 2.0))
            gradient = QLinearGradient(inner.left(), inner.top(), inner.right(), inner.top())
            gradient.setColorAt(0.0, QColor(24, 197, 255))
            gradient.setColorAt(0.34, QColor(54, 129, 255))
            gradient.setColorAt(0.68, QColor(124, 82, 246))
            gradient.setColorAt(1.0, QColor(215, 55, 222))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill, fill_radius, fill_radius)

        percent = int(round(ratio * 100))
        label = self._format.replace("%p", str(percent))
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(outer, Qt.AlignmentFlag.AlignCenter, label)


class AdminPasswordDialog(QDialog):
    def __init__(self, *, setup: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup = setup
        self.setWindowTitle("Yönetici parolası oluştur" if setup else "Yönetici girişi")
        self.setModal(True)
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(13)
        title = QLabel("Yönetici hesabını oluştur" if setup else "Yönetici merkezinin kilidini aç")
        title.setObjectName("SectionTitle")
        subtitle = QLabel(
            "Bu parola yalnızca bu bilgisayarda saklanır. GitHub anahtarından farklı bir parola kullan."
            if setup
            else "Güncelleme yayınlama araçlarına erişmek için yerel yönetici parolanı gir."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("En az 4 karakter")
        layout.addWidget(self.password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("Parolayı tekrar gir")
        self.confirm.setVisible(setup)
        layout.addWidget(self.confirm)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        password = self.password.text()
        if len(password.strip()) < 4:
            QMessageBox.warning(self, "Parola", "Parola en az 4 karakter olmalı.")
            return
        if self.setup and password != self.confirm.text():
            QMessageBox.warning(self, "Parola", "Parolalar aynı değil.")
            return
        self.accept()

    def value(self) -> str:
        return self.password.text()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(APP_ORGANIZATION, APP_SLUG)
        self.jobs: list[DownloadJob] = []
        self.rows: dict[str, int] = {}
        self.progress_widgets: dict[str, RoundedProgressBar] = {}
        self.download_thread: QThread | None = None
        self.download_worker: DownloadWorker | None = None
        self._stop_requested = False
        self._restart_requested = False
        self._completed_job_ids: set[str] = set()
        self._threads: list[QThread] = []
        self._workers: list[Any] = []
        self._analyzed_title = ""
        self._last_page_index = 0
        self._admin_unlocked = False
        self._owner_mode = (app_data_dir() / ".owner-mode").exists()
        self.admin_page_index: int | None = None
        self._pending_update: dict[str, Any] | None = None
        self._built_package: dict[str, str] = {}
        self._update_check_serial = 0
        self._update_check_in_progress = False

        self.setWindowTitle(APP_FULL_NAME)
        self.setMinimumSize(1180, 760)
        self.resize(1460, 900)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._drag_pos: QPoint | None = None
        icon_path = installation_dir() / "assets" / "app.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        activate_tool_paths()
        self._build_ui()
        self._restore_settings()
        self._refresh_tool_status()
        QTimer.singleShot(900, self._auto_check_updates)

    # ---------- UI helpers ----------
    def _card(self, object_name: str = "Card") -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName(object_name)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(13)
        return frame, layout

    def _section_heading(self, icon: str, title: str, subtitle: str = "") -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(11)
        icon_label = QLabel(icon)
        icon_label.setObjectName("Accent")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedWidth(24)
        text = QVBoxLayout()
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        text.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Muted")
            sub.setWordWrap(True)
            text.addWidget(sub)
        row.addWidget(icon_label)
        row.addLayout(text, 1)
        return widget

    def _page_header(self, icon: str, title: str, subtitle: str) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(15)
        icon_frame = QFrame()
        icon_frame.setObjectName("PageIcon")
        icon_frame.setFixedSize(56, 56)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(icon)
        icon_label.setObjectName("PageIconLabel")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)
        texts = QVBoxLayout()
        texts.setSpacing(5)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        texts.addWidget(title_label)
        texts.addWidget(subtitle_label)
        row.addWidget(icon_frame, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(texts, 1)
        return header

    def _scroll_page(self, icon: str, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 28)
        layout.setSpacing(16)
        layout.addWidget(self._page_header(icon, title, subtitle))
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page, layout

    def _plain_page(self, icon: str, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 28)
        layout.setSpacing(16)
        layout.addWidget(self._page_header(icon, title, subtitle))
        return page, layout

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        shell = QFrame()
        shell.setObjectName("AppShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(42)
        topbar_row = QHBoxLayout(topbar)
        topbar_row.setContentsMargins(16, 8, 16, 0)
        topbar_row.setSpacing(8)
        topbar_row.addStretch(1)
        self.min_button = QPushButton("—")
        self.min_button.setObjectName("WindowButton")
        self.min_button.clicked.connect(self.showMinimized)
        self.max_button = QPushButton("▢")
        self.max_button.setObjectName("WindowButton")
        self.max_button.clicked.connect(self._toggle_maximize)
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("WindowButtonClose")
        self.close_button.clicked.connect(self.close)
        topbar_row.addWidget(self.min_button)
        topbar_row.addWidget(self.max_button)
        topbar_row.addWidget(self.close_button)
        shell_layout.addWidget(topbar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(300)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 10, 22, 20)
        side.setSpacing(8)

        brand = QFrame()
        brand.setObjectName("BrandPanel")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(4, 4, 4, 4)
        brand_layout.setSpacing(13)
        logo = QLabel("K")
        logo.setObjectName("LogoFallback")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(72, 72)
        logo_path = installation_dir() / "assets" / "app.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                logo.setPixmap(pix.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                logo.setStyleSheet("background:transparent;border:none;")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setObjectName("BrandTitle")
        subtitle = QLabel("Video Downloader")
        subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand_layout.addWidget(logo)
        brand_layout.addLayout(brand_text, 1)
        side.addWidget(brand)
        side.addSpacing(22)

        self.nav_buttons: list[QPushButton] = []
        nav_items = [
            ("⇩", "İndirme"),
            ("☷", "Kuyruk"),
            ("⚙", "Ayarlar"),
            ("⌘", "Kayıtlar"),
        ]
        if self._owner_mode:
            self.admin_page_index = len(nav_items)
            nav_items.append(("♛", "Yönetici"))
        for index, (icon, text) in enumerate(nav_items):
            button = QPushButton(f"{icon}   {text}")
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self._switch_page(i))
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch(1)

        status, status_layout = self._card("StatusCard")
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(7)
        status_row = QHBoxLayout()
        dot = QLabel("●")
        dot.setObjectName("StatusDot")
        self.engine_pill = QLabel("Motor kontrol ediliyor")
        self.engine_pill.setObjectName("CardTitle")
        status_row.addWidget(dot)
        status_row.addWidget(self.engine_pill, 1)
        status_layout.addLayout(status_row)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color:#283758;")
        status_layout.addWidget(divider)
        version = QLabel(f"v{APP_VERSION}  •  Windows  •  EXE")
        version.setObjectName("TinyMuted")
        status_layout.addWidget(version)
        side.addWidget(status)

        body_layout.addWidget(sidebar)
        self.pages = QStackedWidget()
        body_layout.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_download_page())
        self.pages.addWidget(self._build_queue_page())
        self.pages.addWidget(self._build_settings_page())
        self.pages.addWidget(self._build_logs_page())
        if self._owner_mode:
            self.pages.addWidget(self._build_admin_page())
        shell_layout.addWidget(body, 1)
        root_layout.addWidget(shell, 1)
        self._set_page(0)
        self.statusBar().hide()
        self.statusBar().showMessage("Hazır")

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.max_button.setText("▢")
        else:
            self.showMaximized()
            self.max_button.setText("❐")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 46:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ---------- download page ----------
    def _build_download_page(self) -> QWidget:
        page, layout = self._scroll_page(
            "⇩",
            "Video indir",
            "Bir veya birden fazla bağlantıyı yapıştır; kaliteyi seç, kuyruğa ekle veya hemen indir.",
        )

        url_card, url_layout = self._card()
        url_layout.addWidget(self._section_heading("↗", "Bağlantıyı buraya yapıştırın", "Her satıra ayrı bir bağlantı yazabilirsin."))
        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.url_input = QPlainTextEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("https://...")
        self.url_input.setFixedHeight(78)
        self.url_input.textChanged.connect(self._update_url_count)
        input_row.addWidget(self.url_input, 1)
        input_actions = QVBoxLayout()
        input_actions.setSpacing(8)
        paste = QPushButton("▣  Panodan yapıştır")
        paste.clicked.connect(self._paste_urls)
        clear = QPushButton("×  Temizle")
        clear.clicked.connect(self.url_input.clear)
        input_actions.addWidget(paste)
        input_actions.addWidget(clear)
        input_row.addLayout(input_actions)
        url_layout.addLayout(input_row)
        analyze_row = QHBoxLayout()
        self.url_count_label = QLabel("0 geçerli bağlantı")
        self.url_count_label.setObjectName("Muted")
        self.analyze_button = QPushButton("✦  Bağlantıyı analiz et")
        self.analyze_button.setObjectName("Primary")
        self.analyze_button.clicked.connect(self._analyze)
        analyze_row.addWidget(self.url_count_label)
        analyze_row.addStretch()
        analyze_row.addWidget(self.analyze_button)
        url_layout.addLayout(analyze_row)
        layout.addWidget(url_card)

        preview_card, preview_layout = self._card()
        preview_layout.addWidget(self._section_heading("◉", "Bağlantı önizleme"))
        preview_inner = QFrame()
        preview_inner.setObjectName("PreviewInner")
        preview_row = QHBoxLayout(preview_inner)
        preview_row.setContentsMargins(12, 12, 16, 12)
        preview_row.setSpacing(16)
        thumb_frame = QFrame()
        thumb_frame.setObjectName("ThumbnailFrame")
        thumb_frame.setFixedSize(226, 128)
        thumb_layout = QVBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail = QLabel("▶")
        self.thumbnail.setObjectName("BigEmptyIcon")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setScaledContents(False)
        thumb_layout.addWidget(self.thumbnail)
        preview_row.addWidget(thumb_frame)
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(7)
        self.preview_name = QLabel("Video başlığı burada görünecek")
        self.preview_name.setObjectName("CardTitle")
        self.preview_name.setWordWrap(True)
        self.preview_meta = QLabel("Kanal adı   •   — görüntüleme   •   —")
        self.preview_meta.setObjectName("Muted")
        self.preview_meta.setWordWrap(True)
        self.preview_details = QLabel("Henüz analiz edilmedi")
        self.preview_details.setObjectName("TinyMuted")
        meta_layout.addWidget(self.preview_name)
        meta_layout.addWidget(self.preview_meta)
        meta_layout.addStretch()
        meta_layout.addWidget(self.preview_details)
        preview_row.addLayout(meta_layout, 1)
        self.analysis_badge = QLabel("ANALİZ BEKLİYOR")
        self.analysis_badge.setObjectName("Accent")
        self.analysis_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analysis_badge.setMinimumWidth(150)
        preview_row.addWidget(self.analysis_badge)
        preview_layout.addWidget(preview_inner)
        layout.addWidget(preview_card)

        lower = QHBoxLayout()
        lower.setSpacing(16)
        options_card, options_layout = self._card()
        options_layout.addWidget(self._section_heading("⚙", "İndirme seçenekleri"))
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(14)
        form_grid.setVerticalSpacing(10)
        self.media_type = QComboBox()
        self.media_type.addItems(["Video", "Sadece ses"])
        self.media_type.currentIndexChanged.connect(self._media_type_changed)
        self.quality = QComboBox()
        self.quality.addItems(VIDEO_QUALITIES.keys())
        self.video_container = QComboBox()
        self.video_container.addItems(VIDEO_CONTAINERS)
        self.audio_format = QComboBox()
        self.audio_format.addItems(AUDIO_FORMATS)
        self.audio_bitrate = QComboBox()
        self.audio_bitrate.addItems(AUDIO_BITRATES)
        self.source_mode = QComboBox()
        self.source_mode.addItems(SOURCE_MODES)
        form_grid.addWidget(QLabel("Tür"), 0, 0)
        form_grid.addWidget(self.media_type, 0, 1)
        form_grid.addWidget(QLabel("Kalite"), 1, 0)
        form_grid.addWidget(self.quality, 1, 1)
        form_grid.addWidget(QLabel("Video biçimi"), 2, 0)
        form_grid.addWidget(self.video_container, 2, 1)
        form_grid.addWidget(QLabel("Ses biçimi"), 0, 2)
        form_grid.addWidget(self.audio_format, 0, 3)
        form_grid.addWidget(QLabel("Ses kalitesi"), 1, 2)
        form_grid.addWidget(self.audio_bitrate, 1, 3)
        form_grid.addWidget(QLabel("Kaynak modu"), 2, 2)
        form_grid.addWidget(self.source_mode, 2, 3)
        options_layout.addLayout(form_grid)

        output_row = QHBoxLayout()
        output_label = QLabel("Kaydetme yolu")
        output_label.setMinimumWidth(105)
        self.output_dir = QLineEdit()
        browse = QPushButton("▣  Gözat")
        browse.clicked.connect(self._choose_output)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_dir, 1)
        output_row.addWidget(browse)
        options_layout.addLayout(output_row)

        checks = QGridLayout()
        checks.setHorizontalSpacing(20)
        checks.setVerticalSpacing(10)
        self.playlist = QCheckBox("Oynatma listesini indir")
        self.playlist_subfolder = QCheckBox("Liste için alt klasör aç")
        self.playlist_subfolder.setChecked(True)
        self.subtitles = QCheckBox("Normal altyazıları ekle")
        self.auto_subtitles = QCheckBox("Otomatik altyazıları ekle")
        self.embed_thumbnail = QCheckBox("Kapak görselini ekle")
        self.embed_thumbnail.setChecked(True)
        self.embed_metadata = QCheckBox("Medya bilgilerini ekle")
        self.embed_metadata.setChecked(True)
        self.write_description = QCheckBox("Açıklamayı metin dosyası olarak kaydet")
        self.live_from_start = QCheckBox("Canlı yayını mümkünse baştan kaydet")
        self.format_fallback = QCheckBox("Biçim bulunamazsa otomatik yedek kullan")
        self.format_fallback.setChecked(True)
        checks.addWidget(self.playlist, 0, 0)
        checks.addWidget(self.playlist_subfolder, 0, 1)
        checks.addWidget(self.subtitles, 1, 0)
        checks.addWidget(self.auto_subtitles, 1, 1)
        checks.addWidget(self.embed_thumbnail, 2, 0)
        checks.addWidget(self.embed_metadata, 2, 1)
        checks.addWidget(self.write_description, 3, 0)
        checks.addWidget(self.live_from_start, 3, 1)
        checks.addWidget(self.format_fallback, 4, 0, 1, 2)
        options_layout.addLayout(checks)
        lower.addWidget(options_card, 3)

        analysis_card, analysis_layout = self._card()
        analysis_layout.addWidget(self._section_heading("⌁", "Bağlantı analizi"))
        analysis_icon = QLabel("⌕")
        analysis_icon.setObjectName("BigEmptyIcon")
        analysis_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analysis_title = QLabel("Analiz için bağlantı girin")
        self.analysis_title.setObjectName("CardTitle")
        self.analysis_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analysis_info = QLabel("Kalite, süre ve video bilgileri burada görüntülenecek.")
        self.analysis_info.setObjectName("Muted")
        self.analysis_info.setWordWrap(True)
        self.analysis_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        analysis_layout.addStretch()
        analysis_layout.addWidget(analysis_icon)
        analysis_layout.addWidget(self.analysis_title)
        analysis_layout.addWidget(self.analysis_info)
        analysis_layout.addStretch()
        lower.addWidget(analysis_card, 2)
        layout.addLayout(lower)

        actions_card, action_layout = self._card("ActionCard")
        action_row = QHBoxLayout()
        action_row.addStretch()
        self.add_queue_button = QPushButton("＋  Kuyruğa ekle")
        self.add_queue_button.clicked.connect(self._add_to_queue)
        self.download_now_button = QPushButton("⇩  Şimdi indir")
        self.download_now_button.setObjectName("Primary")
        self.download_now_button.clicked.connect(self._download_now)
        action_row.addWidget(self.add_queue_button)
        action_row.addWidget(self.download_now_button)
        action_layout.addLayout(action_row)
        layout.addWidget(actions_card)
        layout.addStretch()
        self._media_type_changed()
        return page

    # ---------- queue page ----------
    def _build_queue_page(self) -> QWidget:
        page, layout = self._plain_page(
            "⇩",
            "İndirme kuyruğu",
            "İşler sırayla indirilir. Hatalı işler diğerlerini durdurmaz.",
        )
        card, card_layout = self._card()
        bar = QHBoxLayout()
        self.queue_summary = QLabel("Kuyruk boş")
        self.queue_summary.setObjectName("SectionTitle")
        bar.addWidget(self.queue_summary)
        bar.addStretch()
        open_folder = QPushButton("▣  Klasörü aç")
        open_folder.clicked.connect(self.open_output_folder)
        self.remove_button = QPushButton("⌫  Seçileni kaldır")
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button = QPushButton("⌁  Kuyruğu temizle")
        self.clear_button.clicked.connect(self._clear_queue)
        self.stop_button = QPushButton("□  Durdur")
        self.stop_button.setObjectName("Danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_downloads)
        self.start_button = QPushButton("▷  Kuyruğu başlat")
        self.start_button.setObjectName("Primary")
        self.start_button.clicked.connect(self._start_queue)
        for widget in (open_folder, self.remove_button, self.clear_button, self.stop_button, self.start_button):
            bar.addWidget(widget)
        card_layout.addLayout(bar)

        container = QFrame()
        container.setObjectName("QueuePanel")
        stack = QStackedLayout(container)
        stack.setContentsMargins(8, 8, 8, 8)
        stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.queue_table = QTableWidget(0, 8)
        self.queue_table.setObjectName("QueueTable")
        self.queue_table.setHorizontalHeaderLabels(["#", "Başlık / URL", "Tür", "Kalite", "İlerleme", "Hız", "ETA", "Durum"])
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.setShowGrid(False)
        self.queue_table.setCornerButtonEnabled(False)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Kuyruk tablosu pencereye tam oturur; yatay kaydırma oluşmaz.
        self.queue_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.queue_table.setWordWrap(False)
        self.queue_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        header = self.queue_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(36)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 38)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 68)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 88)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 72)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 56)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(7, 86)
        stack.addWidget(self.queue_table)

        self.queue_empty = QFrame()
        empty_layout = QVBoxLayout(self.queue_empty)
        empty_layout.setContentsMargins(0, 86, 0, 40)
        empty_layout.addStretch()
        empty_icon = QLabel("☷")
        empty_icon.setObjectName("BigEmptyIcon")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title = QLabel("Kuyruk boş")
        empty_title.setObjectName("BigEmptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_text = QLabel("Henüz kuyruğa eklenmiş bir indirme yok.\nBaşlamak için indirilecek içerikleri ekleyin.")
        empty_text.setObjectName("Muted")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add = QPushButton("＋  İndirme ekle")
        add.setObjectName("Primary")
        add.clicked.connect(lambda: self._switch_page(0))
        add_row = QHBoxLayout()
        add_row.addStretch()
        add_row.addWidget(add)
        add_row.addStretch()
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_text)
        empty_layout.addLayout(add_row)
        empty_layout.addStretch()
        stack.addWidget(self.queue_empty)
        self.queue_empty.raise_()
        card_layout.addWidget(container, 1)
        layout.addWidget(card, 1)
        return page

    # ---------- settings page ----------
    def _build_settings_page(self) -> QWidget:
        page, layout = self._scroll_page(
            "⚙",
            "Ayarlar",
            "İndirme davranışını, gerekli araçları ve uygulama güncellemelerini yönet.",
        )

        general, gl = self._card()
        gl.addWidget(self._section_heading("⚙", "Genel"))
        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        self.cookie_browser = QComboBox()
        self.cookie_browser.addItems(BROWSERS)
        self.cookie_profile = QLineEdit()
        self.cookie_profile.setPlaceholderText("İsteğe bağlı profil adı veya profil klasörü")
        self.cookie_file = QLineEdit()
        self.cookie_file.setPlaceholderText("İsteğe bağlı: Netscape biçiminde cookies.txt")
        cookie_file_widget = QWidget()
        cookie_file_row = QHBoxLayout(cookie_file_widget)
        cookie_file_row.setContentsMargins(0, 0, 0, 0)
        cookie_file_row.setSpacing(8)
        cookie_file_row.addWidget(self.cookie_file, 1)
        cookie_file_button = QPushButton("Seç")
        cookie_file_button.clicked.connect(self._choose_cookie_file)
        cookie_file_row.addWidget(cookie_file_button)
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("Örnek: http://127.0.0.1:8080")
        self.referer = QLineEdit()
        self.referer.setPlaceholderText("İsteğe bağlı: https://site.example/")
        self.custom_user_agent = QLineEdit()
        self.custom_user_agent.setPlaceholderText("Boş bırakırsan motorun varsayılanı kullanılır")
        self.concurrent_fragments = QSpinBox()
        self.concurrent_fragments.setRange(1, 16)
        self.concurrent_fragments.setValue(4)
        self.concurrent_fragments.setSuffix(" parça")
        self.auto_update_check = QCheckBox("Uygulama açıldığında güncellemeleri denetle")
        form.addRow("Tarayıcı çerezleri", self.cookie_browser)
        form.addRow("Tarayıcı profili", self.cookie_profile)
        form.addRow("Çerez dosyası", cookie_file_widget)
        form.addRow("Proxy", self.proxy)
        form.addRow("Referer", self.referer)
        form.addRow("User-Agent", self.custom_user_agent)
        form.addRow("Eşzamanlı parçalar", self.concurrent_fragments)
        form.addRow("", self.auto_update_check)
        gl.addLayout(form)
        note = QLabel("Çerez dosyası seçilirse tarayıcıdan doğrudan çerez okumaya göre öncelikli kullanılır. Yalnızca kendi oturumunun erişebildiği ve indirme iznin bulunan içeriklerde kullan. DRM koruması desteklenmez.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        gl.addWidget(note)
        layout.addWidget(general)

        tools, tl = self._card()
        tl.addWidget(self._section_heading("⌘", "Gerekli araçlar", "FFmpeg medya birleştirme, Deno ise güncel site çözücüleri için kullanılır."))
        ff_row_frame = QFrame()
        ff_row_frame.setObjectName("ToolRow")
        ff = QHBoxLayout(ff_row_frame)
        ff.setContentsMargins(16, 13, 16, 13)
        ff_text = QVBoxLayout()
        ff_title = QLabel("FFmpeg")
        ff_title.setObjectName("CardTitle")
        self.ffmpeg_status = QLabel("Kontrol ediliyor")
        self.ffmpeg_status.setObjectName("Muted")
        self.ffmpeg_status.setWordWrap(True)
        ff_text.addWidget(ff_title)
        ff_text.addWidget(self.ffmpeg_status)
        self.install_ffmpeg_button = QPushButton("↻  FFmpeg'i kontrol et / onar")
        self.install_ffmpeg_button.clicked.connect(self._install_ffmpeg)
        ff.addLayout(ff_text, 1)
        ff.addWidget(self.install_ffmpeg_button)
        tl.addWidget(ff_row_frame)
        self.ffmpeg_progress = QProgressBar()
        self.ffmpeg_progress.setObjectName("ToolProgress")
        self.ffmpeg_progress.setVisible(False)
        tl.addWidget(self.ffmpeg_progress)

        deno_row_frame = QFrame()
        deno_row_frame.setObjectName("ToolRow")
        dr = QHBoxLayout(deno_row_frame)
        dr.setContentsMargins(16, 13, 16, 13)
        dtext = QVBoxLayout()
        dtitle = QLabel("Deno")
        dtitle.setObjectName("CardTitle")
        self.deno_status = QLabel("Kontrol ediliyor")
        self.deno_status.setObjectName("Muted")
        self.deno_status.setWordWrap(True)
        dtext.addWidget(dtitle)
        dtext.addWidget(self.deno_status)
        self.install_deno_button = QPushButton("↻  Deno'yu kontrol et / onar")
        self.install_deno_button.clicked.connect(self._install_deno)
        recheck = QPushButton("↻  Tekrar kontrol et")
        recheck.clicked.connect(self._refresh_tool_status)
        dr.addLayout(dtext, 1)
        dr.addWidget(self.install_deno_button)
        dr.addWidget(recheck)
        tl.addWidget(deno_row_frame)
        self.deno_progress = QProgressBar()
        self.deno_progress.setObjectName("ToolProgress")
        self.deno_progress.setVisible(False)
        tl.addWidget(self.deno_progress)
        self.tool_notice = QLabel("")
        self.tool_notice.setObjectName("InlineNotice")
        self.tool_notice.setWordWrap(True)
        self.tool_notice.setVisible(False)
        tl.addWidget(self.tool_notice)
        layout.addWidget(tools)

        update_card, ul = self._card("UpdateCard")
        ul.addWidget(self._section_heading("↑", "Uygulama güncellemesi", f"Yüklü sürüm: v{APP_VERSION}"))
        self.update_status = QLabel("Güncelleme kanalı henüz ayarlanmamış olabilir.")
        self.update_status.setObjectName("Muted")
        self.update_status.setWordWrap(True)
        ul.addWidget(self.update_status)
        self.update_progress = QProgressBar()
        self.update_progress.setVisible(False)
        ul.addWidget(self.update_progress)
        update_actions = QHBoxLayout()
        self.check_update_button = QPushButton("↻  Güncellemeleri denetle")
        self.check_update_button.clicked.connect(lambda: self._check_updates(True))
        self.install_update_button = QPushButton("⇩  Güncellemeyi indir ve kur")
        self.install_update_button.setObjectName("Primary")
        self.install_update_button.setEnabled(False)
        self.install_update_button.clicked.connect(self._download_update)
        update_actions.addWidget(self.check_update_button)
        update_actions.addWidget(self.install_update_button)
        update_actions.addStretch()
        ul.addLayout(update_actions)
        layout.addWidget(update_card)

        maintenance, ml = self._card()
        ml.addWidget(self._section_heading("◇", "Bakım"))
        self.engine_update_progress = QProgressBar()
        self.engine_update_progress.setVisible(False)
        ml.addWidget(self.engine_update_progress)
        row2 = QHBoxLayout()
        self.engine_update_button = QPushButton("↑  İndirme motorunu güncelle")
        self.engine_update_button.setObjectName("Primary")
        self.engine_update_button.clicked.connect(self._update_engine)
        open_data = QPushButton("▣  Uygulama veri klasörünü aç")
        open_data.clicked.connect(self._open_app_data)
        open_plugins = QPushButton("◇  Eklenti klasörünü aç")
        open_plugins.clicked.connect(self._open_plugin_dir)
        row2.addWidget(self.engine_update_button)
        row2.addWidget(open_data)
        row2.addWidget(open_plugins)
        row2.addStretch()
        ml.addLayout(row2)
        layout.addWidget(maintenance)
        layout.addStretch()
        return page

    # ---------- logs page ----------
    def _build_logs_page(self) -> QWidget:
        page, layout = self._plain_page("⌘", "Kayıtlar", "İndirme işlemleri, sistem olayları ve hata ayrıntıları burada görünür.")
        card, cl = self._card()
        row = QHBoxLayout()
        row.addWidget(self._section_heading("▤", "Oturum kaydı"))
        row.addStretch()
        diagnostic = QPushButton("▣  Tanılama raporu")
        diagnostic.clicked.connect(self._save_diagnostic_report)
        clear = QPushButton("⌫  Temizle")
        clear.clicked.connect(self._clear_logs)
        row.addWidget(diagnostic)
        row.addWidget(clear)
        cl.addLayout(row)
        self.log_box = QTextEdit()
        self.log_box.setObjectName("LogViewer")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Henüz kayıt yok.\n\nİndirme işlemleri, sistem olayları ve hatalar burada listelenecektir.")
        cl.addWidget(self.log_box, 1)
        layout.addWidget(card, 1)
        return page

    # ---------- admin page ----------
    def _build_admin_page(self) -> QWidget:
        page, layout = self._scroll_page(
            "♛",
            "Yönetici merkezi",
            "Güncelleme paketleri oluştur, GitHub sürümlerini yayınla ve uygulamanın güncelleme kanalını yönet.",
        )

        repo_card, rl = self._card()
        rl.addWidget(self._section_heading("⌁", "Yayın kanalı", "Kullanıcılar güncellemeleri bu GitHub deposundan alır."))
        repo_form = QFormLayout()
        repo_form.setHorizontalSpacing(20)
        repo_form.setVerticalSpacing(11)
        self.repo_owner = QLineEdit()
        self.repo_owner.setPlaceholderText("GitHub kullanıcı veya organizasyon adı")
        self.repo_name = QLineEdit()
        self.repo_name.setPlaceholderText("Depo adı")
        repo_form.addRow("Sahip", self.repo_owner)
        repo_form.addRow("Depo", self.repo_name)
        rl.addLayout(repo_form)
        repo_buttons = QHBoxLayout()
        save_repo = QPushButton("✓  Kanalı kaydet")
        save_repo.clicked.connect(self._save_repository_config)
        self.test_repo_button = QPushButton("↻  Bağlantıyı test et")
        self.test_repo_button.clicked.connect(self._test_repository)
        repo_buttons.addWidget(save_repo)
        repo_buttons.addWidget(self.test_repo_button)
        repo_buttons.addStretch()
        rl.addLayout(repo_buttons)
        self.repo_status = QLabel("Henüz test edilmedi.")
        self.repo_status.setObjectName("Muted")
        rl.addWidget(self.repo_status)
        layout.addWidget(repo_card)

        auth_card, al = self._card()
        al.addWidget(self._section_heading("◆", "GitHub yetkilendirmesi", "Anahtar Windows hesabına bağlı olarak şifrelenir ve güncelleme paketine eklenmez."))
        auth_form = QFormLayout()
        self.github_token = QLineEdit()
        self.github_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token.setPlaceholderText("github_pat_... veya ghp_...")
        auth_form.addRow("Erişim anahtarı", self.github_token)
        al.addLayout(auth_form)
        auth_buttons = QHBoxLayout()
        save_token = QPushButton("✓  Anahtarı güvenli kaydet")
        save_token.clicked.connect(self._save_github_token)
        clear_token = QPushButton("⌫  Kayıtlı anahtarı sil")
        clear_token.clicked.connect(self._clear_github_token)
        auth_buttons.addWidget(save_token)
        auth_buttons.addWidget(clear_token)
        auth_buttons.addStretch()
        al.addLayout(auth_buttons)
        layout.addWidget(auth_card)

        package_card, pl = self._card()
        pl.addWidget(self._section_heading("▣", "Güncelleme paketi", "Yalnızca uygulama kodu ve görseller paketlenir; çalışan EXE, runtime, kurulum ve kullanıcı dosyalarına dokunulmaz."))
        package_form = QFormLayout()
        package_form.setHorizontalSpacing(20)
        package_form.setVerticalSpacing(11)
        self.release_version = QLineEdit(APP_VERSION)
        self.release_title = QLineEdit(f"{APP_FULL_NAME} v{APP_VERSION}")
        self.release_notes = QPlainTextEdit()
        self.release_notes.setPlaceholderText("Bu sürümde neler değişti?")
        self.release_notes.setFixedHeight(100)
        self.source_dir = QLineEdit(str(installation_dir()))
        self.source_dir.setReadOnly(True)
        source_browse = QPushButton("Uygulama klasörü")
        source_browse.setEnabled(False)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_dir, 1)
        source_row.addWidget(source_browse)
        default_zip = Path.home() / "Downloads" / f"{APP_SLUG}-v{APP_VERSION}.zip"
        self.package_path = QLineEdit(str(default_zip))
        package_browse = QPushButton("Seç")
        package_browse.clicked.connect(self._choose_package_path)
        package_row = QHBoxLayout()
        package_row.addWidget(self.package_path, 1)
        package_row.addWidget(package_browse)
        self.release_draft = QCheckBox("Taslak olarak bırak")
        self.release_prerelease = QCheckBox("Ön sürüm olarak işaretle")
        package_form.addRow("Sürüm", self.release_version)
        package_form.addRow("Başlık", self.release_title)
        package_form.addRow("Sürüm notları", self.release_notes)
        package_form.addRow("Kaynak klasörü", source_row)
        package_form.addRow("Çıktı ZIP", package_row)
        pl.addLayout(package_form)
        options_row = QHBoxLayout()
        options_row.addWidget(self.release_draft)
        options_row.addWidget(self.release_prerelease)
        options_row.addStretch()
        pl.addLayout(options_row)
        self.publish_progress = QProgressBar()
        self.publish_progress.setVisible(False)
        pl.addWidget(self.publish_progress)
        self.publish_status = QLabel("Paket henüz oluşturulmadı.")
        self.publish_status.setObjectName("Muted")
        self.publish_status.setWordWrap(True)
        pl.addWidget(self.publish_status)
        publish_actions = QHBoxLayout()
        self.build_package_button = QPushButton("▣  Paketi oluştur")
        self.build_package_button.clicked.connect(self._build_update_package)
        self.publish_button = QPushButton("↑  GitHub'a yayınla")
        self.publish_button.setObjectName("Primary")
        self.publish_button.clicked.connect(self._publish_release)
        publish_actions.addWidget(self.build_package_button)
        publish_actions.addWidget(self.publish_button)
        publish_actions.addStretch()
        pl.addLayout(publish_actions)
        layout.addWidget(package_card)

        local_card, ll = self._card()
        ll.addWidget(self._section_heading("♛", "Yerel yönetici güvenliği"))
        local_actions = QHBoxLayout()
        change_password = QPushButton("◆  Yönetici parolasını değiştir")
        change_password.clicked.connect(self._change_admin_password)
        lock = QPushButton("◇  Yönetici merkezini kilitle")
        lock.clicked.connect(self._lock_admin)
        local_actions.addWidget(change_password)
        local_actions.addWidget(lock)
        local_actions.addStretch()
        ll.addLayout(local_actions)
        layout.addWidget(local_card)
        layout.addStretch()
        return page

    # ---------- navigation / settings ----------
    def _set_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def _switch_page(self, index: int) -> None:
        if self.admin_page_index is not None and index == self.admin_page_index and not self._admin_unlocked:
            if not self._unlock_admin():
                self._set_page(self._last_page_index)
                return
        self._last_page_index = index
        self._set_page(index)

    def _restore_settings(self) -> None:
        self.output_dir.setText(str(self.settings.value("output_dir", str(Path.home() / "Downloads"))))
        self.cookie_browser.setCurrentText(str(self.settings.value("cookie_browser", "Yok")))
        self.cookie_profile.setText(str(self.settings.value("cookie_profile", "")))
        self.cookie_file.setText(str(self.settings.value("cookie_file", "")))
        self.proxy.setText(str(self.settings.value("proxy", "")))
        self.referer.setText(str(self.settings.value("referer", "")))
        self.custom_user_agent.setText(str(self.settings.value("user_agent", "")))
        try:
            self.concurrent_fragments.setValue(int(self.settings.value("concurrent_fragments", 4)))
        except (TypeError, ValueError):
            self.concurrent_fragments.setValue(4)
        self.auto_update_check.setChecked(str(self.settings.value("auto_update", "true")).lower() == "true")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Yönetici arayüzü normal kullanıcılarda hiç oluşturulmaz.
        # Bu yüzden yalnızca sahip modunda yönetici alanlarını doldur.
        if self._owner_mode:
            config = self._load_update_config()
            self.repo_owner.setText(str(self.settings.value("update_owner", config.get("owner", ""))))
            self.repo_name.setText(str(self.settings.value("update_repo", config.get("repo", ""))))
            protected_token = str(self.settings.value("github_token", ""))
            if protected_token:
                self.github_token.setText(unprotect_secret(protected_token))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.settings.setValue("output_dir", self.output_dir.text().strip())
        self.settings.setValue("cookie_browser", self.cookie_browser.currentText())
        self.settings.setValue("cookie_profile", self.cookie_profile.text().strip())
        self.settings.setValue("cookie_file", self.cookie_file.text().strip())
        self.settings.setValue("proxy", self.proxy.text().strip())
        self.settings.setValue("referer", self.referer.text().strip())
        self.settings.setValue("user_agent", self.custom_user_agent.text().strip())
        self.settings.setValue("concurrent_fragments", self.concurrent_fragments.value())
        self.settings.setValue("auto_update", self.auto_update_check.isChecked())
        self.settings.setValue("geometry", self.saveGeometry())
        if self.download_worker:
            self.download_worker.cancel()
        super().closeEvent(event)

    # ---------- thread helper ----------
    def _run_worker(self, worker: Any, on_success: Callable[..., None] | None = None, on_error: Callable[[str], None] | None = None) -> QThread:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        if on_success is not None and hasattr(worker, "success"):
            worker.success.connect(on_success)
        if on_error is not None and hasattr(worker, "error"):
            worker.error.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)

        def cleanup() -> None:
            if thread in self._threads:
                self._threads.remove(thread)
            if worker in self._workers:
                self._workers.remove(worker)

        thread.finished.connect(cleanup)
        thread.start()
        return thread

    # ---------- download actions ----------
    def _media_type_changed(self) -> None:
        audio = self.media_type.currentIndex() == 1
        self.quality.setEnabled(not audio)
        self.video_container.setEnabled(not audio)
        self.audio_format.setEnabled(audio)
        self.audio_bitrate.setEnabled(audio)
        self.subtitles.setEnabled(not audio)
        self.auto_subtitles.setEnabled(not audio)

    def _paste_urls(self) -> None:
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        current = self.url_input.toPlainText().strip()
        self.url_input.setPlainText(f"{current}\n{text}".strip())

    def _update_url_count(self) -> None:
        urls = split_urls(self.url_input.toPlainText())
        count = len(urls)
        if count == 1:
            detected = classify_url(urls[0])
            self.url_count_label.setText(f"1 bağlantı  •  {detected['site']}  •  {detected['kind']}")
        else:
            self.url_count_label.setText(f"{count} geçerli bağlantı")

    def _choose_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "İndirme klasörünü seç", self.output_dir.text() or str(Path.home()))
        if selected:
            self.output_dir.setText(selected)

    def _choose_cookie_file(self) -> None:
        start = self.cookie_file.text().strip() or str(Path.home())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "cookies.txt dosyasını seç",
            start,
            "Çerez dosyaları (*.txt);;Tüm dosyalar (*.*)",
        )
        if selected:
            self.cookie_file.setText(selected)
            self.cookie_browser.setCurrentText("Yok")

    def _analyze(self) -> None:
        urls = split_urls(self.url_input.toPlainText())
        if not urls:
            QMessageBox.warning(self, "Bağlantı", "Önce geçerli bir bağlantı yapıştır.")
            return
        self.analyze_button.setEnabled(False)
        self.analysis_badge.setText("ANALİZ EDİLİYOR")
        self.analysis_title.setText("Bağlantı inceleniyor…")
        worker = AnalyzeWorker(
            urls[0],
            self.cookie_browser.currentText(),
            self.proxy.text(),
            cookie_profile=self.cookie_profile.text(),
            cookie_file=self.cookie_file.text(),
            referer=self.referer.text(),
            user_agent=self.custom_user_agent.text(),
            source_mode=self.source_mode.currentText(),
        )
        worker.success.connect(self._analysis_success)
        worker.error.connect(self._analysis_error)
        worker.finished.connect(lambda: self.analyze_button.setEnabled(True))
        self._run_worker(worker)

    def _analysis_success(self, info: dict[str, Any]) -> None:
        self._analyzed_title = str(info.get("title") or "")
        self.preview_name.setText(self._analyzed_title or "Başlık bulunamadı")
        views = info.get("view_count")
        views_text = f"{int(views):,}".replace(",", ".") if views else "—"
        self.preview_meta.setText(f"{info.get('uploader') or '—'}   •   {views_text} görüntüleme")
        duration = human_duration(info.get("duration"))
        live = "CANLI" if info.get("is_live") else "Video"
        source = str(info.get("site") or "Bilinmeyen site")
        extractor = str(info.get("extractor") or "Generic")
        format_count = int(info.get("format_count") or 0)
        heights = info.get("heights") or []
        max_quality = f"{max(heights)}p" if heights else "otomatik"
        playlist_count = int(info.get("playlist_count") or 0)
        playlist_skipped = int(info.get("playlist_skipped") or 0)
        if playlist_count:
            self.playlist.setChecked(True)
        playlist_text = f"  •  Liste: {playlist_count} öğe" if playlist_count else ""
        protocols = ", ".join((info.get("protocols") or [])[:4]) or str(info.get("source_kind") or "auto")
        self.preview_details.setText(f"{live}   •   Süre: {duration}   •   {source}{playlist_text}")
        self.analysis_badge.setText("ANALİZ TAMAM")
        self.analysis_title.setText(f"{source} bağlantısı hazır")
        self.analysis_info.setText(
            f"Çözücü: {extractor}\nFormat: {format_count} seçenek  •  En yüksek: {max_quality}\nProtokol: {protocols}"
            + (f"\nAtlanacak kullanılamayan öğe: {playlist_skipped}" if playlist_skipped else "")
        )
        raw = info.get("thumbnail_bytes") or b""
        pixmap = QPixmap()
        if raw and pixmap.loadFromData(raw):
            self.thumbnail.setText("")
            self.thumbnail.setPixmap(pixmap.scaled(220, 122, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._log("Analiz tamamlandı: " + self._analyzed_title)

    def _analysis_error(self, message: str) -> None:
        self.analysis_badge.setText("ANALİZ HATASI")
        self.analysis_title.setText("Bağlantı analiz edilemedi")
        self.analysis_info.setText(message)
        self._log("Analiz hatası: " + message)
        QMessageBox.critical(self, "Analiz hatası", message)

    def _jobs_from_form(self) -> list[DownloadJob]:
        urls = split_urls(self.url_input.toPlainText())
        if not urls:
            raise ValueError("Önce en az bir geçerli bağlantı gir.")
        output = self.output_dir.text().strip()
        if not output:
            raise ValueError("Kayıt klasörünü seç.")
        media_type = "audio" if self.media_type.currentIndex() == 1 else "video"
        jobs: list[DownloadJob] = []
        for index, url in enumerate(urls):
            title = self._analyzed_title if index == 0 and len(urls) == 1 else ""
            jobs.append(
                DownloadJob(
                    job_id=uuid.uuid4().hex,
                    url=url,
                    output_dir=output,
                    media_type=media_type,
                    quality=self.quality.currentText(),
                    container=self.video_container.currentText(),
                    audio_format=self.audio_format.currentText(),
                    audio_bitrate=self.audio_bitrate.currentText(),
                    playlist=self.playlist.isChecked(),
                    playlist_subfolder=self.playlist_subfolder.isChecked(),
                    subtitles=self.subtitles.isChecked(),
                    auto_subtitles=self.auto_subtitles.isChecked(),
                    embed_thumbnail=self.embed_thumbnail.isChecked(),
                    embed_metadata=self.embed_metadata.isChecked(),
                    write_description=self.write_description.isChecked(),
                    live_from_start=self.live_from_start.isChecked(),
                    source_mode=self.source_mode.currentText(),
                    format_fallback=self.format_fallback.isChecked(),
                    cookie_browser=self.cookie_browser.currentText(),
                    cookie_profile=self.cookie_profile.text().strip(),
                    cookie_file=self.cookie_file.text().strip(),
                    proxy=self.proxy.text().strip(),
                    referer=self.referer.text().strip(),
                    user_agent=self.custom_user_agent.text().strip(),
                    concurrent_fragments=self.concurrent_fragments.value(),
                    title=title,
                )
            )
        return jobs

    def _add_to_queue(self) -> None:
        try:
            new_jobs = self._jobs_from_form()
        except ValueError as exc:
            QMessageBox.warning(self, "İndirme", str(exc))
            return
        for job in new_jobs:
            self.jobs.append(job)
            self._completed_job_ids.discard(job.job_id)
            self._append_job_row(job)
        self._update_queue_state()
        if not self.download_thread or self._stop_requested:
            self.start_button.setEnabled(True)
        self.statusBar().showMessage(f"{len(new_jobs)} iş kuyruğa eklendi", 5000)
        self._log(f"Kuyruğa {len(new_jobs)} iş eklendi.")

    def _download_now(self) -> None:
        self._add_to_queue()
        if self.jobs and not self.download_thread:
            self._switch_page(1)
            self._start_queue()

    def _set_queue_info(self, row: int, column: int, text: str, state: str = "normal") -> None:
        widget = self.queue_table.cellWidget(row, column)
        if not isinstance(widget, QLabel):
            widget = QLabel()
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.setObjectName("StatusPill" if column == 7 else "InfoPill")
            self.queue_table.setCellWidget(row, column, widget)
        widget.setText(text)
        widget.setProperty("state", state)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    @staticmethod
    def _status_state(status: str) -> str:
        lowered = status.casefold()
        if "tamam" in lowered:
            return "success"
        if "hata" in lowered or "başarısız" in lowered:
            return "error"
        if "durdur" in lowered or "iptal" in lowered:
            return "warning"
        if "indir" in lowered or "işlen" in lowered or "dönüştür" in lowered:
            return "active"
        return "waiting"

    def _append_job_row(self, job: DownloadJob) -> None:
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        self.queue_table.setRowHeight(row, 58)
        self.rows[job.job_id] = row
        self.queue_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.queue_table.setItem(row, 1, QTableWidgetItem(job.title or job.url))
        self.queue_table.setItem(row, 2, QTableWidgetItem("Ses" if job.media_type == "audio" else "Video"))
        quality = f"{job.audio_format} {job.audio_bitrate}k" if job.media_type == "audio" else f"{job.quality} / {job.container}"
        self.queue_table.setItem(row, 3, QTableWidgetItem(quality))
        progress_host = QFrame()
        progress_host.setObjectName("ProgressHost")
        progress_layout = QHBoxLayout(progress_host)
        progress_layout.setContentsMargins(7, 7, 7, 7)
        progress = RoundedProgressBar()
        progress.setObjectName("DownloadProgress")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setFormat("%p%")
        progress.setFixedHeight(26)
        progress_layout.addWidget(progress)
        self.progress_widgets[job.job_id] = progress
        self.queue_table.setCellWidget(row, 4, progress_host)
        self._set_queue_info(row, 5, "—")
        self._set_queue_info(row, 6, "—")
        self._set_queue_info(row, 7, "Bekliyor", "waiting")

    def _update_queue_state(self) -> None:
        count = len(self.jobs)
        self.queue_summary.setText("Kuyruk boş" if count == 0 else f"{count} indirme kuyruğa eklendi")
        self.queue_empty.setVisible(count == 0)
        if count == 0:
            self.queue_empty.raise_()

    def _remove_selected(self) -> None:
        if self.download_thread and not self._stop_requested:
            QMessageBox.warning(self, "Kuyruk", "Önce indirmeyi durdur.")
            return
        rows = sorted({index.row() for index in self.queue_table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "Kuyruk", "Kaldırmak için bir satır seç.")
            return
        for row in rows:
            job_id = next((jid for jid, current_row in self.rows.items() if current_row == row), None)
            if job_id:
                self.jobs = [job for job in self.jobs if job.job_id != job_id]
                self._completed_job_ids.discard(job_id)
                self.rows.pop(job_id, None)
                self.progress_widgets.pop(job_id, None)
            self.queue_table.removeRow(row)
        self._reindex_rows()
        self._update_queue_state()
        self.start_button.setEnabled(bool(self.jobs))

    def _clear_queue(self) -> None:
        if self.download_thread and not self._stop_requested:
            QMessageBox.warning(self, "Kuyruk", "Önce indirmeyi durdur.")
            return
        self.jobs.clear()
        self._completed_job_ids.clear()
        self.rows.clear()
        self.progress_widgets.clear()
        self.queue_table.setRowCount(0)
        self._restart_requested = False
        self.start_button.setText("▷  Kuyruğu başlat")
        self.start_button.setEnabled(False)
        self._update_queue_state()
        self._log("İndirme kuyruğu temizlendi.")

    def _reindex_rows(self) -> None:
        self.rows.clear()
        for row, job in enumerate(self.jobs):
            self.rows[job.job_id] = row
            item = self.queue_table.item(row, 0)
            if item:
                item.setText(str(row + 1))

    def _start_queue(self) -> None:
        if self.download_thread:
            if self._stop_requested:
                self._restart_requested = True
                self.start_button.setEnabled(False)
                self.start_button.setText("Durdurma bekleniyor…")
                self.statusBar().showMessage("Mevcut işlem durunca kuyruk yeniden başlayacak", 5000)
                self._log("Kuyruk, durdurma tamamlanınca yeniden başlatılacak.")
            return
        if not self.jobs:
            QMessageBox.information(self, "Kuyruk", "Kuyrukta indirilecek içerik yok.")
            return

        pending_jobs = [job for job in self.jobs if job.job_id not in self._completed_job_ids]
        if not pending_jobs:
            QMessageBox.information(
                self,
                "Kuyruk",
                "Kuyruktaki tüm indirmeler tamamlandı. Yeniden indirmek için kuyruğu temizleyip bağlantıları tekrar ekle.",
            )
            return

        for job in pending_jobs:
            row = self.rows.get(job.job_id)
            if row is None:
                continue
            progress = self.progress_widgets.get(job.job_id)
            if progress:
                progress.setValue(0)
            self._set_queue_info(row, 5, "—")
            self._set_queue_info(row, 6, "—")
            self._set_queue_info(row, 7, "Bekliyor", "waiting")

        self._stop_requested = False
        self._restart_requested = False
        self.download_thread = QThread(self)
        self.download_worker = DownloadWorker(pending_jobs)
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.progress.connect(self._download_progress)
        self.download_worker.status.connect(self._download_status)
        self.download_worker.log.connect(self._log)
        self.download_worker.job_finished.connect(self._job_finished)
        self.download_worker.all_finished.connect(self._downloads_finished)
        self.download_worker.all_finished.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self._download_thread_finished)
        self.download_thread.finished.connect(self.download_worker.deleteLater)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.start_button.setText("▷  Kuyruğu başlat")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.download_thread.start()
        self._log(f"İndirme kuyruğu başlatıldı. Bekleyen iş: {len(pending_jobs)}")

    def _stop_downloads(self) -> None:
        if not self.download_worker:
            return
        self._stop_requested = True
        self.download_worker.cancel()
        self.stop_button.setEnabled(False)
        self.start_button.setText("▷  Kuyruğu tekrar başlat")
        self.start_button.setEnabled(bool(self.jobs))
        self.statusBar().showMessage("Kuyruk durduruluyor; artık temizleyebilir veya satır silebilirsin", 6000)
        self._log("Durdurma istendi. Kuyruk düzenleme açıldı; mevcut parça güvenli biçimde sonlandırılıyor.")

    def _download_progress(self, job_id: str, data: dict[str, Any]) -> None:
        row = self.rows.get(job_id)
        if row is None:
            return
        progress = self.progress_widgets.get(job_id)
        if progress:
            progress.setValue(int(data.get("percent") or 0))
        speed = data.get("speed")
        speed_text = "—" if not speed else self._format_speed(float(speed))
        eta = data.get("eta")
        self._set_queue_info(row, 5, speed_text)
        self._set_queue_info(row, 6, human_duration(eta))
        title = str(data.get("title") or "")
        if title:
            self.queue_table.setItem(row, 1, QTableWidgetItem(title))

    @staticmethod
    def _format_speed(value: float) -> str:
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        index = 0
        while value >= 1024 and index < len(units) - 1:
            value /= 1024
            index += 1
        return f"{value:.1f} {units[index]}"

    def _download_status(self, job_id: str, status: str) -> None:
        row = self.rows.get(job_id)
        if row is not None:
            self._set_queue_info(row, 7, status, self._status_state(status))

    def _job_finished(self, job_id: str, success: bool, message: str) -> None:
        row = self.rows.get(job_id)
        if success:
            self._completed_job_ids.add(job_id)
        if row is not None:
            final_text = "Tamamlandı" if success else message
            self._set_queue_info(row, 7, final_text, "success" if success else self._status_state(message))
            if success and job_id in self.progress_widgets:
                self.progress_widgets[job_id].setValue(100)
        prefix = "Tamamlandı: " if success else ("Durduruldu: " if "durdur" in message.lower() else "İndirme hatası: ")
        self._log(prefix + message)

    def _downloads_finished(self) -> None:
        self.stop_button.setEnabled(False)
        if self._stop_requested:
            self.start_button.setText("▷  Kuyruğu tekrar başlat")
            self.start_button.setEnabled(bool(self.jobs))
            self.statusBar().showMessage("Kuyruk durduruldu", 6000)
            self._log("İndirme kuyruğu durduruldu.")
        else:
            pending_exists = any(job.job_id not in self._completed_job_ids for job in self.jobs)
            self.start_button.setText("▷  Kuyruğu başlat")
            self.start_button.setEnabled(pending_exists)
            self.statusBar().showMessage("Kuyruk işlemi tamamlandı", 6000)
            self._log("İndirme kuyruğu tamamlandı.")

    def _download_thread_finished(self) -> None:
        restart = self._restart_requested
        self.download_thread = None
        self.download_worker = None
        self._stop_requested = False
        self._restart_requested = False
        if restart and self.jobs:
            self.start_button.setText("▷  Kuyruğu başlat")
            self.start_button.setEnabled(False)
            QTimer.singleShot(0, self._start_queue)
            return
        pending_exists = any(job.job_id not in self._completed_job_ids for job in self.jobs)
        self.start_button.setText("▷  Kuyruğu başlat")
        self.start_button.setEnabled(pending_exists)

    def open_output_folder(self) -> None:
        path = Path(self.output_dir.text().strip() or Path.home() / "Downloads")
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ---------- tool management ----------
    def _refresh_tool_status(self) -> None:
        ffmpeg = find_ffmpeg()
        deno = find_deno()
        if ffmpeg:
            bundled_path = str(bundled_resource("tools/ffmpeg/bin"))
            label = "Uygulamayla birlikte hazır" if Path(ffmpeg) == Path(bundled_path) else f"Hazır: {ffmpeg}"
            self.ffmpeg_status.setText(label)
        else:
            self.ffmpeg_status.setText("Bulunamadı. Onar düğmesiyle FFmpeg'i yeniden hazırlayabilirsin.")
        if deno:
            bundled_deno = str(bundled_resource("tools/deno/bin"))
            deno_label = "Uygulamayla birlikte hazır" if Path(deno) == Path(bundled_deno) else f"Hazır: {deno}"
            self.deno_status.setText(deno_label)
        else:
            self.deno_status.setText("Bulunamadı. Onar düğmesiyle Deno'yu yeniden hazırlayabilirsin.")
        if ffmpeg and deno:
            self.engine_pill.setText("Motor hazır")
        elif ffmpeg:
            self.engine_pill.setText("Deno kurulmalı")
        else:
            self.engine_pill.setText("FFmpeg kurulmalı")

    def _install_ffmpeg(self) -> None:
        existing = find_ffmpeg()
        if existing:
            self.ffmpeg_progress.setVisible(True)
            self.ffmpeg_progress.setValue(100)
            self.ffmpeg_status.setText("FFmpeg doğrulandı")
            self._show_tool_notice("✓ FFmpeg uygulamayla birlikte hazır. Yeniden indirme gerekmiyor.", "success")
            QTimer.singleShot(1200, lambda: self.ffmpeg_progress.setVisible(False))
            return

        self._show_tool_notice("FFmpeg onarılıyor. İndirme arka planda devam eder; uygulama kapanmaz.", "active")
        self.install_ffmpeg_button.setEnabled(False)
        self.ffmpeg_progress.setVisible(True)
        self.ffmpeg_progress.setValue(0)
        worker = FfmpegInstallWorker()
        worker.progress.connect(self._on_ffmpeg_progress)
        worker.success.connect(lambda path: self._tool_success("FFmpeg", path))
        worker.error.connect(lambda message: self._tool_error("FFmpeg", message))
        worker.finished.connect(lambda: self._tool_finished("FFmpeg"))
        self._run_worker(worker)

    def _on_ffmpeg_progress(self, value: int, message: str) -> None:
        # Named slot instead of a tuple-returning lambda: this keeps Qt UI
        # updates deterministic when progress events arrive very quickly.
        self.ffmpeg_progress.setValue(max(0, min(100, int(value))))
        self.ffmpeg_status.setText(message)

    def _install_deno(self) -> None:
        existing = find_deno()
        if existing:
            self.deno_progress.setVisible(True)
            self.deno_progress.setValue(100)
            self.deno_status.setText("Deno doğrulandı")
            self._show_tool_notice("✓ Deno uygulamayla birlikte hazır. Yeniden indirme gerekmiyor.", "success")
            QTimer.singleShot(1200, lambda: self.deno_progress.setVisible(False))
            return

        self._show_tool_notice("Deno onarılıyor. İndirme arka planda devam eder; uygulama kapanmaz.", "active")
        self.install_deno_button.setEnabled(False)
        self.deno_progress.setVisible(True)
        self.deno_progress.setValue(0)
        worker = DenoInstallWorker()
        worker.progress.connect(self._on_deno_progress)
        worker.success.connect(lambda path: self._tool_success("Deno", path))
        worker.error.connect(lambda message: self._tool_error("Deno", message))
        worker.finished.connect(lambda: self._tool_finished("Deno"))
        self._run_worker(worker)

    def _on_deno_progress(self, value: int, message: str) -> None:
        self.deno_progress.setValue(max(0, min(100, int(value))))
        self.deno_status.setText(message)

    def _show_tool_notice(self, message: str, state: str = "normal") -> None:
        self.tool_notice.setText(message)
        self.tool_notice.setProperty("state", state)
        self.tool_notice.style().unpolish(self.tool_notice)
        self.tool_notice.style().polish(self.tool_notice)
        self.tool_notice.setVisible(True)

    def _tool_finished(self, name: str) -> None:
        if name == "FFmpeg":
            self.install_ffmpeg_button.setEnabled(True)
            QTimer.singleShot(900, lambda: self.ffmpeg_progress.setVisible(False))
        else:
            self.install_deno_button.setEnabled(True)
            QTimer.singleShot(900, lambda: self.deno_progress.setVisible(False))

    def _tool_success(self, name: str, path: str) -> None:
        self._log(f"{name} hazır: {path}")
        self._refresh_tool_status()
        self._show_tool_notice(f"✓ {name} başarıyla hazırlandı. Artık uygulamayı normal şekilde kullanabilirsin.", "success")

    def _tool_error(self, name: str, message: str) -> None:
        self._log(f"{name} kurulum hatası: {message}")
        self._show_tool_notice(f"{name} kurulamadı: {message}", "error")

    def _update_engine(self) -> None:
        self.engine_update_button.setEnabled(False)
        self.engine_update_progress.setVisible(True)
        self.engine_update_progress.setValue(0)
        worker = EngineUpdateWorker()
        worker.progress.connect(lambda value, text: (self.engine_update_progress.setValue(value), self.statusBar().showMessage(text)))
        worker.success.connect(lambda message: self._show_tool_notice(f"✓ {message}", "success"))
        worker.error.connect(lambda message: self._show_tool_notice(f"İndirme motoru güncellenemedi: {message}", "error"))
        worker.finished.connect(lambda: self.engine_update_button.setEnabled(True))
        self._run_worker(worker)

    def _open_app_data(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))

    def _open_plugin_dir(self) -> None:
        root = plugin_dir()
        (root / "yt_dlp_plugins" / "extractor").mkdir(parents=True, exist_ok=True)
        (root / "yt_dlp_plugins" / "postprocessor").mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    # ---------- app update ----------
    def _load_update_config(self) -> dict[str, str]:
        path = update_config_path()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return {"owner": str(data.get("owner", "")), "repo": str(data.get("repo", "")), "channel": str(data.get("channel", "stable"))}
        except Exception:
            pass
        return {"owner": "", "repo": "", "channel": "stable"}

    def _repository_values(self) -> tuple[str, str]:
        config = self._load_update_config()
        saved_owner = str(self.settings.value("update_owner", config.get("owner", ""))).strip()
        saved_repo = str(self.settings.value("update_repo", config.get("repo", ""))).strip()
        if self._owner_mode:
            owner_widget = getattr(self, "repo_owner", None)
            repo_widget = getattr(self, "repo_name", None)
            owner = owner_widget.text().strip() if owner_widget is not None else ""
            repo = repo_widget.text().strip() if repo_widget is not None else ""
            return owner or saved_owner, repo or saved_repo
        return saved_owner, saved_repo

    def _saved_token(self) -> str:
        if self._owner_mode:
            token_widget = getattr(self, "github_token", None)
            if token_widget is not None:
                text = token_widget.text().strip()
                if text:
                    return text
        return unprotect_secret(str(self.settings.value("github_token", "")))

    def _auto_check_updates(self) -> None:
        if self.auto_update_check.isChecked():
            owner, repo = self._repository_values()
            if owner and repo:
                self._check_updates(False)

    def _check_updates(self, manual: bool) -> None:
        if self._update_check_in_progress:
            if manual:
                QMessageBox.information(self, "Güncelleme", "Güncelleme kontrolü zaten devam ediyor.")
            return

        owner, repo = self._repository_values()
        if not owner or not repo:
            self.update_status.setText("Güncelleme deposu ayarlanmamış. Yönetici merkezinden GitHub kanalını kaydet.")
            if manual:
                QMessageBox.information(self, "Güncelleme", "Önce Yönetici merkezinden GitHub depo bilgilerini ayarla.")
            return

        self._update_check_serial += 1
        check_id = self._update_check_serial
        self._update_check_in_progress = True
        self.check_update_button.setEnabled(False)
        self.check_update_button.setText("↻  Denetleniyor…")
        self.update_progress.setVisible(True)
        self.update_progress.setRange(0, 0)
        self.update_status.setText(f"GitHub denetleniyor: {owner}/{repo}…")
        self.update_status.repaint()

        worker = UpdateCheckWorker(owner, repo, self._saved_token())
        worker.success.connect(lambda payload, cid=check_id: self._update_check_success(payload, manual, cid))
        worker.error.connect(lambda message, cid=check_id: self._update_check_error(message, manual, cid))
        worker.finished.connect(lambda cid=check_id: self._update_check_finished(cid))
        self._run_worker(worker)

        # Network/DNS/proxy problems must never leave the UI spinning forever.
        QTimer.singleShot(22000, lambda cid=check_id, m=manual: self._update_check_timeout(cid, m))

    def _update_check_timeout(self, check_id: int, manual: bool) -> None:
        if check_id != self._update_check_serial or not self._update_check_in_progress:
            return
        self._update_check_serial += 1  # Ignore late worker signals.
        self._update_check_in_progress = False
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("↻  Güncellemeleri denetle")
        self.update_progress.setRange(0, 100)
        self.update_progress.setVisible(False)
        message = "GitHub 22 saniye içinde yanıt vermedi. İnternet, VPN, proxy veya güvenlik duvarını kontrol et."
        self.update_status.setText("Güncelleme denetlenemedi: " + message)
        self._log("Güncelleme kontrol zaman aşımı: " + message)
        if manual:
            QMessageBox.warning(self, "Güncelleme zaman aşımı", message)

    def _update_check_finished(self, check_id: int) -> None:
        if check_id != self._update_check_serial:
            return
        self._update_check_in_progress = False
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("↻  Güncellemeleri denetle")
        self.update_progress.setRange(0, 100)
        self.update_progress.setVisible(False)

    def _update_check_success(self, payload: dict[str, Any], manual: bool, check_id: int) -> None:
        if check_id != self._update_check_serial:
            return
        if payload.get("newer"):
            self._pending_update = payload
            self.install_update_button.setEnabled(bool(payload.get("url")))
            self.update_status.setText(f"Yeni sürüm hazır: v{payload.get('version')} — {payload.get('name')}")
            self._log(f"Yeni uygulama sürümü bulundu: v{payload.get('version')}")
            if manual:
                QMessageBox.information(self, "Güncelleme bulundu", f"v{payload.get('version')} sürümü indirilmeye hazır.")
        else:
            self._pending_update = None
            self.install_update_button.setEnabled(False)
            self.update_status.setText(f"Kliptora güncel. Yüklü sürüm: v{APP_VERSION}")
            if manual:
                QMessageBox.information(self, "Güncelleme", "Zaten en güncel sürümü kullanıyorsun.")

    def _update_check_error(self, message: str, manual: bool, check_id: int) -> None:
        if check_id != self._update_check_serial:
            return
        self.update_status.setText("Güncelleme denetlenemedi: " + message)
        self._log("Güncelleme kontrol hatası: " + message)
        if manual:
            QMessageBox.critical(self, "Güncelleme hatası", message)

    def _download_update(self) -> None:
        if not self._pending_update:
            return
        version = str(self._pending_update.get("version") or "update")
        target = app_data_dir() / "updates" / f"{APP_SLUG}-v{version}.zip"
        self.install_update_button.setEnabled(False)
        self.update_progress.setVisible(True)
        self.update_progress.setRange(0, 100)
        worker = UpdateDownloadWorker(
            str(self._pending_update.get("url") or ""),
            target,
            str(self._pending_update.get("sha_url") or ""),
            self._saved_token(),
        )
        worker.progress.connect(lambda value, text: (self.update_progress.setValue(value), self.update_status.setText(text)))
        worker.success.connect(self._launch_updater)
        worker.error.connect(self._update_download_error)
        worker.finished.connect(lambda: self.install_update_button.setEnabled(bool(self._pending_update)))
        self._run_worker(worker)

    def _update_download_error(self, message: str) -> None:
        self.update_progress.setVisible(False)
        self.update_status.setText("Güncelleme indirilemedi: " + message)
        QMessageBox.critical(self, "Güncelleme hatası", message)

    def _launch_updater(self, package_path: str) -> None:
        target = installation_dir()
        updater_exe = target / "KliptoraUpdater.exe"
        updater_script = target / "updater.pyw"
        restart = target / "Kliptora.exe"
        try:
            if updater_exe.exists():
                command = [str(updater_exe)]
            else:
                pythonw = Path(sys.executable)
                if pythonw.name.lower() == "python.exe":
                    candidate = pythonw.with_name("pythonw.exe")
                    if candidate.exists():
                        pythonw = candidate
                command = [str(pythonw), str(updater_script)]
            command += ["--package", package_path, "--target", str(target), "--pid", str(os.getpid()), "--restart", str(restart)]
            flags = 0x08000000 | 0x00000008 if os.name == "nt" else 0
            subprocess.Popen(command, cwd=target, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            QMessageBox.information(self, "Güncelleme", "Güncelleme hazır. Kliptora kapanıp yeni sürümle yeniden açılacak.")
            QApplication.quit()
        except Exception as exc:
            QMessageBox.critical(self, "Güncelleme", f"Güncelleyici başlatılamadı:\n{exc}")

    # ---------- admin ----------
    def _unlock_admin(self) -> bool:
        salt = str(self.settings.value("admin_salt", ""))
        digest = str(self.settings.value("admin_digest", ""))
        setup = not salt or not digest
        dialog = AdminPasswordDialog(setup=setup, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        password = dialog.value()
        if setup:
            try:
                salt, digest = create_pin_record(password)
            except ValueError as exc:
                QMessageBox.warning(self, "Yönetici", str(exc))
                return False
            self.settings.setValue("admin_salt", salt)
            self.settings.setValue("admin_digest", digest)
            self._admin_unlocked = True
            QMessageBox.information(self, "Yönetici", "Yönetici hesabın oluşturuldu. Güncelleme merkezinin sahibi sensin.")
            return True
        if not verify_pin(password, salt, digest):
            QMessageBox.critical(self, "Yönetici", "Parola yanlış.")
            return False
        self._admin_unlocked = True
        return True

    def _lock_admin(self) -> None:
        self._admin_unlocked = False
        self.github_token.clear()
        self._switch_page(0)
        self.statusBar().showMessage("Yönetici merkezi kilitlendi", 4000)

    def _change_admin_password(self) -> None:
        dialog = AdminPasswordDialog(setup=True, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            salt, digest = create_pin_record(dialog.value())
            self.settings.setValue("admin_salt", salt)
            self.settings.setValue("admin_digest", digest)
            QMessageBox.information(self, "Yönetici", "Yönetici parolası değiştirildi.")

    def _save_repository_config(self) -> None:
        owner = self.repo_owner.text().strip()
        repo = self.repo_name.text().strip()
        if not owner or not repo:
            QMessageBox.warning(self, "Yayın kanalı", "Sahip ve depo adını gir.")
            return
        self.settings.setValue("update_owner", owner)
        self.settings.setValue("update_repo", repo)
        config = {"owner": owner, "repo": repo, "channel": "stable"}
        try:
            update_config_path().write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            self.repo_status.setText("Yayın kanalı uygulama paketine kaydedildi.")
        except Exception:
            self.repo_status.setText("Kanal bu bilgisayara kaydedildi; kurulum klasörü yazmaya kapalı olduğu için paket dosyasına yazılamadı.")
        QMessageBox.information(self, "Yayın kanalı", "Güncelleme kanalı kaydedildi.")

    def _save_github_token(self) -> None:
        token = self.github_token.text().strip()
        if not token:
            QMessageBox.warning(self, "GitHub", "Önce erişim anahtarını gir.")
            return
        try:
            self.settings.setValue("github_token", protect_secret(token))
            QMessageBox.information(self, "GitHub", "Erişim anahtarı Windows hesabına bağlı olarak güvenli biçimde kaydedildi.")
        except Exception as exc:
            QMessageBox.critical(self, "GitHub", f"Anahtar kaydedilemedi:\n{exc}")

    def _clear_github_token(self) -> None:
        self.settings.remove("github_token")
        self.github_token.clear()
        QMessageBox.information(self, "GitHub", "Kayıtlı erişim anahtarı silindi.")

    def _test_repository(self) -> None:
        owner, repo = self._repository_values()
        if not owner or not repo:
            QMessageBox.warning(self, "GitHub", "Sahip ve depo adını gir.")
            return
        self.test_repo_button.setEnabled(False)
        self.repo_status.setText("GitHub bağlantısı test ediliyor…")
        worker = RepositoryTestWorker(owner, repo, self._saved_token())
        worker.success.connect(self._repo_test_success)
        worker.error.connect(lambda message: self.repo_status.setText("Bağlantı hatası: " + message))
        worker.finished.connect(lambda: self.test_repo_button.setEnabled(True))
        self._run_worker(worker)

    def _repo_test_success(self, data: dict[str, Any]) -> None:
        visibility = "Özel" if data.get("private") else "Herkese açık"
        permissions = data.get("permissions") or {}
        push = "Yazma izni var" if permissions.get("push") else "Yazma izni doğrulanamadı"
        self.repo_status.setText(f"Bağlantı başarılı — {visibility} depo — {push}")

    def _choose_source_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Kaynak klasörünü seç", self.source_dir.text() or str(installation_dir()))
        if selected:
            self.source_dir.setText(selected)

    def _choose_package_path(self) -> None:
        suggested = self.package_path.text() or str(Path.home() / "Downloads" / f"{APP_SLUG}-update.zip")
        selected, _ = QFileDialog.getSaveFileName(self, "Güncelleme paketini kaydet", suggested, "ZIP paketi (*.zip)")
        if selected:
            if not selected.lower().endswith(".zip"):
                selected += ".zip"
            self.package_path.setText(selected)

    def _build_update_package(self) -> None:
        owner, repo = self._repository_values()
        version = self.release_version.text().strip().lstrip("v")
        output = self.package_path.text().strip()
        if not output:
            QMessageBox.warning(self, "Paket", "Çıktı ZIP dosyasını seç.")
            return
        if not owner or not repo:
            QMessageBox.warning(self, "Paket", "Önce GitHub depo sahibi ve depo adını gir.")
            return

        self.build_package_button.setEnabled(False)
        self.publish_button.setEnabled(False)
        self.publish_progress.setVisible(True)
        self.publish_progress.setRange(0, 100)
        self.publish_progress.setValue(15)
        self.publish_status.setText("Güvenli güncelleme paketi hazırlanıyor…")
        QApplication.processEvents()
        try:
            zip_path, checksum_path = build_update_package(
                Path(self.source_dir.text()),
                Path(output),
                version=version,
                owner=owner,
                repo=repo,
            )
            self.publish_progress.setValue(100)
            self._package_build_success({"zip": str(zip_path), "sha256": str(checksum_path)})
        except BaseException as exc:
            self._package_action_error(str(exc) or exc.__class__.__name__)
        finally:
            self.build_package_button.setEnabled(True)
            self.publish_button.setEnabled(True)

    def _package_build_success(self, result: dict[str, str]) -> None:
        self._built_package = result
        self.publish_status.setText(f"Paket hazır:\n{result.get('zip')}\nSHA-256: {result.get('sha256')}")
        self._log("Yönetici güncelleme paketi oluşturdu: " + str(result.get("zip")))
        QMessageBox.information(self, "Paket hazır", "ZIP paketi ve SHA-256 doğrulama dosyası oluşturuldu.")

    def _package_action_error(self, message: str) -> None:
        self.publish_status.setText("Hata: " + message)
        self._log("Yönetici paketi hatası: " + message)
        QMessageBox.critical(self, "Yönetici işlemi", message)

    def _publish_release(self) -> None:
        if not self._built_package or not Path(self._built_package.get("zip", "")).exists():
            QMessageBox.warning(self, "Yayınla", "Önce güncelleme paketini oluştur.")
            return
        owner, repo = self._repository_values()
        token = self._saved_token()
        if not owner or not repo or not token:
            QMessageBox.warning(self, "Yayınla", "GitHub depo bilgileri ve erişim anahtarı gerekli.")
            return
        self.publish_button.setEnabled(False)
        self.publish_progress.setVisible(True)
        self.publish_progress.setValue(0)
        worker = PublishReleaseWorker(
            owner,
            repo,
            token,
            self.release_version.text(),
            self.release_title.text(),
            self.release_notes.toPlainText(),
            self._built_package["zip"],
            self._built_package["sha256"],
            self.release_draft.isChecked(),
            self.release_prerelease.isChecked(),
        )
        worker.progress.connect(lambda value, text: (self.publish_progress.setValue(value), self.publish_status.setText(text)))
        worker.success.connect(self._publish_success)
        worker.error.connect(self._package_action_error)
        worker.finished.connect(lambda: self.publish_button.setEnabled(True))
        self._run_worker(worker)

    def _publish_success(self, result: dict[str, Any]) -> None:
        release = result.get("release") or {}
        url = str(release.get("html_url") or "")
        state = "Taslak kaydedildi" if self.release_draft.isChecked() else "Güncelleme yayınlandı"
        self.publish_status.setText(f"{state}: {url}")
        self._log(f"{state}: {url}")
        QMessageBox.information(self, "Yayın tamamlandı", f"{state}.\n\n{url}")

    # ---------- logs ----------
    def _log(self, message: str) -> None:
        self.log_box.append(message)

    def _save_diagnostic_report(self) -> None:
        try:
            import yt_dlp
            engine_version = str(getattr(getattr(yt_dlp, "version", None), "__version__", "bilinmiyor"))
        except Exception:
            engine_version = "yüklenemedi"

        suggested = Path.home() / "Downloads" / f"Kliptora-tanilama-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        selected, _ = QFileDialog.getSaveFileName(self, "Tanılama raporunu kaydet", str(suggested), "Metin dosyası (*.txt)")
        if not selected:
            return
        report = "\n".join(
            [
                "KLIPTORA TANILAMA RAPORU",
                "=" * 42,
                f"Tarih: {datetime.now().isoformat(timespec='seconds')}",
                f"Kliptora: {APP_VERSION}",
                f"yt-dlp: {engine_version}",
                f"Python: {platform.python_version()}",
                f"Sistem: {platform.platform()}",
                f"FFmpeg: {find_ffmpeg() or 'bulunamadı'}",
                f"Deno: {find_deno() or 'bulunamadı'}",
                f"Çerez tarayıcısı: {self.cookie_browser.currentText()}",
                f"Kaynak modu: {self.source_mode.currentText()}",
                f"Eşzamanlı parçalar: {self.concurrent_fragments.value()}",
                "",
                "OTURUM KAYDI",
                "-" * 42,
                sanitize_diagnostic_text(self.log_box.toPlainText()),
            ]
        )
        try:
            Path(selected).write_text(report, encoding="utf-8")
            QMessageBox.information(self, "Tanılama raporu", "Rapor kaydedildi. Token ve çerez gibi hassas değerler temizlendi.")
        except Exception as exc:
            QMessageBox.critical(self, "Tanılama raporu", f"Rapor kaydedilemedi:\n{exc}")

    def _clear_logs(self) -> None:
        self.log_box.clear()
        self.statusBar().showMessage("Oturum kaydı temizlendi", 3000)
