"""Widgets dessinés à la main : fader, curseur dégradé, grille de pads, pad XY, plan de feu."""
from __future__ import annotations

import colorsys

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme as T


def fixture_display_color(channels: list[str], values: list[int]) -> tuple[int, int, int, float]:
    """(r, g, b, intensité 0..1) d'un appareil à partir de ses valeurs DMX réellement émises."""
    d = dict(zip(channels, values))
    dim = d.get("Dim", 255) / 255
    if {"R", "G", "B"} <= d.keys():
        r, g, b = d["R"], d["G"], d["B"]
        w = d.get("W", 0)
        r, g, b = min(255, r + w), min(255, g + w), min(255, b + w)
        return r, g, b, dim if "Dim" in d else max(r, g, b) / 255
    if {"C", "M", "Y"} <= d.keys():
        r, g, b = 255 - d["C"], 255 - d["M"], 255 - d["Y"]
        return r, g, b, dim
    if "Dim" in d:
        return 255, 255, 255, dim
    if "W" in d:
        return 255, 255, 255, d["W"] / 255
    return 80, 80, 80, 0.0


class Fader(QWidget):
    valueChanged = Signal(float)

    def __init__(self, label: str = "", color: str = T.ACCENT, value: float = 0.0, default: float | None = None,
                 parent=None):
        super().__init__(parent)
        self.label, self.color, self._v = label, QColor(color), value
        self.default = value if default is None else default
        self.setMinimumSize(34, 120)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

    def value(self) -> float:
        return self._v

    def setValue(self, v: float, emit: bool = False) -> None:
        v = min(max(v, 0.0), 1.0)
        if v != self._v:
            self._v = v
            self.update()
            if emit:
                self.valueChanged.emit(v)

    def _track(self) -> QRectF:
        return QRectF(self.width() / 2 - 3, 12, 6, self.height() - 12 - 26)

    def _from_pos(self, y: float) -> float:
        tr = self._track()
        return 1 - (y - tr.top()) / tr.height()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setValue(self._from_pos(e.position().y()), True)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.setValue(self._from_pos(e.position().y()), True)

    def mouseDoubleClickEvent(self, e):
        self.setValue(self.default, True)

    def wheelEvent(self, e):
        self.setValue(self._v + (0.03 if e.angleDelta().y() > 0 else -0.03), True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tr = self._track()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.RAISED_HI))
        p.drawRoundedRect(tr, 3, 3)
        y = tr.bottom() - tr.height() * self._v
        g = QLinearGradient(0, tr.bottom(), 0, tr.top())
        g.setColorAt(0, self.color.darker(220)); g.setColorAt(1, self.color)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(tr.left(), y, tr.width(), tr.bottom() - y), 3, 3)
        # poignée
        h = QRectF(self.width() / 2 - 14, y - 7, 28, 14)
        glow = QColor(self.color); glow.setAlpha(70)
        p.setBrush(glow); p.drawRoundedRect(h.adjusted(-3, -3, 3, 3), 8, 8)
        p.setBrush(QColor("#f2f4f8")); p.drawRoundedRect(h, 5, 5)
        p.setPen(QColor(T.MUTED)); f = QFont(self.font()); f.setPointSize(8); p.setFont(f)
        p.drawText(QRectF(0, self.height() - 22, self.width(), 18), Qt.AlignCenter, self.label)


class GradientSlider(QWidget):
    """Curseur horizontal dont la piste affiche un dégradé (teinte, luminosité…)."""
    valueChanged = Signal(float)

    def __init__(self, stops: list[tuple[float, str]], parent=None):
        super().__init__(parent)
        self.stops, self._v = stops, 0.0
        self.setFixedHeight(26)
        self.setCursor(Qt.PointingHandCursor)

    def set_stops(self, stops):
        self.stops = stops
        self.update()

    def value(self): return self._v

    def setValue(self, v, emit=False):
        v = min(max(v, 0.0), 1.0)
        if v != self._v:
            self._v = v; self.update()
            if emit: self.valueChanged.emit(v)

    def _set_from(self, x):
        self.setValue((x - 10) / max(1, self.width() - 20), True)

    def mousePressEvent(self, e): self._set_from(e.position().x())
    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton: self._set_from(e.position().x())

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(10, self.height() / 2 - 5, self.width() - 20, 10)
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        for pos, col in self.stops: g.setColorAt(pos, QColor(col))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(r, 5, 5)
        x = r.left() + r.width() * self._v
        p.setBrush(QColor(0, 0, 0, 90)); p.drawEllipse(QPointF(x, self.height() / 2 + 1), 10, 10)
        p.setBrush(QColor("#f5f7fa")); p.drawEllipse(QPointF(x, self.height() / 2), 9, 9)


