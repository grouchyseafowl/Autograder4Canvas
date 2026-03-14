"""
QApplication bootstrap for Canvas Autograder GUI.
"""
import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui.styles import APP_QSS


def main() -> None:
    # Ensure high-DPI scaling works well on all platforms
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Autograder4Canvas")
    app.setOrganizationName("CanvasAutograder")
    app.setStyleSheet(APP_QSS)

    # Import here to avoid circular imports at module load time
    from credentials import get_active_profile, load_credentials
    from gui.dialogs.setup_dialog import SetupDialog
    from gui.main_window import MainWindow

    # Check if we have valid credentials; if not, show setup dialog first
    data = load_credentials()
    active_name, active_profile = get_active_profile(data)
    needs_setup = not (
        active_profile.get("canvas_base_url") and active_profile.get("canvas_api_token")
    )

    if needs_setup:
        dlg = SetupDialog()
        result = dlg.exec()
        if result != SetupDialog.Accepted:
            sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
