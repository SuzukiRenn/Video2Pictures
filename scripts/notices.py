import json
import sys
from importlib.metadata import distribution
from pathlib import Path, PurePosixPath


def bundled_notices(binaries):
    files = []
    for name in ("av", "numpy", "Pillow", "pydicom", "PyInstaller"):
        package = distribution(name)
        declared = set(package.metadata.get_all("License-File", []))
        licenses = []
        for entry in package.files or ():
            if not entry.parts[0].endswith(".dist-info") or len(entry.parts) < 2:
                continue
            parts = entry.parts[2:] if entry.parts[1] == "licenses" else entry.parts[1:]
            if not parts:
                continue
            relative = PurePosixPath(*parts)
            if relative.as_posix() in declared and relative.suffix != ".py":
                target = PurePosixPath("third-party", "wheel-notices", f"{name}-{package.version}", relative)
                licenses.append((target.as_posix(), str(package.locate_file(entry)), "DATA"))
        if not licenses:
            raise RuntimeError(f"No license files found in the installed wheel for {name}")
        files.extend(licenses)

    prefix = Path(sys.base_prefix)
    for name in ("LICENSE", "LICENSE.txt", "LICENSE_PYTHON.txt", "DLLs/tcllicense.terms", "DLLs/tklicense.terms"):
        path = prefix / name
        if path.is_file():
            files.append((f"third-party/runtime-notices/CPython/{path.name}", str(path), "DATA"))

    # Anaconda may link separate runtime packages. Keep notices from the package cache for the binaries used here.
    record_dir = prefix / "conda-meta"
    if record_dir.is_dir():
        bundled = set()
        for _, source, _ in binaries:
            path = Path(source)
            if path.is_relative_to(prefix):
                bundled.add(path.relative_to(prefix).as_posix().casefold())
        for record_path in sorted(record_dir.glob("*.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if bundled.isdisjoint(path.casefold() for path in record.get("files", ())):
                continue
            extracted = record.get("extracted_package_dir") or (record.get("link") or {}).get("source")
            package_dir = Path(extracted) if extracted else prefix / "pkgs" / record_path.stem
            licenses_dir = package_dir / "info" / "licenses"
            for path in sorted(licenses_dir.rglob("*")):
                if path.is_file():
                    target = f"third-party/runtime-notices/conda/{record_path.stem}/{path.relative_to(licenses_dir).as_posix()}"
                    files.append((target, str(path), "DATA"))
    return files