class PadGrid(QWidget):
    """Grille 8×8 : 8 lignes de couleurs × 8 colonnes (groupes). Voyants de ligne à droite."""
    padClicked = Signal(int, int)    # ligne, colonne
    rowClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active: dict[int, int] = {}          # colonne -> ligne active
        self.enabled_cols: set[int] = set(range(8))
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return int(w * 0.98)

    def _geom(self):
        w = self.width(); cell = (w - 26) / 8.0
        return cell

    def _hit(self, pos):
        cell = self._geom()
        c, r = int(pos.x() // cell), int(pos.y() // cell)
        return r, c

    def mousePressEvent(self, e):
        r, c = self._hit(e.position())
        if 0 <= r < 8 and 0 <= c < 8 and c in self.enabled_cols: self.padClicked.emit(r, c)
        elif 0 <= r < 8 and c >= 8: self.rowClicked.emit(r)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cell = self._geom(); pad = cell - 5
        for r, (_, rgb) in enumerate(T.PALETTE_ROWS):
            for c in range(8):
                x, y = c * cell + 2.5, r * cell + 2.5
                on = self.active.get(c) == r
                dead = c not in self.enabled_cols
                base = QColor(*rgb)
                col = QColor(base.red() // 5, base.green() // 5, base.blue() // 5) if not on else base
                if dead: col = QColor(T.RAISED)
                rect = QRectF(x, y, pad, pad)
                if on:
                    glow = QColor(base); glow.setAlpha(90)
                    p.setPen(Qt.NoPen); p.setBrush(glow); p.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 10, 10)
                g = QLinearGradient(x, y, x, y + pad)
                g.setColorAt(0, col.lighter(125) if on else col.lighter(115)); g.setColorAt(1, col)
                p.setPen(QPen(QColor(255, 255, 255, 70 if on else 14), 1)); p.setBrush(g)
                p.drawRoundedRect(rect, 8, 8)
            # voyant de ligne
            p.setPen(Qt.NoPen); p.setBrush(QColor(*T.PALETTE_ROWS[r][1]).darker(250))
            p.drawRoundedRect(QRectF(8 * cell + 4, r * cell + cell / 2 - 5, 12, 10), 4, 4)


class PositionPad(QWidget):
    """Pavé XY pour Pan / Tilt."""
    moved = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pan = self.tilt = 0.5
        self.setMinimumSize(110, 110)
        self.setCursor(Qt.CrossCursor)

    def set_position(self, pan, tilt):
        self.pan, self.tilt = pan, tilt; self.update()

    def _set(self, pos):
        r = self.rect().adjusted(8, 8, -8, -8)
        self.pan = min(max((pos.x() - r.left()) / r.width(), 0.0), 1.0)
        self.tilt = min(max(1 - (pos.y() - r.top()) / r.height(), 0.0), 1.0)
        self.update(); self.moved.emit(self.pan, self.tilt)

    def mousePressEvent(self, e): self._set(e.position())
    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton: self._set(e.position())
    def mouseDoubleClickEvent(self, e): self.pan = self.tilt = 0.5; self.update(); self.moved.emit(.5, .5)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect().adjusted(8, 8, -8, -8))
        p.setPen(QPen(QColor(T.BORDER), 1)); p.setBrush(QColor(T.PANEL)); p.drawRoundedRect(r, 10, 10)
        p.setPen(QPen(QColor(T.BORDER), 1, Qt.DashLine))
        p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
        c = QPointF(r.left() + r.width() * self.pan, r.top() + r.height() * (1 - self.tilt))
        glow = QRadialGradient(c, 22); glow.setColorAt(0, QColor(25, 211, 255, 150)); glow.setColorAt(1, QColor(25, 211, 255, 0))
        p.setPen(Qt.NoPen); p.setBrush(glow); p.drawEllipse(c, 22, 22)
        p.setBrush(QColor(T.ACCENT)); p.drawEllipse(c, 6, 6)


