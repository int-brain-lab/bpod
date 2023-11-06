import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from widget_port import BpodDisplay, get_darkModePalette

# sys.argv += ["-platform", "wayland:darkmode=2"]
app = QApplication(sys.argv)
app.setStyle("Fusion")
# app.setPalette(get_darkModePalette(app))

main_win = QMainWindow()
main_win.setWindowTitle("Bpod Finite State Machine")
main_win.setCentralWidget(BpodDisplay())
# main_win.centralWidget().SessionTime.Text = "00:00:00.000"
main_win.show()


app.exec()
