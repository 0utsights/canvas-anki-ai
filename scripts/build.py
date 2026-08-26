from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "addon"
OUTPUT_DIR = ROOT / "dist"
OUTPUT_FILE = OUTPUT_DIR / "canvas-anki-ai.ankiaddon"


def build() -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with ZipFile(OUTPUT_FILE, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ADDON_DIR.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ADDON_DIR))
    return OUTPUT_FILE


if __name__ == "__main__":
    print(build())

