from concurrent.futures import Future
from typing import Any, Dict, List, Tuple

from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    Qt,
)

from .canvas_client import CanvasClient, normalize_canvas_url
from .content_extractor import extract_content
from .content_preparation import prepare_corpus
from .material_ranking import RankedMaterial, rank_current_material
from .models import CanvasCourse, CanvasItemKind, ExtractedContent
from .session import SESSION
from .settings import AddonSettings
from .study_models import PreparedCorpus


class SetupDialog(QDialog):
    def __init__(self, addon_module: str) -> None:
        super().__init__(mw)
        self.addon_module = addon_module
        config = mw.addonManager.getConfig(addon_module) or {}
        self.settings = AddonSettings.from_mapping(config)
        self.courses: List[CanvasCourse] = []
        self.scanning_client = None
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

        self.preview_button = QPushButton("Preview Current Material")
        self.preview_button.clicked.connect(self.preview_current_material)

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
        layout.addWidget(self.preview_button)
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

    def preview_current_material(self) -> None:
        try:
            base_url = normalize_canvas_url(self.base_url.text())
            client = CanvasClient(base_url, self.access_token.text())
        except ValueError as error:
            QMessageBox.warning(self, "Canvas Anki AI", str(error))
            return

        course_ids = self.selected_course_ids()
        if not course_ids:
            QMessageBox.warning(
                self,
                "Canvas Anki AI",
                "Select at least one course before previewing material.",
            )
            return

        self.preview_button.setEnabled(False)
        self.preview_button.setText("Scanning Modules…")
        self.scanning_client = client

        def discover() -> Tuple[RankedMaterial, ...]:
            modules = []
            for course_id in course_ids:
                modules.extend(client.list_course_modules(course_id))
            return rank_current_material(modules)

        mw.taskman.run_in_background(discover, self.on_material_discovered)

    def on_material_discovered(self, future: Future) -> None:
        self.preview_button.setEnabled(True)
        self.preview_button.setText("Preview Current Material")
        try:
            materials = future.result()
        except Exception as error:
            QMessageBox.critical(self, "Canvas scan failed", str(error))
            return

        course_names: Dict[int, str] = {
            course.course_id: course.name for course in self.courses
        }
        if self.scanning_client is None:
            QMessageBox.critical(self, "Canvas scan failed", "Canvas session was lost.")
            return
        dialog = MaterialPreviewDialog(
            materials,
            course_names,
            self.selected_course_ids(),
            self.scanning_client,
            self,
        )
        dialog.exec()

    def selected_course_ids(self) -> Tuple[int, ...]:
        if not self.has_loaded_courses:
            return self.settings.selected_course_ids
        selected_ids = []
        for index in range(self.course_list.count()):
            item = self.course_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected_ids.append(item.data(Qt.ItemDataRole.UserRole))
        return tuple(selected_ids)

    def save_selection(self) -> None:
        try:
            base_url = normalize_canvas_url(self.base_url.text())
        except ValueError as error:
            QMessageBox.warning(self, "Canvas Anki AI", str(error))
            return

        selected_ids = self.selected_course_ids()

        settings = AddonSettings(base_url, selected_ids)
        mw.addonManager.writeConfig(self.addon_module, settings.to_mapping())
        SESSION.canvas_base_url = base_url
        SESSION.access_token = self.access_token.text().strip()
        self.accept()


class MaterialPreviewDialog(QDialog):
    def __init__(
        self,
        materials: Tuple[RankedMaterial, ...],
        course_names: Dict[int, str],
        course_ids: Tuple[int, ...],
        client: CanvasClient,
        parent: QDialog,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Current Canvas Material")
        self.resize(760, 520)
        self.client = client
        self.course_ids = course_ids

        explanation = QLabel(
            "Items are ranked from Canvas dates, module state, module position, and source type. "
            "This is a priority preview; no course files have been sent to AI."
        )
        explanation.setWordWrap(True)

        self.material_list = QListWidget()
        supported_kinds = {
            CanvasItemKind.PAGE,
            CanvasItemKind.FILE,
            CanvasItemKind.ASSIGNMENT,
            CanvasItemKind.QUIZ,
            CanvasItemKind.DISCUSSION,
        }
        for index, material in enumerate(materials):
            source = material.item
            course_name = course_names.get(source.course_id, f"Course {source.course_id}")
            label = (
                f"[{material.score:+d}] {course_name} › {source.module_name} › "
                f"{source.title} ({source.kind.value})"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, source)
            should_extract = (
                index < 25
                and material.score >= 40
                and source.kind in supported_kinds
                and bool(source.api_url)
            )
            item.setCheckState(
                Qt.CheckState.Checked if should_extract else Qt.CheckState.Unchecked
            )
            details = "; ".join(material.reasons)
            if source.due_at:
                details += f"; due {source.due_at.isoformat()}"
            if source.html_url:
                details += f"\n{source.html_url}"
            item.setToolTip(details)
            self.material_list.addItem(item)

        if not materials:
            self.material_list.addItem("No published module material was found.")

        self.include_syllabi = QCheckBox("Include course syllabi")
        self.include_syllabi.setChecked(True)
        self.extract_button = QPushButton("Extract Selected Content")
        self.extract_button.clicked.connect(self.extract_selected)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.material_list)
        layout.addWidget(self.include_syllabi)
        layout.addWidget(self.extract_button)
        layout.addWidget(buttons)

    def extract_selected(self) -> None:
        selected_items = []
        for index in range(self.material_list.count()):
            item = self.material_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                source = item.data(Qt.ItemDataRole.UserRole)
                if source:
                    selected_items.append(source)

        if not selected_items and not self.include_syllabi.isChecked():
            QMessageBox.warning(
                self, "Canvas Anki AI", "Select material or include a syllabus first."
            )
            return
        if len(selected_items) > 30:
            QMessageBox.warning(
                self,
                "Canvas Anki AI",
                "Select no more than 30 items in one extraction batch.",
            )
            return

        include_syllabi = self.include_syllabi.isChecked()
        self.extract_button.setEnabled(False)
        self.extract_button.setText("Extracting…")

        def extract_batch():
            extracted = []
            errors = []
            for source in selected_items:
                try:
                    extracted.append(extract_content(self.client.fetch_item_content(source)))
                except Exception as error:
                    errors.append(f"{source.title}: {error}")
            if include_syllabi:
                for course_id in self.course_ids:
                    try:
                        syllabus = self.client.fetch_course_syllabus(course_id)
                        if syllabus:
                            extracted.append(extract_content(syllabus))
                    except Exception as error:
                        errors.append(f"Course {course_id} syllabus: {error}")
            return tuple(extracted), tuple(errors)

        mw.taskman.run_in_background(extract_batch, self.on_content_extracted)

    def on_content_extracted(self, future: Future) -> None:
        self.extract_button.setEnabled(True)
        self.extract_button.setText("Extract Selected Content")
        try:
            extracted, errors = future.result()
        except Exception as error:
            QMessageBox.critical(self, "Canvas extraction failed", str(error))
            return
        dialog = ExtractionPreviewDialog(extracted, errors, self)
        dialog.exec()


