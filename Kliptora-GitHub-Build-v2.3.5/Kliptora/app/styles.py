APP_STYLE = r"""
* {
    font-family: "Segoe UI Variable", "Segoe UI";
    font-size: 10.4pt;
}
QWidget {
    background: transparent;
    color: #eef2ff;
}
QMainWindow, QDialog {
    background: transparent;
}
QWidget#AppRoot {
    background: qradialgradient(cx:0.1, cy:0.08, radius:1.2,
        fx:0.18, fy:0.10,
        stop:0 #12224e,
        stop:0.35 #0a1736,
        stop:0.7 #071126,
        stop:1 #050b18);
}
QFrame#AppShell {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #091227,
        stop:0.35 #081125,
        stop:0.65 #071020,
        stop:1 #060d18);
    border: 1px solid #4b59a6;
    border-radius: 28px;
}
QFrame#TopBar {
    background: transparent;
    border: none;
}
QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #081427, stop:0.55 #071120, stop:1 #060c19);
    border-right: 1px solid rgba(110, 130, 200, 0.35);
    border-top-left-radius: 28px;
    border-bottom-left-radius: 28px;
}
QFrame#BrandPanel { background: transparent; border: none; }
QFrame#Card, QFrame#ActionCard, QFrame#StatusCard, QFrame#UpdateCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #101a34, stop:0.55 #0d1730, stop:1 #0b1329);
    border: 1px solid rgba(93, 111, 177, 0.55);
    border-radius: 22px;
}
QFrame#Card:hover { border-color: rgba(136, 156, 229, 0.8); }
QFrame#StatusCard {
    background: rgba(10, 18, 36, 0.88);
    border-color: rgba(112, 132, 205, 0.45);
    border-radius: 18px;
}
QFrame#InnerPanel, QFrame#PreviewInner, QFrame#ToolRow, QFrame#EmptyPanel {
    background: rgba(7, 15, 31, 0.82);
    border: 1px solid rgba(83, 101, 163, 0.52);
    border-radius: 18px;
}
QFrame#PageIcon {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #171e43, stop:1 #0b1430);
    border: 1px solid #6750d0;
    border-radius: 18px;
}
QFrame#ThumbnailFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #171d38, stop:1 #0d1224);
    border: 1px solid rgba(92, 107, 166, 0.55);
    border-radius: 18px;
}
QFrame#QueuePanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(9, 17, 36, 0.98), stop:1 rgba(6, 12, 27, 0.98));
    border: 1px solid rgba(78, 98, 164, 0.58);
    border-radius: 22px;
}
QFrame#ProgressHost {
    background: rgba(14, 23, 47, 0.82);
    border: 1px solid rgba(70, 91, 153, 0.52);
    border-radius: 14px;
}
QLabel#InfoPill, QLabel#StatusPill {
    background: rgba(15, 25, 50, 0.9);
    border: 1px solid rgba(76, 96, 160, 0.58);
    border-radius: 13px;
    padding: 6px 9px;
    color: #dbe5ff;
    font-weight: 700;
}
QLabel#StatusPill[state="waiting"] {
    background: rgba(36, 45, 70, 0.82);
    border-color: rgba(101, 119, 173, 0.65);
    color: #cbd5ef;
}
QLabel#StatusPill[state="active"] {
    background: rgba(46, 72, 145, 0.55);
    border-color: rgba(80, 146, 255, 0.9);
    color: #d9ecff;
}
QLabel#StatusPill[state="success"] {
    background: rgba(24, 112, 73, 0.45);
    border-color: rgba(73, 224, 144, 0.82);
    color: #9cf5c5;
}
QLabel#StatusPill[state="warning"] {
    background: rgba(135, 88, 19, 0.44);
    border-color: rgba(245, 180, 66, 0.82);
    color: #ffd992;
}
QLabel#StatusPill[state="error"] {
    background: rgba(126, 37, 67, 0.48);
    border-color: rgba(244, 91, 139, 0.82);
    color: #ffc1d5;
}
QLabel#InlineNotice {
    background: rgba(29, 43, 82, 0.88);
    border: 1px solid rgba(101, 125, 204, 0.78);
    border-radius: 14px;
    padding: 10px 13px;
    color: #dbe5ff;
    font-weight: 650;
}
QLabel#InlineNotice[state="active"] {
    background: rgba(40, 66, 137, 0.48);
    border-color: rgba(85, 148, 255, 0.85);
}
QLabel#InlineNotice[state="success"] {
    background: rgba(24, 112, 73, 0.40);
    border-color: rgba(73, 224, 144, 0.78);
    color: #a4f5c9;
}
QLabel#InlineNotice[state="error"] {
    background: rgba(126, 37, 67, 0.42);
    border-color: rgba(244, 91, 139, 0.78);
    color: #ffc5d7;
}
QFrame#AccentStrip {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7c3aed, stop:0.5 #5b7cff, stop:1 #27b5ff);
    border: none;
    border-radius: 999px;
}
QLabel { background: transparent; }
QLabel#PageIconLabel { color: #ab82ff; font-size: 22pt; font-weight: 800; }
QLabel#PageTitle { font-size: 23pt; font-weight: 850; color: #ffffff; }
QLabel#PageSubtitle { color: #9eb0d6; font-size: 10.4pt; }
QLabel#BrandTitle { font-size: 19pt; font-weight: 850; color: #ffffff; }
QLabel#BrandSubtitle { color: #b4c0de; font-size: 9.4pt; }
QLabel#SectionTitle { font-size: 13.5pt; font-weight: 800; color: #ffffff; }
QLabel#CardTitle { font-size: 12pt; font-weight: 760; color: #ffffff; }
QLabel#Muted { color: #99abd2; }
QLabel#TinyMuted { color: #7d90bb; font-size: 8.9pt; }
QLabel#Accent { color: #b180ff; font-weight: 760; }
QLabel#Success { color: #60f39b; font-weight: 700; }
QLabel#Warning { color: #ffd06e; font-weight: 700; }
QLabel#DangerText { color: #ff91b6; font-weight: 700; }
QLabel#BigEmptyIcon { color: #9b58ff; font-size: 42pt; font-weight: 500; }
QLabel#BigEmptyTitle { color: #ffffff; font-size: 17pt; font-weight: 790; }
QLabel#StatusDot { color: #55e488; font-size: 12pt; }
QLabel#LogoFallback {
    color: white;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7d36e8,stop:0.55 #5e62ff,stop:1 #1dc0ff);
    border: 1px solid #9a72ff;
    border-radius: 18px;
    font-size: 25pt;
    font-weight: 850;
}
QPushButton {
    min-height: 22px;
    background: rgba(21, 31, 57, 0.96);
    border: 1px solid rgba(86, 104, 163, 0.7);
    border-radius: 16px;
    padding: 11px 16px;
    font-weight: 680;
    color: #eef2ff;
}
QPushButton:hover { background: rgba(32, 46, 82, 0.98); border-color: #7d91d9; }
QPushButton:pressed { background: rgba(13, 20, 37, 0.98); }
QPushButton:disabled { color: #64718f; background: #0c1428; border-color: #222d48; }
QPushButton#Primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7b3ef3, stop:0.45 #6b5cff, stop:1 #2da8ff);
    border: 1px solid #8c8eff;
    color: white;
    padding: 11px 22px;
}
QPushButton#Primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #9055ff, stop:0.45 #7e70ff, stop:1 #45b6ff);
    border-color: #b0b4ff;
}
QPushButton#Primary:disabled {
    background: #202846;
    border-color: #343f61;
    color: #6e7a98;
}
QPushButton#Danger { background: #351425; border-color: #83304f; color: #ffb5cc; }
QPushButton#Danger:hover { background: #4b1a31; border-color: #b94770; }
QPushButton#SuccessButton { background: #123225; border-color: #246848; color: #8df0b2; }
QPushButton#Nav {
    min-height: 34px;
    text-align: left;
    border: 1px solid transparent;
    background: transparent;
    padding: 14px 18px;
    color: #c7d3ee;
    border-radius: 18px;
    font-weight: 680;
}
QPushButton#Nav:hover { background: rgba(91, 102, 188, 0.18); color: #ffffff; }
QPushButton#Nav:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(122, 62, 242, 0.32), stop:1 rgba(44, 168, 255, 0.24));
    border: 1px solid rgba(129, 155, 255, 0.72);
    border-right: 4px solid #55e2ff;
    color: white;
}
QPushButton#LinkButton {
    background: transparent;
    border: none;
    color: #a27cff;
    text-align: left;
    padding: 4px;
}
QPushButton#LinkButton:hover { color: #c5aeff; text-decoration: underline; }
QPushButton#WindowButton, QPushButton#WindowButtonClose {
    min-width: 32px;
    max-width: 32px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    padding: 0px;
    background: transparent;
    border: 1px solid transparent;
    color: #aebde7;
    font-size: 11pt;
}
QPushButton#WindowButton:hover {
    background: rgba(110, 130, 210, 0.18);
    border-color: rgba(110, 130, 210, 0.42);
    color: white;
}
QPushButton#WindowButtonClose:hover {
    background: rgba(225, 76, 102, 0.22);
    border-color: rgba(255, 110, 131, 0.45);
    color: white;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: rgba(10, 18, 37, 0.92);
    border: 1px solid rgba(80, 99, 158, 0.75);
    border-radius: 16px;
    padding: 10px 12px;
    selection-background-color: #7242d7;
    color: #f5f7ff;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover { border-color: #7b93da; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #9b6bff;
    background: rgba(11, 20, 41, 0.96);
}
QLineEdit#UrlInput, QPlainTextEdit#UrlInput {
    border: 1px solid #7c4cf0;
    background: rgba(11, 17, 35, 0.95);
    font-size: 11pt;
    border-radius: 18px;
}
QLineEdit#UrlInput:focus, QPlainTextEdit#UrlInput:focus { border: 2px solid #9d6eff; }
QLineEdit[echoMode="2"] { letter-spacing: 2px; }
QComboBox::drop-down { border: none; width: 30px; }
QComboBox QAbstractItemView {
    background: #111a32;
    border: 1px solid #415179;
    selection-background-color: #5e3bc2;
    outline: 0;
    padding: 5px;
    border-radius: 14px;
}
QCheckBox { spacing: 8px; color: #d3daed; background: transparent; }
QCheckBox::indicator {
    width: 20px; height: 20px;
    border: 1px solid #45557d;
    border-radius: 10px;
    background: #091122;
}
QCheckBox::indicator:hover { border-color: #9f68ff; }
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7b3fe4, stop:1 #1a9fcf);
    border-color: #a17dff;
}
QTableWidget#QueueTable {
    background: transparent;
    alternate-background-color: rgba(12, 22, 44, 0.72);
    border: none;
    border-radius: 18px;
    gridline-color: transparent;
    selection-background-color: rgba(53, 77, 145, 0.72);
    selection-color: #ffffff;
    outline: 0;
}
QTableWidget#QueueTable::item {
    border: none;
    padding: 8px;
}
QTableWidget#QueueTable::item:selected {
    background: rgba(61, 88, 165, 0.68);
    border-radius: 10px;
}
QTableWidget#QueueTable QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #182444, stop:1 #111b35);
    color: #d4def4;
    padding: 12px;
    border: none;
    border-right: 1px solid rgba(64, 82, 137, 0.55);
    font-weight: 760;
}
QTableWidget#QueueTable QHeaderView::section:first {
    border-top-left-radius: 14px;
}
QTableWidget#QueueTable QHeaderView::section:last {
    border-top-right-radius: 14px;
    border-right: none;
}
QProgressBar {
    background: rgba(6, 13, 29, 0.92);
    border: 1px solid rgba(67, 87, 147, 0.72);
    border-radius: 12px;
    text-align: center;
    min-height: 22px;
    color: white;
    font-weight: 800;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1cb8ff, stop:0.35 #3978ff, stop:0.68 #7b4df2, stop:1 #cb38d8);
    border-radius: 11px;
    margin: 1px;
}
QProgressBar#DownloadProgress {
    background: rgba(5, 11, 26, 0.96);
    border: 1px solid rgba(93, 116, 191, 0.72);
    border-radius: 13px;
    color: #ffffff;
    font-size: 9.6pt;
    font-weight: 850;
}
QProgressBar#DownloadProgress::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #10c8ff, stop:0.28 #2a91ff, stop:0.62 #7857ff, stop:1 #d339df);
    border-radius: 12px;
    margin: 1px;
}
QProgressBar#ToolProgress {
    min-height: 18px;
    max-height: 18px;
    border-radius: 9px;
}
QProgressBar#ToolProgress::chunk {
    border-radius: 8px;
}
QScrollArea, QStackedWidget { border: none; background: transparent; }
QScrollArea > QWidget > QWidget, QStackedWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(82, 100, 160, 0.72); border-radius: 5px; min-height: 34px; }
QScrollBar::handle:vertical:hover { background: #6c85c4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 1px; }
QScrollBar::handle:horizontal { background: rgba(82, 100, 160, 0.72); border-radius: 5px; min-width: 34px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { background: transparent; color: transparent; border-top: none; }
QToolTip { background: #141d38; color: white; border: 1px solid #6579aa; padding: 7px; }
QTextEdit#LogViewer {
    font-family: "Cascadia Mono", "Consolas";
    font-size: 9.8pt;
    border: 1px solid #7441be;
    background: #091022;
    border-radius: 18px;
}
QDialogButtonBox QPushButton { min-width: 90px; }
QGroupBox {
    border: 1px solid #2d3a5d;
    border-radius: 18px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 700;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #c8d2ec; }
"""
