from aqt import mw
from aqt.qt import QAction

from .setup_dialog import SetupDialog


def show_setup(addon_module: str) -> None:
    dialog = SetupDialog(addon_module)
    dialog.exec()


def register_addon(addon_module: str) -> None:
    action = QAction("Canvas Anki AI", mw)
    action.triggered.connect(lambda: show_setup(addon_module))
    mw.form.menuTools.addAction(action)
