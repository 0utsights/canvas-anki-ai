import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "addon"
OUTPUT_DIR = ROOT / "dist"
OUTPUT_FILE = OUTPUT_DIR / "canvas-anki-ai.ankiaddon"
REQUIREMENTS_FILE = ROOT / "requirements-addon.txt"


def build() -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with TemporaryDirectory() as temporary_directory:
        staging = Path(temporary_directory) / "addon"
        shutil.copytree(ADDON_DIR, staging)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-compile",
                "--require-hashes",
                "--requirement",
                str(REQUIREMENTS_FILE),
                "--target",
                str(staging / "vendor"),
            ],
            check=True,
        )
        with ZipFile(OUTPUT_FILE, "w", ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(staging))
    return OUTPUT_FILE


if __name__ == "__main__":
    print(build())
