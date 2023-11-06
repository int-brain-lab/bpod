from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QSpacerItem, QWidget, QTabBar
from PySide6.QtGui import QPalette, QColor


def get_darkModePalette(app=None):
    darkPalette = app.palette()
    darkPalette.setColor(QPalette.Window, QColor(53, 53, 53))
    darkPalette.setColor(QPalette.WindowText, Qt.white)
    darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.Base, QColor(42, 42, 42))
    darkPalette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
    darkPalette.setColor(QPalette.ToolTipBase, Qt.white)
    darkPalette.setColor(QPalette.ToolTipText, Qt.white)
    darkPalette.setColor(QPalette.Text, Qt.white)
    darkPalette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.Dark, QColor(35, 35, 35))
    darkPalette.setColor(QPalette.Shadow, QColor(20, 20, 20))
    darkPalette.setColor(QPalette.Button, QColor(53, 53, 53))
    darkPalette.setColor(QPalette.ButtonText, Qt.white)
    darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.BrightText, Qt.red)
    darkPalette.setColor(QPalette.Link, QColor(42, 130, 218))
    darkPalette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    darkPalette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80))
    darkPalette.setColor(QPalette.HighlightedText, Qt.white)
    darkPalette.setColor(
        QPalette.Disabled,
        QPalette.HighlightedText,
        QColor(127, 127, 127),
    )

    return darkPalette


class _Bar(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def sizeHint(self):
        return QtCore.QSize(40, 120)

    def paintEvent(self, e):
        painter = QtGui.QPainter(self)
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor("black"))
        brush.setStyle(QtCore.Qt.BrushStyle(1))
        rect = QtCore.QRect(0, 0, painter.device().width(), painter.device().height())
        painter.fillRect(rect, brush)


class _LiveDisplayElement(QWidget):
    def __init__(self, labelText: str = "", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.label = QtWidgets.QLabel()
        self.label.setText(labelText)
        self.edit = QtWidgets.QLineEdit(self.layout())
        self.edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        layout.addWidget(self.edit)

    @property
    def Text(self):
        return self.edit.text()

    @Text.setter
    def Text(self, text: Optional[str]):
        self.edit.setText(text)


class LED(QtWidgets.QAbstractButton):
    def __init__(self, size: int = 10, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.size = size
        self.setCheckable(True)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.size, self.size)

    def _trigger_refresh(self) -> None:
        print(1)
        self.update()

    def click(self) -> None:
        self.setChecked(not self.isChecked())

    def paintEvent(self, e) -> None:
        color = QtGui.QColor("red")

        wLine = round(self.size / 25) * 2

        # base color
        p1 = QtGui.QPainter(self)
        p1.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing)
        p1.setPen(
            QtGui.QPen(
                color.darker(110 if self.isChecked() else 150), wLine, Qt.SolidLine
            )
        )

        if self.isChecked():
            p1.setBrush(QtGui.QBrush(color))
        else:
            gradient = QtGui.QRadialGradient(
                self.size / 2, self.size / 5 * 4, self.size * 0.5
            )
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, color.darker(150))
            p1.setBrush(QtGui.QBrush(gradient))
        p1.drawEllipse(wLine / 2, wLine / 2, self.size - wLine, self.size - wLine)

        # glow
        if self.isChecked():
            p2 = QtGui.QPainter(self)
            p2.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing)
            p2.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
            gradient = QtGui.QRadialGradient(
                self.size / 2, self.size / 2, self.size / 2
            )
            color.setHsv(color.hue(), 255, 255)
            gradient.setColorAt(0, QtGui.QColor("white"))
            gradient.setColorAt(0.3, QtGui.QColor("yellow"))
            gradient.setColorAt(1, QtGui.QColor("transparent"))
            p2.setBrush(QtGui.QBrush(gradient))
            p2.drawEllipse(0, 0, self.size, self.size)

        # outer reflection
        p3 = QtGui.QPainter(self)
        p3.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing)
        p3.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
        x = self.size * 0.2
        y = wLine
        w = self.size * 0.6
        h = self.size * 0.5 - wLine
        gradient = QtGui.QLinearGradient(0, 0, 0, h + y)
        gradient.setColorAt(0, QtGui.QColor("white"))
        gradient.setColorAt(1, QtGui.QColor("transparent"))
        p3.setBrush(QtGui.QBrush(gradient))
        p3.drawEllipse(x, y, w, h)


class LEDArray(QWidget):
    def __init__(self, *args, **kwargs):
        super(LEDArray, self).__init__(*args, **kwargs)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(LED())
        self.layout().addWidget(LED())
        self.layout().addWidget(LED())


class LiveDisplay(QWidget):
    def __init__(self, steps=5, *args, **kwargs):
        super(LiveDisplay, self).__init__(*args, **kwargs)

        # self.setWindowFlags()

        box = QtWidgets.QGroupBox()
        # box.setTitle("Live Display")
        box.setLayout(QtWidgets.QVBoxLayout())

        elements = ["Current State", "Previous State", "Last Event", "Session Time"]
        for idx, name in enumerate(elements):
            camelName = "".join(x for x in name.title() if not x.isspace())
            widget = _LiveDisplayElement(name)
            setattr(self, camelName, widget)
            box.layout().addWidget(widget)
            if idx < len(elements) - 1:
                box.layout().addSpacing(8)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(box)


class LeftColumn(LiveDisplay):
    def __init__(self, steps=5, *args, **kwargs):
        super(LeftColumn, self).__init__(*args, **kwargs)
        self.setMinimumSize(QtCore.QSize(200, 1))
        self.setMaximumSize(QtCore.QSize(200, 16777215))

        copyright = QtWidgets.QLabel("bpod v1.0.0\nInternational Brain Lab")
        copyright.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.layout().addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        self.layout().addWidget(copyright)
        self.layout().setContentsMargins(0, 0, 0, 0)


class CenterColumn(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QVBoxLayout(self)
        # group_box = QtWidgets.QGroupBox()
        # group_box.setMinimumSize(QtCore.QSize(600, 500))
        # group_box.setMaximumSize(QtCore.QSize(16777215, 16777215))
        # group_box.setSizePolicy(
        #     QtWidgets.QSizePolicy(
        #         QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        #         QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        #     )
        # )
        # QtWidgets.QTabWidget(parent=group_box)
        # self.layout().addWidget(group_box)
        # self.layout().setContentsMargins(0, 0, 0, 0)

        self.tabWidget = QtWidgets.QTabWidget()
        self.tabOverride = QtWidgets.QWidget()
        self.tabWidget.addTab(self.tabOverride, "Override")
        self.tabEmpty = QtWidgets.QWidget()
        self.tabWidget.addTab(self.tabEmpty, "Tab 2")
        self.tabWidget.addTab(self.tabEmpty, "Tab 3")
        self.tabWidget.setMinimumSize(QtCore.QSize(600, 500))
        self.tabWidget.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.tabWidget.setSizePolicy(
            QtWidgets.QSizePolicy(
                QtWidgets.QSizePolicy.Policy.MinimumExpanding,
                QtWidgets.QSizePolicy.Policy.MinimumExpanding,
            )
        )
        self.layout().setContentsMargins(4, 4, 4, 4)
        self.layout().addWidget(self.tabWidget)

        LEDArray(parent=self.tabOverride)


class BpodDisplay(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(LeftColumn())
        self.layout().addWidget(CenterColumn())
