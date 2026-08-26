from concurrent.futures import Future
from typing import Any, List

from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    Qt,
)

from .canvas_client import CanvasClient, normalize_canvas_url
from .models import CanvasCourse
from .session import SESSION
from .settings import AddonSettings


class SetupDialog(QDialog):
    def __init__(self, addon_module: str) -> None:
        super().__init__(mw)
        self.addon_module = addon_module
        config = mw.addonManager.getConfig(addon_module) or {}
        self.settings = AddonSettings.from_mapping(config)
        self.courses: List[CanvasCourse] = []
        session_matches = SESSION.canvas_base_url == self.settings.canvas_base_url
        self.has_loaded_courses = session_matches and SESSION.courses_loaded
        self.loading_base_url = ""

        self.setWindowTitle("Canvas Anki AI Setup")
        self.setMinimumWidth(560)

        self.base_url = QLineEdit(self.settings.canvas_base_url)
        self.base_url.setPlaceholderText("https://school.instructure.com")
        session_token = (
            SESSION.access_token
            if SESSION.canvas_base_url == self.settings.canvas_base_url
            else ""
        )
        self.access_token = QLineEdit(session_token)
        self.access_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.access_token.setPlaceholderText("Kept in memory for this Anki session")

        form = QFormLayout()
        form.addRow("Canvas URL", self.base_url)
        form.addRow("Access token", self.access_token)

        self.load_button = QPushButton("Load Active Courses")
        self.load_button.clicked.connect(self.load_courses)

        self.course_list = QListWidget()
        self.course_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.course_list.setMinimumHeight(240)

        token_note = QLabel(
            "Your token is used only for Canvas requests and is not written to Anki's configuration."
        )
        token_note.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.save_selection)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(token_note)
        layout.addWidget(self.load_button)
        layout.addWidget(self.course_list)
        layout.addWidget(self.buttons)

        if self.has_loaded_courses:
            self.populate_courses(SESSION.courses)

    def load_courses(self) -> None:
        try:
            base_url = normalize_canvas_url(self.base_url.text())
            client = CanvasClient(base_url, self.access_token.text())
        except ValueError as error:
            QMessageBox.warning(self, "Canvas Anki AI", str(error))
            return

        self.load_button.setEnabled(False)
        self.load_button.setText("Loading…")
        self.loading_base_url = base_url
        mw.taskman.run_in_background(client.list_active_courses, self.on_courses_loaded)

    def on_courses_loaded(self, future: Future) -> None:
        self.load_button.setEnabled(True)
        self.load_button.setText("Load Active Courses")
        try:
            courses = future.result()
        except Exception as error:
            QMessageBox.critical(self, "Canvas connection failed", str(error))
            return

        if self.loading_base_url != self.settings.canvas_base_url:
            self.settings = AddonSettings(self.loading_base_url, ())
        self.has_loaded_courses = True
        SESSION.canvas_base_url = self.loading_base_url
        SESSION.access_token = self.access_token.text().strip()
        SESSION.courses = courses
        SESSION.courses_loaded = True
        self.populate_courses(courses)
        if not courses:
            QMessageBox.information(self, "Canvas Anki AI", "No active courses were found.")

    def populate_courses(self, courses: Any) -> None:
        selected_ids = set(self.settings.selected_course_ids)
        self.courses = list(courses)
        self.course_list.clear()
        for course in self.courses:
            item = QListWidgetItem(f"{course.name} ({course.course_code})")
            item.setData(Qt.ItemDataRole.UserRole, course.course_id)
            state = (
                Qt.CheckState.Checked
                if course.course_id in selected_ids
                else Qt.CheckState.Unchecked
            )
            item.setCheckState(state)
            self.course_list.addItem(item)

    def save_selection(self) -> None:
        try:
            base_url = normalize_canvas_url(self.base_url.text())
        except ValueError as error:
            QMessageBox.warning(self, "Canvas Anki AI", str(error))
            return

        selected_ids = list(self.settings.selected_course_ids)
        if self.has_loaded_courses:
            selected_ids = []
            for index in range(self.course_list.count()):
                item = self.course_list.item(index)
                if item.checkState() == Qt.CheckState.Checked:
                    selected_ids.append(item.data(Qt.ItemDataRole.UserRole))

        settings = AddonSettings(base_url, tuple(selected_ids))
        mw.addonManager.writeConfig(self.addon_module, settings.to_mapping())
        SESSION.canvas_base_url = base_url
        SESSION.access_token = self.access_token.text().strip()
        self.accept()