class ExtractionPreviewDialog(QDialog):
    def __init__(
        self,
        extracted: Tuple[ExtractedContent, ...],
        errors: Tuple[str, ...],
        parent: QDialog,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Extracted Canvas Content")
        self.resize(820, 620)
        self.extracted = extracted

        summary = QLabel(
            f"Extracted {len(extracted)} sources with {len(errors)} errors. "
            "Content remains local and has not been sent to AI."
        )
        summary.setWordWrap(True)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(self._preview_text(extracted, errors))

        self.prepare_button = QPushButton("Prepare Local Study Corpus")
        self.prepare_button.clicked.connect(self.prepare_study_corpus)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addWidget(preview)
        layout.addWidget(self.prepare_button)
        layout.addWidget(buttons)

    def prepare_study_corpus(self) -> None:
        self.prepare_button.setEnabled(False)
        self.prepare_button.setText("Preparing…")
        mw.taskman.run_in_background(
            lambda: prepare_corpus(self.extracted), self.on_corpus_prepared
        )

    def on_corpus_prepared(self, future: Future) -> None:
        self.prepare_button.setEnabled(True)
        self.prepare_button.setText("Prepare Local Study Corpus")
        try:
            corpus = future.result()
        except Exception as error:
            QMessageBox.critical(self, "Study preparation failed", str(error))
            return
        dialog = PreparedCorpusDialog(corpus, self)
        dialog.exec()

    @staticmethod
    def _preview_text(
        extracted: Tuple[ExtractedContent, ...], errors: Tuple[str, ...]
    ) -> str:
        parts = []
        remaining_characters = 200_000
        for content in extracted:
            if remaining_characters <= 0:
                break
            parts.append(f"# {content.payload.title}")
            for section in content.sections:
                if remaining_characters <= 0:
                    break
                text = section.text[: min(2500, remaining_characters)]
                remaining_characters -= len(text)
                if len(text) < len(section.text):
                    text += "\n[…preview truncated…]"
                parts.append(f"\n## {section.location}\n{text}")
        if remaining_characters <= 0:
            parts.append("\n[…overall preview limit reached…]")
        if errors:
            parts.append("\n# Extraction Errors\n" + "\n".join(f"- {error}" for error in errors))
        return "\n\n".join(parts) or "No extractable content was found."


class PreparedCorpusDialog(QDialog):
    def __init__(self, corpus: PreparedCorpus, parent: QDialog) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prepared Study Corpus")
        self.resize(840, 640)

        estimated_tokens = sum(chunk.estimated_tokens for chunk in corpus.included)
        summary = QLabel(
            f"Prepared {len(corpus.included)} instructional/uncertain chunks "
            f"(~{estimated_tokens:,} tokens) and excluded {len(corpus.excluded)} "
            "high-confidence logistics chunks. Nothing has been sent to AI."
        )
        summary.setWordWrap(True)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(self._corpus_text(corpus))

        provider_note = QLabel(
            "The provider-neutral AI contract is ready, but no provider is configured yet. "
            "The next step will send only approved included chunks for concept analysis."
        )
        provider_note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addWidget(preview)
        layout.addWidget(provider_note)
        layout.addWidget(buttons)

    @staticmethod
    def _corpus_text(corpus: PreparedCorpus) -> str:
        parts = ["# Included Chunks"]
        remaining_characters = 200_000
        for chunk in corpus.included:
            if remaining_characters <= 0:
                break
            entry = (
                f"[{chunk.category.value}] {chunk.chunk_id} | "
                f"{chunk.locator.source_title} | {chunk.locator.location}\n{chunk.text}"
            )
            entry = entry[:remaining_characters]
            remaining_characters -= len(entry)
            parts.append(entry)
        if corpus.excluded and remaining_characters > 0:
            parts.append("# Excluded Logistics")
            for chunk in corpus.excluded:
                if remaining_characters <= 0:
                    break
                entry = (
                    f"{chunk.chunk_id} | {chunk.locator.source_title} | "
                    f"{chunk.locator.location}\n{chunk.text}"
                )
                entry = entry[:remaining_characters]
                remaining_characters -= len(entry)
                parts.append(entry)
        if remaining_characters <= 0:
            parts.append("[…overall preview limit reached…]")
        return "\n\n".join(parts)
