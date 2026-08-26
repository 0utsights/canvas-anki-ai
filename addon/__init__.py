import sys
from pathlib import Path


vendor_directory = Path(__file__).resolve().parent / "vendor"
if vendor_directory.is_dir():
    sys.path.insert(0, str(vendor_directory))

from .canvas_anki_ai.bootstrap import register_addon

register_addon(__name__)
