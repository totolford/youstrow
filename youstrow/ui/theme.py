"""Thème sombre : palette et feuille de style globale."""
from PySide6.QtGui import QColor, QFont, QFontDatabase

BG = "#08090c"
PANEL = "#0f1116"
RAISED = "#171a21"
RAISED_HI = "#1f232c"
BORDER = "#242933"
TEXT = "#e8ebf1"
MUTED = "#7d8697"
ACCENT = "#19d3ff"
ACCENT_DIM = "#0b4d5e"
BRAND = "#ffd60a"
OK = "#2ee59d"
WARN = "#ffb020"
DANGER = "#ff4d6a"

PALETTE_ROWS = [  # lignes de la grille de pads
    ("Blanc", (255, 255, 255)), ("Rouge", (255, 24, 24)), ("Orange", (255, 128, 0)), ("Jaune", (255, 214, 0)),
    ("Vert", (0, 214, 40)), ("Cyan", (0, 200, 220)), ("Bleu", (24, 40, 255)), ("Magenta", (220, 0, 220)),
]


def qc(hexcolor: str, alpha: int = 255) -> QColor:
    c = QColor(hexcolor)
    c.setAlpha(alpha)
    return c


def app_font(size: int = 10) -> QFont:
    fams = QFontDatabase.families()
    for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Inter", "Arial"):
        if name in fams:
            f = QFont(name, size)
            f.setStyleStrategy(QFont.PreferAntialias)
            return f
    return QFont()


STYLESHEET = f"""
* {{ outline: 0; }}
QMainWindow, QDialog, QWidget#root {{ background: {BG}; color: {TEXT}; }}
QWidget {{ color: {TEXT}; }}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#h1 {{ font-size: 15px; font-weight: 600; }}
QLabel#section {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.4px; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QMenuBar {{ background: {BG}; color: {TEXT}; padding: 4px 8px; }}
QMenuBar::item {{ padding: 6px 12px; border-radius: 6px; background: transparent; }}
QMenuBar::item:selected {{ background: {RAISED}; }}
QMenu {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}
QPushButton {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 14px; font-weight: 600; }}
QPushButton:hover {{ background: {RAISED_HI}; border-color: #343a47; }}
QPushButton:pressed {{ background: {ACCENT_DIM}; }}
QPushButton:disabled {{ color: #4b5260; background: {PANEL}; }}
QPushButton#primary {{ background: {ACCENT}; color: #00222b; border: none; }}
QPushButton#primary:hover {{ background: #5be0ff; }}
QPushButton#danger {{ background: #3a1620; color: {DANGER}; border-color: #5a2230; }}
QPushButton#danger:hover {{ background: #4a1a27; }}
QPushButton:checked {{ background: {ACCENT_DIM}; border-color: {ACCENT}; color: {ACCENT}; }}
QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {ACCENT_DIM}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {RAISED}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_DIM}; outline: 0; }}
QTableWidget, QListWidget, QTreeWidget {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px;
    gridline-color: {BORDER}; alternate-background-color: #12151b; selection-background-color: {ACCENT_DIM}; }}
QHeaderView::section {{ background: {RAISED}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px; font-weight: 700; font-size: 10px; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 9px 18px; margin-right: 2px; border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2b313d; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4252; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #2b313d; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QPlainTextEdit, QTextEdit {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px;
    font-family: Consolas, 'Cascadia Mono', monospace; font-size: 11px; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; border-radius: 6px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a4252; background: {RAISED}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 12px; padding-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; color: {MUTED}; padding: 0 6px; }}
QSplitter::handle {{ background: transparent; }}
"""
