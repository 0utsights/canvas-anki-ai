from aqt import mw
from aqt.qt import QAction, QMessageBox


def show_welcome() -> None:
    QMessageBox.information(
        mw,
        "Canvas Anki AI",
        "The add-on shell is installed. Canvas course setup is the next development milestone.",
    )


def register_addon() -> None:
    action = QAction("Canvas Anki AI", mw)
    action.triggered.connect(show_welcome)
    mw.form.menuTools.addAction(action)