class StagePlan(QWidget):
    """Plan de feu 2D : chaque appareil est affiché avec la couleur réellement émise en DMX."""
    selectionChanged = Signal(list)
    fixtureMoved = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.selected: set[int] = set()
        self._drag = None
        self._rubber: QRectF | None = None
        self.setMinimumSize(300, 250)
        self.setMouseTracking(True)
        t = QTimer(self); t.setInterval(33); t.timeout.connect(self.update); t.start()

    def _area(self) -> QRectF:
        return QRectF(self.rect().adjusted(14, 22, -14, -22))

    def _pos(self, fx) -> QPointF:
        a = self._area()
        return QPointF(a.left() + fx.x * a.width(), a.top() + fx.y * a.height())

    def _hit(self, pt: QPointF):
        for fx in reversed(self.ctl.console.patch.fixtures):
            c = self._pos(fx)
            if (c.x() - pt.x()) ** 2 + (c.y() - pt.y()) ** 2 <= 18 ** 2:
                return fx
        return None

    def select(self, ids):
        self.selected = set(ids); self.selectionChanged.emit(sorted(self.selected)); self.update()

    def mousePressEvent(self, e):
        fx = self._hit(e.position())
        if e.button() != Qt.LeftButton: return
        if fx:
            if e.modifiers() & Qt.ShiftModifier:
                self.selected ^= {fx.id}
            elif fx.id not in self.selected:
                self.selected = {fx.id}
            self._drag = (e.position(), {f.id: (f.x, f.y) for f in self.ctl.console.patch.fixtures if f.id in self.selected})
        else:
            if not e.modifiers() & Qt.ShiftModifier: self.selected = set()
            self._rubber = QRectF(e.position(), e.position())
        self.selectionChanged.emit(sorted(self.selected)); self.update()

    def mouseMoveEvent(self, e):
        if self._drag:
            start, orig = self._drag; a = self._area()
            dx, dy = (e.position().x() - start.x()) / a.width(), (e.position().y() - start.y()) / a.height()
            for f in self.ctl.console.patch.fixtures:
                if f.id in orig:
                    f.x, f.y = min(max(orig[f.id][0] + dx, 0.0), 1.0), min(max(orig[f.id][1] + dy, 0.0), 1.0)
        elif self._rubber:
            self._rubber.setBottomRight(e.position())
            r = self._rubber.normalized()
            ids = {f.id for f in self.ctl.console.patch.fixtures if r.contains(self._pos(f))}
            self.selected = ids | (self.selected if e.modifiers() & Qt.ShiftModifier else set())
            self.selectionChanged.emit(sorted(self.selected))
        self.update()

    def mouseReleaseEvent(self, e):
        if self._drag:
            self.fixtureMoved.emit()
        self._drag = self._rubber = None; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        a = self._area()
        bg = QLinearGradient(0, a.top(), 0, a.bottom())
        bg.setColorAt(0, QColor("#0d1018")); bg.setColorAt(1, QColor("#150f0b"))
        p.setPen(QPen(QColor(T.BORDER), 1)); p.setBrush(bg); p.drawRoundedRect(a.adjusted(-6, -6, 6, 6), 14, 14)
        p.setPen(QPen(QColor(255, 255, 255, 9), 1))
        for i in range(1, 8): p.drawLine(QPointF(a.left() + a.width() * i / 8, a.top()), QPointF(a.left() + a.width() * i / 8, a.bottom()))
        for i in range(1, 5): p.drawLine(QPointF(a.left(), a.top() + a.height() * i / 5), QPointF(a.right(), a.top() + a.height() * i / 5))
        f = QFont(self.font()); f.setPointSize(7); f.setBold(True); f.setLetterSpacing(QFont.AbsoluteSpacing, 1.5); p.setFont(f)
        p.setPen(QColor(T.MUTED)); p.drawText(QRectF(a.left(), a.top() - 20, a.width(), 14), Qt.AlignCenter, "CONTRE / HAUT")
        p.drawText(QRectF(a.left(), a.bottom() + 6, a.width(), 14), Qt.AlignCenter, "FACE / EAU")
        fixtures = self.ctl.console.patch.fixtures
        if not fixtures:
            p.setPen(QColor(T.MUTED)); f.setBold(False); f.setPointSize(10); p.setFont(f)
            p.drawText(a, Qt.AlignCenter, "Aucun appareil patché\nEdition ▸ Patch DMX pour en ajouter")
        snaps = [u.snapshot() for u in self.ctl.console.universes]
        for fx in fixtures:
            c = self._pos(fx)
            vals = list(snaps[fx.universe][fx.address - 1: fx.end_address]) if 0 <= fx.universe < len(snaps) else []
            r, g, b, inten = fixture_display_color(fx.channels, vals) if vals else (80, 80, 80, 0)
            col = QColor(r, g, b)
            if inten > 0.02 and max(r, g, b) > 4:
                glow = QRadialGradient(c, 34)
                gc = QColor(col); gc.setAlpha(int(200 * inten)); glow.setColorAt(0, gc)
                gc2 = QColor(col); gc2.setAlpha(0); glow.setColorAt(1, gc2)
                p.setPen(Qt.NoPen); p.setBrush(glow); p.drawEllipse(c, 34, 34)
            body = QColor(col.red() * inten + 22 * (1 - inten), col.green() * inten + 24 * (1 - inten), col.blue() * inten + 30 * (1 - inten))
            sel = fx.id in self.selected
            p.setPen(QPen(QColor(T.ACCENT) if sel else QColor(255, 255, 255, 70), 2 if sel else 1.2))
            p.setBrush(body)
            if "Moving" in fx.fixture_type or "Pan" in fx.channels:
                path = QPainterPath(); path.addRoundedRect(QRectF(c.x() - 11, c.y() - 11, 22, 22), 6, 6); p.drawPath(path)
            else:
                p.drawEllipse(c, 11, 11)
            if fx.stand:                                   # petit trépied sous l'appareil
                p.setPen(QPen(QColor(T.MUTED), 1.2))
                for dx in (-7, 0, 7): p.drawLine(QPointF(c.x(), c.y() + 11), QPointF(c.x() + dx, c.y() + 21))
            p.setPen(QColor(T.TEXT if sel else T.MUTED)); f.setPointSize(7); f.setBold(False); p.setFont(f)
            p.drawText(QRectF(c.x() - 40, c.y() + (24 if fx.stand else 14), 80, 12), Qt.AlignCenter, str(fx.id))
        if self._rubber:
            p.setPen(QPen(QColor(T.ACCENT), 1, Qt.DashLine)); p.setBrush(QColor(25, 211, 255, 25))
            p.drawRect(self._rubber.normalized())
