"""Thème sombre — jetons issus de la maquette Figma « YouStrow — UI » (collection de variables YouStrow/Tokens).

Pour changer l'apparence : modifier les variables dans Figma, puis demander la ré-importation (docs/FIGMA.md) —
seul ce fichier (jetons) et la feuille de style ci-dessous sont concernés."""
from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- surfaces (Figma : surface/*)
BG = "#07080B"
PANEL = "#0E1117"
RAISED = "#151923"
RAISED_HI = "#1D2230"
# --- bordures (border/*)
BORDER = "#262C3B"
BORDER_HI = "#394258"
# --- texte (text/*)
TEXT = "#EEF1F7"
TEXT2 = "#9AA4B8"
MUTED = "#5E6980"
# --- accents (accent/*, status/*)
ACCENT = "#22D3EE"
ACCENT_DIM = "#0B3B47"
BRAND = "#FFC53D"
OK = "#34D399"
WARN = "#FBBF24"
DANGER = "#FB7185"
DANGER_DIM = "#3A1620"
VIOLET = "#A78BFA"
# --- rayons (radius/*)
R_SM, R_MD, R_LG, R_XL = 6, 10, 14, 20

PALETTE_ROWS = [  # lignes de la grille de pads (identiques à la maquette)
    ("Blanc", (244, 246, 250)), ("Rouge", (255, 24, 24)), ("Orange", (255, 128, 0)), ("Jaune", (255, 214, 0)),
    ("Vert", (0, 214, 40)), ("Cyan", (0, 200, 220)), ("Bleu", (24, 40, 255)), ("Magenta", (220, 0, 220)),
]


def qc(hexcolor: str, alpha: int = 255) -> QColor:
    c = QColor(hexcolor)
    c.setAlpha(alpha)
    return c


def app_font(size: int = 10) -> QFont:
    fams = QFontDatabase.families()
    for name in ("Inter", "Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Ubuntu", "Noto Sans", "DejaVu Sans", "Arial"):
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
QLabel#muted {{ color: {TEXT2}; }}
QLabel#h1 {{ font-size: 15px; font-weight: 600; }}
QLabel#section {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.4px; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: {R_LG}px; }}
QFrame#rail {{ background: {PANEL}; border: none; border-right: 1px solid {BORDER}; }}
QFrame#topbar {{ background: {PANEL}; border: none; border-bottom: 1px solid {BORDER}; }}
QMenuBar {{ background: transparent; color: {TEXT2}; padding: 0; }}
QMenuBar::item {{ padding: 8px 12px; border-radius: 8px; background: transparent; font-weight: 500; }}
QMenuBar::item:selected {{ background: {RAISED}; color: {TEXT}; }}
QMenu {{ background: {RAISED}; border: 1px solid {BORDER_HI}; border-radius: {R_LG}px; padding: 8px; }}
QMenu::item {{ padding: 8px 30px 8px 14px; border-radius: 8px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; color: {ACCENT}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}
QPushButton {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: {R_MD}px; padding: 8px 14px; font-weight: 500; }}
QPushButton:hover {{ background: {RAISED_HI}; border-color: {BORDER_HI}; }}
QPushButton:pressed {{ background: {ACCENT_DIM}; }}
QPushButton:disabled {{ color: {MUTED}; background: {PANEL}; }}
QPushButton#primary {{ background: {ACCENT}; color: {BG}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #5BE0F3; }}
QPushButton#danger {{ background: {DANGER_DIM}; color: {DANGER}; border-color: {DANGER}; }}
QPushButton#danger:hover {{ background: #4A1A27; }}
QPushButton#ghost {{ background: transparent; color: {TEXT2}; }}
QPushButton#ghost:hover {{ background: {RAISED}; color: {TEXT}; }}
QPushButton:checked {{ background: {ACCENT_DIM}; border-color: {ACCENT}; color: {ACCENT}; }}
QToolButton#nav {{ background: transparent; border: none; border-radius: 12px; color: {MUTED}; font-size: 9px; font-weight: 700; letter-spacing: 0.8px; }}
QToolButton#nav:hover {{ background: {RAISED}; color: {TEXT2}; }}
QToolButton#nav:checked {{ background: {ACCENT_DIM}; color: {ACCENT}; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {RAISED_HI}; }}
QListWidget::item:selected {{ background: {ACCENT_DIM}; color: {ACCENT}; }}
QPushButton#navOLD {{ background: transparent; border: none; border-radius: 12px; padding: 0; color: {MUTED}; font-size: 9px; font-weight: 700; letter-spacing: 0.8px; }}
QPushButton#nav:hover {{ background: {RAISED}; color: {TEXT2}; }}
QPushButton#nav:checked {{ background: {ACCENT_DIM}; color: {ACCENT}; border: none; }}
QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 7px 10px; selection-background-color: {ACCENT_DIM}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {RAISED}; border: 1px solid {BORDER_HI}; selection-background-color: {ACCENT_DIM}; outline: 0; }}
QTableWidget, QListWidget, QTreeWidget {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: {R_MD}px;
    gridline-color: {BORDER}; alternate-background-color: {RAISED}; selection-background-color: {ACCENT_DIM}; }}
QHeaderView::section {{ background: {RAISED}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px; font-weight: 700; font-size: 10px; letter-spacing: 0.6px; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 10px 16px; margin-right: 2px; border-bottom: 2px solid transparent; font-weight: 500; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT2}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2b313d; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4252; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #2b313d; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollArea {{ border: none; background: transparent; }}
QPlainTextEdit, QTextEdit {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: {R_MD}px; padding: 6px;
    font-family: 'Cascadia Mono', Consolas, 'Ubuntu Mono', 'DejaVu Sans Mono', monospace; font-size: 11px; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_HI}; padding: 6px; border-radius: 6px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {BORDER_HI}; background: {RAISED}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: {R_MD}px; margin-top: 12px; padding-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; color: {MUTED}; padding: 0 6px; }}
QSplitter::handle {{ background: transparent; }}
"""
