"""
Institution profile CRUD dialog.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFormLayout, QLabel, QLineEdit, QGroupBox,
    QDialogButtonBox, QInputDialog, QMessageBox,
)
from gui.dialogs.message_dialog import show_question
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.styles import SPACING_SM, SPACING_MD


class ProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Institutions")
        self.setMinimumWidth(480)
        self.setMinimumHeight(380)
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(16, 16, 16, 16)

        top = QHBoxLayout()

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        top.addWidget(self._list, 1)

        btn_col = QVBoxLayout()
        self._add_btn = QPushButton("+ Add")
        self._add_btn.clicked.connect(self._on_add)
        btn_col.addWidget(self._add_btn)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._on_edit)
        btn_col.addWidget(self._edit_btn)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._on_delete)
        btn_col.addWidget(self._delete_btn)
        self._set_active_btn = QPushButton("Set Active")
        self._set_active_btn.clicked.connect(self._on_set_active)
        btn_col.addWidget(self._set_active_btn)
        btn_col.addStretch()
        top.addLayout(btn_col)
        layout.addLayout(top)

        # Profile detail
        detail_box = QGroupBox("Selected Profile")
        detail_form = QFormLayout(detail_box)
        self._detail_name = QLabel()
        detail_form.addRow("Name:", self._detail_name)
        self._detail_url = QLabel()
        detail_form.addRow("URL:", self._detail_url)
        self._detail_token = QLabel()
        detail_form.addRow("Token:", self._detail_token)
        layout.addWidget(detail_box)

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.accept)
        layout.addWidget(close_btn)

    # ------------------------------------------------------------------

    def _load_data(self):
        from credentials import load_credentials
        return load_credentials()

    def _save_data(self, data: dict) -> None:
        from credentials import save_credentials, set_env_from_profile
        save_credentials(data)
        set_env_from_profile(data)

    def _refresh_list(self) -> None:
        from credentials import get_active_profile
        data = self._load_data()
        active_name, _ = get_active_profile(data)
        self._list.clear()
        for name in sorted(data.get("profiles", {})):
            text = f"★ {name}" if name == active_name else f"   {name}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, name)
            if name == active_name:
                font = QFont()
                font.setBold(True)
                item.setFont(font)
            self._list.addItem(item)

    def _on_row_changed(self, row: int) -> None:
        if row < 0:
            self._detail_name.clear()
            self._detail_url.clear()
            self._detail_token.clear()
            return
        item = self._list.item(row)
        name = item.data(Qt.ItemDataRole.UserRole)
        data = self._load_data()
        p = data.get("profiles", {}).get(name, {})
        self._detail_name.setText(name)
        self._detail_url.setText(p.get("canvas_base_url", "(none)"))
        self._detail_token.setText("••••••••• (saved)" if p.get("canvas_api_token") else "(none)")

    def _on_add(self) -> None:
        url, ok = QInputDialog.getText(self, "Add Institution", "Canvas URL or school name:")
        if not ok or not url.strip():
            return
        url = url.strip().rstrip("/")
        if not url.startswith("http"):
            if "." not in url:
                url = f"https://{url}.instructure.com"
            else:
                url = "https://" + url

        from credentials import profile_name_from_url
        name = profile_name_from_url(url)

        token, ok2 = QInputDialog.getText(self, "API Token", "Paste your Canvas API token:", QLineEdit.EchoMode.Password)
        if not ok2 or not token.strip():
            return

        data = self._load_data()
        if "profiles" not in data:
            data["profiles"] = {}
        data["profiles"][name] = {"canvas_base_url": url, "canvas_api_token": token.strip()}
        data["active_profile"] = name
        self._save_data(data)
        self._refresh_list()

    def _on_edit(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        data = self._load_data()
        p = data.get("profiles", {}).get(name, {})

        url, ok = QInputDialog.getText(self, "Edit URL", "Canvas URL:",
                                        text=p.get("canvas_base_url", ""))
        if ok and url.strip():
            data["profiles"][name]["canvas_base_url"] = url.strip()

        token, ok2 = QInputDialog.getText(self, "Edit Token", "API Token (leave blank to keep current):",
                                           QLineEdit.EchoMode.Password)
        if ok2 and token.strip():
            data["profiles"][name]["canvas_api_token"] = token.strip()

        self._save_data(data)
        self._refresh_list()
        self._on_row_changed(self._list.currentRow())

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if show_question(self, "Delete Profile",
                         f"Delete profile '{name}'?") != QMessageBox.StandardButton.Yes:
            return
        data = self._load_data()
        data.get("profiles", {}).pop(name, None)
        remaining = list(data.get("profiles", {}).keys())
        if data.get("active_profile") == name:
            data["active_profile"] = remaining[0] if remaining else ""
        self._save_data(data)
        self._refresh_list()

    def _on_set_active(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        data = self._load_data()
        data["active_profile"] = name
        self._save_data(data)
        self._refresh_list()
