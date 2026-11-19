"""Refresh the service's bundled synthetic samples from the workspace golden builder."""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    from openbooks_lab.golden import build

    output = Path(__file__).resolve().parent / "openbooks_server" / "samples.zip"
    with TemporaryDirectory(prefix="openbooks-samples-") as temp:
        root = Path(temp)
        build(root)
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for sample in sorted(root.glob("*/*")):
                archive.writestr(sample.relative_to(root).as_posix(), sample.read_bytes())


if __name__ == "__main__":
    main()
