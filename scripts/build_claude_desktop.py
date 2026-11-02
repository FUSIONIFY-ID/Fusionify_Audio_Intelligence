"""Build the Desktop Extension from a fixed set of source and runtime files."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "downloads" / "fusionify-audio.mcpb"


def build(destination):
    package = ROOT / "src" / "fusionify_audio"
    files = {
        "manifest.json": ROOT / "desktop" / "manifest.json",
        "server/launch.cjs": ROOT / "desktop" / "server" / "launch.cjs",
        "engine/README.md": ROOT / "README.md",
        "engine/pyproject.toml": ROOT / "pyproject.toml",
        "engine/uv.lock": ROOT / "uv.lock",
    }
    for source in [*package.glob("*.py"), *package.joinpath("web").glob("*")]:
        if source.is_file() and source.suffix in {".py", ".html", ".css", ".js"}:
            files["engine/" + source.relative_to(ROOT).as_posix()] = source

    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w") as archive:
        for name, source in sorted(files.items()):
            entry = ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, source.read_bytes(), compress_type=ZIP_DEFLATED)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, nargs="?", default=BUNDLE)
    build(parser.parse_args().destination)
