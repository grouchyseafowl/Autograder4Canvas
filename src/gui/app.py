"""
QApplication bootstrap for Canvas Autograder GUI.
"""
import sys
import os
from pathlib import Path

# Ensure src/ is on sys.path so gui.* and other src-level modules resolve
# correctly whether this file is run directly or as part of a package.
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui.styles import build_app_qss


def main() -> None:
    # Ensure high-DPI scaling works well on all platforms
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Autograder4Canvas")
    app.setOrganizationName("CanvasAutograder")
    app.setStyleSheet(build_app_qss())

    # --demo / --demo-hs / --demo-cc flags: skip credentials, launch in demo mode
    demo_mode    = any(f in sys.argv for f in ("--demo", "--demo-hs", "--demo-cc"))
    demo_profile = "cc" if "--demo-cc" in sys.argv else "hs"  # default to hs

    # Import here to avoid circular imports at module load time
    from credentials import get_active_profile, load_credentials
    from gui.dialogs.setup_dialog import SetupDialog
    from gui.main_window import MainWindow

    if demo_mode:
        window = MainWindow(demo_mode=True, demo_profile=demo_profile)
        window.show()
        sys.exit(app.exec())

    # Check if we have valid credentials; if not, show setup dialog first
    data = load_credentials()
    active_name, active_profile = get_active_profile(data)

    # Fall back to environment variables (set by TUI or shell profile)
    env_url = os.environ.get("CANVAS_BASE_URL", "")
    env_token = os.environ.get("CANVAS_API_TOKEN", "")
    if not active_profile.get("canvas_base_url") and env_url and env_token:
        # Persist env-var credentials so the GUI can use them going forward
        from credentials import save_credentials, profile_name_from_url
        name = profile_name_from_url(env_url)
        data["profiles"] = data.get("profiles", {})
        data["profiles"][name] = {"canvas_base_url": env_url, "canvas_api_token": env_token}
        data["active_profile"] = name
        save_credentials(data)
        active_name, active_profile = name, data["profiles"][name]

    needs_setup = not (
        active_profile.get("canvas_base_url") and active_profile.get("canvas_api_token")
    )

    if needs_setup:
        dlg = SetupDialog()
        result = dlg.exec()
        if result != SetupDialog.Accepted:
            sys.exit(0)
        # Check if the user clicked a demo button instead of saving credentials
        if getattr(dlg, "demo_requested", False):
            window = MainWindow(demo_mode=True,
                                demo_profile=getattr(dlg, "demo_profile", "hs"))
            window.show()
            sys.exit(app.exec())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
